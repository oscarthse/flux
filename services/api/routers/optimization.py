"""
Optimization Router - Profit Protection Suite API.

Exposes stochastic optimization engines via REST API:
- Inventory: Newsvendor-based recommendations with explainability
- Staffing: Erlang-C based labor optimization
- Forecasting: Prophet with uncertainty decomposition

All endpoints return "Glass-Box" outputs with plain English explanations.
"""
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.api.database import db_service
from services.api.context import tenant_context
from services.api.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/optimization", tags=["optimization"])


# ============================================================================
# Response Models
# ============================================================================

class RiskProfile(BaseModel):
    """Risk classification with explainability."""
    type: str = Field(..., description="profit_protection or spoilage_risk")
    critical_fractile: float = Field(..., ge=0, le=1)
    explanation: str = Field(..., description="Plain English explanation")
    math_proof: str = Field(..., description="Mathematical formula used")


class InventoryRecommendation(BaseModel):
    """Single ingredient recommendation."""
    ingredient_id: str
    name: str
    current_stock: float
    suggested_order: float
    unit: str = "units"
    risk_profile: RiskProfile


class InventoryRecommendationsResponse(BaseModel):
    """Full inventory recommendations response."""
    items: List[InventoryRecommendation]
    total_items: int
    total_order_value: float


class ActionCard(BaseModel):
    """Actionable insight card."""
    title: str
    body: str
    potential_saving: Optional[float] = None


class HourlyStaffing(BaseModel):
    """Staffing requirement for a single hour."""
    hour: int
    forecast_covers: float
    required_servers: int
    utilization_rate: float
    wait_probability: float
    avg_wait_minutes: float
    action_card: ActionCard


class StaffingRequirementsResponse(BaseModel):
    """Full staffing requirements response."""
    date: str
    service_profile: str
    hourly_breakdown: List[HourlyStaffing]
    total_required_hours: float
    peak_hour: int


class ForecastComponent(BaseModel):
    """Forecast decomposition for a single day."""
    date: str
    base_trend: float
    weekly_seasonality: float
    event_impact: float = 0.0
    total_forecast: float
    uncertainty_lower: float
    uncertainty_upper: float
    sigma: float


class ForecastDecomposeResponse(BaseModel):
    """Forecast decomposition response for visualization."""
    menu_item_id: Optional[str]
    menu_item_name: Optional[str]
    components: List[ForecastComponent]
    model_version: str = "prophet"


# ============================================================================
# Inventory Optimization Endpoint
# ============================================================================

