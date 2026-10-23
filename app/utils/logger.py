"""
Centralized logging service with thread-safe UI callback support.
"""

import logging
import sys
from datetime import datetime
from collections import deque
from pathlib import Path
from typing import Callable, List, Optional
from config import LOGS_DIR

# Keep last 500 log records in memory for UI views
_LOG_HISTORY: deque = deque(maxlen=500)
_LOG_LISTENERS: List[Callable[[dict], None]] = []

class MemoryLogHandler(logging.Handler):
    """Custom logging handler that buffers log records and dispatches to UI listeners."""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3],
                "level": record.levelname,
                "name": record.name,
                "message": self.format(record),
                "raw_message": record.getMessage()
            }
            _LOG_HISTORY.append(entry)
            for listener in _LOG_LISTENERS:
                try:
                    listener(entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

def setup_logger(name: str = "SmartLeads") -> logging.Logger:
    """Configures and returns the application logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_file_path = LOGS_DIR / f"smart_leads_{today_str}.log"
    try:
        file_handler = logging.FileHandler(str(log_file_path), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create log file: {e}", file=sys.stderr)

    # Memory Handler for UI
    mem_handler = MemoryLogHandler()
    mem_handler.setLevel(logging.DEBUG)
    mem_handler.setFormatter(formatter)
    logger.addHandler(mem_handler)

    return logger

def add_log_listener(callback: Callable[[dict], None]) -> None:
    """Register a callback for new log events (thread-safe)."""
    if callback not in _LOG_LISTENERS:
        _LOG_LISTENERS.append(callback)

def remove_log_listener(callback: Callable[[dict], None]) -> None:
    """Unregister a log event callback."""
    if callback in _LOG_LISTENERS:
        _LOG_LISTENERS.remove(callback)

def get_log_history() -> List[dict]:
    """Retrieve in-memory log history."""
    return list(_LOG_HISTORY)

# Global default logger
logger = setup_logger()
