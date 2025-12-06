import logging
import math
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass
from lib.flux_lib.db import get_db_connection

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class IngredientFinancials:
    """Financial risk profile for Newsvendor model."""
    ingredient_id: str
    name: str
    cost_overage: float      # Co: cost per unit if wasted (ingredient cost)
    cost_underage: float     # Cu: weighted avg margin lost if stockout
    shelf_life_days: int
    lead_time_days: int

    @property
    def critical_fractile(self) -> float:
        """Z = Cu / (Cu + Co) - target service level"""
        total = self.cost_underage + self.cost_overage
        if total <= 0:
            return 0.5  # Default to 50% if no cost data
        return self.cost_underage / total


@dataclass
class StochasticOrderResult:
    """Result from Newsvendor optimization with explainability."""
    ingredient_id: str
    name: str
    recommended_qty: float
    newsvendor_qty: float      # Q* from pure math
    shelf_life_cap: float      # Max based on expiry
    critical_fractile: float   # Z value used
    service_level_pct: float   # Z as percentage
    current_stock: float
    lead_time_demand_mean: float
    lead_time_demand_sigma: float
    recommendation_logic: str  # Plain English explanation
    math_proof: str            # The formula used


def get_ingredient_financials(tenant_id: str, conn) -> Dict[str, IngredientFinancials]:
    """
    Calculate Cu (underage cost) and Co (overage cost) for each ingredient.

    Cu = Weighted average contribution margin of menu items using this ingredient.
    Co = Direct cost per unit from ingredients table.

    Returns: Dict mapping ingredient_id to IngredientFinancials.
    """
    financials = {}

    with conn.cursor() as cur:
        # Get all ingredients with their costs
        cur.execute("""
            SELECT id, name, cost_per_unit, shelf_life_days, lead_time_days
            FROM ingredients
            WHERE tenant_id = %s
        """, (tenant_id,))
        ingredients = {row[0]: {
            'name': row[1],
            'cost': float(row[2] or 0),
            'shelf_life': int(row[3] or 7),
            'lead_time': int(row[4] or 2)
        } for row in cur.fetchall()}

        # Calculate weighted contribution margin per ingredient
        # Join: ingredients -> recipes -> menu_items -> sales volume
        cur.execute("""
            WITH ingredient_menu_sales AS (
                SELECT
                    r.ingredient_id,
                    m.id as menu_item_id,
                    m.name as menu_name,
                    m.price as menu_price,
                    r.quantity as recipe_qty,
                    COALESCE(SUM(oli.quantity), 0) as sales_volume
                FROM recipes r
                JOIN menu_items m ON r.menu_item_id = m.id
                LEFT JOIN order_line_items oli ON m.id = oli.menu_item_id
                WHERE r.tenant_id = %s
                GROUP BY r.ingredient_id, m.id, m.name, m.price, r.quantity
            ),
            menu_cogs AS (
                -- Calculate COGS for each menu item
                SELECT
                    m.id as menu_item_id,
                    COALESCE(SUM(r.quantity * i.cost_per_unit), 0) as total_cogs
                FROM menu_items m
                LEFT JOIN recipes r ON m.id = r.menu_item_id
                LEFT JOIN ingredients i ON r.ingredient_id = i.id
                WHERE m.tenant_id = %s
                GROUP BY m.id
            ),
            ingredient_margins AS (
                SELECT
                    ims.ingredient_id,
                    ims.menu_item_id,
                    ims.menu_price - mc.total_cogs as contribution_margin,
                    ims.sales_volume
                FROM ingredient_menu_sales ims
                JOIN menu_cogs mc ON ims.menu_item_id = mc.menu_item_id
            )
            SELECT
                ingredient_id,
                -- Weighted average margin (weighted by sales volume)
                CASE
                    WHEN SUM(sales_volume) > 0
                    THEN SUM(contribution_margin * sales_volume) / SUM(sales_volume)
                    ELSE AVG(contribution_margin)
                END as weighted_avg_margin
            FROM ingredient_margins
            GROUP BY ingredient_id
        """, (tenant_id, tenant_id))

        margin_data = {row[0]: float(row[1] or 0) for row in cur.fetchall()}

    # Build financials dict
    for ing_id, ing_data in ingredients.items():
        # Cu: Cost of underage = lost margin if stockout
        # Default to 2x ingredient cost if no sales data
        cost_underage = margin_data.get(ing_id, ing_data['cost'] * 2)
        cost_underage = max(cost_underage, 0.01)  # Ensure positive

        # Co: Cost of overage = ingredient cost (waste)
        cost_overage = ing_data['cost']
        cost_overage = max(cost_overage, 0.01)  # Ensure positive

        financials[ing_id] = IngredientFinancials(
            ingredient_id=str(ing_id),
            name=ing_data['name'],
            cost_overage=cost_overage,
            cost_underage=cost_underage,
            shelf_life_days=ing_data['shelf_life'],
            lead_time_days=ing_data['lead_time']
        )

        logger.debug(
            f"Financials for {ing_data['name']}: "
            f"Cu=${cost_underage:.2f}, Co=${cost_overage:.2f}, "
            f"Z={financials[ing_id].critical_fractile:.2f}"
        )

    return financials

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

