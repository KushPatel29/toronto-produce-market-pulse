"""Write the Power BI semantic model as code (TMDL, PBIP format) from the star-schema and RGM outputs.

Output: powerbi/MarketPulse.pbip, powerbi/MarketPulse.SemanticModel/ (TMDL) and a one-page report shell.
Column lists are read from the CSV headers, so the model cannot drift from the pipeline. Open
powerbi/MarketPulse.pbip in Power BI Desktop (Developer mode / PBIP enabled) and press Refresh: by
default the data loads from the public GitHub copy of outputs/; point the SourceRoot parameter at a
local outputs/ folder to load your own rebuild instead.
"""

import csv
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
PBI = ROOT / "powerbi"
SM = PBI / "MarketPulse.SemanticModel"
RAW = "https://raw.githubusercontent.com/KushPatel29/toronto-produce-market-pulse/main/outputs/"

PCT = "0.0%;-0.0%;0.0%"
CAD = "\\$#,0;(\\$#,0);\\$#,0"
CAD2 = "\\$#,0.00;(\\$#,0.00);\\$#,0.00"
NUM = "#,0"
NUM1 = "#,0.0"

# table -> (csv path under outputs/, description, French caption, {column: (dataType, format, French caption)})
TABLES = {
    "dim_item": (
        "star_schema/dim_item.csv",
        "Basket item: category, unit, target margin and planned weekly cases.",
        "Article",
        {
            "item_id": ("string", None, "Code article"),
            "item_name": ("string", None, "Article"),
            "category": ("string", None, "Catégorie"),
            "uom": ("string", None, "Unité"),
            "target_margin": ("double", PCT, "Marge cible"),
            "weekly_cases": ("double", NUM1, "Caisses par semaine"),
        },
    ),
    "dim_segment": (
        "star_schema/dim_segment.csv",
        "Customer segment and its pricing terms (assumptions in config/customer_terms.csv).",
        "Segment client",
        {
            "segment_id": ("string", None, "Code segment"),
            "segment": ("string", None, "Segment"),
            "volume_share": ("double", PCT, "Part du volume"),
            "margin_adj": ("double", PCT, "Ajustement de marge"),
            "pricing_policy": ("string", None, "Politique de prix"),
            "terms": ("string", None, "Conditions"),
        },
    ),
    "dim_date": (
        "star_schema/dim_date.csv",
        "Report week. The April 2021 - November 2022 source gap separates periods A and B.",
        "Date",
        {
            "date_key": ("dateTime", "yyyy-mm-dd", "Semaine"),
            "year": ("int64", "0", "Année"),
            "month": ("int64", "0", "Mois"),
            "year_month": ("string", None, "Année-mois"),
            "period": ("string", None, "Période"),
        },
    ),
    "fact_market_price": (
        "star_schema/fact_market_price.csv",
        "Real Toronto terminal price per item and report week, CAD.",
        "Prix du marché",
        {
            "item_id": ("string", None, "Code article"),
            "date_key": ("dateTime", "yyyy-mm-dd", "Semaine"),
            "terminal_cad": ("double", CAD2, "Prix terminal ($ CA)"),
            "landed_cost": ("double", CAD2, "Coût rendu"),
            "n_quotes": ("int64", NUM, "Nombre de cotes"),
        },
    ),
    "fact_sales_price": (
        "star_schema/fact_sales_price.csv",
        "Replayed selling price per item, segment and week on real costs; volumes are assumptions.",
        "Prix de vente",
        {
            "item_id": ("string", None, "Code article"),
            "segment_id": ("string", None, "Code segment"),
            "date_key": ("dateTime", "yyyy-mm-dd", "Semaine"),
            "cases": ("double", NUM1, "Caisses"),
            "sell_price": ("double", CAD2, "Prix de vente"),
            "landed_cost": ("double", CAD2, "Coût rendu"),
            "prior_cost": ("double", CAD2, "Coût précédent"),
            "target_margin": ("double", PCT, "Marge cible"),
            "price_changed": ("int64", "0", "Prix modifié"),
        },
    ),
    "fact_shipments": (
        "rgm/SYNTHETIC_weekly_shipments.csv",
        "SYNTHETIC weekly shipments by item and channel, 2019 and 2023, on real terminal costs.",
        "Expéditions",
        {
            "item_id": ("string", None, "Code article"),
            "category": ("string", None, "Catégorie"),
            "channel": ("string", None, "Canal"),
            "year": ("int64", "0", "Année"),
            "date": ("dateTime", "yyyy-mm-dd", "Semaine"),
            "cases": ("double", NUM1, "Caisses"),
            "list_price": ("double", CAD2, "Prix courant"),
            "net_price": ("double", CAD2, "Prix net"),
            "unit_cost": ("double", CAD2, "Coût unitaire"),
            "promo": ("boolean", None, "Promotion"),
            "promo_depth": ("double", PCT, "Profondeur de promotion"),
            "data_status": ("string", None, "Statut des données"),
            "revenue": ("double", CAD, "Revenu net"),
            "list_revenue": ("double", CAD, "Revenu au prix courant"),
            "cogs": ("double", CAD, "Coût des ventes"),
            "gm": ("double", CAD, "Marge brute"),
        },
    ),
    "fact_promotion": (
        "rgm/promotion_events.csv",
        "One row per SYNTHETIC promotion event: estimated lift, break-even lift, trade spend and verdict.",
        "Promotions",
        {
            "event": ("string", None, "Événement"),
            "item_id": ("string", None, "Code article"),
            "year": ("int64", "0", "Année"),
            "start": ("dateTime", "yyyy-mm-dd", "Début"),
            "depth": ("double", PCT, "Profondeur"),
            "planted_uplift": ("double", "0.00", "Hausse simulée"),
            "baseline_cases": ("double", NUM1, "Caisses de base"),
            "promo_cases": ("double", NUM1, "Caisses en promotion"),
            "est_uplift": ("double", "0.00", "Hausse estimée"),
            "incremental_cases": ("double", NUM1, "Caisses incrémentales"),
            "dip_cases": ("double", NUM1, "Creux après promotion"),
            "breakeven_uplift": ("double", "0.00", "Hausse au seuil de rentabilité"),
            "trade_spend": ("double", CAD, "Dépenses commerciales"),
            "net_incremental_margin": ("double", CAD, "Marge incrémentale nette"),
            "roi": ("double", PCT, "Rendement"),
            "uplift_error_pts": ("double", NUM1, "Erreur de hausse (pts)"),
            "verdict": ("string", None, "Décision"),
        },
    ),
}

