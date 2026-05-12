"""Tests for the rate limiter functionality."""
import time
import pytest
import os

# Set rate limiting enabled for tests
os.environ["BRIDGE_RATE_LIMIT_ENABLED"] = "true"

from fastapi_bridge import RateLimiter


class TestRateLimiter:
    """Test cases for the RateLimiter class."""

    def test_is_allowed_initial_request(self):
        """Test that initial request is allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        assert limiter.is_allowed() is True

    def test_is_allowed_under_limit(self):
        """Test that requests under the limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        for _ in range(4):
            assert limiter.is_allowed() is True

    def test_is_allowed_at_limit(self):
        """Test that request at limit is allowed but next is not."""
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            limiter.is_allowed()
        assert limiter.is_allowed() is False

    def test_is_allowed_over_limit(self):
        """Test that requests over limit are not allowed."""
        limiter = RateLimiter(max_requests=3, window_seconds=60.0)
        for _ in range(3):
            limiter.is_allowed()
        assert limiter.is_allowed() is False

    def test_get_retry_after_initial(self):
        """Test retry_after when no requests have been made."""
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        assert limiter.get_retry_after() == 0

    def test_get_retry_after_with_requests(self):
        """Test retry_after when requests have been made."""
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            limiter.is_allowed()
        retry_after = limiter.get_retry_after()
        assert retry_after >= 0

    def test_rate_limit_disabled(self):
        """Test that rate limiting can be disabled."""
        import os
        os.environ["BRIDGE_RATE_LIMIT_ENABLED"] = "false"
        try:
            limiter = RateLimiter(max_requests=5, window_seconds=60.0)
            for _ in range(10):
                assert limiter.is_allowed() is True
        finally:
            os.environ["BRIDGE_RATE_LIMIT_ENABLED"] = "true"

    def test_window_expiration(self):
        """Test that old requests expire from the window."""
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        limiter.is_allowed()
        limiter.is_allowed()
        assert limiter.is_allowed() is False
        time.sleep(0.15)
        assert limiter.is_allowed() is True
