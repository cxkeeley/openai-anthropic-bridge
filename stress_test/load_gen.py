#!/usr/bin/env python3
"""
Production-grade load generator for Chimera Bridge stress testing.
Uses httpx.AsyncClient for high-performance concurrent streaming requests.
"""

import argparse
import asyncio
import json
import random
import sys
import time
from typing import Any

import httpx

# Configuration
DEFAULT_CONCURRENCY = 20
DEFAULT_REQUESTS_PER_CLIENT = 50
MAX_TEXT_BLOCK_SIZE = 1024 * 1024  # 1MB
BRIDGE_URL = "http://localhost:57123/v1/messages"
METRICS_URL = "http://localhost:57123/metrics"

# Valid roles for normal requests
VALID_ROLES = ["user", "assistant", "system", "tool"]

# Poison payload templates
POISON_PAYLOADS = [
    # Invalid JSON
    b"not valid json {{{",
    b"{invalid: json}",
    b"{\"key\": }",
    b"{\"key\": \"value\" extra garbage after",
    b"",
    # Missing required fields
    {"messages": []},
    {"messages": [{"role": "user", "content": "test"}]},
    {"messages": [{"content": "missing role"}]},
    {"messages": [{"role": "", "content": "empty role"}]},
    # Large text blocks (1MB)
    {"messages": [{"role": "user", "content": "x" * MAX_TEXT_BLOCK_SIZE}],
     "max_tokens": 100},
    # Invalid max_tokens
    {"messages": [{"role": "user", "content": "test"}], "max_tokens": -1},
    {"messages": [{"role": "user", "content": "test"}], "max_tokens": "invalid"},
    # Invalid model
    {"messages": [{"role": "user", "content": "test"}], "model": ""},
    # Tool-related poison
    {"messages": [{"role": "user", "content": "test"}], "tools": "not an array"},
    {"messages": [{"role": "user", "content": "test"}], "tools": [{"type": ""}]},
    # Streaming edge cases
    {"messages": [{"role": "user", "content": "test"}], "stream": "not a bool"},
    # Mixed valid/invalid
    {"messages": [{"role": "user", "content": "test"}, {"role": "invalid", "content": "bad"}], "stream": True},
]


def generate_valid_payload(stream: bool = True) -> dict[str, Any]:
    """Generate a valid OpenAI-compatible request payload."""
    return {
        "messages": [
            {"role": "user", "content": "This is a valid test message for the Chimera Bridge stress test. The bridge is functioning correctly and processing requests as expected."},
            {"role": "assistant", "content": "I can help you with that. What would you like to test?"},
        ],
        "model": "gpt-4o-mini",
        "max_tokens": 100,
        "stream": stream,
        "temperature": 0.7,
    }


def generate_poison_payload() -> dict[str, Any] | bytes:
    """Generate a malformed payload for poison testing."""
    return random.choice(POISON_PAYLOADS)


async def send_request(client: httpx.AsyncClient, payload: dict[str, Any] | bytes,
                       request_id: int, poison_mode: bool) -> tuple[int, str, str]:
    """
    Send a single request and return (request_id, status, error).

    Returns:
        Tuple of (request_id, status, error_message)
    """
    try:
        headers = {"Content-Type": "application/json"}

        if isinstance(payload, bytes):
            # For poison payloads, send raw bytes
            response = await client.send(
                httpx.Request(
                    "POST",
                    BRIDGE_URL,
                    headers=headers,
                    content=payload,
                    content_length=len(payload)
                )
            )
        else:
            response = await client.post(
                BRIDGE_URL,
                json=payload,
                headers=headers
            )

        # Read response to complete the request
        try:
            response.read()
        except Exception:
            pass

        return (request_id, str(response.status_code), "")

    except httpx.TimeoutException as e:
        return (request_id, "TIMEOUT", str(e))
    except httpx.NetworkError as e:
        return (request_id, "NETWORK_ERROR", str(e))
    except Exception as e:
        return (request_id, "ERROR", str(e))


async def run_load_test(
    num_requests: int,
    concurrency: int,
    poison_mode: bool,
    metrics_url: str,
) -> dict[str, Any]:
    """
    Run the load test and return results.

    Args:
        num_requests: Total number of requests to send
        concurrency: Number of concurrent requests
        poison_mode: Whether to use poison payloads
        metrics_url: URL to fetch metrics
    """
    results = {
        "total_requests": 0,
        "success_count": 0,
        "error_count": 0,
        "status_codes": {},
        "errors": [],
        "duration_seconds": 0.0,
    }

    start_time = time.time()

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=concurrency * 2),
        headers={"User-Agent": "StressTest/1.0"},
    ) as client:
        # Create tasks for all requests
        tasks = []
        for i in range(num_requests):
            if poison_mode:
                payload = generate_poison_payload()
            else:
                payload = generate_valid_payload()
            tasks.append(send_request(client, payload, i, poison_mode))

        # Execute with semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_task(task):
            async with semaphore:
                return await task

        results["total_requests"] = num_requests

        # Run all tasks
        task_results = await asyncio.gather(*[bounded_task(t) for t in tasks])

        # Aggregate results
        for req_id, status, error in task_results:
            results["status_codes"][status] = results["status_codes"].get(status, 0) + 1
            if status in ("200", "201", "202", "204"):
                results["success_count"] += 1
            else:
                results["error_count"] += 1
                if len(results["errors"]) < 100:  # Limit error logging
                    results["errors"].append(f"Request {req_id}: {error}")

    results["duration_seconds"] = time.time() - start_time

    return results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Stress test the Chimera Bridge"
    )
    parser.add_argument(
        "--poison",
        action="store_true",
        help="Enable poison mode with malformed payloads"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help=f"Total number of requests (default: 100)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Number of concurrent requests (default: {DEFAULT_CONCURRENCY})"
    )
    parser.add_argument(
        "--metrics-url",
        type=str,
        default=METRICS_URL,
        help=f"Metrics URL (default: {METRICS_URL})"
    )

    args = parser.parse_args()

    print(f"Starting stress test: {args.requests} requests, {args.concurrency} concurrency, poison_mode={args.poison}")

    results = await run_load_test(
        num_requests=args.requests,
        concurrency=args.concurrency,
        poison_mode=args.poison,
        metrics_url=args.metrics_url
    )

    # Print summary
    print("\n" + "=" * 60)
    print("STRESS TEST SUMMARY")
    print("=" * 60)
    print(f"Total Requests: {results['total_requests']}")
    print(f"Success Count: {results['success_count']}")
    print(f"Error Count: {results['error_count']}")
    print(f"Duration: {results['duration_seconds']:.2f} seconds")
    print(f"Requests/Second: {results['total_requests'] / max(results['duration_seconds'], 0.001):.2f}")
    print(f"Status Codes: {results['status_codes']}")

    if results['errors']:
        print("\nSample Errors:")
        for error in results['errors'][:5]:
            print(f"  - {error}")

    # Return exit code based on success rate
    if results['total_requests'] > 0:
        success_rate = results['success_count'] / results['total_requests']
        if success_rate < 0.5:
            print("\nWARNING: Success rate below 50%!")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
