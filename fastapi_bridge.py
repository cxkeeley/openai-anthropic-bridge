import os
import json
import logging
import logging.handlers
import httpx
import time
import sys
import uuid
import re
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# --- 1. Logging ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "bridge.log")

# Auto-cleanup if Docker/System created a directory named 'bridge.log'
if os.path.isdir(LOG_PATH):
    import shutil
    shutil.rmtree(LOG_PATH)

log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=10*1024*1024, backupCount=3)
file_handler.setFormatter(log_formatter)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
logger = logging.getLogger("Bridge")
logger.info(f"BRIDGE LOGGING TO: {LOG_PATH}")

# --- 2. Configuration ---
TARGET_URL = os.environ.get("JTIU_TARGET_URL", "")
API_TOKEN = os.environ.get("JTIU_TOKEN", "")
MODEL_NAME = os.environ.get("JTIU_MODEL", "")
SYSTEM_OVERRIDE = os.environ.get("JTIU_SYSTEM_OVERRIDE", "")
SSL_VERIFY = os.environ.get("JTIU_SSL_VERIFY", "true").lower() == "true"

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = os.environ.get("JTIU_RATE_LIMIT_ENABLED", "false").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.environ.get("JTIU_RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = float(os.environ.get("JTIU_RATE_LIMIT_WINDOW", "60.0"))

# Model Parameters Configuration
MODEL_PARAMS = os.environ.get("JTIU_MODEL_PARAMS", "")

# --- 3. Rate Limiter ---
class RateLimiter:
    """Simple sliding window rate limiter"""
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []

    def is_allowed(self) -> bool:
        """Check if a request is allowed under the rate limit"""
        # Check environment variable at runtime
        rate_limit_enabled = os.environ.get("JTIU_RATE_LIMIT_ENABLED", "false").lower() == "true"
        if not rate_limit_enabled:
            return True

        now = time.time()
        # Remove old requests outside the window
        self.requests = [t for t in self.requests if now - t < self.window_seconds]

        if len(self.requests) >= self.max_requests:
            return False

        self.requests.append(now)
        return True

    def get_retry_after(self) -> int:
        """Get the retry-after value in seconds
        """
        if not self.requests:
            return 0
        oldest = min(self.requests)
        retry_after = int(self.window_seconds - (time.time() - oldest))
        return max(1, retry_after)

# Global rate limiter instance
rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)

# --- 4. Core Utility ---
def validate_tool_call_id(tool_call_id: str) -> bool:
    """
    Validate that a tool call ID matches the expected format.
    Expected format: 'call_' followed by alphanumeric characters, underscores, hyphens, and dots
    """
    if not tool_call_id:
        return False
    # Claude/Anthropic tool call IDs typically start with 'call_' followed by alphanumeric chars
    pattern = r'^call_[a-zA-Z0-9_.-]+$'
    return bool(re.match(pattern, tool_call_id))


def generate_tool_call_id(idx: int) -> str:
    """
    Generate a valid tool call ID that matches expected format
    """
    return f"call_{uuid.uuid4().hex}_{idx}"


def get_model_params() -> Dict[str, Any]:
    """
    Get model parameters from environment or use defaults.
    Returns a dict with model_params structure for JiuTian API.
    """
    import os
    import json

    # Try to load from environment variable
    env_params = os.environ.get("JTIU_MODEL_PARAMS", "")
    if env_params:
        try:
            return json.loads(env_params)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JTIU_MODEL_PARAMS, using defaults")

    # Default model parameters
    return {
        "text": {
            "temperature": 0.2,
            "max_tokens": 8192,
            "presence_penalty": 1.1,
            "frequency_penalty": 0.3,
            "top_p": 0.9
        }
    }


