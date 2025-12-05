"""
Flux Platform API - Main application entry point.
"""
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import dramatiq
from dramatiq.brokers.redis import RedisBroker

from services.api.routers import triage, analytics, inventory, dashboard, staff, auth, ingestion, debug, account
from services.api.logging_config import setup_logging, get_logger
from services.api.database import db_service
from services.api.config import settings
from fastapi.templating import Jinja2Templates

logger = get_logger(__name__)
templates = Jinja2Templates(directory="services/api/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles initialization and cleanup.
    """
    # Startup
    try:
        setup_logging()
        # Ensure DB pool is ready (optional, but good for fail-fast check)
        # db_service._ensure_pool()
    except Exception as e:
        print(f"Startup Error: {e}")
        # We don't raise here so the app can still start and return 500s

    yield

    # Shutdown
    try:
        db_service.close_all_connections()
    except Exception as e:
        print(f"Shutdown Error: {e}")


app = FastAPI(
    title="Flux Platform API",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="services/api/static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(inventory.router)
app.include_router(staff.router)
app.include_router(ingestion.router)
app.include_router(debug.router)
app.include_router(account.router)

from services.api import security
from services.api.context import tenant_context

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Public routes
    if request.url.path in ["/", "/technology", "/health"] or \
       request.url.path.startswith("/auth") or \
       request.url.path.startswith("/static"):
        return await call_next(request)

    # Check session
    session_token = request.cookies.get("flux_session")
    if not session_token:
        # Redirect to login if accessing protected route without session
        return RedirectResponse(url="/auth/login")

    try:
        # Verify and decode signed cookie
        payload = security.verify_session_cookie(session_token)
        logger.info(f"Middleware DEBUG - Decoded payload: {payload}")

        tenant_id = payload.get("tenant_id")
        logger.info(f"Middleware DEBUG - Extracted tenant_id: {tenant_id}")

        if not tenant_id:
            logger.error("Auth Middleware: Missing tenant_id in session payload")
            raise Exception("Missing tenant_id in session")

        # Set ContextVar for RLS (DatabaseService will pick this up)
        token = tenant_context.set(tenant_id)
        logger.info(f"Middleware DEBUG - Set tenant_context to: {tenant_id}")

        # Fetch User and Tenant details for UI
        try:
            from services.api.database import db_service
            with db_service.get_connection(tenant_id=tenant_id) as conn:
                with conn.cursor() as cur:
                    # Get User Email
                    user_id = payload.get("user_id")
                    cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
                    user_row = cur.fetchone()
                    request.state.user_email = user_row[0] if user_row else "Unknown User"
                    request.state.user_id = user_id

                    # Get Tenant Name
                    cur.execute("SELECT name FROM tenants WHERE id = %s", (tenant_id,))
                    tenant_row = cur.fetchone()
                    request.state.tenant_name = tenant_row[0] if tenant_row else "Unknown Restaurant"
                    request.state.tenant_id = tenant_id
        except Exception as e:
            logger.error(f"Failed to fetch user details: {e}")
            request.state.user_email = "User"
            request.state.tenant_name = "Restaurant"

        try:
            response = await call_next(request)
            return response
        finally:
            # Reset context after request
            tenant_context.reset(token)

    except Exception as e:
        # Invalid signature or expired
        logger.error(f"Auth Middleware Error: {e}")
        return RedirectResponse(url="/auth/login")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve Landing Page or Redirect to Dashboard."""
    if request.cookies.get("user_session"):
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/technology", response_class=HTMLResponse)
async def technology(request: Request):
    """Serve Technology Deep Dive Page."""
    return templates.TemplateResponse("technology.html", {"request": request})

# Setup Dramatiq Broker
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
broker = RedisBroker(url=redis_url)
dramatiq.set_broker(broker)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "api"}

@app.post("/webhooks/{source}")
async def receive_webhook(source: str, request: Request):
    """
    Ingest webhook from POS (Square, Toast).
    Enqueues task to worker.
    """
    payload = await request.json()

    # TODO: Extract tenant_id from auth/header. For now, using a placeholder or payload.
    # In a real scenario, this comes from the API Key or JWT.
    tenant_id = request.headers.get("X-Tenant-ID")

    if not tenant_id:
        return JSONResponse(status_code=400, content={"error": "Missing X-Tenant-ID header"})

    # Import task here to avoid circular imports if using shared lib,
    # or use task name string if configured.
    from services.worker.tasks import ingest_pos_data

    ingest_pos_data.send(tenant_id, source, payload)

    return JSONResponse(status_code=202, content={"status": "accepted", "queue": "ingest"})
