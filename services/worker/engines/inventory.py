import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass
from lib.flux_lib.db import get_db_connection

logger = logging.getLogger(__name__)

@dataclass
class InventoryHealth:
    ingredient_id: str
    name: str
    current_stock: float
    cost_per_unit: float
    burn_rate: float
    runout_date: Optional[date]
    days_until_runout: float
    status: str  # 'healthy', 'warning', 'critical', 'dormant'
    revenue_risk: float
    usage_explanation: str
    risk_explanation: str
    should_order: bool
    suggested_qty: float
    order_reason: str

def calculate_runout_date(current_stock: float, daily_forecasts: List[float]) -> Tuple[Optional[date], float]:
    """
    Calculate the date when stock will run out based on forecasts.
    """
    stock = current_stock
    today = date.today()

    for i, demand in enumerate(daily_forecasts):
        if stock < demand:
            # Runs out on this day
            return today + timedelta(days=i), float(i) + (stock / demand if demand > 0 else 0)
        stock -= demand

    return None, float(len(daily_forecasts))

def calculate_revenue_risk_bulk(
    tenant_id: str,
    ingredient_ids: List[str],
    runout_dates: Dict[str, date],
    conn
) -> Dict[str, Tuple[float, str]]:
    """
    Calculate DAILY revenue impact if stock runs out for MULTIPLE ingredients.
    Optimized to use a single query instead of N+1.
    Returns: {ingredient_id: (daily_impact, explanation)}
    """
    if not ingredient_ids or not runout_dates:
        return {}

    # Filter only ingredients that actually have a runout date
    active_ingredients = [ing_id for ing_id in ingredient_ids if ing_id in runout_dates]

    if not active_ingredients:
        return {}

    # Create a mapping of ingredient -> runout_date for SQL usage
    # Since we can't easily pass a map to SQL, we'll fetch all relevant forecast data
    # for the specific runout dates of interest.

    # Strategy: Fetch top revenue driving items for these ingredients
    # where the forecast date matches the runout date.

    results = {}

    with conn.cursor() as cur:
        # We need to query for each ingredient's specific runout date.
        # Doing this in one giant IN clause is tricky because dates differ.
        # However, we can fetch the relevant forecasts for the *range* of dates
        # and filter in Python, OR use a temporary values table.
        # For simplicity and compatibility, we'll fetch potentially relevant forecasts
        # (next 30 days) for these ingredients and filter in memory.
        # This is still much faster than N queries.

        cur.execute("""
            SELECT
                r.ingredient_id,
                m.name,
                m.price,
                f.predicted_quantity,
                f.forecast_date
            FROM forecasts f
            JOIN menu_items m ON f.menu_item_id = m.id
            JOIN recipes r ON m.id = r.menu_item_id
            WHERE f.tenant_id = %s
              AND r.ingredient_id = ANY(%s::uuid[])
              AND f.forecast_date >= CURRENT_DATE
              AND f.forecast_date <= CURRENT_DATE + INTERVAL '30 days'
        """, (tenant_id, active_ingredients))

        rows = cur.fetchall()

        # Organize by ingredient -> date -> list of (item_name, price, qty)
        data_map = {}
        for ing_id, name, price, qty, f_date in rows:
            if ing_id not in data_map:
                data_map[ing_id] = {}
            if f_date not in data_map[ing_id]:
                data_map[ing_id][f_date] = []

            data_map[ing_id][f_date].append({
                'name': name,
                'price': float(price),
                'qty': float(qty),
                'revenue': float(price) * float(qty)
            })

        # Now compute risk for each ingredient based on its specific runout date
        for ing_id in active_ingredients:
            runout_date = runout_dates[ing_id]

            if runout_date not in data_map.get(ing_id, {}):
                results[ing_id] = (0.0, "No immediate sales impact")
                continue

            items = data_map[ing_id][runout_date]
            # Sort by revenue impact
            items.sort(key=lambda x: x['revenue'], reverse=True)

            daily_impact = sum(item['revenue'] for item in items)

            if not items:
                results[ing_id] = (0.0, "No immediate sales impact")
            else:
                top_item = items[0]
                explanation = f"Can't make {int(top_item['qty'])} {top_item['name']} (${top_item['revenue']:.0f}/day)"
                results[ing_id] = (daily_impact, explanation)

    return results

