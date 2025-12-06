from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
import io
import json
import asyncio
import os
import redis.asyncio as redis
from datetime import datetime

from services.api.database import db_service
from services.api.context import tenant_context
from synthetic_data_engine.layers.weather import WeatherGenerator

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
templates = Jinja2Templates(directory="services/api/templates")
logger = logging.getLogger(__name__)

# Redis Connection for Streaming
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- View Endpoints ---

@router.get("/", response_class=HTMLResponse)
async def get_onboarding_page(request: Request):
    """Serves the single-page 'Mise en Place' onboarding experience."""
    return templates.TemplateResponse("onboarding.html", {"request": request})

# --- State & Status Endpoints ---

@router.get("/api/status")
@router.get("/api/status")
async def get_onboarding_status():
    """
    Checks the persistence state of the onboarding process.
    Returns which steps are completed based on database row counts.
    """
    tenant_id = tenant_context.get()
    if not tenant_id:
        # Should be caught by middleware, but safe fallback
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    status = {
        "ingredients": False,
        "menu": False,
        "recipes": False,
        "sales": False
    }

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Check Ingredients (via inventory_batches as proxy for ingredients existence if no specialized table)
                # However, prompt implies 'ingredients' table. Let's assume standard schema.

                # 1. Ingredients
                # Check if table exists to avoid crash on partial migration
                cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ingredients')")
                if cur.fetchone()[0]:
                    cur.execute("SELECT COUNT(*) FROM ingredients WHERE tenant_id = %s", (tenant_id,))
                    if cur.fetchone()[0] > 0:
                         status["ingredients"] = True

                # 2. Menu Items
                cur.execute("SELECT COUNT(*) FROM menu_items WHERE tenant_id = %s", (tenant_id,))
                if cur.fetchone()[0] > 0:
                    status["menu"] = True

                # 3. Recipes
                cur.execute("SELECT COUNT(*) FROM recipes WHERE tenant_id = %s", (tenant_id,))
                if cur.fetchone()[0] > 0:
                    status["recipes"] = True

                # 4. Sales Logs
                cur.execute("SELECT COUNT(*) FROM sales_orders WHERE tenant_id = %s", (tenant_id,))
                if cur.fetchone()[0] > 0:
                    status["sales"] = True

        return JSONResponse(content=status)

    except Exception as e:
        logger.error(f"Status Check Error: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to check status"})

# --- Streaming Endpoint ---

@router.get("/api/stream")
@router.get("/api/stream")
async def stream_discovery_logs(request: Request):
    """
    SSE Endpoint for Discovery Logs.
    Subscribes to Redis channel 'onboarding:logs:{tenant_id}'.
    """
    tenant_id = tenant_context.get()
    if not tenant_id:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    async def event_generator():
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        channel = f"onboarding:logs:{tenant_id}"
        await pubsub.subscribe(channel)

        try:
            # Send initial connection message
            yield f"data: Connected to Discovery Stream for {tenant_id}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    # Format as SSE
                    data = message["data"]
                    yield f"data: {data}\n\n"

                # Keep-alive / yield control
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Stream Error: {e}")
            yield f"data: Error: {str(e)}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await redis_client.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Validation Helper ---

def apply_mapping(df: pd.DataFrame, mapping_str: Optional[str]) -> pd.DataFrame:
    """Applies column mapping from JSON string to DataFrame."""
    if not mapping_str:
        return df

    try:
        mapping = json.loads(mapping_str)
        # Invert mapping? Usually mapping is { "UsersCol": "OurCol" } or { "OurCol": "UsersCol" }
        # Requirement: The Map (mapping={"unit_cost": "Cost", ...}) -> This looks like { "our_key": "user_header" }
        # We need to rename UserHeader to OurKey for validation.
        # So we construct rename dict: { "Cost": "unit_cost" }

        rename_dict = {v: k for k, v in mapping.items()}
        df = df.rename(columns=rename_dict)
        return df
    except Exception as e:
        logger.warning(f"Failed to parse mapping: {e}")
        return df

@router.get("/api/weather")
async def check_weather_availability(city: str):
    """Checks weather data availability (Synthetic)."""
    if not city or len(city) < 3:
        return JSONResponse(content={"available": False, "message": "Invalid city name."}, status_code=400)

    known_cities = ["barcelona", "madrid", "london", "new york", "paris", "berlin", "tokyo"]
    if city.lower() in known_cities:
         return JSONResponse(content={
             "available": True,
             "message": f"Weather impact analysis enabled for {city.title()}."
         })

    return JSONResponse(content={
        "available": False,
        "message": f"Note: Weather impact analysis is currently unavailable for {city.title()}."
    })

@router.post("/api/validate/ingredients")
async def validate_ingredients(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None)
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        df = apply_mapping(df, mapping)

        required_columns = {"name", "cost_per_unit", "unit", "par_level"}
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            return JSONResponse(status_code=400, content={"valid": False, "error": f"Missing required columns: {', '.join(missing)}"})

        if (df['cost_per_unit'] < 0).any():
             return JSONResponse(status_code=400, content={"valid": False, "error": "Found negative costs."})

        return JSONResponse(content={"valid": True, "count": len(df)})
    except Exception as e:
        return JSONResponse(status_code=400, content={"valid": False, "error": str(e)})

@router.post("/api/validate/menu")
async def validate_menu(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None)
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        df = apply_mapping(df, mapping)

        required_columns = {"name", "price"}
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
             return JSONResponse(status_code=400, content={"valid": False, "error": f"Missing required columns: {', '.join(missing)}"})

        if (df['price'] < 0).any():
             return JSONResponse(status_code=400, content={"valid": False, "error": "Prices cannot be negative."})

        return JSONResponse(content={"valid": True, "count": len(df)})
    except Exception as e:
        return JSONResponse(status_code=400, content={"valid": False, "error": str(e)})

@router.post("/api/validate/recipes")
async def validate_recipes(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None)
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        df = apply_mapping(df, mapping)

        required_columns = {"menu_item", "ingredient", "quantity"}
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
             return JSONResponse(status_code=400, content={"valid": False, "error": f"Missing required columns: {', '.join(missing)}"})

        return JSONResponse(content={"valid": True, "count": len(df)})
    except Exception as e:
        return JSONResponse(status_code=400, content={"valid": False, "error": str(e)})

@router.post("/api/validate/sales")
async def validate_sales(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None)
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        df = apply_mapping(df, mapping)

        required_columns = {"date", "menu_item", "quantity"}
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
             return JSONResponse(status_code=400, content={"valid": False, "error": f"Missing required columns: {', '.join(missing)}"})

        try:
            df['date'] = pd.to_datetime(df['date'])
        except Exception:
             return JSONResponse(status_code=400, content={"valid": False, "error": "Invalid date format."})

        min_date = df['date'].min()
        max_date = df['date'].max()
        if (max_date - min_date).days < 7:
            return JSONResponse(status_code=400, content={"valid": False, "error": "Minimum 7 days history required."})

        return JSONResponse(content={"valid": True, "count": len(df), "days": (max_date - min_date).days})
    except Exception as e:
        return JSONResponse(status_code=400, content={"valid": False, "error": str(e)})
