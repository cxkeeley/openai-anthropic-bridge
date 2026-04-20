import json
import uuid
import logging
import traceback
import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from flask import Flask, request, Response, stream_with_context
import requests
import urllib3

# Suppress only the single warning from urllib3 needed for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration from environment
TARGET_URL = os.environ.get("JTIU_TARGET_URL", "")
TOKEN = os.environ.get("JTIU_TOKEN", "")
MODEL_NAME = os.environ.get("JTIU_MODEL", "jt_indonesia")
SYSTEM_OVERRIDE = os.environ.get("JTIU_SYSTEM_OVERRIDE", "")
SSL_VERIFY = os.environ.get("JTIU_SSL_VERIFY", "true").lower() == "true"

class RobustSSEParser:
    """Robust parser for SSE streams that handles byte-level fragmentation."""
    def __init__(self):
        self.buffer = b""
        self.logger = logging.getLogger("SSEParser")

    def parse(self, chunk):
        """Processes a raw byte chunk and yields complete data objects."""
        self.buffer += chunk
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            line = line.decode('utf-8', errors='replace').strip()

            if line.startswith("data:"):
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    yield "[DONE]"
                    continue
                try:
                    yield json.loads(data_str)
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse SSE line: {line[:100]}...")

class ToolArgumentRepair:
    """Heuristic logic to repair missing brackets in model-generated tool arguments."""
    def __init__(self):
        self.open_template_literals = 0
        self.lookbehind = ""
        self.logger = logging.getLogger("RepairLogic")

    def repair_delta(self, fragment):
        """Detects and repairs unclosed sequences in a code fragment."""
        if not fragment:
            return fragment

        original = fragment
        # Update lookbehind (maintain context)
        current_context = (self.lookbehind + fragment)[-100:]

        # 1. Detect unclosed template literals ${...
        self.open_template_literals += fragment.count("${")
        if self.open_template_literals > 0 and "}" in fragment:
            self.open_template_literals -= fragment.count("}")
            if self.open_template_literals < 0:
                self.open_template_literals = 0

        # 2. Smart Variable Closure
        # If we see a character that ends a variable name but doesn't close the template
        # and the previous character was a word character, and we're in a template.
        if self.open_template_literals > 0:
            import re
            # Heuristic: If it looks like a variable name followed by a separator or newline
            if fragment and fragment[0] in [";", ")", ",", "\n", "`"]:
                if re.search(r"[a-zA-Z0-9_]$", self.lookbehind):
                    if not fragment.startswith("}"):
                        fragment = "}" + fragment
                        self.open_template_literals -= 1
                        self.logger.info(f"Smart repaired template closure: {repr(original)} -> {repr(fragment)}")

        # 3. Simple Template repair (fallback)
        if self.open_template_literals > 0:
            if "`" in fragment and "${" not in fragment:
                # If we have an open ${ and see a `, it's almost certainly a missing }
                if not fragment.startswith("}"):
                    fragment = fragment.replace("`", "}`")
                    self.open_template_literals -= 1
                    self.logger.info(f"Repaired terminal template closure: {repr(original)} -> {repr(fragment)}")

        # 4. Simple Block Repair
        stripped = fragment.lstrip()

        # JSDoc Type Repair: @param {Array data -> needs } after Array
        if "@param {" in current_context or "@returns {" in current_context:
            if " " in stripped and "}" not in stripped and "{" not in stripped:
                parts = stripped.split(" ", 1)
                if len(parts) > 1 and not parts[0].endswith("}"):
                    if parts[0] in ["Array", "Object", "String", "Number", "Boolean", "Promise"]:
                        fragment = fragment.replace(parts[0], parts[0] + "}")
                        self.logger.info(f"Repaired JSDoc type: {repr(original)} -> {repr(fragment)}")

        # Block keywords
        if any(stripped.startswith(k) for k in ["else", "catch", "finally"]):
            prev_content = self.lookbehind.strip()
            if prev_content and not prev_content.endswith("}"):
                if not original.strip().startswith("}"):
                    if "\n" in original or original.startswith(" "):
                        ws_len = len(fragment) - len(stripped)
                        indent = fragment[:ws_len]
                        fragment = indent + "}" + stripped
                        self.logger.info(f"Repaired block end: {repr(original)} -> {repr(fragment)}")

        # Update lookbehind
        self.lookbehind = current_context
        return fragment

    def finalize(self):
        """Returns any necessary closing characters when the stream ends."""
        cleanup = ""
        if self.open_template_literals > 0:
            cleanup += "}" * self.open_template_literals
            self.logger.info(f"Finalizing stream: closing {self.open_template_literals} template literals")
            self.open_template_literals = 0
        return cleanup




