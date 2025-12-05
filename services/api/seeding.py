from services.api.database import db_service
import uuid

def seed_tenant_data(tenant_id: str, cursor=None):
    """
    Seed initial data for a new tenant.
    Creates default ingredients and menu items.
    If cursor is provided, uses it (for atomic transactions).
    Otherwise, creates a new connection.
    """
    if cursor:
        _seed_internal(cursor, tenant_id)
    else:
        # Use get_connection with tenant_id to ensure RLS context is set
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                _seed_internal(cur, tenant_id)

def _seed_internal(cur, tenant_id):
    # 1. Seed Ingredients
    ingredients = [
        ("Roma Tomatoes", 1.50, "lb", 20.0, 5.0),
        ("Mozzarella Cheese", 4.00, "lb", 30.0, 10.0),
        ("00 Flour", 0.80, "lb", 100.0, 20.0),
        ("Pepperoni", 6.00, "lb", 15.0, 5.0),
        ("Basil", 12.00, "lb", 2.0, 0.5),
    ]

    ing_map = {} # Name -> ID

    for name, cost, unit, par, reorder in ingredients:
        ing_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO ingredients (id, tenant_id, name, cost_per_unit, unit, par_level, reorder_threshold)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (ing_id, tenant_id, name, cost, unit, par, reorder)
        )
        ing_map[name] = ing_id

    # 2. Seed Menu Items
    menu_items = [
        ("Margherita Pizza", "Food", 14.00),
        ("Pepperoni Pizza", "Food", 16.00),
    ]

    for name, category, price in menu_items:
        menu_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO menu_items (id, tenant_id, name, category, price)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (menu_id, tenant_id, name, category, price)
        )

        # Link Recipes (Simplified)
        if name == "Margherita Pizza":
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["Roma Tomatoes"], 0.5))
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["Mozzarella Cheese"], 0.4))
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["00 Flour"], 0.6))
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["Basil"], 0.05))
        elif name == "Pepperoni Pizza":
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["Roma Tomatoes"], 0.5))
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["Mozzarella Cheese"], 0.4))
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["00 Flour"], 0.6))
            cur.execute("INSERT INTO recipes (tenant_id, menu_item_id, ingredient_id, quantity) VALUES (%s, %s, %s, %s)", (tenant_id, menu_id, ing_map["Pepperoni"], 0.2))
