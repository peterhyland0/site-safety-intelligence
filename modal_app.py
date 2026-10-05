"""Modal deployment: the data build and the web app (API + SPA) share one Volume.

    make refresh                                # download + build on Modal (first time: ~10 min), then move the
                                                # app's decisions onto the new build (needs ssi-db)
    make deploy                                 # deploy the web app with its secrets and one container kept warm
                                                # (SSI_MIN_CONTAINERS=0: none); the nightly build is off
    SSI_NIGHTLY=1 make deploy                   # ... and rebuild the data daily at 13:00 UTC
    make follow                                 # move decisions again, for subs a refresh couldn't

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
    .env({"SSI_DATA_DIR": VOL_PATH, "PYTHONPATH": "/root", **with_flags,
          # `SSI_ALLOW_SHRINK=1 make refresh`: a build may have fewer rows than the live one (a deliberate scope cut)
          **({"SSI_ALLOW_SHRINK": "1"} if os.environ.get("SSI_ALLOW_SHRINK") == "1" else {})})
    .add_local_dir(APP_DIR / "ssi", "/root/ssi", ignore=["**/__pycache__"])
    .add_local_dir(APP_DIR / "scripts", "/root/scripts", ignore=["**/__pycache__"])
    .add_local_dir(APP_DIR / "web" / "dist", "/root/web/dist")
)
app = modal.App("site-safety-intelligence", image=image)

web_secrets = [modal.Secret.from_name(name) for name, flag in SECRET_FLAGS if flag in with_flags]
# Beside the app's Postgres (Supabase, AWS us-east-1 in Virginia): a project page makes dozens of round trips to it, one
# after another, and from an unpinned container each took ~130 ms. Billed at 1.75x; the broad "us" (1.15x) can land in Oregon.
REGION = "us-east"


# No ephemeral_disk: the default 512 GiB is the smallest Modal accepts, and the build needs about 15 GB
@app.function(volumes={VOL_PATH: volume}, secrets=web_secrets, cpu=8, memory=32768, timeout=2 * 3600, region=REGION,
              # daily, after DOL's ~11:00 UTC refresh; off unless deployed with SSI_NIGHTLY=1 (else `make refresh`)
              schedule=modal.Cron("0 13 * * *") if os.environ.get("SSI_NIGHTLY") == "1" else None)
def refresh(download: bool = True) -> dict:
    """Download the latest OSHA files and rebuild the warehouse on the container's local disk, then copy only
    the finished warehouse to the Volume. CURRENT is swapped only if every error-level check passed. Then the app's
    decisions follow their records onto the new build (remap.follow_all; needs ssi-db), and the web containers switch
    to it within a minute (warehouse.follow)."""
    import shutil

    from ssi.matching import remap
    from ssi.pipeline import build
    from ssi.pipeline import download as dl
    from ssi.store import warehouse
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
    report = build.build(work, live_dir=vol / "build")  # compared with the live build on the Volume
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
    out = {k: report[k] for k in ("build_id", "ok", "seconds_total", "warehouse_mb", "data_as_of")}
    if not os.environ.get("DATABASE_URL"):  # no ssi-db: `modal run ::refresh` before the app's database exists
        print("No DATABASE_URL (deploy with SSI_WITH_DB=1): the app's decisions weren't moved onto this build")
        return {**out, "decisions": None}
    warehouse.open_warehouse(wh)  # the new build, from this container's disk
    out["decisions"] = remap.follow_all(vol / "build")  # earlier builds on the Volume, for decisions saved before activity_nrs
    if out["decisions"]["busy"] or out["decisions"]["failed"]:
        print(f"Not moved (Review in the app until `modal run modal_app.py::follow`): {out['decisions']}")
    return out


def latest_local() -> Path | None:
    """The live build, copied to this container's disk once (DuckDB reads a local file much faster than a network
    volume). The Volume is reloaded first, so a running container sees a refresh that finished after it started."""
    import shutil

    from ssi import config
    from ssi.store import warehouse
    try:
        volume.reload()
    except Exception as e:  # noqa: BLE001 - e.g. a file open on the Volume: look again next time
        print(f"volume reload failed: {e}")
    src = config.current_warehouse()
    if src is None:
        return None
    local = Path("/tmp") / src.name
    if not local.exists():
        part = local.with_suffix(".part")
        shutil.copy(src, part)
        part.replace(local)  # a half-copied file is never opened
        for old in Path("/tmp").glob("warehouse-*.duckdb"):  # an earlier copy still open finishes its queries
            if old not in (local, warehouse._path):
                old.unlink(missing_ok=True)
    return local


@app.function(volumes={VOL_PATH: volume}, secrets=web_secrets, cpu=2, memory=8192, region=REGION,
              min_containers=int(os.environ.get("SSI_MIN_CONTAINERS", "0")), scaledown_window=900)
@modal.concurrent(max_inputs=16)
@modal.asgi_app()
def web():
    """FastAPI + SPA. The warehouse is copied from the Volume to local disk on cold start, and again when a refresh
    makes a new build live (warehouse.follow)."""
    from ssi.store import warehouse
    local = latest_local()
    if local:
        warehouse.open_warehouse(local)
    warehouse.follow(latest_local)
    from ssi.api.app import app as fastapi_app
    return fastapi_app


@app.function(volumes={VOL_PATH: volume}, secrets=web_secrets, cpu=2, memory=8192, timeout=3600, region=REGION)
def follow() -> dict:
    """Move the app's decisions onto the live build again: for subs a refresh couldn't move (busy or failed)."""
    from ssi.matching import remap
    from ssi.store import warehouse
    warehouse.open_warehouse(latest_local())
    return remap.follow_all(Path(VOL_PATH) / "build")


@app.function(volumes={VOL_PATH: volume}, secrets=web_secrets, cpu=2, memory=8192, timeout=1800, region=REGION)
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
