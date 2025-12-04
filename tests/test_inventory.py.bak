import pytest
from restaurant_simulator.inventory import InventoryManager
from restaurant_simulator.menu import INGREDIENTS_DB

def test_initial_stock():
    inv = InventoryManager()
    # Check if stock is initialized to par levels
    for ing_id, ing in INGREDIENTS_DB.items():
        assert inv.stock[ing_id] == ing.par_level

def test_can_fulfill(sample_menu_item):
    inv = InventoryManager()
    # Mock stock for test ingredient
    ing_id = sample_menu_item.recipe[0].ingredient_id
    inv.stock = {ing_id: 10.0}

    # Needs 0.5 * 1 = 0.5. Have 10. Should pass.
    assert inv.can_fulfill(sample_menu_item, 1) is True

    # Needs 0.5 * 30 = 15. Have 10. Should fail.
    assert inv.can_fulfill(sample_menu_item, 30) is False

def test_deduct_item(sample_menu_item):
    inv = InventoryManager()
    ing_id = sample_menu_item.recipe[0].ingredient_id
    inv.stock = {ing_id: 10.0}

    inv.deduct_item(sample_menu_item, 2)
    # Deducted 0.5 * 2 = 1.0. Remaining 9.0.
    assert inv.stock[ing_id] == 9.0

def test_check_reorder(current_date):
    inv = InventoryManager()
    # Pick an ingredient to test
    ing_id = 101 # Rice
    ing = INGREDIENTS_DB[ing_id]

    # Set stock below reorder threshold
    inv.stock[ing_id] = ing.reorder_threshold - 1.0
    inv.pending_orders = []

    orders = inv.check_reorder(current_date)

    assert len(orders) == 1
    assert orders[0]['ingredient_id'] == ing_id
    # Should order enough to reach par
    expected_qty = ing.par_level - inv.stock[ing_id]
    assert orders[0]['qty'] == expected_qty
