# Chimera Bridge (OpenAI to Anthropic)

## 🏗️ Architecture Summary

The bridge is a production-grade proxy that translates between the Anthropic and OpenAI API formats, specifically hardened for agentic CLI tools like Claude Code.

### Modular Package Structure (`core/`)
- **`core/persona.py`**: Contains the `EXPERT_PERSONA` (Antigravity Expert Mode) rules.
- **`core/transformers.py`**: Logic for robust JSON parsing, message merging, and tool ID generation.
- **`core/security.py`**: Implementation of `NetworkCircuitBreaker` and `RateLimiter`.
- **`core/logger.py`**: Structured JSON logging infrastructure (`ChimeraLogger`).
- **`core/metrics.py`**: Centralized Prometheus metrics registry and exporter.
- **`core/__init__.py`**: Package initialization with exports for all core modules.

## 🛠️ Deployment & Build

### High-Performance Binary Run
The project uses Cython to compile Python source code into machine-code binaries (`.so` files) for deployment.
- **Build Command**: `./deploy.sh`
- **Manual Build**: `python3 setup_cython.py build_ext --inplace`
- **Zero-Source Policy**: Production Docker containers exclude all `.py` and `.c` files, running exclusively from compiled shared objects.

### Environment Standards
- **Port**: `57123` (Standardized across infrastructure)
- **Runtime**: Python 3.10 inside a Debian-based slim container.
- **Server**: Gunicorn with Uvicorn workers, scaling dynamically: `$(2 * nproc + 1)`.

## 🛡️ Coding Standards & Rules

- **Minimalism**: Write the simplest code possible. Keep the codebase modular.
- **DRY**: Shared logic belongs in `core/`. Providers must not import from each other.
- **Encapsulation**: Use accessors (e.g., `set_current_task()`) for internal state.
- **No Type Ignores**: Fix the underlying type issue; never use `# type: ignore**.
- **Performance**: Use list accumulation for strings, cache env vars at init, prefer iterative over recursive.
- **Zero-Defect Engineering**: Root-cause analysis for bugs; test-driven development for new features.

## 🚫 Critical Tool Usage Rules

- **Atomic Writes**: When writing files, write the entire file in one single `write_to_file` call. Do not use incremental edits for the first version of a file. This prevents context drift and ensures file integrity.
- **Read Loop Prevention**: If a `Read` tool returns "Unchanged since last read", this means the file content is already in context. Do not re-read the same file repeatedly - use what you already have or read a different file.
- **Loop Detection**: If you see "[CIRCUIT BREAKER — LOOP DETECTED]", you have already tried 3 times with different approaches. STOP calling the same tool. Report the exact error and recommend next steps.

## 🔄 Recent Changes

- **2026-05-12**: Refactored monolithic `fastapi_bridge.py` into modular `core/` package structure
- **2026-05-12**: Implemented centralized Prometheus Metrics Engine and `/metrics` endpoint
- **2026-05-12**: Implemented `/v1/status` endpoint for monitoring
- **2026-05-12**: Updated build system to compile entire `core/` package

## 📡 API Endpoints

- **Anthropic**: `POST /v1/messages` (Primary)
- **OpenAI**: `POST /v1/chat/completions` (Secondary)
- **Status**: `GET /v1/status` (Active connections, circuit breaker state)
- **Health**: `GET /health` (Upstream probe)
- **Metrics**: `GET /metrics` (Prometheus)

## 🧪 Verification Protocol

1. **Syntax Check**: `python3 -m py_compile fastapi_bridge.py`
2. **Build Test**: Run `./deploy.sh` and ensure all `.so` files are generated.
3. **Smoke Test**: `curl -s http://localhost:57123/v1/status`
4. **Agent Stress Test**: Verify that the circuit breaker triggers during tool-execution loops.

## 📁 Project Structure

```
openai-anthropic-bridge/
├── core/
│   ├── __init__.py          # Package initialization with exports
│   ├── persona.py           # EXPERT_PERSONA constant
│   ├── transformers.py      # JSON transformers and parsers
│   ├── security.py          # Circuit breaker and rate limiter
│   └── logger.py            # ChimeraLogger infrastructure
├── fastapi_bridge.py        # Main FastAPI application
├── bridge_logging.py        # Logging infrastructure
├── setup_cython.py         # Cython build configuration
├── deploy.sh               # Deployment script
├── Dockerfile              # Docker image definition
└── requirements.txt        # Python dependencies
```

