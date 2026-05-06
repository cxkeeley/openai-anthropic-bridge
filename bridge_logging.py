import os
import json
import logging
import logging.handlers
import sys

# --- 1. Logging ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "logs", "bridge.log")

# Auto-cleanup if Docker/System created a directory named 'bridge.log'
if os.path.isdir(LOG_PATH):
    import shutil
    shutil.rmtree(LOG_PATH)

# Structured logging formatter with request context
class StructuredLogFormatter(logging.Formatter):
    """Custom formatter that adds request context for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        # Add request context if available
        request_id = getattr(record, 'request_id', 'N/A')
        client_ip = getattr(record, 'client_ip', 'N/A')

        # Create structured JSON-like format
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'request_id': request_id,
            'client_ip': client_ip,
            'message': record.getMessage()
        }

        # Add extra fields if present
        if hasattr(record, 'detail'):
            log_entry['detail'] = record.detail
        if hasattr(record, 'error'):
            log_entry['error'] = record.error
        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint
        if hasattr(record, 'method'):
            log_entry['method'] = record.method
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
        if hasattr(record, 'duration_ms'):
            log_entry['duration_ms'] = record.duration_ms
        if hasattr(record, 'response_size'):
            log_entry['response_size'] = record.response_size

        return json.dumps(log_entry, indent=None, separators=(',', ':'))

    def formatException(self, ei):
        if ei[0]:
            return f"\n{self.formatExceptionName(ei[0])}: {ei[1]}"
        return ""

    def formatExceptionName(self, ei):
        return ei[0].__name__ if ei[0] else "Exception"


class ChimeraLogger:
    """ChimeraLogger - Structured logger for the bridge system"""

    def __init__(self, name: str = "Bridge"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup file and stream handlers with structured formatter"""
        # Create log directory if it doesn't exist
        LOG_DIR = os.path.dirname(LOG_PATH)
        if LOG_DIR and not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR, exist_ok=True)

        # Configure logging
        LOG_LEVEL_STR = os.environ.get("JTIU_LOG_LEVEL", "INFO").upper()
        LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

        log_formatter = StructuredLogFormatter()
        file_handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=10*102424, backupCount=3)
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(LOG_LEVEL)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(log_formatter)
        stream_handler.setLevel(LOG_LEVEL)

        # Configure root logger
        logging.basicConfig(level=LOG_LEVEL, handlers=[file_handler, stream_handler], force=True)
        self.logger.info(f"BRIDGE LOGGING TO: {LOG_PATH}")

    def info(self, message: str, **kwargs):
        """Log an info message with optional extra fields"""
        extra = kwargs.pop('extra', {})
        if isinstance(extra, dict):
            kwargs.update(extra)
        self.logger.info(message, extra=kwargs)

    def error(self, message: str, **kwargs):
        """Log an error message with optional extra fields"""
        extra = kwargs.pop('extra', {})
        if isinstance(extra, dict):
            kwargs.update(extra)
        self.logger.error(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        """Log a warning message with optional extra fields"""
        extra = kwargs.pop('extra', {})
        if isinstance(extra, dict):
            kwargs.update(extra)
        self.logger.warning(message, extra=kwargs)

    def debug(self, message: str, **kwargs):
        """Log a debug message with optional extra fields"""
        extra = kwargs.pop('extra', {})
        if isinstance(extra, dict):
            kwargs.update(extra)
        self.logger.debug(message, extra=kwargs)

    def critical(self, message: str, **kwargs):
        """Log a critical message with optional extra fields"""
        extra = kwargs.pop('extra', {})
        if isinstance(extra, dict):
            kwargs.update(extra)
        self.logger.critical(message, extra=kwargs)

    def get_underlying_logger(self) -> logging.Logger:
        """Get the underlying Python logger instance"""
        return self.logger


# Global logger instance
ChimeraLogger = ChimeraLogger("Bridge")
ChimeraLogger.info(f"BRIDGE LOGGING TO: {LOG_PATH}")
