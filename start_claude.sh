#!/bin/bash
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

export ANTHROPIC_BASE_URL="http://127.0.0.1:57123"
export ANTHROPIC_API_KEY="sk-any-key"
MODEL=${BRIDGE_MODEL:-"model"}

echo "Connecting Claude Code to Jiutian Proxy at $ANTHROPIC_BASE_URL..."
echo "Using Model: $MODEL"
claude --model "$MODEL"
