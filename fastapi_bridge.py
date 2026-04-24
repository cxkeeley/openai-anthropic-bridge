import os
import json
import logging
import logging.handlers
import httpx
import time
import sys
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

# --- 3. Core Utility ---
def robust_parse_args(raw: str) -> dict:
    if not raw: return {}
    try:
        args = json.loads(raw)

        # --- The "Intended State" Translator Layer ---

        # 1. Path & URL Mapping
        for k in ['path', 'TargetFile', 'AbsolutePath', 'notebook_path', 'uri', 'link']:
            if k in args:
                if 'file_path' not in args and k not in ['uri', 'link']: args['file_path'] = args[k]
                if 'url' not in args and k in ['uri', 'link']: args['url'] = args[k]
                if 'notebook_path' not in args and k == 'notebook_path': args['notebook_path'] = args[k]

        # 2. Content & Prompt Mapping
        for k in ['text', 'CodeContent', 'new_string', 'new_source', 'instructions', 'task']:
            if k in args:
                if 'content' not in args and k in ['text', 'CodeContent', 'new_string']: args['content'] = args[k]
                if 'prompt' not in args and k in ['instructions', 'task']: args['prompt'] = args[k]
                if 'new_source' not in args and k == 'new_source': args['new_source'] = args[k]

        # 3. Task Mapping
        if 'title' in args and 'subject' not in args: args['subject'] = args['title']
        if 'name' in args and 'subject' not in args: args['subject'] = args['name']
        if 'summary' in args and 'description' not in args: args['description'] = args['summary']
        if 'body' in args and 'description' not in args: args['description'] = args['body']

        # 4. Command & Scheduling Mapping
        if 'cmd' in args and 'command' not in args: args['command'] = args['cmd']
        if 'CommandLine' in args and 'command' not in args: args['command'] = args['CommandLine']
        if 'wait' in args and 'delaySeconds' not in args: args['delaySeconds'] = args['wait']
        if 'schedule' in args and 'cron' not in args: args['cron'] = args['schedule']

        # 5. Metadata Record Sync
        if 'metadata' in args and isinstance(args['metadata'], str):
            try: args['metadata'] = json.loads(args['metadata'])
            except: pass

        # 6. ID Cleaning
        for k in ['taskId', 'task_id', 'id', 'cron_id']:
            if k in args: args[k] = str(args[k]).strip().strip('"').strip("'").strip()

        # 7. Status Normalization
        if 'status' in args:
            s = str(args['status']).lower().strip()
            if s in ['complete', 'done', 'finished']: args['status'] = 'completed'
            if s in ['in progress', 'working', 'started']: args['status'] = 'in_progress'

        return args
    except: return {}

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

@app.post("/v1/messages")
async def proxy_handler(request: Request):
    try:
        body = await request.json()
        tools_list = {t["name"].lower(): t["name"] for t in body.get("tools", [])}

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

        payload = {
            "model": MODEL_NAME,
            "stream": True,
            "temperature": body.get("temperature", 0.0),
            "messages": messages,
            "tools": [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema", {})}} for t in body.get("tools", [])] if body.get("tools") else None
        }

        async def stream_gen():
            yield f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": f"msg_{int(time.time())}", "type": "message", "role": "assistant", "model": MODEL_NAME, "content": [], "stop_reason": None, "usage": {"input_tokens": 0, "output_tokens": 0}}})}\n\n'

            block_idx, text_started, active_tools = 0, False, {}
            async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=httpx.Timeout(600.0)) as client:
                async with client.stream("POST", TARGET_URL, json=payload, headers={"Authorization": f"Bearer {API_TOKEN}"}) as resp:
                    parser = SSEParser()
                    async for chunk in resp.aiter_bytes():
                        for data_str in parser.feed(chunk):
                            if data_str == "[DONE]": break
                            try:
                                data = json.loads(data_str)
                                choice = data.get("choices", [{}])[0]
                                delta = choice.get("delta", {})

                                if delta.get("content"):
                                    if not text_started:
                                        yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "text", "text": ""}})}\n\n'
                                        text_started = True
                                    yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_idx, "delta": {"type": "text_delta", "text": delta["content"]}})}\n\n'

                                for tc in delta.get("tool_calls", []):
                                    idx = tc.get("index", 0)
                                    if idx not in active_tools:
                                        if text_started:
                                            yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'
                                            block_idx += 1; text_started = False
                                        active_tools[idx] = {"id": tc.get("id"), "name": "", "args": "", "block_idx": block_idx, "started": False}
                                        block_idx += 1

                                    info = active_tools[idx]
                                    if tc.get("function", {}).get("name"): info["name"] += tc["function"]["name"]
                                    if tc.get("function", {}).get("arguments"):
                                        arg_chunk = tc["function"]["arguments"]
                                        if not info["started"] and info["name"]:
                                            native_name = tools_list.get(info["name"].lower(), info["name"])
                                            yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": info["id"], "name": native_name, "input": {}}})}\n\n'
                                            info["started"] = True
                                        info["args"] += arg_chunk
                                        yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": arg_chunk}})}\n\n'
                            except: pass

            if text_started:
                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'

            # Finalize Tools: ONLY emit stop if already started, OR emit full block if missed
            _NO_STATUS = {"TaskCreate", "TaskList", "TaskGet", "TaskOutput", "TaskStop"}
            for _, info in sorted(active_tools.items()):
                if info["started"]:
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'
                else:
                    native_name = tools_list.get(info["name"].lower(), info["name"])
                    args = robust_parse_args(info["args"])
                    if native_name in _NO_STATUS and "status" in args: del args["status"]
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": info["id"], "name": native_name, "input": {}}})}\n\n'
                    yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": json.dumps(args)}})}\n\n'
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'

            stop = "tool_use" if active_tools else "end_turn"
            yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 0}})}\n\n'
            yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'

        return StreamingResponse(stream_gen(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Fatal: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
