#!/bin/bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_API_KEY="sk-any-key"

echo "Connecting Claude Code to Jiutian Proxy at $ANTHROPIC_BASE_URL..."
claude --model model