def setup_logging():
    """Setup logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bridge.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

class SafeSession:
    def __init__(self, timeout=30, max_retries=3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = setup_logging()

    def post(self, url, **kwargs):
        """Safely make a POST request with retry logic and timeout"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Set timeout from our instance, override any user-provided timeout
                kwargs['timeout'] = self.timeout

                # Disable SSL verification for self-signed certs if configured
                kwargs['verify'] = SSL_VERIFY

                response = requests.post(url, **kwargs)

                # Log the response for monitoring
                self.logger.info(f"Request to {url} succeeded with status {response.status_code}")

                return response

            except requests.exceptions.Timeout:
                last_error = f"Request timed out after {self.timeout} seconds (attempt {attempt + 1}/{self.max_retries})"
                self.logger.warning(last_error)

            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {str(e)} (attempt {attempt + 1}/{self.max_retries})"
                self.logger.error(last_error)

            except Exception as e:
                last_error = f"Unexpected error: {str(e)} (attempt {attempt + 1}/{self.max_retries})"
                self.logger.error(last_error)

            # If not the last attempt, wait a bit before retrying
            if attempt < self.max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff

        # If we get here, all attempts failed
        self.logger.error(f"All {self.max_retries} attempts failed. Last error: {last_error}")

        # Return a mock response with error status
        class MockResponse:
            def __init__(self, status_code, text):
                self.status_code = status_code
                self.text = text
                self.content = text.encode('utf-8')

            def json(self):
                return {"error": last_error}

        return MockResponse(500, json.dumps({"error": last_error}))

app = Flask(__name__)
session = SafeSession()

# Target configuration moved to top

# Add health check endpoint
class HealthCheck:
    def __init__(self, app, target_url, token):
        self.app = app
        self.target_url = target_url
        self.token = token
        self.session = SafeSession()

        @app.route('/health', methods=['GET'])
        def health():
            try:
                # Test connection to target
                headers = {"Authorization": f"Bearer {self.token}"}
                response = self.session.post(
                    self.target_url,
                    json={"model": MODEL_NAME, "messages": [{"role": "user", "content": "ping"}]},
                    headers=headers
                )

                if response.status_code == 200:
                    return {'status': 'healthy', 'target': 'reachable'}, 200
                else:
                    return {
                        'status': 'degraded',
                        'target': 'unreachable',
                        'target_status': response.status_code
                    }, 503

            except Exception as e:
                return {
                    'status': 'unhealthy',
                    'target': 'unreachable',
                    'error': str(e)
                }, 503

# Initialize health check
health_check = HealthCheck(app, TARGET_URL, TOKEN)

