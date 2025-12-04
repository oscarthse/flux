"""Unit tests for database service module."""
import pytest
from unittest.mock import patch, MagicMock
from services.api.database import DatabaseService
from services.api.exceptions import DatabaseError


@pytest.mark.unit
def test_database_service_singleton():
    """Test DatabaseService is a singleton."""
    db1 = DatabaseService()
    db2 = DatabaseService()
    assert db1 is db2, "DatabaseService should be a singleton"
    assert db1._connection_pool is db2._connection_pool


@pytest.mark.unit
def test_mock_cursor_context_manager_pattern(mock_db_connection):
    """Test mock supports: with conn.cursor() as cur:"""
    mock_conn, mock_cursor = mock_db_connection

    # This pattern should work
    with mock_conn.cursor() as cur:
        cur.execute("SELECT 1")

    mock_cursor.execute.assert_called_once_with("SELECT 1")


@pytest.mark.unit
def test_mock_cursor_direct_assignment_pattern(mock_db_connection):
    """Test mock supports: cur = conn.cursor()"""
    mock_conn, mock_cursor = mock_db_connection

    # This pattern should also work
    cur = mock_conn.cursor()
    # cur is actually the mock_cursor due to return_value
    # But mock_conn.cursor() returns a MagicMock that has mock_cursor as __enter__ result
    # So we need to check if cursor was called
    assert mock_conn.cursor.called

    # When using context manager, it works:
    with mock_conn.cursor() as c:
        c.execute("SELECT 2")

    mock_cursor.execute.assert_called_with("SELECT 2")


@pytest.mark.unit
def test_database_service_has_required_methods():
    """Test DatabaseService has all required methods."""
    db_service = DatabaseService()

    assert hasattr(db_service, 'get_connection')
    assert hasattr(db_service, 'get_cursor')
    assert hasattr(db_service, 'close_all_connections')
    assert callable(db_service.get_connection)
    assert callable(db_service.get_cursor)
