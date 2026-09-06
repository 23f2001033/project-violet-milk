"""
Authentication.  Owner: BE3

WHY THIS EXISTS
Until now `uploaded_by` was a form field the client filled in, and the
frontend hard-coded "IO_SHARMA". Anyone on the network could post evidence as
any officer. A chain of custody whose identity is supplied by the caller is
not a chain of custody - and that log is the legal spine of the dossier.

Every custody entry now records the identity from the verified session token,
never anything the request body claims.

DESIGN, and its limits - stated because a reviewer will ask
- Passwords: PBKDF2-HMAC-SHA256, 240k iterations, 16-byte per-user salt.
  Stdlib only; no dependency to audit.
- Sessions: an HMAC-signed token carrying user id and expiry. Signed, not
  encrypted - it hides nothing, it only proves the server issued it. There is
  no secret in the payload.
- Comparison is constant-time throughout, for both password and signature.
- This is single-tenant password auth for a pilot workstation. It is NOT
  SSO, MFA, or a directory integration, and a production deployment inside a
  police network would use the force's own identity provider. Say so rather
  than implying more.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from .. import config
from ..db import cursor

ITERATIONS = 240_000
SALT_BYTES = 16


# --------------------------------------------------------------- passwords

def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                             ITERATIONS)
    return dk.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate, _ = hash_password(password, salt)
    # Constant-time: a timing difference here leaks the hash byte by byte.
    return hmac.compare_digest(candidate, password_hash)


# ------------------------------------------------------------------ tokens

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(user_id: str, hours: int | None = None) -> tuple[str, str]:
    """Return (token, expiry ISO). Signed with AUTH_SECRET."""
    expires = datetime.now(timezone.utc) + timedelta(
        hours=hours or config.AUTH_TOKEN_HOURS)
    payload = {"sub": user_id, "exp": expires.isoformat(),
               "jti": secrets.token_hex(8)}
    body = _b64(json.dumps(payload, sort_keys=True).encode())
    sig = _b64(hmac.new(config.AUTH_SECRET.encode(), body.encode(),
                        hashlib.sha256).digest())
    return f"{body}.{sig}", expires.isoformat()


def read_token(token: str) -> str | None:
    """Return the user id, or None if the token is invalid or expired."""
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None

    expected = _b64(hmac.new(config.AUTH_SECRET.encode(), body.encode(),
                             hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None

    try:
        payload = json.loads(_unb64(body))
        if datetime.fromisoformat(payload["exp"]) < datetime.now(timezone.utc):
            return None
        return payload["sub"]
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


# ------------------------------------------------------------------- users

def create_user(user_id: str, display_name: str, rank: str,
                password: str) -> dict:
    pw_hash, salt = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()
    with cursor() as conn:
        conn.execute(
            "INSERT INTO users (user_id, display_name, rank, password_hash, "
            "salt, created_at, active) VALUES (?,?,?,?,?,?,1)",
            (user_id, display_name, rank, pw_hash, salt, now),
        )
    return {"user_id": user_id, "display_name": display_name, "rank": rank}


def authenticate(user_id: str, password: str) -> dict | None:
    with cursor() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ? AND active = 1", (user_id,)
        ).fetchone()

    if not row:
        # Hash anyway, so a missing user and a wrong password take the same
        # time. Otherwise the endpoint becomes a user-enumeration oracle.
        hash_password(password)
        return None

    if not verify_password(password, row["password_hash"], row["salt"]):
        return None
    return {"user_id": row["user_id"], "display_name": row["display_name"],
            "rank": row["rank"]}


def get_user(user_id: str) -> dict | None:
    with cursor() as conn:
        row = conn.execute(
            "SELECT user_id, display_name, rank FROM users "
            "WHERE user_id = ? AND active = 1", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def using_default_password() -> bool:
    """True when the seeded officer still has the documented demo password.

    Surfaced in /health and shown as a banner, so an instance left on the
    default cannot quietly look like a secured one.
    """
    with cursor() as conn:
        row = conn.execute(
            "SELECT password_hash, salt FROM users WHERE user_id = ?",
            (config.DEFAULT_IO_NAME,),
        ).fetchone()
    if not row:
        return False
    return verify_password(config.DEMO_OFFICER_PASSWORD,
                           row["password_hash"], row["salt"])
