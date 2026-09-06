"""
Shared authenticated test client.

Case data now requires a verified session, so every suite signs in the seeded
officer once and reuses the token. Tests that need to assert the UNauthenticated
behaviour build their own bare TestClient.
"""

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app


def make_client() -> TestClient:
    client = TestClient(app)
    r = client.post("/api/auth/login", json={
        "user_id": config.DEFAULT_IO_NAME,
        "password": config.DEMO_OFFICER_PASSWORD,
    })
    assert r.status_code == 200, f"test login failed: {r.text}"
    client.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return client
