# Memory Index

This directory contains persistent memory files for Claude Code.

## User Profile
- **Role**: Software Engineer / Developer
- **Expertise**: Python, FastAPI, API Bridges, System Integration
- **Current Focus**: JiuTian (九天) Model Integration, Claude Code Bridge Development

## Project Context
- **Project**: OpenAI-Anthropic Bridge for JiuTian Model
- **Purpose**: Translate between OpenAI and Anthropic API formats for JiuTian model integration
- **Status**: Production-ready, all tests passing (69/69 tests pass)

## Key Technical Decisions
1. **Rate Limiting**: Disabled by default (`BRIDGE_RATE_LIMIT_ENABLED=false`)
2. **Model Parameters**: Optimized for code generation with low temperature (0.2) and high max_tokens (8192)
3. **Memory**: Persistent memory stored in `/mnt/projectone/openai-anthropic-bridge/.claude/memory/`

## Recent Work
- Added `get_model_params()` function with defaults
- Fixed rate limiter to check environment variable at runtime
- All 69 tests passing
- Ready for production deployment

## Environment Variables
- `BRIDGE_TARGET_URL`: JiuTian API endpoint
- `BRIDGE_TOKEN`: Authentication token
- `BRIDGE_MODEL`: Model name (default: jt_indonesia)
- `BRIDGE_MODEL_PARAMS`: Model parameters in JSON format
- `BRIDGE_RATE_LIMIT_ENABLED`: Enable/disable rate limiting
- `BRIDGE_RATE_LIMIT_REQUESTS`: Max requests per window
- `BRIDGE_RATE_LIMIT_WINDOW`: Time window in seconds

## Current Branch
- **Branch**: prod
- **Main Branch**: main

## Last Updated
2026-04-26
