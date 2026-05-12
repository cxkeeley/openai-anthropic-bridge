"""Tests for the SSE parser functionality."""
import pytest
from fastapi_bridge import SSEParser


class TestSSEParser:
    """Test cases for the SSEParser class."""

    def test_empty_feed(self):
        """Test empty feed."""
        parser = SSEParser()
        assert list(parser.feed(b"")) == []

    def test_single_event(self):
        """Test single event."""
        parser = SSEParser()
        data = b"data: test\n\n"
        assert list(parser.feed(data)) == ["test"]

    def test_multiple_events(self):
        """Test multiple events."""
        parser = SSEParser()
        data = b"data: test1\n\ndata: test2\n\n"
        assert list(parser.feed(data)) == ["test1", "test2"]

    def test_multiline_data(self):
        """Test multiline data."""
        parser = SSEParser()
        data = b"data: line1\nline2\n\n"
        assert list(parser.feed(data)) == ["line1"]

    def test_invalid_utf8(self):
        """Test invalid UTF-8."""
        parser = SSEParser()
        data = b"data: \xff\xfe\n\n"
        assert list(parser.feed(data)) == ["��"]
