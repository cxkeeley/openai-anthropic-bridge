import json
import httpx
import asyncio

async def test_large_tool_call():
    url = "http://localhost:57123/v1/messages"
    payload = {
        "model": "model",
        "messages": [
            {
                "role": "user",
                "content": "Write a shell script that prints numbers 1 to 1000."
            }
        ],
        "tools": [
            {
                "name": "write_to_file",
                "description": "Write to a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "TargetFile": {"type": "string"},
                        "CodeContent": {"type": "string"}
                    },
                    "required": ["TargetFile", "CodeContent"]
                }
            }
        ],
        "max_tokens": 4096
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as resp:
            async for line in resp.aiter_lines():
                if line:
                    print(line)

if __name__ == "__main__":
    asyncio.run(test_large_tool_call())
