"""
Analytics API router.

Handles forecasting dashboard and charts.
"""
from fastapi import APIRouter, Request, Query
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
    try:
        tenant_id = settings.DEFAULT_TENANT_ID
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name
                    FROM menu_items
                    WHERE tenant_id = %s
                    ORDER BY name
                """, (tenant_id,))
                menu_items = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]

        return templates.TemplateResponse("forecasts.html", {
            "request": request,
            "menu_items": menu_items
        })

    except Exception as e:
        logger.error(f"Failed to render forecast dashboard: {e}")
        raise internal_error("Dashboard load failed", {"error": str(e)})


@router.get("/forecast-chart")
async def forecast_chart(request: Request, menu_item_id: str = Query(...)):
    """
    Generate forecast chart for a specific menu item.

    Args:
        menu_item_id: UUID of the menu item

    Returns:
        HTML fragment with Plotly chart

    Raises:
        HTTPException: 500 if database or chart generation fails
    """
    try:
        tenant_id = settings.DEFAULT_TENANT_ID

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Fetch forecast data (all forecasts, not just future)
                cur.execute("""
                    SELECT
                        f.forecast_date,
                        f.predicted_quantity,
                        mi.name as menu_name
                    FROM forecasts f
                    JOIN menu_items mi ON f.menu_item_id = mi.id
                    WHERE f.menu_item_id = %s
                      AND f.tenant_id = %s
                    ORDER BY f.forecast_date
                    LIMIT 100
                """, (menu_item_id, tenant_id))

                forecast_data = cur.fetchall()

        if not forecast_data:
            return HTMLResponse(f"""
                <div class="p-4 bg-yellow-100 rounded">
                    <p class="text-yellow-800">No forecast data found for this item.</p>
                    <p class="text-sm text-yellow-600 mt-2">Click "Generate Forecasts" to create predictions.</p>
                </div>
            """)

        # Prepare chart data
        dates = [str(row[0]) for row in forecast_data]
        quantities = [float(row[1]) for row in forecast_data]
        menu_name = forecast_data[0][2]

        # Generate Plotly chart
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=quantities,
            mode='lines+markers',
            name='Predicted Demand',
            line=dict(color='#3B82F6', width=2),
            marker=dict(size=6)
        ))

        fig.update_layout(
            title=f"Forecast: {menu_name}",
            xaxis_title="Date",
            yaxis_title="Predicted Quantity",
            hovermode='x unified',
            height=400
        )

        chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

        return HTMLResponse(chart_html)

    except Exception as e:
        logger.error(f"Chart generation failed: {e}", exc_info=True)
        raise internal_error(
            "Chart generation failed",
            detail={
                "message": "Chart generation failed",
                "details": {"error": str(e)}
            }
        )


@router.post("/generate-forecasts", response_class=HTMLResponse)
async def generate_forecasts_endpoint(request: Request):
    """
    Generate demand forecasts from historical sales data.

    Uses configured forecasting model (Prophet or moving average)
    to analyze sales history and predict future demand.

    Query Parameters:
        model: Optional override for forecast model ('prophet' or 'moving_average')

    Returns:
        HTML fragment showing forecast summary

    Raises:
        HTTPException: 500 if generation fails
    """
    # Get model from query params or use default from settings
    params = dict(request.query_params)
    model_name = params.get('model', settings.FORECAST_MODEL)

    tenant_id = settings.DEFAULT_TENANT_ID
    logger.info(f"Generating forecasts for tenant {tenant_id} using {model_name}")

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            from services.worker.engines.forecasting import ForecastingEngine

            engine = ForecastingEngine(tenant_id, conn, model_name=model_name)
            count = engine.generate_forecasts(forecast_days=settings.FORECAST_DAYS)

        logger.info(f"Successfully generated {count} forecasts using {model_name}")

        return HTMLResponse(f"""
            <div class="alert alert-success p-4 mb-4 bg-green-100 border border-green-400 rounded" role="alert">
                <h4 class="font-bold text-green-800">✅ Forecasts Generated!</h4>
                <p class="text-green-700">Created <strong>{count}</strong> forecasts using <code>{model_name}</code> model.</p>
                <p class="text-sm text-green-600 mt-2">Select a menu item above to view predictions.</p>
            </div>
        """)

    except ValueError as e:
        # Invalid model name
        logger.error(f"Invalid model selection: {e}")
        raise internal_error(
            f"Invalid model: {model_name}",
            {"available_models": "prophet, moving_average"}
        )

    except Exception as e:
        logger.error(f"Forecast generation failed: {e}", exc_info=True)
        raise internal_error(
            "Forecast generation failed",
            {"error": str(e), "model": model_name}
        )
