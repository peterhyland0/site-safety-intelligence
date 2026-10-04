"""Resolving a sub's uncertain records against Postgres: one request at a time per sub, a record the GC moves while
the AI works keeps the GC's bucket, one failed AI call doesn't lose the rest, and a company profile another request
is building is waited for. The warehouse is stubbed (red flags, the card); the AI and the web search are fakes."""
import json
import threading
import time
import uuid

import pytest
from conftest import local_db

from ssi.api import schemas as S
from ssi.matching import adjudicate as ADJ
from ssi.queries import core as Q
from ssi.scoring.verdict import Facts, evaluate
from ssi.store import pg

pytestmark = local_db


def key() -> str:
    return uuid.uuid4().hex


def evidence(name: str) -> dict:
    return {"rule": "U", "reason": "Could be the same company; needs more evidence", "similarity": 0.9, "name": name,
            "state": "TN", "city": "NASHVILLE", "zip": "37201", "address": "1 MAIN ST",
            "years": ["2019-02-01", "2024-06-01"], "inspections": 3, "naics4": "2382", "related_only": False,
            "query": {"clean": "ACME ELECTRIC", "core": "ACME", "tier": "distinctive"}}


@pytest.fixture
def make_sub():
    """A project with one new sub whose records ({establishment_key: OSHA name}) are uncertain, waiting for the AI."""
    pg.ensure_schema()
    made = []

    def make(records: dict[str, str]):
        with pg.conn() as c:
            p = c.execute("INSERT INTO app.project (name, state) VALUES ('pytest adjudication', 'TN') RETURNING *").fetchone()
            s = c.execute("""INSERT INTO app.project_sub (project_id, entered_name, entered_city, entered_state, profile_status)
                             VALUES (%s, 'Acme Electric', 'Nashville', 'TN', 'pending') RETURNING *""",
                          [p["project_id"]]).fetchone()
            for k, name in records.items():
                c.execute("""INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale,
                                                        evidence, needs_adjudication, decided_by)
                             VALUES (%s, %s, 'possible', 'rule', 'U', 'Could be the same company', %s, true, 'rules')""",
                          [s["sub_id"], k, json.dumps(evidence(name))])
        made.append(p["project_id"])
        return p, s

    yield make
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = ANY(%s)", [made])


@pytest.fixture
def flags(monkeypatch):
    """Red-flag counts by establishment key, in place of the warehouse's mart.red_flag."""
    counts: dict[str, int] = {}
    monkeypatch.setattr(ADJ.C, "red_flag_counts", lambda keys: {k: counts[k] for k in keys if k in counts})
    return counts


def packet(sub, crow):
    return {"lines": [], "sub": sub["entered_name"], "keys": [r["establishment_key"] for r in crow]}


def different(packet):
    return {"decision": "different", "confidence": 0.95, "rationale": "Another company.", "decided_by": "ai:test"}


def rows(sub_id) -> dict[str, dict]:
    with pg.conn() as c:
        return {r["establishment_key"]: r for r in c.execute("SELECT * FROM app.sub_match WHERE sub_id = %s", [sub_id])}


def questions(sub_id) -> list[dict]:
    with pg.conn() as c:
        return c.execute("SELECT * FROM app.match_question WHERE sub_id = %s", [sub_id]).fetchall()


def claimed_at(sub_id):
    with pg.conn() as c:
        return c.execute("SELECT adjudicating_since FROM app.project_sub WHERE sub_id = %s", [sub_id]).fetchone()[
            "adjudicating_since"]


def in_thread(fn) -> tuple[threading.Thread, dict]:
    out: dict = {}

    def run():
        try:
            out["result"] = fn()
        except BaseException as e:  # noqa: BLE001 - re-raised by the test
            out["error"] = e

    t = threading.Thread(target=run)
    t.start()
    return t, out


