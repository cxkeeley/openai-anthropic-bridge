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
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# --- 1. Logging ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "bridge.log")

# Auto-cleanup if Docker/System created a directory named 'bridge.log'
if os.path.isdir(LOG_PATH):
    import shutil
    shutil.rmtree(LOG_PATH)

# Structured logging formatter with request context
class StructuredLogFormatter(logging.Formatter):
    """Custom formatter that adds request context for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        # Add request context if available
        request_id = getattr(record, 'request_id', 'N/A')
        client_ip = getattr(record, 'client_ip', 'N/A')

        # Create structured JSON-like format
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'request_id': request_id,
            'client_ip': client_ip,
            'message': record.getMessage()
        }

        # Add extra fields if present
        if hasattr(record, 'detail'):
            log_entry['detail'] = record.detail
        if hasattr(record, 'error'):
            log_entry['error'] = record.error
        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint
        if hasattr(record, 'method'):
            log_entry['method'] = record.method
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
        if hasattr(record, 'duration_ms'):
            log_entry['duration_ms'] = record.duration_ms
        if hasattr(record, 'response_size'):
            log_entry['response_size'] = record.response_size

        return json.dumps(log_entry, indent=None, separators=(',', ':'))

    def formatException(self, ei):
        if ei[0]:
            return f"\n{self.formatExceptionName(ei[0])}: {ei[1]}"
        return ""

    def formatExceptionName(self, ei):
        return ei[0].__name__ if ei[0] else "Exception"

# Create log directory if it doesn't exist
LOG_DIR = os.path.dirname(LOG_PATH)
if LOG_DIR and not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
log_formatter = StructuredLogFormatter()
file_handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=10*1024*1024, backupCount=3)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)

# Configure root logger
logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)
logger = logging.getLogger("Bridge")
logger.info(f"BRIDGE LOGGING TO: {LOG_PATH}")

# Silence noisy dependency logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)

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

# --- 3. Request Context Middleware ---
class RequestLoggingMiddleware:
    """Middleware to add request context to log records"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        method = request.method
        start_time = time.time()

        # Store ID in state for use by endpoints
        scope["state"] = scope.get("state", {})
        scope["state"]["request_id"] = request_id

        try:
            await self.app(scope, receive, send)
        except Exception as e:
            logger.error(
                f"Request failed",
                extra={
                    'request_id': request_id,
                    'client_ip': client_ip,
                    'endpoint': endpoint,
                    'method': method,
                    'error': str(e),
                }
            )
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed",
                extra={
                    'request_id': request_id,
                    'client_ip': client_ip,
                    'endpoint': endpoint,
                    'method': method,
                    'duration_ms': round(duration_ms, 2),
                }
            )

# --- 5. Logging Helper Functions ---
def log_request_start(request_id: str, endpoint: str, method: str) -> float:
    """
    Log the start of a request and return the start time.

    Args:
        request_id: Unique request identifier
        endpoint: Request endpoint path
        method: HTTP method
    Returns:
        Start time for duration calculation
    """
    logger.info(
        f"Request started",
        extra={
            'request_id': request_id,
            'endpoint': endpoint,
            'method': method,
        }
    )
    return time.time()


def log_request_end(
    request_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    start_time: float,
    response_size: int = 0,
) -> None:
    """
    Log the end of a request with duration and response info.

    Args:
        request_id: Unique request identifier
        endpoint: Request endpoint path
        method: HTTP method
        status_code: Response status code
        start_time: Request start time
        response_size: Response size in bytes
    """
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        f"Request completed",
        extra={
            'request_id': request_id,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'duration_ms': round(duration_ms, 2),
            'response_size': response_size,
        }
    )


def log_error(
    request_id: str,
    endpoint: str,
    method: str,
    error: str,
    status_code: int = 500,
) -> None:
    """
    Log an error with request context.

    Args:
        request_id: Unique request identifier
        endpoint: Request endpoint path
        method: HTTP method
        error: Error message
        status_code: HTTP status code
    """
    logger.error(
        f"Request failed",
        extra={
            'request_id': request_id,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'error': error,
        }
    )


def log_warning(
    request_id: str,
    endpoint: str,
    method: str,
    message: str,
) -> None:
    """
    Log a warning with request context.

    Args:
        request_id: Unique request identifier
        endpoint: Request endpoint path
        method: HTTP method
        message: Warning message
    """
    logger.warning(
        f"Request warning",
        extra={
            'request_id': request_id,
            'endpoint': endpoint,
            'method': method,
            'detail': message,
        }
    )


def get_logger() -> logging.Logger:
    """
    Get the bridge logger instance.

    Returns:
        Logger instance
    """
    return logger


