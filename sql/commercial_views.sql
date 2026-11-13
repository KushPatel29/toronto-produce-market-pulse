-- SQLite; illustrative ERP-style transactions, not an actual ERP connection.
DROP VIEW IF EXISTS v_customer_margin;
CREATE VIEW v_customer_margin AS
SELECT customer,
       SUM(actual_cases * actual_net_price) AS net_revenue,
       SUM(actual_cases * actual_unit_cost) AS variable_cost,
       SUM(actual_cases * (actual_net_price - actual_unit_cost)) AS contribution,
       SUM(actual_cases * (actual_net_price - actual_unit_cost)) /
         NULLIF(SUM(actual_cases * actual_net_price), 0) AS contribution_margin
FROM fact_sales
GROUP BY customer;

DROP VIEW IF EXISTS v_finance_bridge;
CREATE VIEW v_finance_bridge AS
SELECT item_id, customer,
       budget_cases * (budget_net_price - budget_unit_cost) AS budget_contribution,
       (actual_cases - budget_cases) * (budget_net_price - budget_unit_cost) AS volume_mix_effect,
       actual_cases * (actual_net_price - budget_net_price) AS net_price_effect,
       -actual_cases * (actual_unit_cost - budget_unit_cost) AS cost_effect,
       actual_cases * (actual_net_price - actual_unit_cost) AS actual_contribution
FROM fact_sales;

DROP VIEW IF EXISTS v_item_profitability;
CREATE VIEW v_item_profitability AS
SELECT d.item_id, d.display_name, d.category, d.unit_note,
       SUM(f.actual_cases) AS cases,
       SUM(f.actual_cases * f.actual_net_price) AS revenue,
       SUM(f.actual_cases * (f.actual_net_price - f.actual_unit_cost)) AS contribution
FROM fact_sales AS f
JOIN dim_item AS d ON d.item_id = f.item_id
GROUP BY d.item_id, d.display_name, d.category, d.unit_note;
