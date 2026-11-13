"""Static checks on the TMDL semantic model: it matches the pipeline outputs and every DAX reference resolves."""

import json
import re
from pathlib import Path

import pandas as pd

import build_powerbi_model as bpm

ROOT = Path(__file__).resolve().parents[1]
DEF = ROOT / "powerbi/MarketPulse.SemanticModel/definition"
SECURITY_COLS = {"user_email", "segment_id"}


def all_dax():
    for table, ms in bpm.MEASURES.items():
        for name, dax, *_ in ms:
            yield table, name, dax
    for role, (_, perms) in bpm.ROLES.items():
        for table, expr in perms.items():
            yield table, role, expr


def test_committed_tmdl_is_current():
    for name in bpm.TABLES:
        assert (DEF / "tables" / f"{name}.tmdl").read_text(encoding="utf-8") == bpm.table_tmdl(name), name
    assert (DEF / "cultures/fr-CA.tmdl").read_text(encoding="utf-8") == bpm.culture_tmdl()


def test_column_references_resolve():
    cols = {t: set(spec[3]) for t, spec in bpm.TABLES.items()} | {"security_user_segment": SECURITY_COLS}
    for _, name, dax in all_dax():
        for table, col in re.findall(r"(\w+)\[([^\]]+)\]", dax):
            assert table in cols, f"{name}: unknown table {table}"
            assert col in cols[table], f"{name}: unknown column {table}[{col}]"


def test_measure_references_resolve():
    measures = {n for ms in bpm.MEASURES.values() for n, *_ in ms}
    assert len(measures) == sum(len(ms) for ms in bpm.MEASURES.values()), "duplicate measure names"
    for _, name, dax in all_dax():
        for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", dax):
            assert ref in measures or ref.startswith("@"), f"{name}: unknown measure [{ref}]"
        assert dax.count("(") == dax.count(")"), f"{name}: unbalanced parentheses"


def test_relationships_are_many_to_one_on_keys():
    for ft, fc, dt, dc in bpm.RELATIONSHIPS:
        assert fc in bpm.TABLES[ft][3] and bpm.KEYS[dt] == dc
        fact = pd.read_csv(ROOT / "outputs" / bpm.TABLES[ft][0], usecols=[fc], dtype=str)
        dim = pd.read_csv(ROOT / "outputs" / bpm.TABLES[dt][0], usecols=[dc], dtype=str)
        assert dim[dc].is_unique, f"{dt}[{dc}] is not unique"
        assert set(fact[fc]) <= set(dim[dc]), f"{ft}[{fc}] has keys missing from {dt}"


def test_pvm_measure_algebra_matches_python_bridge():
    """Evaluate the DAX PVM formulas' algebra in pandas; it must equal the Python bridge to the cent."""
    w = pd.read_csv(ROOT / "outputs/rgm/SYNTHETIC_weekly_shipments.csv")
    g = w.groupby(["item_id", "year"])[["cases", "gm", "list_revenue", "revenue", "cogs"]].sum().unstack("year")
    g = g.dropna()
    qa, qb = g["cases"][2019], g["cases"][2023]
    QA, QB, GMA = qa.sum(), qb.sum(), g["gm"][2019].sum()
    dax = {
        "Gross margin 2019": GMA,
        "Volume": (QB - QA) / QA * GMA,
        "Mix": (qb * g["gm"][2019] / qa).sum() - QB / QA * GMA,
        "List price": (g["list_revenue"][2023] - qb * g["list_revenue"][2019] / qa).sum(),
        "Discounts & promotions": (
            (g["revenue"][2023] - g["list_revenue"][2023]) - qb * (g["revenue"][2019] - g["list_revenue"][2019]) / qa
        ).sum(),
        "Cost": -(g["cogs"][2023] - qb * g["cogs"][2019] / qa).sum(),
        "Gross margin 2023": g["gm"][2023].sum(),
    }
    facts = json.loads((ROOT / "outputs/rgm/rgm_facts.json").read_text(encoding="utf-8"))["bridge"]
    for k, v in dax.items():
        assert abs(v - facts[k]) < 0.01, (k, v, facts[k])
