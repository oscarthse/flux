import numpy as np
from scipy.stats import norm
from typing import Dict, List, Tuple

class InventoryOptimizer:
    def calculate_optimal_par(self,
                            mean_demand: float,
                            std_dev_demand: float,
                            cost_per_unit: float,
                            price_per_unit: float,
                            shelf_life_days: int) -> float:
        """
        Calculates the optimal inventory level (Par Level) using the Newsvendor Model.

        Cu (Underage Cost) = Profit Margin = Price - Cost
        Co (Overage Cost) = Cost per unit (assuming 100% loss if spoiled, simplified)

        Critical Ratio (CR) = Cu / (Cu + Co)
        Optimal Q = InverseCDF(CR) * std_dev + mean
        """
        if std_dev_demand == 0:
            return mean_demand

        cu = price_per_unit - cost_per_unit
        co = cost_per_unit # Simplified: assuming waste if not sold within shelf life

        # Adjust Co for shelf life: if shelf life is long, risk of waste is lower per day
        # This is a heuristic adjustment for the single-period Newsvendor model applied to multi-period
        # Effective Co decreases as shelf life increases
        effective_co = co / max(1, shelf_life_days)

        critical_ratio = cu / (cu + effective_co)

        # Z-score for the critical ratio
        z_score = norm.ppf(critical_ratio)

        optimal_qty = mean_demand + z_score * std_dev_demand
        return max(0, optimal_qty)

    def calculate_flux_sharpe(self,
                            current_par: float,
                            optimal_par: float,
                            mean_demand: float,
                            std_dev_demand: float,
                            cost_per_unit: float,
                            price_per_unit: float) -> float:
        """
        Calculates the FluxSharpe score: A risk-adjusted measure of how 'good' the current decision is.

        FluxSharpe = (Expected Profit(Current) - Expected Profit(Baseline)) / Risk

        For MVP, we simplify:
        Score = 1.0 - (Abs(Current - Optimal) / Optimal)
        Scaled 0-100.
        100 = Perfect alignment with Optimal.
        0 = Far off.
        """
        if optimal_par == 0:
            return 0.0

        deviation = abs(current_par - optimal_par)
        score = max(0, 1.0 - (deviation / optimal_par)) * 100
        return round(score, 1)
