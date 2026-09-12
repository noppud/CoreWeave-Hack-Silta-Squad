"""Public routes must work without exposing local artifacts or localhost links."""

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SILTA_HOSTED", "1")
    from silta.web import app

    with TestClient(app) as client:
        yield client


def test_public_reports_and_health(client):
    assert client.get("/health").json()["status"] == "ok"
    for name in ("guide.html", "evals.html", "slides.html"):
        response = client.get(f"/presentation/{name}")
        assert response.status_code == 200
        assert "http://localhost:" not in response.text
    assert client.get("/presentation/evals.json").json()["batches"]


def test_private_files_are_not_public_reports(client):
    for name in (".env", "web.py", "repair-events.json"):
        assert client.get(f"/presentation/{name}").status_code == 404


def test_presentations_have_independent_notebook_routes(client):
    assert "Interactive slides" in client.get("/slides/").text
    assert "SILTA CAD" in client.get("/demo/").text
