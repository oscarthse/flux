from fastapi import APIRouter, UploadFile, File, Request, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from services.api.database import db_service
from services.api.logging_config import get_logger
from services.api.schemas.ingestion import IngredientRow, MenuRow, RecipeRow, SalesRow
from services.worker.engines import ingestion as ingestion_engine
import csv
import io
from decimal import Decimal
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
templates = Jinja2Templates(directory="services/api/templates")

@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("csv_import.html", {"request": request})

from services.api.context import tenant_context

from datetime import date, timedelta

from fastapi import BackgroundTasks

def run_forecasting_job(tenant_id: str):
    """Helper to run forecasting in background with its own DB connection"""
    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            # Use the engine to generate forecasts for next 7 days
            from services.worker.engines.forecasting import ForecastingEngine
            engine = ForecastingEngine(tenant_id, conn, model_name='moving_average')
            engine.generate_forecasts(forecast_days=7)
        logger.info(f"Background forecasting completed for tenant {tenant_id}")
    except Exception as e:
        logger.error(f"Background forecasting failed: {e}")

@router.post("/upload")
async def handle_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    type: str = Form(...)
):
    # Get tenant_id from context (set by auth middleware)
    tenant_id = tenant_context.get()

    if not tenant_id:
        return JSONResponse(status_code=400, content={"error": "Tenant ID missing from session context"})

    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))

    rows = list(reader)
    errors = []
    processed_count = 0

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:

                if type == "ingredients":
                    for row in rows:
                        try:
                            data = IngredientRow(**row)
                            # Upsert Ingredient
                            cur.execute("""
                                INSERT INTO ingredients (tenant_id, name, cost_per_unit, unit, par_level, reorder_threshold, lead_time_days, shelf_life_days)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (tenant_id, name) DO UPDATE SET
                                    cost_per_unit = EXCLUDED.cost_per_unit,
                                    unit = EXCLUDED.unit,
                                    par_level = EXCLUDED.par_level,
                                    reorder_threshold = EXCLUDED.reorder_threshold,
                                    lead_time_days = EXCLUDED.lead_time_days,
                                    shelf_life_days = EXCLUDED.shelf_life_days
                                RETURNING id
                            """, (tenant_id, data.name, data.cost_per_unit, data.unit, data.par_level, data.reorder_threshold, data.lead_time_days, data.shelf_life_days))

                            ing_id = cur.fetchone()[0]

                            # DEMO MAGIC: Seed Initial Inventory if empty
                            # Check if we have any stock
                            cur.execute("SELECT COUNT(*) FROM inventory_batches WHERE tenant_id = %s AND ingredient_id = %s AND remaining_quantity > 0", (tenant_id, ing_id))
                            has_stock = cur.fetchone()[0] > 0

                            if not has_stock:
                                cur.execute("""
                                    INSERT INTO inventory_batches (tenant_id, ingredient_id, quantity, remaining_quantity, cost_per_unit, received_at, expires_at)
                                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW() + INTERVAL '30 days')
                                """, (tenant_id, ing_id, data.par_level, data.par_level, data.cost_per_unit))

                            processed_count += 1
                        except Exception as e:
                            errors.append(f"Row {processed_count+1}: {str(e)}")

                elif type == "menu":
                    for row in rows:
                        try:
                            data = MenuRow(**row)
                            # Use name as external_id for CSV imports to prevent duplicates
                            cur.execute("""
                                INSERT INTO menu_items (tenant_id, external_id, name, category, price)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (tenant_id, external_id) DO UPDATE SET
                                    price = EXCLUDED.price,
                                    category = EXCLUDED.category,
                                    name = EXCLUDED.name
                            """, (tenant_id, data.name, data.name, data.category, data.price))
                            processed_count += 1
                        except Exception as e:
                            errors.append(f"Row {processed_count+1}: {str(e)}")

                elif type == "recipes":
                    # Wipe and Replace Strategy for Recipes
                    # But only for items in the CSV? Or all recipes?
                    # Safer to just insert/update.
                    # Schema: PK (tenant_id, menu_item_id, ingredient_id)

                    for row in rows:
                        try:
                            data = RecipeRow(**row)

                            # Resolve IDs
                            cur.execute("SELECT id FROM menu_items WHERE tenant_id = %s AND name = %s", (tenant_id, data.menu_item))
                            mi = cur.fetchone()
                            if not mi:
                                errors.append(f"Menu Item not found: {data.menu_item}")
                                continue

                            cur.execute("SELECT id FROM ingredients WHERE tenant_id = %s AND name = %s", (tenant_id, data.ingredient))
                            ing = cur.fetchone()
                            if not ing:
                                errors.append(f"Ingredient not found: {data.ingredient}")
                                continue

                            cur.execute("""
                                INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (tenant_id, menu_item_id, ingredient_id) DO UPDATE SET
                                    quantity = EXCLUDED.quantity
                            """, (tenant_id, mi[0], ing[0], data.quantity))
                            processed_count += 1
                        except Exception as e:
                            errors.append(f"Row {processed_count+1}: {str(e)}")

                elif type == "sales":
                    for row in rows:
                        try:
                            data = SalesRow(**row)

                            # Resolve Menu Item
                            cur.execute("SELECT id FROM menu_items WHERE tenant_id = %s AND name = %s", (tenant_id, data.menu_item))
                            mi = cur.fetchone()
                            if not mi:
                                errors.append(f"Menu Item not found: {data.menu_item}")
                                continue

                            # Insert Historical Sale
                            cur.execute("""
                                INSERT INTO sales_orders (tenant_id, timestamp, total_amount, status)
                                VALUES (%s, %s, 0, 'completed')
                                RETURNING id
                            """, (tenant_id, data.date))
                            order_id = cur.fetchone()[0]

                            cur.execute("""
                                INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
                                VALUES (%s, %s, %s, %s, 0)
                            """, (tenant_id, order_id, mi[0], data.quantity))

                            processed_count += 1
                        except Exception as e:
                            errors.append(f"Row {processed_count+1}: {str(e)}")

                    # DEMO MAGIC: Trigger Forecasting after sales upload
                    # Generate forecasts for next 7 days in background
                    if processed_count > 0:
                        background_tasks.add_task(run_forecasting_job, tenant_id)


    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return JSONResponse(content={
        "status": "success" if not errors else "partial_success",
        "processed": processed_count,
        "errors": errors
    })
