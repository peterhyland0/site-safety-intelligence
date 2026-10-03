"""Read-only access to the DuckDB warehouse (OSHA facts). One shared database instance; each caller
gets its own cursor, which DuckDB makes safe across threads."""
from __future__ import annotations

import threading
from pathlib import Path

import duckdb

from ssi import config
from ssi.cleaning import install_macros

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None
_path: Path | None = None
_meta: dict = {}


def open_warehouse(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    global _con, _path, _meta
    with _lock:
        path = path or config.current_warehouse()
        if path is None:
            raise RuntimeError(f"No warehouse found (looked for {config.CURRENT_POINTER}). Run the build first.")
        if _con is not None and _path == path:
            return _con
        con = duckdb.connect(str(path), read_only=True, config={"threads": "4"})
        if not con.execute("SELECT count(*) FROM duckdb_functions() WHERE function_name = 'clean_name'").fetchone()[0]:
            install_macros(con, temp=True)  # older warehouse without persisted macros
        _con, _path = con, path
        row = con.execute("SELECT build_id, data_as_of::VARCHAR, accident_detail_through::VARCHAR FROM mart.build_info").fetchone()
        _meta = {"build_id": row[0], "data_as_of": row[1], "accident_detail_through": row[2]}
        return con


def cursor() -> duckdb.DuckDBPyConnection:
    con = _con or open_warehouse()
    cur = con.cursor()
    if not cur.execute("SELECT count(*) FROM duckdb_functions() WHERE function_name = 'clean_name'").fetchone()[0]:
        install_macros(cur, temp=True)  # temp macros are per-connection
    return cur


def meta() -> dict:
    if not _meta:
        open_warehouse()
    return _meta


def rows(sql: str, params: list | tuple = ()) -> list[dict]:
    cur = cursor()
    try:
        res = cur.execute(sql, list(params))
        cols = [d[0].lower() for d in res.description]
        return [dict(zip(cols, r)) for r in res.fetchall()]
    finally:
        cur.close()


def one(sql: str, params: list | tuple = ()) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None
