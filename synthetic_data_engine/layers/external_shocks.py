from dataclasses import dataclass
from typing import Dict
from ..config.profiles import RestaurantProfile
from ..config.barcelona_calendar import BarcelonaEvent
from .weather import WeatherCondition

@dataclass
class DayContext:
    effective_capacity: int
    price_multiplier: float
    demand_multiplier: float
    delivery_surge: float

class ShockEngine:
    """Calculates the impact of Weather and Events on a specific Profile."""

    @staticmethod
    def calculate_impact(profile: RestaurantProfile, weather: WeatherCondition, event: BarcelonaEvent | None) -> DayContext:
        cap = profile.seating_capacity

        # 1. Weather Impact (Terrace)
        if weather.is_rainy or weather.temperature < 12.0:
            # Terrace closed
            pass
        else:
            # Terrace open
            cap += profile.terrace_capacity

        # 2. Demand & Pricing Multipliers (Base)
        demand_mult = 1.0
        price_mult = 1.0
        delivery_mult = 1.0

        # Rain Impact on Demand
        if weather.is_rainy:
            if weather.rain_mm > 2.0:
                demand_mult *= 0.6  # -40% footfall
                delivery_mult = 3.0 # +200% delivery
            else:
                demand_mult *= 0.8
                delivery_mult = 1.5

        # Event Impact
        if event:
            # MWC (Corporate cards)
            if event.name.startswith("MWC") and profile.location == "Eixample":
                price_mult = 1.4 # +40% Lunch Price
                demand_mult *= 1.2 # Busy

            # Sant Jordi (Crowded everywhere)
            if event.name == "Sant Jordi":
                demand_mult *= 1.5

            # Local Holidays (Locals leave, Tourists stay)
            if event.impact_type == "local_holiday":
                if profile.location == "Eixample":
                    demand_mult *= 0.5 # Locals gone
                else:
                    demand_mult *= 1.2 # Tourists maximize

        # Seasonality check (Chiringuito closed winter)
        # Note: Handled by open_months in profile, but demand might taper
        if profile.menu_theme == "beach_bar" and weather.temperature < 15:
            demand_mult *= 0.3

        return DayContext(
            effective_capacity=cap,
            price_multiplier=price_mult,
            demand_multiplier=demand_mult,
            delivery_surge=delivery_mult
        )
