"""
Inventory management API router.

Handles Smart Order dashboard and purchase order optimization.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

from services.api.config import settings
from services.api.database import db_service
from services.api.logging_config import get_logger
from services.api.exceptions import DatabaseError, internal_error, not_found

logger = get_logger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="services/api/templates")

# --- Pydantic Models for UI ---
class InventoryItem(BaseModel):
    id: str
    name: str
    category: str
    unit: str
    cost_per_unit: float
    current_stock: float
    burn_rate: float # Avg daily usage
    days_on_hand: float # Days until runout
    health_status: str # 'healthy', 'warning', 'critical', 'dormant'
    usage_explanation: str
    revenue_risk: float

class LineItem(BaseModel):
    ingredient_name: str
    quantity: float
    unit_price: float
    total: float
    reason: str

class PurchaseOrder(BaseModel):
    id: str
    status: str
    created_at: datetime
    delivery_date: datetime
    total_value: float
    line_items: List[LineItem]

class InventoryOverview(BaseModel):
    inventory: List[InventoryItem]
    purchase_orders: List[PurchaseOrder]
    total_draft_value: float
    total_items_to_order: int

# --- Helper Functions ---

def get_inventory_data(tenant_id: str, conn) -> List[InventoryItem]:
    """Fetch inventory using the unified engine logic."""
    from services.worker.engines.inventory import calculate_inventory_health

    health_data = calculate_inventory_health(tenant_id, conn)

    inventory_list = []
    for item in health_data:
        inventory_list.append(InventoryItem(
            id=item.ingredient_id,
            name=item.name,
            category="General", # Placeholder until we add category to engine
            unit="kg", # Placeholder
            cost_per_unit=item.cost_per_unit,
            current_stock=item.current_stock,
            burn_rate=item.burn_rate,
            days_on_hand=item.days_until_runout,
            health_status=item.status,
            # Add new fields for UI explanation
            usage_explanation=item.usage_explanation,
            revenue_risk=item.revenue_risk
        ))

    return sorted(inventory_list, key=lambda x: x.health_status == 'critical', reverse=True)

def get_draft_orders(tenant_id: str, conn) -> List[PurchaseOrder]:
    """Fetch draft purchase orders with line items and REAL runout reasoning."""
    from services.worker.engines.inventory import calculate_inventory_health
    from datetime import date

    # Get fresh inventory health data for accurate reasoning
    health_data = calculate_inventory_health(tenant_id, conn)
    health_by_ingredient = {item.ingredient_id: item for item in health_data}

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, status, created_at, delivery_date
            FROM purchase_orders
            WHERE tenant_id = %s AND status = 'draft'
            ORDER BY created_at DESC
        """, (tenant_id,))

        pos = []
        rows = cur.fetchall()

        for row in rows:
            po_id, status, created_at, delivery_date = row

            # Fetch Lines with ingredient IDs
            cur.execute("""
                SELECT i.name, pli.ingredient_id, pli.quantity, pli.unit_price
                FROM po_line_items pli
                JOIN ingredients i ON pli.ingredient_id = i.id
                WHERE pli.po_id = %s
            """, (po_id,))

            lines = []
            po_total = 0.0

            for l_row in cur.fetchall():
                name, ing_id, qty, price = l_row
                qty = float(qty)
                price = float(price)
                total = qty * price
                po_total += total

                # REAL Reasoning from inventory health data - EXACT match with revenue risk
                health = health_by_ingredient.get(ing_id)
                if health and health.runout_date:
                    days = health.days_until_runout

                    # Use EXACT same wording as revenue risk breakdown (no dates to avoid confusion)
                    if days < 1:
                        reason = f"⚠️ Runs out in {days:.1f} days"
                    elif days < 3:
                        reason = f"⚠️ Only {days:.1f} days left"
                    else:
                        reason = f"⏰ {days:.1f} days left"
                else:
                    reason = "Safety stock replenishment"

                lines.append(LineItem(
                    ingredient_name=name,
                    quantity=qty,
                    unit_price=price,
                    total=total,
                    reason=reason
                ))

            pos.append(PurchaseOrder(
                id=po_id,
                status=status,
                created_at=created_at,
                delivery_date=delivery_date,
                total_value=po_total,
                line_items=lines
            ))

        return pos

# --- Endpoints ---

@router.get("/smart-order")
async def redirect_smart_order():
    """Redirect legacy URL to new dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/inventory/")

@router.get("/", response_class=HTMLResponse)
async def inventory_dashboard(request: Request):
    """Render the main Inventory ERP Dashboard."""
    from services.api.context import tenant_context
    tenant_id = tenant_context.get()
    if not tenant_id:
        return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            inventory = get_inventory_data(tenant_id, conn)
            orders = get_draft_orders(tenant_id, conn)

            total_val = sum(o.total_value for o in orders)
            total_items = sum(len(o.line_items) for o in orders)

            # Calculate REAL revenue risk with explainability
            total_revenue_risk = 0.0
            risk_breakdown = []
            for item in inventory:
                if item.revenue_risk > 0:
                    total_revenue_risk += item.revenue_risk
                    risk_breakdown.append({
                        "name": item.name,
                        "risk": item.revenue_risk,
                        "days_on_hand": item.days_on_hand,
                        "explanation": item.usage_explanation
                    })

            # Sort by risk descending
            risk_breakdown = sorted(risk_breakdown, key=lambda x: x["risk"], reverse=True)

            return templates.TemplateResponse("inventory/main.html", {
                "request": request,
                "inventory": inventory,
                "purchase_orders": orders,
                "total_draft_value": total_val,
                "total_items_to_order": total_items,
                "draft_orders_count": len(orders),
                "total_revenue_risk": total_revenue_risk,
                "risk_breakdown": risk_breakdown
            })

    except Exception as e:
        logger.error(f"Failed to load inventory dashboard: {e}", exc_info=True)
        raise internal_error("Failed to load dashboard")

@router.post("/generate")
async def trigger_optimization(request: Request):
    """Run optimization and return updated PO list (HTMX)."""
    from services.api.context import tenant_context
    tenant_id = tenant_context.get()
    if not tenant_id:
        return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            # Run Engine
            from services.worker.engines.inventory import generate_draft_orders as run_engine
            run_engine(tenant_id, conn)

            # Fetch Updated Orders
            orders = get_draft_orders(tenant_id, conn)

            return templates.TemplateResponse("components/po_list.html", {
                "request": request,
                "purchase_orders": orders
            })

    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        raise internal_error("Optimization failed")

@router.post("/orders/{po_id}/approve")
async def approve_order(request: Request, po_id: str):
    """Approve PO and return updated list."""
    from services.api.context import tenant_context
    tenant_id = tenant_context.get()
    if not tenant_id:
        return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE purchase_orders
                    SET status = 'ordered'
                    WHERE id = %s AND tenant_id = %s
                """, (po_id, tenant_id))
            conn.commit()

            orders = get_draft_orders(tenant_id, conn)

            return templates.TemplateResponse("components/po_list.html", {
                "request": request,
                "purchase_orders": orders
            })

    except Exception as e:
        logger.error(f"Approval failed: {e}", exc_info=True)
        raise internal_error("Failed to approve order")
