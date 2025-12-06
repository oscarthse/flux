"""
Staff Optimization Router - API endpoints for workforce planning.

Provides staffing requirements calculation, schedule management,
and cost analysis for restaurant labor optimization.
"""
from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from datetime import date, datetime, time, timedelta
from typing import List, Optional
from decimal import Decimal

from services.api.database import db_service
from services.api.config import settings, get_settings
from services.api.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/staff", tags=["staff"])
templates = Jinja2Templates(directory="services/api/templates")


# ==================== Data Models ====================

class StaffRequirement(BaseModel):
    """Required staffing levels for a specific hour."""
    hour: int  # 0-23
    required_servers: float
    required_cooks: float
    demand_forecast: float  # Covers per hour


class ScheduledShift(BaseModel):
    """An actual scheduled employee shift."""
    employee_id: str
    employee_name: str
    role: str
    start_time: str  # HH:MM format
    end_time: str
    hourly_rate: float
    shift_cost: float


class HourlyStaffing(BaseModel):
    """Staffing comparison for a single hour."""
    hour: int
    hour_display: str  # "11 AM"
    demand: float
    required_servers: int
    required_cooks: int
    actual_servers: int
    actual_cooks: int
    status: str  # "optimal", "over", "under"
    variance_cost: float  # Positive = overstaffed cost


class CostAnalysis(BaseModel):
    """Cost comparison between optimal and actual staffing."""
    date: date
    optimal_cost: float
    actual_cost: float
    variance: float  # Positive = overspending
    overstaffed_hours: int
    understaffed_hours: int
    optimal_hours: int
    potential_savings: float


# ==================== Endpoints ====================

@router.get("/", response_class=HTMLResponse)
async def staff_dashboard(
    request: Request,
    target_date: Optional[date] = None,
    settings=Depends(get_settings)
):
    """
    Main staff optimization dashboard.

    Shows staffing requirements, actual schedule, and cost analysis.
    """

    from services.api.context import tenant_context
    tenant_id = tenant_context.get()
    if not tenant_id:
        return HTMLResponse("<div>Error: Not authenticated</div>", status_code=401)

    if target_date is None:
        target_date = date.today()

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            # Get staffing requirements and schedule
            from services.worker.engines.staff_requirements import (
                calculate_staff_requirements,
                get_actual_schedule,
                calculate_cost_analysis,
                CostAnalysis as EngineCostAnalysis,
                StaffRequirement as EngineStaffRequirement,
                ScheduledShift as EngineScheduledShift
            )

            requirements = calculate_staff_requirements(tenant_id, target_date, conn)
            schedule = get_actual_schedule(tenant_id, target_date, conn)
            cost_analysis_obj = calculate_cost_analysis(tenant_id, target_date, requirements, schedule)

            # Convert engine objects to Pydantic models
            cost_analysis = CostAnalysis(
                date=cost_analysis_obj.date,
                optimal_cost=cost_analysis_obj.optimal_cost,
                actual_cost=cost_analysis_obj.actual_cost,
                variance=cost_analysis_obj.variance,
                overstaffed_hours=cost_analysis_obj.overstaffed_hours,
                understaffed_hours=cost_analysis_obj.understaffed_hours,
                optimal_hours=cost_analysis_obj.optimal_hours,
                potential_savings=cost_analysis_obj.potential_savings
            )

            hourly_comparison = _build_hourly_comparison(requirements, schedule, target_date)
            recommendations = _generate_recommendations(hourly_comparison)

        return templates.TemplateResponse("staff/main.html", {
            "request": request,
            "target_date": target_date,
            "cost_analysis": cost_analysis,
            "hourly_staffing": hourly_comparison,
            "schedule": schedule,
            "recommendations": recommendations
        })

    except Exception as e:
        logger.error(f"Staff dashboard error: {e}", exc_info=True)

        # Return error state with fallback data
        fallback_cost = CostAnalysis(
            date=target_date,
            optimal_cost=0.0,
            actual_cost=0.0,
            variance=0.0,
            overstaffed_hours=0,
            understaffed_hours=0,
            optimal_hours=0,
            potential_savings=0.0
        )

        return templates.TemplateResponse("staff/main.html", {
            "request": request,
            "target_date": target_date,
            "cost_analysis": fallback_cost,
            "hourly_staffing": [],
            "schedule": [],
            "recommendations": [f"Error loading data: {str(e)}"],
            "error": str(e)
        })


