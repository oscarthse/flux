"""
Custom exceptions for Flux Platform.

Provides a hierarchy of domain-specific exceptions with structured error
details for better error handling and API responses.

Exception Hierarchy:
    FluxBaseException
    ├── DatabaseError
    ├── TenantNotFoundError
    ├── ResourceNotFoundError
    ├── ValidationError
    ├── OptimizationError
    └── ForecastingError

Usage:
    >>> from services.api.exceptions import DatabaseError, not_found
    >>>
    >>> # Raise custom exception
    >>> raise DatabaseError(
    ...     "Connection failed",
    ...     details={"host": "localhost", "error_code": "08001"}
    ... )
    >>>
    >>> # Use HTTP exception factories
    >>> from fastapi import HTTPException
    >>> raise not_found("Purchase Order", "po-123")

Best Practices:
    - Use specific exception types for different error categories
    - Always include context in the details dictionary
    - Use factory functions (not_found, bad_request, etc.) in API routes
    - Log exceptions before raising them
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class FluxBaseException(Exception):
    """
    Base exception for all Flux-specific errors.

    All custom exceptions should inherit from this class to allow
    for centralized exception handling.

    Attributes:
        message: Human-readable error message
        details: Dictionary of additional error context

    Example:
        >>> try:
        ...     raise FluxBaseException(
        ...         "Something went wrong",
        ...         details={"component": "inventory", "action": "generate_po"}
        ...     )
        ... except FluxBaseException as e:
        ...     print(f"Error: {e.message}")
        ...     print(f"Details: {e.details}")
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(FluxBaseException):
    """Database operation failed."""
    pass


class TenantNotFoundError(FluxBaseException):
    """Tenant does not exist or is inactive."""
    pass


class ResourceNotFoundError(FluxBaseException):
    """Requested resource does not exist."""
    pass


class ValidationError(FluxBaseException):
    """Input validation failed."""
    pass


class OptimizationError(FluxBaseException):
    """Inventory optimization failed."""
    pass


class ForecastingError(FluxBaseException):
    """Forecasting computation failed."""
    pass


def create_http_exception(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """
    Create a standardized HTTPException with details.

    Args:
        status_code: HTTP status code
        message: Error message
        details: Additional error context

    Returns:
        HTTPException with formatted detail
    """
    detail = {"message": message}
    if details:
        detail["details"] = details

    return HTTPException(status_code=status_code, detail=detail)


# Convenience exception factories
def not_found(resource: str, identifier: str) -> HTTPException:
    """Create a 404 Not Found exception."""
    return create_http_exception(
        status.HTTP_404_NOT_FOUND,
        f"{resource} not found",
        {"identifier": identifier}
    )


def bad_request(message: str, details: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Create a 400 Bad Request exception."""
    return create_http_exception(
        status.HTTP_400_BAD_REQUEST,
        message,
        details
    )


def internal_error(message: str = "Internal server error", details: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Create a 500 Internal Server Error exception."""
    return create_http_exception(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        message,
        details
    )
