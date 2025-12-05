import pytest
from datetime import date, timedelta
from uuid import uuid4
from services.worker.engines.inventory import generate_draft_orders
from lib.flux_lib.db import get_db_connection

@pytest.fixture
def tenant_id():
    return f"test-tenant-{uuid4()}"

@pytest.fixture
def db_setup(tenant_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Create Menu Item "Steak"
            steak_id = str(uuid4())
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, price)
                VALUES (%s, %s, 'Steak', 25.00)
            """, (steak_id, tenant_id))

            # Create Ingredient "Beef"
            beef_id = str(uuid4())
            cur.execute("""
                INSERT INTO ingredients (id, tenant_id, name, unit, cost_per_unit, lead_time_days)
                VALUES (%s, %s, 'Beef', 'kg', 15.00, 2)
            """, (beef_id, tenant_id))

            # Create Recipe (1 Steak = 0.3kg Beef)
            cur.execute("""
                INSERT INTO recipes (menu_item_id, ingredient_id, quantity)
                VALUES (%s, %s, 0.3)
            """, (steak_id, beef_id))

            # Set Initial Stock (0.5kg) - Low enough to trigger order
            cur.execute("""
                INSERT INTO inventory_batches (id, tenant_id, ingredient_id, quantity, remaining_quantity, received_date, expiry_date)
                VALUES (%s, %s, %s, 0.5, 0.5, CURRENT_DATE, CURRENT_DATE + INTERVAL '10 days')
            """, (str(uuid4()), tenant_id, beef_id))

            conn.commit()

            yield {
                "tenant_id": tenant_id,
                "steak_id": steak_id,
                "beef_id": beef_id
            }

        # Cleanup handled by test DB rollback usually, but explicit cleanup if needed

def test_golden_path_inventory_optimization(db_setup):
    """
    Golden Path: Forecast -> Optimization -> Draft PO
    Scenario:
    - Stock: 0.5kg Beef
    - Forecast: 10 Steaks/day for next 7 days
    - Demand: 3kg Beef/day
    - Runout: Immediate (0.5kg < 3kg)
    - Expectation: Draft PO created for Beef
    """
    tenant_id = db_setup["tenant_id"]
    steak_id = db_setup["steak_id"]
    beef_id = db_setup["beef_id"]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Insert Forecasts
            # Predict 10 steaks per day for next 7 days
            for i in range(7):
                f_date = date.today() + timedelta(days=i)
                cur.execute("""
                    INSERT INTO forecasts (tenant_id, menu_item_id, forecast_date, predicted_quantity)
                    VALUES (%s, %s, %s, 10.0)
                """, (tenant_id, steak_id, f_date))
            conn.commit()

            # 2. Run Engine
            generate_draft_orders(tenant_id, conn)

            # 3. Verify Draft PO
            cur.execute("""
                SELECT id FROM purchase_orders
                WHERE tenant_id = %s AND status = 'draft'
            """, (tenant_id,))
            po_row = cur.fetchone()

            assert po_row is not None, "Draft PO should have been created"
            po_id = po_row[0]

            # 4. Verify Line Items
            cur.execute("""
                SELECT quantity, unit_price FROM po_line_items
                WHERE po_id = %s AND ingredient_id = %s
            """, (po_id, beef_id))
            line_item = cur.fetchone()

            assert line_item is not None, "Beef should be in the PO"
            quantity = float(line_item[0])

            # Calculation Check:
            # Daily Demand = 10 steaks * 0.3kg = 3kg
            # Lead Time (2) + Review (3) + Buffer (1) = 6 days coverage target
            # Needed = 6 days * 3kg/day = 18kg
            # Current Stock = 0.5kg
            # Order = 18 - 0.5 = 17.5kg

            # Allow some float tolerance
            assert 17.0 < quantity < 18.0, f"Expected order ~17.5kg, got {quantity}"
