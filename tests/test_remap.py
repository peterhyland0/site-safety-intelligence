"""Decisions follow their records' inspections when a cleaning-rule change gives records new keys (ssi/matching/remap.py,
run by scripts/rematch.py). Two mini warehouses are built by the pipeline's own SQL from the same OSHA records and
differ by one cleaning rule: in A, n9 leaves Iowa's L.C. on a name, so ADELPHI CONSTRUCTION, L.C. is a record of its
own; in B (the repo's rules) it joins ADELPHI CONSTRUCTION LLC as one record. A -> B merges two keys into one,
B -> A splits one in two. Writes to the app database, so it runs only against a local Postgres."""
import json
import uuid

import duckdb
import pytest
from conftest import local_db

import tests.mini_warehouse as MW
from scripts import rematch
from ssi import cleaning
from ssi.matching import adjudicate as ADJ
from ssi.matching import remap, run
from ssi.store import pg, warehouse
from tests.mini_warehouse import Rec

pytestmark = local_db

RECS = [
    Rec("ADELPHI CONSTRUCTION LLC", "1 Grand Ave", "Des Moines", "IA", "50309", n=3),
    Rec("ADELPHI CONSTRUCTION, L.C.", "1 Grand Ave", "Des Moines", "IA", "50309", n=2),
    Rec("BRASFIELD & GORRIE, LLC", "3021 7th Ave South", "Birmingham", "AL", "35233", n=2),
]
GONE = Rec("KESTREL ROOFING", "8 Court Ave", "Des Moines", "IA", "50309")  # in A only: left the data by B


@pytest.fixture(scope="module")
def builds(tmp_path_factory):
    d = tmp_path_factory.mktemp("builds")
    without_lc = cleaning.MACROS_SQL.replace("|LLC|LCC|LC|", "|LLC|LCC|")
    assert without_lc.count("|LLC|LCC|") == 2  # both of n9's lists
    real = MW.install_macros
    MW.install_macros = lambda con, temp=False: con.execute(without_lc)
    try:
        MW.build(d / "warehouse-A.duckdb", RECS + [GONE])  # GONE last: the other records keep their activity numbers
    finally:
        MW.install_macros = real
    MW.build(d / "warehouse-B.duckdb", RECS)
    for b in "AB":
        with duckdb.connect(str(d / f"warehouse-{b}.duckdb")) as con:
            con.execute("UPDATE mart.build_info SET build_id = ?", [b])
    saved = warehouse._con, warehouse._path, warehouse._meta
    warehouse._con = None
    yield d
    if warehouse._con is not None:
        warehouse._con.close()
    warehouse._con, warehouse._path, warehouse._meta = saved


def use(builds, b):
    """Serve build A or B (closing the other: DuckDB opens a file once per process)."""
    if warehouse._con is not None:
        warehouse._con.close()
        warehouse._con = None
    warehouse.open_warehouse(builds / f"warehouse-{b}.duckdb")


def key(clean):
    return warehouse.one("SELECT establishment_key FROM entity.establishment WHERE clean_name = ?", [clean])["establishment_key"]


@pytest.fixture
def new_sub():
    pg.ensure_schema()
    made = []

    def make(name, city="Des Moines", state="IA"):
        with pg.conn() as c:
            p = c.execute("INSERT INTO app.project (name, state) VALUES (%s, %s) RETURNING *",
                          [f"pytest remap {uuid.uuid4().hex[:6]}", state]).fetchone()
            made.append(p["project_id"])
            return c.execute("""INSERT INTO app.project_sub (project_id, entered_name, entered_city, entered_state)
                                VALUES (%s, %s, %s, %s) RETURNING *""", [p["project_id"], name, city, state]).fetchone()

    yield make
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = ANY(%s)", [made])


def fresh(sub):
    with pg.conn() as c:
        return c.execute("SELECT * FROM app.project_sub WHERE sub_id = %s", [sub["sub_id"]]).fetchone()


def rows(sub):
    with pg.conn() as c:
        return {r["establishment_key"]: r for r in c.execute(
            "SELECT * FROM app.sub_match WHERE sub_id = %s AND establishment_key <> '__note__'", [sub["sub_id"]])}


def open_questions(sub):
    with pg.conn() as c:
        return c.execute("SELECT * FROM app.match_question WHERE sub_id = %s AND answer IS NULL ORDER BY created_at",
                         [sub["sub_id"]]).fetchall()


