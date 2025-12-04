from typing import Dict, List, Tuple
from datetime import date, timedelta
import uuid
import numpy as np

from .menu import INGREDIENTS_DB, MENU_DB, MenuItem, Ingredient
from .models import Batch

class InventoryManager:
    def __init__(self):
        self.stock: Dict[int, List[Batch]] = {} # ingredient_id -> List[Batch]
        self.opening_stock: Dict[int, float] = {} # Snapshot at start of day
        self.pending_orders: List[dict] = [] # List of {arrival_date, ingredient_id, qty}

        # Initialize stock at par level with fresh batches
        start_date = date.fromisoformat("2025-01-01")
        for ing_id, ing in INGREDIENTS_DB.items():
            self.stock[ing_id] = []
            self._add_batch(ing_id, ing.par_level, start_date, ing.shelf_life_days, ing.cost_per_unit)
            self.opening_stock[ing_id] = ing.par_level

    def _add_batch(self, ing_id: int, qty: float, current_date: date, shelf_life: int, cost: float):
        batch = Batch(
            id=str(uuid.uuid4()),
            ingredient_id=ing_id,
            quantity=qty,
            received_date=current_date,
            expiration_date=current_date + timedelta(days=shelf_life),
            cost_per_unit=cost
        )
        self.stock[ing_id].append(batch)

    def record_opening_stock(self):
        """Call this at the very start of the day before any operations."""
        for ing_id, batches in self.stock.items():
            total_qty = sum(b.quantity for b in batches)
            self.opening_stock[ing_id] = total_qty

    def receive_orders(self, current_date: date) -> Dict[int, float]:
        received = {}
        remaining_orders = []
        for order in self.pending_orders:
            if order['arrival_date'] <= current_date:
                ing_id = order['ingredient_id']
                qty = order['qty']
                ing = INGREDIENTS_DB[ing_id]

                self._add_batch(ing_id, qty, current_date, ing.shelf_life_days, ing.cost_per_unit)

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

            available = sum(b.quantity for b in self.stock.get(ing_id, []))
            if available < needed:
                return False
        return True

    def deduct_item(self, menu_item: MenuItem, quantity: int):
        """Deduct ingredients for an item using FIFO."""
        for recipe_item in menu_item.recipe:
            ing_id = recipe_item.ingredient_id
            needed = recipe_item.quantity * quantity

            # Sort by expiration date (FIFO)
            batches = sorted(self.stock.get(ing_id, []), key=lambda b: b.expiration_date)

            remaining_needed = needed
            for batch in batches:
                if batch.quantity >= remaining_needed:
                    batch.quantity -= remaining_needed
                    remaining_needed = 0
                    break
                else:
                    remaining_needed -= batch.quantity
                    batch.quantity = 0

            # Clean up empty batches
            self.stock[ing_id] = [b for b in batches if b.quantity > 0.001]

    def check_reorder(self, current_date: date) -> List[dict]:
        new_orders = []
        for ing_id, ing in INGREDIENTS_DB.items():
            current_qty = sum(b.quantity for b in self.stock.get(ing_id, []))

            # Check if we have pending orders for this item
            pending_qty = sum(o['qty'] for o in self.pending_orders if o['ingredient_id'] == ing_id)

            effective_stock = current_qty + pending_qty

            if effective_stock <= ing.reorder_threshold:
                order_qty = ing.par_level - effective_stock

                if order_qty > 0:
                    # Stochastic Lead Time: Poisson(LeadTime)
                    # Minimum 1 day
                    actual_lead_time = max(1, np.random.poisson(ing.lead_time_days))
                    arrival = current_date + timedelta(days=actual_lead_time)

                    order = {
                        'arrival_date': arrival,
                        'ingredient_id': ing_id,
                        'qty': order_qty,
                        'cost': order_qty * ing.cost_per_unit
                    }
                    self.pending_orders.append(order)
                    new_orders.append(order)
        return new_orders

    def apply_spoilage(self, current_date: date) -> Dict[int, float]:
        """Check for expired batches."""
        waste = {}
        for ing_id, batches in self.stock.items():
            active_batches = []
            spoil_qty = 0.0
            for batch in batches:
                if batch.expiration_date <= current_date:
                    spoil_qty += batch.quantity
                else:
                    active_batches.append(batch)

            if spoil_qty > 0:
                waste[ing_id] = spoil_qty
                self.stock[ing_id] = active_batches

        return waste

    def get_stock_snapshot(self) -> Dict[int, float]:
        snapshot = {}
        for ing_id, batches in self.stock.items():
            snapshot[ing_id] = sum(b.quantity for b in batches)
        return snapshot

    def get_opening_stock(self) -> Dict[int, float]:
        return self.opening_stock.copy()
