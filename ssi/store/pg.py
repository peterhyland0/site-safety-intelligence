"""Postgres access for the app layer (projects, subs, match decisions, logs)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ssi import config

_pool: ConnectionPool | None = None
SCHEMA_SQL = (Path(__file__).parent / "app_schema.sql").read_text()


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        # prepare_threshold=None: safe behind transaction poolers (Supabase/pgbouncer)
        _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=8, open=True,
                               kwargs={"row_factory": dict_row, "prepare_threshold": None})
    return _pool


@contextmanager
def conn():
    with pool().connection() as c:
        yield c


def ensure_schema() -> None:
    with conn() as c:
        c.execute(SCHEMA_SQL)


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