def calculate_inventory_health(tenant_id: str, conn, ingredient_ids: Optional[List[str]] = None) -> List[InventoryHealth]:
    """
    Single Source of Truth for Inventory Logic.
    Used by both the API (Dashboard) and the Worker (Order Gen).
    """
    health_report = []

    with conn.cursor() as cur:
        # 1. Fetch Ingredients
        query_ingredients = """
            SELECT
                i.id, i.name, i.lead_time_days, i.cost_per_unit, i.unit,
                COALESCE(SUM(ib.remaining_quantity), 0) as current_stock
            FROM ingredients i
            LEFT JOIN inventory_batches ib ON i.id = ib.ingredient_id AND ib.remaining_quantity > 0
            WHERE i.tenant_id = %s
        """
        params_ingredients = [tenant_id]

        if ingredient_ids:
            query_ingredients += " AND i.id = ANY(%s::uuid[])"
            params_ingredients.append(ingredient_ids)

        query_ingredients += " GROUP BY i.id"

        cur.execute(query_ingredients, tuple(params_ingredients))
        ingredients = cur.fetchall()

        # 2. Fetch Forecasts (Next 14 Days)
        query_forecasts = """
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
        """
        params_forecasts = [tenant_id]

        if ingredient_ids:
            query_forecasts += " AND r.ingredient_id = ANY(%s::uuid[])"
            params_forecasts.append(ingredient_ids)

        query_forecasts += " GROUP BY r.ingredient_id, f.forecast_date ORDER BY f.forecast_date"

        cur.execute(query_forecasts, tuple(params_forecasts))

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


