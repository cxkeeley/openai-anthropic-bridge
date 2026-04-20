import os
import json
import logging
import httpx
import re
import time
import sys
import ctypes
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional

# --- 1. System Resilience (Windows Optimization) ---
def setup_windows_console():
    """Optimizes console output and resilience for Windows environments."""
    if sys.platform != "win32": return
    class NullWriter:
        def write(self, s): pass
        def flush(self): pass
        def isatty(self): return False
    try:
        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout = open("CONOUT$", "w", encoding="utf-8")
            sys.stderr = open("CONOUT$", "w", encoding="utf-8")
    except: pass
    if sys.stdout is None: sys.stdout = NullWriter()
    if sys.stderr is None: sys.stderr = NullWriter()

setup_windows_console()

# --- 2. Logging Setup (Verbose Debugging) ---
log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler = logging.FileHandler("bridge.log", encoding='utf-8')
file_handler.setFormatter(log_formatter)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)

# Set to INFO to avoid flooding, but keep REPAIR actions visible
logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
logger = logging.getLogger("Bridge")
logger.info("BRIDGE STARTED - INFO LEVEL ENABLED")

# --- 3. Configuration ---
TARGET_URL = os.environ.get("JTIU_TARGET_URL", "")
API_TOKEN = os.environ.get("JTIU_TOKEN", "")
MODEL_NAME = os.environ.get("JTIU_MODEL", "jt_indonesia")
SSL_VERIFY = os.environ.get("JTIU_SSL_VERIFY", "true").lower() == "true"
JTIU_REPAIR_SYNTAX = os.environ.get("JTIU_REPAIR_SYNTAX", "true").lower() == "true"

# --- 4. Core Logic & Utility Engines ---
def sanitize_path(path: Any) -> str:
    """Standardizes file paths and removes local directory noise."""
    if not path: return ""
    p = str(path).replace("\\", "/").replace('"', '').replace("'", "")
    cwd = os.getcwd().replace("\\", "/").lower()
    if cwd in p.lower():
        idx = p.lower().find(cwd) + len(cwd)
        return p[idx:].lstrip("/")
    return p

