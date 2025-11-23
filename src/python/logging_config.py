"""
Logging configuration for RCY application.

This module provides centralized logging configuration with support for:
- Console output (development)
- Rotating file logs (production)
- Configurable log levels
- Structured log format
"""

import logging
import logging.handlers
import os
from pathlib import Path
from config_manager import config


def setup_logging():
    """
    Initialize logging configuration for the application.

    Reads configuration from config.json and sets up:
    - Root logger with configured level
    - Console handler for development output
    - Rotating file handler for persistent logs
    - Consistent formatting across all handlers

    Configuration is read from the 'logging' section of config.json:
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - file: Path to log file
    - maxBytes: Maximum log file size before rotation
    - backupCount: Number of backup files to keep
    - console: Whether to enable console output
    """
    # Get logging configuration
    log_level_str = config.get_logging_setting("level", "INFO")
    log_file = config.get_logging_setting("file", "logs/rcy.log")
    max_bytes = config.get_logging_setting("maxBytes", 10485760)  # 10MB default
    backup_count = config.get_logging_setting("backupCount", 3)
    console_enabled = config.get_logging_setting("console", True)

    # Convert log level string to logging constant
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Add console handler if enabled
    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Create log directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Add rotating file handler
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        root_logger.info("=" * 70)
        root_logger.info("RCY Application Started")
        root_logger.info("=" * 70)
        root_logger.info("Logging initialized - Level: %s, File: %s", log_level_str, log_file)

    except Exception as e:
        # If file handler fails, log to console only
        root_logger.error("Failed to initialize file logging: %s", e)
        root_logger.warning("Continuing with console logging only")


def get_logger(name):
    """
    Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)
