"""
Analytics API router.

Handles forecasting dashboard and charts.
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from datetime import date, timedelta

from services.api.config import settings
from services.api.database import db_service
from services.api.logging_config import get_logger
from services.api.exceptions import DatabaseError, internal_error

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])
templates = Jinja2Templates(directory="services/api/templates")

@router.get("/forecasts", response_class=HTMLResponse)
async def forecast_dashboard(request: Request):
    """
    Render the Forecasting Dashboard with menu items dropdown.

    Returns:
        HTML page with menu items for forecast selection

    Raises:
        HTTPException: 500 if database error occurs
    """
    tenant_id = settings.DEFAULT_TENANT_ID
    logger.info(f"Loading Forecasting dashboard for tenant {tenant_id}")

    try:
        with db_service.get_cursor(tenant_id=tenant_id) as cur:
            cur.execute(
                "SELECT id, name FROM menu_items WHERE tenant_id = %s ORDER BY name",
                (tenant_id,)
            )
            menu_items = [{"id": str(row[0]), "name": row[1]} for row in cur.fetchall()]

        logger.info(f"Loaded {len(menu_items)} menu items")
        return templates.TemplateResponse("forecasts.html", {
            "request": request,
            "menu_items": menu_items,
            "tenant_name": "Demo Tenant"
        })

    except DatabaseError as e:
        logger.error(f"Database error loading menu items: {e}")
        raise internal_error("Failed to load menu items", details=e.details)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise internal_error("An unexpected error occurred")

@router.get("/forecast-chart", response_class=HTMLResponse)
async def forecast_chart(request: Request, item_selector: str):
    """HTMX: Render the chart for a specific item."""
    tenant_id = request.headers.get("X-Tenant-ID")

    dates = []
    actuals = []
    predictions = []
    upper_bound = []
    lower_bound = []
    item_name = "Unknown Item"

    if tenant_id and item_selector:
        with get_db_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Get Item Name
                cur.execute("SELECT name FROM menu_items WHERE id = %s", (item_selector,))
                row = cur.fetchone()
                if row:
                    item_name = row[0]

                # Fetch Data (Last 30 days + Next 7 days)
                start_date = date.today() - timedelta(days=30)
                end_date = date.today() + timedelta(days=7)

                # 1. Actuals
                cur.execute("""
                    SELECT so.timestamp::date, SUM(oli.quantity)
                    FROM order_line_items oli
                    JOIN sales_orders so ON oli.order_id = so.id
                    WHERE oli.tenant_id = %s AND oli.menu_item_id = %s
                      AND so.timestamp >= %s
                    GROUP BY 1 ORDER BY 1
                """, (tenant_id, item_selector, start_date))
                actual_map = {row[0]: float(row[1]) for row in cur.fetchall()}

                # 2. Forecasts
                cur.execute("""
                    SELECT forecast_date, predicted_quantity, confidence_interval_lower, confidence_interval_upper
                    FROM forecasts
                    WHERE tenant_id = %s AND menu_item_id = %s
                      AND forecast_date >= %s AND forecast_date <= %s
                    ORDER BY forecast_date
                """, (tenant_id, item_selector, start_date, end_date))
                forecast_rows = cur.fetchall()
                forecast_map = {row[0]: (float(row[1]), float(row[2]), float(row[3])) for row in forecast_rows}

                # Merge Data
                current = start_date
                while current <= end_date:
                    dates.append(current.strftime("%Y-%m-%d"))
                    actuals.append(actual_map.get(current, None)) # None for gaps/future

                    fc = forecast_map.get(current)
                    if fc:
                        predictions.append(fc[0])
                        lower_bound.append(fc[1])
                        upper_bound.append(fc[2])
                    else:
                        predictions.append(None)
                        lower_bound.append(None)
                        upper_bound.append(None)

                    current += timedelta(days=1)

    return templates.TemplateResponse("components/forecast_chart.html", {
        "request": request,
        "dates": dates,
        "actuals": actuals,
        "predictions": predictions,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "item_name": item_name
    })