# --- 4. Core Utility ---
def validate_tool_call_id(tool_call_id: str | None) -> bool:
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
app.add_middleware(RequestLoggingMiddleware)
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
        # Retrieve context from middleware state
        request_id = request.state.request_id
        endpoint = request.url.path
        method = request.method

        # Rate limiting check
        if not rate_limiter.is_allowed():
            retry_after = rate_limiter.get_retry_after()
            log_warning(request_id, endpoint, method, f"Rate limit exceeded. Retry after: {retry_after} seconds")
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
        # 'ANTIGRAVITY' EXPERT PERSONA: This forces the model into a high-precision, meta-cognitive state.
        # v2: Hierarchical rules, explicit tool map, graduated escalation, output format constraint.
        EXPERT_PERSONA = (
            "\n\n[ANTIGRAVITY EXPERT MODE — ACTIVE]\n"
            "You are a high-precision Systems Architect operating inside a bridged agentic environment.\n"
            "Obey these rules in strict priority order:\n"
            "\n"
            "=== CRITICAL (apply before every tool call) ===\n"
            "C1. TOOL MAP — Always prefer the specialized tool over a shell equivalent:\n"
            "    cat/head/tail  → view_file\n"
            "    grep/rg        → grep_search\n"
            "    ls/find        → list_dir\n"
            "    sed/awk/patch  → replace_file_content or multi_replace_file_content\n"
            "    echo > file    → write_to_file\n"
            "    Use Bash ONLY when no specialized tool covers the operation.\n"
            "C2. ESCALATION LADDER — On any edit/write failure, follow this exact sequence:\n"
            "    Step 1: Use view_file on the SPECIFIC failing lines (not the whole file) to confirm exact content.\n"
            "    Step 2: Retry replace_file_content with a narrower, more precise match string.\n"
            "    Step 3: If Step 2 fails, use multi_replace_file_content for surgical multi-block edits.\n"
            "    Step 4 (NUCLEAR): If Step 3 fails, use write_to_file with the complete corrected file.\n"
            "    NEVER skip steps. NEVER repeat the exact same failed call.\n"
            "C3. BASH FAILURE: If a Bash command fails, diagnose the error class first:\n"
            "    SyntaxError → fix code, do NOT re-run.\n"
            "    ModuleNotFoundError → install or use alternative path.\n"
            "    PermissionError → check path and permissions with list_dir first.\n"
            "C4. CACHE HIT — STOP RE-READING:\n"
            "    If a Read/view_file result says 'Unchanged since last read', this means:\n"
            "    - The file content IS ALREADY in your context window from a previous read.\n"
            "    - Calling Read again on the same path/lines will ALWAYS return the same result.\n"
            "    - You MUST NOT call Read on that file again. Scroll up in your context and use what you already have.\n"
            "    - If you cannot find the content you need in context, read a DIFFERENT line range or a DIFFERENT file.\n"
            "    - Repeatedly reading the same unchanged file is a CRITICAL LOOP. Stop immediately.\n"
            "C5. LOOP DETECTION — When circuit breaker triggers:\n"
            "    - If you see '[CIRCUIT BREAKER — LOOP DETECTED]' in the system prompt:\n"
            "    - STOP calling the same tool with the same arguments.\n"
            "    - Report the exact error to the user instead of retrying.\n"
            "    - If stuck on a file edit: jump directly to Step 4 (write_to_file with full content).\n"
            "    - If stuck reading the same file: trust what you already read and proceed to write the fix.\n"
            "\n"
            "=== STANDARD (apply when relevant) ===\n"
            "S1. SILENT REASONING: Internally decide which tool to use before invoking. Only narrate reasoning if the user asks 'why'.\n"
            "S2. NO PLACEHOLDERS: Never emit '...', 'content remains same', or partial code. Always provide complete, working blocks.\n"
            "S3. OUTPUT LANGUAGE: Always respond in English regardless of the language of the system prompt or user content.\n"
            "S4. TOOL RESULT TRUST: Treat tool results as ground truth. Do not contradict a tool result with a prior assumption.\n"
            "    Corollary: 'Unchanged since last read' IS a tool result. Trust it. Do not re-read to 'confirm'."
        )

        final_sys = SYSTEM_OVERRIDE
        if sys_p: final_sys = f"{SYSTEM_OVERRIDE}\n\n{sys_p}" if final_sys else sys_p

        # Inject the high-precision persona
        final_sys = f"{final_sys}{EXPERT_PERSONA}" if final_sys else EXPERT_PERSONA.strip()

        # [CIRCUIT BREAKER] Detect repeated tool calls in message history to break agentic loops
        repeats = 0
        last_calls = None
        last_read_file = None
        actions_since_read = 0

        for msg in reversed(messages):
            if msg["role"] == "assistant" and "tool_calls" in msg:
                current_calls = []
                for tc in msg["tool_calls"]:
                    name = tc.get("function", {}).get("name")
                    current_calls.append(name)

                    # Track Read operations
                    if name in ["Read", "view_file"]:
                        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                        file_path = args.get("file_path") or args.get("AbsolutePath") or args.get("path")
                        if file_path == last_read_file and actions_since_read == 0:
                            repeats += 1
                        last_read_file = file_path
                        actions_since_read = 0
                    elif name not in ["Read", "view_file", "list_dir", "ls"]:
                        actions_since_read += 1

                if last_calls == current_calls and current_calls:
                    repeats += 1
                else:
                    if last_calls is not None: break
                    last_calls = current_calls

        if repeats >= 2:
            # Build a diagnostic hint from the actual repeated call(s)
            repeated_names = list(dict.fromkeys(
                tc.get("function", {}).get("name", "unknown")
                for msg in messages
                if msg["role"] == "assistant"
                for tc in msg.get("tool_calls", [])
            ))
            repeated_hint = ", ".join(repeated_names[:5]) if repeated_names else "unknown"
            log_warning(request_id, endpoint, method, f"CIRCUIT BREAKER: {repeats} redundant calls detected. Repeated tools: {repeated_hint}")
            final_sys += (
                f"\n\n[CIRCUIT BREAKER — LOOP DETECTED]\n"
                f"You have called [{repeated_hint}] {repeats} times without progress. This is a loop.\n"
                "MANDATORY ACTIONS:\n"
                "1. Do NOT call the same tool again with the same arguments.\n"
                "2. If stuck on a file edit: jump directly to ESCALATION LADDER Step 4 (write_to_file with full content).\n"
                "3. If stuck on a Bash error: stop executing and report the exact error to the user instead of retrying.\n"
                "4. If stuck reading the same file: trust what you already read and proceed to write the fix."
            )

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
                            log_error(request_id, endpoint, method, f"Upstream Error {resp.status_code}: {err_body.decode()}")
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

                                            # FIX 5: Set tool_id at block start using upstream ID
                                            upstream_id = tc.get("id")
                                            tool_id = upstream_id if upstream_id else generate_tool_call_id(idx)
                                            active_tools[idx] = {"id": upstream_id, "tool_id": tool_id, "name": "", "args": "", "block_idx": block_idx, "started": False}
                                            block_idx += 1

                                        info = active_tools[idx]
                                        if tc.get("function", {}).get("name"):
                                            info["name"] += tc["function"]["name"]

                                        if tc.get("function", {}).get("arguments"):
                                            arg_chunk = tc["function"]["arguments"]
                                            if not info["started"] and info["name"]:
                                                native_name = tools_list.get(info["name"].lower(), info["name"])
                                                # Use the tool_id already set in info dict (FIX 1)
                                                tool_id = info.get("tool_id", generate_tool_call_id(idx))
                                                yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": tool_id, "name": native_name, "input": {}}})}\n\n'
                                                info["started"] = True
                                            info["args"] += arg_chunk
                                            yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": arg_chunk}})}\n\n'
                                except Exception as e:
                                    log_error(request_id, endpoint, method, f"Stream Parse Error: {e} | Data: {data_str}")
                except Exception as e:
                    log_error(request_id, endpoint, method, f"Connection Error: {e}")
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "text", "text": f"Connection Error: {str(e)}"}})}\n\n'

            # --- Finalization Phase ---
            if text_started:
                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'

            # Ensure all tool calls are closed and valid
            # Tools that legitimately use 'status' in their schema
            _STATUS_ALLOWED = {"TaskUpdate"}
            # Per-tool safe argument defaults to prevent empty-call loops
            _EMPTY_ARGS_DEFAULTS = {
                "ls": {"path": "."},
                "Bash": {"command": "echo 'no-op'"},
                "Read": {"file_path": "."},
            }
            for _, info in sorted(active_tools.items()):
                if info["started"]:
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'
                else:
                    # Fallback for tools that never even "started" (missed chunks)
                    native_name = tools_list.get(info["name"].lower(), info["name"] or "unknown_tool")
                    args = robust_parse_args(info["args"])

                    # FIX 2: Aggressively strip hallucinated 'status' for every tool not in the allow-list.
                    if "status" in args and native_name not in _STATUS_ALLOWED:
                        del args["status"]
                        logger.debug(f"Stripped hallucinated 'status' field from {native_name} call")

                    # FIX 3: Guard against empty-arg tool calls which cause Claude Code to loop.
                    if not args and native_name in _EMPTY_ARGS_DEFAULTS:
                        args = _EMPTY_ARGS_DEFAULTS[native_name]
                        log_warning(request_id, endpoint, method, f"Empty args for '{native_name}' — injecting safe default: {args}")

                    # FIX 1 (fallback path): Use the tool_id already set in info dict
                    tool_id = info.get("tool_id", generate_tool_call_id(0))
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": tool_id, "name": native_name, "input": {}}})}\n\n'
                    yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": json.dumps(args)}})}\n\n'
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'

            stop = "tool_use" if active_tools else "end_turn"
            # Finalize the message with actual usage
            yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}})}\n\n'
            yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'

        return StreamingResponse(stream_gen(), media_type="text/event-stream")
    except Exception as e:
        log_error(request_id, endpoint, method, f"Fatal Proxy Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
