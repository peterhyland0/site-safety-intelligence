"""A sub is never shown as clean while a decision on a record a rebuild regrouped hasn't moved onto the new build.
Runs on the live warehouse and a local Postgres."""
import hashlib
import uuid

import pytest
from conftest import local_db

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
