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
MODEL = os.environ.get("SSI_MODEL", "claude-sonnet-5-5")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
DAILY_TOKEN_BUDGET = int(os.environ.get("SSI_DAILY_TOKEN_BUDGET", "2000000"))

# Verdict and matching thresholds (documented in the README)
RED_FLAG_RECENCY_YEARS = 10
BENCHMARK_MIN_PEERS = 30
BENCHMARK_MIN_RATED_INSPECTIONS = 3
DISTINCTIVE_MAX_VARIETY = 5
GENERIC_MIN_VARIETY = 25
SHARED_OFFICE_MIN_CORES = 6
ADJUDICATE_MAX_CLUSTERS = 15
MAX_QUESTIONS_PER_SUB = 3  # more red-flag lookalikes stay visible as 'possible' (not counted)


def current_warehouse() -> Path | None:
    """Path of the live warehouse, from the CURRENT pointer written at the end of a successful build."""
    if CURRENT_POINTER.exists():
        p = BUILD_DIR / CURRENT_POINTER.read_text().strip()
        if p.exists():
            return p
    return None
