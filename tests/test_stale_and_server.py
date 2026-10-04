"""A sub is never shown as clean while something could still add a red flag: a decision on a record a rebuild
regrouped (not moved yet), or a red-flagged record the adjudicator hasn't turned into a question. Adding subs writes
all or nothing, and the server resolves new subs itself. Runs on the live warehouse and a local Postgres."""
import hashlib
import threading
import uuid

import pytest
from conftest import local_db
from pydantic import ValidationError

from ssi.api import schemas as S
from ssi.queries import core as Q
from ssi.store import pg, warehouse

pytestmark = local_db


@pytest.fixture
def project():
    warehouse.open_warehouse()
    pg.ensure_schema()
    with pg.conn() as c:
        p = c.execute("INSERT INTO app.project (name, state) VALUES (%s, 'TN') RETURNING *",
                      [f"pytest stale {uuid.uuid4().hex[:6]}"]).fetchone()
    yield p
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = %s", [p["project_id"]])


def sub_with(project, *rows):
    """A sub with these app.sub_match rows: (key, bucket, needs_adjudication, activity_nrs)."""
    with pg.conn() as c:
        s = c.execute("""INSERT INTO app.project_sub (project_id, entered_name, entered_state) VALUES (%s, 'Pytest Co', 'TN')
                         RETURNING *""", [project["project_id"]]).fetchone()
        for k, bucket, needs, nrs in rows:
            c.execute("""INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale,
                                                    needs_adjudication, decided_by, activity_nrs)
                         VALUES (%s, %s, %s, 'rule', 'U', 'test', %s, 'rules', %s)""", [s["sub_id"], k, bucket, needs, nrs])
    return s


def a_fatality():
    """A record with a cited fatality, and its inspections."""
    k = warehouse.one("SELECT establishment_key FROM mart.red_flag WHERE kind = 'fatality_cited' "
                      "ORDER BY establishment_key LIMIT 1")["establishment_key"]
    nrs = [r["activity_nr"] for r in warehouse.rows(
        "SELECT activity_nr FROM entity.establishment_member WHERE establishment_key = ?", [k])]
    return k, nrs


def test_a_decision_on_a_record_this_build_regrouped_is_review_never_no_record(project):
    # the GC matched a record before a rebuild gave its inspections (here: a cited fatality's) another key; until the
    # decision moves, nothing is counted, and the sub says so instead of reading "No OSHA record"
    _, nrs = a_fatality()
    gone = hashlib.md5(b"a key from an earlier build").hexdigest()
    s = sub_with(project, (gone, "matched", False, nrs))
    d = Q.compute(s, project)
    assert d["stale"] == [gone] and d["keys"] == [] and d["verdict"] == "review"
    assert [r.code for r in d["reasons"] if r.code == "R_stale"] == ["R_stale"]
    assert "aren't in this data update" in Q.coverage(d).sentence and "No matching" not in Q.coverage(d).sentence


def test_a_red_flagged_record_waiting_for_the_adjudicator_makes_it_review(project):
    k, nrs = a_fatality()
    d = Q.compute(sub_with(project, (k, "possible", True, nrs)), project)
    assert d["verdict"] == "review" and d["facts"].unresolved_red_flags == 1
    assert Q.card(sub_with(project, (k, "possible", True, nrs)), project).match_status == "needs_adjudication"
    # once the adjudicator has seen it (a question now, or decided), it's the question's to say
    assert Q.compute(sub_with(project, (k, "possible", False, nrs)), project)["facts"].unresolved_red_flags == 0


def test_adding_subs_writes_all_or_nothing(project, monkeypatch):
    from ssi.api import app as A
    real, calls = A.match_and_persist, []

    def flaky(sub, state, c=None):
        calls.append(sub["entered_name"])
        if len(calls) == 2:
            raise RuntimeError("the database went away")
        return real(sub, state, c)
    monkeypatch.setattr(A, "match_and_persist", flaky)
    body = S.SubsCreate(rows=[S.SubInput(name="Brasfield & Gorrie", state="AL"), S.SubInput(name="Barnhart Crane")])
    with pytest.raises(RuntimeError):
        A.add_subs(str(project["project_id"]), body)
    with pg.conn() as c:  # neither sub is left behind without its matches (it would read "No OSHA record")
        assert c.execute("SELECT count(*) AS n FROM app.project_sub WHERE project_id = %s",
                         [project["project_id"]]).fetchone()["n"] == 0
    monkeypatch.setattr(A, "match_and_persist", real)
    assert [c.entered_name for c in A.add_subs(str(project["project_id"]), body)] == ["Brasfield & Gorrie", "Barnhart Crane"]


def test_a_batch_is_capped_on_the_server_too():
    with pytest.raises(ValidationError):
        S.SubsCreate(rows=[S.SubInput(name=f"Co {i}") for i in range(51)])


def test_the_server_resolves_new_subs_itself_once_each(project, monkeypatch):
    from ssi import config
    from ssi.api import app as A
    seen, release = [], threading.Event()

    def slow(sub_id, p):
        seen.append(sub_id)
        release.wait(5)
    assert A.resolve_later(project, ["s1", "s2"], run=slow) == 2
    assert A.resolve_later(project, ["s1"], run=slow) == 0  # already queued
    release.set()
    A._resolver.submit(lambda: None).result(5)
    for _ in range(50):
        if not A._queued:
            break
        threading.Event().wait(0.05)
    assert sorted(seen) == ["s1", "s2"] and not A._queued
    # opening a project queues its subs still waiting for the adjudicator (left when a server stopped part way)
    k, nrs = a_fatality()
    s = sub_with(project, (k, "possible", True, nrs))
    queued = []
    monkeypatch.setattr(config, "RESOLVE_ON_SERVER", True)
    monkeypatch.setattr(A, "resolve", lambda sub_id, p: queued.append(sub_id))
    A.get_project(str(project["project_id"]))
    A._resolver.submit(lambda: None).result(5)
    for _ in range(50):
        if queued:
            break
        threading.Event().wait(0.05)
    assert queued == [str(s["sub_id"])]