def generate_stochastic_orders(tenant_id: str, conn=None) -> List[StochasticOrderResult]:
    """
    Newsvendor-based inventory optimization.

    Calculates optimal order quantity Q* balancing stockout risk (Cu) vs waste risk (Co).

    Algorithm:
    1. Get ingredient financials (Cu, Co)
    2. Get demand forecasts with sigma (uncertainty)
    3. Calculate critical fractile Z = Cu / (Cu + Co)
    4. Calculate Q* = norm.ppf(Z, mu, sigma)
    5. Apply shelf life constraint: Q_max = sum(forecasts[:shelf_life])
    6. Final Q = min(Q*, Q_max) - current_stock

    Returns: List of StochasticOrderResult with recommendations and explanations.
    """
    if not SCIPY_AVAILABLE:
        raise ImportError("scipy required for stochastic optimization. Install with: pip install scipy")

    if conn is None:
        with get_db_connection(tenant_id) as conn:
            return generate_stochastic_orders(tenant_id, conn)

    logger.info(f"Starting stochastic inventory optimization for tenant {tenant_id}")

    results = []

    # 1. Get financial profiles (Cu, Co)
    financials = get_ingredient_financials(tenant_id, conn)

    if not financials:
        logger.warning("No ingredient financials found")
        return results

    with conn.cursor() as cur:
        # 2. Get current stock levels
        cur.execute("""
            SELECT
                i.id,
                i.name,
                COALESCE(SUM(ib.remaining_quantity), 0) as current_stock
            FROM ingredients i
            LEFT JOIN inventory_batches ib ON i.id = ib.ingredient_id AND ib.remaining_quantity > 0
            WHERE i.tenant_id = %s
            GROUP BY i.id, i.name
        """, (tenant_id,))
        stock_levels = {row[0]: {'name': row[1], 'stock': float(row[2])} for row in cur.fetchall()}

        # 3. Get demand forecasts aggregated by ingredient over lead time
        # This uses recipe explosion: forecast qty × recipe usage
        for ing_id, fin in financials.items():
            lead_time = fin.lead_time_days
            shelf_life = fin.shelf_life_days

            # Get aggregated demand over lead time + buffer
            forecast_horizon = max(lead_time + 3, shelf_life)

            cur.execute("""
                SELECT
                    f.forecast_date,
                    SUM(f.predicted_quantity * r.quantity) as ingredient_demand,
                    SUM(
                        CASE
                            WHEN f.confidence_interval_upper IS NOT NULL AND f.confidence_interval_lower IS NOT NULL
                            THEN ((f.confidence_interval_upper - f.confidence_interval_lower) / 3.92) * r.quantity
                            ELSE f.predicted_quantity * r.quantity * 0.15  -- Default 15% variance
                        END
                    ) as demand_sigma
                FROM forecasts f
                JOIN recipes r ON f.menu_item_id = r.menu_item_id AND r.tenant_id = f.tenant_id
                WHERE f.tenant_id = %s
                  AND r.ingredient_id = %s
                  AND f.forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '%s days'
                GROUP BY f.forecast_date
                ORDER BY f.forecast_date
            """, (tenant_id, ing_id, forecast_horizon))

            forecast_rows = cur.fetchall()

            if not forecast_rows:
                # No forecast data - skip this ingredient
                logger.debug(f"No forecast data for {fin.name}")
                continue

            # Calculate lead time demand (mu, sigma)
            lead_time_demands = [float(row[1]) for row in forecast_rows[:lead_time]]
            lead_time_sigmas = [float(row[2]) for row in forecast_rows[:lead_time]]

            # Aggregate: sum of means, sqrt of sum of variances
            mu = sum(lead_time_demands)
            # Variance is sigma^2, sum them, then sqrt
            sigma = math.sqrt(sum(s**2 for s in lead_time_sigmas)) if lead_time_sigmas else mu * 0.15

            # Clamp sigma minimum
            sigma = max(sigma, 0.1 * mu) if mu > 0 else 0.1

            # 4. Calculate Critical Fractile and Q*
            Z = fin.critical_fractile

            # Newsvendor optimal quantity
            # Q* = norm.ppf(Z) * sigma + mu
            try:
                Q_star = norm.ppf(Z, loc=mu, scale=sigma)
                Q_star = max(0, Q_star)  # Non-negative
            except Exception as e:
                logger.warning(f"Newsvendor calc failed for {fin.name}: {e}")
                Q_star = mu * 1.1  # Fallback: 10% buffer

            # 5. Shelf life constraint
            shelf_life_demands = [float(row[1]) for row in forecast_rows[:shelf_life]]
            shelf_life_cap = sum(shelf_life_demands)

            # 6. Final recommendation
            current_stock = stock_levels.get(ing_id, {}).get('stock', 0)

            # Final Q = min(Newsvendor, ShelfLife) - CurrentStock
            target_stock = min(Q_star, shelf_life_cap)
            recommended_qty = max(0, target_stock - current_stock)

            # 7. Generate explanation
            is_constrained_by_shelf = Q_star > shelf_life_cap
            is_high_margin = Z > 0.7

            if recommended_qty <= 0:
                recommendation_logic = "No order needed - current stock covers demand."
                math_proof = f"Stock ({current_stock:.1f}) ≥ Target ({target_stock:.1f})"
            elif is_constrained_by_shelf:
                recommendation_logic = (
                    f"Order capped at {recommended_qty:.1f} units to prevent spoilage. "
                    f"Sales forecast indicates you cannot sell more than {shelf_life_cap:.1f} units "
                    f"before expiration ({shelf_life} days)."
                )
                math_proof = f"Shelf Life Cap: Q_max = Σ(demand[0:{shelf_life}]) = {shelf_life_cap:.1f}"
            elif is_high_margin:
                recommendation_logic = (
                    f"Stocking aggressive safety stock ({recommended_qty:.1f} units) because "
                    f"running out costs you ${fin.cost_underage:.2f} in lost profit per unit, "
                    f"while waste only costs ${fin.cost_overage:.2f}. Service level: {Z*100:.0f}%."
                )
                math_proof = f"Z = Cu/(Cu+Co) = {fin.cost_underage:.1f}/({fin.cost_underage:.1f}+{fin.cost_overage:.1f}) = {Z:.2f}"
            else:
                recommendation_logic = (
                    f"Order {recommended_qty:.1f} units. Balanced approach - "
                    f"waste penalty (${fin.cost_overage:.2f}) is significant relative to "
                    f"stockout penalty (${fin.cost_underage:.2f}). Service level: {Z*100:.0f}%."
                )
                math_proof = f"Q* = norm.ppf({Z:.2f}, μ={mu:.1f}, σ={sigma:.1f}) = {Q_star:.1f}"

            results.append(StochasticOrderResult(
                ingredient_id=str(ing_id),
                name=fin.name,
                recommended_qty=round(recommended_qty, 2),
                newsvendor_qty=round(Q_star, 2),
                shelf_life_cap=round(shelf_life_cap, 2),
                critical_fractile=round(Z, 2),
                service_level_pct=round(Z * 100, 1),
                current_stock=round(current_stock, 2),
                lead_time_demand_mean=round(mu, 2),
                lead_time_demand_sigma=round(sigma, 2),
                recommendation_logic=recommendation_logic,
                math_proof=math_proof
            ))

    logger.info(f"Generated {len(results)} stochastic order recommendations")

    # Optionally persist to purchase_orders
    _save_stochastic_orders(tenant_id, results, conn)

    return results


