"""
Analytics API router - Enterprise Edition.

Handles forecasting dashboard and chart generation with proper HTMX integration.
"""
from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import date, timedelta
import json

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
    Render the main forecasting dashboard.

    Auto-loads data for the first menu item on initial page load.
    """
    try:
        tenant_id = request.headers.get("X-Tenant-ID", settings.DEFAULT_TENANT_ID)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Get menu items ordered by name
                cur.execute("""
                    SELECT id, name, category
                    FROM menu_items
                    WHERE tenant_id = %s
                    ORDER BY name
                """, (tenant_id,))
                menu_items = [
                    {"id": row[0], "name": row[1], "category": row[2] or "Other"}
                    for row in cur.fetchall()
                ]

                # Get forecast summary stats
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT menu_item_id) as items_with_forecasts,
                        COUNT(*) as total_forecasts,
                        MIN(forecast_date) as earliest_date,
                        MAX(forecast_date) as latest_date
                    FROM forecasts
                    WHERE tenant_id = %s
                """, (tenant_id,))

                stats = cur.fetchone()
                forecast_stats = {
                    "items_with_forecasts": stats[0] or 0,
                    "total_forecasts": stats[1] or 0,
                    "date_range": f"{stats[2]} to {stats[3]}" if stats[2] else "No data"
                }

        return templates.TemplateResponse("forecasts.html", {
            "request": request,
            "menu_items": menu_items,
            "forecast_stats": forecast_stats,
            "initial_item_id": menu_items[0]["id"] if menu_items else None,
            "initial_item_name": menu_items[0]["name"] if menu_items else None
        })

    except Exception as e:
        logger.error(f"Dashboard render failed: {e}", exc_info=True)
        raise internal_error("Dashboard load failed", {"error": str(e)})