def test_one_request_at_a_time_resolves_a_sub(make_sub, flags):
    # The sub page opened while the project page's request was still looking the company up used to start a second
    # run: it adjudicated every record before the profile arrived, and asked the GC the same question twice.
    red, plain = key(), key()
    p, s = make_sub({red: "ACME ELECTRIC CO OF TEXAS", plain: "ACME ELECTRICAL"})
    sid = str(s["sub_id"])
    flags[red] = 2
    in_lookup, second_done = threading.Event(), threading.Event()
    lookups, calls = [], []

    def slow_lookup(sub, project):  # the web search takes a while
        lookups.append(sub["sub_id"])
        in_lookup.set()
        assert second_done.wait(10)

    def ai(packet):
        calls.append(packet["keys"])
        return different(packet)

    t, first = in_thread(lambda: ADJ.resolve(sid, p, llm=ai, packet_fn=packet, profile_fn=slow_lookup))
    assert in_lookup.wait(10)
    assert claimed_at(sid) is not None
    assert ADJ.resolve(sid, p, llm=ai, packet_fn=packet, profile_fn=slow_lookup) is None  # the second request
    second_done.set()
    t.join(10)
    if "error" in first:
        raise first["error"]

    assert first["result"]["clusters"] == 2 and first["result"]["questions"] == 1
    assert len(lookups) == 1 and len(calls) == 2  # one lookup, one AI call per group
    assert len(questions(sid)) == 1  # asked once
    assert claimed_at(sid) is None  # released
    assert ADJ.resolve(sid, p, llm=ai, packet_fn=packet)["clusters"] == 0  # free again, and nothing left to do


def test_an_abandoned_claim_is_taken_over_and_its_late_release_leaves_the_new_one(make_sub, monkeypatch):
    _, s = make_sub({})
    sid = str(s["sub_id"])
    with ADJ.claim(sid) as held:
        assert held is not None and str(held["sub_id"]) == sid
        with ADJ.claim(sid) as other:
            assert other is None
    assert claimed_at(sid) is None

    monkeypatch.setattr(ADJ, "CLAIM_STALE_MINUTES", 0)  # every claim counts as abandoned at once
    old, new = ADJ.claim(sid), ADJ.claim(sid)
    assert old.__enter__() is not None
    assert new.__enter__() is not None  # a request that died is taken over
    old.__exit__(None, None, None)  # the old request ends after all...
    assert claimed_at(sid) is not None  # ... and leaves the new request's claim alone
    new.__exit__(None, None, None)
    assert claimed_at(sid) is None


def test_a_record_the_gc_moves_while_the_ai_works_keeps_the_gc_bucket(make_sub, flags):
    moved, red, other = key(), key(), key()
    _, s = make_sub({moved: "ACME ELECTRICAL", red: "ACME ELECTRIC CO OF TEXAS", other: "ACME ELECTRIC SERVICES"})
    sid = str(s["sub_id"])
    flags[red] = 1
    done = []

    def ai(packet):
        if not done:  # the GC moves two records while the first AI call is out
            ADJ.override(sid, moved, "matched")
            ADJ.override(sid, red, "excluded")
            done.append(True)
        return different(packet)

    stats = ADJ.adjudicate(s, llm=ai, packet_fn=packet)
    r = rows(sid)
    assert (r[moved]["bucket"], r[moved]["method"]) == ("matched", "gc")
    assert (r[red]["bucket"], r[red]["method"]) == ("excluded", "gc")
    assert (r[other]["bucket"], r[other]["method"]) == ("excluded", "llm")  # the AI's call where the GC made none
    assert stats["questions"] == 0 and questions(sid) == []  # a red flag the GC has ruled on isn't asked about


def test_a_failed_ai_call_leaves_its_group_possible_and_the_others_are_decided(make_sub, flags, monkeypatch):
    from ssi.llm import adjudicator
    from ssi.llm import client as llm
    red, plain = key(), key()
    _, s = make_sub({red: "ACME ELECTRIC CO OF TEXAS", plain: "ACME ELECTRICAL"})
    sid = str(s["sub_id"])
    flags[red] = 2

    def flaky(packet):  # the red-flagged group goes to the LLM, whose endpoint times out
        if packet["red_flagged"]:
            raise TimeoutError("adjudicator endpoint timed out")
        return {**different(packet), "evidence_ids": ["E1"]}

    monkeypatch.setattr(llm, "available", lambda role="foreman": True)
    monkeypatch.setattr(adjudicator, "use_jev", lambda: False)
    monkeypatch.setattr(adjudicator, "decide_llm", flaky)
    stats = ADJ.adjudicate(s, llm=adjudicator.decide, packet_fn=packet)

    r = rows(sid)
    assert stats["llm_calls"] == 2
    assert (r[plain]["bucket"], r[plain]["method"]) == ("excluded", "llm")  # not lost to the other group's failure
    assert (r[red]["bucket"], r[red]["method"]) == ("possible", "rule")
    [q] = questions(sid)  # the red flag still reaches the GC, without an AI lean
    assert q["establishment_keys"] == [red] and q["ai_suggestion"] is None
    assert not any(x["needs_adjudication"] for x in r.values())