KEYS = {"dim_item": "item_id", "dim_segment": "segment_id", "dim_date": "date_key"}
HIDDEN = {"item_id", "segment_id", "date_key"}  # hide keys on fact tables; visible on dimensions

RELATIONSHIPS = [
    ("fact_sales_price", "item_id", "dim_item", "item_id"),
    ("fact_sales_price", "segment_id", "dim_segment", "segment_id"),
    ("fact_sales_price", "date_key", "dim_date", "date_key"),
    ("fact_market_price", "item_id", "dim_item", "item_id"),
    ("fact_market_price", "date_key", "dim_date", "date_key"),
    ("fact_shipments", "item_id", "dim_item", "item_id"),
    ("fact_promotion", "item_id", "dim_item", "item_id"),
]

# PVM helper: items present in both years, with base- and compare-year totals.
_PVM_T = """VAR a = 2019
VAR b = 2023
VAR t =
    ADDCOLUMNS (
        FILTER (
            VALUES ( fact_shipments[item_id] ),
            CALCULATE ( SUM ( fact_shipments[cases] ), fact_shipments[year] = a ) > 0
                && CALCULATE ( SUM ( fact_shipments[cases] ), fact_shipments[year] = b ) > 0
        ),
        "@qa", CALCULATE ( SUM ( fact_shipments[cases] ), fact_shipments[year] = a ),
        "@qb", CALCULATE ( SUM ( fact_shipments[cases] ), fact_shipments[year] = b ),
        "@gma", CALCULATE ( SUM ( fact_shipments[gm] ), fact_shipments[year] = a ),
        "@gmb", CALCULATE ( SUM ( fact_shipments[gm] ), fact_shipments[year] = b ),
        "@lra", CALCULATE ( SUM ( fact_shipments[list_revenue] ), fact_shipments[year] = a ),
        "@lrb", CALCULATE ( SUM ( fact_shipments[list_revenue] ), fact_shipments[year] = b ),
        "@ra", CALCULATE ( SUM ( fact_shipments[revenue] ), fact_shipments[year] = a ),
        "@rb", CALCULATE ( SUM ( fact_shipments[revenue] ), fact_shipments[year] = b ),
        "@ca", CALCULATE ( SUM ( fact_shipments[cogs] ), fact_shipments[year] = a ),
        "@cb", CALCULATE ( SUM ( fact_shipments[cogs] ), fact_shipments[year] = b )
    )
VAR QA = SUMX ( t, [@qa] )
VAR QB = SUMX ( t, [@qb] )
VAR GMA = SUMX ( t, [@gma] )"""

