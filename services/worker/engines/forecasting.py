from datetime import date, timedelta
from typing import List, Dict
from decimal import Decimal
import pandas as pd
from lib.flux_lib.db import get_db_connection

def generate_forecast(tenant_id: str, forecast_date: date, conn):
    """
    Generates sales forecast for a specific date using 4-week Moving Average.
    """
    # 1. Fetch Historical Data (Last 4 weeks for same day-of-week)
    # e.g., if forecast_date is Friday, get last 4 Fridays.

    target_dow = forecast_date.weekday() # 0=Mon, 6=Sun

    with conn.cursor() as cur:
        # Fetch all sales for this tenant
        # Optimization: In prod, filter by date range (e.g. last 60 days)
        cur.execute("""
            SELECT
                oli.menu_item_id,
                so.timestamp::date as sale_date,
                SUM(oli.quantity) as total_qty
            FROM order_line_items oli
            JOIN sales_orders so ON oli.order_id = so.id
            WHERE oli.tenant_id = %s
            GROUP BY oli.menu_item_id, sale_date
        """, (tenant_id,))

        rows = cur.fetchall()

    if not rows:
        print(f"[Forecasting] No sales data for tenant {tenant_id}. Skipping.")
        return

    df = pd.DataFrame(rows, columns=["menu_item_id", "sale_date", "total_qty"])
    df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.date
    df["total_qty"] = df["total_qty"].astype(float)

    # Filter for same day of week
    # We look back up to 8 weeks to get at least 4 data points
    start_date = forecast_date - timedelta(weeks=8)
    history = df[
        (df["sale_date"] < forecast_date) &
        (df["sale_date"] >= start_date)
    ].copy()

    # Add DOW column
    history["dow"] = pd.to_datetime(history["sale_date"]).dt.dayofweek
    same_dow_history = history[history["dow"] == target_dow]

    # Calculate Average per Item
    # If < 2 data points, fallback to global average or 0
    forecasts = same_dow_history.groupby("menu_item_id")["total_qty"].mean().reset_index()

    with conn.cursor() as cur:
        for _, row in forecasts.iterrows():
            item_id = row["menu_item_id"]
            predicted_qty = round(row["total_qty"], 2)

            # Simple Confidence Interval (e.g. +/- 20%)
            # In real ML, use std dev
            lower = predicted_qty * 0.8
            upper = predicted_qty * 1.2

            cur.execute("""
                INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity, confidence_interval_lower, confidence_interval_upper, model_version)
                VALUES (%s, %s, %s, %s, %s, %s, 'v1_moving_avg')
                ON CONFLICT (tenant_id, menu_item_id, forecast_date)
                DO UPDATE SET
                    predicted_quantity = EXCLUDED.predicted_quantity,
                    confidence_interval_lower = EXCLUDED.confidence_interval_lower,
                    confidence_interval_upper = EXCLUDED.confidence_interval_upper,
                    created_at = NOW()
            """, (tenant_id, item_id, forecast_date, predicted_qty, lower, upper))

    print(f"[Forecasting] Generated forecasts for {forecast_date} (Tenant: {tenant_id})")
