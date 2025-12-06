from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class RestaurantProfile:
    id: str
    name: str
    location: str
    agent_mix: Dict[str, float]  # e.g. {"tourist": 0.8, "local": 0.2}
    seating_capacity: int
    terrace_capacity: int
    avg_turnover_minutes_lunch: int
    avg_turnover_minutes_dinner: int
    open_months: List[int]       # 1-12
    weekend_heavy: bool          # True if weekends are significantly busier
    menu_theme: str              # "tapas", "fine_dining", "beach_bar"

PROFILES = {
    "la_boqueria_bites": RestaurantProfile(
        id="la_boqueria_bites",
        name="La Boqueria Bites",
        location="Ciutat Vella",
        agent_mix={"tourist": 0.80, "local": 0.10, "group": 0.10},
        seating_capacity=40,
        terrace_capacity=0,      # Tight space in market area
        avg_turnover_minutes_lunch=35,
        avg_turnover_minutes_dinner=45,
        open_months=list(range(1, 13)),
        weekend_heavy=False,     # Consistent tourist flow
        menu_theme="tapas"
    ),
    "eixample_elegance": RestaurantProfile(
        id="eixample_elegance",
        name="Eixample Elegance Test",
        location="Eixample",
        agent_mix={"tourist": 0.10, "local": 0.70, "group": 0.20}, # Business heavy
        seating_capacity=80,
        terrace_capacity=20,
        avg_turnover_minutes_lunch=60,  # Business lunch
        avg_turnover_minutes_dinner=120, # Sobremesa
        open_months=list(range(1, 13)), # Although August is dead, it's open
        weekend_heavy=True,
        menu_theme="fine_dining"
    ),
    "chiringuito_sol": RestaurantProfile(
        id="chiringuito_sol",
        name="Chiringuito Sol",
        location="Barceloneta",
        agent_mix={"tourist": 0.70, "local": 0.20, "group": 0.10},
        seating_capacity=30,
        terrace_capacity=100,    # Mostly outdoor
        avg_turnover_minutes_lunch=90,  # Paella takes time
        avg_turnover_minutes_dinner=90,
        open_months=[3, 4, 5, 6, 7, 8, 9, 10], # Closed Nov-Feb
        weekend_heavy=True,
        menu_theme="beach_bar"
    )
}
