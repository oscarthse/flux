from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.api.context import tenant_context
import psycopg2
import os

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/whoami")
async def whoami(request: Request):
    """Debug endpoint to show current session info"""
    tenant_id = tenant_context.get()

    # Get tenant details
    DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flux")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get tenant name
    cur.execute("SELECT name FROM tenants WHERE id = %s", (tenant_id,))
    tenant_result = cur.fetchone()
    tenant_name = tenant_result[0] if tenant_result else "UNKNOWN"

    # Get menu items
    cur.execute("SELECT name FROM menu_items WHERE tenant_id = %s LIMIT 10", (tenant_id,))
    menu_items = [r[0] for r in cur.fetchall()]

    # Get user
    cur.execute("SELECT email FROM users WHERE tenant_id = %s", (tenant_id,))
    users = [r[0] for r in cur.fetchall()]

    conn.close()

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "users": users,
        "menu_items": menu_items,
        "cookie_present": "flux_session" in request.cookies
    }
