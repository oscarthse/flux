from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Ingredient:
    name: str
    cost: float
    unit: str
    par: float
    reorder: float
    lead_time: int
    shelf_life: int

@dataclass
class MenuItem:
    name: str
    category: str
    price: float
    recipe: Dict[str, float] # Ingredient -> Qty

# --- 1. Ingredients Catalog ---
INGREDIENTS = [
    # Produce
    Ingredient("Potatoes", 0.50, "kg", 100, 20, 1, 14),
    Ingredient("Tomatoes", 1.20, "kg", 50, 10, 1, 7),
    Ingredient("Lettuce", 0.80, "head", 30, 5, 1, 5),
    Ingredient("Onions", 0.40, "kg", 40, 10, 2, 20),
    # Protein
    Ingredient("Beef Steak", 15.00, "kg", 20, 5, 2, 5),
    Ingredient("Chicken", 5.00, "kg", 40, 10, 2, 4),
    Ingredient("Seafood Mix", 12.00, "kg", 30, 5, 1, 3), # For Paella/Tapas
    Ingredient("Eggs", 0.20, "unit", 200, 50, 2, 21), # Tortilla
    # Pantry
    Ingredient("Rice (Bomba)", 2.00, "kg", 50, 10, 5, 180),
    Ingredient("Olive Oil", 6.00, "L", 20, 5, 3, 365),
    Ingredient("Flour", 0.80, "kg", 50, 10, 3, 180),
    # Alcohol/Bev
    Ingredient("Beer Keg (30L)", 60.00, "keg", 10, 2, 2, 60),
    Ingredient("Wine Bottle (Red)", 5.00, "btl", 60, 12, 3, 365),
    Ingredient("Sangria Mix", 3.00, "L", 20, 5, 2, 30),
    Ingredient("Coffee Beans", 12.00, "kg", 10, 2, 5, 90),
]

ING_MAP = {i.name: i for i in INGREDIENTS}

# --- 2. Menu Catalog ---
MENU_ITEMS = [
    # Tapas
    MenuItem("Patatas Bravas", "Tapas", 6.50, {"Potatoes": 0.3, "Olive Oil": 0.05}),
    MenuItem("Tortilla Espanola", "Tapas", 5.00, {"Eggs": 3, "Potatoes": 0.2, "Onions": 0.1, "Olive Oil": 0.05}),
    MenuItem("Gambas al Ajillo", "Tapas", 12.00, {"Seafood Mix": 0.2, "Olive Oil": 0.1}),

    # Mains
    MenuItem("Seafood Paella", "Paella", 18.00, {"Rice (Bomba)": 0.15, "Seafood Mix": 0.25, "Olive Oil": 0.05}),
    MenuItem("Grilled Steak", "Main", 22.00, {"Beef Steak": 0.3, "Potatoes": 0.2}),
    MenuItem("Chicken Roast", "Main", 14.00, {"Chicken": 0.4, "Potatoes": 0.2}),

    # Drinks
    MenuItem("Estrella Damm (Caña)", "Drink", 2.50, {"Beer Keg (30L)": 0.3}), # 0.3L
    MenuItem("Sangria Jug", "Drink", 16.00, {"Sangria Mix": 1.0}),
    MenuItem("Glass of Rioja", "Drink", 4.50, {"Wine Bottle (Red)": 0.15}),
    MenuItem("Cortado", "Drink", 1.80, {"Coffee Beans": 0.015}),

    # Menu del Dia Special (Abstracted)
    MenuItem("Menu del Dia", "Main", 14.50, {"Chicken": 0.3, "Potatoes": 0.2, "Lettuce": 0.1, "Beer Keg (30L)": 0.3}),
]
