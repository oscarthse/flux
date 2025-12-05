"""
Menu Analytics Engine - Menu Engineering & Profitability Analysis.

Implements the Kasavana & Smith Menu Engineering Matrix classification:
- Stars: High Margin, High Volume
- Plowhorses: Low Margin, High Volume
- Puzzles: High Margin, Low Volume
- Dogs: Low Margin, Low Volume

Uses recipe explosion to calculate true COGS for each menu item.
"""
from datetime import date, timedelta
from typing import List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MenuItemPerformance:
    """Performance metrics for a single menu item."""
    item_id: str
    item_name: str
    category: str
    price: float
    unit_cogs: float  # Cost of Goods Sold per unit
    unit_margin: float  # Contribution margin per unit
    margin_percent: float  # Margin as % of price
    sales_volume: int
    total_revenue: float
    total_margin: float
    classification: str  # "Star", "Plowhorse", "Puzzle", "Dog"
    strategic_insight: str
    color: str  # For UI (green, blue, yellow, red)

    def to_dict(self):
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "category": self.category,
            "price": round(self.price, 2),
            "unit_cogs": round(self.unit_cogs, 2),
            "unit_margin": round(self.unit_margin, 2),
            "margin_percent": round(self.margin_percent, 1),
            "sales_volume": self.sales_volume,
            "total_revenue": round(self.total_revenue, 2),
            "total_margin": round(self.total_margin, 2),
            "classification": self.classification,
            "strategic_insight": self.strategic_insight,
            "color": self.color
        }


def calculate_menu_performance(
    tenant_id: str,
    period_days: int,
    conn
) -> Tuple[List[MenuItemPerformance], dict]:
    """
    Calculate menu engineering metrics for all menu items.

    Algorithm:
    1. Query sales data (last N days)
    2. Recipe explosion: Calculate COGS for each item
    3. Calculate contribution margins
    4. Classify into 4 quadrants (Kasavana & Smith Matrix)
    5. Generate strategic insights

    Returns:
        (list of MenuItemPerformance, dict of portfolio metrics)
    """
    logger.info(f"Calculating menu performance for {period_days} days")

    with conn.cursor() as cur:
        # Step 1: Get ALL menu items with sales data (or zeros if no sales)
        # NOTE: We LEFT JOIN from menu_items so items without sales still appear
        cur.execute("""
            WITH all_menu_items AS (
                SELECT
                    mi.id as menu_item_id,
                    mi.name as item_name,
                    mi.category,
                    mi.price
                FROM menu_items mi
                WHERE mi.tenant_id = %s
                  AND mi.price IS NOT NULL AND mi.price > 0
            ),
            sales_summary AS (
                SELECT
                    oli.menu_item_id,
                    SUM(oli.quantity) as total_sold,
                    SUM(oli.quantity * oli.price_at_order) as total_revenue
                FROM order_line_items oli
                JOIN sales_orders so ON oli.order_id = so.id
                WHERE so.tenant_id = %s
                  AND so.timestamp >= NOW() - make_interval(days := %s)
                GROUP BY oli.menu_item_id
            ),
            cogs_calculation AS (
                SELECT
                    r.menu_item_id,
                    SUM(r.quantity * i.cost_per_unit) as unit_cogs
                FROM recipes r
                JOIN ingredients i ON r.ingredient_id = i.id
                WHERE r.tenant_id = %s
                GROUP BY r.menu_item_id
            ),
            combined AS (
                SELECT
                    ami.menu_item_id,
                    ami.item_name,
                    ami.category,
                    ami.price,
                    COALESCE(c.unit_cogs, 0) as unit_cogs,
                    COALESCE(s.total_sold, 0) as total_sold,
                    COALESCE(s.total_revenue, 0) as total_revenue,
                    (ami.price - COALESCE(c.unit_cogs, 0)) as unit_margin,
                    ((ami.price - COALESCE(c.unit_cogs, 0)) * COALESCE(s.total_sold, 0)) as total_margin
                FROM all_menu_items ami
                LEFT JOIN sales_summary s ON ami.menu_item_id = s.menu_item_id
                LEFT JOIN cogs_calculation c ON ami.menu_item_id = c.menu_item_id
            )
            SELECT
                menu_item_id,
                item_name,
                category,
                price,
                unit_cogs,
                unit_margin,
                total_sold,
                total_revenue,
                total_margin
            FROM combined
            ORDER BY total_margin DESC, total_sold DESC
        """, (tenant_id, tenant_id, period_days, tenant_id))

        rows = cur.fetchall()

    if not rows:
        logger.warning("No sales data found for menu analysis")
        return [], {"avg_margin": 0, "avg_volume": 0, "total_items": 0}

    # Step 2: Calculate portfolio averages
    margins = [float(row[5]) for row in rows]  # unit_margin
    volumes = [int(row[6]) for row in rows]    # total_sold

    avg_margin = sum(margins) / len(margins)
    avg_volume = sum(volumes) / len(volumes)

    logger.info(f"Portfolio: Avg Margin=${avg_margin:.2f}, Avg Volume={avg_volume:.0f}")

    # Step 3: Classify each item and generate insights
    performance_items = []

    for row in rows:
        item_id, name, category, price, cogs, margin, volume, revenue, total_margin = row

        item_id = str(item_id)
        price = float(price)
        cogs = float(cogs)
        margin = float(margin)
        volume = int(volume)
        revenue = float(revenue)
        total_margin = float(total_margin)

        margin_percent = (margin / price * 100) if price > 0 else 0

        # Classify using Kasavana & Smith Matrix
        # Classify using Kasavana & Smith Matrix
        if margin > avg_margin and volume > avg_volume:
            classification = "Star"
            color = "#10b981"  # emerald-500
            insight = "High margin, high volume. Maintain quality and promote visibility."
        elif margin < avg_margin and volume > avg_volume:
            classification = "Plowhorse"
            color = "#3b82f6"  # blue-500
            insight = "High volume, low margin. Consider price increase or portion adjustment."
        elif margin > avg_margin and volume < avg_volume:
            classification = "Puzzle"
            color = "#f59e0b"  # amber-500
            insight = "High margin, low volume. Increase marketing or bundle with popular items."
        else:  # Dog
            classification = "Dog"
            color = "#ef4444"  # red-500
            insight = "Low margin, low volume. Evaluate for removal or rebranding."

        performance_items.append(MenuItemPerformance(
            item_id=item_id,
            item_name=name,
            category=category or "Uncategorized",
            price=price,
            unit_cogs=cogs,
            unit_margin=margin,
            margin_percent=margin_percent,
            sales_volume=volume,
            total_revenue=revenue,
            total_margin=total_margin,
            classification=classification,
            strategic_insight=insight,
            color=color
        ))

    portfolio_metrics = {
        "avg_margin": round(avg_margin, 2),
        "avg_volume": round(avg_volume, 0),
        "total_items": len(performance_items),
        "total_revenue": sum(item.total_revenue for item in performance_items),
        "total_margin": sum(item.total_margin for item in performance_items),
        "stars": len([i for i in performance_items if i.classification == "Star"]),
        "plowhorses": len([i for i in performance_items if i.classification == "Plowhorse"]),
        "puzzles": len([i for i in performance_items if i.classification == "Puzzle"]),
        "dogs": len([i for i in performance_items if i.classification == "Dog"])
    }

    logger.info(f"Classification: {portfolio_metrics['stars']} Stars, {portfolio_metrics['plowhorses']} Plowhorses, "
                f"{portfolio_metrics['puzzles']} Puzzles, {portfolio_metrics['dogs']} Dogs")

    return performance_items, portfolio_metrics
