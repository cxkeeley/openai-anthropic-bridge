"""
Transformers module for the OpenAI/Anthropic Bridge.

This module contains JSON/Argument transformers and message processors.
"""
import json
import uuid
import re
import time
from typing import List, Dict, Any, Optional


def robust_parse_args(raw: str) -> dict:
    """
    Robustly parse raw string input into a dictionary.
    Handles truncated JSON, common hallucinations, and normalization.
    """
    if not raw:
        return {}

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

        # --- The "Intended State' Translator Layer ---
        # Normalize common hallucinations to the Claude Code Tool Spec

        # 1. Path & URL Mapping
        for k in ['path', 'TargetFile', 'AbsolutePath', 'notebook_path', 'uri', 'link', 'filename']:
            if k in args:
                if 'file_path' not in args and k not in ['uri', 'link']:
                    args['file_path'] = args[k]
                if 'url' not in args and k in ['uri', 'link']:
                    args['url'] = args[k]
                if 'notebook_path' not in args and k == 'notebook_path':
                    args['notebook_path'] = args[k]

        # 2. Content & Prompt Mapping
        for k in ['text', 'CodeContent', 'TargetContent', 'ReplacementContent', 'new_string', 'new_source', 'instructions', 'task', 'replacement', 'original']:
            if k in args:
                if 'content' not in args and k in ['text', 'CodeContent']:
                    args['content'] = args[k]
                if 'prompt' not in args and k in ['instructions', 'task']:
                    args['prompt'] = args[k]
                if 'new_string' not in args and k in ['replacement', 'ReplacementContent']:
                    args['new_string'] = args[k]
                if 'old_string' not in args and k in ['original', 'TargetContent']:
                    args['old_string'] = args[k]

        # 3. Task & Project Mapping
        for k in ['title', 'name', 'subject']:
            if k in args and 'subject' not in args:
                args['subject'] = args[k]
        for k in ['summary', 'body', 'description']:
            if k in args and 'description' not in args:
                args['description'] = args[k]
        for k in ['addBlockedBy', 'blocked_by', 'depends_on', 'blockedBy']:
            if k in args:
                if 'blockedBy' not in args:
                    args['blockedBy'] = args[k]
                # If model sends empty list to 'add' parameter, it likely intends to clear
                if args[k] == [] and 'removeBlockedBy' not in args:
                    args['removeBlockedBy'] = []
        if 'body' in args and 'description' not in args:
            args['description'] = args['body']

        # 4. Command & Scheduling Mapping
        for k in ['cmd', 'CommandLine', 'script', 'command_line']:
            if k in args and 'command' not in args:
                args['command'] = args[k]

        if 'wait' in args and 'delaySeconds' not in args:
            args['delaySeconds'] = args['wait']
        if 'schedule' in args and 'cron' not in args:
            args['cron'] = args['schedule']

        # 5. ID Normalization (Handle taskId vs task_id)
        for k in ['taskId', 'task_id', 'id', 'cron_id', 'shell_id']:
            if k in args:
                val = str(args[k]).strip().strip('"').strip("'").strip()
                if 'id' not in args:
                    args['id'] = val
                if 'taskId' not in args:
                    args['taskId'] = val
                if 'task_id' not in args:
                    args['task_id'] = val

        # 6. Metadata Record Sync
        if 'metadata' in args and isinstance(args['metadata'], str):
            try:
                args['metadata'] = json.loads(args['metadata'])
            except:
                pass

        # 7. Status Normalization
        if 'status' in args:
            s = str(args['status']).lower().strip()
            if s in ['complete', 'done', 'finished']:
                args['status'] = 'completed'
            if s in ['in progress', 'working', 'started']:
                args['status'] = 'in_progress'

        # 8. Web & Search Mapping
        for k in ['q', 'search', 'search_query']:
            if k in args and 'query' not in args:
                args['query'] = args[k]

        return args
    except:
        # Final fallback: if JSON is still broken, return as much as we parsed
        return {"raw_input_error": raw}


def validate_tool_call_id(tool_call_id: str | None) -> bool:
    """
    Validate that a tool call ID matches the expected format.
    Expected format: 'toolu_' followed by alphanumeric characters.
    """
    if not tool_call_id:
        return False
    # Anthropic tool call IDs use the 'toolu_' prefix followed by alphanumeric chars
    pattern = r'^toolu_[a-zA-Z0-9]+$'
    return bool(re.match(pattern, tool_call_id))


def generate_tool_call_id(idx: int) -> str:
    """
    Generate a valid tool call ID that matches expected format
    """
    return f"toolu_{uuid.uuid4().hex[:24]}"


def merge_messages(messages: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
    """
    Merge consecutive messages with the same role.
    """
    if not messages:
        return []
    merged = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"] and msg["role"] != "tool":
            e, n = merged[-1]["content"], msg["content"]
            if isinstance(e, str) and isinstance(n, str):
                merged[-1]["content"] = e + "\n\n" + n
            elif isinstance(e, list) and isinstance(n, list):
                merged[-1]["content"].extend(n)
            if msg.get("tool_calls"):
                merged[-1].setdefault("tool_calls", []).extend(msg["tool_calls"])
        else:
            merged.append(msg)
    return merged


class SSEParser:
    """
    Simple Server-Sent Events parser.
    """
    def __init__(self):
        self.buffer = ""

    def feed(self, chunk: bytes):
        """
        Feed a chunk of data to the parser.
        Yields complete SSE blocks.
        """
        decoded = chunk.decode('utf-8', errors='replace')
        self.buffer += decoded
        while "\n\n" in self.buffer:
            block, self.buffer = self.buffer.split("\n\n", 1)
            for line in block.split("\n"):
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data:
                        yield data
