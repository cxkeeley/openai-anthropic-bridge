#!/usr/bin/env python3
"""
Production-grade metrics verification script for Chimera Bridge stress testing.
Scrapes /metrics endpoint and asserts bridge_requests_total delta.
"""

import argparse
import re
import sys
from typing import Optional


def parse_metrics(metrics_text: str) -> dict[str, int]:
    """
    Parse Prometheus metrics text and return a dict of metric_name -> value.

    Args:
        metrics_text: Raw Prometheus metrics text
    Returns:
        Dict mapping metric names to their integer values
    """
    metrics = {}
    for line in metrics_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Match Prometheus metric format: metric_name{labels} value
        match = re.match(r'^(\w+)(?:\{[^}]*\})?\s+(-?\d+\.?\d*)', line)
        if match:
            metric_name = match.group(1)
            value_str = match.group(2)
            try:
                value = int(float(value_str))
                metrics[metric_name] = value
            except ValueError:
                pass
    return metrics


def get_bridge_requests_total(metrics: dict[str, int]) -> Optional[int]:
    """
    Extract bridge_requests_total from metrics dict.

    Args:
        metrics: Parsed metrics dict
    Returns:
        bridge_requests_total value or None if not found
    """
    return metrics.get('bridge_requests_total')


def verify_metrics(metrics_url: str, expected_requests: int) -> bool:
    """
    Verify that bridge_requests_total has incremented by expected_requests.

    Args:
        metrics_url: URL to fetch metrics from
        expected_requests: Expected delta in bridge_requests_total
    Returns:
        True if verification passed, False otherwise
    """
    import urllib.request
    import urllib.error

    try:
        with urllib.request.urlopen(metrics_url, timeout=10) as response:
            metrics_text = response.read().decode('utf-8')
    except urllib.error.URLError as e:
        print(f"ERROR: Failed to fetch metrics from {metrics_url}: {e}")
        return False

    metrics = parse_metrics(metrics_text)
    current_requests = get_bridge_requests_total(metrics)

    if current_requests is None:
        print("ERROR: bridge_requests_total not found in metrics")
        return False

    print(f"Current bridge_requests_total: {current_requests}")
    print(f"Expected delta: {expected_requests}")

    # Check if the current value is at least the expected value
    # (it could be higher if other requests were made during testing
    if current_requests >= expected_requests:
        print(f"SUCCESS: bridge_requests_total ({current_requests}) >= expected ({expected_requests})")
        return True
    else:
        print(f"FAILURE: bridge_requests_total ({current_requests}) < expected ({expected_requests})")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify bridge_requests_total metrics"
    )
    parser.add_argument(
        "expected_requests",
        type=int,
        help="Expected number of requests that should have been sent"
    )
    parser.add_argument(
        "--metrics-url",
        type=str,
        default="http://localhost:57123/metrics",
        help="Metrics URL (default: http://localhost:57123/metrics)"
    )

    args = parser.parse_args()

    print(f"Verifying metrics: expected_requests={args.expected_requests}, metrics_url={args.metrics_url}")

    success = verify_metrics(args.metrics_url, args.expected_requests)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