def _save_stochastic_orders(tenant_id: str, results: List[StochasticOrderResult], conn):
    """Persist stochastic order recommendations to purchase_orders table."""
    items_to_order = [r for r in results if r.recommended_qty > 0]

    if not items_to_order:
        logger.info("No stochastic orders to save")
        return

    import uuid

    with conn.cursor() as cur:
        # Clear existing draft POs
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

        # Create new PO
        po_id = str(uuid.uuid4())
        delivery_date = date.today() + timedelta(days=3)

        cur.execute("""
            INSERT INTO purchase_orders (id, tenant_id, status, delivery_date)
            VALUES (%s, %s, 'draft', %s)
        """, (po_id, tenant_id, delivery_date))

        # Create line items with cost lookup
        for item in items_to_order:
            line_id = str(uuid.uuid4())

            # Get cost
            cur.execute("""
                SELECT cost_per_unit FROM ingredients WHERE id = %s
            """, (item.ingredient_id,))
            cost_row = cur.fetchone()
            unit_cost = float(cost_row[0]) if cost_row else 0

            cur.execute("""
                INSERT INTO po_line_items (id, tenant_id, po_id, ingredient_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (line_id, tenant_id, po_id, item.ingredient_id, item.recommended_qty, unit_cost))

        conn.commit()
        logger.info(f"Saved stochastic PO {po_id} with {len(items_to_order)} items")
