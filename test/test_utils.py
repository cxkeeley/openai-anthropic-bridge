"""Tests for utility functions."""
import pytest
from fastapi_bridge import validate_tool_call_id, generate_tool_call_id, merge_messages


class TestValidateToolCallId:
    """Test cases for validate_tool_call_id function."""

    def test_valid_tool_call_id(self):
        """Test valid tool call IDs."""
        assert validate_tool_call_id("call_abc123") is True
        assert validate_tool_call_id("call_abc_def") is True
        assert validate_tool_call_id("call_abc-def") is True
        assert validate_tool_call_id("call_abc.def") is True
        assert validate_tool_call_id("call_abc123def456") is True

    def test_invalid_tool_call_id(self):
        """Test invalid tool call IDs."""
        assert validate_tool_call_id("call_abc def") is False
        assert validate_tool_call_id("call_abc@def") is False
        assert validate_tool_call_id("call_abc#def") is False
        assert validate_tool_call_id("call_abc$def") is False
        assert validate_tool_call_id("call_abc%def") is False
        assert validate_tool_call_id("call_abc&def") is False
        assert validate_tool_call_id("call_abc*def") is False
        assert validate_tool_call_id("call_abc(def") is False
        assert validate_tool_call_id("call_abc)def") is False
        assert validate_tool_call_id("call_abc+def") is False
        assert validate_tool_call_id("call_abc=def") is False
        assert validate_tool_call_id("call_abc[def") is False
        assert validate_tool_call_id("call_abc]def") is False
        assert validate_tool_call_id("call_abc{def") is False
        assert validate_tool_call_id("call_abc}def") is False
        assert validate_tool_call_id("call_abc|def") is False
        assert validate_tool_call_id("call_abc\\def") is False
        assert validate_tool_call_id("call_abc?def") is False
        assert validate_tool_call_id("call_abc;def") is False
        assert validate_tool_call_id("call_abc,def") is False
        assert validate_tool_call_id("call_abc<def") is False
        assert validate_tool_call_id("call_abc>def") is False
        assert validate_tool_call_id("call_abc:def") is False
        assert validate_tool_call_id("call_abc/def") is False
        assert validate_tool_call_id("call_abc'def") is False
        assert validate_tool_call_id("call_abc`def") is False
        assert validate_tool_call_id("call_abc~def") is False
        assert validate_tool_call_id("call_abc!def") is False
        assert validate_tool_call_id("call_abc@def") is False
        assert validate_tool_call_id("call_abc#def") is False
        assert validate_tool_call_id("call_abc$def") is False
        assert validate_tool_call_id("call_abc%def") is False
        assert validate_tool_call_id("call_abc^def") is False
        assert validate_tool_call_id("call_abc&def") is False
        assert validate_tool_call_id("call_abc*def") is False
        assert validate_tool_call_id("call_abc(def") is False
        assert validate_tool_call_id("call_abc)def") is False
        assert validate_tool_call_id("call_abc+def") is False
        assert validate_tool_call_id("call_abc=def") is False
        assert validate_tool_call_id("call_abc[def") is False
        assert validate_tool_call_id("call_abc]def") is False
        assert validate_tool_call_id("call_abc{def") is False
        assert validate_tool_call_id("call_abc}def") is False
        assert validate_tool_call_id("call_abc|def") is False
        assert validate_tool_call_id("call_abc\\def") is False
        assert validate_tool_call_id("call_abc/def") is False
        assert validate_tool_call_id("call_abc?def") is False
        assert validate_tool_call_id("call_abc;def") is False
        assert validate_tool_call_id("call_abc:def") is False
        assert validate_tool_call_id("call_abc,def") is False
        assert validate_tool_call_id("call_abc<def") is False
        assert validate_tool_call_id("call_abc>def") is False
        assert validate_tool_call_id("call_abc.def") is True

    def test_empty_string(self):
        """Test empty string."""
        assert validate_tool_call_id("") is False

    def test_none(self):
        """Test None."""
        assert validate_tool_call_id(None) is False


class TestGenerateToolCallId:
    """Test cases for generate_tool_call_id function."""

    def test_generates_valid_id(self):
        """Test that generated IDs are valid."""
        for i in range(10):
            tool_call_id = generate_tool_call_id(i)
            assert validate_tool_call_id(tool_call_id) is True

    def test_ids_are_unique(self):
        """Test that generated IDs are unique."""
        ids = [generate_tool_call_id(i) for i in range(1000)]
        assert len(ids) == len(set(ids))


class TestMergeMessages:
    """Test cases for merge_messages function."""

    def test_empty_list(self):
        """Test empty list."""
        assert merge_messages([]) == []

    def test_single_message(self):
        """Test single message."""
        messages = [{"role": "user", "content": "Hello"}]
        assert merge_messages(messages) == messages

    def test_consecutive_same_role(self):
        """Test merging consecutive same-role messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "World"}
        ]
        result = merge_messages(messages)
        assert len(result) == 1
        assert result[0]["content"] == "Hello\n\nWorld"

    def test_different_roles(self):
        """Test different roles don't merge."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ]
        result = merge_messages(messages)
        assert len(result) == 2

    def test_tool_calls_merge(self):
        """Test tool calls merge."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "World", "tool_calls": [{"id": "call_1"}]}
        ]
        result = merge_messages(messages)
        assert len(result) == 1
        assert result[0]["content"] == "Hello\n\nWorld"
        assert len(result[0]["tool_calls"]) == 1
