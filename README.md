# Claude Bridge for JiuTian (九天) Model

This repository contains a robust bridge application that allows you to use the China Mobile JiuTian (九天) AI model with both the Anthropic and OpenAI API formats. The bridge translates between these API formats, enabling seamless integration with agentic CLI tools like Claude Code.

## Features

- **Agentic Capability**: Includes strict system prompt overrides to force models like `qwen3-coder-next` and `jt_indonesia` to emit perfect OpenAI JSON tooling hooks.
- **Docker Compose Ready**: One-click containerization with `gunicorn` for parallel thread processing.
- **Auto-Healing Streams**: Real-time bracket interpolation fixes tokenization glitches during Server-Sent Event (SSE) streaming.
- **Localization Override**: Forces the native model to communicate in strict English rather than Chinese defaults.

## Prerequisites

- Python 3.12+ (For local bare-metal run)
- Docker & Docker Compose (Recommended)

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd <repository-name>
   ```

2. Copy the example configuration to your secure local environment context:
   ```bash
   cp .env.example .env
   ```

3. Open `.env` and paste in your active JWT Access Token.

## Usage

### Method 1: Using Docker Compose (Highly Recommended)

The bridge utilizes Gunicorn threaded workers to sustain multiple parallel SSE streams. Docker handles this optimally.

```bash
docker compose up --build -d

# To view live generation logs:
docker compose logs -f
```

### Method 2: Local Python Execution

If you wish to run the app manually without Docker:
```bash
pip install -r requirements.txt
./start_claude_bridge.sh
```

## Configure Environment (.env)

The bridge dynamically reads variables from your `.env` file mapping.

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Host to bind to | `0.0.0.0` |
| `PORT` | Port to listen on | `8000` |
| `JTIU_TARGET_URL` | Target JiuTian service URL | `https://ai.asix.id.../chat/completions` |
| `JTIU_TOKEN` | Authentication JWT token | (Required) |
| `JTIU_MODEL` | Target coding model override | `qwen3-coder-next` |

## Connect Claude Code

To boot Anthropic's Claude Code utilizing your local proxy cluster, set these environment variables and run it:

```bash
# Point Claude at your localhost bridge
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"

# Enter any string, the proxy ignores this and uses JTIU_TOKEN
export ANTHROPIC_API_KEY="sk-any-key"

# Launch the agent
claude
```

## Troubleshooting

### Streaming Freezes or Hanging Requests
If your CLI abruptly stops, verify that you are running via Docker. Development Flask servers cannot handle concurrent HTTP chunked stream protocols cleanly on Windows. Use `docker compose` which deploys a dedicated Gunicorn WSGI matrix.

### Out of Bounds / File Security Warning
With `claude-code`, the prompt constraints force the model to stay inside the project root (`./`). If the model ignores this and reads `/home/`, Claude will trigger a manual verification prompt.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
