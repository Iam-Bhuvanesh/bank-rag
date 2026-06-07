import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Resolve base directories
# This will output logs to backend/logs/app.log
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = LOG_DIR / "app.log"

def setup_logging(log_level: str = "INFO") -> None:
    """
    Configures the root logging settings for the entire application.
    Streams formatted logs to the standard output and persists rotating log files.
    """
    # Parse logging level string to integer level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Log line format: [Timestamp] [Level] [Logger Name] [File:Line] - Message
    log_format = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s %(name)s [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler (Standard Output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(numeric_level)

    # 2. File Handler (Rotating log file, max 10MB per file, keeping up to 5 backups)
    file_handler = RotatingFileHandler(
        filename=LOG_FILE_PATH,
        maxBytes=10 * 1024 * 1024,  # 10 Megabytes
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(numeric_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to prevent duplicate logs
    root_logger.handlers = []
    
    # Add console and file logging targets
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set custom levels on noisy external libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    logging.info(f"Centralized logging initialized. Log level: {log_level.upper()} | Output: {LOG_FILE_PATH}")
