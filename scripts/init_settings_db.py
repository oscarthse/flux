import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.api.database import db_service
from services.api.logging_config import setup_logging

setup_logging()

def init_settings_table():
    print("Initializing tenant_settings table...")

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS tenant_settings (
        tenant_id UUID PRIMARY KEY REFERENCES tenants(id),
        forecasting_model VARCHAR(50) DEFAULT 'prophet',
        prediction_horizon_days INT DEFAULT 30,
        historical_lookback_days INT DEFAULT 365,
        data_recency_alert_days INT DEFAULT 3,
        safety_stock_buffer_percent DECIMAL(5,2) DEFAULT 20.00,
        order_cycle_target_days INT DEFAULT 7,
        default_lead_time_days INT DEFAULT 2,
        financial_risk_threshold DECIMAL(10,2) DEFAULT 500.00,
        timezone VARCHAR(50) DEFAULT 'UTC',
        updated_at TIMESTAMP DEFAULT NOW()
    );

    ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE tablename = 'tenant_settings' AND policyname = 'tenant_isolation'
        ) THEN
            CREATE POLICY tenant_isolation ON tenant_settings USING (tenant_id = current_tenant_id());
        END IF;
    END
    $$;
    """

    try:
        # Use get_connection with use_rls=False to avoid setting tenant context for DDL
        # This allows us to create the table globally.
        with db_service.get_connection(use_rls=False) as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_sql)
                # Connection context manager handles commit/rollback
                print("Table tenant_settings created successfully (or already exists).")
    except Exception as e:
        print(f"Error creating table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_settings_table()
