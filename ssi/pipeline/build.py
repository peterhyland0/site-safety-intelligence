"""Build the warehouse: raw OSHA CSVs -> cleaned layers (ref, osha, entity, ref_ext, mart) in DuckDB.

Intermediate tables live in a scratch database; only final layers are written to the new
warehouse-<build_id>.duckdb, which the API serves read-only. The CURRENT pointer is swapped only after
every 'error' check passes, so a failed build never replaces the live data.

    uv run python -m ssi.pipeline.build                 # full build
    uv run python -m ssi.pipeline.build --dev --from 40 # rerun from step 40 reusing scratch (dev only)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from ssi import config
from ssi.cleaning import NAME_STEPS, install_macros

TEMPLATE_VARS = {
    "GENERIC_MIN_VARIETY": str(config.GENERIC_MIN_VARIETY),
    "DISTINCTIVE_MAX_VARIETY": str(config.DISTINCTIVE_MAX_VARIETY),
    "SHARED_OFFICE_MIN_CORES": str(config.SHARED_OFFICE_MIN_CORES),
    "MIN_RATED": str(config.BENCHMARK_MIN_RATED_INSPECTIONS),
    "HISTORY_YEARS": str(config.HISTORY_YEARS),
}

# Ref tables the SQL depends on, with the columns to stub if the CSV is not there yet
REF_STUBS = {
    "trade": "code VARCHAR, code_type VARCHAR, label VARCHAR, naics4 VARCHAR",
    "standard_hazard_map": "family VARCHAR, match_type VARCHAR, pattern VARCHAR, range_to VARCHAR, hazard_code VARCHAR, note VARCHAR",
    "hazard_category": "hazard_code VARCHAR, label VARCHAR, fatal_four BOOLEAN, sort INTEGER",
    "violation_type": "code VARCHAR, label VARCHAR, severity_rank INTEGER, serious_plus BOOLEAN",
    "inspection_type": "code VARCHAR, label VARCHAR, is_accident BOOLEAN, decode_confirmed BOOLEAN, source VARCHAR",
    "state_plan": "state VARCHAR, plan_scope VARCHAR, plan_name VARCHAR",
    "given_name": "name VARCHAR",
}


def render(sql: str, raw_dir: Path) -> str:
    sql = sql.replace("{{RAW}}", str(raw_dir)).replace("{{REF}}", str(config.REF_DIR))
    sql = sql.replace("{{REFERENCE_RAW}}", str(raw_dir / "reference"))
    for k, v in TEMPLATE_VARS.items():
        sql = sql.replace("{{" + k + "}}", v)
    return sql


def load_refs(con) -> list[str]:
    loaded = []
    for name, cols in REF_STUBS.items():
        path = config.REF_DIR / f"{name}.csv"
        if path.exists():
            con.execute(f"CREATE OR REPLACE TABLE ref_{name} AS SELECT * FROM read_csv('{path}', header = true, all_varchar = true)")
            loaded.append(name)
        else:
            con.execute(f"CREATE OR REPLACE TABLE ref_{name} ({cols})")
        con.execute(f"CREATE OR REPLACE TABLE wh.ref.{name} AS SELECT * FROM ref_{name}")
    for path in sorted(config.REF_DIR.glob("*.csv")):  # any extra ref CSVs
        if path.stem not in REF_STUBS:
            con.execute(f"CREATE OR REPLACE TABLE ref_{path.stem} AS SELECT * FROM read_csv('{path}', header = true, all_varchar = true)")
            con.execute(f"CREATE OR REPLACE TABLE wh.ref.{path.stem} AS SELECT * FROM ref_{path.stem}")
            loaded.append(path.stem)
    return loaded


def ensure_hazard_stub(con) -> bool:
    """If the hazard-map step isn't available yet, every citation maps to 'other' (and the check warns)."""
    exists = con.execute("SELECT count(*) FROM duckdb_tables() WHERE database_name = current_database() "
                         "AND table_name = 'violation_hazard'").fetchone()[0]
    if exists:
        return False
    con.execute("""CREATE OR REPLACE TABLE violation_hazard AS
                   SELECT activity_nr, citation_id, NULL::VARCHAR AS std_family, standard_raw AS standard_cite,
                          NULL::VARCHAR AS section_key, 'other' AS hazard_code FROM stg_violation""")
    return True


