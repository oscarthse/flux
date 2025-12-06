import os
import logging
import psycopg2
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")

@contextmanager
def get_db_connection(tenant_id=None):
    """
    Context manager for DB connection.
    Enforces RLS if tenant_id is provided.
    """
    conn = psycopg2.connect(DB_URL)
    try:
        if tenant_id:
            with conn.cursor() as cur:
                # Use set_config for safe parameterized tenant context
                # Third param 'true' = local to transaction
                cur.execute(
                    "SELECT set_config('app.current_tenant', %s, true)",
                    (str(tenant_id),)
                )
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # Reset tenant context before closing (safety measure)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('app.current_tenant', '', false)")
        except Exception:
            pass
        conn.close()
