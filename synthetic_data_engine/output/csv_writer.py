import csv
import os
from typing import List, Tuple, Dict
from datetime import datetime
from ..config.catalog import INGREDIENTS, MENU_ITEMS, MenuItem, Ingredient
from ..layers.calendar import DailyState
from ..simulation.kitchen import KitchenChaos # Intentionally misspelt in import for check? No, fix.

class CSVWriter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def write_static_catalogs(self):
        # 1. Ingredients
        with open(f"{self.output_dir}/ingredients.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["name", "cost_per_unit", "unit", "par_level", "reorder_threshold", "lead_time_days", "shelf_life_days"])
            for i in INGREDIENTS:
                writer.writerow([i.name, i.cost, i.unit, i.par, i.reorder, i.lead_time, i.shelf_life])

        # 2. Menu Items
        with open(f"{self.output_dir}/menu_items.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["name", "category", "price"])
            for m in MENU_ITEMS:
                writer.writerow([m.name, m.category, m.price])

        # 3. Recipes
        with open(f"{self.output_dir}/recipes.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["menu_item", "ingredient", "quantity"])
            for m in MENU_ITEMS:
                for ing_name, qty in m.recipe.items():
                    writer.writerow([m.name, ing_name, qty])

    def write_sales_log(self, all_orders: List[Tuple[datetime, MenuItem, str, str]]):
        # Format: timestamp,menu_item,quantity,total_price,service_type,customer_type
        # Note: Ingestion router expects: date, menu_item, quantity.
        # But for "FluxSim" analysis we want more detail.
        # We will produce TWO files: pos_sales.csv (for analysis) and sales.csv (for ingestion)

        # 1. Rich POS Log
        with open(f"{self.output_dir}/pos_sales_log.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "menu_item", "qty", "price", "service_type", "customer_type"])
            for ts, item, agent, service in all_orders:
                writer.writerow([ts.strftime("%Y-%m-%d %H:%M:%S"), item.name, 1, item.price, service, agent])

        # 2. Ingestion Format (Aggregation per day/item)
        # Aggregation needed? No, Ingestion router can handle rows.
        # But schema says `date: date`. So we strip time?
        # sales.csv: date,menu_item,quantity

        # Aggregate by day/item to reduce file size and match typical nightly batch
        daily_agg = {} # (date, item_name) -> qty
        for ts, item, _, _ in all_orders:
            k = (ts.date(), item.name)
            daily_agg[k] = daily_agg.get(k, 0) + 1

        with open(f"{self.output_dir}/sales.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "menu_item", "quantity"])
            for (d, item_name), qty in sorted(daily_agg.items()):
                writer.writerow([d, item_name, qty])

    def write_inventory_log(self, inventory_usage: List[Dict]):
        # inventory_usage is a list of {"date": date, "usage": {ing_name: qty}}
        with open(f"{self.output_dir}/inventory_usage.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "ingredient", "quantity_used"])
            for entry in inventory_usage:
                d = entry["date"]
                for ing, qty in entry["usage"].items():
                    writer.writerow([d, ing, round(qty, 4)])

    def write_external_factors(self, history: List[DailyState]):
        with open(f"{self.output_dir}/external_factors.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "temperature", "rain_mm", "is_weekend", "event_name", "event_impact"])
            for day in history:
                evt = day.event.name if day.event else ""
                imp = day.event.impact_type if day.event else ""
                writer.writerow([
                    day.date,
                    day.weather.temperature,
                    day.weather.rain_mm,
                    day.is_weekend,
                    evt,
                    imp
                ])
