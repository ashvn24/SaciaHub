"""
Structured logging configuration with JSON support for production.
"""

import logging
import logging.config
import os
import sys
from typing import Any, Dict

from src.core.config import get_settings


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        return json.dumps(log_entry)


def setup_logging() -> logging.Logger:
    """Configure application logging based on environment."""
    settings = get_settings()

    os.makedirs("logs", exist_ok=True)

    if settings.is_production:
        formatter_config = {
            "json": {
                "()": f"{__name__}.JSONFormatter",
            }
        }
        default_formatter = "json"
    else:
        formatter_config = {
            "default": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        }
        default_formatter = "default"

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatter_config,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": default_formatter,
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": default_formatter,
                "filename": "logs/app.log",
                "when": "midnight",
                "backupCount": 14,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "app": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console", "file"],
        },
    }

    logging.config.dictConfig(logging_config)
    return logging.getLogger("app")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the app prefix."""
    return logging.getLogger(f"app.{name}")
