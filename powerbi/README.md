# Power BI model

`python run_pipeline.py` writes a star schema to `outputs/star_schema/` (CSV) and `outputs/star_schema/market_pulse.sqlite`.

| Table | Grain | Rows |
|---|---|---|
| `fact_sales_price` | item x customer segment x week | 28,560 |
| `fact_market_price` | item x week (real Toronto terminal prices, CAD) | 7,199 |
| `dim_item` | basket item (category, unit, target margin, volume) | 30 |
| `dim_segment` | customer segment and pricing terms | 4 |
| `dim_date` | report week (year, month, source period) | 265 |

**To build the report:** Get Data > Text/CSV for each file, set the relationships listed at the top of
`measures.dax`, mark `dim_date` as the date table, then paste the measures.

The measures reproduce the Python and SQL results exactly. For example, `GM %` by segment matches
`outputs/terms_profitability.csv`, and `Margin Variance` = `Variance - Cost Timing` + `Variance - Price Hold`.
