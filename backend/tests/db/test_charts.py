import os
import pytest

requires_db = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live network test — set RUN_LIVE_TESTS=1 to run",
)


@requires_db
def test_save_and_get_chart_round_trip():
    from sqlalchemy import text
    from app.db.connection import get_engine
    from app.db.charts import save_chart, get_chart, list_charts

    engine = get_engine()
    saved = save_chart(
        engine,
        title="__test_chart",
        question="how many claims?",
        sql="SELECT COUNT(*) FROM demo.claims",
        chart_type="bar",
        chart_config={"xAxis": {"type": "category"}},
        result_cache={"columns": ["count"], "rows": [{"count": 30000}]},
    )
    try:
        assert saved["id"]
        fetched = get_chart(engine, saved["id"])
        assert fetched["title"] == "__test_chart"
        assert fetched["chart_type"] == "bar"
        assert fetched["chart_config"]["xAxis"]["type"] == "category"
        assert fetched["result_cache"]["rows"][0]["count"] == 30000

        listed = list_charts(engine)
        assert any(c["id"] == saved["id"] for c in listed)
    finally:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM public.saved_charts WHERE id = :id"), {"id": saved["id"]})
            conn.commit()


@requires_db
def test_save_and_get_dashboard_round_trip():
    from sqlalchemy import text
    from app.db.connection import get_engine
    from app.db.charts import save_chart, save_dashboard, get_dashboard

    engine = get_engine()
    chart = save_chart(
        engine, title="__test_chart_for_dash", question="q", sql="SELECT 1",
        chart_type="bar", chart_config={}, result_cache={},
    )
    dashboard = save_dashboard(engine, title="__test_dashboard", chart_ids=[str(chart["id"])])
    try:
        fetched = get_dashboard(engine, dashboard["id"])
        assert fetched["title"] == "__test_dashboard"
        assert str(fetched["chart_ids"][0]) == str(chart["id"])
    finally:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM public.dashboards WHERE id = :id"), {"id": dashboard["id"]})
            conn.execute(text("DELETE FROM public.saved_charts WHERE id = :id"), {"id": chart["id"]})
            conn.commit()