def repair_syntax(content: str, is_fragment: bool = False) -> str:
    """Pro-grade stack-based syntax repair: handles template literals and balances brackets."""
    if not content: return content
    
    orig_content = content
    pairs = {'{': '}', '[': ']', '(': ')', '${': '}', '`': '`'}
    stack = []
    in_string = None
    in_comment = None
    escaped = False
    
    result_chars = []
    i = 0
    while i < len(content):
        char = content[i]
        next_char = content[i+1] if i + 1 < len(content) else ""
        
        # Semicolon heuristic: Force close hanging template expressions (only if not in a string already)
        # Semicolon heuristic: Auto-close hanging template expressions at statement end
        if char == ';' and (in_string is None or in_string == '`') and not in_comment and stack:
            # If we are inside a ${} or similar hanging state, unwind it
            found_template = False
            for idx in range(len(stack) - 1, -1, -1):
                if stack[idx] == '${':
                    found_template = True
                    break
            
            if found_template:
                logger.info("HEURISTIC: Closing hanging expressions at semicolon")
                while stack and stack[-1] in ['${', '`', '(', '[']:
                    opening = stack.pop()
                    c_char = pairs.get(opening)
                    if c_char:
                        result_chars.append(c_char)
                in_string = None

        if escaped:
            result_chars.append(char); escaped = False; i += 1; continue
        if char == '\\':
            result_chars.append(char); escaped = True; i += 1; continue
            
        # Comment handling
        if not in_string:
            if not in_comment:
                if char == '/' and next_char == '/': 
                    in_comment = 'line'; result_chars.extend([char, next_char]); i += 2; continue
                if char == '/' and next_char == '*': 
                    in_comment = 'block'; result_chars.extend([char, next_char]); i += 2; continue
            else:
                result_chars.append(char)
                if in_comment == 'line' and char == '\n': in_comment = None
                elif in_comment == 'block' and char == '*' and next_char == '/': 
                    result_chars.append(next_char); in_comment = None; i += 2; continue
                i += 1; continue

        # String and Template Literal Handling
        if in_string:
            if char == in_string:
                if in_string == '`' and stack and stack[-1] == '`':
                    stack.pop()
                in_string = None
                result_chars.append(char)
            elif in_string == '`' and char == '$' and next_char == '{':
                # Nested expression in template literal
                stack.append('`') 
                stack.append('${')
                in_string = None
                result_chars.extend([char, next_char])
                i += 2; continue
            else:
                result_chars.append(char)
            i += 1; continue
        
        # Keyword heuristic for else: if we see 'else' and last block was an 'if' without '}'
        if char == 'e' and content[i:i+5] == 'else ' and not in_string and not in_comment:
            if stack and stack[-1] == '{':
                # Peek back for 'if' (crude but effective)
                snippet = "".join(result_chars[-50:]).strip()
                if 'if' in snippet and not snippet.endswith('}'):
                    logger.info("HEURISTIC: Closing unclosed 'if' block before 'else'")
                    stack.pop()
                    result_chars.append('}')

        # Outside string/comment
        if char in ["'", '"', '`']:
            in_string = char
            if char == '`':
                stack.append('`')
            result_chars.append(char)
        elif char in pairs:
            stack.append(char)
            result_chars.append(char)
        elif char in pairs.values():
            if stack:
                # Look for a match deeper in the stack
                found_idx = -1
                for idx in range(len(stack) - 1, -1, -1):
                    if pairs.get(stack[idx]) == char:
                        found_idx = idx
                        break
                
                if found_idx != -1:
                    # Unwind the stack to this match
                    while len(stack) > found_idx + 1:
                        opening = stack.pop()
                        c_char = pairs.get(opening)
                        if c_char:
                            logger.info(f"UNWIND REPAIR: Auto-closing '{opening}' with '{c_char}' to match deeper '{char}'")
                            result_chars.append(c_char)
                            if opening == '${' and stack and stack[-1] == '`':
                                stack.pop()
                                logger.info("UNWIND REPAIR: Also auto-closing template backtick '`'")
                                result_chars.append('`')
                    
                    # Now pop the matching one
                    opening = stack.pop()
                    result_chars.append(char)
                    if opening == '${':
                        if stack and stack[-1] == '`':
                            stack.pop()
                            in_string = '`'
                else:
                    logger.info(f"STRAY BRACKET: Found '{char}' with no match in stack. Keeping it.")
                    result_chars.append(char)
            else:
                logger.info(f"STRAY BRACKET: Found '{char}' with empty stack. Keeping it.")
                result_chars.append(char)
        else:
            result_chars.append(char)
        i += 1
    
    repaired = "".join(result_chars)
    
    # Close any unclosed strings or template expressions
    if in_string:
        logger.info(f"REPAIR: Closing unclosed string {in_string}")
        repaired += in_string

    # Balance remaining stack
    if stack:
        if is_fragment:
            logger.info(f"FRAGMENT DETECTED: Stack has {len(stack)} items left, but skipping full balance for fragment.")
        else:
            repaired = repaired.rstrip()
            closing = ""
            while stack:
                opening = stack.pop()
                if opening == '`': continue 
                c_char = pairs.get(opening)
                if not c_char: continue
                
                if c_char == '}' and not closing.startswith('\n'): 
                    closing = '\n' + '}' + closing
                else: 
                    closing = c_char + closing
            
            if closing:
                logger.info(f"REPAIR: Appending balanced brackets: {closing.replace('\n', '\\n')}")
                repaired += closing
    
    if repaired != orig_content:
        logger.info(f"REPAIR ACTION: content modified by sanitizer (Length: {len(orig_content)} -> {len(repaired)})")
    return repaired

