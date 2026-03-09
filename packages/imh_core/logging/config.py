import logging
import logging.config
import os


# Define base directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
LOG_DIR = os.path.join(BASE_DIR, "logs")
AGENT_LOG_DIR = os.path.join(LOG_DIR, "agent")

# Ensure log directories exist
os.makedirs(AGENT_LOG_DIR, exist_ok=True)

# Log file paths
AGENT_LOG_FILE = os.path.join(AGENT_LOG_DIR, "agent.log")
AGENT_ERROR_LOG_FILE = os.path.join(AGENT_LOG_DIR, "agent.error.log")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file_agent": {
            "level": "DEBUG",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": AGENT_LOG_FILE,
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "encoding": "utf-8",
            "formatter": "standard",
        },
        "file_error": {
            "level": "ERROR",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": AGENT_ERROR_LOG_FILE,
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "encoding": "utf-8",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console", "file_agent", "file_error"],
        "level": "DEBUG",
    },
}

def setup_logging():
    """Apply default logging configuration."""
    logging.config.dictConfig(LOGGING_CONFIG)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with standard configuration."""
    # Ensure configuration is applied at least once
    if not logging.getLogger().handlers:
        setup_logging()
    
    return logging.getLogger(name)

# Apply configuration immediately upon import to ensure capture
setup_logging()
