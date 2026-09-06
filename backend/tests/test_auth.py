"""
Authentication, and the custody guarantee it exists to provide.

Before this, `uploaded_by` was a form field the client filled in and the
frontend hard-coded "IO_SHARMA". Anyone on the network could file evidence as
any officer, which made the chain of custody worthless in exactly the way that
matters.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.services import auth

from ._client import make_client

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"

client = make_client()
anon = TestClient(app)          # deliberately unauthenticated


# ------------------------------------------------------------- passwords

def test_passwords_are_salted_and_not_recoverable():
    h1, s1 = auth.hash_password("correct-horse")
    h2, s2 = auth.hash_password("correct-horse")
    assert s1 != s2, "each password needs its own salt"
    assert h1 != h2, "identical passwords must not produce identical hashes"
    assert "correct-horse" not in h1


def test_password_verification_round_trips():
    h, s = auth.hash_password("s3cret")
    assert auth.verify_password("s3cret", h, s) is True
    assert auth.verify_password("wrong", h, s) is False
    assert auth.verify_password("s3cret", h, "not-hex") is False


# ---------------------------------------------------------------- tokens

def test_a_token_round_trips():
    token, _ = auth.issue_token("IO_TEST")
    assert auth.read_token(token) == "IO_TEST"


def test_a_tampered_token_is_rejected():
    """The signature is the whole point: a client must not be able to edit the
    subject and become another officer."""
    token, _ = auth.issue_token("IO_TEST")
    body, sig = token.split(".", 1)
    forged = auth._b64(b'{"sub":"IO_CHIEF","exp":"2099-01-01T00:00:00+00:00"}')
    assert auth.read_token(f"{forged}.{sig}") is None
    assert auth.read_token(token[:-4] + "AAAA") is None
    assert auth.read_token("garbage") is None


def test_an_expired_token_is_rejected():
    token, _ = auth.issue_token("IO_TEST", hours=-1)
    assert auth.read_token(token) is None


def test_a_token_signed_with_another_secret_is_rejected(monkeypatch):
    token, _ = auth.issue_token("IO_TEST")
    monkeypatch.setattr(config, "AUTH_SECRET", "a-different-secret")
    assert auth.read_token(token) is None


# ------------------------------------------------------------- endpoints

def test_case_data_requires_a_session():
    for path in (f"/api/cases/{CASE}/graph", f"/api/cases/{CASE}/audit",
                 f"/api/cases/{CASE}/timeline", "/api/cases"):
        assert anon.get(path).status_code == 401, f"{path} is unprotected"


def test_mutations_require_a_session():
    assert anon.post(f"/api/cases/{CASE}/report").status_code == 401
    assert anon.post(f"/api/cases/{CASE}/trace",
                     json={"seed": SEED}).status_code == 401


def test_health_and_login_stay_open():
    """An operator must be able to check the service and sign in."""
    assert anon.get("/api/health").status_code == 200
    assert anon.post("/api/auth/login",
                     json={"user_id": "x", "password": "y"}).status_code == 401


def test_login_succeeds_and_identifies_the_officer():
    r = anon.post("/api/auth/login", json={
        "user_id": config.DEFAULT_IO_NAME,
        "password": config.DEMO_OFFICER_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["user_id"] == config.DEFAULT_IO_NAME
    assert body["token"] and body["expires_at"]


def test_bad_credentials_do_not_reveal_whether_the_user_exists():
    """Different messages here turn the endpoint into a user-enumeration
    oracle."""
    a = anon.post("/api/auth/login", json={
        "user_id": config.DEFAULT_IO_NAME, "password": "wrong"})
    b = anon.post("/api/auth/login", json={
        "user_id": "NO_SUCH_OFFICER", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_me_returns_the_signed_in_officer():
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["user_id"] == config.DEFAULT_IO_NAME


# ------------------------------------------------- THE custody guarantee

def test_custody_identity_comes_from_the_session_not_the_request():
    """A caller must not be able to file evidence as somebody else, even by
    saying so explicitly in the form body."""
    import hashlib

    csv = b"from,to,amount,asset,timestamp\n"
    r = client.post(
        f"/api/cases/{CASE}/evidence",
        files={"file": ("identity.csv", csv, "text/csv")},
        data={"sha256_client": hashlib.sha256(csv).hexdigest(),
              "is_synthetic": "true",
              "uploaded_by": "IO_IMPOSTER"},      # ignored on purpose
    )
    assert r.status_code == 201
    assert r.json()["uploaded_by"] == config.DEFAULT_IO_NAME

    audit = client.get(f"/api/cases/{CASE}/audit").json()
    entry = next(a for a in audit if a["target"] == "identity.csv")
    assert entry["user_id"] == config.DEFAULT_IO_NAME
    assert entry["user_id"] != "IO_IMPOSTER"
    assert client.get(f"/api/cases/{CASE}/audit/verify").json()["intact"] is True


def test_a_default_password_is_reported_not_hidden():
    """An instance left on the documented demo password must never look like a
    secured one."""
    assert auth.using_default_password() is True
    body = anon.get("/api/health").json()["components"]
    assert body["using_default_password"] is True
    assert body["auth_enabled"] is True

    login = anon.post("/api/auth/login", json={
        "user_id": config.DEFAULT_IO_NAME,
        "password": config.DEMO_OFFICER_PASSWORD}).json()
    assert "demo password" in (login["warning"] or "").lower()
