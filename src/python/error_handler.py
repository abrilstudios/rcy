"""
RCY Error Handler Module

This module provides a centralized error handling system that:
1. Logs errors to stdout/stderr for visibility to AI assistants
2. Optionally shows user-friendly notifications/toasts rather than modal dialogs
3. Provides a consistent error reporting pattern throughout the application
"""

import sys
import traceback
import logging
from typing import Optional, Callable, Any

from PyQt6.QtWidgets import QMessageBox, QApplication, QWidget
from PyQt6.QtCore import Qt, QObject, QTimer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout  # Log to stdout for AI visibility
)

logger = logging.getLogger("rcy.error_handler")

# Global flag to determine if we should show UI error dialogs
# Set to False in tests or headless environments
SHOW_UI_ERRORS = True


class ErrorHandler:
    """Centralized error handling for RCY application."""
    
    @staticmethod
    def set_show_ui_errors(show: bool):
        """Set whether UI error dialogs should be shown."""
        global SHOW_UI_ERRORS
        SHOW_UI_ERRORS = show
    
    @staticmethod
    def log_exception(e: Exception, context: str = ""):
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
    def show_error(message: str, title: str = "Error", parent: Optional[QWidget] = None):
        """Show an error message to the user and log it."""
        # Always log the error for AI visibility
        logger.error(f"UI ERROR - {title}: {message}")
        
        # Only show UI dialog if enabled and we have a QApplication
        if SHOW_UI_ERRORS and QApplication.instance():
            # Use non-modal message box
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            
            # Show non-modally if we have a parent
            if parent:
                msg_box.setWindowModality(Qt.WindowModality.NonModal)
                msg_box.show()
            else:
                # We still need to show modally if no parent to prevent box from being garbage collected
                msg_box.exec()
    
    @staticmethod
    def handle_exception(e: Exception, context: str = "", parent: Optional[QWidget] = None, 
                         title: str = "Application Error", show_ui: bool = True):
        """Log an exception and optionally show it to the user."""
        # Log and format the error message
        error_msg = ErrorHandler.log_exception(e, context)
        
        # Show to user if requested
        if show_ui:
            context_prefix = f"{context}: " if context else ""
            ErrorHandler.show_error(f"{context_prefix}{error_msg}", title, parent)
        
        return error_msg


def exception_handling_decorator(func: Callable) -> Callable:
    """Decorator to handle exceptions in any function."""
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Get parent widget if first arg is a QWidget
            parent = args[0] if args and isinstance(args[0], QWidget) else None
            ErrorHandler.handle_exception(e, context=func.__name__, parent=parent)
            # Re-raise to allow caller to handle
            raise
    return wrapper


# Simple global function for error display without instantiating the class
def show_error(message: str, title: str = "Error", parent: Optional[QWidget] = None):
    """Helper function to show and log an error message."""
    ErrorHandler.show_error(message, title, parent)


# Install a global exception hook to catch unhandled exceptions
def install_global_exception_hook():
    """Install a global exception hook to catch unhandled exceptions."""
    original_hook = sys.excepthook
    
    def exception_hook(exc_type, exc_value, exc_traceback):
        # Log the exception
        logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))
        
        # Show error to user if UI is available and enabled
        if SHOW_UI_ERRORS and QApplication.instance():
            error_msg = str(exc_value)
            ErrorHandler.show_error(f"Unhandled exception: {error_msg}", "Critical Error")
        
        # Call the original exception hook
        original_hook(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = exception_hook