def extract_truncated_value(raw: str, key: str) -> Optional[str]:
    """Manually extracts key values from malformed or truncated JSON strings."""
    pattern = rf'"{re.escape(key)}"\s*:\s*"'
    match = re.search(pattern, raw)
    if not match: return None
    start, result, i, escaped = match.end(), [], match.end(), False
    while i < len(raw):
        char = raw[i]
        if escaped:
            mapping = {'n': '\n', 't': '\t', '"': '"', '\\': '\\'}
            result.append(mapping.get(char, char))
            escaped = False
        elif char == '\\': escaped = True
        elif char == '"': break
        else: result.append(char)
        i += 1
    return "".join(result)

def robust_parse_args(raw: str) -> dict:
    """Primary argument parser with multi-stage fallback for Jiutian model output."""
    if not raw: return {}
    is_truncated = False
    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"JSON Parse Failed. Attempting Robust Extraction. Raw: {raw[:100]}...")
        args = {}
        is_truncated = True
        for k in ['file_path', 'path', 'content', 'text', 'new_string', 'command', 'description']:
            val = extract_truncated_value(raw, k)
            if val is not None: args[k] = val
    
    # Post-processing
    for k in ['file_path', 'path']:
        if k in args: args[k] = sanitize_path(args[k])
    
    # Apply syntax repair to code-related fields if enabled
    if JTIU_REPAIR_SYNTAX:
        for k in ['content', 'text', 'new_string', 'ReplacementContent', 'CodeContent']:
            if k in args and isinstance(args[k], str):
                # Treat new_string and ReplacementContent as fragments to avoid over-balancing
                is_frag = k in ['new_string', 'ReplacementContent']
                args[k] = repair_syntax(args[k], is_fragment=is_frag)
    return args

class SSEParser:
    """Stateful SSE Parser designed for fragmented network packets."""
    def __init__(self):
        self.buffer = ""
    def feed(self, chunk: bytes):
        self.buffer += chunk.decode('utf-8', errors='replace')
        while "\n\n" in self.buffer:
            block, self.buffer = self.buffer.split("\n\n", 1)
            for line in block.split("\n"):
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data: yield data

class IntentRouter:
    """Heuristic engine to detect and recover implicit tool calls from plain text."""
    def __init__(self, tools: list):
        self.tools = tools
    def detect_filename(self, context: str) -> str:
        match = re.search(rf'[`\'"]([\w.][\w./-]*\.[a-z0-9]+)[`\'"]', context, re.I)
        return match.group(1) if match else "generated_file.js"
    def detect_hallucinated_tool_calls(self, text: str) -> list:
        intents = []
        # 1. Detect Markdown blocks (assume Write if not specified)
        for match in re.finditer(r'```(?:\w+)?\n?(.*?)\n?```', text, re.DOTALL):
            content = repair_syntax(match.group(1).strip())
            if content:
                fname = sanitize_path(self.detect_filename(text[:match.start()]))
                intents.append(("write_to_file", {"TargetFile": fname, "CodeContent": content, "Overwrite": True, "Description": "Hallucinated write from markdown block"}))
        
        # 2. Detect ToolName({...}) patterns
        patterns = [
            (r'Bash\s*\(\s*({.*?})\s*\)', 'run_command'),
            (r'Write\s*\(\s*({.*?})\s*\)', 'write_to_file'),
            (r'Read\s*\(\s*({.*?})\s*\)', 'read_file'),
            (r'Edit\s*\(\s*({.*?})\s*\)', 'replace_file_content'),
            (r'Update\s*\(\s*({.*?})\s*\)', 'replace_file_content'),
        ]
        
        for pattern, native_name in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    raw_args = match.group(1)
                    args = robust_parse_args(raw_args)
                    
                    # Map arguments to native names
                    mapped_args = {}
                    if native_name == "run_command":
                        mapped_args = {"CommandLine": args.get("command") or args.get("CommandLine", ""), "Cwd": ".", "SafeToAutoRun": True, "WaitMsBeforeAsync": 500}
                    elif native_name == "write_to_file":
                        mapped_args = {"TargetFile": args.get("file_path") or args.get("TargetFile", "") or args.get("path", ""), "CodeContent": args.get("content") or args.get("CodeContent", ""), "Overwrite": True, "Description": "Hallucinated write"}
                    elif native_name == "read_file":
                        mapped_args = {"path": args.get("file_path") or args.get("path", "") or args.get("AbsolutePath", "")}
                    elif native_name == "replace_file_content":
                        mapped_args = {
                            "TargetFile": args.get("file_path") or args.get("path", "") or args.get("TargetFile", ""),
                            "TargetContent": args.get("target_content") or args.get("TargetContent", ""),
                            "ReplacementContent": args.get("replacement_content") or args.get("ReplacementContent", "") or args.get("new_string", ""),
                            "Description": "Hallucinated edit",
                            "AllowMultiple": False,
                            "StartLine": 1,
                            "EndLine": 500 # Default range
                        }
                    
                    if mapped_args:
                        intents.append((native_name, mapped_args))
                except: continue
        return intents

