import random
from typing import List, Dict
from ..config.agents import AgentArchetype
from ..config.catalog import MenuItem, MENU_ITEMS

class CustomerAgent:
    def __init__(self, archetype: AgentArchetype):
        self.archetype = archetype

    def generate_order(self, service_type: str, price_multiplier: float) -> List[MenuItem]:
        """
        Simulates the agent ordering items.

        Logic:
        1. Decide how many items to order (Poisson-ish distribution around avg).
        2. Pick categories based on preference weights.
        3. Pick specific items within category.
        4. Budget check: complex agents might reject expensive items (simplified here).
        """

        # 1. Item Count
        # Add variance: +/- 1 or 2 items
        count = max(1, int(random.normalvariate(self.archetype.avg_items_ordered, 1.0)))

        # Special logic: Menu del Dia at Lunch for Locals/Business
        if service_type == "lunch" and self.archetype.name in ["Local", "Group"]:
            # 80% chance to just order Menu del Dia logic if available
            # We treat "Menu del Dia" as a single item for simplicity
            if random.random() < 0.8:
                return [m for m in MENU_ITEMS if m.name == "Menu del Dia"]

        order = []

        # 2. Pick Items
        for _ in range(count):
            # Select Category
            cats = list(self.archetype.preferred_categories.keys())
            weights = list(self.archetype.preferred_categories.values())
            chosen_cat = random.choices(cats, weights=weights, k=1)[0]

            # Filter Menu
            options = [m for m in MENU_ITEMS if m.category == chosen_cat]
            if not options:
                # Fallback to Drink
                options = [m for m in MENU_ITEMS if m.category == "Drink"]

            if options:
                choice = random.choice(options)
                order.append(choice)

        return order
