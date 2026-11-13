"""Exercise the actual Streamlit script and user controls without a network service."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_app_default_and_commercial_and_budget_controls():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    assert not app.exception
    assert len(app.tabs) == 11
    assert any("Price, mix & promotions" == tab.label for tab in app.tabs)
    assert any("Customer terms & margin variance" == tab.label for tab in app.tabs)
    assert any("Customer & pricing desk" == tab.label for tab in app.tabs)
    assert any("Supplier comparison" == tab.label for tab in app.tabs)
    for slider in app.slider:
        if slider.label == "Volume change":
            slider.set_value(-0.10)
        if slider.label == "Price increase requiring Finance review":
            slider.set_value(0.05)
    app.run()
    assert not app.exception
    for slider in app.slider:
        if slider.label == "Maximum supplier lead time (days)":
            slider.set_value(0)
    app.run()
    assert not app.exception
    supplier_metric = next(m for m in app.metric if m.label == "Items with a feasible single supplier")
    assert supplier_metric.value == "0"
    for select in app.selectbox:
        if select.label == "Report week":
            select.select_index(len(select.options) - 1)
    for number in app.number_input:
        if number.label == "Current list price (CAD/case)":
            number.set_value(0.0)
    app.run()
    assert not app.exception
    assert any("Enter a positive current list price" in item.value for item in app.info)
    for select in app.selectbox:
        if select.label == "Commercial scenario week":
            select.select_index(len(select.options) - 1)
            break
    app.run()
    assert not app.exception


def test_app_terms_tab_and_star_schema_controls():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    app.multiselect(key="var_cats").set_value(["Leafy & lettuce"]).run()
    app.multiselect(key="var_segs").set_value(["Institutional contracts"]).run()
    assert not app.exception
    week = app.selectbox(key="pl_week")
    week.set_value(week.options[5]).run()
    for q in ["02_margin_variance_by_month.sql", "03_reprice_list.sql"]:
        app.selectbox(key="sqlq").set_value(q).run()
    assert not app.exception
    app.multiselect(key="var_segs").set_value([]).run()
    assert not app.exception
    assert any("Pick at least one" in w.value for w in app.warning)


def test_app_rgm_tab_calculator():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    app.slider(key="be_depth").set_value(0.30).run()
    assert not app.exception
    assert any("no lift breaks even" in e.value for e in app.error)
    app.slider(key="be_depth").set_value(0.10).run()
    assert not app.exception
