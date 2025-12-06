from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account"])
templates = Jinja2Templates(directory="services/api/templates")

@router.get("/", response_class=HTMLResponse)
async def account_page(request: Request):
    """Render the Account Details page."""
    from services.api.database import db_service

    tenant_id = getattr(request.state, "tenant_id", None)
    stats = {"menu_items": 0, "orders": 0, "revenue": 0}
    team = []

    if tenant_id and tenant_id != "Unknown":
        try:
            with db_service.get_connection(tenant_id=tenant_id) as conn:
                with conn.cursor() as cur:
                    # Stats
                    cur.execute("SELECT COUNT(*) FROM menu_items WHERE tenant_id = %s", (tenant_id,))
                    stats["menu_items"] = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM sales_orders WHERE tenant_id = %s", (tenant_id,))
                    stats["orders"] = cur.fetchone()[0]

                    # Team
                    cur.execute("SELECT full_name, email, role FROM users WHERE tenant_id = %s", (tenant_id,))
                    team = [{"name": r[0], "email": r[1], "role": r[2]} for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching account data: {e}")

    return templates.TemplateResponse("account.html", {
        "request": request,
        "user_email": getattr(request.state, "user_email", "Unknown"),
        "tenant_name": getattr(request.state, "tenant_name", "Unknown"),
        "user_id": getattr(request.state, "user_id", "Unknown"),
        "tenant_id": tenant_id,
        "stats": stats,
        "team": team
    })
