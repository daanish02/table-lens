from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_post_visualize_returns_chart_spec():
    fake_spec = {
        "title": "Claims by Status",
        "chart_type": "pie",
        "option": {"series": [{"type": "pie", "data": [{"name": "APPROVED", "value": 8912}]}]},
    }
    with patch("app.api.routes.visualize.generate_chart", return_value=fake_spec) as mock_gen:
        response = client.post("/api/visualize", json={
            "question": "break down claims by status",
            "sql": "SELECT claim_status, COUNT(*) FROM demo.claims GROUP BY claim_status",
            "headline": "APPROVED is the largest bucket.",
            "columns": ["claim_status", "claim_count"],
            "rows": [{"claim_status": "APPROVED", "claim_count": 8912}],
        })
    assert response.status_code == 200
    assert response.json() == fake_spec
    mock_gen.assert_called_once_with(
        "break down claims by status",
        "SELECT claim_status, COUNT(*) FROM demo.claims GROUP BY claim_status",
        "APPROVED is the largest bucket.",
        ["claim_status", "claim_count"],
        [{"claim_status": "APPROVED", "claim_count": 8912}],
        theme="dark",
    )


def test_post_visualize_defaults_missing_headline_to_empty_string():
    with patch("app.api.routes.visualize.generate_chart", return_value={}) as mock_gen:
        client.post("/api/visualize", json={
            "question": "q", "sql": "SELECT 1", "columns": ["a"], "rows": [{"a": 1}],
        })
    args, _ = mock_gen.call_args
    assert args[2] == ""


def test_post_visualize_passes_theme():
    with patch("app.api.routes.visualize.generate_chart", return_value={}) as mock_gen:
        client.post("/api/visualize", json={
            "question": "q", "sql": "SELECT 1", "columns": ["a"], "rows": [{"a": 1}], "theme": "light",
        })
    _, kwargs = mock_gen.call_args
    assert kwargs["theme"] == "light"


def test_post_visualize_requires_fields():
    response = client.post("/api/visualize", json={"question": "q"})
    assert response.status_code == 422