# home table -> [(name, DAX, format, display folder, description, French caption)]
MEASURES = {
    "fact_sales_price": [
        ("Revenue", "SUMX ( fact_sales_price, fact_sales_price[sell_price] * fact_sales_price[cases] )", CAD, "Pricing", "Selling price x cases.", "Revenu"),
        ("COGS", "SUMX ( fact_sales_price, fact_sales_price[landed_cost] * fact_sales_price[cases] )", CAD, "Pricing", "Landed cost x cases.", "Coût des ventes"),
        ("Gross Margin", "[Revenue] - [COGS]", CAD, "Pricing", "Revenue minus landed cost.", "Marge brute"),
        ("GM %", "DIVIDE ( [Gross Margin], [Revenue] )", PCT, "Pricing", "Gross margin as a share of revenue.", "Marge brute %"),
        ("GM at Target", "SUMX (\n    fact_sales_price,\n    fact_sales_price[sell_price] * fact_sales_price[cases] * fact_sales_price[target_margin]\n)", CAD, "Margin variance", "Margin the same revenue would earn at each item's target margin.", "Marge à la cible"),
        ("Target GM %", "DIVIDE ( [GM at Target], [Revenue] )", PCT, "Margin variance", "Revenue-weighted target margin.", "Marge cible %"),
        ("Margin Variance", "[Gross Margin] - [GM at Target]", CAD, "Margin variance", "Equals Variance - Cost Timing plus Variance - Price Hold.", "Écart de marge"),
        ("Margin Gap (pts)", "( [GM %] - [Target GM %] ) * 100", "0.0", "Margin variance", "Margin points above (+) or below (-) target.", "Écart de marge (pts)"),
        ("Variance - Cost Timing", "SUMX (\n    fact_sales_price,\n    fact_sales_price[cases] * ( fact_sales_price[prior_cost] - fact_sales_price[landed_cost] )\n)", CAD, "Margin variance", "Quotes go out on last week's cost.", "Écart - décalage des coûts"),
        ("Variance - Price Hold", "SUMX (\n    fact_sales_price,\n    fact_sales_price[cases]\n        * ( fact_sales_price[sell_price] * ( 1 - fact_sales_price[target_margin] ) - fact_sales_price[prior_cost] )\n)", CAD, "Margin variance", "Cost of keeping a list or band price instead of repricing.", "Écart - prix maintenu"),
        ("Variance Check", "ROUND ( [Margin Variance] - [Variance - Cost Timing] - [Variance - Price Hold], 2 )", CAD2, "Margin variance", "Must be 0.", "Contrôle de l'écart"),
        ("Breach Rate", "AVERAGEX (\n    fact_sales_price,\n    IF (\n        1 - DIVIDE ( fact_sales_price[landed_cost], fact_sales_price[sell_price] )\n            < fact_sales_price[target_margin] - 0.10,\n        1,\n        0\n    )\n)", PCT, "Pricing", "Share of item-weeks more than 10 points under target margin.", "Taux de dépassement"),
        ("Price Changes", "SUM ( fact_sales_price[price_changed] )", NUM, "Pricing", "Number of price changes.", "Changements de prix"),
    ],
    "fact_market_price": [
        ("Avg Terminal Price (CAD)", "AVERAGE ( fact_market_price[terminal_cad] )", CAD2, "Market", "Mean terminal price per case.", "Prix terminal moyen ($ CA)"),
        ("Terminal Price vs Prior Year", "VAR cur = [Avg Terminal Price (CAD)]\nVAR py =\n    CALCULATE (\n        [Avg Terminal Price (CAD)],\n        FILTER ( ALL ( dim_date ), dim_date[year] = MAX ( dim_date[year] ) - 1 ),\n        VALUES ( dim_item[item_id] )\n    )\nRETURN\n    DIVIDE ( cur - py, py )", PCT, "Market", "Change against the prior calendar year.", "Prix terminal vs année précédente"),
    ],
    "fact_shipments": [
        ("Net Revenue", "SUM ( fact_shipments[revenue] )", CAD, "Revenue growth", "After discounts and promotions.", "Revenu net"),
        ("List Revenue", "SUM ( fact_shipments[list_revenue] )", CAD, "Revenue growth", "Cases at list price.", "Revenu au prix courant"),
        ("Discounts & Promotions", "[List Revenue] - [Net Revenue]", CAD, "Revenue growth", "Price given away below list.", "Remises et promotions"),
        ("Discount Rate", "DIVIDE ( [Discounts & Promotions], [List Revenue] )", PCT, "Revenue growth", "Price investment as a share of list revenue.", "Taux de remise"),
        ("Shipment GM", "SUM ( fact_shipments[gm] )", CAD, "Revenue growth", "Gross margin on synthetic shipments.", "Marge brute (expéditions)"),
        ("Shipment GM %", "DIVIDE ( [Shipment GM], [Net Revenue] )", PCT, "Revenue growth", "Gross margin on net revenue.", "Marge brute % (expéditions)"),
        ("Cases Shipped", "SUM ( fact_shipments[cases] )", NUM, "Revenue growth", "Synthetic cases.", "Caisses expédiées"),
        ("Promo Share of Cases", "DIVIDE ( CALCULATE ( [Cases Shipped], fact_shipments[promo] = TRUE () ), [Cases Shipped] )", PCT, "Revenue growth", "Cases sold on promotion.", "Part des caisses en promotion"),
        ("PVM GM 2019", _PVM_T + "\nRETURN\n    GMA", CAD, "Price-volume-mix", "Base-year gross margin, items sold in both years.", "Marge brute 2019"),
        ("PVM GM 2023", _PVM_T + "\nRETURN\n    SUMX ( t, [@gmb] )", CAD, "Price-volume-mix", "Compare-year gross margin, items sold in both years.", "Marge brute 2023"),
        ("PVM Volume", _PVM_T + "\nRETURN\n    DIVIDE ( QB - QA, QA ) * GMA", CAD, "Price-volume-mix", "Change in total cases at the base-year mix and margin.", "Effet volume"),
        ("PVM Mix", _PVM_T + "\nRETURN\n    SUMX ( t, [@qb] * DIVIDE ( [@gma], [@qa] ) ) - DIVIDE ( QB, QA ) * GMA", CAD, "Price-volume-mix", "Shift in item shares, valued at base-year margin per case.", "Effet de composition"),
        ("PVM List Price", _PVM_T + "\nRETURN\n    SUMX ( t, [@lrb] - [@qb] * DIVIDE ( [@lra], [@qa] ) )", CAD, "Price-volume-mix", "Change in list price per case on compare-year cases.", "Effet prix courant"),
        ("PVM Discounts & Promotions", _PVM_T + "\nRETURN\n    SUMX ( t, ( [@rb] - [@lrb] ) - [@qb] * DIVIDE ( [@ra] - [@lra], [@qa] ) )", CAD, "Price-volume-mix", "Change in discount per case on compare-year cases.", "Effet remises et promotions"),
        ("PVM Cost", _PVM_T + "\nRETURN\n    - SUMX ( t, [@cb] - [@qb] * DIVIDE ( [@ca], [@qa] ) )", CAD, "Price-volume-mix", "Change in landed cost per case on compare-year cases (negative when cost rises).", "Effet coût"),
        ("PVM Check", "ROUND ( [PVM GM 2023] - [PVM GM 2019] - [PVM Volume] - [PVM Mix] - [PVM List Price] - [PVM Discounts & Promotions] - [PVM Cost], 2 )", CAD2, "Price-volume-mix", "Must be 0: the bridge reconciles.", "Contrôle du pont"),
    ],
    "fact_promotion": [
        ("Promo Events", "COUNTROWS ( fact_promotion )", NUM, "Promotions", "Number of promotion events.", "Événements promotionnels"),
        ("Trade Spend", "SUM ( fact_promotion[trade_spend] )", CAD, "Promotions", "Price investment plus fixed promotion fee.", "Dépenses commerciales"),
        ("Net Incremental Margin", "SUM ( fact_promotion[net_incremental_margin] )", CAD, "Promotions", "Incremental margin after trade spend and the post-promotion dip.", "Marge incrémentale nette"),
        ("Promo ROI", "DIVIDE ( [Net Incremental Margin], [Trade Spend] )", PCT, "Promotions", "Net incremental margin per dollar of trade spend.", "Rendement promotionnel"),
        ("Events Paid Back", "COUNTROWS ( FILTER ( fact_promotion, fact_promotion[roi] > 0 ) )", NUM, "Promotions", "Events with positive ROI.", "Événements rentables"),
        ("Median Break-even Lift", "MEDIAN ( fact_promotion[breakeven_uplift] )", "0.00", "Promotions", "Lift needed to pay back the price cut and fee.", "Hausse médiane au seuil"),
        ("Lift Estimate Error (pts)", "AVERAGE ( fact_promotion[uplift_error_pts] )", "0.0", "Promotions", "Mean absolute gap between estimated and planted lift, in points.", "Erreur d'estimation (pts)"),
    ],
}

