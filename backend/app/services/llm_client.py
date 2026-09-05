"""
Provider-agnostic LLM client.  Owner: BE2

Speaks the OpenAI-compatible /chat/completions shape, so Groq, xAI, DeepSeek,
Together and Gemini's compatibility endpoint all work by changing two
environment variables. No vendor SDK is imported anywhere in this project.

THREE RULES, all of them about surviving demo day:

1. Never on the critical path. Every caller must have a deterministic fallback.
   If this module returns None the application continues unchanged.
2. Cache to disk. A successful response is written to `ai_cache/` and replayed
   on any later failure, so a dead venue wifi cannot break the demo.
3. Hard timeout. A hanging request is worse than a failed one on stage.

AI is confined to LANGUAGE work - reading messy bank headers, drafting an
officer's summary. It never computes or influences a risk score. Section 63 BSA
2023 requires explaining how a result was produced, and a language model's
weights cannot be cross-examined.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from .. import config

log = logging.getLogger(__name__)

CACHE_DIR = config.DATA_DIR / "ai_cache"


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _cache_key(model: str, messages: list[dict[str, str]]) -> str:
    blob = json.dumps({"model": model, "messages": messages}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def read_cache(key: str) -> str | None:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))["content"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None
    return None


def write_cache(key: str, content: str, meta: dict[str, Any] | None = None) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(
        json.dumps({"content": content, "meta": meta or {}}, indent=2),
        encoding="utf-8",
    )


def _post(payload: dict[str, Any]) -> httpx.Response:
    return httpx.post(
        f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=config.LLM_TIMEOUT_SECONDS,
    )


def complete(
    system: str,
    user: str,
    *,
    max_tokens: int = 1500,
    temperature: float = 0.2,
    use_cache: bool = True,
) -> tuple[str | None, str]:
    """Return (content, provenance).

    `provenance` is one of "live", "cache" or "unavailable" and is recorded in
    the dossier, so a reader always knows whether prose was generated now,
    replayed from cache, or fell back to a deterministic template.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    key = _cache_key(config.LLM_MODEL or "none", messages)

    if not config.LLM_CONFIGURED:
        cached = read_cache(key) if use_cache else None
        return (cached, "cache") if cached else (None, "unavailable")

    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Reasoning models (gpt-oss, o-series and friends) spend max_tokens on
        # hidden reasoning FIRST. Left unbounded, a short budget is consumed
        # entirely by reasoning and `content` comes back as an empty string with
        # finish_reason "length" - a silent failure that looks like an outage.
        # "low" keeps reasoning cheap and leaves room for the actual answer.
        "reasoning_effort": "low",
    }

    try:
        r = _post(payload)
        if r.status_code == 400:
            # Providers that do not know `reasoning_effort` reject the request.
            # Drop it and retry, so the client stays genuinely provider-agnostic.
            payload.pop("reasoning_effort", None)
            r = _post(payload)
        r.raise_for_status()

        choice = r.json()["choices"][0]
        content = (choice.get("message") or {}).get("content") or ""
        if not content.strip() and choice.get("finish_reason") == "length":
            raise ValueError(
                "completion truncated before any content - raise max_tokens"
            )
        if content.strip():
            write_cache(key, content, {"model": config.LLM_MODEL})
            return content.strip(), "live"
        raise ValueError("empty completion")

    except Exception as exc:  # noqa: BLE001 - any failure must degrade, not raise
        log.warning("LLM call failed (%s); falling back", exc.__class__.__name__)
        cached = read_cache(key) if use_cache else None
        return (cached, "cache") if cached else (None, "unavailable")


def prewarm(system: str, user: str, **kw) -> str:
    """Force a live call and cache it. Run before the demo so every AI feature
    has a warm cache and the network becomes optional."""
    content, prov = complete(system, user, use_cache=False, **kw)
    return prov if content else "failed"
