import pytest
from datetime import datetime
from restaurant_simulator.inventory import InventoryManager
from restaurant_simulator.menu import MenuItem, RecipeItem, Ingredient
from restaurant_simulator.demand import Order, OrderItem

# Mock Menu
RICE_ID = 101
SEAFOOD_ID = 102
WINE_ID = 105

@pytest.fixture
def mock_menu_map():
    return {
        1: MenuItem(1, "Paella", "Main", 30.0, [RecipeItem(RICE_ID, 0.2), RecipeItem(SEAFOOD_ID, 0.4)]),
        2: MenuItem(2, "Wine", "Beverage", 20.0, [RecipeItem(WINE_ID, 1.0)])
    }

@pytest.fixture
def inventory_manager():
    inv = InventoryManager()
    # Reset stock
    inv.stock = {}
    return inv

def test_partial_fulfillment(inventory_manager, mock_menu_map):
    # Setup: Plenty of Rice and Seafood, NO Wine
    inventory_manager.stock[RICE_ID] = 100.0
    inventory_manager.stock[SEAFOOD_ID] = 100.0
    inventory_manager.stock[WINE_ID] = 0.0 # Out of stock

    # Order: 1 Paella, 1 Wine
    order_intent = Order(
        id="1", timestamp=datetime.now(), party_size=2,
        items=[
            OrderItem(menu_item_id=1, quantity=1, price_at_order=30.0),
            OrderItem(menu_item_id=2, quantity=1, price_at_order=20.0)
        ],
        total_amount=50.0
    )

    # Simulate Logic (Copy-paste logic from simulation.py effectively, or extract method if refactored)
    # Since we didn't extract a method in simulation.py, we are testing the logic by replicating the loop
    # Ideally, we should refactor simulation.py to have a `process_order` method, but for now we test the concept
    # or we can write an integration test that mocks the inventory module.

    # Let's verify the InventoryManager.can_fulfill behavior first
    paella = mock_menu_map[1]
    wine = mock_menu_map[2]

    assert inventory_manager.can_fulfill(paella, 1) is True
    assert inventory_manager.can_fulfill(wine, 1) is False

    # Now simulate the loop
    fulfilled_items = []
    lost_sales = []

    for item in order_intent.items:
        menu_item = mock_menu_map.get(item.menu_item_id)
        if inventory_manager.can_fulfill(menu_item, item.quantity):
            inventory_manager.deduct_item(menu_item, item.quantity)
            fulfilled_items.append(item)
        else:
            lost_sales.append(item)

    # Assertions
    assert len(fulfilled_items) == 1
    assert fulfilled_items[0].menu_item_id == 1 # Paella fulfilled

    assert len(lost_sales) == 1
    assert lost_sales[0].menu_item_id == 2 # Wine lost

    # Verify Stock Deductions
    assert inventory_manager.stock[RICE_ID] == 99.8 # 100 - 0.2
    assert inventory_manager.stock[WINE_ID] == 0.0
