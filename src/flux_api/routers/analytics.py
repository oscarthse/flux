from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import get_db_connection
from src.analytics_engine.forecasting import ForecastEngine
from src.analytics_engine.inventory import InventoryOptimizer
import pandas as pd
import numpy as np

router = APIRouter()
forecast_engine = ForecastEngine()
inventory_optimizer = InventoryOptimizer()

@router.get("/sales/daily")
def get_daily_sales(db=Depends(get_db_connection)):
    query = """
    SELECT
        o.timestamp as date,
        mi.name as item_name,
        mi.id as item_id,
        SUM(oi.quantity) as quantity,
        SUM(oi.quantity * oi.price_at_order) as revenue
    FROM sales_orders o
    JOIN order_line_items oi ON o.id = oi.order_id
    JOIN menu_items mi ON oi.menu_item_id = mi.id
    GROUP BY o.timestamp, mi.name, mi.id
    ORDER BY o.timestamp DESC
    """
    # Use manual fetch to avoid read_sql + RealDictCursor issues
    with db.cursor() as cur:
        cur.execute(query)
        data = cur.fetchall()

    df = pd.DataFrame(data)

    if df.empty:
        return []

    # Ensure numeric types
    df['quantity'] = df['quantity'].astype(float)
    df['revenue'] = df['revenue'].astype(float)

    # Convert date to string for JSON serialization
    df['date'] = df['date'].astype(str)
    return df.to_dict(orient="records")

@router.get("/inventory/recommendations")
def get_inventory_recommendations(db=Depends(get_db_connection)):
    # 1. Get Current Inventory & Parameters
    query_inv = """
    SELECT
        i.id, i.name, i.unit, i.cost_per_unit, i.shelf_life_days,
        i.par_level as current_par,
        i.lead_time_days,
        COALESCE(il.closing_stock, 0) as current_stock
    FROM ingredients i
    LEFT JOIN (
        SELECT ingredient_id, closing_stock, date
        FROM inventory_log
        WHERE date = (SELECT MAX(date) FROM inventory_log)
    ) il ON i.id = il.ingredient_id
    """
    with db.cursor() as cur:
        cur.execute(query_inv)
        data_inv = cur.fetchall()
    df_inv = pd.DataFrame(data_inv)

    if df_inv.empty:
        return []

    # Ensure numeric types
    numeric_cols = ['cost_per_unit', 'current_par', 'current_stock']
    for col in numeric_cols:
        df_inv[col] = df_inv[col].astype(float)

    # 2. Get Usage History for Forecasting
    # We need to map Ingredients to Sales.
    # For MVP, let's forecast Ingredient Usage directly from inventory_log 'used_qty'
    query_usage = """
    SELECT date, ingredient_id as item_id, used_qty as quantity
    FROM inventory_log
    ORDER BY date
    """
    with db.cursor() as cur:
        cur.execute(query_usage)
        data_usage = cur.fetchall()
    df_usage = pd.DataFrame(data_usage)

    if not df_usage.empty:
        df_usage['quantity'] = df_usage['quantity'].astype(float)

    recommendations = []

    for _, row in df_inv.iterrows():
        ing_id = row['id']

        # Train Forecast Model
        model = forecast_engine.train_model(df_usage, ing_id)

        if model:
            # Predict next Lead Time + Safety days (e.g. 7 days)
            forecast_days = row['lead_time_days'] + 7
            forecast = forecast_engine.predict_demand(ing_id, days=forecast_days)
            mean_demand = np.sum(forecast)
            std_dev = np.std(forecast) if len(forecast) > 1 else mean_demand * 0.2 # Fallback volatility
        else:
            # Fallback: Average of last 30 days
            item_usage = df_usage[df_usage['item_id'] == ing_id]
            mean_demand = item_usage['quantity'].tail(30).sum()
            std_dev = item_usage['quantity'].tail(30).std()

        # Calculate Optimal Par
        # Proxy for Price: We don't sell ingredients directly.
        # We assume a target food cost percentage (e.g. 30%). So Price ~ Cost / 0.3
        implied_price = row['cost_per_unit'] / 0.3

        optimal_par = inventory_optimizer.calculate_optimal_par(
            mean_demand=mean_demand,
            std_dev_demand=std_dev,
            cost_per_unit=row['cost_per_unit'],
            price_per_unit=implied_price,
            shelf_life_days=row['shelf_life_days']
        )

        # Calculate Score
        score = inventory_optimizer.calculate_flux_sharpe(
            current_par=row['current_par'],
            optimal_par=optimal_par,
            mean_demand=mean_demand,
            std_dev_demand=std_dev,
            cost_per_unit=row['cost_per_unit'],
            price_per_unit=implied_price
        )

        recommendations.append({
            "ingredient": row['name'],
            "current_par": row['current_par'],
            "optimal_par": round(optimal_par, 1),
            "flux_sharpe": score,
            "action": "Increase" if optimal_par > row['current_par'] * 1.1 else "Decrease" if optimal_par < row['current_par'] * 0.9 else "Hold"
        })

    return recommendations
