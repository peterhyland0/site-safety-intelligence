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
from ssi.matching.rules import Query
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


def questions(sub):
    with pg.conn() as c:
        return c.execute("SELECT * FROM app.match_question WHERE sub_id = %s ORDER BY created_at",
                         [sub["sub_id"]]).fetchall()


def ask_about(sub, k):
    """A red-flag question about `k` as rules-only adjudication leaves it: the rule's row, possible, waiting."""
    with pg.conn() as c:
        c.execute("""UPDATE app.sub_match SET bucket = 'possible', needs_adjudication = false
                     WHERE sub_id = %s AND establishment_key = %s""", [sub["sub_id"], k])
        c.execute("INSERT INTO app.match_question (sub_id, establishment_keys, text) VALUES (%s, %s, 'q')",
                  [sub["sub_id"], [k]])


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
    # the question would now ask about a record the GC matched (it used to stay open, about a counted record): the
    # GC's decision settles it
    assert open_questions(sub) == []
    assert [(q["establishment_keys"], q["answer"]) for q in questions(sub)] == [([plain], "yes")]
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


def test_a_question_moved_onto_a_record_the_rules_matched_keeps_it_waiting(builds, new_sub):
    # the L.C.'s record waits for the GC's answer (red flags, no AI answer); merged into the LLC's record, which the
    # rules match, the question asks about the merged record, and the rules' match waits for the answer too
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    ask_about(sub, lc)
    use(builds, "B")
    p = remap.plan(fresh(sub), builds)
    assert p["targets"][plain]["action"] == "rules"
    dry = rematch.plan(fresh(sub), "IA", p["after"], {plain})  # the dry run says what the re-match will do
    assert [(ch["key"], ch["old"], ch["new"]) for ch in dry] == [(plain, "matched/M1", "possible/M1")]
    rematch_on(builds, sub)
    r = rows(sub)
    assert lc not in r and (r[plain]["bucket"], r[plain]["method"], r[plain]["needs_adjudication"]) == ("possible", "rule", False)
    assert r[plain]["rationale"].endswith("; waiting for your answer to its question")
    (q,) = open_questions(sub)
    assert q["establishment_keys"] == [plain]
    ADJ.answer_question(str(q["question_id"]), "yes")
    assert (rows(sub)[plain]["bucket"], rows(sub)[plain]["method"]) == ("matched", "gc")


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


# --- a re-match on the same build ----------------------------------------------------------------------------
def test_a_record_in_an_open_question_waits_through_a_re_match(builds, new_sub):
    # The rules match the L.C.'s record (M2), but a question about it is open: a re-match used to replace its row
    # with the rules' match, counting it while the question still asked
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    ask_about(sub, lc)
    assert rematch.plan(fresh(sub), "IA") == []  # the dry run: nothing changes
    rematch_on(builds, sub, "A")
    r = rows(sub)
    assert (r[lc]["bucket"], r[lc]["rule_id"], r[lc]["needs_adjudication"]) == ("possible", "M2", False)
    assert (r[plain]["bucket"], r[plain]["rule_id"]) == ("matched", "M1")  # the rest as before
    # and if the rules no longer find it at all, its row stays, waiting; the others go
    run.persist(str(sub["sub_id"]), {"query": Query(clean="ADELPHI", core="ADELPHI", state="IA", city=None, trade=None,
                                                     tier="distinctive", initials_only=False, sibling=None, aliases=set()),
                                     "decisions": [], "note": None})
    assert {k: r["bucket"] for k, r in rows(sub).items()} == {lc: "possible"}
    assert len(open_questions(sub)) == 1


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


# --- after a build: every sub's decisions follow (remap.follow, from the build and from Modal's refresh) ----------
def project_of(sub):
    with pg.conn() as c:
        return c.execute("SELECT * FROM app.project WHERE project_id = %s", [sub["project_id"]]).fetchone()


def test_a_build_moves_each_subs_decisions_and_runs_the_rules_again(builds, new_sub):
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    ADJ.override(str(sub["sub_id"]), lc, "matched")
    use(builds, "B")
    stats = remap.follow(fresh(sub), "IA", builds)
    assert stats["moved"] == 1 and stats["carried"] == 1
    r = rows(sub)
    assert lc not in r and (r[plain]["bucket"], r[plain]["method"]) == ("matched", "gc")
    assert remap.follow(fresh(sub), "IA", builds)["moved"] == 0  # done: nothing left to move


def test_follow_leaves_a_sub_the_app_is_resolving(builds, new_sub):
    sub, _, lc = adelphi_on_a(builds, new_sub)
    use(builds, "B")
    with ADJ.claim(str(sub["sub_id"])):
        assert remap.follow(fresh(sub), "IA", builds) is None
    assert lc in rows(sub)  # untouched; the next build or `python -m ssi.matching.remap` moves it


def test_a_record_split_by_a_rebuild_is_stale_until_its_decision_moves(builds, new_sub):
    # B -> A: the L.C.'s 2 inspections leave the sub's matched ADELPHI CONSTRUCTION for a record of their own, which
    # the sub has no decision on. They aren't counted, and the sub is Review (core.compute; test_stale_and_server.py),
    # until follow moves the decision
    from ssi.queries import core as Q
    use(builds, "B")
    sub = new_sub("Adelphi Construction")
    run.match_and_persist(sub, "IA")
    plain = key("ADELPHI CONSTRUCTION")
    use(builds, "A")
    assert Q.unmoved(Q.scope(str(sub["sub_id"])))[0] == [plain]
    remap.follow(fresh(sub), "IA", builds)
    stale, present = Q.unmoved(Q.scope(str(sub["sub_id"])))
    assert stale == [] and present == {plain, key("ADELPHI CONSTRUCTION LC")}


def test_a_record_merged_into_a_matched_one_or_gone_from_the_data_isnt_stale(builds, new_sub):
    from ssi.queries import core as Q
    sub, plain, _ = adelphi_on_a(builds, new_sub)  # A -> B: the L.C. merges into the matched ADELPHI CONSTRUCTION
    kestrel = new_sub("Kestrel Roofing")  # ...and KESTREL ROOFING's only record leaves the data
    run.match_and_persist(kestrel, "IA")
    gone = key("KESTREL ROOFING")
    use(builds, "B")
    assert Q.unmoved(Q.scope(str(sub["sub_id"]))) == ([], {plain})  # its inspections are all counted
    assert Q.unmoved(Q.scope(str(kestrel["sub_id"]))) == ([], set())  # nothing in the data window to count
    assert gone in rows(kestrel)


def test_follow_all_moves_every_sub_and_tries_a_busy_one_again(builds, new_sub, monkeypatch):
    sub, plain, lc = adelphi_on_a(builds, new_sub)
    busy, _, busy_lc = adelphi_on_a(builds, new_sub)
    ADJ.override(str(sub["sub_id"]), lc, "matched")
    use(builds, "B")
    real, tries = remap.follow, []

    def follow(s, state, build_dir=None):
        tries.append(s["entered_name"] + str(s["sub_id"]))
        if s["sub_id"] == busy["sub_id"] and tries.count(s["entered_name"] + str(s["sub_id"])) == 1:
            return None  # the app is resolving it; free on the second try
        return real(s, state, build_dir)
    monkeypatch.setattr(remap, "follow", follow)
    out = remap.follow_all(builds, retry_after=0)
    assert out["busy"] == [] and "Adelphi Construction" not in out["failed"]
    assert lc not in rows(sub) and rows(sub)[plain]["method"] == "gc"
    assert busy_lc not in rows(busy)  # moved on the second try