# ----- 1. ANTHROPIC TO OPENAI TRANSLATOR (For Claude Code) -----
@app.route('/v1/messages', methods=['POST'])
def proxy_anthropic():
    print("Received Anthropic API request (Claude Code)")

    try:
        anthropic_payload = request.get_json()

        # Map to OpenAI format
        openai_payload = {
            "model": MODEL_NAME,
            "stream": anthropic_payload.get("stream", False),
            "messages": []
        }

        if "temperature" in anthropic_payload:
            openai_payload["temperature"] = anthropic_payload["temperature"]
        if "max_tokens" in anthropic_payload:
            openai_payload["max_tokens"] = anthropic_payload["max_tokens"]

        # System prompt handling
        sys_val = anthropic_payload.get("system", "")
        if isinstance(sys_val, list):
            sys_val = "".join(b["text"] for b in sys_val if b.get("type") == "text")

        core_rules = (
            "\n\nCRITICAL INSTRUCTION: You MUST execute tools natively using the OpenAI function calling schema! "
            "DO NOT output text like 'Write({...})' or 'Bash({...})' or '[Tool Use: ...]' as plain text responses! "
            "If you need to write a file or run a command, you MUST actively invoke the JSON tool API hook. "
            "Never hallucinate a 'Write' tool, use the 'Bash' or 'Edit' tools provided to you! "
            "If a tool fails with an error, DO NOT keep trying to use the same tool in an endless loop. "
            "Instead, immediately switch to an alternative tool (like using Bash instead of Edit). "
            "IMPORTANT REPOSITORY RULE: You must NEVER try to read or modify files outside of the user's current project directory. "
            "Do NOT search for global files like .env or configuration files in the user's home or root directories. Focus exclusively on the local repository. "
            "LANGUAGE RULE: You MUST always respond and communicate with the user in English. Never use Chinese unless explicitly requested."
        )

        # Combine original prompt + core rules + optional persona override from .env
        full_system_prompt = sys_val + core_rules
        if SYSTEM_OVERRIDE:
            full_system_prompt = SYSTEM_OVERRIDE + "\n\n" + full_system_prompt

        print(f"DEBUG: Personas loaded: {SYSTEM_OVERRIDE[:100]}...")
        openai_payload["messages"].append({"role": "system", "content": full_system_prompt})

        # ++++ MAP TOOLS FROM ANTHROPIC TO OPENAI ++++
        if "tools" in anthropic_payload:
            openai_payload["tools"] = []
            for t in anthropic_payload["tools"]:
                openai_payload["tools"].append({
                    "type": "function",
                    "function": {
                        "name": t.get("name"),
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {})
                    }
                })

        if "tool_choice" in anthropic_payload:
            choice = anthropic_payload["tool_choice"]
            if choice.get("type") == "tool":
                openai_payload["tool_choice"] = {
                    "type": "function",
                    "function": {"name": choice.get("name")}
                }
            elif choice.get("type") == "any":
                openai_payload["tool_choice"] = "required"
            elif choice.get("type") == "auto":
                openai_payload["tool_choice"] = "auto"

        # Translate conversation history
        for msg in anthropic_payload.get("messages", []):
            role = "assistant" if msg["role"] == "assistant" else "user"
            content = msg["content"]

            # Anthropic content can be a list of blocks
            if isinstance(content, list):
                texts = []
                tool_calls = []

                for block in content:
                    if block.get("type") == "text":
                        texts.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(block.get("input", {}))
                            }
                        })
                    elif block.get("type") == "tool_result":
                        # Flush texts as a user message if we collected any before the result
                        if texts:
                            openai_payload["messages"].append({"role": "user", "content": "\n".join(texts)})
                            texts = []

                        # Anthropic tool result -> OpenAI tool message
                        tool_content = block.get("content", "")
                        if isinstance(tool_content, list):
                            tc_texts = [tc.get("text", "") for tc in tool_content if tc.get("type") == "text"]
                            tool_content_str = "\n".join(tc_texts)
                        else:
                            tool_content_str = str(tool_content)

                        raw_tool_id = block.get("tool_use_id", "")
                        # Remove 'toolu_' prefix if we added it earlier
                        if raw_tool_id.startswith("toolu_"):
                            raw_tool_id = raw_tool_id[6:]

                        openai_payload["messages"].append({
                            "role": "tool",
                            "tool_call_id": raw_tool_id,
                            "content": tool_content_str
                        })

                # Finish up remaining blocks
                if texts or tool_calls:
                    m = {"role": role}
                    if texts:
                        m["content"] = "\n".join(texts)
                    else:
                        m["content"] = ""
                    if tool_calls:
                        m["tool_calls"] = tool_calls
                    openai_payload["messages"].append(m)
            else:
                openai_payload["messages"].append({"role": role, "content": str(content)})

        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        }

        # Stream handling
        is_stream = openai_payload["stream"]

        try:
            # Use our safe session with retry logic
            resp = session.post(TARGET_URL, json=openai_payload, headers=headers, stream=is_stream)
        except Exception as e:
            error_msg = f"Failed to connect to target: {str(e)}"
            app.logger.error(error_msg)
            return Response(
                json.dumps({"error": error_msg}),
                status=500,
                mimetype='application/json'
            )

        # Stream mapping back to Anthropic
        if is_stream:
            def generate_anthropic_stream():
                try:
                    yield f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": f"msg_{uuid.uuid4().hex}", "type": "message", "role": "assistant", "model": MODEL_NAME, "content": []}})}\n\n'

                    active_tool_calls = {}  # index -> block_index mapping
                    current_block_index = 0
                    has_started_text = False
                    finish_reason = "end_turn"
                    total_usage = {"input_tokens": 0, "output_tokens": 0}

                    parser = RobustSSEParser()
                    repair_logic = ToolArgumentRepair()

                    for raw_chunk in resp.iter_content(chunk_size=4096):
                        for chunk in parser.parse(raw_chunk):
                            if chunk == "[DONE]":
                                break

                            try:
                                if 'choices' not in chunk or not chunk['choices']:
                                    # Check for usage data in chunks (some providers send it at the end)
                                    if 'usage' in chunk:
                                        total_usage.update(chunk['usage'])
                                    continue

                                delta = chunk['choices'][0].get('delta', {})

                                # Safely fetch stop status (tool_call vs end_turn)
                                fr = chunk['choices'][0].get('finish_reason')
                                if fr in ['tool_calls', 'function_call']:
                                    finish_reason = "tool_use"
                                elif fr in ['stop', 'length']:
                                    finish_reason = "end_turn"

                                # 1. Map Text
                                if 'content' in delta and delta['content']:
                                    if not has_started_text:
                                        has_started_text = True
                                        yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": current_block_index, "content_block": {"type": "text", "text": ""}})}\n\n'
                                    yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": current_block_index, "delta": {"type": "text_delta", "text": delta["content"]}})}\n\n'

                                # 2. Map Tool Calling Requests Stream
                                if 'tool_calls' in delta:
                                    for tc in delta['tool_calls']:
                                        tc_idx = tc.get('index')
                                        # First chunk of new tool call
                                        if tc_idx not in active_tool_calls:
                                            if has_started_text:
                                                yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": current_block_index})}\n\n'
                                                has_started_text = False
                                                current_block_index += 1

                                            active_tool_calls[tc_idx] = current_block_index
                                            tool_name = tc.get('function', {}).get('name', 'unknown_tool')
                                            tool_id = tc.get('id', f"toolu_{uuid.uuid4().hex[:16]}")

                                            if not tool_id.startswith("toolu_"):
                                                tool_id = f"toolu_{tool_id}"

                                            yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": current_block_index, "content_block": {"type": "tool_use", "id": tool_id, "name": tool_name, "input": {}}})}\n\n'
                                            current_block_index += 1
                                            finish_reason = "tool_use"

                                        # Output the streaming arguments JSON delta
                                        if 'function' in tc and 'arguments' in tc['function'] and tc['function']['arguments']:
                                            block_idx = active_tool_calls[tc_idx]
                                            arg_fragment = tc["function"]["arguments"]

                                            # Apply heuristic repair logic
                                            repaired_fragment = repair_logic.repair_delta(arg_fragment)

                                            yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_idx, "delta": {"type": "input_json_delta", "partial_json": repaired_fragment}})}\n\n'

                            except Exception as e:
                                app.logger.error(f"Error processing stream chunk: {str(e)}")
                                continue

                    # Stop any open blocks cleanly
                    if has_started_text:
                        yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": current_block_index})}\n\n'

                    for tc_idx, block_idx in active_tool_calls.items():
                        # Final heuristic repair check
                        cleanup = repair_logic.finalize()
                        if cleanup:
                            yield f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_idx, "delta": {"type": "input_json_delta", "partial_json": cleanup}})}\n\n'
                        
                        yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_idx})}\n\n'

                    yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": finish_reason, "stop_sequence": None}, "usage": {"output_tokens": total_usage.get("completion_tokens", 0)}})}\n\n'
                    yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'
                except Exception as e:
                    app.logger.error(f"Error in stream generation: {str(e)}")
                    yield f'event: error\ndata: {json.dumps({"type": "error", "error": {"type": "api_error", "message": str(e)}})}\n\n'

            return Response(stream_with_context(generate_anthropic_stream()), status=resp.status_code, headers={"Content-Type": "text/event-stream"})
        else:
            # non streaming translation
            try:
                result = resp.json()
                anthropic_resp = {
                    "id": "msg_123", "type": "message", "role": "assistant", "model": MODEL_NAME,
                    "content": [{"type": "text", "text": result['choices'][0]['message']['content']}],
                    "stop_reason": "end_turn", "usage": {"input_tokens": 0, "output_tokens": 0}
                }
                return Response(json.dumps(anthropic_resp), resp.status_code, headers={"Content-Type": "application/json"})
            except Exception as e:
                app.logger.error(f"Error parsing non-streaming response: {str(e)}")
                return Response(json.dumps({"error": "Failed to parse response from target"}), 500, headers={"Content-Type": "application/json"})

    except Exception as e:
        app.logger.error(f"Error in proxy_anthropic: {str(e)}")
        return Response(json.dumps({"error": str(e)}), 500, headers={"Content-Type": "application/json"})


