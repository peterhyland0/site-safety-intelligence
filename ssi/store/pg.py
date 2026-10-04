"""Postgres access for the app layer (projects, subs, match decisions, logs)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ssi import config

_pool: ConnectionPool | None = None
SCHEMA_SQL = (Path(__file__).parent / "app_schema.sql").read_text()


# Options some hosts put in copy-paste connection strings for Prisma; libpq rejects them.
_ORM_ONLY_PARAMS = {"pgbouncer", "connection_limit", "pool_timeout", "schema"}


def dsn(url: str) -> str:
    """The connection string without ORM-only query options (e.g. Supabase's '?pgbouncer=true')."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in _ORM_ONLY_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        # prepare_threshold=None: safe behind transaction poolers (Supabase/pgbouncer)
        _pool = ConnectionPool(dsn(config.DATABASE_URL), min_size=1, max_size=8, open=True,
                               kwargs={"row_factory": dict_row, "prepare_threshold": None})
    return _pool


@contextmanager
def conn(existing=None):
    """A pooled connection, one transaction (committed on exit, rolled back on an error); or `existing`, so a step can
    run inside its caller's transaction."""
    if existing is not None:
        yield existing
        return
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
