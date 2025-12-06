from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class AgentArchetype:
    name: str
    patience_minutes: int
    alcohol_prob: float
    avg_items_ordered: int
    budget_sensitivity: float # 0.0 (unlimited) to 1.0 (very cheap)
    arrival_time_dist_lunch: Tuple[int, int] # (mean_hour, sigma_min) - simplified
    arrival_time_dist_dinner: Tuple[int, int]
    preferred_categories: Dict[str, float] # Weights for category choice

AGENTS = {
    "local": AgentArchetype(
        name="Local",
        patience_minutes=15,
        alcohol_prob=0.4,       # Caña or wine
        avg_items_ordered=3,    # Shared tapas
        budget_sensitivity=0.6,
        arrival_time_dist_lunch=(14, 30), # Late lunch (2pm)
        arrival_time_dist_dinner=(21, 30),# Late dinner (9pm)
        preferred_categories={"Tapas": 0.6, "Main": 0.2, "Drink": 0.2}
    ),
    "tourist": AgentArchetype(
        name="Tourist",
        patience_minutes=45,    # In vacation mode
        alcohol_prob=0.8,       # Sangria!
        avg_items_ordered=4,    # Appetizer + Paella + Dessert
        budget_sensitivity=0.2,
        arrival_time_dist_lunch=(13, 30), # Early lunch (1pm)
        arrival_time_dist_dinner=(19, 45),# Early dinner (7:30pm)
        preferred_categories={"Paella": 0.5, "Drink": 0.3, "Dessert": 0.2}
    ),
    "group": AgentArchetype(
        name="Group",
        patience_minutes=30,
        alcohol_prob=0.9,       # Social drinking
        avg_items_ordered=6,    # Heavy ordering
        budget_sensitivity=0.4,
        arrival_time_dist_lunch=(14, 0),
        arrival_time_dist_dinner=(21, 0),
        preferred_categories={"Tapas": 0.4, "Paella": 0.3, "Drink": 0.3}
    )
}
