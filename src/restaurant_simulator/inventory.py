from typing import Dict, List, Tuple
from datetime import date, timedelta
from dataclasses import dataclass

from .menu import INGREDIENTS_DB, MENU_DB, MenuItem, Ingredient
from .demand import Order

@dataclass
class InventoryState:
    ingredient_id: int
    quantity: float

class InventoryManager:
    def __init__(self):
        self.stock: Dict[int, float] = {} # ingredient_id -> quantity
        self.opening_stock: Dict[int, float] = {} # Snapshot at start of day
        self.pending_orders: List[dict] = [] # List of {arrival_date, ingredient_id, qty}

        # Initialize stock at par level
        for ing_id, ing in INGREDIENTS_DB.items():
            self.stock[ing_id] = ing.par_level
            self.opening_stock[ing_id] = ing.par_level

    def record_opening_stock(self):
        """Call this at the very start of the day before any operations."""
        self.opening_stock = self.stock.copy()

    def receive_orders(self, current_date: date) -> Dict[int, float]:
        received = {}
        remaining_orders = []
        for order in self.pending_orders:
            if order['arrival_date'] <= current_date:
                ing_id = order['ingredient_id']
                qty = order['qty']
                self.stock[ing_id] = self.stock.get(ing_id, 0) + qty
                received[ing_id] = received.get(ing_id, 0) + qty
            else:
                remaining_orders.append(order)
        self.pending_orders = remaining_orders
        return received

    def can_fulfill(self, menu_item: MenuItem, quantity: int) -> bool:
        """Check if we have enough stock for this item * quantity."""
        for recipe_item in menu_item.recipe:
            ing_id = recipe_item.ingredient_id
            needed = recipe_item.quantity * quantity
            if self.stock.get(ing_id, 0) < needed:
                return False
        return True

    def deduct_item(self, menu_item: MenuItem, quantity: int):
        """Deduct ingredients for an item. Assumes can_fulfill was checked."""
        for recipe_item in menu_item.recipe:
            ing_id = recipe_item.ingredient_id
            needed = recipe_item.quantity * quantity
            self.stock[ing_id] -= needed

    def check_reorder(self, current_date: date) -> List[dict]:
        new_orders = []
        for ing_id, ing in INGREDIENTS_DB.items():
            current_qty = self.stock.get(ing_id, 0)

            # Check if we have pending orders for this item
            pending_qty = sum(o['qty'] for o in self.pending_orders if o['ingredient_id'] == ing_id)

            effective_stock = current_qty + pending_qty

            # Reorder Logic:
            # If effective stock is below threshold, order enough to reach Par Level.
            # CRITICAL FIX: Ensure we order at least enough to cover lead time usage if needed.
            # For MVP, simply topping up to Par Level is usually sufficient IF Par Level is high enough (Par > Daily Usage * Lead Time + Safety).
            # We updated Par Levels in menu.py to be robust.

            if effective_stock <= ing.reorder_threshold:
                order_qty = ing.par_level - effective_stock

                # Ensure positive order quantity (e.g. if effective stock > par which shouldn't happen but good for safety)
                if order_qty > 0:
                    arrival = current_date + timedelta(days=ing.lead_time_days)
                    order = {
                        'arrival_date': arrival,
                        'ingredient_id': ing_id,
                        'qty': order_qty,
                        'cost': order_qty * ing.cost_per_unit
                    }
                    self.pending_orders.append(order)
                    new_orders.append(order)
        return new_orders

    def apply_spoilage(self) -> Dict[int, float]:
        waste = {}
        for ing_id, ing in INGREDIENTS_DB.items():
            if ing.shelf_life_days <= 3:
                current = self.stock.get(ing_id, 0)
                if current > 0:
                    spoil_qty = current * 0.05
                    self.stock[ing_id] -= spoil_qty
                    waste[ing_id] = spoil_qty
        return waste

    def get_stock_snapshot(self) -> Dict[int, float]:
        return self.stock.copy()

    def get_opening_stock(self) -> Dict[int, float]:
        return self.opening_stock.copy()