# ----- 2. PURE OPENAI PROXY (Direct pass-through) -----
@app.route('/v1/chat/completions', methods=['POST'])
def proxy_openai():
    print("Received OpenAI API request")

    try:
        payload = request.get_json()
        payload["model"] = MODEL_NAME

        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        }

        is_stream = payload.get("stream", False)

        try:
            # Use our safe session with retry logic
            resp = session.post(TARGET_URL, json=payload, headers=headers, stream=is_stream)
        except Exception as e:
            error_msg = f"Failed to connect to target: {str(e)}"
            app.logger.error(error_msg)
            return Response(
                json.dumps({"error": error_msg}),
                status=500,
                mimetype='application/json'
            )

        if is_stream:
            def generate():
                try:
                    for chunk in resp.iter_content(chunk_size=1024):
                        yield chunk
                except Exception as e:
                    app.logger.error(f"Error in stream generation: {str(e)}")

            return Response(stream_with_context(generate()), resp.status_code, headers={"Content-Type": resp.headers.get("Content-Type", "text/event-stream")})
        else:
            return Response(resp.content, resp.status_code, headers={"Content-Type": "application/json"})

    except Exception as e:
        app.logger.error(f"Error in proxy_openai: {str(e)}")
        return Response(json.dumps({"error": str(e)}), 500, headers={"Content-Type": "application/json"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Listening on http://{host}:{port}")
    print(f"Claude Code Proxy Endpoint: http://{host}:{port}")
    app.run(port=port, host=host)
