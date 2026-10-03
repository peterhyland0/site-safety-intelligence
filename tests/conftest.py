"""Fixtures for tests that sign in through the API. They write to the app database, so the tests that use them
carry `local_db` and run only against a local Postgres."""
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

import pytest

from ssi import config

local_db = pytest.mark.skipif(urlsplit(config.DATABASE_URL).hostname not in ("localhost", "127.0.0.1", "::1"),
                              reason="writes to the app database; runs only against a local Postgres")


@pytest.fixture
def fast_auth(monkeypatch):
    """The auth module with a cheap scrypt cost (the real one takes ~0.3 s a hash) and no failed sign-ins."""
    from ssi.api import auth
    monkeypatch.setattr(auth, "SCRYPT_N", 2**12)
    auth._dummy_hash.cache_clear()
    auth._failures.clear()
    yield auth
    auth._dummy_hash.cache_clear()
    auth._failures.clear()


@pytest.fixture
def make_user(fast_auth):
    """Factory for accounts, deleted (with their sessions and chats) after the test."""
    from ssi.store import pg
    pg.ensure_schema()
    made = []

    def make(password="correct horse battery", name="Pat Lee", disabled=False):
        email = f"pytest-{uuid.uuid4().hex[:10]}@example.com"
        with pg.conn() as c:
            u = c.execute("""INSERT INTO app.app_user (email, name, password_hash, disabled_at)
                             VALUES (%s, %s, %s, %s) RETURNING *""",
                          [email, name, fast_auth.hash_password(password),
                           datetime.now(UTC) if disabled else None]).fetchone()
        made.append(u["user_id"])
        return {**u, "password": password}

    yield make
    with pg.conn() as c:
        c.execute("DELETE FROM app.app_user WHERE user_id = ANY(%s)", [made])


@pytest.fixture
def client():
    """Factory for API clients with their own cookie jars. https, so the Secure session cookie is sent back."""
    from fastapi.testclient import TestClient

    from ssi.api.app import app

    def make(signed_in_as: dict | None = None, client_header: bool = True):
        c = TestClient(app, base_url="https://testserver", headers={"X-SSI-Client": "test"} if client_header else {})
        if signed_in_as:
            r = c.post("/api/auth/login", json={"email": signed_in_as["email"], "password": signed_in_as["password"]})
            assert r.status_code == 200, r.text
        return c

    return make