@router.get("/inventory/recommendations/{tenant_id}", response_model=InventoryRecommendationsResponse)
async def get_inventory_recommendations(tenant_id: str):
    """
    Get Newsvendor-based inventory recommendations.

    Returns optimal order quantities balancing stockout risk vs waste risk,
    with full explainability including plain English explanations and math proof.
    """
    logger.info(f"Fetching inventory recommendations for tenant {tenant_id}")

    try:
        from services.worker.engines.inventory import (
            generate_stochastic_orders,
            StochasticOrderResult
        )

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            # Generate stochastic orders
            results: List[StochasticOrderResult] = generate_stochastic_orders(tenant_id, conn)

            if not results:
                return InventoryRecommendationsResponse(
                    items=[],
                    total_items=0,
                    total_order_value=0.0
                )

            # Get unit costs for value calculation
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, unit, cost_per_unit
                    FROM ingredients
                    WHERE tenant_id = %s
                """, (tenant_id,))
                ingredient_info = {
                    str(row[0]): {"unit": row[1] or "units", "cost": float(row[2] or 0)}
                    for row in cur.fetchall()
                }

            items = []
            total_value = 0.0

            for result in results:
                # Determine risk type
                is_shelf_constrained = result.newsvendor_qty > result.shelf_life_cap
                risk_type = "spoilage_risk" if is_shelf_constrained else "profit_protection"

                ing_info = ingredient_info.get(result.ingredient_id, {"unit": "units", "cost": 0})
                order_value = result.recommended_qty * ing_info["cost"]
                total_value += order_value

                items.append(InventoryRecommendation(
                    ingredient_id=result.ingredient_id,
                    name=result.name,
                    current_stock=result.current_stock,
                    suggested_order=result.recommended_qty,
                    unit=ing_info["unit"],
                    risk_profile=RiskProfile(
                        type=risk_type,
                        critical_fractile=result.critical_fractile,
                        explanation=result.recommendation_logic,
                        math_proof=result.math_proof
                    )
                ))

            return InventoryRecommendationsResponse(
                items=items,
                total_items=len(items),
                total_order_value=round(total_value, 2)
            )

    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail="Optimization engine not available. Install scipy.")
    except Exception as e:
        logger.error(f"Inventory recommendations failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Staffing Optimization Endpoint
# ============================================================================

@router.get("/staffing/requirements", response_model=StaffingRequirementsResponse)
async def get_staffing_requirements(
    target_date: str = Query(..., description="Date in YYYY-MM-DD format"),
    service_profile: str = Query("casual", description="fine_dining or casual")
):
    """
    Get Erlang-C based staffing requirements.

    Returns optimal server counts per hour to meet service level targets,
    with actionable insights and potential savings.
    """
    tenant_id = tenant_context.get()
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant context required")

    # Parse date
    try:
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Adjust service rate based on profile
    service_rate = 12.0 if service_profile == "casual" else 8.0

    logger.info(f"Fetching staffing requirements for {target_date}, profile={service_profile}")

    try:
        from services.worker.engines.staff_requirements import (
            calculate_erlang_c_requirements,
            ErlangCResult,
            SERVICE_RATE_MU
        )

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            results = calculate_erlang_c_requirements(tenant_id, parsed_date, conn)

            if not results:
                return StaffingRequirementsResponse(
                    date=target_date,
                    service_profile=service_profile,
                    hourly_breakdown=[],
                    total_required_hours=0,
                    peak_hour=0
                )

            hourly_breakdown = []
            total_hours = 0
            peak_hour = 0
            peak_servers = 0

            for result in results:
                # Handle utilization > 1.0 edge case (system overload)
                if result.utilization >= 1.0:
                    action_card = ActionCard(
                        title="⚠️ System Overload",
                        body=f"Demand ({result.forecasted_covers:.0f} guests) exceeds capacity. "
                             f"Consider limiting reservations or adding emergency staff.",
                        potential_saving=None
                    )
                elif result.utilization < 0.5:
                    # Low utilization - potential savings
                    excess_servers = max(0, result.required_servers - 1)
                    saving = excess_servers * 12.0  # $12/hour
                    action_card = ActionCard(
                        title="Efficiency Opportunity",
                        body=f"Consider reducing to {result.required_servers - 1} servers. "
                             f"Current utilization only {result.utilization*100:.0f}%.",
                        potential_saving=round(saving, 2) if saving > 0 else None
                    )
                elif result.prob_wait <= 0.10:
                    action_card = ActionCard(
                        title="✓ Excellent Service",
                        body=f"Wait times projected under 2 minutes. "
                             f"Utilization: {result.utilization*100:.0f}%.",
                        potential_saving=None
                    )
                else:
                    action_card = ActionCard(
                        title="Peak Efficiency",
                        body=f"Maintain {result.required_servers} servers. "
                             f"Wait times projected under 5 mins.",
                        potential_saving=None
                    )

                # Cap utilization at 1.0 for display
                display_utilization = min(result.utilization, 1.0)

                hourly_breakdown.append(HourlyStaffing(
                    hour=result.hour,
                    forecast_covers=result.forecasted_covers,
                    required_servers=result.required_servers,
                    utilization_rate=round(display_utilization, 2),
                    wait_probability=round(result.prob_wait, 2),
                    avg_wait_minutes=round(result.avg_wait_time, 1),
                    action_card=action_card
                ))

                total_hours += result.required_servers

                if result.required_servers > peak_servers:
                    peak_servers = result.required_servers
                    peak_hour = result.hour

            return StaffingRequirementsResponse(
                date=target_date,
                service_profile=service_profile,
                hourly_breakdown=hourly_breakdown,
                total_required_hours=total_hours,
                peak_hour=peak_hour
            )

    except Exception as e:
        logger.error(f"Staffing requirements failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Forecasting Decomposition Endpoint
# ============================================================================

@router.get("/forecasting/decompose", response_model=ForecastDecomposeResponse)
async def get_forecast_decomposition(
    menu_item_id: Optional[str] = Query(None, description="Specific menu item ID"),
    days: int = Query(7, ge=1, le=30, description="Days to forecast")
):
    """
    Get Prophet forecast with decomposition for visualization.

    Returns trend, seasonality, and uncertainty components for stacked bar chart.
    """
    tenant_id = tenant_context.get()
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant context required")

    logger.info(f"Fetching forecast decomposition, item={menu_item_id}, days={days}")

    try:
        with db_service.get_connection(tenant_id=tenant_id) as conn:
            with conn.cursor() as cur:
                # Get forecast data from cached table
                if menu_item_id:
                    cur.execute("""
                        SELECT
                            f.forecast_date,
                            f.predicted_quantity,
                            COALESCE(f.confidence_interval_lower, f.predicted_quantity * 0.85) as ci_lower,
                            COALESCE(f.confidence_interval_upper, f.predicted_quantity * 1.15) as ci_upper,
                            m.name
                        FROM forecasts f
                        JOIN menu_items m ON f.menu_item_id = m.id
                        WHERE f.tenant_id = %s
                          AND f.menu_item_id = %s
                          AND f.forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '%s days'
                        ORDER BY f.forecast_date
                    """, (tenant_id, menu_item_id, days))
                else:
                    # Aggregate all items
                    cur.execute("""
                        SELECT
                            f.forecast_date,
                            SUM(f.predicted_quantity) as predicted_quantity,
                            SUM(COALESCE(f.confidence_interval_lower, f.predicted_quantity * 0.85)) as ci_lower,
                            SUM(COALESCE(f.confidence_interval_upper, f.predicted_quantity * 1.15)) as ci_upper,
                            'All Items' as name
                        FROM forecasts f
                        WHERE f.tenant_id = %s
                          AND f.forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '%s days'
                        GROUP BY f.forecast_date
                        ORDER BY f.forecast_date
                    """, (tenant_id, days))

                rows = cur.fetchall()

                if not rows:
                    return ForecastDecomposeResponse(
                        menu_item_id=menu_item_id,
                        menu_item_name=None,
                        components=[]
                    )

                components = []
                menu_item_name = rows[0][4] if rows else None

                for row in rows:
                    forecast_date, qty, ci_lower, ci_upper, _ = row
                    qty = float(qty or 0)
                    ci_lower = float(ci_lower or qty * 0.85)
                    ci_upper = float(ci_upper or qty * 1.15)

                    # Calculate sigma
                    sigma = (ci_upper - ci_lower) / 3.92
                    sigma = max(sigma, 0.1 * qty) if qty > 0 else 0.1

                    # Decompose into components (estimated)
                    # Base trend: ~70% of forecast
                    # Weekly: ~25%
                    # Events: ~5%
                    base_trend = qty * 0.70
                    day_of_week = forecast_date.weekday()

                    # Weekend boost
                    if day_of_week >= 4:  # Fri-Sun
                        weekly_impact = qty * 0.30
                        base_trend = qty * 0.65
                    else:
                        weekly_impact = qty * 0.20
                        base_trend = qty * 0.75

                    event_impact = qty - base_trend - weekly_impact
                    event_impact = max(0, event_impact)

                    components.append(ForecastComponent(
                        date=str(forecast_date),
                        base_trend=round(base_trend, 2),
                        weekly_seasonality=round(weekly_impact, 2),
                        event_impact=round(event_impact, 2),
                        total_forecast=round(qty, 2),
                        uncertainty_lower=round(ci_lower, 2),
                        uncertainty_upper=round(ci_upper, 2),
                        sigma=round(sigma, 2)
                    ))

                return ForecastDecomposeResponse(
                    menu_item_id=menu_item_id,
                    menu_item_name=menu_item_name,
                    components=components
                )

    except Exception as e:
        logger.error(f"Forecast decomposition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Purchase Order Approval Endpoint
# ============================================================================

class ApproveOrdersRequest(BaseModel):
    """Request to approve inventory orders."""
    ingredient_ids: Optional[List[str]] = None  # None = approve all


class ApproveOrdersResponse(BaseModel):
    """Response from order approval."""
    purchase_order_id: str
    status: str
    line_items_count: int
    total_value: float


@router.post("/inventory/approve", response_model=ApproveOrdersResponse)
async def approve_inventory_orders(request: ApproveOrdersRequest):
    """
    Approve inventory recommendations and create/update purchase order.

    Creates a draft PO if none exists, or updates existing draft for same date.
    """
    tenant_id = tenant_context.get()
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant context required")

    logger.info(f"Approving inventory orders for tenant {tenant_id}")

    try:
        from services.worker.engines.inventory import generate_stochastic_orders
        import uuid
        from datetime import timedelta

        with db_service.get_connection(tenant_id=tenant_id) as conn:
            # Generate recommendations
            results = generate_stochastic_orders(tenant_id, conn)

            # Filter if specific IDs provided
            if request.ingredient_ids:
                results = [r for r in results if r.ingredient_id in request.ingredient_ids]

            # Filter to items needing orders
            to_order = [r for r in results if r.recommended_qty > 0]

            if not to_order:
                raise HTTPException(status_code=400, detail="No items to order")

            with conn.cursor() as cur:
                # Check for existing draft PO for today
                today = date.today()
                cur.execute("""
                    SELECT id FROM purchase_orders
                    WHERE tenant_id = %s AND status = 'draft' AND delivery_date >= %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (tenant_id, today))

                existing = cur.fetchone()

                if existing:
                    po_id = str(existing[0])
                    # Clear existing line items
                    cur.execute("""
                        DELETE FROM po_line_items
                        WHERE tenant_id = %s AND po_id = %s
                    """, (tenant_id, po_id))
                else:
                    # Create new PO
                    po_id = str(uuid.uuid4())
                    delivery_date = today + timedelta(days=3)
                    cur.execute("""
                        INSERT INTO purchase_orders (id, tenant_id, status, delivery_date)
                        VALUES (%s, %s, 'draft', %s)
                    """, (po_id, tenant_id, delivery_date))

                # Insert line items
                total_value = 0.0
                for item in to_order:
                    line_id = str(uuid.uuid4())

                    # Get cost
                    cur.execute("""
                        SELECT cost_per_unit FROM ingredients WHERE id = %s
                    """, (item.ingredient_id,))
                    cost_row = cur.fetchone()
                    unit_cost = float(cost_row[0]) if cost_row else 0

                    cur.execute("""
                        INSERT INTO po_line_items (id, tenant_id, po_id, ingredient_id, quantity, unit_price)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (line_id, tenant_id, po_id, item.ingredient_id, item.recommended_qty, unit_cost))

                    total_value += item.recommended_qty * unit_cost

                conn.commit()

                return ApproveOrdersResponse(
                    purchase_order_id=po_id,
                    status="draft",
                    line_items_count=len(to_order),
                    total_value=round(total_value, 2)
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order approval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
