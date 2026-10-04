"""Modal deployment: the data build and the web app (API + SPA) share one Volume.

    uv run modal run modal_app.py::refresh      # download + build on Modal (first time: ~10 min)
    make deploy                                 # deploy the web app with its secrets (the nightly build is off)
    SSI_NIGHTLY=1 make deploy                   # ... and rebuild the data daily at 13:00 UTC

Secrets (created by you, never committed):
    modal secret create ssi-db DATABASE_URL=postgresql://...      (Postgres for the app layer)
    modal secret create ssi-anthropic ANTHROPIC_API_KEY=...       (optional: AI matcher + foreman)
    modal secret create ssi-jev JEV_API_KEY=...                   (optional: Jev adjudicates matches without red flags)
    modal secret create ssi-langsmith LANGSMITH_API_KEY=... LANGSMITH_PROJECT=site-safety-intelligence LANGSMITH_TRACING=true
    modal secret create ssi-tavily TAVILY_API_KEY=... SSI_PROFILE_BACKEND=tavily   (optional: web check + profiles)

Sign-in accounts live in the app database: create them with scripts/add_user.py (see docs/deploy.md).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import modal

APP_DIR = Path(__file__).parent
VOL_PATH = "/vol"

# Secrets are opt-in at deploy time, so the data job can run before they exist (Modal refuses to start an
# app that names a missing secret):
#   SSI_WITH_DB=1         -> ssi-db (DATABASE_URL: Postgres for the app layer; required by `web`)
#   SSI_WITH_GLM=1        -> ssi-glm (SSI_LLM_PROVIDER=openai_compat, SSI_LLM_FOREMAN_BASE_URL,
#                                     SSI_LLM_ADJUDICATOR_BASE_URL, SSI_LLM_MODAL_KEY, SSI_LLM_MODAL_SECRET)
#   SSI_WITH_ANTHROPIC=1  -> ssi-anthropic (ANTHROPIC_API_KEY)
#   SSI_WITH_LANGSMITH=1  -> ssi-langsmith (LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_TRACING)
#   SSI_WITH_JEV=1        -> ssi-jev (JEV_API_KEY: Jev for clusters without red flags; see docs/adjudicator.md)
#   SSI_WITH_TAVILY=1     -> ssi-tavily (TAVILY_API_KEY, SSI_PROFILE_BACKEND=tavily: the web check and company
#                                        profiles; both also need the adjudicator LLM)
# The container imports this file again and must find the same secrets, or it crash-loops ("Function has 2
# dependencies but container got 7 object ids"), so the flags set at deploy time go into the image's env.
SECRET_FLAGS = (("ssi-db", "SSI_WITH_DB"), ("ssi-glm", "SSI_WITH_GLM"), ("ssi-anthropic", "SSI_WITH_ANTHROPIC"),
                ("ssi-langsmith", "SSI_WITH_LANGSMITH"), ("ssi-jev", "SSI_WITH_JEV"), ("ssi-tavily", "SSI_WITH_TAVILY"))
with_flags = {flag: "1" for _, flag in SECRET_FLAGS if os.environ.get(flag) == "1"}
# A deploy without ssi-db serves an API with no database (it tries 127.0.0.1); `modal run ::refresh` needs none
if modal.is_local() and "deploy" in sys.argv and "SSI_WITH_DB" not in with_flags:
    raise SystemExit("modal deploy without SSI_WITH_DB=1: the web app would have no database. Use `make deploy`.")

volume = modal.Volume.from_name("ssi-data", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("duckdb==1.4.5", "fastapi>=0.115", "uvicorn>=0.30", "psycopg[binary,pool]>=3.2", "pydantic>=2.8",
                    "anthropic>=1.0", "langsmith>=0.3", "httpx>=0.27", "python-dotenv>=1.0", "jellyfish>=1.0", "openai>=1.0")
    .env({"SSI_DATA_DIR": VOL_PATH, "PYTHONPATH": "/root", **with_flags})
    .add_local_dir(APP_DIR / "ssi", "/root/ssi", ignore=["**/__pycache__"])
    .add_local_dir(APP_DIR / "scripts", "/root/scripts", ignore=["**/__pycache__"])
    .add_local_dir(APP_DIR / "web" / "dist", "/root/web/dist")
)
app = modal.App("site-safety-intelligence", image=image)

web_secrets = [modal.Secret.from_name(name) for name, flag in SECRET_FLAGS if flag in with_flags]


# No ephemeral_disk: the default 512 GiB is the smallest Modal accepts, and the build needs about 15 GB
@app.function(volumes={VOL_PATH: volume}, cpu=8, memory=32768, timeout=2 * 3600,
              # daily, after DOL's ~11:00 UTC refresh; off unless deployed with SSI_NIGHTLY=1 (else `make refresh`)
              schedule=modal.Cron("0 13 * * *") if os.environ.get("SSI_NIGHTLY") == "1" else None)
def refresh(download: bool = True) -> dict:
    """Download the latest OSHA files and rebuild the warehouse on the container's local disk, then copy only
    the finished warehouse to the Volume. CURRENT is swapped only if every error-level check passed."""
    import shutil

    from ssi.pipeline import build, download as dl
    vol = Path(VOL_PATH)
    work = Path("/tmp/ssi")
    raw = work / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (vol / "raw" / "reference").mkdir(parents=True, exist_ok=True)
    if not (raw / "reference").exists():
        (raw / "reference").symlink_to(vol / "raw" / "reference")  # hand-downloaded ITA/CSLB files persist on the Volume
    if download:
        dl.download_osha(raw)
        dl.download_licences(raw)
    report = build.build(work)
    (vol / "build").mkdir(parents=True, exist_ok=True)
    wh = work / "build" / report["warehouse"]
    shutil.copy(wh, vol / "build" / wh.name)
    shutil.copy(work / "build" / f"build_report-{report['build_id']}.json", vol / "build")
    tmp = vol / "build" / "CURRENT.tmp"
    tmp.write_text(wh.name)
    tmp.replace(vol / "build" / "CURRENT")
    for old in sorted((vol / "build").glob("warehouse-2*.duckdb"))[:-2]:  # keep two builds for rollback
        old.unlink()
    volume.commit()
    return {k: report[k] for k in ("build_id", "ok", "seconds_total", "warehouse_mb", "data_as_of")}


@app.function(volumes={VOL_PATH: volume}, secrets=web_secrets, cpu=2, memory=8192,
              min_containers=int(os.environ.get("SSI_MIN_CONTAINERS", "0")), scaledown_window=900)
@modal.concurrent(max_inputs=16)
@modal.asgi_app()
def web():
    """FastAPI + SPA. The warehouse is copied from the Volume to local disk on cold start: DuckDB reads
    a local file much faster than a network volume."""
    import shutil

    from ssi import config
    src = config.current_warehouse()
    if src:
        local = Path("/tmp") / src.name
        if not local.exists():
            shutil.copy(src, local)
        from ssi.store import warehouse
        warehouse.open_warehouse(local)
    from ssi.api.app import app as fastapi_app
    return fastapi_app


@app.function(volumes={VOL_PATH: volume}, secrets=web_secrets, cpu=2, memory=8192, timeout=1800)
def seed_demo() -> None:
    """Create the demo project against the deployed warehouse and Postgres."""
    import shutil

    from ssi import config
    from ssi.store import warehouse
    src = config.current_warehouse()
    local = Path("/tmp") / src.name
    if not local.exists():
        shutil.copy(src, local)
    warehouse.open_warehouse(local)
    from scripts import seed_demo as s
    s.main()
