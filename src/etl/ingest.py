"""
ETL Pipeline for Flux Platform.

Loads simulator output data (CSV files) into the database with proper
tenant isolation, error handling, and logging.
"""
import os
import sys
import logging
import pandas as pd
from typing import Optional
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.restaurant_simulator.menu import MENU_DB, INGREDIENTS_DB
from services.api.config import settings
from services.api.database import db_service
from services.api.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def truncate_tables(tenant_id: str) -> None:
    """
    Truncate all data tables for a tenant.

    Important: This preserves master data (tenants) but removes all
    transactional and simulated data.

    Args:
        tenant_id: UUID of the tenant whose data to truncate

    Raises:
        DatabaseError: If truncation fails
    """
    logger.info(f"Truncating tables for tenant {tenant_id}")

    tables_to_truncate = [
        "order_line_items",
        "sales_orders",
        "inventory_log",
        "staff_schedule",
        "lost_sales",
        "forecasts",
        "po_line_items",
        "purchase_orders",
        "recipes",
        "menu_items",
        "ingredients"
    ]

    with db_service.get_cursor(tenant_id=tenant_id) as cur:
        for table in tables_to_truncate:
            try:
                cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
                logger.debug(f"Truncated {table}")
            except Exception as e:
                logger.warning(f"Could not truncate {table}: {e}")

    logger.info("Table truncation complete")