def test_a_profile_another_request_is_building_is_waited_for_not_marked_failed(make_sub, monkeypatch):
    # the same company from another project's sub: its search is used, not paid for again, and this sub's lookup
    # is "done" (it used to be "error", and the records went to the AI without the profile)
    from ssi.llm import profile as P
    p, s = make_sub({key(): "ACME ELECTRICAL"})
    pkey = P.profile_key(P.context(s, "TN", list(rows(str(s["sub_id"])).values())), P.model())
    searched = []
    monkeypatch.setattr(P, "available", lambda: True)
    monkeypatch.setattr(P, "BUILDING_POLL_SECONDS", 0.05)
    monkeypatch.setattr(P, "research", lambda *a, **kw: searched.append(a))
    with pg.conn() as c:
        pid = c.execute("""INSERT INTO app.company_profile (profile_key, query, status, model)
                           VALUES (%s, '{}', 'building', %s) RETURNING profile_id""", [pkey, P.model()]).fetchone()["profile_id"]

    def other_request_finishes():
        time.sleep(0.3)
        with pg.conn() as c:
            c.execute("UPDATE app.company_profile SET status = 'found', profile = %s WHERE profile_id = %s",
                      [json.dumps({"found": True, "name": "Acme Electric", "locations": []}), pid])

    try:
        t, _ = in_thread(other_request_finishes)
        prof = P.for_sub(s, p)
        t.join(10)
        assert prof is not None and prof["profile_id"] == str(pid) and prof["name"] == "Acme Electric"
        assert searched == []
        with pg.conn() as c:
            sub = c.execute("SELECT profile_status, profile_id FROM app.project_sub WHERE sub_id = %s",
                            [s["sub_id"]]).fetchone()
        assert sub["profile_status"] == "done" and sub["profile_id"] == pid
    finally:
        with pg.conn() as c:
            c.execute("DELETE FROM app.company_profile WHERE profile_key = %s", [pkey])


def test_an_open_question_makes_the_verdict_review_only_when_a_red_flag_is_at_stake(make_sub, flags):
    # A company profile's question holds records at locations the company lists: possible until answered, counted
    # neither way, and often without red flags. It used to make the verdict Review, labelled "with red flags".
    red, listed, also_listed, regrouped, found = key(), key(), key(), key(), key()
    _, s = make_sub({red: "ACME ELECTRIC CO OF TEXAS"})
    sid = str(s["sub_id"])
    with pg.conn() as c:
        ADJ._ask(c, s, [{"text": "Acme Electric lists these addresses on acme.example, and OSHA has records there",
                           "keys": [listed, also_listed], "suggestion": "same", "rationale": "Listed on acme.example",
                           "sources": []}], set())

    def verdict():
        f = Facts(as_of_year=2026, window_years=5, matched_establishments=0, inspections_all=0, inspections_window=0,
                  rated_window=0, serious_plus_window=0, red_flags=[], hazards=[], open_serious_cases=[],
                  **Q.question_facts(Q.scope(sid)["pending_questions"]))
        v, reasons = evaluate(f)
        return v, [(r.code, r.label) for r in reasons]

    assert verdict() == ("no_record", [("I_profile_questions", "2 record(s) at locations the company lists need your confirmation")])

    flags[also_listed] = 1  # a listed record with a red flag: the answer can add one
    assert verdict() == ("review", [("R_questions", "1 possible match(es) with red flags need your confirmation")])

    flags[red] = 2
    ADJ.adjudicate(s)  # rules only: the red-flagged record is a red-flag question
    with pg.conn() as c:  # a data update regrouped records the GC answered differently (no red flags), and the web
        # check suggests a record (a suggestion about a record that doesn't count yet: no reason at all)
        for k, kind in ((regrouped, "remap"), (found, "web")):
            c.execute("INSERT INTO app.match_question (sub_id, establishment_keys, text, kind) VALUES (%s, %s, 'x', %s)",
                      [sid, [k], kind])
    assert [q["kind"] for q in questions(sid)].count("red_flag") == 1
    assert verdict() == ("review", [("R_questions", "2 possible match(es) with red flags need your confirmation"),
                                    ("I_questions", "1 possible match(es) need your confirmation")])


