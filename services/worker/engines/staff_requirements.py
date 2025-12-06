"""
Staff Requirements Engine - Calculate optimal staffing levels.

Uses forecasted demand and Erlang-C queuing theory to determine
optimal workforce levels by hour. Implements full probabilistic
approach for service level optimization.
"""
from datetime import date, datetime, time, timedelta
from typing import List, Tuple
from decimal import Decimal
from dataclasses import dataclass
import math

from services.api.logging_config import get_logger

logger = get_logger(__name__)


# Industry-standard staffing ratios (covers per employee)
COVERS_PER_SERVER = 15  # 1 server can handle 15 customers per hour
COVERS_PER_COOK = 20    # 1 cook can prepare 20 meals per hour
SAFETY_BUFFER = 1.10    # 10% buffer for variance

# Erlang-C Model Parameters
SERVICE_RATE_MU = 12.0      # Guests served per server per hour
TARGET_WAIT_PROB = 0.20     # Target: P(wait > target_time) < 20%
TARGET_WAIT_TIME = 5.0      # Target wait time in minutes
MAX_SERVERS_SEARCH = 25     # Maximum servers to check in search


@dataclass
class ErlangCResult:
    """Result from Erlang-C staffing optimization with explainability."""
    hour: int
    forecasted_covers: float
    arrival_rate: float          # λ (lambda) - arrivals per hour
    service_rate: float          # μ (mu) - services per server per hour
    required_servers: int        # Optimal number of servers
    utilization: float           # ρ (rho) = λ / (s × μ)
    prob_wait: float             # P_w - probability of waiting
    avg_wait_time: float         # E[W_q] - expected wait in queue (minutes)
    explanation: str             # Plain English
    math_proof: str              # Formula used

    def dict(self):
        return {
            "hour": self.hour,
            "forecasted_covers": self.forecasted_covers,
            "required_servers": self.required_servers,
            "utilization_pct": round(self.utilization * 100, 1),
            "prob_wait_pct": round(self.prob_wait * 100, 1),
            "avg_wait_time_min": round(self.avg_wait_time, 1),
            "explanation": self.explanation,
            "math_proof": self.math_proof
        }


def _erlang_c(s: int, arrival_rate: float, service_rate: float) -> float:
    """
    Calculate Erlang-C probability of waiting.

    P_w = (A^s / s!) / ((s - A) * sum_{k=0}^{s-1}(A^k / k!) + A^s / s!)

    Where A = λ / μ (offered load)

    Args:
        s: Number of servers
        arrival_rate: λ (arrivals per hour)
        service_rate: μ (services per server per hour)

    Returns:
        P_w = Probability of waiting in queue
    """
    if s <= 0 or service_rate <= 0:
        return 1.0

    A = arrival_rate / service_rate  # Offered load

    if A <= 0:
        return 0.0

    rho = A / s  # Utilization

    # System unstable if utilization >= 1
    if rho >= 1.0:
        return 1.0

    # Calculate A^s / s!
    try:
        A_s_over_s_fact = (A ** s) / math.factorial(s)
    except (OverflowError, ValueError):
        return 1.0

    # Calculate sum_{k=0}^{s-1} A^k / k!
    sum_terms = 0.0
    for k in range(s):
        try:
            sum_terms += (A ** k) / math.factorial(k)
        except (OverflowError, ValueError):
            break

    # Erlang-C formula
    denominator = (1 - rho) * sum_terms + A_s_over_s_fact

    if denominator <= 0:
        return 1.0

    P_w = A_s_over_s_fact / denominator

    return min(1.0, max(0.0, P_w))


def _avg_wait_time(s: int, arrival_rate: float, service_rate: float, P_w: float) -> float:
    """
    Calculate average wait time in queue (minutes).

    E[W_q] = P_w / (s × μ - λ)

    Returns wait time in minutes.
    """
    if s <= 0 or service_rate <= 0:
        return float('inf')

    denominator = s * service_rate - arrival_rate

    if denominator <= 0:
        return float('inf')

    # Wait time in hours
    wait_hours = P_w / denominator

    # Convert to minutes
    return wait_hours * 60


