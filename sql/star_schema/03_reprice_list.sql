-- Latest week: item x segment prices whose margin at this week's cost sits more than 5 points off target.
WITH latest AS (SELECT MAX(date_key) AS date_key FROM fact_sales_price)
SELECT i.item_name,
       s.segment,
       ROUND(f.sell_price, 2)                                   AS current_price,
       ROUND(f.landed_cost, 2)                                  AS landed_cost,
       ROUND(1 - f.landed_cost / f.sell_price, 3)               AS margin_now,
       f.target_margin,
       ROUND(f.landed_cost / (1 - f.target_margin), 2)          AS price_at_target,
       CASE WHEN 1 - f.landed_cost / f.sell_price < f.target_margin THEN 'RAISE' ELSE 'ROOM TO SHARPEN' END AS action
FROM fact_sales_price f
JOIN latest l USING (date_key)
JOIN dim_item i USING (item_id)
JOIN dim_segment s USING (segment_id)
WHERE ABS(1 - f.landed_cost / f.sell_price - f.target_margin) > 0.05
ORDER BY margin_now - f.target_margin;