def calculate_inventory_health(tenant_id: str, conn) -> List[InventoryHealth]:
    """
    Single Source of Truth for Inventory Logic.
    Used by both the API (Dashboard) and the Worker (Order Gen).
    """
    health_report = []

    with conn.cursor() as cur:
        # 1. Fetch Ingredients
        cur.execute("""
            SELECT
                i.id, i.name, i.lead_time_days, i.cost_per_unit, i.unit,
                COALESCE(SUM(ib.remaining_quantity), 0) as current_stock
            FROM ingredients i
            LEFT JOIN inventory_batches ib ON i.id = ib.ingredient_id AND ib.remaining_quantity > 0
            WHERE i.tenant_id = %s
            GROUP BY i.id
        """, (tenant_id,))
        ingredients = cur.fetchall()

        # 2. Fetch Forecasts (Next 14 Days)
        cur.execute("""
            SELECT
                r.ingredient_id,
                f.forecast_date,
                SUM(f.predicted_quantity * r.quantity) as required_qty,
                string_agg(DISTINCT m.name, ', ') as menu_items
            FROM forecasts f
            JOIN recipes r ON f.menu_item_id = r.menu_item_id
            JOIN menu_items m ON f.menu_item_id = m.id
            WHERE f.tenant_id = %s
              AND f.forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '13 days'
            GROUP BY r.ingredient_id, f.forecast_date
            ORDER BY f.forecast_date
        """, (tenant_id,))

        forecast_rows = cur.fetchall()

        # Map forecasts
        ing_forecasts = {}
        ing_menu_items = {} # To track which menu items drive demand

        for ing_id, f_date, qty, menu_names in forecast_rows:
            if ing_id not in ing_forecasts:
                ing_forecasts[ing_id] = [0.0] * 14

            day_idx = (f_date - date.today()).days
            if 0 <= day_idx < 14:
                ing_forecasts[ing_id][day_idx] = float(qty)

            # Collect menu items for explanation
            if ing_id not in ing_menu_items:
                ing_menu_items[ing_id] = set()
            if menu_names:
                ing_menu_items[ing_id].update(menu_names.split(', '))

        # 3. Pre-calculate Runout Dates for Bulk Risk Calculation
        runout_dates_map = {}
        ingredient_data_map = {} # Store processed data to avoid re-looping logic

        for ing in ingredients:
            ing_id, name, lead_time, cost, unit, current_stock = ing
            lead_time = float(lead_time or 2)
            cost = float(cost or 0)
            current_stock = float(current_stock)

            daily_demands = ing_forecasts.get(ing_id, [0.0] * 14)
            avg_burn_rate = sum(daily_demands[:7]) / 7.0

            runout_date, days_until_runout = calculate_runout_date(current_stock, daily_demands)

            if runout_date:
                runout_dates_map[ing_id] = runout_date

            ingredient_data_map[ing_id] = {
                'name': name,
                'lead_time': lead_time,
                'cost': cost,
                'current_stock': current_stock,
                'avg_burn_rate': avg_burn_rate,
                'runout_date': runout_date,
                'days_until_runout': days_until_runout,
                'daily_demands': daily_demands
            }

        # 4. Bulk Calculate Revenue Risk
        # This replaces the N+1 query loop
        risk_map = calculate_revenue_risk_bulk(tenant_id, list(ingredient_data_map.keys()), runout_dates_map, conn)

        # 5. Final Assembly
        for ing_id, data in ingredient_data_map.items():

            # Retrieve risk data
            risk_amount, risk_expl = risk_map.get(ing_id, (0.0, "No immediate risk"))

            # Usage Explanation
            menu_items = list(ing_menu_items.get(ing_id, []))[:3]
            if menu_items:
                usage_expl = f"Needed for: {', '.join(menu_items)}"
                if len(ing_menu_items.get(ing_id, [])) > 3:
                    usage_expl += ", etc."
            else:
                usage_expl = "No forecasted usage"

            # Status & Order Logic
            status = 'healthy'
            should_order = False
            suggested_qty = 0.0
            order_reason = ""

            if data['avg_burn_rate'] == 0:
                status = 'dormant'
            else:
                buffer_days = 1.0
                critical_threshold = data['lead_time'] + buffer_days

                if data['runout_date'] and data['days_until_runout'] <= critical_threshold:
                    status = 'critical'
                    should_order = True
                    order_reason = f"You have {data['days_until_runout']:.1f} days left, but delivery takes {data['lead_time']} days. Order NOW."
                elif data['days_until_runout'] <= (critical_threshold + 2):
                    status = 'warning'

                if should_order:
                    # Order up to Par (Lead Time + 3 Days Review + Buffer)
                    target_days = data['lead_time'] + 3 + buffer_days
                    needed = sum(data['daily_demands'][:int(target_days)]) + (data['avg_burn_rate'] * (target_days - int(target_days)))
                    suggested_qty = max(0, needed - data['current_stock'])

            health_report.append(InventoryHealth(
                ingredient_id=ing_id,
                name=data['name'],
                current_stock=data['current_stock'],
                cost_per_unit=data['cost'],
                burn_rate=data['avg_burn_rate'],
                runout_date=data['runout_date'],
                days_until_runout=data['days_until_runout'],
                status=status,
                revenue_risk=risk_amount,
                usage_explanation=usage_expl,
                risk_explanation=risk_expl,
                should_order=should_order,
                suggested_qty=suggested_qty,
                order_reason=order_reason
            ))

    return health_report

