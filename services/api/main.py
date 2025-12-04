"""
Flux Platform API - Main application entry point.
"""
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import dramatiq
from dramatiq.brokers.redis import RedisBroker

from services.api.routers import triage, analytics, inventory
from services.api.logging_config import setup_logging
from services.api.database import db_service
from services.api.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles initialization and cleanup.
    """
    # Startup
    setup_logging()
    yield
    # Shutdown
    db_service.close_all_connections()


app = FastAPI(
    title="Flux Platform API",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="services/api/static"), name="static")

# Include Routers
app.include_router(triage.router)
app.include_router(analytics.router)
app.include_router(inventory.router) # Added this line

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
