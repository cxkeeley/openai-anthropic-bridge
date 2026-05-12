# Chimera Bridge (OpenAI to Anthropic)

This repository contains **Chimera Bridge**, a production-grade, modular application that allows you to use any OpenAI-compatible AI model (like China Mobile JiuTian, NVIDIA NIM, or Groq) with the Anthropic API format. The bridge is compiled with Cython for high performance and hardened with proactive circuit breakers to ensure stable agentic communication.

## Key Features

- **Modular Architecture**: Core logic is isolated into a compiled `core/` package for maximum stability and performance.
- **Zero-Source Deployment**: Production containers run exclusively from Cython-compiled `.so` binaries—no source `.py` files in the runtime environment.
- **Antigravity Expert Mode**: High-precision system persona with hierarchical rules for tool selection and escalation ladders for edit failures.
- **Hardened Loop Prevention**:
    - **Proactive**: In-persona instructions forcing tool switching after repeated failures.
    - **Reactive**: Real-time circuit breaker that monitors all Bash commands and tool calls, injecting loop-break warnings when redundancy is detected.
- **Live Monitoring**: New `/v1/status` endpoint providing real-time JSON metrics on active connections and circuit breaker health.
- **Tool Call ID Pinning**: Strictly uses the `toolu_` namespace to ensure seamless correlation with Claude Code agents.
- **Dynamic Scaling**: Optimized Gunicorn configuration that scales workers dynamically based on CPU cores.
- **Dual API Support**: Native Anthropic API (`/v1/messages`) and OpenAI-compatible (`/v1/chat/completions`) endpoints.

## Prerequisites

- Python 3.10+ (For compilation/local run)
- Docker & Docker Compose (Recommended for production)

## Installation & Deployment

The recommended way to deploy is using the automated build script:

1. Clone the repository and configure `.env`:
   ```bash
   cp .env.example .env
   # Edit .env with your BRIDGE_TOKEN and TARGET_URL
   ```

2. Run the automated deployment script:
   ```bash
   ./deploy.sh
   ```
   *This script handles Cython compilation, artifact cleanup, and Docker Compose restart.*

## Configure Environment (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Port to listen on | `57123` |
| `BRIDGE_TARGET_URL` | Target JiuTian service URL | (Required) |
| `BRIDGE_TOKEN` | Authentication JWT token | (Required) |
| `BRIDGE_MODEL` | Target model name | `jt_indonesia` |
| `BRIDGE_UPSTREAM_TIMEOUT`| Timeout for upstream requests | `600.0` |

## Monitoring & Health

The bridge provides dedicated endpoints for observability:

- **Status**: `GET http://localhost:57123/v1/status` (Metrics, Circuit Breaker state)
- **Health**: `GET http://localhost:57123/health` (Upstream connectivity check)
- **Metrics**: `GET http://localhost:57123/metrics` (Prometheus-compatible format)

## Connect Claude Code

To use Claude Code with your bridge:

```bash
# Point Claude at your bridge port
export ANTHROPIC_BASE_URL="http://127.0.0.1:57123"
export ANTHROPIC_API_KEY="sk-any-key"

# Launch the agent
claude
```

## Project Structure

- `core/`: Compiled package containing `persona`, `transformers`, `security`, and `logger`.
- `fastapi_bridge.py`: Main entry point and server orchestration.
- `setup_cython.py`: Build configuration for machine-code compilation.
- `deploy.sh`: Automated production deployment and cleanup script.
- `docker-compose.yml`: Infrastructure configuration with DNS stability fixes.

## License

This project is licensed under the MIT License.

