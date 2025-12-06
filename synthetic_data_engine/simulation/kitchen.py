import random
from typing import List, Dict
from collections import defaultdict
from ..config.catalog import MenuItem, Ingredient, INGREDIENTS

class KitchenChaos:
    """
    Simulates the 'Imperfect Inventory' layer.
    """

    WASTE_RATE = 0.02 # 2% of food is wasted/returned but not sold
    STAFF_MEAL_RATE = 0.01 # 1% of total daily stock is consumed by staff

    @staticmethod
    def calculate_usage(sales: List[MenuItem]) -> Dict[str, float]:
        """
        Takes clean POS sales and returns 'dirty' inventory usage.
        """
        usage = defaultdict(float) # Ingredient Name -> Qty

        # 1. Theoretical Usage (Clean)
        for item in sales:
            for ing_name, qty in item.recipe.items():
                usage[ing_name] += qty

        # 2. Kitchen Waste (Shrinkage)
        # Apply random waste multiplier per ingredient category?
        # Simpler: Randomly add waste events
        for item in sales:
            if random.random() < KitchenChaos.WASTE_RATE:
                # This item was cooked but returned/dropped
                # We add the ingredients to usage, but they aren't in sales again
                for ing_name, qty in item.recipe.items():
                    usage[ing_name] += qty

        # 3. Staff Consumption (Shift Meal)
        # Simplified: Add 1% buffer to common items
        staff_staples = ["Rice (Bomba)", "Chicken", "Potatoes", "Coffee Beans"]
        for ing_name in staff_staples:
            if ing_name in usage:
               usage[ing_name] *= (1 + KitchenChaos.STAFF_MEAL_RATE)

        return dict(usage)
