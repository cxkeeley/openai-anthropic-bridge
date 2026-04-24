#!/bin/bash

# Default values
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="8000"
DEFAULT_TARGET_URL="http://localhost:11434/v1/chat/completions"
DEFAULT_TOKEN="sk-your-token-here"

# Secure .env loading - parse line-by-line to prevent arbitrary code execution
load_env_file() {
    local env_file=".env"
    if [ -f "$env_file" ]; then
        echo "Loading configuration from .env..."
        # Parse .env file line-by-line safely
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip empty lines and comments
            [[ -z "$line" ]] && continue
            [[ "$line" =~ ^[[:space:]]*# ]] && continue

            # Match valid variable assignments: VAR=value or VAR="value" or VAR='value'
            if [[ "$line" =~ ^[[:space:]]*([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$ ]]; then
                var_name="${BASH_REMATCH[1]}"
                var_value="${BASH_REMATCH[2]}"

                # Remove surrounding quotes if present (handle both single and double quotes)
                if [[ "$var_value" =~ ^\"(.*)\"$ ]]; then
                    var_value="${BASH_REMATCH[1]}"
                elif [[ "$var_value" =~ ^\'(.*)\'$ ]]; then
                    var_value="${BASH_REMATCH[1]}"
                fi

                # Export the variable safely
                export "$var_name"="$var_value"
            fi
        done < "$env_file"
    fi
}

# Load .env file if it exists
load_env_file

# Function to display usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  -h, --host HOST     Host to bind to (default: $DEFAULT_HOST)"
    echo "  -p, --port PORT     Port to listen on (default: $DEFAULT_PORT)"
    echo "  -u, --url URL     Target URL for the JiuTian service"
    echo "  -t, --token TOKEN Authentication token for the service"
    echo "  -m, --model MODEL Target model (default: jt_indonesia)"
    echo "  -d, --debug       Run with uvicorn reload"
    echo "  --help            Show this help message"
    echo ""
    echo "Example: $0 --port 8080 --debug"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -u|--url)
            TARGET_URL="$2"
            shift 2
            ;;
        -t|--token)
            TOKEN="$2"
            shift 2
            ;;
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        -d|--debug)
            DEBUG=1
            shift
            ;;
        --help)
            show_usage
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Use environment variables if set, otherwise use defaults or command line args
HOST=${JTIU_HOST:-${HOST:-$DEFAULT_HOST}}
PORT=${JTIU_PORT:-${PORT:-$DEFAULT_PORT}}
TARGET_URL=${JTIU_TARGET_URL:-${TARGET_URL:-$DEFAULT_TARGET_URL}}
TOKEN=${JTIU_TOKEN:-${TOKEN:-$DEFAULT_TOKEN}}
MODEL=${JTIU_MODEL:-${MODEL:-jt_indonesia}}

# Export for the application
export JTIU_TARGET_URL="$TARGET_URL"
export JTIU_TOKEN="$TOKEN"
export JTIU_MODEL="$MODEL"
export JTIU_HOST="$HOST"
export JTIU_PORT="$PORT"

# Display configuration
echo "==================================================="
if [ -n "$DEBUG" ]; then
    echo "Starting Claude Bridge (FastAPI) in DEBUG mode"
else
    echo "Starting Claude Bridge (FastAPI)"
fi
echo "==================================================="
echo "Host: $HOST:$PORT"
echo "Target URL: $TARGET_URL"
echo "Token: ${TOKEN:0:20}...${TOKEN: -10}"
echo "Model: $MODEL"
echo "Reload/Debug: ${DEBUG:+enabled}"
echo "==================================================="
echo

# Run the application
if [ -n "$DEBUG" ]; then
    # Use uvicorn directly for reload support in debug mode
    uvicorn fastapi_bridge:app --host "$HOST" --port "$PORT" --reload
else
    # Use the embedded runner in the script
    python3 fastapi_bridge.py
fi
