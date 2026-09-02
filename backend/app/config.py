import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("PM_DB_PATH", DATA_DIR / "app.db"))

SESSION_TTL_HOURS = 24 * 14
SESSION_COOKIE = "pm_session"

CLAUDE_BINARY = os.environ.get("PM_CLAUDE_BINARY") or os.environ.get("CLAUDE_CODE_EXECPATH") or "claude"
CLAUDE_MODEL = os.environ.get("PM_CLAUDE_MODEL", "claude-sonnet-5")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

SEARCH_TIMEOUT_SECONDS = int(os.environ.get("PM_SEARCH_TIMEOUT", "900"))
BUDGET_SEARCHES = int(os.environ.get("PM_BUDGET_SEARCHES", "6"))
BUDGET_FETCHES = int(os.environ.get("PM_BUDGET_FETCHES", "10"))
HARD_CAP_SEARCHES = int(os.environ.get("PM_CAP_SEARCHES", "12"))
HARD_CAP_FETCHES = int(os.environ.get("PM_CAP_FETCHES", "18"))
FORCED_PROVIDER = os.environ.get("PM_PROVIDER", "")

WEIGHTS = {
    "interest": 0.40,
    "location": 0.25,
    "compensation": 0.15,
    "timeframe": 0.20,
}