def robust_parse_args(raw: str) -> dict:
    if not raw: return {}
    
    # --- Stack-Based JSON Repair for Truncated Outputs ---
    processed_raw = raw.strip()
    if not processed_raw.endswith(('}', ']')):
        stack = []
        # Basic scanning for unclosed symbols (ignoring strings for simplicity, but improved)
        in_string = False
        escape = False
        for char in processed_raw:
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in '{[':
                    stack.append(char)
                elif char in '}]':
                    if stack:
                        # Only pop if it matches (very basic validation)
                        if (char == '}' and stack[-1] == '{') or (char == ']' and stack[-1] == '['):
                            stack.pop()
        
        # Close remaining items in reverse order
        while stack:
            opener = stack.pop()
            processed_raw += '}' if opener == '{' else ']'
        
    try:
        args = json.loads(processed_raw)
        
        # --- The "Intended State" Translator Layer ---
        # Normalize common hallucinations to the Claude Code Tool Spec
        
        # 1. Path & URL Mapping
        for k in ['path', 'TargetFile', 'AbsolutePath', 'notebook_path', 'uri', 'link', 'filename']:
            if k in args:
                if 'file_path' not in args and k not in ['uri', 'link']: args['file_path'] = args[k]
                if 'url' not in args and k in ['uri', 'link']: args['url'] = args[k]
                if 'notebook_path' not in args and k == 'notebook_path': args['notebook_path'] = args[k]

        # 2. Content & Prompt Mapping
        for k in ['text', 'CodeContent', 'new_string', 'new_source', 'instructions', 'task', 'replacement', 'original']:
            if k in args:
                if 'content' not in args and k in ['text', 'CodeContent']: args['content'] = args[k]
                if 'prompt' not in args and k in ['instructions', 'task']: args['prompt'] = args[k]
                if 'new_string' not in args and k == 'replacement': args['new_string'] = args[k]
                if 'old_string' not in args and k == 'original': args['old_string'] = args[k]

        # 3. Task Mapping
        if 'title' in args and 'subject' not in args: args['subject'] = args['title']
        if 'name' in args and 'subject' not in args: args['subject'] = args['name']
        if 'summary' in args and 'description' not in args: args['description'] = args['summary']
        if 'body' in args and 'description' not in args: args['description'] = args['body']

        # 4. Command & Scheduling Mapping
        for k in ['cmd', 'CommandLine', 'script', 'command_line']:
            if k in args and 'command' not in args: args['command'] = args[k]
        
        if 'wait' in args and 'delaySeconds' not in args: args['delaySeconds'] = args['wait']
        if 'schedule' in args and 'cron' not in args: args['cron'] = args['schedule']

        # 5. ID Normalization (Handle taskId vs task_id)
        for k in ['taskId', 'task_id', 'id', 'cron_id', 'shell_id']:
            if k in args:
                val = str(args[k]).strip().strip('"').strip("'").strip()
                if 'id' not in args: args['id'] = val
                if 'taskId' not in args: args['taskId'] = val
                if 'task_id' not in args: args['task_id'] = val

        # 6. Metadata Record Sync
        if 'metadata' in args and isinstance(args['metadata'], str):
            try: args['metadata'] = json.loads(args['metadata'])
            except: pass

        # 7. Status Normalization
        if 'status' in args:
            s = str(args['status']).lower().strip()
            if s in ['complete', 'done', 'finished']: args['status'] = 'completed'
            if s in ['in progress', 'working', 'started']: args['status'] = 'in_progress'

        # 8. Web & Search Mapping
        for k in ['q', 'search', 'search_query']:
            if k in args and 'query' not in args: args['query'] = args[k]
        
        for k in ['domains', 'site', 'sites']:
            if k in args and 'allowed_domains' not in args: args['allowed_domains'] = args[k]

        return args
    except:
        # Final fallback: if JSON is still broken, return as much as we parsed
        return {"raw_input_error": raw}

class SSEParser:
    def __init__(self): self.buffer = ""
    def feed(self, chunk: bytes):
        self.buffer += chunk.decode('utf-8', errors='replace')
        while "\n\n" in self.buffer:
            block, self.buffer = self.buffer.split("\n\n", 1)
            for line in block.split("\n"):
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data: yield data

