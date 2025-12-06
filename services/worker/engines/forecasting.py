from datetime import date, timedelta
from typing import List, Dict
from decimal import Decimal
import logging
import pandas as pd
import redis
import os
from lib.flux_lib.db import get_db_connection

logger = logging.getLogger(__name__)

# Redis Connection for Discovery Stream
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def publish_discovery_event(tenant_id: str, message: str):
    """
    Publishes a discovery event to the tenant's onboarding stream channel.
    This drives the "Matrix/Terminal" UI effect in the frontend.
    """
    try:
        r = redis.from_url(REDIS_URL)
        r.publish(f"onboarding:logs:{tenant_id}", message)
    except Exception as e:
        logger.error(f"Redis Publish Error: {e}")

def generate_forecast(tenant_id: str, forecast_date: date, conn):
    """
    Generates sales forecast for a specific date using 4-week Moving Average.
    """
    publish_discovery_event(tenant_id, f"Initializing Forecast Engine for {forecast_date}...")

    # 1. Fetch Historical Data (Last 4 weeks for same day-of-week)
    target_dow = forecast_date.weekday() # 0=Mon, 6=Sun

    with conn.cursor() as cur:
        # Fetch all sales for this tenant
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
        msg = "No sales data found. Skipping forecast generation."
        logger.info(msg, extra={"tenant_id": tenant_id})
        publish_discovery_event(tenant_id, f"WARNING: {msg}")
        return

    publish_discovery_event(tenant_id, f"Loaded {len(rows)} sales records. Analyzing seasonality...")

    df = pd.DataFrame(rows, columns=["menu_item_id", "sale_date", "total_qty"])
    df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.date
    df["total_qty"] = df["total_qty"].astype(float)

    # Filter for same day of week
    start_date = forecast_date - timedelta(weeks=8)
    history = df[
        (df["sale_date"] < forecast_date) &
        (df["sale_date"] >= start_date)
    ].copy()

    publish_discovery_event(tenant_id, f"Filtered history window: {start_date} to {forecast_date}")

    # Add DOW column
    history["dow"] = pd.to_datetime(history["sale_date"]).dt.dayofweek
    same_dow_history = history[history["dow"] == target_dow]

    if same_dow_history.empty:
         publish_discovery_event(tenant_id, "Insufficient history for Day-of-Week pattern matching.")

    # Calculate Average per Item
    forecasts = same_dow_history.groupby("menu_item_id")["total_qty"].mean().reset_index()

    publish_discovery_event(tenant_id, f"Identified {len(forecasts)} active menu items for forecast.")

    with conn.cursor() as cur:
        for _, row in forecasts.iterrows():
            item_id = row["menu_item_id"]
            predicted_qty = round(row["total_qty"], 2)

            # Simple Confidence Interval
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

    msg = f"Generated forecasts for {len(forecasts)} items."
    logger.info(msg, extra={"forecast_date": str(forecast_date), "tenant_id": tenant_id})
    publish_discovery_event(tenant_id, f"SUCCESS: {msg}")