def set_ai(sub, k, bucket):
    with pg.conn() as c:
        c.execute("""UPDATE app.sub_match SET method = 'llm', bucket = %s, confidence = 0.9, rationale = 'AI: test',
                            decided_by = 'ai:test' WHERE sub_id = %s AND establishment_key = %s""", [bucket, sub["sub_id"], k])


def rematch_on(builds, sub, b="B"):
    """What scripts/rematch.py --apply does for one sub, on build `b`: remap, then the rules again."""
    use(builds, b)
    p = remap.plan(fresh(sub), builds)
    stats = remap.apply(sub, p)
    run.match_and_persist(fresh(sub), "IA")
    return p, stats


def adelphi_on_a(builds, new_sub):
    use(builds, "A")
    sub = new_sub("Adelphi Construction")
    run.match_and_persist(sub, "IA")
    plain, lc = key("ADELPHI CONSTRUCTION"), key("ADELPHI CONSTRUCTION LC")
    r = rows(sub)
    assert (r[plain]["bucket"], r[plain]["rule_id"], r[lc]["bucket"], r[lc]["rule_id"]) == ("matched", "M1", "matched", "M2")
    assert len(r[plain]["activity_nrs"]) == 3 and len(r[lc]["activity_nrs"]) == 2  # stored with each decision
    return sub, plain, lc


# --- merge (A -> B) -------------------------------------------------------------------------------------------
def test_a_gc_answer_follows_its_record_into_the_merged_one(builds, new_sub):
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    ADJ.override(str(sub["sub_id"]), lc, "matched")  # the GC: the L.C. is my sub too
    with pg.conn() as c:  # and a question about it was still open
        c.execute("INSERT INTO app.match_question (sub_id, establishment_keys, text) VALUES (%s, %s, 'q')",
                  [sub["sub_id"], [lc, plain]])
    use(builds, "B")
    assert key("ADELPHI CONSTRUCTION") == plain  # the LLC's record keeps its key; the L.C.'s is gone
    p, stats = rematch_on(builds, sub)
    assert p["moves"][lc]["targets"] == {plain: 2} and p["moves"][lc]["via"] == "stored" and not p["splits"]
    assert p["targets"][plain]["action"] == "carry" and stats["carried"] == 1
    r = rows(sub)
    assert lc not in r
    assert (r[plain]["bucket"], r[plain]["method"], r[plain]["rationale"]) == ("matched", "gc", "Set by the GC")
    assert len(r[plain]["activity_nrs"]) == 5 and r[plain]["build_id"] == "B"
    assert r[plain]["evidence"]["inspections"] == 5
    assert r[plain]["evidence"]["remapped_from"] == [{"key": lc, "name": "ADELPHI CONSTRUCTION LC", "shared_inspections": 2}]
    assert [q["establishment_keys"] for q in open_questions(sub)] == [[plain]]  # asks about where its records are now
    assert not remap.changes(remap.plan(fresh(sub), builds))  # done: running it again moves nothing


def test_gc_answers_that_disagree_become_a_question(builds, new_sub):
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    ADJ.override(str(sub["sub_id"]), lc, "matched")
    ADJ.override(str(sub["sub_id"]), plain, "excluded")
    p, stats = rematch_on(builds, sub)
    assert p["targets"][plain]["action"] == "ask" and stats["questions"] == 1
    r = rows(sub)
    assert lc not in r and (r[plain]["bucket"], r[plain]["method"]) == ("possible", "remap")  # not counted yet
    (q,) = open_questions(sub)
    assert q["kind"] == "remap" and q["establishment_keys"] == [plain] and q["ai_suggestion"] is None
    assert q["text"] == (
        "After a data update, OSHA records you answered differently are one record: you confirmed 'ADELPHI CONSTRUCTION "
        "LC' (Des Moines, IA) as your sub; you marked 'ADELPHI CONSTRUCTION' (Des Moines, IA) as a different company. "
        "OSHA's records now group them as 'ADELPHI CONSTRUCTION' (1 GRAND AVE, Des Moines, IA, 5 inspections). Is this "
        "record your sub 'Adelphi Construction'?")
    rematch_on(builds, sub)  # the re-match keeps the record waiting, and doesn't ask twice
    assert rows(sub)[plain]["method"] == "remap" and len(open_questions(sub)) == 1
    ADJ.answer_question(str(q["question_id"]), "yes")
    assert (rows(sub)[plain]["bucket"], rows(sub)[plain]["method"]) == ("matched", "gc")