def generate_draft_orders(tenant_id: str, conn=None):
    """
    Generates draft purchase orders using the unified InventoryHealth logic.
    """
    if conn is None:
        with get_db_connection() as conn:
            return generate_draft_orders(tenant_id, conn)

    logger.info(f"Starting inventory optimization for tenant {tenant_id}")

    try:
        # 1. Get Unified Health Data
        health_data = calculate_inventory_health(tenant_id, conn)

        # 2. Filter items that need ordering
        items_to_order = [item for item in health_data if item.should_order and item.suggested_qty > 0]

        if not items_to_order:
            logger.info("No items need ordering at this time")
            return

        # 3. Delete existing draft orders (we regenerate fresh each time)
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM po_line_items
                WHERE tenant_id = %s AND po_id IN (
                    SELECT id FROM purchase_orders WHERE tenant_id = %s AND status = 'draft'
                )
            """, (tenant_id, tenant_id))

            cur.execute("""
                DELETE FROM purchase_orders
                WHERE tenant_id = %s AND status = 'draft'
            """, (tenant_id,))

            # 4. Create a single consolidated PO
            import uuid
            from datetime import date, timedelta

            po_id = str(uuid.uuid4())
            # Calculate delivery date based on max lead time
            max_lead_time = max([2] + [item.days_until_runout for item in items_to_order if item.days_until_runout > 0])
            delivery_date = date.today() + timedelta(days=min(int(max_lead_time), 3))

            cur.execute("""
                INSERT INTO purchase_orders (id, tenant_id, status, delivery_date)
                VALUES (%s, %s, 'draft', %s)
            """, (po_id, tenant_id, delivery_date))

            # 5. Create line items
            total_items = 0
            for item in items_to_order:
                line_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO po_line_items (id, tenant_id, po_id, ingredient_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (line_id, tenant_id, po_id, item.ingredient_id, item.suggested_qty, item.cost_per_unit))
                total_items += 1

            conn.commit()
            logger.info(f"Created draft PO {po_id} with {total_items} line items")

    except Exception as e:
        logger.error(f"Inventory optimization failed: {e}", exc_info=True)
        raise
