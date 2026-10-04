"""Read-only access to the DuckDB warehouse (OSHA facts). One shared database instance; each caller
gets its own cursor, which DuckDB makes safe across threads. A running app switches to a new build when one goes
live (follow), so every container serves the build the app's decisions were moved onto."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

import duckdb

from ssi import config
from ssi.cleaning import install_macros

log = logging.getLogger(__name__)
FOLLOW_SECONDS = 60  # how often a running app looks for a new build

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None
_path: Path | None = None
_meta: dict = {}
_follower: threading.Thread | None = None


def open_warehouse(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """The warehouse at `path`, switching to it if another is open (queries already running finish on the old one).
    With no path: the one already open, or else the current build (CURRENT)."""
    global _con, _path, _meta
    with _lock:
        if path is None and _con is not None:
            return _con  # a copy opened from local disk (modal_app.web) isn't swapped back for the Volume's file
        path = path or config.current_warehouse()
        if path is None:
            raise RuntimeError(f"No warehouse found (looked for {config.CURRENT_POINTER}). Run the build first.")
        if _con is not None and _path == path:
            return _con
        con = duckdb.connect(str(path), read_only=True, config={"threads": "8"})
        if not con.execute("SELECT count(*) FROM duckdb_functions() WHERE function_name = 'clean_name'").fetchone()[0]:
            install_macros(con, temp=True)  # older warehouse without persisted macros
        row = con.execute("SELECT * FROM mart.build_info").fetchone()
        cols = [d[0] for d in con.description]
        info = dict(zip(cols, row))
        _con, _path = con, path
        _meta = {"build_id": info["build_id"], "data_as_of": str(info["data_as_of"]),
                 "accident_detail_through": str(info["accident_detail_through"]),
                 "history_since": str(info["history_since"]) if info.get("history_since") else None}
        return con


def follow(latest: Callable[[], Path | None] | None = None, every: float = FOLLOW_SECONDS) -> None:
    """Switch to a new build when one goes live: every `every` seconds, `latest()` (default: the build CURRENT names)
    gives the path to serve, and a new one is opened. One follower a process; errors are logged, never raised. Without
    it a running app served its first build until it restarted, while a rebuild had moved the decisions to new keys."""
    global _follower
    latest = latest or config.current_warehouse

    def loop() -> None:
        while True:
            time.sleep(every)
            try:
                path = latest()
                if path is not None and path != _path:
                    open_warehouse(path)
                    log.info("serving warehouse %s", path.name)
            except Exception:  # keep serving the build that's open
                log.exception("couldn't switch to the new warehouse build")

    with _lock:
        if _follower is None:
            _follower = threading.Thread(target=loop, name="warehouse-follow", daemon=True)
            _follower.start()


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
