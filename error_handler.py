"""Error handling utilities for safe operation of the translation app."""

import logging
import traceback
from functools import wraps
from typing import Callable, TypeVar, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def safe_execute(default_return=None, log_errors=True, error_message=None):
    """Decorator to safely execute functions and catch exceptions.
    
    Args:
        default_return: Value to return if an exception occurs
        log_errors: Whether to log errors
        error_message: Custom error message prefix
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                msg = error_message or f"Error in {func.__name__}"
                if log_errors:
                    logger.error(f"{msg}: {str(e)}")
                    logger.debug(traceback.format_exc())
                return default_return
        return wrapper  # type: ignore
    return decorator


def safe_execute_async(default_return=None, log_errors=True, error_message=None):
    """Decorator for async functions."""
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                msg = error_message or f"Error in {func.__name__}"
                if log_errors:
                    logger.error(f"{msg}: {str(e)}")
                    logger.debug(traceback.format_exc())
                return default_return
        return wrapper  # type: ignore
    return decorator


class SafeWindowCapture:
    """Wrapper to add safety checks to window capture operations."""
    
    @staticmethod
    def is_window_valid(hwnd) -> bool:
        """Check if a window handle is still valid."""
        if not hwnd:
            return False
        try:
            import ctypes
            from ctypes import windll
            # Check if window still exists
            return windll.user32.IsWindow(hwnd) != 0
        except Exception:
            return False
    
    @staticmethod
    def validate_image(image) -> bool:
        """Validate that an image is usable."""
        if image is None:
            return False
        try:
            from PIL import Image
            if not isinstance(image, Image.Image):
                return False
            # Check if image has valid size
            if image.size[0] <= 0 or image.size[1] <= 0:
                return False
            return True
        except Exception:
            return False


def validate_region_data(region_data: dict) -> bool:
    """Validate region data structure."""
    required_keys = ['left', 'top', 'width', 'height']
    if not isinstance(region_data, dict):
        return False
    for key in required_keys:
        if key not in region_data:
            return False
        if not isinstance(region_data[key], (int, float)):
            return False
        if region_data[key] < 0:
            return False
    return True
