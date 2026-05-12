#!/usr/bin/env python3
"""
Neuron connection test script to verify token usage metadata awareness.
Sends a simple message and extracts usage data from SSE stream.
"""

import asyncio
import httpx


async def test_neuron_connection():
    """Test neuron connection and extract token usage."""
    url = "http://localhost:57123/v1/messages"

    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Hello, perform a system check."
            }
        ],
        "model": "gpt-4o-mini",
        "max_tokens": 50,
        "stream": True
    }

    headers = {
        "Content-Type": "application/json"
    }

    print("Sending request to bridge...")
    print(f"Payload: {payload}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        print(f"\nResponse status: {response.status_code}")

        # Parse SSE stream
        usage_data = None
        full_response = ""

        for line in response.iter_lines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                if data_str == "[DONE]":
                    break
                try:
                    data = __import__("json").loads(data_str)
                    if "choices" in data and data["choices"]:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_response += content
                    if "usage" in data:
                        usage_data = data["usage"]
                except Exception as e:
                    print(f"Error parsing SSE data: {e}")

        print(f"\nFull response: {full_response}")

        if usage_data:
            print("\n" + "=" * 60)
            print("TOKEN USAGE DATA:")
            print("=" * 60)
            print(f"Input tokens: {usage_data.get('input_tokens', 'N/A')}")
            print(f"Output tokens: {usage_data.get('output_tokens', 'N/A')}")
            print(f"Total tokens: {usage_data.get('total_tokens', 'N/A')}")
            return usage_data
        else:
            print("\nNo usage data received in SSE stream")
            return None


if __name__ == "__main__":
    result = asyncio.run(test_neuron_connection())
