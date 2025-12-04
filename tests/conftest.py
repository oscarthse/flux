import pytest
import os
import psycopg2
from uuid import uuid4
from unittest.mock import MagicMock, patch
import lib.flux_lib.db
from importlib import reload

from services.api.config import Settings

# Use the app user for testing RLS (superuser bypasses RLS)
TEST_DB_URL = "postgresql://flux:flux_password@localhost:5432/flux_test"

os.environ["DATABASE_URL"] = TEST_DB_URL

# Reload the module so it picks up the new env var
reload(lib.flux_lib.db)
from lib.flux_lib.db import get_db_connection
DB_URL = TEST_DB_URL

# Patch the global db_service singleton to use the test database
# This ensures that all routers (which import db_service) use the correct pool
from services.api.database import db_service
from psycopg2 import pool

if db_service._connection_pool:
    try:
        db_service._connection_pool.closeall()
    except Exception:
        pass

# Re-initialize pool with test credentials
db_service._connection_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=TEST_DB_URL
)



# ============================================================================
# Settings & Configuration
# ============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        DATABASE_URL=TEST_DB_URL,
        DEFAULT_TENANT_ID="test-tenant-00-0000-0000-000000000000",
        LOG_LEVEL="DEBUG",
        REDIS_URL="redis://localhost:6379/15"
    )


# ============================================================================
# Database Fixtures (RLS-aware)
# ============================================================================

@pytest.fixture(scope="session")
def db_connection():
    """Global DB connection for setup/teardown."""
    conn = psycopg2.connect(DB_URL)
    yield conn
    conn.close()


@pytest.fixture
def tenant_id(db_connection):
    """Creates a temporary tenant for testing."""
    tid = str(uuid4())
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", (tid, f"Test Tenant {tid}"))
    db_connection.commit()
    return tid


@pytest.fixture
def other_tenant_id(db_connection):
    """Creates a second tenant to test isolation."""
    tid = str(uuid4())
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", (tid, f"Other Tenant {tid}"))
    db_connection.commit()
    return tid


# Alias for consistency with new tests
@pytest.fixture
def tenant_a_id(tenant_id):
    """Alias for tenant_id (tenant A)."""
    return tenant_id


@pytest.fixture
def tenant_b_id(other_tenant_id):
    """Alias for other_tenant_id (tenant B)."""
    return other_tenant_id


@pytest.fixture
def test_tenant_id():
    """Standard test tenant ID."""
    return "a73ba506-b078-42b3-91f6-fd168c958ee2"


# ============================================================================
# Mock Database Fixtures (FIXED - supports both cursor patterns)
# ============================================================================

@pytest.fixture
def mock_db_connection():
    """
    Mock database connection supporting BOTH cursor patterns:
    1. with conn.cursor() as cur:
    2. cur = conn.cursor()
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Support context manager pattern: with conn.cursor() as cur:
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = None

    # Support direct assignment pattern: cur = conn.cursor()
    # The __enter__ makes it work as a context manager
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=None)

    # Mock execute/fetchall
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = None
    mock_cursor.execute.return_value = None
    mock_cursor.close.return_value = None

    # Mock transaction methods
    mock_conn.commit.return_value = None
    mock_conn.rollback.return_value = None
    mock_conn.close.return_value = None

    return mock_conn, mock_cursor


# ============================================================================
# Worker / Redis Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for worker tests."""
    with patch('redis.Redis') as mock:
        yield mock.return_value



@pytest.fixture
def mock_dramatiq_broker():
    """Mock Dramatiq broker for worker tests."""
    with patch('dramatiq.get_broker') as mock:
        yield mock.return_value


@pytest.fixture
def mock_prophet():
    """
    Mock Prophet class to avoid installing/running full Prophet.

    Returns a MagicMock that simulates the Prophet API:
    - fit()
    - make_future_dataframe()
    - predict()
    - history attribute
    """
    with patch('services.worker.engines.forecasting.prophet_model.Prophet') as mock_cls:
        # Setup the mock instance returned by Prophet()
        mock_instance = mock_cls.return_value

        # Mock fit
        mock_instance.fit.return_value = None

        # Mock make_future_dataframe
        # Returns a dummy DataFrame with 'ds' column
        def make_future_df(periods):
            import pandas as pd
            dates = pd.date_range(start='2025-01-01', periods=periods + 10) # +10 to cover history
            return pd.DataFrame({'ds': dates})
        mock_instance.make_future_dataframe.side_effect = make_future_df

        # Mock predict
        # Returns a DataFrame with 'ds' and 'yhat'
        def predict(df):
            import pandas as pd
            df['yhat'] = 10.0 # Constant prediction
            return df
        mock_instance.predict.side_effect = predict

        # Mock history
        import pandas as pd
        mock_instance.history = pd.DataFrame({
            'ds': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'y': [10.0, 12.0]
        })

        yield mock_cls



# ============================================================================
# Test Data Factories
# ============================================================================

@pytest.fixture
def sample_menu_item_data(tenant_a_id):
    """Sample menu item data."""
    return {
        "id": str(uuid4()),
        "tenant_id": tenant_a_id,
        "name": "Test Burger",
        "category": "Mains",
        "price": 15.99
    }


@pytest.fixture
def sample_ingredient_data(tenant_a_id):
    """Sample ingredient data."""
    return {
        "id": str(uuid4()),
        "tenant_id": tenant_a_id,
        "name": "Test Beef",
        "cost_per_unit": 8.50,
        "unit": "kg",
        "par_level": 50.0,
        "reorder_threshold": 20.0,
        "lead_time_days": 2
    }
