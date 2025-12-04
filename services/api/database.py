"""
Database service layer with connection pooling and error handling.

Provides a clean interface for database operations with proper resource management.
"""
import logging
from contextlib import contextmanager
from typing import Optional, Generator
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from services.api.config import settings
from services.api.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Database service with connection pooling and tenant context management.

    Implements the singleton pattern to ensure only one connection pool exists
    for the application. Provides context managers for safe connection and
    cursor management with automatic resource cleanup.

    Features:
        - Connection pooling for improved performance
        - Row Level Security (RLS) support via tenant context
        - Automatic transaction management (commit/rollback)
        - Comprehensive error handling with custom exceptions
        - Proper resource cleanup via context managers

    Example:
        >>> from services.api.database import db_service
        >>> from services.api.config import settings
        >>>
        >>> # Get a cursor with tenant context
        >>> tenant_id = settings.DEFAULT_TENANT_ID
        >>> with db_service.get_cursor(tenant_id=tenant_id) as cur:
        ...     cur.execute("SELECT * FROM menu_items")
        ...     items = cur.fetchall()
        >>>
        >>> # Manually manage connection
        >>> with db_service.get_connection(tenant_id=tenant_id) as conn:
        ...     with conn.cursor() as cur:
        ...         cur.execute("INSERT INTO ...")
        ...         cur.execute("UPDATE ...")
        ...     # Auto-commits on successful exit

    Attributes:
        _instance: Singleton instance of DatabaseService
        _connection_pool: psycopg2 connection pool

    Note:
        This is a singleton - calling DatabaseService() multiple times
        returns the same instance with the same connection pool.
    """

    _instance: Optional['DatabaseService'] = None
    _connection_pool: Optional[pool.SimpleConnectionPool] = None

    def __new__(cls):
        """Singleton pattern to ensure only one connection pool."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize connection pool if not already initialized."""
        if self._connection_pool is None:
            try:
                self._connection_pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=settings.DB_POOL_SIZE,
                    dsn=settings.DATABASE_URL
                )
                logger.info("Database connection pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize connection pool: {e}")
                raise DatabaseError(
                    "Failed to initialize database connection pool",
                    details={"error": str(e)}
                )

    @contextmanager
    def get_connection(
        self,
        tenant_id: Optional[str] = None
    ) -> Generator:
        """
        Get a database connection from the pool with optional tenant context.

        Args:
            tenant_id: Tenant ID for RLS. Uses default if not provided.

        Yields:
            Database connection

        Raises:
            DatabaseError: If unable to get connection

        Example:
            with db_service.get_connection(tenant_id="123") as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM menu_items WHERE tenant_id = %s", (tenant_id,))
        """
        conn = None
        try:
            conn = self._connection_pool.getconn()

            # Set tenant context for RLS if enabled
            if settings.ENABLE_RLS and tenant_id:
                with conn.cursor() as cur:
                    cur.execute("SET app.current_tenant_id = %s", (tenant_id,))

            yield conn

            conn.commit()

        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e.pgcode} - {e.pgerror}")
            raise DatabaseError(
                "Database operation failed",
                details={
                    "error_code": e.pgcode,
                    "error_message": str(e)
                }
            )
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Unexpected error in database operation: {type(e).__name__}: {e}", exc_info=True)
            raise DatabaseError(
                "Unexpected database error",
                details={"error": str(e), "error_type": type(e).__name__}
            )
        finally:
            if conn:
                # Reset tenant context
                if settings.ENABLE_RLS:
                    try:
                        with conn.cursor() as cur:
                            cur.execute("RESET app.current_tenant_id")
                    except:
                        pass

                self._connection_pool.putconn(conn)

    @contextmanager
    def get_cursor(
        self,
        tenant_id: Optional[str] = None
    ) -> Generator:
        """
        Convenience method to get a cursor directly.

        Args:
            tenant_id: Tenant ID for RLS

        Yields:
            Database cursor

        Example:
            with db_service.get_cursor(tenant_id="123") as cur:
                cur.execute("SELECT * FROM menu_items")
                results = cur.fetchall()
        """
        with self.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                yield cur

    def close_all_connections(self):
        """Close all connections in the pool. Call on application shutdown."""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("All database connections closed")


# Global database service instance
db_service = DatabaseService()
