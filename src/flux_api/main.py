from fastapi import FastAPI
from .routers import analytics

app = FastAPI(
    title="Flux API",
    description="AI-Powered Restaurant Analytics Platform",
    version="0.1.0"
)

app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}
