from datetime import date
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class BarcelonaEvent:
    name: str
    impact_type: str # "business", "local_holiday", "tourist_spike"
    magnitude: float # Multiplier for demand or price

# 2025 Specific Dates
SPECIAL_EVENTS = {
    # MWC 2025 (Projected: Feb 26 - Mar 1)
    date(2025, 2, 26): BarcelonaEvent("MWC Day 1", "business", 1.4),
    date(2025, 2, 27): BarcelonaEvent("MWC Day 2", "business", 1.4),
    date(2025, 2, 28): BarcelonaEvent("MWC Day 3", "business", 1.4),
    date(2025, 3, 1):  BarcelonaEvent("MWC Day 4", "business", 1.2),

    # Sant Jordi
    date(2025, 4, 23): BarcelonaEvent("Sant Jordi", "local_holiday", 1.3),

    # Sant Joan (Eve + Day)
    date(2025, 6, 23): BarcelonaEvent("Sant Joan Eve", "party", 1.5),
    date(2025, 6, 24): BarcelonaEvent("Sant Joan", "local_holiday", 0.5), # Hangover day

    # Diada
    date(2025, 9, 11): BarcelonaEvent("La Diada", "local_holiday", 0.8), # Protests/Closed

    # La Mercè
    date(2025, 9, 24): BarcelonaEvent("La Mercè", "local_holiday", 1.2),
}

def get_event(d: date) -> Optional[BarcelonaEvent]:
    return SPECIAL_EVENTS.get(d)
