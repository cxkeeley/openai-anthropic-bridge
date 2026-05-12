"""
Metrics module for the OpenAI/Anthropic Bridge.

This module contains the Prometheus Metrics Engine for the bridge:
- MetricsRegistry: Global registry for all metrics
- MetricsCollector: Prometheus metrics collector
"""
import time
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class MetricType(Enum):
    """Types of metrics supported by the metrics engine."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """Represents a single metric with its value and metadata."""
    name: str
    value: float
    type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    help_text: str = ""
    timestamp: float = field(default_factory=time.time)


class MetricsRegistry:
    """
    Global registry for all metrics in the bridge.
    Thread-safe implementation using locks for concurrent access.
    """
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.RLock()

    def register_counter(self, name: str, help_text: str = "") -> None:
        """Register a new counter metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Metric(
                    name=name,
                    value=0.0,
                    type=MetricType.COUNTER,
                    help_text=help_text
                )

    def register_gauge(self, name: str, help_text: str = "") -> None:
        """Register a new gauge metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Metric(
                    name=name,
                    value=0.0,
                    type=MetricType.GAUGE,
                    help_text=help_text
                )

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        with self._lock:
            if name in self._metrics:
                self._metrics[name].value += value
                self._metrics[name].timestamp = time.time()

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        with self._lock:
            if name in self._metrics:
                self._metrics[name].value = value
                self._metrics[name].timestamp = time.time()

    def get_all_metrics(self) -> Dict[str, Metric]:
        """Get all metrics."""
        with self._lock:
            return dict(self._metrics)

    def get_metric(self, name: str) -> Optional[Metric]:
        """Get a specific metric."""
        with self._lock:
            return self._metrics.get(name)

    def to_prometheus_format(self) -> str:
        """Convert all metrics to Prometheus text format."""
        lines = []
        with self._lock:
            for name, metric in self._metrics.items():
                if metric.help_text:
                    lines.append(f"# HELP {name} {metric.help_text}")
                lines.append(f"# TYPE {name} {metric.type.value}")
                
                labels_str = ""
                if metric.labels:
                    labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in metric.labels.items()) + "}"
                
                lines.append(f"{name}{labels_str} {metric.value}")
        return "\n".join(lines) + "\n"


# Global metrics registry instance
metrics_registry = MetricsRegistry()
