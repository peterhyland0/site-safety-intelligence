"""Runtime configuration. Paths work locally (repo data/) and on Modal (/vol)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

DATA_DIR = Path(os.environ.get("SSI_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
REFERENCE_RAW_DIR = RAW_DIR / "reference"
BUILD_DIR = DATA_DIR / "build"
CURRENT_POINTER = BUILD_DIR / "CURRENT"  # contains the file name of the live warehouse

PIPELINE_DIR = Path(__file__).resolve().parent / "pipeline"
SQL_DIR = PIPELINE_DIR / "sql"
REF_DIR = PIPELINE_DIR / "ref"

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/ssi")
# LangSmith tracing: on when a key is set, unless LANGSMITH_TRACING=false (e.g. the plan's monthly trace
# allowance is used up; the AI calls still work, only their logging is rejected).
TRACING = bool(os.environ.get("LANGSMITH_API_KEY")) and \
    os.environ.get("LANGSMITH_TRACING", "true").strip().lower() not in ("false", "0", "no", "off")
MODEL = os.environ.get("SSI_MODEL", "claude-sonnet-5-5")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
DAILY_TOKEN_BUDGET = int(os.environ.get("SSI_DAILY_TOKEN_BUDGET", "2000000"))

# How much OSHA history the warehouse keeps: inspections opened in the last N years before the newest
# inspection in the data (0 = all years, back to 1972). Default 10.
HISTORY_YEARS = int(os.environ.get("SSI_HISTORY_YEARS", "10"))

# Verdict and matching thresholds (documented in the README)
RED_FLAG_RECENCY_YEARS = 10
BENCHMARK_MIN_PEERS = 30
BENCHMARK_MIN_RATED_INSPECTIONS = 3
DISTINCTIVE_MAX_VARIETY = 5
GENERIC_MIN_VARIETY = 25
SHARED_OFFICE_MIN_CORES = 6
RELATED_MIN_CONSTRUCTION_SHARE = 0.2  # related facilities only for firms with >= 20% construction-coded inspections
# uncertain groups per sub sent to the AI, most inspections first (the rest stay possible; red flags still reach
# the GC). 15 when every call was the LLM; Jev answers in ~0.25 s for a fraction of a cent, so smaller lookalike
# groups get cleared too.
ADJUDICATE_MAX_CLUSTERS = 50
QUESTION_GROUP_THRESHOLD = 3  # past this many red-flag questions for a sub, one question per OSHA name
# The API resolves new subs' uncertain records itself (ssi/api/app.py resolve_later), not only when an open page asks;
# 0 leaves it to the page (the tests: it calls the adjudicator and the web search)
RESOLVE_ON_SERVER = os.environ.get("SSI_RESOLVE_ON_SERVER", "1") != "0"
RESOLVE_WORKERS = 2  # subs resolved at once by one server process


def current_warehouse() -> Path | None:
    """Path of the live warehouse, from the CURRENT pointer written at the end of a successful build."""
    if CURRENT_POINTER.exists():
        p = BUILD_DIR / CURRENT_POINTER.read_text().strip()
        if p.exists():
            return p
    return None
