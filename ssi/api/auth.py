"""Accounts and sessions: invite-only email + password, a random token in an HttpOnly cookie, its hash in Postgres.

Accounts are made with scripts/add_user.py. The middleware in app.py calls `session_user` on every /api request
except PUBLIC_PATHS; routes that need to know who is asking take `user = Depends(current_user)`.
"""
from __future__ import annotations

import functools
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ssi.api import schemas as S
from ssi.store import pg

COOKIE = "ssi_session"
SESSION_DAYS = 30
# The SPA sends this on every request. A cross-site form can't set a custom header, so requiring it on writes
# stops another site from making a signed-in browser change data (SameSite=Lax already covers most of this).
CLIENT_HEADER = "x-ssi-client"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# scrypt at OWASP's minimum (N=2^17, r=8, p=1: 128 MiB, about 0.3 s). The parameters are stored in each hash,
# so raising them later only affects new passwords.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**17, 8, 1
_MAXMEM = 256 * 1024 * 1024

# Failed sign-ins per email, in memory (so per container): enough to stop password guessing against one account.
MAX_FAILURES, FAILURE_WINDOW_S = 10, 15 * 60
_failures: dict[str, deque[float]] = defaultdict(deque)


# --- passwords -------------------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=_MAXMEM, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        want = bytes.fromhex(dk)
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=_MAXMEM, dklen=len(want))
    except ValueError:
        return False
    return hmac.compare_digest(got, want)


@functools.cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_hex(16))


# --- sign-in ---------------------------------------------------------------------------------------
def _too_many_failures(key: str) -> bool:
    q = _failures[key]
    cutoff = time.monotonic() - FAILURE_WINDOW_S
    while q and q[0] < cutoff:
        q.popleft()
    if not q:
        del _failures[key]
        return False
    return len(q) >= MAX_FAILURES


def authenticate(email: str, password: str) -> dict:
    key = email.strip().lower()
    if _too_many_failures(key):
        raise HTTPException(429, "Too many failed sign-ins for this email. Wait 15 minutes and try again.")
    with pg.conn() as c:
        user = c.execute("SELECT * FROM app.app_user WHERE lower(email) = %s", [key]).fetchone()
    # an unknown email costs the same hash as a wrong password, so timing doesn't reveal which emails exist
    ok = verify_password(password, user["password_hash"] if user else _dummy_hash())
    if not (ok and user and user["disabled_at"] is None):
        _failures[key].append(time.monotonic())
        raise HTTPException(401, "That email and password don't match an account.")
    _failures.pop(key, None)
    return user


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def create_session(user_id) -> str:
    token = secrets.token_urlsafe(32)
    with pg.conn() as c:
        c.execute("INSERT INTO app.user_session (token_hash, user_id, expires_at) VALUES (%s, %s, now() + %s)",
                  [_token_hash(token), user_id, timedelta(days=SESSION_DAYS)])
        c.execute("UPDATE app.app_user SET last_login_at = now() WHERE user_id = %s", [user_id])
        c.execute("DELETE FROM app.user_session WHERE expires_at < now()")
    return token


def session_user(token: str | None) -> tuple[dict | None, bool]:
    """The signed-in user for a cookie value, and whether the session was just extended (re-send the cookie).
    Sessions slide: one used within its last 29 days gets a fresh 30, written at most once a day."""
    if not token:
        return None, False
    h = _token_hash(token)
    with pg.conn() as c:
        row = c.execute("""SELECT u.user_id, u.email, u.name, s.expires_at
                           FROM app.user_session s JOIN app.app_user u USING (user_id)
                           WHERE s.token_hash = %s AND s.expires_at > now() AND u.disabled_at IS NULL""",
                        [h]).fetchone()
        if not row:
            return None, False
        refresh = row["expires_at"] - datetime.now(timezone.utc) < timedelta(days=SESSION_DAYS - 1)
        if refresh:
            c.execute("UPDATE app.user_session SET expires_at = now() + %s WHERE token_hash = %s",
                      [timedelta(days=SESSION_DAYS), h])
    return row, refresh


def end_session(token: str | None) -> None:
    if token:
        with pg.conn() as c:
            c.execute("DELETE FROM app.user_session WHERE token_hash = %s", [_token_hash(token)])


def end_all_sessions(c, user_id) -> None:
    c.execute("DELETE FROM app.user_session WHERE user_id = %s", [user_id])


def set_cookie(response: Response, token: str, request: Request) -> None:
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, path="/", httponly=True, samesite="lax",
                        secure=request.url.hostname not in LOCAL_HOSTS)


def clear_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax",
                           secure=request.url.hostname not in LOCAL_HOSTS)


def current_user(request: Request) -> dict:
    """Route dependency: the user the middleware signed in (every non-public /api route has one)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(401, "Sign in to continue.")
    return user


def user_model(u: dict) -> S.User:
    return S.User(user_id=str(u["user_id"]), email=u["email"], name=u["name"])


# --- routes ----------------------------------------------------------------------------------------
router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=S.User)
def login(body: S.LoginRequest, request: Request, response: Response):
    user = authenticate(body.email, body.password)
    set_cookie(response, create_session(user["user_id"]), request)
    return user_model(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    end_session(request.cookies.get(COOKIE))
    clear_cookie(response, request)


@router.get("/me", response_model=S.User)
def me(user: dict = Depends(current_user)):
    return user_model(user)
