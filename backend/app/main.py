"""
Project Violet Milk — API entrypoint.

Run (from the repository root):
    .venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --reload --port 8000

Interactive contract:  http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import logging

from . import config, db
from .config import ROOT
from .models import ComponentHealth, DataMode, HealthResponse
from .routers import (
    audit, auth, cases, evidence, graph, report, risk, timeline,
)
from .routers.auth import RequireUser
from .seed import seed_demo_case, seed_team_cases

log = logging.getLogger(__name__)

app = FastAPI(
    title="Project Violet Milk",
    version="0.1.0",
    description=(
        "Crypto flow tracking and analytics for Indian cyber-crime "
        "investigation.\n\n"
        "**DEMONSTRATION / SYNTHETIC DATA MODE.** Output provides analytical "
        "leads for investigative assistance. It does not constitute a legal "
        "finding of guilt, and does not identify any person without "
        "independent verification under Section 94 BNSS 2023."
    ),
)

# Vite dev server. In Phase 7 the built bundle is served from this same
# process, at which point cross-origin requests disappear entirely.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

# Everything touching case data requires a verified session. Health and login
# stay open so an operator can check the service and sign in.
for r in (cases, evidence, graph, risk, timeline, audit, report):
    app.include_router(r.router, dependencies=[RequireUser])

# Initialise and seed at import rather than on a startup event. A startup hook
# does not fire for a module-level TestClient, which silently left the schema
# missing under pytest. This is idempotent and runs identically under uvicorn,
# TestClient and any ad-hoc script.
seed_demo_case()
seed_team_cases()


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Never show a stack trace on stage.

    An unexpected failure returns the same {"detail": ...} shape as every
    other error, so the frontend renders it as a message instead of a blank
    screen. The trace still goes to the server log for us.
    """
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. The action was not "
                           "completed; nothing was recorded."},
    )


def _default_password() -> bool:
    try:
        from .services.auth import using_default_password
        return using_default_password()
    except Exception:  # noqa: BLE001 - health must never fail
        return False


@app.get("/api/health", response_model=HealthResponse, tags=["system"],
         summary="System status")
def health():
    components = ComponentHealth(
        database=db.healthy(),
        graph_engine=True,
        report_engine=True,
        llm_configured=config.LLM_CONFIGURED,
        etherscan_configured=config.ETHERSCAN_CONFIGURED,
        anchoring_configured=config.ANCHOR_CONFIGURED,
        auth_enabled=True,
        using_default_password=_default_password(),
    )
    healthy = components.database and components.graph_engine
    return HealthResponse(
        status="ok" if healthy else "degraded",
        data_mode=DataMode(config.DATA_MODE),
        components=components,
    )


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
#
# Phase 7: serve the built React bundle from this same process. On stage that
# means ONE command and ONE port - no second terminal, no Vite dev server, and
# no cross-origin step that can fail in front of a room.
#
#     cd frontend && npm run build
#     python -m uvicorn backend.app.main:app --port 8000
#
# With dist/ absent (normal during development) the API still runs and "/"
# redirects to the docs, so nothing breaks for the team.

DIST = ROOT / "frontend" / "dist"
FRONTEND_BUILT = (DIST / "index.html").is_file()


def _mount_frontend() -> None:
    """Must be called AFTER every API route is registered.

    FastAPI matches routes in registration order, so a catch-all declared
    earlier in the file silently swallows /api/health and everything after it.
    Invoking this at the very bottom of the module is load-bearing, not
    stylistic.
    """
    if not FRONTEND_BUILT:
        @app.get("/", include_in_schema=False)
        def root():
            return RedirectResponse("/docs")
        return

    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root():
        return FileResponse(DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """Serve index.html for any non-API path.

        An unmatched /api path must still 404 as JSON rather than quietly
        returning the HTML shell, which would turn a typo into an unreadable
        parse error in the browser.
        """
        if full_path.startswith("api/") or full_path in {"docs", "openapi.json"}:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (DIST / full_path).resolve()
        if candidate.is_file() and DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")


_mount_frontend()
