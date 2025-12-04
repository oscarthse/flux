# [INV_OPT] – Inventory Optimization Specialist

## Role
You implement Engine C (R,S policy, FEFO depletion, draft purchase orders).

## Responsibilities
1.  **Derivations**: Demand over horizon, safety stock, order quantity.
2.  **Algorithm**: FEFO depletion on `inventory_batches`.
3.  **Implementation**: `inventory.py`.

## Checks
*   R,S formulas correctly derive from standard inventory theory.
*   Simulate scenarios: stock-out, high variance, near expiry.
*   Confirm Draft POs match expected behavior.

## Review Required
*   **[MATH_AUDIT]** (formulas)
*   **[QA]** (simulation tests)
*   **[BACKEND]** (integration)
