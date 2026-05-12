"""
Security module for the OpenAI/Anthropic Bridge.

This module contains security-related components:
- NetworkCircuitBreaker: Circuit breaker for upstream connections
- RateLimiter: Rate limiter for incoming requests
"""
import time
import os


class NetworkCircuitBreaker:
    """
    Network Circuit Breaker for Upstream connections.

    Implements the Circuit Breaker pattern to prevent cascading failures.
    """
    def __init__(self, threshold: int = 5, timeout_sec: int = 30):
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.threshold = threshold
        self.timeout = timeout_sec
        self.total_requests = 0
        self.total_failures = 0
        self.total_latency_ms = 0.0

    def record_success(self):
        """Record a successful request."""
        self.total_requests += 1
        self.success_count += 1
        if self.state == "half-open":
            self.state = "closed"
        self.failure_count = 0

    def record_failure(self):
        """Record a failed request."""
        self.total_requests += 1
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.threshold:
            self.state = "open"

    def can_request(self) -> bool:
        """
        Check if a request can be made.
        Returns True if the circuit is closed or half-open and the timeout has passed.
        """
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "half-open"
                return True
            return False
        return True


class RateLimiter:
    """
    Simple sliding window rate limiter.
    """
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed under the rate limit.
        Returns True if the request is allowed, False otherwise.
        """
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
        """
        Get the retry-after value in seconds.
        Returns the number of seconds to wait before retrying.
        """
        if not self.requests:
            return 0
        oldest = min(self.requests)
        retry_after = int(self.window_seconds - (time.time() - oldest))
        return max(1, retry_after)