def stub_card(sub, project, data=None) -> S.SubCard:
    """The card without the warehouse: only what Postgres knows."""
    sc = Q.scope(str(sub["sub_id"]))
    return S.SubCard(sub_id=str(sub["sub_id"]), entered_name=sub["entered_name"], entered_city=sub["entered_city"],
                     entered_state=sub["entered_state"], trade=None, display_name=None, verdict="no_record",
                     verdict_label="No OSHA record", reasons=[], match_status=Q.match_status(sc), matched_establishments=0,
                     matched_inspections=0, possible_inspections=0, pending_questions=len(sc["pending_questions"]),
                     red_flag_count=0, window_years=5, inspections_in_window=0, serious_plus_rate=None, trade_label=None,
                     trade_p50=None, trade_p75=None, states=[], first_year=None, last_year=None)


def test_the_api_leaves_a_sub_alone_while_another_request_resolves_it(client, make_user, make_sub, flags, monkeypatch):
    from ssi.api import app as A
    from ssi.llm import adjudicator
    from ssi.llm import profile as P
    k = key()
    p, s = make_sub({k: "ACME ELECTRICAL"})
    sid = str(s["sub_id"])
    looked_up = []
    monkeypatch.setattr(A.Q, "card", stub_card)
    monkeypatch.setattr(P, "for_sub", lambda *a, **kw: looked_up.append(a))
    monkeypatch.setattr(adjudicator, "available", lambda: False)  # rules only: no model calls from a test
    c = client(signed_in_as=make_user())
    base = f"/api/projects/{p['project_id']}/subs/{sid}"

    with ADJ.claim(sid):  # another request is resolving the sub
        r = c.post(base + "/adjudicate")
        assert r.status_code == 200 and r.json()["match_status"] == "needs_adjudication"  # the app asks again
        r = c.post(base + "/profile")
        assert r.status_code == 409 and "being resolved" in r.json()["detail"]
    assert looked_up == [] and rows(sid)[k]["needs_adjudication"]

    r = c.post(base + "/adjudicate")  # once it's free, this request resolves it
    assert r.status_code == 200 and r.json()["match_status"] == "resolved"
    assert len(looked_up) == 1 and claimed_at(sid) is None


def test_records_the_ai_couldnt_decide_go_back_to_it(make_sub, flags):
    # an outage or a spent budget used to leave them possible for good, shown as resolved, never counted or retried
    red, plain = key(), key()
    p, s = make_sub({red: "ACME ELECTRIC CO OF TEXAS", plain: "ACME ELECTRICAL"})
    sid = str(s["sub_id"])
    flags[red] = 1
    stats = ADJ.adjudicate(s, llm=lambda pk: None, packet_fn=packet)
    r = rows(sid)
    assert stats["unavailable"] == 1
    assert (r[plain]["bucket"], r[plain]["decided_by"], r[plain]["needs_adjudication"]) == ("possible", ADJ.AI_UNAVAILABLE, False)
    assert ADJ.UNAVAILABLE_NOTE in r[plain]["rationale"]
    assert r[red]["decided_by"] == "rules" and len(questions(sid)) == 1  # a red flag is the GC's question regardless
    assert ADJ.requeue_unavailable(str(p["project_id"])) == []  # not before the wait
    assert ADJ.requeue_unavailable(str(p["project_id"]), minutes=0) == [sid]
    assert rows(sid)[plain]["needs_adjudication"]
    ADJ.adjudicate(s, llm=lambda pk: None, packet_fn=packet)  # down again: one note, not two
    assert rows(sid)[plain]["rationale"].count(ADJ.UNAVAILABLE_NOTE) == 1
    ADJ.requeue_unavailable(str(p["project_id"]), minutes=0)
    ADJ.adjudicate(s, llm=different, packet_fn=packet)  # back up: decided
    assert (rows(sid)[plain]["bucket"], rows(sid)[plain]["decided_by"]) == ("excluded", "ai:test")


def test_the_verdict_says_when_the_ai_couldnt_check_records():
    from ssi.scoring.verdict import Facts, evaluate
    f = Facts(as_of_year=2026, window_years=5, matched_establishments=1, inspections_all=3, inspections_window=1,
              rated_window=1, serious_plus_window=0, red_flags=[], hazards=[], open_serious_cases=[], pending_questions=0,
              ai_unchecked=2)
    v, r = evaluate(f)
    assert v == "no_flags" and [x.code for x in r] == ["I_ai_unchecked"]  # possible records count neither way


