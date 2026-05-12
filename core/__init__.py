"""
Core package for the OpenAI/Anthropic Bridge.

This package contains the modular components of the bridge:
- persona: Expert persona configuration
- transformers: Request/response transformers
- security: Circuit breaker and rate limiter
"""
from .persona import EXPERT_PERSONA
from .transformers import robust_parse_args, merge_messages, SSEParser, validate_tool_call_id, generate_tool_call_id
from .security import NetworkCircuitBreaker, RateLimiter

__all__ = [
    "EXPERT_PERSONA",
    "NetworkCircuitBreaker",
    "RateLimiter",
    "robust_parse_args",
    "merge_messages",
    "SSEParser",
]
