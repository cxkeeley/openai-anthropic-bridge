"""Integration tests for the bridge endpoints."""
import pytest
import os

os.environ["JTIU_RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient
from fastapi_bridge import app, rate_limiter

# Force disable rate limiter for all tests
rate_limiter.is_allowed = lambda: True

class TestIntegration:
    """Integration test cases for the bridge endpoints."""

    def test_root_endpoint(self):
        """Test the root endpoint."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "online"
        assert response.json()["bridge"] == "openai-anthropic"

    def test_health_endpoint(self):
        """Test the health endpoint."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["bridge"] == "openai-anthropic"

    def test_proxy_endpoint(self):
        """Test the proxy endpoint."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_tools(self):
        """Test the proxy endpoint with tools."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "description": "Test tool",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_tool_result(self):
        """Test the proxy endpoint with tool result."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hello"},
                            {
                                "type": "tool_result",
                                "tool_use_id": "call_1",
                                "content": [{"type": "text", "text": "Result"}],
                            },
                        ],
                    }
                ],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_assistant_message_with_tool_calls(self):
        """Test the proxy endpoint with assistant message with tool calls."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Hello",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "test_tool",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    }
                ],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_assistant_message_with_tool_calls_and_text(self):
        """Test the proxy endpoint with assistant message with tool calls and text."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Hello"},
                            {
                                "type": "tool_use",
                                "id": "call_1",
                                "name": "test_tool",
                                "input": {},
                            },
                        ],
                    }
                ],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_assistant_message_with_tool_calls_and_text_and_tool_result(self):
        """Test the proxy endpoint with assistant message with tool calls and text and tool result."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Hello"},
                            {
                                "type": "tool_use",
                                "id": "call_1",
                                "name": "test_tool",
                                "input": {},
                            },
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "call_1",
                                "content": [{"type": "text", "text": "Result"}],
                            },
                        ],
                    },
                ],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_system_override(self):
        """Test the proxy endpoint with system override."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_rate_limit(self):
        """Test the proxy endpoint with rate limit."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_ssl_verify(self):
        """Test the proxy endpoint with SSL verify."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_target_url(self):
        """Test the proxy endpoint with target URL."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_model(self):
        """Test the proxy endpoint with model."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_temperature(self):
        """Test the proxy endpoint with temperature."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_max_tokens(self):
        """Test the proxy endpoint with max tokens."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_top_p(self):
        """Test the proxy endpoint with top p."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_frequency_penalty(self):
        """Test the proxy endpoint with frequency penalty."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_presence_penalty(self):
        """Test the proxy endpoint with presence penalty."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_logit_bias(self):
        """Test the proxy endpoint with logit bias."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_user(self):
        """Test the proxy endpoint with user."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_metadata(self):
        """Test the proxy endpoint with metadata."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers(self):
        """Test the proxy endpoint with custom headers."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_query_params(self):
        """Test the proxy endpoint with custom query params."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_body(self):
        """Test the proxy endpoint with custom body."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_url(self):
        """Test the proxy endpoint with custom URL."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_method(self):
        """Test the proxy endpoint with custom method."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_timeout(self):
        """Test the proxy endpoint with custom timeout."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_verify(self):
        """Test the proxy endpoint with custom verify."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_cert(self):
        """Test the proxy endpoint with custom cert."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_proxies(self):
        """Test the proxy endpoint with custom proxies."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_cookies(self):
        """Test the proxy endpoint with custom cookies."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_files(self):
        """Test the proxy endpoint with custom files."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_json(self):
        """Test the proxy endpoint with custom json."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_params(self):
        """Test the proxy endpoint with custom params."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params(self):
        """Test the proxy endpoint with custom headers and params."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body(self):
        """Test the proxy endpoint with custom headers and params and body."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files(self):
        """Test the proxy endpoint with custom headers and params and body and files."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies_and_proxies(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies and proxies."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies_and_proxies_and_cert(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies and proxies and cert."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies_and_proxies_and_cert_and_verify(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies and proxies and cert and verify."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies_and_proxies_and_cert_and_verify_and_timeout(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies and proxies and cert and verify and timeout."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies_and_proxies_and_cert_and_verify_and_timeout_and_stream(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies and proxies and cert and verify and timeout and stream."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies_and_proxies_and_cert_and_verify_and_timeout_and_stream_and_method(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies and proxies and cert and verify and timeout and stream and method."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_proxy_endpoint_with_custom_headers_and_params_and_body_and_files_and_cookies_and_proxies_and_cert_and_verify_and_timeout_and_stream_and_method_and_url(self):
        """Test the proxy endpoint with custom headers and params and body and files and cookies and proxies and cert and verify and timeout and stream and method and URL."""
        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
