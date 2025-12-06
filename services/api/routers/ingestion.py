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
import uuid

logger = get_logger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
templates = Jinja2Templates(directory="services/api/templates")

@router.get("/hub", response_class=HTMLResponse)
async def data_hub_page(request: Request):
    """Main Data Hub Interface"""
    return templates.TemplateResponse("data_hub.html", {"request": request})

@router.get("/upload", response_class=HTMLResponse)
async def upload_page_legacy(request: Request):
    """Redirect legacy upload URL to new Hub"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ingestion/hub")

# --- DATA HUB API ---

@router.get("/api/stats")
async def get_hub_stats(request: Request):
    """Returns overview stats HTML snippet with sleek monochrome styling"""
    tenant_id = tenant_context.get()
    if not tenant_id: return HTMLResponse("<div>Error</div>")

    stats = []
    with db_service.get_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            tables = [
                ("ingredients", "Ingredients"),
                ("menu_items", "Menu Items"),
                ("recipes", "Recipes"),
                ("sales_orders", "Sales Orders")
            ]
            for tbl, name in tables:
                cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE tenant_id = %s", (tenant_id,))
                count = cur.fetchone()[0]
                stats.append({"name": name, "count": count})

    html = '<div class="grid grid-cols-1 md:grid-cols-4 gap-6">'
    for s in stats:
        html += f"""
        <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 hover:border-slate-300 transition-colors">
            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">{s['name']}</p>
            <p class="mt-2 text-3xl font-bold text-slate-900">{s['count']:,}</p>
        </div>
        """
    html += '</div>'
    return HTMLResponse(html)

@router.get("/api/table/filters")
async def get_table_filters(request: Request, table: str):
    """Returns filter options HTML for the specific table"""
    tenant_id = tenant_context.get()
    options = []

    with db_service.get_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            if table == "ingredients":
                cur.execute("SELECT DISTINCT category FROM ingredients WHERE tenant_id = %s ORDER BY 1", (tenant_id,))
                options = [r[0] for r in cur.fetchall() if r[0]]
            elif table == "menu_items":
                cur.execute("SELECT DISTINCT category FROM menu_items WHERE tenant_id = %s ORDER BY 1", (tenant_id,))
                options = [r[0] for r in cur.fetchall() if r[0]]
            # Recipes and Sales don't have good categorical filters yet, maybe Menu Item Name?
            # Keeping it simple for the requested 'filter options'

    html = '<option value="">All Categories</option>'
    for opt in options:
        html += f'<option value="{opt}">{opt}</option>'

    return HTMLResponse(html)

@router.get("/api/table/chart")
async def get_table_chart(request: Request, table: str):
    """Returns a Plotly chart configuration for the selected table"""
    tenant_id = tenant_context.get()

    try:
        data = []
        layout = {"title": "Data Visualization", "height": 300, "margin": {"t": 40, "b": 30, "l": 50, "r": 20}, "font": {"family": "Inter, sans-serif"}}

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:

                if table == "sales_orders":
                    cur.execute("""
                        SELECT date_trunc('day', timestamp) as day, SUM(total_amount)
                        FROM sales_orders WHERE tenant_id = %s
                        GROUP BY 1 ORDER BY 1 LIMIT 30
                    """, (tenant_id,))
                    rows = cur.fetchall()
                    if rows:
                        x = [r[0].isoformat() for r in rows]
                        y = [float(r[1]) for r in rows]
                        data = [{"x": x, "y": y, "type": "scatter", "mode": "lines+markers", "name": "Revenue", "line": {"color": "#111827"}}]
                        layout["title"] = "Revenue Trend (30 Days)"

                elif table == "ingredients":
                    cur.execute("""
                        SELECT category, COUNT(*) FROM ingredients
                        WHERE tenant_id = %s GROUP BY 1 ORDER BY 2 DESC
                    """, (tenant_id,))
                    rows = cur.fetchall()
                    if rows:
                        labels = [r[0] or "Uncategorized" for r in rows]
                        values = [r[1] for r in rows]
                        data = [{"labels": labels, "values": values, "type": "pie", "hole": 0.6, "marker": {"colors": ["#111827", "#374151", "#4B5563", "#6B7280", "#9CA3AF"]}}]
                        layout["title"] = "Ingredient Categories"

                elif table == "menu_items":
                    cur.execute("""
                        SELECT name, price FROM menu_items
                        WHERE tenant_id = %s ORDER BY price DESC LIMIT 10
                    """, (tenant_id,))
                    rows = cur.fetchall()
                    if rows:
                        x = [r[0] for r in rows]
                        y = [float(r[1]) for r in rows]
                        data = [{"x": x, "y": y, "type": "bar", "marker": {"color": "#111827"}}]
                        layout["title"] = "Top 10 Most Expensive Items"

        # Unique ID for the chart div to prevent collisions
        chart_id = f"chart_{uuid.uuid4().hex[:8]}"
        import json

        return HTMLResponse(f"""
            <div id="{chart_id}" style="width:100%; height:320px;"></div>
            <script>
                (function() {{
                    var data = {json.dumps(data)};
                    var layout = {json.dumps(layout)};
                    Plotly.newPlot('{chart_id}', data, layout, {{responsive: true, displayModeBar: false}});
                }})();
            </script>
        """)

    except Exception as e:
        logger.error(f"Chart generation failed: {e}")
        return HTMLResponse(f"<div class='text-red-500 p-4'>Could not generate chart: {str(e)}</div>")

@router.get("/api/table/view")
async def view_table_data(request: Request, table: str, search: str = "", filter_category: str = ""):
    """Returns HTML table rows with filtering, column masking, and JOINs"""
    tenant_id = tenant_context.get()

    # Define Column Mappings (DisplayName -> DB Column) and Queries
    # This replaces SELECT * to strictly control output

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:

                query = ""
                params = [tenant_id]
                columns = [] # (Header, DB Column)

                if table == "ingredients":
                    columns = [("Name", "name"), ("Category", "category"), ("Cost", "cost_per_unit"), ("Unit", "unit"), ("Par", "par_level")]
                    query = "SELECT name, category, cost_per_unit, unit, par_level FROM ingredients WHERE tenant_id = %s"
                    if filter_category:
                        query += " AND category = %s"
                        params.append(filter_category)
                    if search:
                        query += " AND name ILIKE %s"
                        params.append(f"%{search}%")

                elif table == "menu_items":
                    columns = [("Name", "name"), ("Category", "category"), ("Price", "price")]
                    query = "SELECT name, category, price FROM menu_items WHERE tenant_id = %s"
                    if filter_category:
                        query += " AND category = %s"
                        params.append(filter_category)
                    if search:
                        query += " AND name ILIKE %s"
                        params.append(f"%{search}%")

                elif table == "recipes":
                    # JOIN to get names!
                    columns = [("Menu Item", "menu_item_name"), ("Ingredient", "ingredient_name"), ("Qty", "quantity")]
                    query = """
                        SELECT m.name as menu_item_name, i.name as ingredient_name, r.quantity
                        FROM recipes r
                        JOIN menu_items m ON r.menu_item_id = m.id
                        JOIN ingredients i ON r.ingredient_id = i.id
                        WHERE r.tenant_id = %s
                    """
                    if search:
                        query += " AND (m.name ILIKE %s OR i.name ILIKE %s)"
                        params.extend([f"%{search}%", f"%{search}%"])

                elif table == "sales_orders":
                    columns = [("Time", "timestamp"), ("Total", "total_amount"), ("Status", "status")]
                    query = "SELECT timestamp, total_amount, status FROM sales_orders WHERE tenant_id = %s"
                    if search:
                        # Search by date string or status
                        query += " AND (status ILIKE %s)"
                        params.append(f"%{search}%")

                else:
                    return HTMLResponse("<div class='p-4 text-red-600'>Invalid table</div>")

                query += " ORDER BY 1 DESC LIMIT 100"

                cur.execute(query, tuple(params))
                rows = cur.fetchall()

                if not rows:
                     return HTMLResponse("<div class='p-12 text-center text-slate-500 italic'>No records found.</div>")

                # Build Table
                thead = "".join(f"<th scope='col' class='px-6 py-3 text-left text-xs font-semibold text-slate-900 uppercase tracking-wider border-b border-slate-200'>{col[0]}</th>" for col in columns)

                tbody = ""
                for row in rows:
                    tbody += "<tr class='bg-white hover:bg-slate-50 transition-colors'>"
                    for i, val in enumerate(row):
                        if isinstance(val, (float, Decimal)):
                            val = f"{val:.2f}"
                        if isinstance(val, datetime):
                            val = val.strftime("%Y-%m-%d %H:%M")
                        if val is None: val = "-"
                        tbody += f"<td class='px-6 py-4 whitespace-nowrap text-sm text-slate-600 border-b border-slate-100'>{val}</td>"
                    tbody += "</tr>"

                return HTMLResponse(f"""
                <div class="overflow-x-auto rounded-lg border border-slate-200">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-gray-50"><tr>{thead}</tr></thead>
                        <tbody class="divide-y divide-slate-100">{tbody}</tbody>
                    </table>
                     <div class="px-6 py-3 bg-white text-xs text-slate-400 border-t border-slate-200 flex justify-between">
                        <span>Showing max 100 results</span>
                        <span>{len(rows)} records</span>
                    </div>
                </div>
                """)

    except Exception as e:
        logger.error(f"Table View Error: {e}")
        return HTMLResponse(f"<div class='text-red-600 p-4'>Error loading table: {e}</div>")

@router.delete("/api/table/truncate")
async def truncate_table(request: Request, table: str):
    """Truncate a specific table"""
    tenant_id = tenant_context.get()
    allowed_tables = ["ingredients", "menu_items", "recipes", "sales_orders"]

    if table not in allowed_tables:
        return HTMLResponse("<div class='text-red-600'>Invalid table</div>")

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Manual Cascade for RLS Safety (Postgres TRUNCATE cannot be scoped by WHERE)
                if table == 'sales_orders':
                    # Delete child line items first
                    cur.execute("DELETE FROM order_line_items WHERE tenant_id = %s", (tenant_id,))
                elif table == 'menu_items':
                    # Delete recipes
                    cur.execute("DELETE FROM recipes WHERE tenant_id = %s", (tenant_id,))
                    # Note: If sales exist, this might still fail on order_line_items if we don't prefer to nuke sales
                    # For Data Hub "Reset", we assume user wants to clear menu, so we check constraints or just fail if sales exist?
                    # Let's try to delete recipes, but let DB fail on sales if they exist to prevent accidental history loss
                    pass
                elif table == 'ingredients':
                    # Delete recipes (that use this ingredient) and inventory
                    cur.execute("DELETE FROM recipes WHERE tenant_id = %s", (tenant_id,))
                    cur.execute("DELETE FROM inventory_batches WHERE tenant_id = %s", (tenant_id,))

                # Perform main delete
                cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))

        # Success: Return empty state targeting the table view
        return HTMLResponse(
            """
            <div class='p-12 text-center flex flex-col items-center justify-center h-full text-slate-500'>
                <svg class="w-12 h-12 text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                <p>Table data cleared successfully.</p>
                <p class='text-xs mt-2 text-slate-400'>Select a table or upload data to continue.</p>
            </div>
            """
        )

    except Exception as e:
        logger.error(f"Truncate failed: {e}")
        return HTMLResponse(f"<div class='p-4 text-red-600 bg-red-50 rounded-lg'>Failed to clear table. <br><span class='text-xs'>{str(e)}</span></div>")

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
    ingredients_file: UploadFile = File(None),
    menu_file: UploadFile = File(None),
    recipes_file: UploadFile = File(None),
    sales_file: UploadFile = File(None)
):
    # Get tenant_id from context (set by auth middleware)
    tenant_id = tenant_context.get()

    if not tenant_id:
        return JSONResponse(status_code=400, content={"error": "Tenant ID missing from session context"})

    errors = []
    total_processed = 0

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:

                # Process Ingredients
                if ingredients_file and ingredients_file.filename:
                    processed_count = 0
                    content = await ingredients_file.read()
                    decoded = content.decode('utf-8')
                    reader = csv.DictReader(io.StringIO(decoded))
                    rows = list(reader)
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
                            errors.append(f"Ingredients row {processed_count+1}: {str(e)}")
                    total_processed += processed_count

                # Process Menu
                if menu_file and menu_file.filename:
                    processed_count = 0
                    content = await menu_file.read()
                    decoded = content.decode('utf-8')
                    reader = csv.DictReader(io.StringIO(decoded))
                    rows = list(reader)
                    for row in rows:
                        try:
                            data = MenuRow(**row)
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
                            errors.append(f"Menu row {processed_count+1}: {str(e)}")
                    total_processed += processed_count

                # Process Recipes
                if recipes_file and recipes_file.filename:
                    processed_count = 0
                    content = await recipes_file.read()
                    decoded = content.decode('utf-8')
                    reader = csv.DictReader(io.StringIO(decoded))
                    rows = list(reader)
                    for row in rows:
                        try:
                            data = RecipeRow(**row)
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
                            errors.append(f"Recipes row {processed_count+1}: {str(e)}")
                    total_processed += processed_count

                # Process Sales
                if sales_file and sales_file.filename:
                    processed_count = 0
                    content = await sales_file.read()
                    decoded = content.decode('utf-8')
                    reader = csv.DictReader(io.StringIO(decoded))
                    rows = list(reader)
                    for row in rows:
                        try:
                            data = SalesRow(**row)
                            cur.execute("SELECT id FROM menu_items WHERE tenant_id = %s AND name = %s", (tenant_id, data.menu_item))
                            mi = cur.fetchone()
                            if not mi:
                                errors.append(f"Menu Item not found: {data.menu_item}")
                                continue
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
                            errors.append(f"Sales row {processed_count+1}: {str(e)}")
                    total_processed += processed_count

                    # Trigger Forecasting after sales upload
                    if processed_count > 0:
                        background_tasks.add_task(run_forecasting_job, tenant_id)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return JSONResponse(content={
        "status": "success" if not errors else "partial_success",
        "processed": total_processed,
        "errors": errors
    })
