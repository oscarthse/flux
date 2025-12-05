"""
Menu Item Master View Router.

Provides a central registry for all menu items and detailed audit panels.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

from services.api.config import settings
from services.api.database import db_service
from services.api.logging_config import get_logger
from services.api.context import tenant_context
from services.worker.engines.inventory import calculate_inventory_health

logger = get_logger(__name__)

router = APIRouter(prefix="/menu", tags=["menu"])
templates = Jinja2Templates(directory="services/api/templates")

# --- Pydantic Models ---

class IngredientAudit(BaseModel):
    id: str
    name: str
    quantity_needed: float
    unit: str
    current_stock: float
    stock_health_status: str # 'healthy', 'warning', 'critical'
    days_left: float
    cost: float

class MenuDetailView(BaseModel):
    id: str
    name: str
    price: float
    category: str

    # Sales Stats (L30D)
    total_units_sold: int
    total_revenue: float
    peak_day: str

    # Audit
    ingredients: List[IngredientAudit]

    # Profitability
    total_cost: float
    margin_percent: float

# --- Routes ---

@router.get("/", response_class=HTMLResponse)
async def menu_registry_page(request: Request):
    """
    Render the Menu Registry page (Master-Detail layout).
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Fetch Master List
                cur.execute("""
                    SELECT id, name, category, price
                    FROM menu_items
                    WHERE tenant_id = %s
                    ORDER BY name
                """, (tenant_id,))

                menu_items = [
                    {"id": row[0], "name": row[1], "category": row[2] or "General", "price": float(row[3] or 0)}
                    for row in cur.fetchall()
                ]

        return templates.TemplateResponse("menu_registry.html", {
            "request": request,
            "menu_items": menu_items
        })

    except Exception as e:
        logger.error(f"Menu registry load failed: {e}", exc_info=True)
        return HTMLResponse("Failed to load menu registry", status_code=500)


@router.get("/{menu_item_id}", response_class=HTMLResponse)
async def get_menu_details(request: Request, menu_item_id: str):
    """
    HTMX Endpoint: Returns the detailed audit panel for a specific menu item.
    """
    try:
        tenant_id = tenant_context.get()
        if not tenant_id:
            return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # 1. Fetch Basic Info
                cur.execute("""
                    SELECT name, price, category
                    FROM menu_items
                    WHERE id = %s AND tenant_id = %s
                """, (menu_item_id, tenant_id))
                item_row = cur.fetchone()

                if not item_row:
                    return HTMLResponse("<div class='p-4'>Item not found</div>", status_code=404)

                name, price, category = item_row
                price = float(price or 0)

                # 2. Fetch Sales Stats (L30D)
                cur.execute("""
                    SELECT
                        SUM(oli.quantity),
                        SUM(oli.quantity * oli.price_at_order),
                        TO_CHAR(so.timestamp, 'Day') as day_name
                    FROM order_line_items oli
                    JOIN sales_orders so ON oli.order_id = so.id
                    WHERE oli.menu_item_id = %s
                      AND so.tenant_id = %s
                      AND so.timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY day_name
                    ORDER BY SUM(oli.quantity) DESC
                    LIMIT 1
                """, (menu_item_id, tenant_id))

                sales_row = cur.fetchone()

                # If no sales, run a simpler query for totals
                if not sales_row:
                    total_units = 0
                    total_revenue = 0.0
                    peak_day = "N/A"
                else:
                    # We need total units/revenue across ALL days, the previous query grouped by day
                    # Let's run a separate simple total query
                    cur.execute("""
                        SELECT SUM(oli.quantity), SUM(oli.quantity * oli.price_at_order)
                        FROM order_line_items oli
                        JOIN sales_orders so ON oli.order_id = so.id
                        WHERE oli.menu_item_id = %s
                          AND so.tenant_id = %s
                          AND so.timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    """, (menu_item_id, tenant_id))
                    totals = cur.fetchone()
                    total_units = int(totals[0] or 0)
                    total_revenue = float(totals[1] or 0)
                    peak_day = sales_row[2].strip()

                # 3. Fetch Recipe & Ingredients
                cur.execute("""
                    SELECT
                        r.ingredient_id,
                        i.name,
                        r.quantity,
                        i.unit,
                        i.cost_per_unit
                    FROM recipes r
                    JOIN ingredients i ON r.ingredient_id = i.id
                    WHERE r.menu_item_id = %s AND i.tenant_id = %s
                """, (menu_item_id, tenant_id))

                recipe_rows = cur.fetchall()

                ingredient_ids = [row[0] for row in recipe_rows]
                recipe_map = {row[0]: {'qty': float(row[2]), 'unit': row[3], 'cost': float(row[4])} for row in recipe_rows}

            # 4. Calculate Inventory Health (Filtered)
            # This uses the optimized engine logic
            health_data = []
            if ingredient_ids:
                health_data = calculate_inventory_health(tenant_id, conn, ingredient_ids=ingredient_ids)

            # 5. Assemble Audit Data
            ingredients_audit = []
            total_cost = 0.0

            # Map health data back to recipe
            health_map = {h.ingredient_id: h for h in health_data}

            for ing_id, r_data in recipe_map.items():
                health = health_map.get(ing_id)

                # Cost calculation
                cost_for_item = r_data['cost'] * r_data['qty']
                total_cost += cost_for_item

                ingredients_audit.append(IngredientAudit(
                    id=ing_id,
                    name=health.name if health else "Unknown",
                    quantity_needed=r_data['qty'],
                    unit=r_data['unit'],
                    current_stock=health.current_stock if health else 0,
                    stock_health_status=health.status if health else "unknown",
                    days_left=health.days_until_runout if health else 0,
                    cost=r_data['cost']
                ))

            margin_percent = ((price - total_cost) / price * 100) if price > 0 else 0

            view_model = MenuDetailView(
                id=menu_item_id,
                name=name,
                price=price,
                category=category or "General",
                total_units_sold=total_units,
                total_revenue=total_revenue,
                peak_day=peak_day,
                ingredients=ingredients_audit,
                total_cost=total_cost,
                margin_percent=margin_percent
            )

        return templates.TemplateResponse("menu/detail_panel.html", {
            "request": request,
            "item": view_model
        })

    except Exception as e:
        logger.error(f"Menu detail load failed: {e}", exc_info=True)
        return HTMLResponse(f"<div class='p-4 text-red-600'>Error loading details: {str(e)}</div>", status_code=500)