def ensure_ref_ext_stubs(con) -> None:
    """Without reference downloads the app still works; enrichment tables are just empty."""
    con.execute("""CREATE TABLE IF NOT EXISTS wh.ref_ext.licence (source VARCHAR, number VARCHAR, entity_id VARCHAR,
                   name VARCHAR, dba VARCHAR, clean_name VARCHAR, dba_clean VARCHAR, address VARCHAR, addr_key VARCHAR,
                   city VARCHAR, state VARCHAR, zip5 VARCHAR, status VARCHAR, expires DATE, specialty VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS wh.ref_ext.ita_establishment_year (establishment_id VARCHAR, year INTEGER,
                   company_name VARCHAR, establishment_name VARCHAR, ein VARCHAR, naics VARCHAR, employees DOUBLE,
                   hours DOUBLE, deaths INTEGER, dafw INTEGER, djtr INTEGER, other_cases INTEGER, trir DOUBLE,
                   dart DOUBLE, dq_flags VARCHAR[])""")
    con.execute("CREATE TABLE IF NOT EXISTS wh.entity.ref_link (establishment_key VARCHAR, source VARCHAR, ref_id VARCHAR, method VARCHAR)")
    con.execute("""CREATE TABLE IF NOT EXISTS wh.mart.ita_benchmark (naics4 VARCHAR, year INTEGER, peer_n BIGINT,
                   trir_pooled DOUBLE, dart_pooled DOUBLE, trir_p50 DOUBLE, trir_p75 DOUBLE, dart_p50 DOUBLE,
                   dart_p75 DOUBLE)""")


def rule_merge_counts(con) -> list[dict]:
    """Distinct construction employer names after each cleaning step (all years and since 2015)."""
    out, expr = [], "estab_name"
    base = ("FROM raw_inspection WHERE (naics_code LIKE '23%' OR left(sic_code, 2) IN ('15','16','17'))")
    raw_all, raw_recent = con.execute(
        f"SELECT count(DISTINCT estab_name), count(DISTINCT estab_name) FILTER (WHERE open_date >= '2015') {base}"
    ).fetchone()
    out.append({"step": "raw", "all_years": raw_all, "since_2015": raw_recent})
    for step in NAME_STEPS:
        expr = f"{step}({expr})"
        a, r = con.execute(
            f"SELECT count(DISTINCT {expr}), count(DISTINCT {expr}) FILTER (WHERE open_date >= '2015') {base}"
        ).fetchone()
        out.append({"step": step, "all_years": a, "since_2015": r})
    return out


def table_counts(con) -> dict:
    rows = con.execute("""SELECT schema_name || '.' || table_name, estimated_size
                          FROM duckdb_tables() WHERE database_name = 'wh' ORDER BY 1""").fetchall()
    return {name: con.execute(f"SELECT count(*) FROM wh.{name}").fetchone()[0] for name, _ in rows}


# Tables compared build-to-build: same raw files + same code must give identical tables (M3 in the review).
CHECKSUM_TABLES = ["osha.inspection", "osha.violation", "osha.accident", "osha.accident_inspection", "osha.injury",
                   "entity.establishment", "entity.core_stats", "mart.establishment_year", "mart.red_flag",
                   "mart.trade_benchmark", "ref_ext.ita_establishment_year", "ref_ext.licence", "entity.ref_link"]