@router.get("/forecast-data")
async def forecast_data(request: Request, menu_item_id: str = Query(...)):
    """
    Return forecast data as JSON for client-side Plotly rendering.

    This solves the HTMX + Plotly script execution issue by separating
    data from presentation.
    """
    try:
        tenant_id = request.headers.get("X-Tenant-ID", settings.DEFAULT_TENANT_ID)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        f.forecast_date,
                        f.predicted_quantity,
                        mi.name
                    FROM forecasts f
                    JOIN menu_items mi ON f.menu_item_id = mi.id
                    WHERE f.menu_item_id = %s
                      AND f.tenant_id = %s
                    ORDER BY f.forecast_date
                    LIMIT 100
                """, (menu_item_id, tenant_id))

                forecast_data = cur.fetchall()

        if not forecast_data:
            return JSONResponse({
                "status": "empty",
                "message": "No forecast data available"
            })

        # Structure data for Plotly
        dates = [str(row[0]) for row in forecast_data]
        quantities = [float(row[1]) for row in forecast_data]
        menu_name = forecast_data[0][2]

        return JSONResponse({
            "status": "success",
            "data": {
                "dates": dates,
                "quantities": quantities,
                "menu_name": menu_name,
                "total_points": len(dates)
            }
        })

    except Exception as e:
        logger.error(f"Data fetch failed: {e}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": "Failed to load forecast data"
        }, status_code=500)


@router.get("/forecast-table")
async def forecast_table(request: Request, menu_item_id: str = Query(...)):
    """
    Generate HTML table fragment for forecast details.
    """
    try:
        tenant_id = request.headers.get("X-Tenant-ID", settings.DEFAULT_TENANT_ID)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT f.forecast_date, f.predicted_quantity
                    FROM forecasts f
                    WHERE f.menu_item_id = %s AND f.tenant_id = %s
                    ORDER BY f.forecast_date
                    LIMIT 30
                """, (menu_item_id, tenant_id))

                forecast_data = cur.fetchall()

        if not forecast_data:
            return HTMLResponse("""
                <div class="text-center py-12 text-slate-400">
                    <svg class="w-12 h-12 mx-auto mb-3 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"/>
                    </svg>
                    <p class="text-sm font-medium">No forecast data available</p>
                    <p class="text-xs mt-1">Generate forecasts to see predictions</p>
                </div>
            """)

        # Build table rows
        from datetime import datetime
        rows = []
        prev_qty = None

        for forecast_date, qty in forecast_data:
            dt = datetime.combine(forecast_date, datetime.min.time())
            day_name = dt.strftime("%a")
            date_str = forecast_date.strftime("%b %d")
            qty_val = float(qty)

            # Calculate trend
            if prev_qty is not None:
                diff = qty_val - prev_qty
                if abs(diff) < 1:
                    trend = '<span class="text-slate-400">→</span>'
                elif diff > 0:
                    trend = f'<span class="text-emerald-600">↑ {diff:.1f}</span>'
                else:
                    trend = f'<span class="text-rose-600">↓ {abs(diff):.1f}</span>'
            else:
                trend = '<span class="text-slate-300">—</span>'

            is_weekend = day_name in ['Sat', 'Sun']
            row_class = 'bg-blue-50/30' if is_weekend else ''

            rows.append(f"""
                <tr class="{row_class} hover:bg-slate-50">
                    <td class="px-4 py-3 text-sm text-slate-900 font-medium">{date_str}</td>
                    <td class="px-4 py-3 text-xs text-slate-500 font-mono">{day_name}</td>
                    <td class="px-4 py-3 text-sm text-slate-900 font-semibold tabular-nums">{qty_val:.1f}</td>
                    <td class="px-4 py-3 text-sm font-medium">{trend}</td>
                </tr>
            """)
            prev_qty = qty_val

        return HTMLResponse(f"""
            <table class="min-w-full divide-y divide-slate-200">
                <thead class="bg-slate-50 sticky top-0">
                    <tr>
                        <th class="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">Date</th>
                        <th class="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">Day</th>
                        <th class="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">Quantity</th>
                        <th class="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">Trend</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-slate-100">
                    {''.join(rows)}
                </tbody>
            </table>
        """)

    except Exception as e:
        logger.error(f"Table generation failed: {e}", exc_info=True)
        return HTMLResponse("""
            <div class="text-center py-12">
                <p class="text-rose-600 font-medium text-sm">Failed to load data</p>
            </div>
        """)


@router.post("/generate-forecasts")
async def generate_forecasts_endpoint(request: Request):
    """
    Generate forecasts using the configured model.
    """
    params = dict(request.query_params)
    model_name = params.get('model', settings.FORECAST_MODEL)
    tenant_id = request.headers.get("X-Tenant-ID", settings.DEFAULT_TENANT_ID)

    logger.info(f"Generating forecasts for {tenant_id} using {model_name}")

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            from services.worker.engines.forecasting import ForecastingEngine

            engine = ForecastingEngine(tenant_id, conn, model_name=model_name)
            count = engine.generate_forecasts(forecast_days=settings.FORECAST_DAYS)

        logger.info(f"Generated {count} forecasts using {model_name}")

        return HTMLResponse(f"""
            <div class="rounded-lg bg-emerald-50 border border-emerald-200 p-4">
                <div class="flex items-start">
                    <svg class="w-5 h-5 text-emerald-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <div class="ml-3">
                        <p class="text-sm font-medium text-emerald-900">Forecasts Generated</p>
                        <p class="text-xs text-emerald-700 mt-1">Created {count} predictions using {model_name} model</p>
                    </div>
                </div>
            </div>
        """)

    except Exception as e:
        logger.error(f"Forecast generation failed: {e}", exc_info=True)
        return HTMLResponse("""
            <div class="rounded-lg bg-rose-50 border border-rose-200 p-4">
                <div class="flex items-start">
                    <svg class="w-5 h-5 text-rose-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <div class="ml-3">
                        <p class="text-sm font-medium text-rose-900">Generation Failed</p>
                        <p class="text-xs text-rose-700 mt-1">Please try again or contact support</p>
                    </div>
                </div>
            </div>
        """, status_code=500)
