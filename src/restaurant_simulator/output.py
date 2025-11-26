import csv
import os
from typing import List, Any
from .demand import Order

class OutputManager:
    def __init__(self, output_dir: str = "output_data"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Initialize files with headers
        self._init_csv("orders.csv", ["order_id", "timestamp", "party_size", "total_amount"])
        self._init_csv("order_items.csv", ["order_id", "menu_item_id", "quantity", "price_at_order"])
        self._init_csv("inventory_log.csv", ["date", "ingredient_id", "opening_stock", "used_qty", "restock_qty", "waste_qty", "closing_stock"])
        self._init_csv("staff_schedule.csv", ["date", "role", "count", "cost"])
        self._init_csv("lost_sales.csv", ["timestamp", "party_size", "reason", "potential_revenue"])

    def _init_csv(self, filename: str, headers: List[str]):
        filepath = os.path.join(self.output_dir, filename)
        # Overwrite mode for new simulation run
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def _append_csv(self, filename: str, rows: List[List[Any]]):
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def save_orders(self, orders: List[Order]):
        order_rows = []
        item_rows = []
        for o in orders:
            order_rows.append([o.id, o.timestamp.isoformat(), o.party_size, o.total_amount])
            for item in o.items:
                item_rows.append([o.id, item.menu_item_id, item.quantity, item.price_at_order])

        self._append_csv("orders.csv", order_rows)
        self._append_csv("order_items.csv", item_rows)

    def save_inventory_log(self, log_entries: List[dict]):
        # Expects dict with keys matching header
        rows = []
        for entry in log_entries:
            rows.append([
                entry['date'], entry['ingredient_id'],
                entry['opening_stock'], entry['used_qty'],
                entry['restock_qty'], entry['waste_qty'],
                entry['closing_stock']
            ])
        self._append_csv("inventory_log.csv", rows)

    def save_staff_schedule(self, schedule: List[dict]):
        rows = []
        for s in schedule:
            rows.append([s['date'], s['role'], s['count'], s['cost']])
        self._append_csv("staff_schedule.csv", rows)

    def save_lost_sales(self, lost_sales: List[dict]):
        rows = []
        for s in lost_sales:
            rows.append([s['timestamp'], s['party_size'], s['reason'], s['potential_revenue']])
        self._append_csv("lost_sales.csv", rows)