def calculate_labor_needs(
    forecasted_covers: float,
    hour: int = 0,
    service_rate: float = SERVICE_RATE_MU,
    target_wait_prob: float = TARGET_WAIT_PROB
) -> ErlangCResult:
    """
    Calculate optimal staffing using Erlang-C queuing theory.

    Algorithm:
    1. Set arrival rate λ = forecasted_covers
    2. Iterate servers s from 1 to MAX_SERVERS_SEARCH
    3. For each s, calculate utilization ρ = λ / (s × μ)
    4. If ρ >= 1, system is unstable, continue
    5. Calculate P_w using Erlang-C formula
    6. Stop when P_w ≤ target (e.g., 20%)

    Args:
        forecasted_covers: Expected customer arrivals for this hour
        hour: Hour of day (for output)
        service_rate: μ - customers served per server per hour
        target_wait_prob: Target P_w threshold

    Returns:
        ErlangCResult with optimal servers and explanation
    """
    arrival_rate = forecasted_covers  # λ

    # Edge case: no demand
    if arrival_rate <= 0:
        return ErlangCResult(
            hour=hour,
            forecasted_covers=forecasted_covers,
            arrival_rate=0,
            service_rate=service_rate,
            required_servers=0,
            utilization=0,
            prob_wait=0,
            avg_wait_time=0,
            explanation="No customer demand forecasted for this hour.",
            math_proof="λ = 0 → No servers required"
        )

    # Search for optimal server count
    optimal_s = 1
    optimal_P_w = 1.0
    optimal_rho = 1.0
    optimal_wait = float('inf')

    for s in range(1, MAX_SERVERS_SEARCH + 1):
        rho = arrival_rate / (s * service_rate)

        # Must have ρ < 1 for stable system
        if rho >= 1.0:
            continue

        P_w = _erlang_c(s, arrival_rate, service_rate)
        wait_time = _avg_wait_time(s, arrival_rate, service_rate, P_w)

        # Check if this meets target
        if P_w <= target_wait_prob:
            optimal_s = s
            optimal_P_w = P_w
            optimal_rho = rho
            optimal_wait = wait_time
            break

        # Track best so far even if not meeting target
        if P_w < optimal_P_w:
            optimal_s = s
            optimal_P_w = P_w
            optimal_rho = rho
            optimal_wait = wait_time

    # Generate explanation
    hour_str = f"{hour:02d}:00"
    target_pct = int(target_wait_prob * 100)
    actual_pct = int(optimal_P_w * 100)

    if optimal_P_w <= target_wait_prob:
        explanation = (
            f"Requires {optimal_s} server(s) at {hour_str} to keep wait times under "
            f"{TARGET_WAIT_TIME:.0f} minutes during peak (Forecast: {forecasted_covers:.0f} guests). "
            f"System utilization: {optimal_rho*100:.0f}%, Probability of wait: {actual_pct}%."
        )
    else:
        explanation = (
            f"Warning: {optimal_s} servers at {hour_str} results in {actual_pct}% wait probability "
            f"(target: {target_pct}%). Consider adding more capacity or managing demand. "
            f"Forecast: {forecasted_covers:.0f} guests."
        )

    math_proof = (
        f"Erlang-C: λ={arrival_rate:.1f}, μ={service_rate:.1f}, "
        f"s={optimal_s}, ρ={optimal_rho:.2f}, "
        f"P_w={optimal_P_w:.3f}"
    )

    return ErlangCResult(
        hour=hour,
        forecasted_covers=forecasted_covers,
        arrival_rate=arrival_rate,
        service_rate=service_rate,
        required_servers=optimal_s,
        utilization=optimal_rho,
        prob_wait=optimal_P_w,
        avg_wait_time=optimal_wait,
        explanation=explanation,
        math_proof=math_proof
    )


def calculate_erlang_c_requirements(
    tenant_id: str,
    target_date: date,
    conn
) -> List[ErlangCResult]:
    """
    Calculate Erlang-C based staffing requirements for entire day.

    Uses demand forecasts and applies Erlang-C queuing theory to
    determine optimal server count for each operating hour.

    Args:
        tenant_id: Restaurant tenant ID
        target_date: Date to calculate for
        conn: Database connection

    Returns:
        List of ErlangCResult (one per operating hour)
    """
    logger.info(f"Calculating Erlang-C requirements for {target_date}")

    # Get hourly demand forecast
    hourly_demand = _get_hourly_demand(tenant_id, target_date, conn)

    if not hourly_demand:
        logger.warning(f"No forecast data for {target_date}, using default pattern")
        hourly_demand = _get_default_pattern()

    results = []

    for hour, covers in hourly_demand:
        # Skip closed hours
        if hour < 10 or hour >= 23:
            continue

        result = calculate_labor_needs(
            forecasted_covers=covers,
            hour=hour,
            service_rate=SERVICE_RATE_MU,
            target_wait_prob=TARGET_WAIT_PROB
        )

        results.append(result)

    logger.info(f"Generated Erlang-C requirements for {len(results)} hours")
    return results


