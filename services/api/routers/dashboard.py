from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from services.api.database import db_service
from services.api.config import get_settings, settings
from services.api.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory="services/api/templates")

from services.api.context import tenant_context

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    Render the main dashboard with comprehensive metrics.
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # 1. Model Accuracy (WMAPE)
                cur.execute("""
                    WITH daily_sales AS (
                        SELECT
                            oli.menu_item_id,
                            DATE(so.timestamp) as sale_date,
                            SUM(oli.quantity) as actual_qty
                        FROM sales_orders so
                        JOIN order_line_items oli ON so.id = oli.order_id
                        WHERE so.tenant_id = %s
                          AND so.timestamp >= NOW() - INTERVAL '30 days'
                        GROUP BY oli.menu_item_id, DATE(so.timestamp)
                    ),
                    comparison AS (
                        SELECT
                            f.predicted_quantity as forecast,
                            COALESCE(ds.actual_qty, 0) as actual
                        FROM forecasts f
                        LEFT JOIN daily_sales ds
                            ON f.menu_item_id = ds.menu_item_id
                            AND f.forecast_date = ds.sale_date
                        WHERE f.tenant_id = %s
                          AND f.forecast_date >= CURRENT_DATE - INTERVAL '30 days'
                          AND f.forecast_date < CURRENT_DATE
                    )
                    SELECT
                        SUM(ABS(forecast - actual)) as total_error,
                        SUM(actual) as total_actual
                    FROM comparison
                """, (tenant_id, tenant_id))

                error_row = cur.fetchone()
                total_error = float(error_row[0] or 0)
                total_actual = float(error_row[1] or 0)

                if total_actual == 0:
                    accuracy = 100.0
                else:
                    wmape = total_error / total_actual
                    accuracy = max(0.0, (1.0 - wmape) * 100.0)

                # 2. Low Stock Alerts & Financial Impact
                cur.execute("""
                    WITH future_demand AS (
                        SELECT
                            menu_item_id,
                            SUM(predicted_quantity) as total_predicted_qty
                        FROM forecasts
                        WHERE tenant_id = %s
                          AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
                        GROUP BY menu_item_id
                    ),
                    ingredient_demand AS (
                        SELECT
                            r.ingredient_id,
                            SUM(fd.total_predicted_qty * r.quantity) as required_qty
                        FROM future_demand fd
                        JOIN recipes r ON fd.menu_item_id = r.menu_item_id AND r.tenant_id = %s
                        GROUP BY r.ingredient_id
                    ),
                    current_stock AS (
                        SELECT
                            ingredient_id,
                            SUM(remaining_quantity) as total_stock
                        FROM inventory_batches
                        WHERE tenant_id = %s
                        GROUP BY ingredient_id
                    )
                    SELECT
                        COUNT(DISTINCT id.ingredient_id) as low_stock_count,
                        SUM(
                            CASE
                                WHEN COALESCE(cs.total_stock, 0) < id.required_qty THEN
                                    (id.required_qty - COALESCE(cs.total_stock, 0)) * i.cost_per_unit
                                ELSE 0
                            END
                        ) as financial_impact
                    FROM ingredient_demand id
                    LEFT JOIN current_stock cs ON id.ingredient_id = cs.ingredient_id
                    JOIN ingredients i ON id.ingredient_id = i.id AND i.tenant_id = %s
                    WHERE COALESCE(cs.total_stock, 0) < id.required_qty
                """, (tenant_id, tenant_id, tenant_id, tenant_id))

                stock_row = cur.fetchone()
                low_stock_count = stock_row[0] or 0
                financial_impact = float(stock_row[1] or 0)

                # 3. Revenue Forecast (Next 7 Days)
                # Use the start of the forecast period to handle cases where data might be in the past/future relative to system time
                cur.execute("""
                    WITH forecast_start AS (
                        SELECT MIN(forecast_date) as start_date
                        FROM forecasts
                        WHERE tenant_id = %s
                    )
                    SELECT COALESCE(SUM(f.predicted_quantity * mi.price), 0)
                    FROM forecasts f
                    JOIN menu_items mi ON f.menu_item_id = mi.id AND mi.tenant_id = %s
                    CROSS JOIN forecast_start fs
                    WHERE f.tenant_id = %s
                      AND f.forecast_date >= fs.start_date
                      AND f.forecast_date < fs.start_date + INTERVAL '7 days'
                """, (tenant_id, tenant_id, tenant_id))
                revenue_forecast = float(cur.fetchone()[0] or 0)

                # 4. Draft Orders & Estimated Savings (Value of Draft POs)
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT po.id),
                        COALESCE(SUM(poli.quantity * poli.unit_price), 0)
                    FROM purchase_orders po
                    JOIN po_line_items poli ON po.id = poli.po_id
                    WHERE po.tenant_id = %s
                      AND po.status = 'draft'
                """, (tenant_id,))

                po_row = cur.fetchone()
                draft_orders_count = po_row[0] or 0
                draft_po_value = float(po_row[1] or 0)

                # 5. Total Menu Items (for link text)
                cur.execute("SELECT COUNT(*) FROM menu_items WHERE tenant_id = %s", (tenant_id,))
                items_count = cur.fetchone()[0]

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "greeting": "Good evening", # TODO: Dynamic greeting based on time
            "restaurant_name": "Flux Restaurant", # TODO: Dynamic name from settings
            "items_count": items_count,
            "stats": {
                "model_accuracy": f"{round(accuracy, 1)}%",
                "low_stock_count": low_stock_count,
                "financial_impact": f"${financial_impact:,.2f}",
                "items_forecasted": f"{revenue_forecast:,.0f}", # Using this for Revenue card
                "draft_orders": draft_orders_count,
                "estimated_savings": f"${draft_po_value:,.2f}"
            }
        })

    except Exception as e:
        logger.error(f"Dashboard render failed: {e}", exc_info=True)
        return HTMLResponse(f"""
            <div class="text-center py-12">
                <p class="text-rose-600 font-medium text-sm">Failed to load dashboard: {str(e)}</p>
            </div>
        """, status_code=500)


@router.get("/metrics-chart", response_class=HTMLResponse)
async def get_dashboard_chart(request: Request):
    """
    Return HTML fragment for the dashboard trend chart.
    Renders a Plotly chart of aggregated daily forecast demand.
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Aggregate predicted quantity by date for the next 7 days
                # Use the start of the forecast period to match the revenue metric
                cur.execute("""
                    WITH forecast_start AS (
                        SELECT MIN(forecast_date) as start_date
                        FROM forecasts
                        WHERE tenant_id = %s
                    )
                    SELECT
                        f.forecast_date,
                        SUM(f.predicted_quantity) as total_qty
                    FROM forecasts f
                    CROSS JOIN forecast_start fs
                    WHERE f.tenant_id = %s
                      AND f.forecast_date >= fs.start_date
                      AND f.forecast_date <= fs.start_date + INTERVAL '7 days'
                    GROUP BY f.forecast_date
                    ORDER BY f.forecast_date
                """, (tenant_id, tenant_id))

                rows = cur.fetchall()

        if not rows:
            return HTMLResponse("""
                <div class="flex items-center justify-center h-full text-slate-400">
                    <p class="text-sm">No forecast data available for chart</p>
                </div>
            """)

        dates = [row[0].strftime("%Y-%m-%d") for row in rows]
        quantities = [float(row[1]) for row in rows]

        # Generate unique ID for chart container to avoid conflicts
        chart_id = "dashboard-trend-chart"

        # Return HTML with script to render Plotly chart
        # Note: We assume Plotly is loaded in base.html or we load it here if needed.
        # Ideally base.html has <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        return HTMLResponse(f"""
            <div id="{chart_id}" class="w-full h-full"></div>
            <script>
                (function() {{
                    var data = [{{
                        x: {dates},
                        y: {quantities},
                        type: 'scatter',
                        mode: 'lines+markers',
                        line: {{shape: 'spline', color: '#2563eb', width: 3}},
                        marker: {{size: 6, color: '#2563eb'}},
                        fill: 'tozeroy',
                        fillcolor: 'rgba(37, 99, 235, 0.1)'
                    }}];

                    var layout = {{
                        margin: {{t: 10, r: 10, b: 30, l: 40}},
                        showlegend: false,
                        xaxis: {{
                            showgrid: false,
                            zeroline: false,
                            tickformat: '%b %d'
                        }},
                        yaxis: {{
                            showgrid: true,
                            gridcolor: '#f1f5f9',
                            zeroline: false
                        }},
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        autosize: true
                    }};

                    var config = {{responsive: true, displayModeBar: false}};

                    Plotly.newPlot('{chart_id}', data, layout, config);
                }})();
            </script>
        """)

    except Exception as e:
        logger.error(f"Chart generation failed: {e}", exc_info=True)
        return HTMLResponse("""
            <div class="flex items-center justify-center h-full text-rose-500">
                <p class="text-sm">Failed to load chart</p>
            </div>
        """)


@router.get("/stats")
async def get_dashboard_stats(request: Request, settings=Depends(get_settings)):
    """
    Get high-level dashboard statistics using real-time data.

    Metrics:
    1. Model Accuracy (WMAPE): Weighted Mean Absolute Percentage Error over last 30 days.
    2. Low Stock Alerts: Ingredients where current stock < predicted demand (next 7 days).
    3. Financial Impact: Cost to replenish the low stock ingredients.
    """
    tenant_id = tenant_context.get()
    if not tenant_id:
        return {"error": "Not authenticated"}

    with db_service.get_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # 1. Model Accuracy (WMAPE)
            # Formula: 1 - (Sum|Forecast - Actual| / Sum Actual)
            # We use COALESCE to handle missing data points (e.g. forecast exists but no sales, or vice versa)
            cur.execute("""
                WITH daily_sales AS (
                    SELECT
                        oli.menu_item_id,
                        DATE(so.timestamp) as sale_date,
                        SUM(oli.quantity) as actual_qty
                    FROM sales_orders so
                    JOIN order_line_items oli ON so.id = oli.order_id
                    WHERE so.tenant_id = %s
                      AND so.timestamp >= NOW() - INTERVAL '30 days'
                    GROUP BY oli.menu_item_id, DATE(so.timestamp)
                ),
                comparison AS (
                    SELECT
                        f.predicted_quantity as forecast,
                        COALESCE(ds.actual_qty, 0) as actual
                    FROM forecasts f
                    LEFT JOIN daily_sales ds
                        ON f.menu_item_id = ds.menu_item_id
                        AND f.forecast_date = ds.sale_date
                    WHERE f.tenant_id = %s
                      AND f.forecast_date >= CURRENT_DATE - INTERVAL '30 days'
                      AND f.forecast_date < CURRENT_DATE
                )
                SELECT
                    SUM(ABS(forecast - actual)) as total_error,
                    SUM(actual) as total_actual
                FROM comparison
            """, (tenant_id, tenant_id))

            error_row = cur.fetchone()
            total_error = error_row[0] or 0
            total_actual = error_row[1] or 0

            if total_actual == 0:
                # No actual sales to compare against, default to 100% if we have forecasts,
                # or maybe 0? Let's stick to 100% as "no error observed"
                accuracy = 100.0
            else:
                wmape = total_error / total_actual
                # Accuracy can be negative if error > actual (e.g. massive over-forecast), clamp to 0
                accuracy = max(0.0, (1.0 - wmape) * 100.0)

            # 2. Low Stock Alerts & Financial Impact
            # Logic: Forecast (next 7 days) -> Recipe Explosion -> Compare with Inventory
            cur.execute("""
                WITH future_demand AS (
                    SELECT
                        menu_item_id,
                        SUM(predicted_quantity) as total_predicted_qty
                    FROM forecasts
                    WHERE tenant_id = %s
                      AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
                    GROUP BY menu_item_id
                ),
                ingredient_demand AS (
                    SELECT
                        r.ingredient_id,
                        SUM(fd.total_predicted_qty * r.quantity) as required_qty
                    FROM future_demand fd
                    JOIN recipes r ON fd.menu_item_id = r.menu_item_id AND r.tenant_id = %s
                    GROUP BY r.ingredient_id
                ),
                current_stock AS (
                    SELECT
                        ingredient_id,
                        SUM(remaining_quantity) as total_stock
                    FROM inventory_batches
                    WHERE tenant_id = %s
                    GROUP BY ingredient_id
                )
                SELECT
                    COUNT(DISTINCT id.ingredient_id) as low_stock_count,
                    SUM(
                        CASE
                            WHEN COALESCE(cs.total_stock, 0) < id.required_qty THEN
                                (id.required_qty - COALESCE(cs.total_stock, 0)) * i.cost_per_unit
                            ELSE 0
                        END
                    ) as financial_impact
                FROM ingredient_demand id
                LEFT JOIN current_stock cs ON id.ingredient_id = cs.ingredient_id
                JOIN ingredients i ON id.ingredient_id = i.id AND i.tenant_id = %s
                WHERE COALESCE(cs.total_stock, 0) < id.required_qty
            """, (tenant_id, tenant_id, tenant_id, tenant_id))

            stock_row = cur.fetchone()
            low_stock_count = stock_row[0] or 0
            financial_impact = stock_row[1] or 0.0

            return {
                "model_accuracy": round(accuracy, 1),
                "low_stock_alerts": low_stock_count,
                "financial_impact": round(financial_impact, 2)
            }