def merge_messages(messages: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
    if not messages: return []
    merged = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"] and msg["role"] != "tool":
            e, n = merged[-1]["content"], msg["content"]
            if isinstance(e, str) and isinstance(n, str): merged[-1]["content"] = e + "\n\n" + n
            elif isinstance(e, list) and isinstance(n, list): merged[-1]["content"].extend(n)
            if msg.get("tool_calls"): merged[-1].setdefault("tool_calls", []).extend(msg["tool_calls"])
        else: merged.append(msg)
    return merged

# --- 4. Server ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root():
    return {"status": "online", "bridge": "openai-anthropic", "model": MODEL_NAME}

@app.get("/health")
def health():
    # Rate limiting check for health endpoint
    if not rate_limiter.is_allowed():
        retry_after = rate_limiter.get_retry_after()
        logger.warning(f"Rate limit exceeded for health check. Retry after: {retry_after} seconds")
        return JSONResponse(
            {"error": {"message": "Rate limit exceeded", "code": "rate_limit_exceeded"}},
            status_code=429,
            headers={"Retry-After": str(retry_after)}
        )

    # Health check with upstream connectivity check
    health_status = {"status": "ok", "bridge": "openai-anthropic", "model": MODEL_NAME}
    upstream_status = "unknown"
    upstream_latency_ms = None

    if TARGET_URL:
        try:
            import httpx

            with httpx.Client(verify=SSL_VERIFY, timeout=httpx.Timeout(5.0)) as client:
                start_time = time.time()
                try:
                    headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
                    resp = client.get(TARGET_URL, headers=headers)
                    latency_ms = (time.time() - start_time) * 1000
                    # A 405 (Method Not Allowed) or 403 (Forbidden) still means the upstream is reachable
                    upstream_status = "ok" if resp.status_code < 500 or resp.status_code in [403, 405] else "error"
                    upstream_latency_ms = latency_ms
                except Exception as e:
                    upstream_status = "error"
                    logger.warning(f"Upstream health check failed: {e}")
        except Exception as e:
            upstream_status = "error"
            logger.warning(f"Health check error: {e}")
    else:
        upstream_status = "not_configured"
        logger.info("Upstream URL not configured, skipping upstream health check")

    health_status["upstream"] = {
        "status": upstream_status,
        "latency_ms": upstream_latency_ms
    }

    status_code = 200 if upstream_status == "ok" else 503
    return JSONResponse(health_status, status_code=status_code)

@app.post("/v1/messages")
async def proxy_handler(request: Request):
    try:
        # Rate limiting check
        if not rate_limiter.is_allowed():
            retry_after = rate_limiter.get_retry_after()
            logger.warning(f"Rate limit exceeded. Retry after: {retry_after} seconds")
            return JSONResponse(
                {"error": {"message": "Rate limit exceeded", "code": "rate_limit_exceeded"}},
                status_code=429,
                headers={"Retry-After": str(retry_after)}
            )

        body = await request.json()
        tools_list = {}
        for t in body.get("tools", []):
            tool_name = t.get("name", "")
            if tool_name:
                tools_list[tool_name.lower()] = tool_name

        raw_msgs = []
        for msg in body.get("messages", []):
            role, content = msg.get("role"), msg.get("content")
            if role == "assistant" and isinstance(content, list):
                text = "".join(b["text"] for b in content if b.get("type") == "text")
                calls = [{"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b["input"])}} for b in content if b.get("type") == "tool_use"]
                m = {"role": "assistant", "content": text or None}
                if calls: m["tool_calls"] = calls
                raw_msgs.append(m); continue
            if role == "user" and isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_result":
                        c = b.get("content", "")
                        if isinstance(c, list): c = "\n".join(p.get("text", "") for p in c if p.get("type") == "text")
                        raw_msgs.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": str(c)})
                    elif b.get("type") == "text": raw_msgs.append({"role": "user", "content": b["text"]})
                continue
            raw_msgs.append({"role": role, "content": content})

        messages = merge_messages(raw_msgs)
        sys_p = body.get("system", "")
        if isinstance(sys_p, list): sys_p = "".join(b["text"] for b in sys_p if b.get("type") == "text")

        # Apply System Override / Persona Injection
        final_sys = SYSTEM_OVERRIDE
        # if sys_p: messages.insert(0, {"role": "system", "content": sys_p})
        if sys_p: final_sys = f"{SYSTEM_OVERRIDE}\n\n{sys_p}" if final_sys else sys_p

        if final_sys: messages.insert(0, {"role": "system", "content": final_sys})

        # Get model parameters
        model_params = get_model_params()

        payload = {
            "model": MODEL_NAME,
            "stream": True,
            "temperature": body.get("temperature", 0.0),
            "messages": messages,
            "tools": [{"type": "function", "function": {"name": t.get("name", ""), "description": t.get("description", ""), "parameters": t.get("input_schema", {})}} for t in body.get("tools", [])] if body.get("tools") else None,
            "model_params": model_params
        }

        async def stream_gen():
            msg_id = f"msg_{uuid.uuid4().hex}"
            input_tokens, output_tokens = 0, 0
            yield f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "model": MODEL_NAME, "content": [], "stop_reason": None, "usage": {"input_tokens": 0, "output_tokens": 0}}})}\n\n'

            block_idx, text_started, active_tools, tool_results = 0, False, {}, []
            async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=httpx.Timeout(600.0)) as client:
                try:
                    async with client.stream("POST", TARGET_URL, json=payload, headers={"Authorization": f"Bearer {API_TOKEN}"}) as resp:
                        if resp.status_code != 200:
                            err_body = await resp.aread()
                            logger.error(f"Upstream Error {resp.status_code}: {err_body.decode()}")
                            yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": f"Error from upstream: {resp.status_code}"}})}\n\n'
                            return

                        parser = SSEParser()
                        async for chunk in resp.aiter_bytes():
                            for data_str in parser.feed(chunk):
                                if data_str == "[DONE]": break
                                try:
                                    data = json.loads(data_str)
                                    # Capture Usage data if present
                                    if data.get("usage"):
                                        u = data["usage"]
                                        input_tokens = u.get("prompt_tokens", input_tokens)
                                        output_tokens = u.get("completion_tokens", output_tokens)

                                    choice = data.get("choices", [{}])[0]
                                    delta = choice.get("delta", {})

                                    # Handle Text Content
                                    if delta.get("content"):
                                        if not text_started:
                                            # Close any active tool blocks if text appears (rare but possible)
                                            yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "text", "text": ""}})}\n\n'
                                            text_started = True
                                        yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_idx, "delta": {"type": "text_delta", "text": delta["content"]}})}\n\n'

                                    # Handle Tool Calls
                                    for tc in delta.get("tool_calls", []):
                                        idx = tc.get("index", 0)
                                        if idx not in active_tools:
                                            # If we were writing text, stop that block
                                            if text_started:
                                                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'
                                                block_idx += 1; text_started = False
                                            
                                            active_tools[idx] = {"id": tc.get("id"), "name": "", "args": "", "block_idx": block_idx, "started": False}
                                            block_idx += 1

                                        info = active_tools[idx]
                                        if tc.get("function", {}).get("name"): 
                                            info["name"] += tc["function"]["name"]
                                        
                                        if tc.get("function", {}).get("arguments"):
                                            arg_chunk = tc["function"]["arguments"]
                                            if not info["started"] and info["name"]:
                                                native_name = tools_list.get(info["name"].lower(), info["name"])
                                                yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": generate_tool_call_id(idx), "name": native_name, "input": {}}})}\n\n'
                                                info["started"] = True
                                            info["args"] += arg_chunk
                                            yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": arg_chunk}})}\n\n'
                                except Exception as e:
                                    logger.error(f"Stream Parse Error: {e} | Data: {data_str}")
                except Exception as e:
                    logger.error(f"Connection Error: {e}")
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "text", "text": f"Connection Error: {str(e)}"}})}\n\n'

            # --- Finalization Phase ---
            if text_started:
                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'

            # Ensure all tool calls are closed and valid
            _NO_STATUS = {"TaskCreate", "TaskList", "TaskGet", "TaskOutput", "TaskStop", "Bash", "Read", "Write", "Edit", "WebSearch", "WebFetch", "AskUserQuestion", "CronCreate", "CronDelete", "CronList", "ScheduleWakeup", "Skill", "Monitor", "RemoteTrigger", "EnterPlanMode", "ExitPlanMode", "EnterWorktree", "ExitWorktree", "Agent", "Plan", "Explore", "claude-code-guide", "statusline-setup", "update-config", "fewer-permission-prompts", "loop", "schedule", "claude-api", "init", "review", "security-review"}
            for _, info in sorted(active_tools.items()):
                if info["started"]:
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'
                else:
                    # Fallback for tools that never even "started" (missed chunks)
                    native_name = tools_list.get(info["name"].lower(), info["name"] or "unknown_tool")
                    args = robust_parse_args(info["args"])
                    
                    # Clean up status hallucinations for specific tools
                    if native_name in _NO_STATUS and "status" in args: del args["status"]
                    
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": info["id"] or f"gen_{int(time.time())}", "name": native_name, "input": {}}})}\n\n'
                    yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": json.dumps(args)}})}\n\n'
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'

            stop = "tool_use" if active_tools else "end_turn"
            # Finalize the message with actual usage
            yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}})}\n\n'
            yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'

        return StreamingResponse(stream_gen(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Fatal Proxy Error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
