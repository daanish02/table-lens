import json
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        assert block.startswith("data: ")
        events.append(json.loads(block[len("data: "):]))
    return events


def test_post_query_streams_events_ending_in_done():
    def fake_stream(engine, question, history=None):
        yield {"type": "tool_call", "tool": "search_tables", "args": {"query": "claims"}}
        yield {"type": "answer_delta", "text": "There are "}
        yield {"type": "answer_delta", "text": "30000 claims."}
        yield {
            "type": "done",
            "answer": "There are 30000 claims.",
            "sql": "SELECT COUNT(*) FROM demo.claims LIMIT 1000",
            "columns": ["count"], "rows": [{"count": 30000}], "row_count": 1,
            "headline": "There are 30,000 claims in total.",
        }

    with patch("app.api.routes.query.ask_stream", side_effect=fake_stream) as mock_stream:
        response = client.post("/api/query", json={"question": "how many claims are there?"})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert [e["type"] for e in events] == ["tool_call", "answer_delta", "answer_delta", "done"]
    assert events[-1]["sql"] == "SELECT COUNT(*) FROM demo.claims LIMIT 1000"
    assert "elapsed_ms" in events[-1]

    mock_stream.assert_called_once()
    args, kwargs = mock_stream.call_args
    assert args[1] == "how many claims are there?"
    assert kwargs["history"] == []


def test_post_query_passes_history():
    def fake_stream(engine, question, history=None):
        yield {"type": "done", "answer": "", "sql": None, "columns": None, "rows": None, "row_count": None, "headline": None}

    with patch("app.api.routes.query.ask_stream", side_effect=fake_stream) as mock_stream:
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
    _, kwargs = mock_stream.call_args
    assert kwargs["history"] == [("user", "how many claims are there?"), ("assistant", "There are 30,000 claims.")]


def test_post_query_stream_error_yields_graceful_done():
    def fake_stream(engine, question, history=None):
        yield {"type": "tool_call", "tool": "search_tables", "args": {}}
        raise RuntimeError("boom")

    with patch("app.api.routes.query.ask_stream", side_effect=fake_stream):
        response = client.post("/api/query", json={"question": "anything"})

    events = _parse_sse(response.text)
    assert events[-1]["type"] == "done"
    assert "Something went wrong" in events[-1]["answer"]


def test_post_query_requires_question():
    response = client.post("/api/query", json={})
    assert response.status_code == 422
