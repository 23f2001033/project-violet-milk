"""
Project Violet Milk — API entrypoint.

Run (from the repository root):
    .venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --reload --port 8000

Interactive contract:  http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from . import config, db
from .models import ComponentHealth, DataMode, HealthResponse
from .routers import audit, cases, evidence, graph, report, risk, timeline
from .seed import seed_demo_case

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

for r in (cases, evidence, graph, risk, timeline, audit, report):
    app.include_router(r.router)

# Initialise and seed at import rather than on a startup event. A startup hook
# does not fire for a module-level TestClient, which silently left the schema
# missing under pytest. This is idempotent and runs identically under uvicorn,
# TestClient and any ad-hoc script.
seed_demo_case()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/api/health", response_model=HealthResponse, tags=["system"],
         summary="System status")
def health():
    components = ComponentHealth(
        database=db.healthy(),
        graph_engine=True,
        report_engine=False,    # lands in Phase 5
        llm_configured=config.LLM_CONFIGURED,
        etherscan_configured=config.ETHERSCAN_CONFIGURED,
    )
    healthy = components.database and components.graph_engine
    return HealthResponse(
        status="ok" if healthy else "degraded",
        data_mode=DataMode(config.DATA_MODE),
        components=components,
    )
