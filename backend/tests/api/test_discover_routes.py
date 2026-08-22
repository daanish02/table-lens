from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_post_discover_kicks_off_run_and_returns_run_id():
    with patch("app.api.routes.discover.run_discovery", return_value="fake-run-id"):
        response = client.post("/api/discover", json={"db_url": "postgres://fake"})
    assert response.status_code == 202
    assert response.json() == {"run_id": "fake-run-id"}


def test_get_discover_status_returns_run_state():
    with patch("app.api.routes.discover.get_discovery_status", return_value={"run_id": "fake-run-id", "status": "done", "step": None, "error": None}):
        response = client.get("/api/discover/status/fake-run-id")
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_get_discover_status_404_for_unknown_run():
    with patch("app.api.routes.discover.get_discovery_status", return_value=None):
        response = client.get("/api/discover/status/unknown-run-id")
    assert response.status_code == 404


def test_get_discover_overview_returns_stats_and_last_run():
    fake_stats = {"table_count": 5, "column_count": 40, "row_count": 100000}
    fake_run = {"run_id": "fake-run-id", "status": "done", "started_at": None, "finished_at": None, "total_tables": 5, "tables_done": 5}
    with patch("app.api.routes.discover.get_overview_stats", return_value=fake_stats), \
         patch("app.api.routes.discover.get_last_run", return_value=fake_run):
        response = client.get("/api/discover/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["stats"] == fake_stats
    assert body["last_run"] == fake_run
