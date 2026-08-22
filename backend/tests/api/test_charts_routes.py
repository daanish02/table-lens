from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_post_charts_saves_and_returns_id():
    fake_row = {"id": "11111111-1111-1111-1111-111111111111", "created_at": "2026-01-01T00:00:00"}
    with patch("app.api.routes.charts.save_chart", return_value=fake_row) as mock_save:
        response = client.post("/api/charts", json={
            "title": "Claims by status", "question": "how many claims by status?",
            "sql": "SELECT status, COUNT(*) FROM demo.claims GROUP BY status",
            "chart_type": "bar", "chart_config": {"xAxis": {}}, "result_cache": {"rows": []},
        })
    assert response.status_code == 200
    assert response.json() == fake_row
    mock_save.assert_called_once()


def test_get_charts_returns_list():
    with patch("app.api.routes.charts.list_charts", return_value=[{"id": "x", "title": "t"}]):
        response = client.get("/api/charts")
    assert response.status_code == 200
    assert response.json() == {"charts": [{"id": "x", "title": "t"}]}


def test_get_chart_404_when_missing():
    with patch("app.api.routes.charts.get_chart", return_value=None):
        response = client.get("/api/charts/does-not-exist")
    assert response.status_code == 404


def test_post_dashboards_saves_and_returns_id():
    fake_row = {"id": "22222222-2222-2222-2222-222222222222", "created_at": "2026-01-01T00:00:00"}
    with patch("app.api.routes.charts.save_dashboard", return_value=fake_row) as mock_save:
        response = client.post("/api/dashboards", json={"title": "Q4 Review", "chart_ids": ["a", "b"]})
    assert response.status_code == 200
    assert response.json() == fake_row
    mock_save.assert_called_once_with(mock_save.call_args[0][0], "Q4 Review", ["a", "b"])


def test_get_dashboard_includes_its_charts():
    fake_dashboard = {"id": "d1", "title": "Q4", "chart_ids": ["c1", "c2"], "created_at": "2026-01-01T00:00:00"}
    fake_charts = [{"id": "c1"}, {"id": "c2"}]
    with patch("app.api.routes.charts.get_dashboard", return_value=fake_dashboard), \
         patch("app.api.routes.charts.get_charts", return_value=fake_charts):
        response = client.get("/api/dashboards/d1")
    assert response.status_code == 200
    body = response.json()
    assert body["charts"] == fake_charts


def test_get_dashboard_404_when_missing():
    with patch("app.api.routes.charts.get_dashboard", return_value=None):
        response = client.get("/api/dashboards/does-not-exist")
    assert response.status_code == 404
