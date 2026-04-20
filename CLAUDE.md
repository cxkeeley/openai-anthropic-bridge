# Claude Bridge for JiuTian (九天) Model

## Purpose

This repository contains a bridge application that allows the JiuTian (九天) AI model to be used with both the Anthropic and OpenAI API formats. The bridge translates between these API formats, enabling seamless integration with various AI development tools and platforms.

## Project Structure

- `claude_bridge.py`: Main application with enhanced error handling and configuration
- `simple_bridge.py`: Basic implementation of the bridge functionality
- `start_claude_bridge.sh`: Enhanced startup script with better configuration options
- `test_claude_bridge.py`: Comprehensive test suite for the bridge
- `test-jiutien.py`: Additional test script for the JiuTian model
- `requirements.txt`: Python dependencies
- `README.md`: Project documentation

## Key Features

1. **Dual API Support**
   - Anthropic API compatible endpoint at `/v1/messages`
   - OpenAI API compatible endpoint at `/v1/chat/completions`

2. **Flexible Configuration**
   - Command-line arguments
   - Environment variables
   - Default values

3. **Robust Error Handling**
   - Comprehensive error handling for API requests
   - Proper status code propagation
   - Detailed logging

4. **Streaming Support**
   - Full support for streaming responses
   - Proper event stream formatting
   - Client-side compatibility with both API formats

5. **Testing**
   - Integration tests for both endpoints
   - Health check endpoint testing
   - Proper resource cleanup

## Usage

### Starting the Bridge

```bash
# Using the start script (recommended)
./start_claude_bridge.sh

# With custom port
./start_claude_bridge.sh --port 8080

# In debug mode
./start_claude_bridge.sh --debug

# Direct execution
python claude_bridge.py --host=127.0.0.1 --port=8000
```

### Environment Variables

- `JTIU_HOST`: Host to bind to (default: 127.0.0.1)
- `JTIU_PORT`: Port to listen on (default: 8000)
- `JTIU_TARGET_URL`: Target JiuTian service URL
- `JTIU_TOKEN`: Authentication token

### Connecting Claude Code

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_API_KEY="sk-any-key"
claude --model jt_indonesia
```

## Development

### Running Tests

```bash
python test_claude_bridge.py
```

### Adding New Features

When adding new features to the bridge:

1. Update the `claude_bridge.py` file with the new functionality
2. Add corresponding tests in `test_claude_bridge.py`
3. Update this CLAUDE.md documentation
4. Test thoroughly with both API endpoints

### Code Style

- Follow PEP 8 guidelines for Python code
- Use descriptive variable and function names
- Include docstrings for all functions and classes
- Add comments for complex logic
- Maintain consistent formatting

## Architecture

The bridge operates as a proxy server that translates between different API formats:

1. **Request Flow**:
   - Client sends request to bridge
   - Bridge translates request format if needed
   - Bridge forwards request to JiuTian model
   - Bridge receives response
   - Bridge translates response format if needed
   - Bridge returns response to client

2. **Key Components**:
   - API endpoint handlers
   - Request/response transformers
   - Error handling middleware
   - Configuration manager

## Security Considerations

- Use environment variables for sensitive data
- Validate all incoming requests
- Implement rate limiting in production
- Use HTTPS in production environments
- Rotate authentication tokens regularly

## Deployment

For production deployment:

1. Use a process manager like systemd or supervisor
2. Set up proper logging and monitoring
3. Implement health checks
4. Configure a reverse proxy (e.g., nginx)
5. Set up SSL/TLS encryption

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure the bridge is running
   - Check that the port is not in use
   - Verify host and port configuration

2. **Authentication Errors**
   - Verify your token is correct and not expired
   - Check that the target URL is accessible

3. **Streaming Issues**
   - Ensure your client supports Server-Sent Events (SSE)
   - Check network connection stability

## License

This project is licensed under the MIT License - see the LICENSE file for details.
