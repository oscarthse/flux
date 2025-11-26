from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Ingredient:
    id: int
    name: str
    unit: str
    cost_per_unit: float
    shelf_life_days: int
    supplier: str
    lead_time_days: int
    par_level: float
    reorder_threshold: float

@dataclass
class RecipeItem:
    ingredient_id: int
    quantity: float

@dataclass
class MenuItem:
    id: int
    name: str
    category: str
    price: float
    recipe: List[RecipeItem]

# Define Ingredients
INGREDIENTS_DB = {
    # Usage Analysis (Revised based on Sim Data):
    # Demand is ~300 covers/day. Wine is sole beverage -> 300 bottles/day.
    # Eggs ~600/day. Potatoes ~100kg/day.

    # Rice: Par 300 -> 600. Reorder 100 -> 200.
    101: Ingredient(101, "Bomba Rice", "kg", 2.0, 180, "Wholesaler A", 2, 600.0, 200.0),

    # Seafood: Par 200 -> 400. Reorder 80 -> 160.
    102: Ingredient(102, "Mixed Seafood", "kg", 12.0, 2, "Fishmonger", 1, 400.0, 160.0),

    # Potatoes: Par 600 -> 1200. Reorder 250 -> 500.
    103: Ingredient(103, "Potatoes", "kg", 0.8, 14, "Farm Direct", 2, 1200.0, 500.0),

    # Eggs: Par 3000 -> 6000. Reorder 1500 -> 3000.
    104: Ingredient(104, "Eggs", "piece", 0.2, 21, "Farm Direct", 2, 6000.0, 3000.0),

    # Wine: Usage ~250/day. Lead 3d. Usage during lead = 750. Needs buffer.
    # Par 1000 -> 2500. Reorder 500 -> 1200.
    105: Ingredient(105, "Red Wine", "bottle", 4.0, 365, "Vinos SL", 3, 2500.0, 1200.0),

    # Milk: Par 150 -> 300. Reorder 50 -> 100.
    106: Ingredient(106, "Milk", "liter", 0.9, 7, "Dairy Co", 1, 300.0, 100.0),

    # Sugar: Par 50 -> 100. Reorder 20 -> 40.
    107: Ingredient(107, "Sugar", "kg", 1.0, 365, "Wholesaler A", 2, 100.0, 40.0),

    # Saffron: Par 50 -> 100. Reorder 20 -> 40.
    108: Ingredient(108, "Saffron", "g", 5.0, 365, "Spice Trader", 5, 100.0, 40.0),

    # Oil: Par 200 -> 400. Reorder 80 -> 160.
    109: Ingredient(109, "Olive Oil", "liter", 6.0, 365, "Wholesaler A", 2, 400.0, 160.0),

    # NEW: Water
    110: Ingredient(110, "Mineral Water", "bottle", 0.5, 365, "Wholesaler A", 1, 1000.0, 300.0),
}

# Define Menu
MENU_DB = [
    MenuItem(1, "Patatas Bravas", "Starter", 6.50, [
        RecipeItem(103, 0.3), # 300g potatoes
        RecipeItem(109, 0.05) # 50ml oil
    ]),
    MenuItem(2, "Seafood Paella (for 2)", "Main", 32.00, [
        RecipeItem(101, 0.2), # 200g rice
        RecipeItem(102, 0.4), # 400g seafood
        RecipeItem(108, 0.001), # 1g saffron
        RecipeItem(109, 0.05)
    ]),
    MenuItem(3, "Tortilla Española", "Starter", 8.00, [
        RecipeItem(103, 0.2),
        RecipeItem(104, 4.0), # 4 eggs
        RecipeItem(109, 0.05)
    ]),
    MenuItem(4, "Crema Catalana", "Dessert", 6.00, [
        RecipeItem(106, 0.2), # 200ml milk
        RecipeItem(104, 2.0), # 2 eggs (yolks)
        RecipeItem(107, 0.05) # 50g sugar
    ]),
    MenuItem(5, "House Red Wine", "Beverage", 18.00, [
        RecipeItem(105, 1.0) # 1 bottle
    ]),
    MenuItem(6, "Menu del Día", "Set Menu", 15.00, [
        # Simplified: Average consumption for a set menu
        RecipeItem(103, 0.2), # Potatoes
        RecipeItem(104, 1.0), # Egg
        RecipeItem(106, 0.1), # Milk
        RecipeItem(109, 0.05) # Oil
    ]),
    MenuItem(7, "Mineral Water", "Beverage", 2.50, [
        RecipeItem(110, 1.0)
    ])
]

def get_menu_items_by_category(category: str) -> List[MenuItem]:
    return [item for item in MENU_DB if item.category == category]
