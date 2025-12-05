import logging
import pandas as pd
from datetime import date, timedelta
from lib.flux_lib.db import get_db_connection
from src.analytics_engine.forecasting import ForecastEngine
from services.api.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_forecasting(tenant_id: str):
    logger.info(f"Starting forecasting for tenant {tenant_id}")

    with get_db_connection() as conn:
        # 1. Fetch Sales History
        logger.info("Fetching sales history...")
        query = """
            SELECT
                oli.menu_item_id as item_id,
                DATE(so.timestamp) as date,
                SUM(oli.quantity) as quantity
            FROM sales_orders so
            JOIN order_line_items oli ON so.id = oli.order_id
            WHERE so.tenant_id = %s
            GROUP BY oli.menu_item_id, DATE(so.timestamp)
            ORDER BY date
        """
        sales_df = pd.read_sql(query, conn, params=(tenant_id,))

        if sales_df.empty:
            logger.warning("No sales data found. Cannot generate forecasts.")
            return

        # 2. Initialize Engine
        engine = ForecastEngine()

        # 3. Train & Predict for each item
        unique_items = sales_df['item_id'].unique()
        logger.info(f"Found {len(unique_items)} items to forecast")

        forecasts_to_save = []
        today = date.today()

        for item_id in unique_items:
            # Train
            model = engine.train_model(sales_df, item_id)
            if not model:
                logger.warning(f"Skipping item {item_id} (insufficient data)")
                continue

            # Predict (Next 14 days)
            predictions = engine.predict_demand(item_id, days=14)

            for i, qty in enumerate(predictions):
                forecast_date = today + timedelta(days=i)
                forecasts_to_save.append((
                    tenant_id,
                    item_id,
                    forecast_date,
                    max(0.0, float(qty)) # Ensure no negative forecasts
                ))

        # 4. Save to DB
        if forecasts_to_save:
            logger.info(f"Saving {len(forecasts_to_save)} forecast entries...")
            with conn.cursor() as cur:
                # Clear old forecasts for this period to avoid duplicates/conflicts
                # (Or use ON CONFLICT UPDATE if schema supports it, schema has UNIQUE constraint)

                # Using ON CONFLICT DO UPDATE
                cur.executemany("""
                    INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id, menu_item_id, forecast_date)
                    DO UPDATE SET predicted_quantity = EXCLUDED.predicted_quantity, created_at = NOW()
                """, forecasts_to_save)

            conn.commit()
            logger.info("Forecasts saved successfully.")
        else:
            logger.info("No forecasts generated.")

if __name__ == "__main__":
    # Use default tenant from settings
    tenant_id = settings.DEFAULT_TENANT_ID
    run_forecasting(tenant_id)
