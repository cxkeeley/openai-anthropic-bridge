#!/bin/bash
#
# Production-grade stress test suite runner for Chimera Bridge.
# Orchestrates load_gen.py and verify_metrics.py to test the bridge.
#
# Usage: ./run_suite.sh [OPTIONS]
#
# Options:
#   -e, --expected N    Expected number of requests (default: 100)
#   -c, --concurrency N Number of concurrent requests (default: 20)
#   -r, --requests N    Total requests per client (default: 50)
#   -p, --poison       Enable poison mode with malformed payloads
#   -h, --help         Show help
#   -v, --verbose      Enable verbose output
#   -q, --quiet        Enable quiet mode (suppress non-error output)
#

set -euo pipefail

# Configuration
DEFAULT_EXPECTED_REQUESTS=100
DEFAULT_CONCURRENCY=20
DEFAULT_REQUESTS_PER_CLIENT=50
DEFAULT_WAIT_SECONDS=5
BRIDGE_URL="http://localhost:57123/metrics"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOAD_GEN_SCRIPT="${SCRIPT_DIR}/load_gen.py"
VERIFY_METRICS_SCRIPT="${SCRIPT_DIR}/verify_metrics.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Global variables
VERBOSE=false
QUIET=false
POISON_MODE=false
EXPECTED_REQUESTS=0
CONCURRENCY=0
TOTAL_REQUESTS=0

# Print usage information
usage() {
    cat << 'USAGE_EOF'
Usage: run_suite.sh [OPTIONS]

Stress test suite runner for Chimera Bridge.

Options:
  -e, --expected N    Expected number of requests (default: 100)
  -c, --concurrency N Number of concurrent requests (default: 20)
  -r, --requests N    Total requests per client (default: 50)
  -p, --poison       Enable poison mode with malformed payloads
  -h, --help         Show help
  -v, --verbose      Enable verbose output
  -q, --quiet        Enable quiet mode (suppress non-error output)
USAGE_EOF
}

# Log functions
log_info() {
    if ! $QUIET; then
        echo -e "${GREEN}[INFO]${NC} $1"
    fi
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_verbose() {
    if $VERBOSE; then
        echo -e "${NC}[VERBOSE] $1"
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--expected)
                EXPECTED_REQUESTS="$2"
                shift 2
                ;;
            -c|--concurrency)
                CONCURRENCY="$2"
                shift 2
                ;;
            -r|--requests)
                TOTAL_REQUESTS="$2"
                shift 2
                ;;
            -p|--poison)
                POISON_MODE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Set defaults if not specified
    EXPECTED_REQUESTS=${EXPECTED_REQUESTS:-$DEFAULT_EXPECTED_REQUESTS}
    CONCURRENCY=${CONCURRENCY:-$DEFAULT_CONCURRENCY}
    TOTAL_REQUESTS=${TOTAL_REQUESTS:-$DEFAULT_REQUESTS_PER_CLIENT}
}

# Check if bridge is running
check_bridge() {
    log_verbose "Checking if bridge is running..."
    if ! curl -s -o /dev/null -w "%{http_code}" "${BRIDGE_URL}" | grep -q "200"; then
        log_error "Bridge is not running at ${BRIDGE_URL}"
        exit 1
    fi
    log_info "Bridge is running"
}

# Get initial metrics
get_initial_metrics() {
    log_verbose "Fetching initial metrics..."
    local initial_requests
    initial_requests=$(curl -s "${BRIDGE_URL}" | grep "bridge_requests_total" | awk '{print $2}')
    log_verbose "Initial bridge_requests_total: ${initial_requests}"
    echo "${initial_requests}"
}

# Run load generator
run_load_generator() {
    log_info "Starting load generator..."
    local load_gen_cmd="python3 ${LOAD_GEN_SCRIPT} --requests ${TOTAL_REQUESTS} --concurrency ${CONCURRENCY}"
    if $POISON_MODE; then
        load_gen_cmd="${load_gen_cmd} --poison"
    fi
    log_verbose "Running: ${load_gen_cmd}"

    if ! python3 "${LOAD_GEN_SCRIPT}" --requests "${TOTAL_REQUESTS}" --concurrency "${CONCURRENCY}" > /tmp/load_gen_output.txt 2>&1; then
        log_error "Load generator failed. Output:"
        cat /tmp/load_gen_output.txt
        exit 1
    fi

    log_info "Load generator completed"
}

# Run metrics verification
run_metrics_verification() {
    local expected_delta=$1
    log_info "Running metrics verification..."
    log_verbose "Running: python3 ${VERIFY_METRICS_SCRIPT} ${expected_delta}"

    if ! python3 "${VERIFY_METRICS_SCRIPT}" "${expected_delta}"; then
        log_error "Metrics verification failed"
        exit 1
    fi

    log_info "Metrics verification completed"
}

# Main function
main() {
    parse_args "$@"

    log_info "Starting stress test suite..."
    log_info "Expected requests: ${EXPECTED_REQUESTS}"
    log_info "Total requests: ${TOTAL_REQUESTS}"
    log_info "Concurrency: ${CONCURRENCY}"
    log_info "Poison mode: ${POISON_MODE}"

    # Check if scripts exist
    if [[ ! -f "${LOAD_GEN_SCRIPT}" ]]; then
        log_error "Load generator script not found: ${LOAD_GEN_SCRIPT}"
        exit 1
    fi

    if [[ ! -f "${VERIFY_METRICS_SCRIPT}" ]]; then
        log_error "Metrics verification script not found: ${VERIFY_METRICS_SCRIPT}"
        exit 1
    fi

    # Check if bridge is running
    check_bridge

    # Get initial metrics
    local initial_requests
    initial_requests=$(get_initial_metrics)

    # Run load generator
    run_load_generator

    # Wait for metrics to update
    log_info "Waiting ${DEFAULT_WAIT_SECONDS} seconds for metrics to update..."
    sleep "${DEFAULT_WAIT_SECONDS}"

    # Calculate expected delta
    local expected_delta=$((TOTAL_REQUESTS))

    # Run metrics verification
    run_metrics_verification "${expected_delta}"

    log_info "Stress test suite completed successfully"
}

# Run main function
main "$@"