def inputs_fingerprint(raw_dir: Path) -> str:
    """The raw files this build read (path, size, modification time)."""
    h = hashlib.sha256()
    for p in sorted(raw_dir.rglob("*.csv")):
        st = p.stat()
        h.update(f"{p.relative_to(raw_dir)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:16]


def code_fingerprint() -> str:
    """The pipeline code and reference data, plus the settings that change outputs."""
    h = hashlib.sha256()
    files = [*config.SQL_DIR.glob("*.sql"), *config.REF_DIR.glob("*.csv"), *Path(__file__).parent.parent.joinpath("cleaning").glob("*"),
             Path(__file__)]
    for p in sorted(f for f in files if f.is_file()):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    h.update(f"{config.HISTORY_YEARS}|{config.DISTINCTIVE_MAX_VARIETY}|{config.GENERIC_MIN_VARIETY}|"
             f"{config.SHARED_OFFICE_MIN_CORES}|{config.BENCHMARK_MIN_RATED_INSPECTIONS}".encode())
    return h.hexdigest()[:16]


def table_checksums(con) -> dict[str, str]:
    """Row count and an order-independent hash of every row, per table."""
    out = {}
    for t in CHECKSUM_TABLES:
        try:
            n, s = con.execute(f"SELECT count(*), coalesce(sum(hash(x)), 0)::VARCHAR FROM wh.{t} x").fetchone()
        except duckdb.Error:
            continue
        out[t] = f"{n}:{s}"
    return out


def previous_build_info(build_dir: Path) -> dict | None:
    ptr = build_dir / "CURRENT"
    if not ptr.exists() or not (build_dir / ptr.read_text().strip()).exists():
        return None
    try:
        with duckdb.connect(str(build_dir / ptr.read_text().strip()), read_only=True) as c:
            cols = [d[0] for d in c.execute("SELECT * FROM mart.build_info").description]
            return dict(zip(cols, c.execute("SELECT * FROM mart.build_info").fetchone()))
    except duckdb.Error:
        return None


def build(data_dir: Path, dev: bool = False, from_step: str | None = None, keep_scratch: bool = False) -> dict:
    raw_dir = data_dir / "raw"
    build_dir = data_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    build_id = "dev" if dev else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wh_path = build_dir / f"warehouse-{build_id}.duckdb"
    scratch_path = build_dir / f"scratch-{build_id}.duckdb"
    if not from_step:
        for p in (wh_path, scratch_path):
            p.unlink(missing_ok=True)
    tmp_dir = build_dir / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    con = duckdb.connect(str(scratch_path))
    con.execute(f"SET threads = {os.cpu_count() or 4}")
    con.execute(f"SET memory_limit = '{os.environ.get('SSI_MEMORY_LIMIT', '12GB')}'")
    con.execute(f"SET temp_directory = '{tmp_dir}'")
    con.execute("SET enable_progress_bar = false")
    con.execute(f"ATTACH '{wh_path}' AS wh")
    install_macros(con)

    report: dict = {"build_id": build_id, "started_at": datetime.now(timezone.utc).isoformat(), "steps": []}
    t0 = time.time()
    hazard_stubbed = False
    for path in sorted(config.SQL_DIR.glob("*.sql")):
        prefix = path.name.split("_")[0]
        if from_step and prefix < from_step and not prefix.startswith("0"):
            continue
        if prefix == "31" or (prefix >= "32" and not hazard_stubbed and not (config.SQL_DIR / "31_hazard_map.sql").exists()):
            if prefix >= "31":
                report["refs_loaded"] = load_refs(con)
        if prefix == "32":
            hazard_stubbed = ensure_hazard_stub(con)
        if prefix.startswith("6") and not (raw_dir / "reference").exists():
            ensure_ref_ext_stubs(con)
            report["steps"].append({"step": path.name, "skipped": "no data/raw/reference"})
            continue
        t = time.time()
        con.execute(render(path.read_text(), raw_dir))
        report["steps"].append({"step": path.name, "seconds": round(time.time() - t, 1)})
        print(f"  {path.name:34s} {time.time() - t:7.1f}s", flush=True)

    report["hazard_map_stubbed"] = hazard_stubbed
    report["rule_merge_counts"] = rule_merge_counts(con)
    report["scope"] = dict(con.execute(
        "SELECT scope_reason, count(*) FROM wh.osha.inspection GROUP BY 1 ORDER BY 1").fetchall())
    data_as_of = con.execute("SELECT max(open_date)::VARCHAR FROM wh.osha.inspection").fetchone()[0]
    report["data_as_of"] = data_as_of
    checks = con.execute("SELECT name, severity, expected, actual, pass FROM wh.mart.dq_check").fetchall()
    report["checks"] = [dict(zip(["name", "severity", "expected", "actual", "pass"], c)) for c in checks]
    report["tables"] = table_counts(con)
    history_since = con.execute("SELECT since::VARCHAR FROM history_window").fetchone()[0]
    report["history_since"] = history_since
    fingerprints = {"inputs_fingerprint": inputs_fingerprint(raw_dir), "code_fingerprint": code_fingerprint()}
    checksums = table_checksums(con)
    report.update(fingerprints)
    # Same raw files and same code must build identical tables; a difference means a non-deterministic step.
    prev = previous_build_info(build_dir)
    if prev and prev.get("inputs_fingerprint") == fingerprints["inputs_fingerprint"] \
            and prev.get("code_fingerprint") == fingerprints["code_fingerprint"]:
        prev_sums = json.loads(prev.get("table_checksums") or "{}")
        differ = sorted(t for t in checksums if t in prev_sums and prev_sums[t] != checksums[t])
        report["checks"].append({"name": "rebuild_identical_to_previous", "severity": "warn", "expected": 0,
                                 "actual": len(differ), "pass": not differ, "tables": differ})
    con.execute("""CREATE OR REPLACE TABLE wh.mart.build_info AS
                   SELECT ? AS build_id, ?::TIMESTAMP AS built_at, ?::DATE AS data_as_of,
                          ?::DATE AS accident_detail_through, ?::DATE AS history_since,
                          ? AS inputs_fingerprint, ? AS code_fingerprint, ? AS table_checksums""",
                [build_id, datetime.now(timezone.utc).replace(tzinfo=None), data_as_of,
                 con.execute("SELECT max(event_date)::VARCHAR FROM wh.osha.accident").fetchone()[0], history_since,
                 fingerprints["inputs_fingerprint"], fingerprints["code_fingerprint"], json.dumps(checksums)])
    con.execute("DETACH wh")
    con.close()
    # Persist the cleaning macros in the warehouse itself: GC input is then cleaned by exactly the
    # rules that built this data, even if the code's rules change later.
    whc = duckdb.connect(str(wh_path))
    install_macros(whc)
    whc.close()

    failed = [c for c in report["checks"] if c["severity"] == "error" and not c["pass"]]
    report["seconds_total"] = round(time.time() - t0, 1)
    report["warehouse"] = wh_path.name
    report["warehouse_mb"] = round(wh_path.stat().st_size / 1e6, 1)
    report["ok"] = not failed
    (build_dir / f"build_report-{build_id}.json").write_text(json.dumps(report, indent=2, default=str))
    if failed:
        raise SystemExit(f"Build {build_id} failed checks: {[c['name'] for c in failed]}")

    tmp_ptr = build_dir / "CURRENT.tmp"
    tmp_ptr.write_text(wh_path.name)
    tmp_ptr.replace(build_dir / "CURRENT")  # atomic swap
    if not keep_scratch and not dev:
        scratch_path.unlink(missing_ok=True)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    ap.add_argument("--dev", action="store_true", help="fixed build id 'dev'; keeps scratch for --from reruns")
    ap.add_argument("--from", dest="from_step", help="rerun from this step prefix, e.g. 40 (dev only)")
    ap.add_argument("--keep-scratch", action="store_true")
    args = ap.parse_args()
    r = build(args.data_dir, dev=args.dev, from_step=args.from_step, keep_scratch=args.keep_scratch)
    print(json.dumps({k: r[k] for k in ("build_id", "ok", "seconds_total", "warehouse_mb", "data_as_of", "history_since", "scope")}, indent=2))
    for c in r["checks"]:
        print(f"  {'PASS' if c['pass'] else 'FAIL'} {c['severity']:5s} {c['name']}: actual={c['actual']} expected={c['expected']}")


if __name__ == "__main__":
    main()
