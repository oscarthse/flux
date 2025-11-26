import pytest
from datetime import date
from restaurant_simulator.menu import MenuItem, Ingredient, RecipeItem

@pytest.fixture
def sample_ingredient():
    return Ingredient(
        id=1, name="Test Ingredient", unit="kg", cost_per_unit=10.0,
        shelf_life_days=10, supplier="Test Supplier", lead_time_days=1,
        par_level=10.0, reorder_threshold=2.0
    )

@pytest.fixture
def sample_menu_item(sample_ingredient):
    return MenuItem(
        id=1, name="Test Dish", category="Main", price=20.0,
        recipe=[RecipeItem(ingredient_id=sample_ingredient.id, quantity=0.5)]
    )

@pytest.fixture
def current_date():
    return date(2025, 1, 1)
