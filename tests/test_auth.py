"""Sign-in and sessions through the real middleware and routes."""
import hashlib

from conftest import local_db

from ssi.store import pg


def test_password_hashes_are_salted_and_verify(fast_auth):
    h = fast_auth.hash_password("correct horse")
    assert h.startswith("scrypt$") and "correct horse" not in h
    assert fast_auth.verify_password("correct horse", h)
    assert not fast_auth.verify_password("correct horsf", h)
    assert fast_auth.hash_password("correct horse") != h
    assert not fast_auth.verify_password("anything", "not-a-hash")


@local_db
def test_api_needs_a_session_except_health_and_sign_in(client, monkeypatch):
    from ssi.api import app as A
    monkeypatch.setattr(A.warehouse, "meta", lambda: {"data_as_of": None, "build_id": None})
    c = client()
    assert c.get("/api/projects").status_code == 401
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/projects", json={"name": "x"}).status_code == 401
    assert c.get("/api/health").status_code == 200
    assert c.post("/api/auth/logout").status_code == 204


@local_db
def test_sign_in_sets_a_private_cookie_and_sign_out_ends_the_session(client, make_user):
    u = make_user()
    c = client()
    r = c.post("/api/auth/login", json={"email": u["email"].upper(), "password": u["password"]})
    assert r.status_code == 200
    assert r.json() == {"user_id": str(u["user_id"]), "email": u["email"], "name": "Pat Lee"}
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "samesite=lax" in cookie.lower()

    token = c.cookies["ssi_session"]
    with pg.conn() as conn:
        stored = [bytes(s["token_hash"]) for s in
                  conn.execute("SELECT token_hash FROM app.user_session WHERE user_id = %s", [u["user_id"]])]
    assert stored == [hashlib.sha256(token.encode()).digest()]  # only the hash is kept
    assert c.get("/api/me").json()["email"] == u["email"]

    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/me").status_code == 401
    with pg.conn() as conn:
        assert not conn.execute("SELECT 1 FROM app.user_session WHERE user_id = %s", [u["user_id"]]).fetchone()


@local_db
def test_wrong_password_unknown_email_and_disabled_account_get_the_same_answer(client, make_user):
    u, off = make_user(), make_user(disabled=True)
    c = client()
    answers = [c.post("/api/auth/login", json={"email": e, "password": p})
               for e, p in ((u["email"], "wrong password!"), ("nobody@example.com", "whatever12"),
                            (off["email"], off["password"]))]
    assert {r.status_code for r in answers} == {401}
    assert len({r.json()["detail"] for r in answers}) == 1
    assert "ssi_session" not in c.cookies


@local_db
def test_repeated_failures_lock_the_email_for_a_while(client, make_user, fast_auth):
    u = make_user()
    c = client()
    for _ in range(fast_auth.MAX_FAILURES):
        assert c.post("/api/auth/login", json={"email": u["email"], "password": "wrong password!"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 429


@local_db
def test_expired_or_disabled_sessions_are_rejected(client, make_user):
    u = make_user()
    c = client(signed_in_as=u)
    with pg.conn() as conn:
        conn.execute("UPDATE app.user_session SET expires_at = now() - interval '1 minute' WHERE user_id = %s",
                     [u["user_id"]])
    assert c.get("/api/me").status_code == 401

    c = client(signed_in_as=u)
    with pg.conn() as conn:
        conn.execute("UPDATE app.app_user SET disabled_at = now() WHERE user_id = %s", [u["user_id"]])
    assert c.get("/api/me").status_code == 401


@local_db
def test_a_session_in_use_is_extended_and_its_cookie_resent(client, make_user):
    u = make_user()
    c = client(signed_in_as=u)
    assert "set-cookie" not in c.get("/api/me").headers  # fresh: nothing to extend
    with pg.conn() as conn:
        conn.execute("UPDATE app.user_session SET expires_at = now() + interval '2 days' WHERE user_id = %s",
                     [u["user_id"]])
    r = c.get("/api/me")
    assert r.status_code == 200 and "ssi_session=" in r.headers["set-cookie"]
    with pg.conn() as conn:
        left = conn.execute("SELECT expires_at - now() AS left FROM app.user_session WHERE user_id = %s",
                            [u["user_id"]]).fetchone()["left"]
    assert left.days >= 29


@local_db
def test_writes_need_the_apps_client_header(client, make_user):
    u = make_user()
    bare = client(client_header=False)
    assert bare.post("/api/auth/login", json={"email": u["email"], "password": u["password"]}).status_code == 403
    c = client(signed_in_as=u)
    del c.headers["X-SSI-Client"]
    assert c.get("/api/me").status_code == 200  # reads don't need it
    assert c.post("/api/projects", json={"name": "x"}).status_code == 403
