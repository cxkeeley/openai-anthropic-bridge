#!/bin/bash

# Default values
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="8000"
DEFAULT_TARGET_URL="https://ai.asix.id/kunlun/ingress/api-safe/5351ea/a95e59932d094883945ed08ab2a1f6bc/ai-4f4f1bee55324e7382a864176dbdd8da/service-2c125598e6b543c8a8859570f5688811/v1/chat/completions"
DEFAULT_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJlNGRhM2EzN2FmOGY0ZGQxYTU3N2RhNzU1MTQyMzc3YSIsImlzcyI6ImFwaS1hdXRoLWtleSIsImV4cCI6NDkyNzUxMDU0NX0.iVRE-7MW9KhKbBMSVUdm79DC5prAf7xpHHt9GB5rvVGXYy0IL5mkZqkn1JdLXiYMXkBt0OXKkzkOo-4tJ3NpoEiIjNU150lg3821eSqPwD3uILoHhQW0K1LShIAgiPplviAoAZFsvD_Hmg9kMha7ziKNW1KmJH_54-_DPSbv4QGSe4ZY41snjj4960AmmVrg4u94c1PHIJBOzfphaVuN7MLrjV3EVVZ3ySwjE4hqpHxn6D4_GAuJ6eTdHuUEWblvnKKr__aKali3d95UPmB1K6QxeGyfZcprgn3rJtLIsWwTudcNm1yGWags0MFp2D79YvjzX3QNPv6nAANrulm3eg"

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
    echo "  -d, --debug       Run in debug mode"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "You can also set these via environment variables:"
    echo "  JTIU_HOST, JTIU_PORT, JTIU_TARGET_URL, JTIU_TOKEN, JTIU_MODEL"
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

# Set debug flag
if [ -n "$DEBUG" ]; then
    export FLASK_DEBUG=1
fi

# Display configuration
echo "==================================================="
if [ -n "$DEBUG" ]; then
    echo "Starting Claude Bridge in DEBUG mode"
else
    echo "Starting Claude Bridge"
fi
echo "==================================================="
echo "Host: $HOST:$PORT"
echo "Target URL: $TARGET_URL"
echo "Token: ${TOKEN:0:20}...${TOKEN: -10}"
echo "Model: $MODEL"
echo "Debug Mode: ${DEBUG:+enabled}"
echo "==================================================="
echo

# Run the application
if [ -n "$DEBUG" ]; then
    python claude_bridge.py --host="$HOST" --port="$PORT" --debug
else
    python claude_bridge.py --host="$HOST" --port="$PORT"
fi
