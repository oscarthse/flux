"""
Inventory management API router.

Handles Smart Order dashboard and purchase order optimization.
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from services.api.config import settings
from services.api.database import db_service
from services.api.logging_config import get_logger
from services.api.exceptions import DatabaseError, internal_error, not_found

logger = get_logger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="services/api/templates")

@router.get("/smart-order", response_class=HTMLResponse)
async def smart_order_dashboard(request: Request):
    """
    Render the Smart Order dashboard with purchase orders.

    Returns:
        HTML page with list of purchase orders and line items

    Raises:
        HTTPException: 500 if database error occurs
    """
    tenant_id = settings.DEFAULT_TENANT_ID
    logger.info(f"Loading Smart Order dashboard for tenant {tenant_id}")

    try:
        with db_service.get_cursor(tenant_id=tenant_id) as cur:
            # Fetch POs
            cur.execute("""
                SELECT id, status, created_at, delivery_date
                FROM purchase_orders
                WHERE tenant_id = %s
                ORDER BY created_at DESC
            """, (tenant_id,))

            pos = []
            for row in cur.fetchall():
                pos.append({
                    "id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                    "delivery_date": row[3],
                    "line_items": []
                })

            # Organize POs with line items
            purchase_orders = []
            for po in pos:
                cur.execute("""
                    SELECT i.name, pli.quantity, pli.unit_price
                    FROM po_line_items pli
                    JOIN ingredients i ON pli.ingredient_id = i.id
                    WHERE pli.po_id = %s
                """, (po["id"],))

                po["line_items"] = [
                    {"ingredient": row[0], "quantity": row[1], "unit_price": row[2]}
                    for row in cur.fetchall()
                ]
                purchase_orders.append(po)

        return templates.TemplateResponse("smart_order.html", {
            "request": request
        })

    except Exception as e:
        logger.error(f"Dashboard rendering failed: {e}", exc_info=True)
        raise internal_error("Dashboard load failed", {"error": str(e)})


@router.get("/smart-order-list", response_class=HTMLResponse)
async def smart_order_list(request: Request):
    """
    Return HTML fragment of purchase orders for HTMX loading.
    """
    tenant_id = settings.DEFAULT_TENANT_ID

    try:
        with db_service.get_cursor(tenant_id=tenant_id) as cur:
            cur.execute("""
                SELECT id, status, created_at, delivery_date
                FROM purchase_orders
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                LIMIT 50
            """, (tenant_id,))

            pos = cur.fetchall()

            if not pos:
                return HTMLResponse("""
                    <div class="text-center py-12">
                        <svg class="w-16 h-16 mx-auto text-slate-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                        </svg>
                        <p class="text-slate-600 font-medium">No Purchase Orders</p>
                        <p class="text-sm text-slate-400 mt-2">Generate orders to see recommendations</p>
                    </div>
                """)

            # Build PO cards HTML
            cards_html = []
            for po_id, status, created_at, delivery_date in pos:
                # Fetch line items
                cur.execute("""
                    SELECT i.name, pli.quantity, pli.unit_price
                    FROM po_line_items pli
                    JOIN ingredients i ON pli.ingredient_id = i.id
                    WHERE pli.po_id = %s
                    ORDER BY i.name
                """, (po_id,))

                line_items = cur.fetchall()
                total = sum(float(qty) * float(price) for _, qty, price in line_items)

                status_class = {
                    'DRAFT': 'bg-amber-100 text-amber-800',
                    'APPROVED': 'bg-emerald-100 text-emerald-800',
                    'SENT': 'bg-blue-100 text-blue-800'
                }.get(status, 'bg-slate-100 text-slate-800')

                # Build line items table
                lines_html = ''.join([
                    f"""
                    <tr class="hover:bg-slate-50">
                        <td class="px-4 py-3 text-sm text-slate-900">{name}</td>
                        <td class="px-4 py-3 text-sm text-slate-600 text-right tabular-nums">{float(qty):.2f}</td>
                        <td class="px-4 py-3 text-sm text-slate-600 text-right tabular-nums">${float(price):.2f}</td>
                        <td class="px-4 py-3 text-sm font-semibold text-slate-900 text-right tabular-nums">${float(qty) * float(price):.2f}</td>
                    </tr>
                    """
                    for name, qty, price in line_items
                ])

                cards_html.append(f"""
                    <div class="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
                        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                            <div>
                                <div class="flex items-center space-x-3">
                                    <h3 class="text-lg font-semibold text-slate-900">PO #{str(po_id)[:8]}</h3>
                                    <span class="px-2.5 py-1 text-xs font-semibold rounded-full {status_class}">{status}</span>
                                </div>
                                <p class="text-xs text-slate-500 mt-1">Created {created_at.strftime('%b %d, %Y')} • Delivery {delivery_date.strftime('%b %d, %Y')}</p>
                            </div>
                            <div class="text-right">
                                <p class="text-2xl font-bold text-slate-900">${total:.2f}</p>
                                <p class="text-xs text-slate-500">{len(line_items)} items</p>
                            </div>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-slate-200">
                                <thead class="bg-slate-50">
                                    <tr>
                                        <th class="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Ingredient</th>
                                        <th class="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase">Qty</th>
                                        <th class="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase">Unit Price</th>
                                        <th class="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase">Total</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-slate-100">
                                    {lines_html}
                                </tbody>
                            </table>
                        </div>
                        <div class="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-end">
                            <button
                                hx-post="/inventory/orders/{po_id}/approve"
                                hx-target="#po-list"
                                hx-swap="innerHTML"
                                class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors">
                                Approve Order
                            </button>
                        </div>
                    </div>
                """)

            return HTMLResponse(''.join(cards_html))

    except Exception as e:
        logger.error(f"PO list generation failed: {e}", exc_info=True)
        return HTMLResponse("""
            <div class="text-center py-12">
                <p class="text-rose-600 font-medium">Failed to load purchase orders</p>
            </div>
        """)


@router.post("/orders/{po_id}/approve")
async def approve_order(request: Request, po_id: str):
    """
    Approve a draft purchase order.

    Args:
        po_id: Purchase order ID to approve

    Returns:
        HTML fragment with updated purchase order list

    Raises:
        HTTPException: 404 if PO not found, 500 if database error
    """
    tenant_id = settings.DEFAULT_TENANT_ID
    logger.info(f"Approving purchase order {po_id} for tenant {tenant_id}")

    try:
        with db_service.get_cursor(tenant_id=tenant_id) as cur:
            cur.execute("""
                UPDATE purchase_orders
                SET status = 'ordered'
                WHERE id = %s AND tenant_id = %s
            """, (po_id, tenant_id))

        # Fetch updated POs for HTMX partial update
        with db_service.get_cursor(tenant_id=tenant_id) as cur:
            cur.execute("""
                SELECT id, status, created_at, delivery_date
                FROM purchase_orders
                WHERE tenant_id = %s
                ORDER BY created_at DESC
            """, (tenant_id,))

            pos = []
            for row in cur.fetchall():
                pos.append({
                    "id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                    "delivery_date": row[3],
                    "line_items": []
                })

            # Fetch Line Items for each PO
            for po in pos:
                cur.execute("""
                    SELECT i.name, pli.quantity, pli.unit_price
                    FROM po_line_items pli
                    JOIN ingredients i ON pli.ingredient_id = i.id
                    WHERE pli.po_id = %s
                """, (po["id"],))
                po["line_items"] = [
                    {
                        "ingredient_name": r[0],
                        "quantity": float(r[1]),
                        "unit_price": float(r[2])
                    }
                    for r in cur.fetchall()
                ]

        logger.info(f"Purchase order {po_id} approved successfully")
        return templates.TemplateResponse("components/po_list.html", {
            "request": request,
            "purchase_orders": pos
        })

    except DatabaseError as e:
        logger.error(f"Database error approving order: {e}")
        raise internal_error("Failed to approve purchase order", details=e.details)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise internal_error("An unexpected error occurred")

@router.post("/generate")
async def trigger_optimization(request: Request):
    """
    Run inventory optimization and generate draft purchase orders.

    Returns:
        HTML fragment with updated purchase order list

    Raises:
        HTTPException: 500 if optimization fails
    """
    tenant_id = settings.DEFAULT_TENANT_ID
    logger.info(f"Starting inventory optimization for tenant {tenant_id}")

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Insert test data if not exists (for prototype)
                cur.execute("""
                    INSERT INTO menu_items (id, tenant_id, name, price)
                    VALUES ('88888888-8888-8888-8888-888888888888', %s, 'Wagyu Burger', 25.00)
                    ON CONFLICT (id) DO NOTHING
                """, (tenant_id,))

                cur.execute("""
                    INSERT INTO ingredients (id, tenant_id, name, unit, cost_per_unit)
                    VALUES
                        ('11111111-1111-1111-1111-111111111111', %s, 'Premium Wagyu Beef', 'kg', 50.00),
                        ('22222222-2222-2222-2222-222222222222', %s, 'Test Flour', 'kg', 10.00)
                    ON CONFLICT (tenant_id, name) DO NOTHING
                """, (tenant_id, tenant_id))

                conn.commit()

                # Run the inventory optimization engine
                from services.worker.engines.inventory import generate_draft_orders as run_inventory
                run_inventory(tenant_id, conn)

                logger.info("Inventory optimization completed successfully")

        # Fetch updated purchase orders
        with db_service.get_cursor(tenant_id=tenant_id) as cur:
            cur.execute("""
                SELECT id, status, created_at, delivery_date
                FROM purchase_orders
                WHERE tenant_id = %s
                ORDER BY created_at DESC
            """, (tenant_id,))

            pos = []
            for row in cur.fetchall():
                pos.append({
                    "id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                    "delivery_date": row[3],
                    "line_items": []
                })

            # Fetch Line Items for each PO
            for po in pos:
                cur.execute("""
                    SELECT i.name, pli.quantity, pli.unit_price
                    FROM po_line_items pli
                    JOIN ingredients i ON pli.ingredient_id = i.id
                    WHERE pli.po_id = %s
                """, (po["id"],))
                po["line_items"] = [
                    {
                        "ingredient_name": r[0],
                        "quantity": float(r[1]),
                        "unit_price": float(r[2])
                    }
                    for r in cur.fetchall()
                ]

        logger.info(f"Returning {len(pos)} purchase orders")
        return templates.TemplateResponse("components/po_list.html", {
            "request": request,
            "purchase_orders": pos
        })

    except DatabaseError as e:
        logger.error(f"Database error during optimization: {e}")
        raise internal_error("Failed to generate purchase orders", details=e.details)
    except Exception as e:
        logger.error(f"Unexpected error during optimization: {e}", exc_info=True)
        raise internal_error("Optimization failed")
