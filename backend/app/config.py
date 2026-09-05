"""Environment configuration. Read once at import, never re-read."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
MOCKS_DIR = DATA_DIR / "mocks"
LIVE_CACHE_DIR = DATA_DIR / "live_cache"
REPORTS_DIR = ROOT / "backend" / "generated_reports"


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


# --- Etherscan -------------------------------------------------------------
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()
ETHERSCAN_BASE_URL = os.getenv(
    "ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api"
).strip()
ETHERSCAN_CHAIN_ID = _int("ETHERSCAN_CHAIN_ID", 1)

# --- LLM: any OpenAI-compatible provider -----------------------------------
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_TIMEOUT_SECONDS = _int("LLM_TIMEOUT_SECONDS", 20)

# --- Application -----------------------------------------------------------
DATA_MODE = os.getenv("DATA_MODE", "synthetic").strip()
DB_PATH = ROOT / os.getenv("DB_PATH", "./violet.db").lstrip("./")
DEFAULT_IO_NAME = os.getenv("DEFAULT_IO_NAME", "IO_SHARMA").strip()

# --- Trace bounds (SPEC 07) ------------------------------------------------
MAX_TRACE_DEPTH = _int("MAX_TRACE_DEPTH", 3)
MAX_EDGES_PER_NODE = _int("MAX_EDGES_PER_NODE", 20)
MIN_AMOUNT_INR = _float("MIN_AMOUNT_INR", 10000.0)
TIME_WINDOW_HOURS = _int("TIME_WINDOW_HOURS", 72)

# --- Demo constants (SPEC 09) ----------------------------------------------
DEMO_INR_PER_USDT = _float("DEMO_INR_PER_USDT", 90.38)
DEMO_CASE_ID = "CP-CYBER-2026-001"

# --- Derived flags ---------------------------------------------------------
LLM_CONFIGURED = bool(LLM_API_KEY and LLM_BASE_URL and LLM_MODEL)
ETHERSCAN_CONFIGURED = bool(ETHERSCAN_API_KEY)

DILUTION_THRESHOLD = 0.30
