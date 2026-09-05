"""
Phase 1 fixture loader.

Every endpoint is stubbed from the generated fixtures so FastAPI /docs renders
the complete API on day one and the frontend can integrate immediately.

In Phase 2 each router replaces its `load()` call with a real engine call. The
response SHAPE must not change - that is what keeps the frozen contract honest.
"""

import json
from functools import lru_cache
from typing import Any

from .config import MOCKS_DIR


@lru_cache(maxsize=None)
def load(name: str) -> Any:
    path = MOCKS_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing fixture {name!r}. Run: python backend/tools/generate_mocks.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))
