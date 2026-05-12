#!/usr/bin/env python3
"""
OpenAI/Anthropic Bridge - Main Application

This is the main application file for the OpenAI/Anthropic Bridge.
It imports all components from the core package and sets up the FastAPI application.

The bridge translates between the Anthropic and OpenAI API formats,
enabling seamless integration with various AI development tools and platforms.
"""
import os
import json
import logging
import logging.handlers
import httpx
import time
import uuid
import re
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from contextlib import asynccontextmanager
import asyncio

# Import from core package
from core import EXPERT_PERSONA
from core import NetworkCircuitBreaker, RateLimiter
from core import robust_parse_args, merge_messages, SSEParser, validate_tool_call_id, generate_tool_call_id, ChimeraLogger

load_dotenv()

class AnthropicMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: str
    content: Any

class AnthropicRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    messages: List[AnthropicMessage]

# --- Global State ---
http_client: Optional[httpx.AsyncClient] = None
shutdown_event = asyncio.Event()
active_connections = 0

# --- 2. Configuration ---
TARGET_URL = os.environ.get("BRIDGE_TARGET_URL", "")
API_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
MODEL_NAME = os.environ.get("BRIDGE_MODEL", "")
SYSTEM_OVERRIDE = os.environ.get("BRIDGE_SYSTEM_OVERRIDE", "")
SSL_VERIFY = os.environ.get("BRIDGE_SSL_VERIFY", "true").lower() == "true"

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = os.environ.get("BRIDGE_RATE_LIMIT_ENABLED", "false").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.environ.get("BRIDGE_RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = float(os.environ.get("BRIDGE_RATE_LIMIT_WINDOW", "60.0"))

# Upstream Configuration
UPSTREAM_TIMEOUT = float(os.environ.get("BRIDGE_UPSTREAM_TIMEOUT", "600.0"))
RETRY_MAX_ATTEMPTS = int(os.environ.get("BRIDGE_RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY = float(os.environ.get("BRIDGE_RETRY_BASE_DELAY", "1.0"))
MAX_PAYLOAD_SIZE = int(os.environ.get("BRIDGE_MAX_PAYLOAD_SIZE", "10485760"))  # 10MB default

# Global circuit breaker and rate limiter instances
circuit_breaker = NetworkCircuitBreaker()
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
            ChimeraLogger.error(
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
            circuit_breaker.total_latency_ms += duration_ms
            ChimeraLogger.info(
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
    """
    ChimeraLogger.info(
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
    """
    duration_ms = (time.time() - start_time) * 1000
    ChimeraLogger.info(
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
    """
    ChimeraLogger.error(
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
    """
    ChimeraLogger.warning(
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
    """
    return ChimeraLogger





def get_model_params() -> Dict[str, Any]:
    """
    Get model parameters from environment or use defaults.
    Returns a dict with model_params structure for JiuTian API.
    """
    # Try to load from environment variable
    env_params = os.environ.get("BRIDGE_MODEL_PARAMS", "")
    if env_params:
        try:
            return json.loads(env_params)
        except json.JSONDecodeError:
            ChimeraLogger.warning("Failed to parse BRIDGE_MODEL_PARAMS, using defaults")

    # Default model parameters
    return {
        "text": {
            "temperature": 0.0,
            "max_tokens": 131072,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "top_p": 0.95
        }
    }


# --- 4. Server ---
async def _wait_for_connections():
    global active_connections
    while active_connections > 0:
        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(verify=SSL_VERIFY, timeout=httpx.Timeout(UPSTREAM_TIMEOUT))
    yield
    shutdown_event.set()
    try:
        await asyncio.wait_for(_wait_for_connections(), timeout=10.0)
    except asyncio.TimeoutError:
        pass
    if http_client:
        await http_client.aclose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log_error(
        getattr(request.state, "request_id", "unknown"),
        request.url.path,
        request.method,
        f"Validation Error: {exc.errors()}",
        400
    )
    return JSONResponse(
        status_code=400,
        content={"error": {"message": "Invalid request payload", "details": exc.errors()}}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_error(
        getattr(request.state, "request_id", "unknown"),
        request.url.url.path,
        request.method,
        f"Internal Server Error: {str(exc)}",
        500
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"message": "Internal Server Error", "details": str(exc)}}
    )


@app.get("/")
async def root():
    return {"status": "online", "bridge": "openai-anthropic", "model": MODEL_NAME}


@app.get("/metrics")
async def get_metrics():
    metrics = [
        f'bridge_requests_total {circuit_breaker.total_requests}',
        f'bridge_failures_total {circuit_breaker.total_failures}',
        f'bridge_request_latency_ms_sum {circuit_breaker.total_latency_ms}',
        f'bridge_circuit_breaker_state{{state="{circuit_breaker.state}"}} 1',
        f'bridge_active_connections {active_connections}'
    ]
    return PlainTextResponse("\n".join(metrics) + "\n")


@app.get("/health")
async def health():
    # Rate limiting check for health endpoint
    if not rate_limiter.is_allowed():
        retry_after = rate_limiter.get_retry_after()
        ChimeraLogger.warning(f"Rate limit exceeded for health check. Retry after: {retry_after} seconds")
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
            with httpx.Client(verify=SSL_VERIFY, timeout=httpx.Timeout(5.0)) as client:
                start_time = time.time()
                try:
                    headers = {
                        "Authorization": f"Bearer {API_TOKEN}" if API_TOKEN else "",
                        "Content-Type": "application/json",
                    }
                    # The upstream only accepts POST — send a minimal probe body.
                    # A 400/401/422 still means the upstream is alive; only 5xx = down.
                    probe_body = {"model": MODEL_NAME, "messages": [], "max_tokens": 1}
                    resp = client.post(TARGET_URL, json=probe_body, headers=headers)
                    latency_ms = (time.time() - start_time) * 1000
                    upstream_status = "ok" if resp.status_code < 500 else "error"
                    upstream_latency_ms = latency_ms
                except Exception as e:
                    upstream_status = "error"
                    ChimeraLogger.warning(f"Upstream health check failed: {e}")
        except Exception as e:
            upstream_status = "error"
            ChimeraLogger.warning(f"Health check error: {e}")
    else:
        upstream_status = "not_configured"
        ChimeraLogger.info("Upstream URL not configured, skipping upstream health check")

    health_status["upstream"] = {
        "status": upstream_status,
        "latency_ms": upstream_latency_ms
    }

    status_code = 200 if upstream_status == "ok" else 503
    return JSONResponse(health_status, status_code=status_code)


@app.post("/v1/messages")
async def proxy_handler(payload: AnthropicRequest, request: Request):
    if shutdown_event.is_set():
        return JSONResponse({"error": {"message": "Server is shutting down"}}, status_code=503)

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

        body = payload.model_dump(mode='json')
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
        # EXPERT_PERSONA is a module-level constant (allocated once at startup).

        # 1. Start with the Base System Override (if any)
        final_sys = SYSTEM_OVERRIDE or ""

        # 2. Add the Bridge Expert Persona (The "How to think" layer)
        if EXPERT_PERSONA:
            final_sys = f"{final_sys}\n\n{EXPERT_PERSONA}" if final_sys else EXPERT_PERSONA

        # 3. Add the User's settings.json / Project Rules (The "What to obey" layer)
        # We put this LAST so it has the highest priority and recency influence.
        if sys_p:
            final_sys = f"{final_sys}\n\n[USER RULES & PROJECT PROTOCOLS]\n{sys_p}" if final_sys else sys_p

        # [CIRCUIT BREAKER] Detect repeated tool calls in message history to break agentic loops
        repeats = 0
        last_calls = None
        read_history = []  # Track last 10 read/list paths to catch cyclical loops
        last_read_file = None
        actions_since_read = 0

        # Scan messages backwards to find loop patterns
        assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]

        for msg in reversed(assistant_messages):
            if "tool_calls" in msg:
                current_calls = [tc.get("function", {}).get("name") for tc in msg["tool_calls"]]

                for tc in msg["tool_calls"]:
                    name = tc.get("function", {}).get("name")

                    # Track Read/List operations AND all Bash commands for loop detection.
                    # Any Bash command (curl, grep, cat, find, …) repeated with the same
                    # arguments without intervening progress counts as a loop.
                    is_read = name in ["Read", "view_file", "list_dir"]
                    is_trackable_bash = name == "Bash"

                    if is_read or is_trackable_bash:
                        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                        # For Bash: track the full command string as the "key"
                        file_path = args.get("file_path") or args.get("AbsolutePath") or args.get("path") or args.get("DirectoryPath") or args.get("command", "")

                        if file_path:
                            # Immediate Repeat Detection
                            if file_path == last_read_file and actions_since_read == 0:
                                repeats += 1

                            # Cyclical Loop Detection (Last 10 paths/commands)
                            if file_path in read_history:
                                repeats += 0.5 # Fractional weight for cyclical hits

                            read_history.append(file_path)
                            if len(read_history) > 10: read_history.pop(0)

                            last_read_file = file_path
                            actions_since_read = 0
                    elif name not in ["Read", "view_file", "list_dir", "ls"]:
                        actions_since_read += 1

                # Check if the overall tool call pattern is repeating
                if last_calls == current_calls and current_calls:
                    repeats += 1
                elif last_calls is not None:
                    # Chain is broken! Stop scanning backwards so old, resolved loops don't haunt future requests.
                    break

                last_calls = current_calls

                if repeats >= 2.5: break # Threshold reached

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
                "1. You MUST switch to a DIFFERENT tool. Do NOT call the same tool again.\n"
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

        async def _internal_stream_gen():
            if not circuit_breaker.can_request():
                yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": "Error: Circuit Breaker OPEN. Upstream service is temporarily unreachable."}})}\n\n'
                return

            msg_id = f"msg_{uuid.uuid4().hex}"
            input_tokens, output_tokens = 0, 0
            yield f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "model": MODEL_NAME, "content": [], "stop_reason": None, "usage": {"input_tokens": 0, "output_tokens": 0}}})}\n\n'

            block_idx, text_started, active_tools, tool_results = 0, False, {}, []
            thinking_started = False  # Tracks if a thinking block is open
            for attempt in range(RETRY_MAX_ATTEMPTS):
                try:
                    async with http_client.stream("POST", TARGET_URL, json=payload, headers={"Authorization": f"Bearer {API_TOKEN}"}) as resp:
                        if resp.status_code != 200:
                            if resp.status_code >= 500:
                                circuit_breaker.record_failure()
                            if resp.status_code in [502, 503, 504] and attempt < RETRY_MAX_ATTEMPTS - 1:
                                delay = RETRY_BASE_DELAY * (2 ** attempt)
                                log_warning(request_id, endpoint, method, f"Upstream 50x error ({resp.status_code}), retrying in {delay}s...")
                                await asyncio.sleep(delay)
                                continue

                            # Limit reading to prevent OOM on massive error pages
                            err_chunk = await resp.aread()
                            err_body = err_chunk[:4096] # 4KB max
                            log_error(request_id, endpoint, method, f"Upstream Error {resp.status_code}: {err_body.decode(errors='replace')}")
                            yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": f"Error from upstream: {resp.status_code}"}})}\n\n'
                            return

                        parser = SSEParser()
                        async for chunk in resp.aiter_bytes():
                            if shutdown_event.is_set():
                                break
                            for data_str in parser.feed(chunk):
                                if data_str == "[DONE]": break
                                try:
                                    data = json.loads(data_str)
                                    # Capture Usage data if present
                                    usage = data.get("usage")
                                    if usage:
                                        input_tokens = usage.get("prompt_tokens", input_tokens)
                                        output_tokens = usage.get("completion_tokens", output_tokens)

                                    choice = data.get("choices", [{}])[0]
                                    delta = choice.get("delta", {})

                                    # Handle Reasoning / Thinking Content (OpenAI reasoning_content → Anthropic thinking block)
                                    reasoning_chunk = delta.get("reasoning_content") or delta.get("reasoning")
                                    if reasoning_chunk:
                                        if not thinking_started:
                                            yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "thinking", "thinking": ""}})}\n\n'
                                            thinking_started = True
                                        yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_idx, "delta": {"type": "thinking_delta", "thinking": reasoning_chunk}})}\n\n'

                                    # Handle Text Content
                                    if delta.get("content"):
                                        if thinking_started:
                                            # Close the thinking block before opening a text block
                                            yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'
                                            block_idx += 1; thinking_started = False
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
                    circuit_breaker.record_success()
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                    circuit_breaker.record_failure()
                    if attempt < RETRY_MAX_ATTEMPTS - 1:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        log_warning(request_id, endpoint, method, f"Connection error ({str(e)}), retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        log_error(request_id, endpoint, method, f"Connection Failed after {RETRY_MAX_ATTEMPTS} attempts: {str(e)}")
                        yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "text", "text": f"Connection Failed: {str(e)}"}})}\n\n'
                except Exception as e:
                    log_error(request_id, endpoint, method, f"Connection Error: {e}")
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_idx, "content_block": {"type": "text", "text": f"Connection Error: {str(e)}"}})}\n\n'

            # --- Finalization Phase ---
            if thinking_started:
                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'
                block_idx += 1
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
                    ChimeraLogger.debug(f"Stripped hallucinated 'status' field from {native_name} call")

                    # FIX 3: Guard against empty-arg tool calls which cause Claude Code to loop.
                    if not args and native_name in _EMPTY_ARGS_DEFAULTS:
                        args = _EMPTY_ARGS_DEFAULTS[native_name]
                    log_warning(request_id, endpoint, method, f"Empty args for '{native_name}' — injecting safe default: {args}")

                    # FIX 1 (fallback path): Use the tool_id already set in info dict (FIX 1)
                    tool_id = info.get("tool_id", generate_tool_call_id(0))
                    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": info["block_idx"], "content_block": {"type": "tool_use", "id": tool_id, "name": native_name, "input": {}}})}\n\n'
                    yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": info["block_idx"], "delta": {"type": "input_json_delta", "partial_json": json.dumps(args)}})}\n\n'
                    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": info["block_idx"]})}\n\n'

            stop = "tool_use" if active_tools else "end_turn"
            # Finalize the message with actual usage
            yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}})}\n\n'
            yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'

        async def stream_gen():
            global active_connections
            active_connections += 1
            try:
                async for chunk in _internal_stream_gen():
                    yield chunk
            finally:
                active_connections -= 1

        return StreamingResponse(stream_gen(), media_type="text/event-stream")
    except Exception as e:
        log_error(request_id, endpoint, method, f"Fatal Proxy Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/v1/status")
async def status():
    """
    Status endpoint that returns JSON data for active_connections
    and the current NetworkCircuitBreaker status.
    """
    return JSONResponse({
        "active_connections": active_connections,
        "circuit_breaker": {
            "state": circuit_breaker.state,
            "failure_count": circuit_breaker.failure_count,
            "total_requests": circuit_breaker.total_requests,
            "total_failures": circuit_breaker.total_failures,
            "total_latency_ms": circuit_breaker.total_latency_ms,
            "last_failure_time": circuit_breaker.last_failure_time,
        },
        "rate_limiter": {
            "max_requests": rate_limiter.max_requests,
            "window_seconds": rate_limiter.window_seconds,
            "requests_count": len(rate_limiter.requests),
        },
        "model": MODEL_NAME,
        "upstream_url": TARGET_URL,
        "status": "ok",
    })


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 57123))
    uvicorn.run(app, host="0.0.0.0", port=port)
