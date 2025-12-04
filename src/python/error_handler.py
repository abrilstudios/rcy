"""
RCY Error Handler Module

This module provides a centralized error handling system that:
1. Logs errors to stdout/stderr for visibility
2. Provides a consistent error reporting pattern throughout the application
"""

import traceback
import logging

logger = logging.getLogger("rcy.error_handler")


class ErrorHandler:
    """Centralized error handling for RCY application."""

    @staticmethod
    def log_exception(e: Exception, context: str = "") -> str:
        """Log an exception with stack trace to stdout."""
        error_type = type(e).__name__
        error_msg = str(e)

        if context:
            logger.error(f"{context}: {error_type}: {error_msg}")
        else:
            logger.error(f"{error_type}: {error_msg}")

        # Log the full stack trace
        traceback.print_exc()

        return f"{error_type}: {error_msg}"

    @staticmethod
    def show_error(message: str, title: str = "Error") -> None:
        """Log an error message."""
        logger.error(f"[{title}] {message}")

    @staticmethod
    def show_warning(message: str, title: str = "Warning") -> None:
        """Log a warning message."""
        logger.warning(f"[{title}] {message}")

    @staticmethod
    def show_info(message: str, title: str = "Info") -> None:
        """Log an info message."""
        logger.info(f"[{title}] {message}")