def load_master_data(tenant_id: str) -> None:
    """
    Load master data (ingredients, menu items, recipes) from simulator definitions.

    Args:
        tenant_id: UUID of the tenant

    Raises:
        DatabaseError: If loading fails
    """
    logger.info(f"Loading master data for tenant {tenant_id}")

    with db_service.get_cursor(tenant_id=tenant_id) as cur:
        # 1. Load Ingredients
        for ing in INGREDIENTS_DB.values():
            # Convert integer ID to UUID format (pad to 32 chars with zeros)
            ing_uuid = f"{ing.id:032d}"
            cur.execute("""
                INSERT INTO ingredients (
                    id, tenant_id, name, cost_per_unit, unit,
                    par_level, reorder_threshold, lead_time_days, shelf_life_days
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ing_uuid, tenant_id, ing.name, ing.cost_per_unit, ing.unit,
                ing.par_level, ing.reorder_threshold, ing.lead_time_days, ing.shelf_life_days
            ))
        logger.info(f"Loaded {len(INGREDIENTS_DB)} ingredients")

        # 2. Load Menu Items
        for item in MENU_DB:
            item_uuid = f"{item.id:032d}"
            cur.execute("""
                INSERT INTO menu_items (id, tenant_id, name, category, price)
                VALUES (%s, %s, %s, %s, %s)
            """, (item_uuid, tenant_id, item.name, item.category, item.price))
        logger.info(f"Loaded {len(MENU_DB)} menu items")

        # 3. Load Recipes
        recipe_count = 0
        for item in MENU_DB:
            item_uuid = f"{item.id:032d}"
            for recipe_item in item.recipe:
                ing_uuid = f"{recipe_item.ingredient_id:032d}"
                cur.execute("""
                    INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity)
                    VALUES (%s, %s, %s, %s)
                """, (tenant_id, item_uuid, ing_uuid, recipe_item.quantity))
                recipe_count += 1
        logger.info(f"Loaded {recipe_count} recipes")

    logger.info("Master data loading complete")


def load_csv_data(tenant_id: str, output_dir: str = "output_data") -> None:
    """
    Load simulator CSV output files into database.

    Maps simulator column names to database schema and injects tenant_id.

    Args:
        tenant_id: UUID of the tenant
        output_dir: Directory containing CSV files from simulator

    Raises:
        DatabaseError: If loading fails
        FileNotFoundError: If CSV files don't exist
    """
    logger.info(f"Loading CSV data from {output_dir} for tenant {tenant_id}")

    if not os.path.exists(output_dir):
        raise FileNotFoundError(f"Output directory '{output_dir}' not found")

    with db_service.get_cursor(tenant_id=tenant_id) as cur:
        # 1. Sales Orders (orders.csv -> sales_orders table)
        orders_file = os.path.join(output_dir, "orders.csv")
        if os.path.exists(orders_file):
            df_orders = pd.read_csv(orders_file)
            for _, row in df_orders.iterrows():
                # Generate UUID from integer order_id for consistency
                order_uuid = f"{int(row['order_id']):032d}"
                cur.execute("""
                    INSERT INTO sales_orders (id, tenant_id, timestamp, party_size, total_amount)
                    VALUES (%s, %s, %s, %s, %s)
                """, (order_uuid, tenant_id, row['timestamp'], int(row['party_size']), float(row['total_amount'])))
            logger.info(f"Loaded {len(df_orders)} sales orders")
        else:
            logger.warning(f"Orders file not found: {orders_file}")

        # 2. Order Line Items (order_items.csv -> order_line_items table)
        items_file = os.path.join(output_dir, "order_items.csv")
        if os.path.exists(items_file):
            df_items = pd.read_csv(items_file)
            for _, row in df_items.iterrows():
                order_uuid = f"{int(row['order_id']):032d}"
                menu_item_uuid = f"{int(row['menu_item_id']):032d}"
                cur.execute("""
                    INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
                    VALUES (%s, %s, %s, %s, %s)
                """, (tenant_id, order_uuid, menu_item_uuid, int(row['quantity']), float(row['price_at_order'])))
            logger.info(f"Loaded {len(df_items)} order line items")
        else:
            logger.warning(f"Order items file not found: {items_file}")

        # 3. Inventory Log
        inv_file = os.path.join(output_dir, "inventory_log.csv")
        if os.path.exists(inv_file):
            df_inv = pd.read_csv(inv_file)
            for _, row in df_inv.iterrows():
                ing_uuid = f"{int(row['ingredient_id']):032d}"
                cur.execute("""
                    INSERT INTO inventory_log (
                        tenant_id, date, ingredient_id, opening_stock,
                        used_qty, restock_qty, waste_qty, closing_stock
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    tenant_id, row['date'], ing_uuid,
                    float(row['opening_stock']), float(row['used_qty']),
                    float(row.get('restock_qty', 0)), float(row['waste_qty']),
                    float(row['closing_stock'])
                ))
            logger.info(f"Loaded {len(df_inv)} inventory log entries")
        else:
            logger.warning(f"Inventory log file not found: {inv_file}")

        # 4. Staff Schedule
        staff_file = os.path.join(output_dir, "staff_schedule.csv")
        if os.path.exists(staff_file):
            df_staff = pd.read_csv(staff_file)
            for _, row in df_staff.iterrows():
                cur.execute("""
                    INSERT INTO staff_schedule (tenant_id, date, role, count, cost)
                    VALUES (%s, %s, %s, %s, %s)
                """, (tenant_id, row['date'], row['role'], int(row['count']), float(row['cost'])))
            logger.info(f"Loaded {len(df_staff)} staff schedule entries")
        else:
            logger.warning(f"Staff schedule file not found: {staff_file}")

        # 5. Lost Sales
        lost_file = os.path.join(output_dir, "lost_sales.csv")
        if os.path.exists(lost_file):
            df_lost = pd.read_csv(lost_file)
            for _, row in df_lost.iterrows():
                cur.execute("""
                    INSERT INTO lost_sales (tenant_id, timestamp, party_size, reason, potential_revenue)
                    VALUES (%s, %s, %s, %s, %s)
                """, (tenant_id, row['timestamp'], int(row['party_size']), row['reason'], float(row['potential_revenue'])))
            logger.info(f"Loaded {len(df_lost)} lost sales entries")
        else:
            logger.warning(f"Lost sales file not found: {lost_file}")

    logger.info("CSV data loading complete")


def run_etl(tenant_id: Optional[str] = None, output_dir: str = "output_data") -> None:
    """
    Run the complete ETL pipeline.

    Truncates existing data, loads master data, and loads CSV simulator output.

    Args:
        tenant_id: UUID of tenant. Uses default from settings if not provided.
        output_dir: Directory containing CSV files

    Example:
        >>> run_etl()  # Uses default tenant
        >>> run_etl(tenant_id="custom-uuid-here")
    """
    tenant_id = tenant_id or settings.DEFAULT_TENANT_ID
    logger.info(f"Starting ETL pipeline for tenant {tenant_id}")

    try:
        truncate_tables(tenant_id)
        load_master_data(tenant_id)
        load_csv_data(tenant_id, output_dir)

        logger.info("✅ ETL pipeline completed successfully")
        print(f"\n✅ ETL Complete for tenant: {tenant_id}")
        print(f"   Data loaded from: {output_dir}")

    except Exception as e:
        logger.error(f"❌ ETL pipeline failed: {e}", exc_info=True)
        print(f"\n❌ ETL Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Setup logging
    setup_logging()

    # Run ETL
    run_etl()
