-- Star schema for the pricing model. Built by src/pulse/datamodel.py into outputs/star_schema/market_pulse.sqlite
-- and exported as CSV to outputs/star_schema/ for Power BI or Tableau.
CREATE TABLE dim_item (
    item_id        TEXT PRIMARY KEY,
    item_name      TEXT NOT NULL,
    category       TEXT NOT NULL,
    uom            TEXT NOT NULL,
    target_margin  REAL NOT NULL,
    weekly_cases   REAL NOT NULL
);
CREATE TABLE dim_segment (
    segment_id     TEXT PRIMARY KEY,
    segment        TEXT NOT NULL,
    volume_share   REAL NOT NULL,
    margin_adj     REAL NOT NULL,
    pricing_policy TEXT NOT NULL,
    terms          TEXT NOT NULL
);
CREATE TABLE dim_date (
    date_key   TEXT PRIMARY KEY,   -- report week, ISO date
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    year_month TEXT NOT NULL,
    period     TEXT NOT NULL       -- A_2017_2021 or B_2022_2024 (source gap between them)
);
CREATE TABLE fact_market_price (   -- one row per item x report week (real terminal prices, CAD)
    item_id      TEXT NOT NULL REFERENCES dim_item(item_id),
    date_key     TEXT NOT NULL REFERENCES dim_date(date_key),
    terminal_cad REAL NOT NULL,
    landed_cost  REAL NOT NULL,
    n_quotes     INTEGER,
    PRIMARY KEY (item_id, date_key)
);
CREATE TABLE fact_sales_price (    -- one row per item x segment x week (replayed pricing)
    item_id       TEXT NOT NULL REFERENCES dim_item(item_id),
    segment_id    TEXT NOT NULL REFERENCES dim_segment(segment_id),
    date_key      TEXT NOT NULL REFERENCES dim_date(date_key),
    cases         REAL NOT NULL,
    sell_price    REAL NOT NULL,
    landed_cost   REAL NOT NULL,
    prior_cost    REAL NOT NULL,
    target_margin REAL NOT NULL,
    price_changed INTEGER NOT NULL,
    PRIMARY KEY (item_id, segment_id, date_key)
);
CREATE INDEX ix_sales_date ON fact_sales_price(date_key);
