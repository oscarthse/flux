from typing import Dict, Any
import json
from datetime import datetime
from lib.flux_lib.domain.ingestion import NormalizedOrder, NormalizedLineItem

def normalize_payload(source: str, payload: Dict[str, Any]) -> NormalizedOrder:
    """
    Adapts external POS payloads to internal NormalizedOrder.
    """
    if source == "square":
        # Mock mapping for Square
        # Assumes payload structure: { "id": "...", "created_at": "...", "line_items": [...], "total_money": {...} }
        return NormalizedOrder(
            external_id=payload.get("id"),
            timestamp=datetime.fromisoformat(payload.get("created_at").replace("Z", "+00:00")),
            source="square",
            total_amount=payload.get("total_money", {}).get("amount", 0) / 100.0,
            items=[
                NormalizedLineItem(
                    external_id=item.get("catalog_object_id"),
                    name=item.get("name"),
                    quantity=int(item.get("quantity", 1)),
                    price=float(item.get("total_money", {}).get("amount", 0) / 100.0)
                ) for item in payload.get("line_items", [])
            ]
        )
    elif source == "toast":
        # Mock mapping for Toast
        pass

    raise ValueError(f"Unsupported source: {source}")

def process_ingestion(tenant_id: str, source: str, payload: Dict[str, Any], conn):
    """
    Core Ingestion Logic:
    1. Normalize
    2. Triage (Ghost Items)
    3. Record Sales
    4. Explode Recipes & Deduct Inventory
    """
    order = normalize_payload(source, payload)

    with conn.cursor() as cur:
        # 1. Record Order
        cur.execute("""
            INSERT INTO sales_orders (tenant_id, external_id, timestamp, party_size, total_amount)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, external_id) DO NOTHING
            RETURNING id
        """, (tenant_id, order.external_id, order.timestamp, order.party_size, order.total_amount))

        row = cur.fetchone()
        if not row:
            print(f"Order {order.external_id} already exists. Skipping.")
            return

        order_uuid = row[0]

        for item in order.items:
            # 2. Resolve Item (Triage Check)
            cur.execute("""
                SELECT id FROM menu_items
                WHERE tenant_id = %s AND external_id = %s
            """, (tenant_id, item.external_id))

            menu_item_row = cur.fetchone()

            if not menu_item_row:
                # GHOST ITEM -> Triage
                print(f"Ghost Item detected: {item.name} ({item.external_id})")
                cur.execute("""
                    INSERT INTO triage_items (tenant_id, external_id, external_name, source, status)
                    VALUES (%s, %s, %s, %s, 'pending')
                    ON CONFLICT (tenant_id, external_id) DO NOTHING
                """, (tenant_id, item.external_id, item.name, source))
                continue

            menu_item_id = menu_item_row[0]

            # 3. Record Line Item
            cur.execute("""
                INSERT INTO order_line_items (tenant_id, order_id, menu_item_id, quantity, price_at_order)
                VALUES (%s, %s, %s, %s, %s)
            """, (tenant_id, order_uuid, menu_item_id, item.quantity, item.price))

            # 4. Recipe Explosion & Inventory Deduction (FEFO)
            # Fetch recipe ingredients
            cur.execute("""
                SELECT ingredient_id, quantity
                FROM recipes
                WHERE tenant_id = %s AND menu_item_id = %s
            """, (tenant_id, menu_item_id))

            ingredients = cur.fetchall()
            for ing_id, qty_per_item in ingredients:
                total_qty_needed = float(qty_per_item) * item.quantity

                # FEFO Logic: Fetch batches ordered by expiry
                cur.execute("""
                    SELECT id, remaining_quantity
                    FROM inventory_batches
                    WHERE tenant_id = %s AND ingredient_id = %s AND remaining_quantity > 0
                    ORDER BY expires_at ASC
                """, (tenant_id, ing_id))

                batches = cur.fetchall()
                remaining_needed = total_qty_needed

                for batch_id, batch_qty in batches:
                    if remaining_needed <= 0:
                        break

                    deduct = min(remaining_needed, float(batch_qty))

                    cur.execute("""
                        UPDATE inventory_batches
                        SET remaining_quantity = remaining_quantity - %s
                        WHERE id = %s
                    """, (deduct, batch_id))

                    remaining_needed -= deduct

                if remaining_needed > 0:
                    print(f"WARNING: Insufficient stock for ingredient {ing_id}. Deficit: {remaining_needed}")
                    # TODO: Log to a 'stockout_log' or similar
