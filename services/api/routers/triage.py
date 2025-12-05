from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from lib.flux_lib.db import get_db_connection
from typing import Optional

router = APIRouter(prefix="/triage", tags=["triage"])
templates = Jinja2Templates(directory="services/api/templates")

# Mock Tenant ID for now (In prod, this comes from auth)
DEFAULT_TENANT_ID = "3cf60c8e-5b33-4fb3-a9f0-6fbc0cabd6aa" # Matches test fixture if possible, or placeholder

@router.get("/", response_class=HTMLResponse)
async def triage_page(request: Request):
    """Render the main Triage Room page."""
    return templates.TemplateResponse("triage.html", {
        "request": request,
        "tenant_name": "Demo Tenant"
    })

@router.get("/list", response_class=HTMLResponse)
async def list_triage_items(request: Request):
    """HTMX: Fetch list of pending ghost items."""
    from services.api.context import tenant_context
    tenant_id = tenant_context.get()

    items = []
    if tenant_id:
        with get_db_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, external_id, external_name, source, detected_at
                    FROM triage_items
                    WHERE status = 'pending' AND tenant_id = %s
                    ORDER BY detected_at DESC
                """, (tenant_id,))
                rows = cur.fetchall()
                items = [
                    {
                        "id": str(row[0]),
                        "external_id": row[1],
                        "external_name": row[2],
                        "source": row[3],
                        "detected_at": row[4].strftime("%Y-%m-%d %H:%M")
                    }
                    for row in rows
                ]

    return templates.TemplateResponse("components/triage_list.html", {
        "request": request,
        "items": items
    })

@router.post("/resolve", response_class=HTMLResponse)
async def resolve_item(
    request: Request,
    triage_id: str = Form(...),
    action: str = Form(...)
):
    """HTMX: Resolve a ghost item (Map/Ignore/Create)."""
    from services.api.context import tenant_context
    tenant_id = tenant_context.get()

    if tenant_id:
        with get_db_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                if action == "ignore":
                    cur.execute("""
                        UPDATE triage_items SET status = 'ignored' WHERE id = %s AND tenant_id = %s
                    """, (triage_id, tenant_id))
                # TODO: Implement 'map' and 'create' logic

    # Re-render the list
    return await list_triage_items(request)