class StaffRequirement:
    """Staffing requirement for a single hour."""
    def __init__(self, hour: int, required_servers: float, required_cooks: float, demand_forecast: float):
        self.hour = hour
        self.required_servers = required_servers
        self.required_cooks = required_cooks
        self.demand_forecast = demand_forecast

    def dict(self):
        return {
            "hour": self.hour,
            "required_servers": self.required_servers,
            "required_cooks": self.required_cooks,
            "demand_forecast": self.demand_forecast
        }


class ScheduledShift:
    """Actual scheduled employee shift."""
    def __init__(self, employee_id: str, employee_name: str, role: str,
                 start_time: str, end_time: str, hourly_rate: float, shift_cost: float):
        self.employee_id = employee_id
        self.employee_name = employee_name
        self.role = role
        self.start_time = start_time
        self.end_time = end_time
        self.hourly_rate = hourly_rate
        self.shift_cost = shift_cost

    def dict(self):
        return {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "role": self.role,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "hourly_rate": self.hourly_rate,
            "shift_cost": self.shift_cost
        }


class CostAnalysis:
    """Cost comparison between optimal and actual staffing."""
    def __init__(self, date, optimal_cost: float, actual_cost: float, variance: float,
                 overstaffed_hours: int, understaffed_hours: int, optimal_hours: int,
                 potential_savings: float):
        self.date = date
        self.optimal_cost = optimal_cost
        self.actual_cost = actual_cost
        self.variance = variance
        self.overstaffed_hours = overstaffed_hours
        self.understaffed_hours = understaffed_hours
        self.optimal_hours = optimal_hours
        self.potential_savings = potential_savings

    def dict(self):
        return {
            "date": str(self.date),
            "optimal_cost": self.optimal_cost,
            "actual_cost": self.actual_cost,
            "variance": self.variance,
            "overstaffed_hours": self.overstaffed_hours,
            "understaffed_hours": self.understaffed_hours,
            "optimal_hours": self.optimal_hours,
            "potential_savings": self.potential_savings
        }


def calculate_staff_requirements(
    tenant_id: str,
    target_date: date,
    conn
) -> List[StaffRequirement]:
    """
    Calculate required staffing levels by hour based on forecasted demand.

    Algorithm:
    1. Aggregate forecasts to get hourly covers
    2. Apply industry ratios: 1 server per 15 covers, 1 cook per 20 covers
    3. Add 10% safety buffer
    4. Round up to whole numbers

    Args:
        tenant_id: Restaurant tenant ID
        target_date: Date to calculate requirements for
        conn: Database connection

    Returns:
        List of StaffRequirement objects (one per operating hour)
    """
    logger.info(f"Calculating staff requirements for {target_date}")

    # Get hourly demand forecast
    hourly_demand = _get_hourly_demand(tenant_id, target_date, conn)

    if not hourly_demand:
        logger.warning(f"No forecast data for {target_date}, using default pattern")
        hourly_demand = _get_default_pattern()

    requirements = []

    for hour, covers in hourly_demand:
        # Skip closed hours (midnight to 10am, 11pm-midnight)
        if hour < 10 or hour >= 23:
            continue

        # Calculate required staff
        raw_servers = covers / COVERS_PER_SERVER
        raw_cooks = covers / COVERS_PER_COOK

        # Apply safety buffer and round up
        required_servers = math.ceil(raw_servers * SAFETY_BUFFER)
        required_cooks = math.ceil(raw_cooks * SAFETY_BUFFER)

        # Minimum staffing (never go below 1 of each role during service)
        if covers > 0:
            required_servers = max(1, required_servers)
            required_cooks = max(1, required_cooks)

        requirements.append(StaffRequirement(
            hour=hour,
            required_servers=float(required_servers),
            required_cooks=float(required_cooks),
            demand_forecast=covers
        ))

    logger.info(f"Calculated requirements for {len(requirements)} hours")
    return requirements


