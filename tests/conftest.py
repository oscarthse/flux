import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_db_connection():
    """
    Fixture that returns a mock database connection and cursor.
    Handles the context manager pattern: with conn.cursor() as cur:
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Setup cursor context manager: with conn.cursor() as cur
    # conn.cursor() returns a mock object whose __enter__ returns the actual mock_cursor
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    return mock_conn, mock_cursor

@pytest.fixture
def mock_prophet():
    """
    Fixture that mocks the Prophet class.
    """
    with patch("services.worker.engines.forecasting.prophet_model.Prophet") as mock:
        yield mock
