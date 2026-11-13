-- Revenue, gross margin and margin-vs-target by customer pricing terms.
SELECT s.segment,
       s.pricing_policy,
       ROUND(SUM(f.sell_price * f.cases), 0)                                   AS revenue,
       ROUND(SUM((f.sell_price - f.landed_cost) * f.cases), 0)                 AS gross_margin,
       SUM((f.sell_price - f.landed_cost) * f.cases) / SUM(f.sell_price * f.cases) AS gm_pct,
       SUM(f.sell_price * f.cases * f.target_margin) / SUM(f.sell_price * f.cases) AS target_pct,
       AVG(CASE WHEN 1 - f.landed_cost / f.sell_price < f.target_margin - 0.10 THEN 1.0 ELSE 0 END) AS breach_rate
FROM fact_sales_price f
JOIN dim_segment s USING (segment_id)
GROUP BY s.segment, s.pricing_policy
ORDER BY revenue DESC;
