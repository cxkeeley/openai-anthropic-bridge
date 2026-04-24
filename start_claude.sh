#!/bin/bash
# Load .env file if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_API_KEY="sk-any-key"
MODEL=${JTIU_MODEL:-"model"}

echo "Connecting Claude Code to Jiutian Proxy at $ANTHROPIC_BASE_URL..."
echo "Using Model: $MODEL"
claude --model "$MODEL"
