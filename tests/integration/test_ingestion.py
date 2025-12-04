import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from services.worker.engines.ingestion import process_ingestion
from lib.flux_lib.db import get_db_connection

def test_ingestion_flow(tenant_id):
    """
    Test full ingestion flow:
    1. Setup: Create Menu Item, Ingredient, Recipe, Inventory Batch.
    2. Action: Process 'Square' payload.
    3. Assert: Order created, Inventory deducted.
    """

    # 1. Setup Data
    menu_item_id = str(uuid4())
    ingredient_id = str(uuid4())
    external_item_id = "SQUARE_ITEM_123"

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Create Ingredient
            cur.execute("""
                INSERT INTO ingredients (id, tenant_id, name, cost_per_unit, unit)
                VALUES (%s, %s, 'Test Ingredient', 1.00, 'kg')
            """, (ingredient_id, tenant_id))

            # Create Inventory Batch (10 units)
            cur.execute("""
                INSERT INTO inventory_batches (tenant_id, ingredient_id, quantity, remaining_quantity, expires_at)
                VALUES (%s, %s, 10.0, 10.0, %s)
            """, (tenant_id, ingredient_id, datetime.now() + timedelta(days=7)))

            # Create Menu Item
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, external_id, name, price)
                VALUES (%s, %s, %s, 'Test Burger', 15.00)
            """, (menu_item_id, tenant_id, external_item_id))

            # Create Recipe (1 Burger = 0.5 units of Ingredient)
            cur.execute("""
                INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
                VALUES (%s, %s, %s, 0.5)
            """, (tenant_id, menu_item_id, ingredient_id))

    # 2. Simulate Payload
    payload = {
        "id": "ORDER_999",
        "created_at": "2023-10-27T12:00:00Z",
        "total_money": {"amount": 1500}, # $15.00
        "line_items": [
            {
                "catalog_object_id": external_item_id,
                "name": "Test Burger",
                "quantity": "2", # 2 Burgers -> Should use 1.0 unit of ingredient
                "total_money": {"amount": 3000}
            }
        ]
    }

    # 3. Run Ingestion
    with get_db_connection(tenant_id=tenant_id) as conn:
        process_ingestion(tenant_id, "square", payload, conn)

    # 4. Verify
    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Check Order
            cur.execute("SELECT total_amount FROM sales_orders WHERE external_id = 'ORDER_999'")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 15.00

            # Check Inventory Deduction
            # Initial 10.0 - (2 burgers * 0.5) = 9.0 remaining
            cur.execute("SELECT remaining_quantity FROM inventory_batches WHERE ingredient_id = %s", (ingredient_id,))
            batch_row = cur.fetchone()
            assert batch_row is not None
            assert float(batch_row[0]) == 9.0

def test_ghost_item_triage(tenant_id):
    """
    Test that unknown items are added to triage.
    """
    payload = {
        "id": "ORDER_GHOST",
        "created_at": "2023-10-27T13:00:00Z",
        "total_money": {"amount": 500},
        "line_items": [
            {
                "catalog_object_id": "UNKNOWN_ITEM_X",
                "name": "Mystery Special",
                "quantity": "1",
                "total_money": {"amount": 500}
            }
        ]
    }

    with get_db_connection(tenant_id=tenant_id) as conn:
        process_ingestion(tenant_id, "square", payload, conn)

    with get_db_connection(tenant_id=tenant_id) as conn:
        with conn.cursor() as cur:
            # Check Triage
            cur.execute("SELECT external_name, status FROM triage_items WHERE external_id = 'UNKNOWN_ITEM_X'")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "Mystery Special"
            assert row[1] == "pending"
