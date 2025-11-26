import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from typing import Dict, List, Optional, Tuple

class ForecastEngine:
    def __init__(self):
        self.models = {}

    def train_model(self, sales_data: pd.DataFrame, item_id: int) -> Optional[SARIMAX]:
        """
        Trains a SARIMA model for a specific item.
        Expects sales_data to have 'date' and 'quantity' columns.
        """
        item_data = sales_data[sales_data['item_id'] == item_id].copy()
        if len(item_data) < 7:
            # Not enough data for a meaningful model
            return None

        item_data['date'] = pd.to_datetime(item_data['date'])
        item_data = item_data.set_index('date').asfreq('D').fillna(0)

        # Simple SARIMA (1,1,1)x(1,1,1,7) for weekly seasonality
        # In production, we would use auto_arima or grid search
        try:
            model = SARIMAX(
                item_data['quantity'],
                order=(1, 1, 1),
                seasonal_order=(1, 1, 1, 7),
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            results = model.fit(disp=False)
            self.models[item_id] = results
            return results
        except Exception as e:
            print(f"Error training model for item {item_id}: {e}")
            return None

    def predict_demand(self, item_id: int, days: int = 7) -> List[float]:
        """
        Returns predicted demand for the next N days.
        """
        model = self.models.get(item_id)
        if not model:
            return [0.0] * days

        forecast = model.forecast(steps=days)
        return forecast.tolist()