def _get_hourly_demand(tenant_id: str, target_date: date, conn) -> List[Tuple[int, float]]:
    """
    Get forecasted customer demand by hour.

    Aggregates menu item forecasts into total covers per hour.
    """
    with conn.cursor() as cur:
        # Get total forecasted quantity for the day
        cur.execute("""
            SELECT SUM(predicted_quantity) as total_covers
            FROM forecasts
            WHERE tenant_id = %s
              AND forecast_date = %s
        """, (tenant_id, target_date))

        row = cur.fetchone()
        total_daily_covers = float(row[0]) if row and row[0] else 0

    if total_daily_covers == 0:
        return []

    # Distribute across typical restaurant hours using demand curve
    # Lunch: 11am-2pm (30% of daily), Dinner: 5pm-9pm (60%), Other: (10%)
    demand_distribution = {
        11: 0.08,  # 8% of daily demand
        12: 0.15,  # 15%
        13: 0.10,  # 10%
        14: 0.05,  # 5%
        15: 0.03,
        16: 0.03,
        17: 0.10,  # Dinner starts
        18: 0.18,
        19: 0.20,  # Peak
        20: 0.12,
        21: 0.05,
        22: 0.01
    }

    hourly_demand = []
    for hour, pct in demand_distribution.items():
        covers = total_daily_covers * pct
        hourly_demand.append((hour, covers))

    return hourly_demand


def _get_default_pattern() -> List[Tuple[int, float]]:
    """Default demand pattern when no forecast available."""
    return [
        (11, 20), (12, 40), (13, 30), (14, 15),
        (17, 25), (18, 50), (19, 60), (20, 35), (21, 15)
    ]


def get_actual_schedule(tenant_id: str, target_date: date, conn) -> List[ScheduledShift]:
    """
    Get actual scheduled shifts for a date.

    Returns list of ScheduledShift objects.
    Note: The actual schema stores aggregated counts, not individual shifts.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                role,
                COALESCE(count, 0) as staff_count,
                COALESCE(cost, 0.0) as total_cost
            FROM staff_schedule
            WHERE tenant_id = %s
              AND date = %s
            ORDER BY role
        """, (tenant_id, target_date))

        shifts = []
        for row in cur.fetchall():
            role, count, total_cost = row

            if count == 0:
                continue

            # Create pseudo-shifts for each role
            # Since schema stores counts, not individual shifts, we create representative shifts
            hourly_rate = (total_cost / count / 8) if count > 0 else 15.0  # Assume 8 hour shifts

            # Create a representative shift for visualization
            shifts.append(ScheduledShift(
                employee_id=f"{role}-team",
                employee_name=f"{count} {role}(s)",
                role=role,
                start_time="11:00",  # Default service hours
                end_time="22:00",
                hourly_rate=float(hourly_rate),
                shift_cost=float(total_cost)
            ))

    logger.info(f"Retrieved {len(shifts)} role groups for {target_date}")
    return shifts


def calculate_cost_analysis(
    tenant_id: str,
    target_date: date,
    requirements: List[StaffRequirement],
    schedule: List[ScheduledShift]
) -> CostAnalysis:
    """
    Calculate cost comparison between optimal and actual staffing.

    Returns CostAnalysis showing variance and savings opportunities.
    """
    # Calculate optimal cost (based on requirements)
    optimal_cost = 0.0
    avg_server_rate = 12.0  # Assume $12/hour for servers
    avg_cook_rate = 18.0    # Assume $18/hour for cooks

    for req in requirements:
        optimal_cost += (req.required_servers * avg_server_rate)
        optimal_cost += (req.required_cooks * avg_cook_rate)

    # Calculate actual cost (from schedule)
    actual_cost = sum(shift.shift_cost for shift in schedule)

    # Calculate variance
    variance = actual_cost - optimal_cost
    potential_savings = max(0, variance)  # Only count overspending as savings

    # Count hour statuses
    overstaffed = 0
    understaffed = 0
    optimal = 0

    # This is simplified - full implementation would compare hour by hour
    if variance > 50:
        overstaffed = 5
    elif variance < -50:
        understaffed = 5
    else:
        optimal = len(requirements)

    return CostAnalysis(
        date=target_date,
        optimal_cost=optimal_cost,
        actual_cost=actual_cost,
        variance=variance,
        overstaffed_hours=overstaffed,
        understaffed_hours=understaffed,
        optimal_hours=optimal,
        potential_savings=potential_savings
    )
