"""
Core package for the OpenAI/Anthropic Bridge.

This package contains the modular components of the bridge:
- persona: Expert persona configuration
- transformers: Request/response transformers
- security: Circuit breaker and rate limiter
- metrics: Prometheus metrics engine
"""
from .persona import EXPERT_PERSONA
from .transformers import robust_parse_args, merge_messages, SSEParser, validate_tool_call_id, generate_tool_call_id
from .security import NetworkCircuitBreaker, RateLimiter
from .logger import ChimeraLogger
from .metrics import metrics_registry, MetricsRegistry, Metric, MetricType

__all__ = [
    "EXPERT_PERSONA",
    "NetworkCircuitBreaker",
    "RateLimiter",
    "metrics_registry",
    "MetricsRegistry",
    "Metric",
    "MetricType",
    "robust_parse_args",
    "merge_messages",
    "SSEParser",
    "validate_tool_call_id",
    "generate_tool_call_id",
    "ChimeraLogger"
]
