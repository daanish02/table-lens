from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_data_browse_returns_paginated_rows():
    fake_result = {
        "table": "claims", "page": 1, "page_size": 50, "total_rows": 3,
        "columns": ["id", "amount"], "rows": [{"id": 1, "amount": 100}],
    }
    with patch("app.api.routes.data.browse_table", return_value=fake_result):
        response = client.get("/api/data/claims")
    assert response.status_code == 200
    assert response.json() == fake_result


def test_get_data_browse_404_for_unknown_table():
    with patch("app.api.routes.data.browse_table", side_effect=ValueError("unknown table: nope")):
        response = client.get("/api/data/nope")
    assert response.status_code == 404


def test_get_data_browse_passes_page_params():
    with patch("app.api.routes.data.browse_table", return_value={}) as mock_browse:
        client.get("/api/data/claims?page=2&page_size=25")
    mock_browse.assert_called_once()
    args = mock_browse.call_args[0]
    assert args[1] == "claims"
    assert args[2] == 2
    assert args[3] == 25