@pytest.fixture
def hoffman(tmp_path):
    """"Hoffman Construction Company, Portland" on a tiny warehouse of OSHA records (tests/mini_warehouse.py): two of
    its OF <PLACE> companies at its head office, and its Seattle one. Yields the sub, not yet matched."""
    from ssi.store import warehouse
    from tests.mini_warehouse import Rec, build
    hq = "805 SW Broadway Ste 2100"
    build(tmp_path / "warehouse.duckdb", [
        Rec("HOFFMAN CONSTRUCTION CO. OF OREGON", hq, "Portland", "OR", "97205", n=3, naics="236220"),
        Rec("HOFFMAN CONSTRUCTION COMPANY OF AMERICA", hq, "Portland", "OR", "97205", n=2, naics="236220"),
        Rec("HOFFMAN CONSTRUCTION COMPANY OF WA", "600 Stewart St Ste 1000", "Seattle", "WA", "98101", n=2, naics="236220")])
    saved = warehouse._con, warehouse._path, warehouse._meta
    warehouse._con = None
    warehouse.open_warehouse(tmp_path / "warehouse.duckdb")
    pg.ensure_schema()
    with pg.conn() as c:
        p = c.execute("INSERT INTO app.project (name, state) VALUES ('pytest hoffman', 'OR') RETURNING *").fetchone()
        s = c.execute("""INSERT INTO app.project_sub (project_id, entered_name, entered_city, entered_state, trade)
                         VALUES (%s, 'Hoffman Construction Company', 'Portland', 'OR', 'general contractor') RETURNING *""",
                      [p["project_id"]]).fetchone()
    yield s
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = %s", [p["project_id"]])
    warehouse._con.close()
    warehouse._con, warehouse._path, warehouse._meta = saved


def by_name(sub) -> dict[tuple, tuple]:
    return {(r["evidence"]["name"], r["evidence"]["city"]): (r["bucket"], r["method"], r["rule_id"])
            for r in rows(str(sub["sub_id"])).values() if r["evidence"]}


HQ_MATCHED = {("HOFFMAN CONSTRUCTION CO OF OREGON", "PORTLAND"): ("matched", "rule", "M1s"),
              ("HOFFMAN CONSTRUCTION COMPANY OF AMERICA", "PORTLAND"): ("matched", "rule", "M1s"),
              ("HOFFMAN CONSTRUCTION COMPANY OF WA", "SEATTLE"): ("excluded", "llm", "S1")}


def test_a_gcs_own_companies_at_its_office_never_reach_the_ai(hoffman):
    # "Hoffman Construction Company, Portland" read "No OSHA record": with no record under exactly that name there,
    # rule S1 sent Hoffman's OF OREGON and OF AMERICA records at its head office to the adjudicator, which, told a
    # suffix usually means a sister company, excluded them. Now they're matched (M1s), and the record it's still asked
    # about is judged against them
    from ssi.matching import run
    run.match_and_persist(hoffman, "OR")
    asked = []

    def ai(packet):
        asked.append(packet)
        return different(packet)
    ADJ.adjudicate(hoffman, llm=ai, packet_fn=ADJ.evidence_packet)
    assert by_name(hoffman) == HQ_MATCHED
    # one question for the AI, the Seattle company, with the head office's records as the sub's matched ones
    assert len(asked) == 1 and any(" OF WA" in line["text"] for line in asked[0]["lines"])
    matched = [line["text"] for line in asked[0]["lines"] if line["text"].startswith("Already matched OSHA record")]
    assert len(matched) == 2 and all("PORTLAND OR 97205" in t for t in matched)


def test_a_re_match_replaces_the_ais_exclusion_of_records_a_rule_now_matches(hoffman, monkeypatch):
    # the live sub: added before M1s, so Jev excluded its head office's records. A re-match (make follow,
    # scripts/rematch.py) used to keep every AI decision, so the sub kept reading "No OSHA record"
    from ssi.matching import run
    with monkeypatch.context() as m:
        m.setattr(run, "home_office", lambda q, cands, descriptors=None: {})  # the rules before M1s
        run.match_and_persist(hoffman, "OR")
    ADJ.adjudicate(hoffman, llm=different, packet_fn=packet)
    assert {k: v[:2] for k, v in by_name(hoffman).items()} == {k: ("excluded", "llm") for k in HQ_MATCHED}
    run.match_and_persist(hoffman, "OR")  # the re-match, with M1s
    assert by_name(hoffman) == HQ_MATCHED  # the Seattle company, still S1 to the rules, keeps the AI's answer