def merge_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes message sequences to maintain Anthropic protocol compatibility."""
    if not messages: return []
    merged = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"]:
            e, n = merged[-1]["content"], msg["content"]
            if isinstance(e, str) and isinstance(n, str):
                merged[-1]["content"] = e + "\n\n" + n
            elif isinstance(e, list) and isinstance(n, list):
                merged[-1]["content"].extend(n)
            else:
                e_list = e if isinstance(e, list) else [{"type": "text", "text": str(e)}]
                n_list = n if isinstance(n, list) else [{"type": "text", "text": str(n)}]
                merged[-1]["content"] = e_list + n_list
        else: merged.append(msg)
    return merged

# --- 5. Bridge Server Implementation ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.post("/v1/messages")
async def proxy_handler(request: Request):
    try:
        body = await request.json()
        logger.info(f"--- NEW REQUEST RECEIVED ---")
        raw_msgs = []
        for msg in body.get("messages", []):
            role, content = msg.get("role"), msg.get("content")
            if role == "user" and isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_result":
                        raw_msgs.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": str(b.get("content", ""))})
                    elif b.get("type") == "text":
                        raw_msgs.append({"role": "user", "content": b["text"]})
                continue
            if isinstance(content, list):
                content = "".join(b["text"] for b in content if b.get("type") == "text")
            raw_msgs.append({"role": role, "content": content})

        messages = merge_messages(raw_msgs)
        sys_p = body.get("system", "")
        if isinstance(sys_p, list): sys_p = "".join(b["text"] for b in sys_p if b.get("type") == "text")
        messages.insert(0, {"role": "system", "content": f"{sys_p}\n\nCRITICAL: Use NATIVE tool calls ONLY. Never output tool calls as text like 'ToolName({...})'. Always use the provided tool-calling functionality."})

        tools_reg = body.get("tools", [])
        payload = {
            "model": MODEL_NAME, "stream": True, "temperature": 0.0, "messages": messages,
            "tools": [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema", {})}} for t in tools_reg] if tools_reg else None
        }
        
        logger.debug(f"Payload to Jiutian: {json.dumps(payload, indent=2)}")

        async def stream_gen():
            headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
            yield f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": f"msg_br_{int(time.time())}", "type": "message", "role": "assistant", "model": MODEL_NAME, "content": [], "stop_reason": None, "usage": {"input_tokens": 0, "output_tokens": 0}}})}\n\n'

            router, block_idx, text_started, active_tools, full_text, finish_reason = IntentRouter(tools_reg), 0, False, {}, "", None

            async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=None) as client:
                try:
                    async with client.stream("POST", TARGET_URL, json=payload, headers=headers) as resp:
                        if resp.status_code != 200:
                            err = (await resp.aread()).decode('utf-8', errors='replace')
                            logger.error(f"Target Error {resp.status_code}: {err}")
                            yield f'event: error\ndata: {json.dumps({"type": "error", "error": {"type": "api_error", "message": f"Jiutian API {resp.status_code}: {err}"}})}\n\n'
                            return

                        parser = SSEParser()
                        async for chunk in resp.aiter_bytes():
                            for data_str in parser.feed(chunk):
                                if data_str == "[DONE]": 
                                    logger.debug("SSE Stream: [DONE] received")
                                    break
                                try:
                                    logger.debug(f"Raw Chunk: {data_str}")
                                    data = json.loads(data_str)
                                    choice = data.get("choices", [{}])[0]
                                    delta = choice.get("delta", {})
                                    if choice.get("finish_reason"): finish_reason = choice["finish_reason"]

                                    if delta.get("content"):
                                        txt = delta["content"]
                                        full_text += txt
                                        if not text_started:
                                            yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "text", "text": ""}})}\n\n'
                                            text_started = True
                                        yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_idx, "delta": {"type": "text_delta", "text": txt}})}\n\n'

                                    for tc in delta.get("tool_calls", []):
                                        idx = tc.get("index", 0)
                                        if idx not in active_tools:
                                            if text_started:
                                                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'
                                                block_idx += 1; text_started = False
                                            active_tools[idx] = {"id": tc.get("id") or f"call_{time.time_ns()}", "name": "", "args": "", "block_idx": block_idx}
                                            block_idx += 1
                                            logger.info(f"Tool Call Started: idx={idx} id={active_tools[idx]['id']}")
                                        
                                        info = active_tools[idx]
                                        if tc.get("function", {}).get("name"): 
                                            info["name"] += tc["function"]["name"]
                                            logger.debug(f"Tool Name Update: {info['name']}")
                                        if tc.get("function", {}).get("arguments"): 
                                            info["args"] += tc["function"]["arguments"]
                                            logger.debug(f"Tool Args Update (accumulated): {info['args']}")
                                except Exception as e:
                                    logger.error(f"Chunk processing error: {e}")
                except Exception as e:
                    logger.error(f"Stream Exception: {e}")
                    yield f'event: error\ndata: {json.dumps({"type": "error", "error": {"type": "api_error", "message": f"Bridge Stream Loss: {str(e)}"}})}\n\n'

            if text_started:
                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'
            
            # Emit Native Tools
            for t_idx, info in sorted(active_tools.items()):
                if not info["name"]: continue
                logger.info(f"Finalizing Native Tool: {info['name']}")
                args = robust_parse_args(info["args"])
                logger.info(f"Final Repaired Args for {info['name']}: {json.dumps(args, indent=2)}")
                
                yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": info["id"], "name": info["name"], "input": {}}})}\n\n'
                yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": json.dumps(args, ensure_ascii=False)}})}\n\n'
                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'

            # Emit Hallucinated Tools (Intent Router)
            if not active_tools:
                synthetic = router.detect_hallucinated_tool_calls(full_text)
                if synthetic: logger.info(f"Found {len(synthetic)} Synthetic Intents")
                for i, (name, args) in enumerate(synthetic):
                    tid = f"synth_{int(time.time())}_{i}"
                    logger.debug(f"Emitting Synthetic Tool: {name} with args {list(args.keys())}")
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "tool_use", "id": tid, "name": name, "input": {}}})}\n\n'
                    yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_idx, "delta": {"type": "input_json_delta", "partial_json": json.dumps(args, ensure_ascii=False)}})}\n\n'
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'
                    block_idx += 1; active_tools[f"synth_{i}"] = {"id": tid}

            stop = "tool_use" if (finish_reason in ["tool_calls", "function_call"] or active_tools) else "end_turn"
            logger.info(f"Request Finished. Stop Reason: {stop}")
            yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 0}})}\n\n'
            yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'

        return StreamingResponse(stream_gen(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
    except Exception as e:
        logger.error(f"Fatal Bridge Error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
