from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_post_query_returns_agent_result():
    fake_result = {
        "answer": "There are 30000 claims.",
        "sql": "SELECT COUNT(*) FROM demo.claims LIMIT 1000",
        "columns": ["count"],
        "rows": [{"count": 30000}],
        "row_count": 1,
        "headline": "There are 30,000 claims in total.",
    }
    with patch("app.api.routes.query.ask", return_value=fake_result) as mock_ask:
        response = client.post("/api/query", json={"question": "how many claims are there?"})
    assert response.status_code == 200
    assert response.json() == fake_result
    mock_ask.assert_called_once()
    args, kwargs = mock_ask.call_args
    assert args[1] == "how many claims are there?"
    assert kwargs["history"] == []


def test_post_query_passes_history():
    with patch("app.api.routes.query.ask", return_value={}) as mock_ask:
        client.post(
            "/api/query",
            json={
                "question": "and last month?",
                "history": [
                    {"role": "user", "content": "how many claims are there?"},
                    {"role": "assistant", "content": "There are 30,000 claims."},
                ],
            },
        )
    _, kwargs = mock_ask.call_args
    assert kwargs["history"] == [("user", "how many claims are there?"), ("assistant", "There are 30,000 claims.")]


def test_post_query_requires_question():
    response = client.post("/api/query", json={})
    assert response.status_code == 422
