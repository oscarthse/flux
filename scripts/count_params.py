#!/usr/bin/env python3
"""
Count %s placeholders in dashboard queries
"""

# Query 1: Low stock (lines 69-108)
query1 = """
                    WITH future_demand AS (
                        SELECT
                            menu_item_id,
                            SUM(predicted_quantity) as total_predicted_qty
                        FROM forecasts
                        WHERE tenant_id = %s
                          AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
                        GROUP BY menu_item_id
                    ),
                    ingredient_demand AS (
                        SELECT
                            r.ingredient_id,
                            SUM(fd.total_predicted_qty * r.quantity) as required_qty
                        FROM future_demand fd
                        JOIN recipes r ON fd.menu_item_id = r.menu_item_id AND r.tenant_id = %s
                        GROUP BY r.ingredient_id
                    ),
                    current_stock AS (
                        SELECT
                            ingredient_id,
                            SUM(remaining_quantity) as total_stock
                        FROM inventory_batches
                        WHERE tenant_id = %s
                        GROUP BY ingredient_id
                    )
                    SELECT
                        COUNT(DISTINCT id.ingredient_id) as low_stock_count,
                        SUM(
                            CASE
                                WHEN COALESCE(cs.total_stock, 0) < id.required_qty THEN
                                    (id.required_qty - COALESCE(cs.total_stock, 0)) * i.cost_per_unit
                                ELSE 0
                            END
                        ) as financial_impact
                    FROM ingredient_demand id
                    LEFT JOIN current_stock cs ON id.ingredient_id = cs.ingredient_id
                    JOIN ingredients i ON id.ingredient_id = i.id AND i.tenant_id = %s
                    WHERE COALESCE(cs.total_stock, 0) < id.required_qty
"""

print(f"Query 1 (Low Stock): {query1.count('%s')} parameters needed")
print(f"Current: (tenant_id, tenant_id) = 2 parameters")
print(f"Should be: (tenant_id, tenant_id, tenant_id, tenant_id) = 4 parameters")

# Query 2: Revenue forecast (lines 114-129)
query2 = """
                    WITH forecast_start AS (
                        SELECT GREATEST(CURRENT_DATE, MIN(forecast_date)) as start_date
                        FROM forecasts
                        WHERE tenant_id = %s
                    )
                    SELECT COALESCE(SUM(f.predicted_quantity * mi.price), 0)
                    FROM forecasts f
                    JOIN menu_items mi ON f.menu_item_id = mi.id AND mi.tenant_id = %s
                    CROSS JOIN forecast_start fs
                    WHERE f.tenant_id = %s
                      AND f.forecast_date >= fs.start_date
                      AND f.forecast_date < fs.start_date + INTERVAL '7 days'
"""

print(f"\nQuery 2 (Revenue): {query2.count('%s')} parameters needed")
print(f"Current: (tenant_id, tenant_id) = 2 parameters")
print(f"Should be: (tenant_id, tenant_id, tenant_id) = 3 parameters")

# Query 3: Stats endpoint (lines 340-378)
query3 = """
                WITH future_demand AS (
                    SELECT
                        menu_item_id,
                        SUM(predicted_quantity) as total_predicted_qty
                    FROM forecasts
                    WHERE tenant_id = %s
                      AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
                    GROUP BY menu_item_id
                ),
                ingredient_demand AS (
                    SELECT
                        r.ingredient_id,
                        SUM(fd.total_predicted_qty * r.quantity) as required_qty
                    FROM future_demand fd
                    JOIN recipes r ON fd.menu_item_id = r.menu_item_id AND r.tenant_id = %s
                    GROUP BY r.ingredient_id
                ),
                current_stock AS (
                    SELECT
                        ingredient_id,
                        SUM(remaining_quantity) as total_stock
                    FROM inventory_batches
                    WHERE tenant_id = %s
                    GROUP BY ingredient_id
                )
                SELECT
                    COUNT(DISTINCT id.ingredient_id) as low_stock_count,
                    SUM(
                        CASE
                            WHEN COALESCE(cs.total_stock, 0) < id.required_qty THEN
                                (id.required_qty - COALESCE(cs.total_stock, 0)) * i.cost_per_unit
                            ELSE 0
                        END
                    ) as financial_impact
                FROM ingredient_demand id
                LEFT JOIN current_stock cs ON id.ingredient_id = cs.ingredient_id
                JOIN ingredients i ON id.ingredient_id = i.id AND i.tenant_id = %s
                WHERE COALESCE(cs.total_stock, 0) < id.required_qty
"""

print(f"\nQuery 3 (Stats): {query3.count('%s')} parameters needed")
print(f"Current: (tenant_id, tenant_id) = 2 parameters")
print(f"Should be: (tenant_id, tenant_id, tenant_id, tenant_id) = 4 parameters")