@pytest.mark.parametrize("ai, plain_after", [("matched", ("matched", "llm")), ("excluded", ("matched", "rule"))])
def test_an_ai_answer_carries_over_only_when_the_merged_record_agrees(builds, new_sub, ai, plain_after):
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    set_ai(sub, lc, ai)
    p, stats = rematch_on(builds, sub)
    # agreeing with the rules' match of the LLC's record, the AI's answer carries; disagreeing, the rules decide again
    assert p["targets"][plain]["action"] == ("carry" if ai == "matched" else "release")
    assert stats["released"] == (ai == "excluded")
    r = rows(sub)
    assert lc not in r and (r[plain]["bucket"], r[plain]["method"]) == plain_after


def test_a_record_that_left_the_data_keeps_its_answer(builds, new_sub):
    use(builds, "A")
    sub = new_sub("Kestrel Roofing")
    run.match_and_persist(sub, "IA")
    kestrel = key("KESTREL ROOFING")
    ADJ.override(str(sub["sub_id"]), kestrel, "matched")
    p, _ = rematch_on(builds, sub)
    assert [r["establishment_key"] for r in p["lost"]] == [kestrel] and not remap.changes(p)
    assert (rows(sub)[kestrel]["bucket"], rows(sub)[kestrel]["method"]) == ("matched", "gc")


# --- split (B -> A) -------------------------------------------------------------------------------------------
def test_a_split_record_passes_the_gc_answer_to_the_part_that_left(builds, new_sub):
    use(builds, "B")
    sub = new_sub("Adelphi Construction")
    run.match_and_persist(sub, "IA")
    plain = key("ADELPHI CONSTRUCTION")
    ADJ.override(str(sub["sub_id"]), plain, "excluded")  # the GC: not my sub
    p, stats = rematch_on(builds, sub, "A")
    lc = key("ADELPHI CONSTRUCTION LC")
    assert p["splits"][plain]["targets"] == {lc: 2} and not p["moves"] and stats["split"] == 1
    r = rows(sub)
    assert {k: (r[k]["bucket"], r[k]["method"]) for k in (plain, lc)} == {plain: ("excluded", "gc"), lc: ("excluded", "gc")}
    assert len(r[plain]["activity_nrs"]) == 3 and len(r[lc]["activity_nrs"]) == 2  # stored as this build has them


# --- rows saved before activity_nrs ---------------------------------------------------------------------------
def test_without_stored_inspections_the_old_build_is_read_if_its_kept(builds, new_sub, tmp_path):
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    ADJ.override(str(sub["sub_id"]), lc, "matched")
    with pg.conn() as c:
        c.execute("UPDATE app.sub_match SET activity_nrs = NULL WHERE sub_id = %s", [sub["sub_id"]])
    use(builds, "B")
    gone = remap.plan(fresh(sub), tmp_path)  # a data/build without build A
    assert [r["establishment_key"] for r in gone["unknown"]] == [lc] and not remap.changes(gone)
    p = remap.plan(fresh(sub), builds)
    assert p["moves"][lc]["via"] == "build A" and p["targets"][plain]["action"] == "carry"


# --- the dry run ----------------------------------------------------------------------------------------------
def test_the_dry_run_shows_the_move_and_writes_nothing(builds, new_sub):
    sub, _, lc = adelphi_on_a(builds, new_sub)
    ADJ.override(str(sub["sub_id"]), lc, "matched")
    before = rows(sub)
    use(builds, "B")
    p = remap.plan(fresh(sub), builds)
    assert rematch.remap_lines(p) == [
        ("    'ADELPHI CONSTRUCTION LC' (Des Moines, IA) -> 'ADELPHI CONSTRUCTION' (Des Moines, IA; 2 of 2 inspections): "
         "gc/matched kept")]
    # the GC's answer lands on the LLC's record, so the rules have nothing left to change there
    assert rematch.plan(fresh(sub), "IA", p["after"]) == []
    assert json.dumps(rows(sub), default=str) == json.dumps(before, default=str)
