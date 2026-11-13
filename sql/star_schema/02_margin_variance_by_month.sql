-- Monthly gross margin against target, split into cost timing and price hold.
WITH w AS (
    SELECT d.year_month,
           f.sell_price * f.cases                                        AS revenue,
           (f.sell_price - f.landed_cost) * f.cases                      AS gm,
           f.sell_price * f.cases * f.target_margin                      AS gm_target,
           f.cases * (f.prior_cost - f.landed_cost)                      AS var_cost_timing,
           f.cases * (f.sell_price * (1 - f.target_margin) - f.prior_cost) AS var_price_hold
    FROM fact_sales_price f
    JOIN dim_date d USING (date_key)
)
SELECT year_month,
       ROUND(SUM(revenue), 0)                          AS revenue,
       ROUND(SUM(gm), 0)                               AS gross_margin,
       ROUND(SUM(gm_target), 0)                        AS gm_at_target,
       ROUND(SUM(gm) - SUM(gm_target), 0)              AS variance,
       ROUND(SUM(var_cost_timing), 0)                  AS cost_timing,
       ROUND(SUM(var_price_hold), 0)                   AS price_hold,
       ROUND(100.0 * (SUM(gm) - SUM(gm_target)) / SUM(revenue), 2) AS gap_pts
FROM w
GROUP BY year_month
ORDER BY year_month;
