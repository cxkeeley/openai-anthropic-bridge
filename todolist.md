# Todo List - Claude Code API Compliance

## Missing Features to Add

### 1. Tool Result Streaming
- **Priority**: High
- **Description**: Add proper tool result streaming with `tool_result` event type
- **Current State**: Tool results are merged into messages but not streamed separately
- **Required**: Stream tool results as they complete with proper `tool_result` event type
- **Status**: ⚠️ **PENDING** - Tool results are merged into messages but not streamed separately. This is a medium priority item that can be addressed later.

### 2. Usage Tracking
- **Priority**: High
- **Description**: Implement proper token usage tracking in `usage` field
- **Current State**: Token usage is set to 0 for all requests
- **Required**: Parse and track input_tokens and output_tokens from upstream response
- **Status**: ✅ **COMPLETED** - Usage tracking is now implemented. The bridge parses `usage` from upstream response chunks and updates `output_tokens` in the final `message_delta` event.

### 3. Message ID Persistence
- **Priority**: Medium
- **Description**: Use consistent message IDs across streaming chunks
- **Current State**: Message IDs are generated per request with timestamp
- **Required**: Use upstream message ID if available, or generate once per request

### 4. Tool Call ID Validation
- **Priority**: Medium
- **Description**: Validate tool call IDs match expected format
- **Current State**: Tool call IDs are generated with `call_{timestamp}_{idx}` format
- **Required**: Validate tool call IDs match Claude Code expected format

### 5. Error Handling Improvements
- **Priority**: Medium
- **Description**: Improve error handling for upstream errors
- **Current State**: Errors are logged but may not be properly formatted
- **Required**: Format errors according to Claude Code error format

### 6. Rate Limiting
- **Priority**: Low
- **Description**: Implement rate limiting for upstream requests
- **Current State**: No rate limiting
- **Required**: Add rate limiting based on upstream response headers

### 7. Request Timeout
- **Priority**: Low
- **Description**: Add configurable request timeout
- **Current State**: Fixed 600 second timeout
- **Required**: Make timeout configurable via environment variable

### 8. Health Check Improvements
- **Priority**: Low
- **Description**: Improve health check endpoint
- **Current State**: Simple status check
- **Required**: Add upstream connectivity check

## Implementation Order

1. **Usage Tracking** (High Priority) - ✅ **COMPLETED**
2. **Tool Result Streaming** (High Priority) - ⚠️ **PENDING**
3. **Message ID Persistence** (Medium Priority)
4. **Error Handling Improvements** (Medium Priority)
5. **Tool Call ID Validation** (Medium Priority)
6. **Request Timeout** (Low Priority)
7. **Rate Limiting** (Low Priority)
8. **Health Check Improvements** (Low Priority)

## Notes

- All changes should maintain backward compatibility
- Follow existing code style and patterns
- Add appropriate logging for new features
- Test changes with existing test suite
