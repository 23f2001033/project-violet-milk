"""
Phase 7 - single-process serving and error handling.

On stage there is one command and one port. These tests guard the two ways
that arrangement can silently break: a catch-all route swallowing the API, and
an unexpected exception putting a stack trace on the projector.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import FRONTEND_BUILT, app

client = TestClient(app)


def test_api_still_answers_with_the_spa_mounted():
    """The regression this exists for: FastAPI matches routes in registration
    order, so a catch-all declared before the API routes swallows them. If the
    SPA mount is ever moved back up the module, this fails."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["status"] in {"ok", "degraded"}


def test_unknown_api_path_404s_as_json_not_html():
    """Returning the HTML shell for a mistyped API path turns a typo into an
    unreadable JSON parse error in the browser."""
    r = client.get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["detail"]


def test_openapi_and_docs_are_reachable():
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


@pytest.mark.skipif(not FRONTEND_BUILT,
                    reason="frontend/dist not built in this checkout")
def test_root_serves_the_application():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<div id=\"root\">" in r.text


@pytest.mark.skipif(not FRONTEND_BUILT,
                    reason="frontend/dist not built in this checkout")
def test_client_side_route_falls_back_to_the_shell():
    """A deep link or a refresh must not 404."""
    r = client.get("/some/client/route")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_health_reports_every_component():
    body = client.get("/api/health").json()["components"]
    assert body["database"] is True
    assert body["graph_engine"] is True
    assert body["report_engine"] is True   # implemented in Phase 5
