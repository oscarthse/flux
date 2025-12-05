from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/account", tags=["account"])
templates = Jinja2Templates(directory="services/api/templates")

@router.get("/", response_class=HTMLResponse)
async def account_page(request: Request):
    """Render the Account Details page."""
    return templates.TemplateResponse("account.html", {
        "request": request,
        "user_email": getattr(request.state, "user_email", "Unknown"),
        "tenant_name": getattr(request.state, "tenant_name", "Unknown"),
        "user_id": getattr(request.state, "user_id", "Unknown"),
        "tenant_id": getattr(request.state, "tenant_id", "Unknown")
    })
