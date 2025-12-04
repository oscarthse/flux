import os
import psycopg2
from contextlib import contextmanager

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
                cur.execute(f"SET app.current_tenant_id = '{tenant_id}';")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
