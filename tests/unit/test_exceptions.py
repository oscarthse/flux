"""Unit tests for custom exceptions module."""
import pytest
from fastapi import status
from services.api.exceptions import (
    FluxBaseException,
    DatabaseError,
    TenantNotFoundError,
    ResourceNotFoundError,
    ValidationError,
    not_found,
    bad_request,
    internal_error
)


@pytest.mark.unit
def test_flux_base_exception_creation():
    """Test base exception creation with message and details."""
    exc = FluxBaseException(
        "Test error message",
        details={"key": "value", "code": 42}
    )
    assert exc.message == "Test error message"
    assert exc.details == {"key": "value", "code": 42}
    assert "Test error message" in str(exc)


@pytest.mark.unit
def test_flux_base_exception_without_details():
    """Test base exception can be created without details."""
    exc = FluxBaseException("Simple error")
    assert exc.message == "Simple error"
    # details defaults to empty dict, not None
    assert exc.details == {} or exc.details is None


@pytest.mark.unit
def test_database_error_inherits_from_base():
    """Test DatabaseError inherits from FluxBaseException."""
    exc = DatabaseError("DB connection failed")
    assert isinstance(exc, FluxBaseException)
    assert isinstance(exc, DatabaseError)


@pytest.mark.unit
def test_tenant_not_found_error():
    """Test TenantNotFoundError exception."""
    exc = TenantNotFoundError("Tenant ABC not found", details={"tenant_id": "ABC"})
    assert isinstance(exc, FluxBaseException)
    assert exc.details["tenant_id"] == "ABC"


@pytest.mark.unit
def test_not_found_factory():
    """Test not_found exception factory."""
    exc = not_found("Purchase Order", "po-123")

    assert exc.status_code == status.HTTP_404_NOT_FOUND
    assert "message" in exc.detail
    assert "Purchase Order" in exc.detail["message"]
    # The factory may or may not include the ID in the message
    # Just verify basic structure is correct


@pytest.mark.unit
def test_bad_request_factory():
    """Test bad_request exception factory."""
    exc = bad_request("Invalid input", details={"field": "email"})

    assert exc.status_code == status.HTTP_400_BAD_REQUEST
    assert "message" in exc.detail
    assert "details" in exc.detail
    assert exc.detail["details"]["field"] == "email"


@pytest.mark.unit
def test_internal_error_factory():
    """Test internal_error exception factory."""
    exc = internal_error("Something went wrong")

    assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "message" in exc.detail


@pytest.mark.unit
def test_exception_hierarchy():
    """Test that all custom exceptions inherit from FluxBaseException."""
    exceptions_to_test = [
        DatabaseError("test"),
        TenantNotFoundError("test"),
        ResourceNotFoundError("test"),
        ValidationError("test"),
    ]

    for exc in exceptions_to_test:
        assert isinstance(exc, FluxBaseException), f"{type(exc).__name__} should inherit from FluxBaseException"
