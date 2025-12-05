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


from services.api.context import tenant_context

@router.get("/forecasts", response_class=HTMLResponse)
async def forecast_dashboard(request: Request):
    """
    Render the main forecasting dashboard.

    Auto-loads data for the first menu item on initial page load.
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

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
    Return forecast data with actual sales comparison and accuracy metrics.

    Returns JSON with:
    - predictions: List of forecasted quantities
    - actuals: List of actual sales (null for future dates)
    - metrics: WMAPE, accuracy %, grade
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        today = date.today()

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Get forecasts (past 30 days + future 30 days)
                cur.execute("""
                    SELECT
                        f.forecast_date,
                        f.predicted_quantity,
                        mi.name
                    FROM forecasts f
                    JOIN menu_items mi ON f.menu_item_id = mi.id
                    WHERE f.menu_item_id = %s
                      AND f.tenant_id = %s
                      AND f.forecast_date >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY f.forecast_date
                """, (menu_item_id, tenant_id))

                forecast_data = cur.fetchall()

                # Get actual sales (past 60 days to ensure coverage)
                cur.execute("""
                    SELECT
                        DATE(so.timestamp) as sale_date,
                        SUM(oli.quantity) as actual_quantity
                    FROM sales_orders so
                    JOIN order_line_items oli ON so.id = oli.order_id
                    WHERE oli.menu_item_id = %s
                      AND so.tenant_id = %s
                      AND so.timestamp >= CURRENT_DATE - INTERVAL '60 days'
                    GROUP BY DATE(so.timestamp)
                    ORDER BY sale_date
                """, (menu_item_id, tenant_id))

                actual_sales = {row[0]: float(row[1]) for row in cur.fetchall()}

        if not forecast_data:
            return JSONResponse({
                "status": "empty",
                "message": "No forecast data available"
            })

        # Build aligned data structures
        dates = []
        predictions = []
        actuals = []

        # For WMAPE calculation (only overlapping past dates)
        wmape_pairs = []

        menu_name = forecast_data[0][2]

        for forecast_date, predicted_qty, _ in forecast_data:
            date_str = str(forecast_date)
            dates.append(date_str)
            pred_val = float(predicted_qty)
            predictions.append(pred_val)

            # Add actual if it exists and date is in the past
            if forecast_date <= today and forecast_date in actual_sales:
                actual_val = actual_sales[forecast_date]
                actuals.append(actual_val)

                # Track for WMAPE calculation
                wmape_pairs.append((actual_val, pred_val))
            else:
                # Future date or no actual data
                actuals.append(None)

        # Calculate WMAPE and metrics
        metrics = _calculate_accuracy_metrics(wmape_pairs)

        return JSONResponse({
            "status": "success",
            "data": {
                "dates": dates,
                "predictions": predictions,
                "actuals": actuals,
                "menu_name": menu_name,
                "total_points": len(dates),
                "metrics": metrics
            }
        })

    except Exception as e:
        logger.error(f"Data fetch failed: {e}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": "Failed to load forecast data"
        }, status_code=500)


def _calculate_accuracy_metrics(pairs: list) -> dict:
    """
    Calculate WMAPE and accuracy grade from (actual, predicted) pairs.

    Returns dict with wmape, accuracy, grade, bias.
    """
    if not pairs or len(pairs) == 0:
        return {
            "wmape": None,
            "accuracy": None,
            "grade": "N/A",
            "bias": None,
            "sample_size": 0
        }

    total_actual = sum(actual for actual, _ in pairs)
    total_error = sum(abs(actual - pred) for actual, pred in pairs)
    total_pred = sum(pred for _, pred in pairs)

    # Handle division by zero
    if total_actual == 0:
        return {
            "wmape": None,
            "accuracy": None,
            "grade": "N/A",
            "bias": None,
            "sample_size": len(pairs)
        }

    # WMAPE = Sum(|Actual - Predicted|) / Sum(Actual)
    wmape = total_error / total_actual
    accuracy = max(0.0, (1.0 - wmape) * 100.0)  # Convert to percentage

    # Bias = (Sum(Predicted) - Sum(Actual)) / Sum(Actual)
    bias = (total_pred - total_actual) / total_actual * 100.0

    # Determine grade
    if wmape < 0.10:
        grade = "A"
    elif wmape < 0.20:
        grade = "B"
    elif wmape < 0.30:
        grade = "C"
    else:
        grade = "D"

    return {
        "wmape": round(wmape, 3),
        "accuracy": round(accuracy, 1),
        "grade": grade,
        "bias": round(bias, 1),
        "sample_size": len(pairs)
    }





@router.get("/forecast-table")
async def forecast_table(request: Request, menu_item_id: str = Query(...)):
    """
    Generate HTML table fragment for forecast details.
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

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
    tenant_id = tenant_context.get()
    if not tenant_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

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


# ==================== Menu Engineering Matrix ====================

@router.get("/menu-matrix", response_class=HTMLResponse)
async def menu_matrix_dashboard(request: Request, period: str = Query("30")):
    """
    Render the Menu Engineering Matrix dashboard (Kasavana & Smith).

    Provides menu profitability analysis with classification into:
    - Stars (High Margin, High Volume)
    - Plowhorses (Low Margin, High Volume)
    - Puzzles (High Margin, Low Volume)
    - Dogs (Low Margin, Low Volume)
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        period_days = int(period)

        return templates.TemplateResponse("analytics/menu_matrix.html", {
            "request": request,
            "period": period_days
        })

    except Exception as e:
        logger.error(f"Menu matrix dashboard failed: {e}", exc_info=True)
        raise internal_error("Failed to load menu matrix", {"error": str(e)})


@router.get("/menu-matrix-data")
async def get_menu_matrix_data(
    request: Request,
    period: int = Query(30),
    sort_by: str = Query("margin", regex="^(margin|volume|name|classification)$")
):
    """
    Get menu performance data for the matrix visualization.

    Returns classified menu items with COGS, margins, and strategic insights.
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            from services.worker.engines.menu_analytics import calculate_menu_performance

            items, portfolio_metrics = calculate_menu_performance(tenant_id, period, conn)

        # Sort items
        if sort_by == "margin":
            items.sort(key=lambda x: x.unit_margin, reverse=True)
        elif sort_by == "volume":
            items.sort(key=lambda x: x.sales_volume, reverse=True)
        elif sort_by == "name":
            items.sort(key=lambda x: x.item_name)
        elif sort_by == "classification":
            # Sort by classification priority: Star > Plowhorse > Puzzle > Dog
            class_order = {"Star": 0, "Plowhorse": 1, "Puzzle": 2, "Dog": 3}
            items.sort(key=lambda x: class_order.get(x.classification, 4))

        return JSONResponse({
            "status": "success",
            "data": {
                "items": [item.to_dict() for item in items],
                "portfolio": portfolio_metrics
            }
        })

    except Exception as e:
        logger.error(f"Menu matrix data fetch failed: {e}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": "Failed to calculate menu performance"
        }, status_code=500)
