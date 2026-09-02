import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("PM_DB_PATH", DATA_DIR / "app.db"))

SESSION_TTL_HOURS = 24 * 14
SESSION_COOKIE = "pm_session"

CLAUDE_BINARY = os.environ.get("PM_CLAUDE_BINARY") or os.environ.get("CLAUDE_CODE_EXECPATH") or "claude"
CLAUDE_MODEL = os.environ.get("PM_CLAUDE_MODEL", "claude-haiku-4-5")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

SEARCH_TIMEOUT_SECONDS = int(os.environ.get("PM_SEARCH_TIMEOUT", "900"))
BUDGET_SEARCHES = int(os.environ.get("PM_BUDGET_SEARCHES", "4"))
BUDGET_FETCHES = int(os.environ.get("PM_BUDGET_FETCHES", "5"))
HARD_CAP_SEARCHES = int(os.environ.get("PM_CAP_SEARCHES", "6"))
HARD_CAP_FETCHES = int(os.environ.get("PM_CAP_FETCHES", "7"))
MAX_TURNS = os.environ.get("PM_MAX_TURNS", "18")

MAX_COST_USD = float(os.environ.get("PM_MAX_COST_USD", "0.40"))
COST_CEILING_USD = float(os.environ.get("PM_COST_CEILING_USD", "1.00"))
DEPTHS = {"sparsam": 0.20, "normal": 0.40, "gruendlich": 0.80}
WAVE_SIZE = int(os.environ.get("PM_WAVE_SIZE", "2"))

EXPECTED_ANGLE_COST = float(os.environ.get("PM_EXPECTED_ANGLE_COST", "0.13"))
RUNAWAY_FACTOR = float(os.environ.get("PM_RUNAWAY_FACTOR", "3.0"))

COST_PER_WEB_SEARCH = 0.01
COST_PER_FETCH = 0.022
COST_PER_TURN = 0.004
FORCED_PROVIDER = os.environ.get("PM_PROVIDER", "")

WEIGHTS = {
    "interest": 0.40,
    "location": 0.25,
    "compensation": 0.15,
    "timeframe": 0.20,
}
