"""
Logging configuration for Flux Platform.

Provides structured logging with request correlation and proper formatting.
"""
import logging
import sys
from typing import Optional
from services.api.config import settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Optional log level override. Uses settings.LOG_LEVEL if not provided.
    """
    level = log_level or settings.LOG_LEVEL

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=settings.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at {level} level")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Processing started")
    """
    return logging.getLogger(name)