@router.get("/requirements")
async def get_requirements(
    target_date: date = Query(...),
    settings=Depends(get_settings)
):
    """Get calculated staffing requirements for a date."""

    from services.api.context import tenant_context
    tenant_id = tenant_context.get()
    if not tenant_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            from services.worker.engines.staff_requirements import calculate_staff_requirements

            requirements = calculate_staff_requirements(tenant_id, target_date, conn)

        return JSONResponse({
            "status": "success",
            "date": str(target_date),
            "requirements": [r.dict() for r in requirements]
        })

    except Exception as e:
        logger.error(f"Requirements calculation failed: {e}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


# ==================== Helper Functions ====================

def _build_hourly_comparison(
    requirements: List,
    schedule: List,
    target_date: date
) -> List[HourlyStaffing]:
    """
    Build hour-by-hour comparison of required vs actual staffing.

    Note: Since the database stores daily aggregated counts, we distribute
    staff evenly across operating hours for comparison purposes.
    """
    # Get total actual staff by role from schedule
    actual_staff = {"servers": 0, "cooks": 0}

    for shift in schedule:
        role_lower = shift.role.lower()
        # Parse count from employee_name (format: "5 Server(s)")
        if "(" in shift.employee_name:
            count_str = shift.employee_name.split()[0]
            try:
                count = int(count_str)
            except:
                count = 1

            if role_lower in ["server", "waiter", "host"]:
                actual_staff["servers"] = count
            elif role_lower in ["cook", "chef", "kitchen"]:
                actual_staff["cooks"] = count

    # Build hourly comparison
    comparison = []
    for req in requirements:
        # Use the same daily count for all hours (simplified)
        actual_servers = actual_staff["servers"]
        actual_cooks = actual_staff["cooks"]

        # Determine status
        required_servers = int(req.required_servers)
        required_cooks = int(req.required_cooks)

        server_diff = actual_servers - required_servers
        cook_diff = actual_cooks - required_cooks

        # If we have 0 staff when any are required, that's definitely understaffed
        if (actual_servers == 0 and required_servers > 0) or (actual_cooks == 0 and required_cooks > 0):
            status = "under"
        elif server_diff < -1 or cook_diff < -1:
            status = "under"
        elif server_diff > 1 or cook_diff > 1:
            status = "over"
        else:
            status = "optimal"

        # Calculate variance cost (simplified: $15/hour average)
        variance_cost = (server_diff + cook_diff) * 15.0 if status == "over" else 0.0

        hour_display = datetime.combine(target_date, time(hour=req.hour)).strftime("%I %p")

        comparison.append(HourlyStaffing(
            hour=req.hour,
            hour_display=hour_display,
            demand=req.demand_forecast,
            required_servers=int(req.required_servers),
            required_cooks=int(req.required_cooks),
            actual_servers=actual_servers,
            actual_cooks=actual_cooks,
            status=status,
            variance_cost=variance_cost
        ))

    return comparison


def _generate_recommendations(hourly_staffing: List[HourlyStaffing]) -> List[str]:
    """Generate actionable staffing recommendations."""
    recommendations = []

    for hour in hourly_staffing:
        server_diff = hour.actual_servers - hour.required_servers
        cook_diff = hour.actual_cooks - hour.required_cooks

        if server_diff > 1:
            recommendations.append(
                f"{hour.hour_display}: Reduce {server_diff} server(s) (overstaffed)"
            )
        elif server_diff < -1:
            recommendations.append(
                f"{hour.hour_display}: Add {abs(server_diff)} server(s) (understaffed)"
            )

        if cook_diff > 1:
            recommendations.append(
                f"{hour.hour_display}: Reduce {cook_diff} cook(s) (overstaffed)"
            )
        elif cook_diff < -1:
            recommendations.append(
                f"{hour.hour_display}: Add {abs(cook_diff)} cook(s) (understaffed)"
            )

    if not recommendations:
        recommendations.append("✓ Staffing is optimal across all hours")

    return recommendations