ROLES = {
    "Contracts team": (
        "Static role: sees institutional contract customers only.",
        {"dim_segment": 'dim_segment[segment_id] = "contract"'},
    ),
    "Segment manager (dynamic)": (
        "Dynamic role: each signed-in user sees the segments mapped to their email in security_user_segment.",
        {
            "dim_segment": "dim_segment[segment_id]\n    IN CALCULATETABLE (\n        VALUES ( security_user_segment[segment_id] ),\n        security_user_segment[user_email] = USERPRINCIPALNAME ()\n    )",
            "security_user_segment": "security_user_segment[user_email] = USERPRINCIPALNAME ()",
        },
    ),
}

SECURITY_ROWS = [
    ("fine.dining.manager@example.com", "fine_dining"),
    ("restaurants.manager@example.com", "casual"),
    ("hotels.manager@example.com", "hotels"),
    ("contracts.manager@example.com", "contract"),
    ("pricing.lead@example.com", "fine_dining"),
    ("pricing.lead@example.com", "casual"),
    ("pricing.lead@example.com", "hotels"),
    ("pricing.lead@example.com", "contract"),
]

M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date", "boolean": "type logical"}


def tag(*parts: str) -> str:
    """Stable lineage tag, so regenerating the model does not churn Git diffs."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "market-pulse/" + "/".join(parts)))


def q(name: str) -> str:
    """TMDL object name, quoted when it is not a plain identifier."""
    return name if name.replace("_", "").isalnum() and not name[0].isdigit() else "'" + name.replace("'", "''") + "'"


def indent(text: str, tabs: int) -> str:
    return "\n".join("\t" * tabs + line if line.strip() else "" for line in text.splitlines())


def csv_header(rel: str) -> list[str]:
    with open(OUT / rel, encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def table_tmdl(name: str) -> str:
    rel, desc, _fr, cols = TABLES[name]
    header = csv_header(rel)
    if header != list(cols):
        raise ValueError(f"{rel}: CSV columns {header} differ from model columns {list(cols)}")
    out = [f"/// {desc}", f"table {name}", f"\tlineageTag: {tag(name)}", ""]
    for c, (dtype, fmt, _) in cols.items():
        out.append(f"\tcolumn {q(c)}")
        out.append(f"\t\tdataType: {dtype}")
        out.append(f"\t\tlineageTag: {tag(name, c)}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        if KEYS.get(name) == c:
            out.append("\t\tisKey")
        if c in HIDDEN and name.startswith("fact_"):
            out.append("\t\tisHidden")
        out.append("\t\tsummarizeBy: none")
        out.append(f"\t\tsourceColumn: {c}")
        out.append("")
    for m_name, dax, fmt, folder, mdesc, _ in MEASURES.get(name, []):
        out.append(f"\t/// {mdesc}")
        if "\n" in dax:
            out.append(f"\tmeasure {q(m_name)} =")
            out.append(indent(dax, 3))
        else:
            out.append(f"\tmeasure {q(m_name)} = {dax}")
        out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tdisplayFolder: {folder}")
        out.append(f"\t\tlineageTag: {tag(name, 'measure', m_name)}")
        out.append("")
    types = ", ".join(f'{{"{c}", {M_TYPES[t]}}}' for c, (t, _, _) in cols.items())
    m = (
        "let\n"
        f'    Source = Csv.Document(Web.Contents(SourceRoot, [RelativePath = "{rel}"]), '
        "[Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n"
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")\n'
        "in\n"
        "    Typed"
    )
    out += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =", indent(m, 4), ""]
    return "\n".join(out) + "\n"


def security_tmdl() -> str:
    rows = ", ".join(f'{{ "{e}", "{s}" }}' for e, s in SECURITY_ROWS)
    return (
        "/// Illustrative user-to-segment map for dynamic row-level security. Replace the emails with real accounts.\n"
        "table security_user_segment\n"
        "\tisHidden\n"
        f"\tlineageTag: {tag('security_user_segment')}\n\n"
        "\tcolumn user_email\n\t\tdataType: string\n\t\tisHidden\n\t\tisNameInferred\n\t\tsummarizeBy: none\n\t\tsourceColumn: [user_email]\n\n"
        "\tcolumn segment_id\n\t\tdataType: string\n\t\tisHidden\n\t\tisNameInferred\n\t\tsummarizeBy: none\n\t\tsourceColumn: [segment_id]\n\n"
        "\tpartition security_user_segment = calculated\n\t\tmode: import\n\t\tsource =\n"
        + indent(f'DATATABLE (\n    "user_email", STRING,\n    "segment_id", STRING,\n    {{ {rows} }}\n)', 4)
        + "\n"
    )


def culture_tmdl() -> str:
    out = ["cultureInfo fr-CA", "", "\ttranslations", "", "\t\tmodel Model"]
    for name, (_rel, _desc, fr, cols) in TABLES.items():
        out += ["", f"\t\t\ttable {name}", f"\t\t\t\tcaption: {fr}"]
        for c, (_t, _f, cfr) in cols.items():
            out += ["", f"\t\t\t\tcolumn {q(c)}", f"\t\t\t\t\tcaption: {cfr}"]
        for m_name, *_rest, mfr in MEASURES.get(name, []):
            out += ["", f"\t\t\t\tmeasure {q(m_name)}", f"\t\t\t\t\tcaption: {mfr}"]
    return "\n".join(out) + "\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    d = SM / "definition"
    write(SM / "definition.pbism", json.dumps({"version": "4.0", "settings": {}}, indent=2) + "\n")
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    write(
        d / "model.tmdl",
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tdiscourageImplicitMeasures\n\tsourceQueryCulture: en-US\n",
    )
    write(
        d / "expressions.tmdl",
        "/// Folder or URL holding the pipeline outputs (must end with a slash). Default: the public GitHub copy.\n"
        f'expression SourceRoot = "{RAW}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n',
    )
    for name in TABLES:
        write(d / "tables" / f"{name}.tmdl", table_tmdl(name))
    write(d / "tables" / "security_user_segment.tmdl", security_tmdl())
    rel = []
    for ft, fc, dt, dc in RELATIONSHIPS:
        rel += [f"relationship {ft}_{fc}_to_{dt}", f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {dt}.{dc}", ""]
    write(d / "relationships.tmdl", "\n".join(rel))
    for role, (desc, perms) in ROLES.items():
        lines = [f"/// {desc}", f"role {q(role)}", "\tmodelPermission: read", ""]
        for t, expr in perms.items():
            if "\n" in expr:
                lines += [f"\ttablePermission {t} =", indent(expr, 3), ""]
            else:
                lines += [f"\ttablePermission {t} = {expr}", ""]
        write(d / "roles" / f"{role.split(' (')[0].replace(' ', '_')}.tmdl", "\n".join(lines))
    write(d / "cultures" / "fr-CA.tmdl", culture_tmdl())

    rp = PBI / "MarketPulse.Report"
    if rp.exists():
        shutil.rmtree(rp)
    platform = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    for folder, kind, name in [(SM, "SemanticModel", "Market Pulse model"), (rp, "Report", "Market Pulse")]:
        meta = {"$schema": platform, "metadata": {"type": kind, "displayName": name}, "config": {"version": "2.0", "logicalId": tag(kind)}}
        write(folder / ".platform", json.dumps(meta, indent=2) + "\n")
    schema = "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    write(rp / "definition.pbir", json.dumps({"$schema": schema + "definitionProperties/2.0.0/schema.json", "version": "4.0", "datasetReference": {"byPath": {"path": "../MarketPulse.SemanticModel"}}}, indent=2) + "\n")
    rd = rp / "definition"
    write(rd / "version.json", json.dumps({"$schema": schema + "definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2) + "\n")
    report = {
        "$schema": schema + "definition/report/1.2.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61", "type": "SharedResources"}},
        "layoutOptimization": "None",
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources", "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True, "useEnhancedTooltips": True},
    }
    write(rd / "report.json", json.dumps(report, indent=2) + "\n")
    page = "overview0000000000000"
    write(rd / "pages" / "pages.json", json.dumps({"$schema": schema + "definition/pagesMetadata/1.0.0/schema.json", "pageOrder": [page], "activePageName": page}, indent=2) + "\n")
    write(rd / "pages" / page / "page.json", json.dumps({"$schema": schema + "definition/page/2.1.0/schema.json", "name": page, "displayName": "Overview", "displayOption": "FitToPage", "width": 1280, "height": 720}, indent=2) + "\n")
    theme = rp / "StaticResources/SharedResources/BaseThemes/CY24SU10.json"
    theme.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PBI / "assets/CY24SU10.json", theme)
    write(
        PBI / "MarketPulse.pbip",
        json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0", "artifacts": [{"report": {"path": "MarketPulse.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2) + "\n",
    )
    write(PBI / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    dax = ["// Generated by build_powerbi_model.py from the same definitions as the TMDL model.", "// Relationships (single direction, many-to-one):"]
    dax += [f"//   {ft}[{fc}] -> {dt}[{dc}]" for ft, fc, dt, dc in RELATIONSHIPS]
    for table, ms in MEASURES.items():
        dax += ["", f"// ---- {table} ----"]
        for m_name, expr, *_ in ms:
            dax += ["", f"{m_name} =" if "\n" in expr else f"{m_name} = {expr}"]
            if "\n" in expr:
                dax.append(indent(expr, 1).replace("\t", "    "))
    write(PBI / "measures.dax", "\n".join(dax) + "\n")
    n_measures = sum(len(v) for v in MEASURES.values())
    print(f"TMDL model: {len(TABLES) + 1} tables, {len(RELATIONSHIPS)} relationships, {n_measures} measures, {len(ROLES)} roles, 1 culture")


if __name__ == "__main__":
    main()
