"""Modal deployment: the nightly data build and the web app (API + SPA) share one Volume.

    uv run modal run modal_app.py::refresh      # download + build on Modal (first time: ~10 min)
    uv run modal deploy modal_app.py            # deploy the web app and the nightly schedule

Secrets (created by you, never committed):
    modal secret create ssi-db DATABASE_URL=postgresql://...      (Postgres for the app layer)
    modal secret create ssi-anthropic ANTHROPIC_API_KEY=...       (optional: AI matcher + foreman)
    modal secret create ssi-langsmith LANGSMITH_API_KEY=... LANGSMITH_PROJECT=site-safety-intelligence LANGSMITH_TRACING=true
    modal secret create ssi-auth BASIC_AUTH_USER=... BASIC_AUTH_PASS=...
"""
from __future__ import annotations

import os
from pathlib import Path

import modal

APP_DIR = Path(__file__).parent
VOL_PATH = "/vol"

volume = modal.Volume.from_name("ssi-data", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("duckdb==1.4.5", "fastapi>=0.115", "uvicorn>=0.30", "psycopg[binary,pool]>=3.2", "pydantic>=2.8",
                    "anthropic>=1.0", "langsmith>=0.3", "httpx>=0.27", "python-dotenv>=1.0", "jellyfish>=1.0", "openai>=1.0")
    .env({"SSI_DATA_DIR": VOL_PATH, "PYTHONPATH": "/root"})
    .add_local_dir(APP_DIR / "ssi", "/root/ssi", ignore=["**/__pycache__"])
    .add_local_dir(APP_DIR / "scripts", "/root/scripts", ignore=["**/__pycache__"])
    .add_local_dir(APP_DIR / "web" / "dist", "/root/web/dist")
)
app = modal.App("site-safety-intelligence", image=image)

# Required secrets, plus opt-in ones chosen at deploy time (Modal refuses to deploy if a named secret is missing):
#   SSI_WITH_ANTHROPIC=1  -> ssi-anthropic (Claude for the matcher + foreman)
#   SSI_WITH_GLM=1        -> ssi-glm (SSI_LLM_PROVIDER=openai_compat, SSI_LLM_BASE_URL, SSI_LLM_MODEL,
#                                     SSI_LLM_MODAL_KEY, SSI_LLM_MODAL_SECRET for a GLM endpoint on Modal)
#   SSI_WITH_LANGSMITH=1  -> ssi-langsmith (tracing)
secrets = [modal.Secret.from_name(n) for n in ("ssi-db", "ssi-auth")]
llm_secrets = [modal.Secret.from_name(name) for name, flag in
               (("ssi-anthropic", "SSI_WITH_ANTHROPIC"), ("ssi-glm", "SSI_WITH_GLM"), ("ssi-langsmith", "SSI_WITH_LANGSMITH"))
               if os.environ.get(flag) == "1"]


@app.function(volumes={VOL_PATH: volume}, cpu=8, memory=32768, timeout=2 * 3600,
              schedule=modal.Cron("0 13 * * *"))  # daily, after DOL's ~11:00 UTC refresh
def refresh(download: bool = True) -> dict:
    """Download the latest OSHA files and rebuild the warehouse. The live warehouse is only replaced
    (CURRENT pointer) if every error-level check passes."""
    from ssi import config
    from ssi.pipeline import build, download as dl
    raw = Path(VOL_PATH) / "raw"
    if download:
        dl.download_osha(raw)
        dl.download_licences(raw)
    volume.commit()
    report = build.build(Path(VOL_PATH))
    # keep the two newest warehouses for rollback
    whs = sorted((Path(VOL_PATH) / "build").glob("warehouse-2*.duckdb"))
    for old in whs[:-2]:
        old.unlink()
    volume.commit()
    return {k: report[k] for k in ("build_id", "ok", "seconds_total", "warehouse_mb", "data_as_of")}


@app.function(volumes={VOL_PATH: volume}, secrets=secrets + llm_secrets, cpu=2, memory=8192,
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


@app.function(volumes={VOL_PATH: volume}, secrets=secrets, cpu=2, memory=8192, timeout=1800)
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
