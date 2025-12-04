"""
Moving Average forecasting model (baseline).

Simple yet effective baseline using trailing window average.
"""
from datetime import date, timedelta
from typing import List, Tuple, Dict
from .base import ForecastModel


class MovingAverageForecast(ForecastModel):
    """
    Moving average forecasting model.

    Uses trailing N-day window to calculate average daily sales,
    then projects that average forward.

    Args:
        window: Number of historical days to average (default 28)

    Example:
        >>> model = MovingAverageForecast(tenant_id, conn, window=28)
        >>> model.fit(sales_data)
        >>> predictions = model.predict('menu-item-123', forecast_days=30)
    """

    def __init__(self, tenant_id: str, conn, window: int = 28):
        """
        Initialize moving average model.

        Args:
            tenant_id: Tenant identifier
            conn: Database connection
            window: Trailing window size in days (default 28 = 4 weeks)
        """
        super().__init__(tenant_id, conn)
        self.window = window
        self.sales_by_item: Dict[str, List[Tuple[date, float]]] = {}

    @property
    def name(self) -> str:
        """Model identifier."""
        return f"moving_average_{self.window}d"

    def fit(self, sales_data: List[Tuple]) -> None:
        """
        Organize sales data by menu item.

        Args:
            sales_data: List of (menu_item_id, order_date, quantity) tuples
        """
        self.sales_by_item = {}

        for menu_item_id, order_date, quantity in sales_data:
            if menu_item_id not in self.sales_by_item:
                self.sales_by_item[menu_item_id] = []

            self.sales_by_item[menu_item_id].append((order_date, float(quantity)))

    def predict(self, menu_item_id: str, forecast_days: int) -> List[Tuple[date, float]]:
        """
        Generate predictions using trailing window average.

        Algorithm:
        1. Get last N days of sales for item
        2. Calculate average daily quantity
        3. Project average forward for forecast_days

        Args:
            menu_item_id: Menu item to forecast
            forecast_days: Number of days to predict

        Returns:
            List of (forecast_date, predicted_quantity) tuples
        """
        sales = self.sales_by_item.get(menu_item_id, [])

        # Handle items with no sales history
        if not sales:
            # Start from today if no history
            start_date = date.today()
            return [(start_date + timedelta(days=i), 0.0) for i in range(forecast_days)]

        # Calculate average from last N days
        recent_sales = sales[-self.window:] if len(sales) >= self.window else sales
        avg_daily_sales = sum(qty for _, qty in recent_sales) / len(recent_sales)

        # Start forecast from the day AFTER last historical date
        last_historical_date = max(d for d, _ in sales)
        start_date = last_historical_date + timedelta(days=1)

        predictions = []
        for i in range(forecast_days):
            forecast_date = start_date + timedelta(days=i)
            predictions.append((forecast_date, avg_daily_sales))

        return predictions
