"""Company profiles: the checks on what the web search reported, the Claude call loop (with a fake client), how
records are matched to listed locations, and the questions they become. The adjudication tests run against a
local Postgres with the warehouse lookups stubbed."""
import re
import uuid

import pytest
from conftest import local_db

from ssi.llm import profile as P
from ssi.matching import adjudicate as ADJ

PAGE = ("Headquarters 2273 Hayne Street Spartanburg, SC 29301 | Virginia Division 5400 Olgers Road "
        "Petersburg, VA 23803 | Texas Division San Antonio, TX")
URL = "https://tindallcorp.com/contact/"


def fake_addr(address: str, quote: str) -> tuple[str | None, bool]:
    """addr_key as the warehouse macro builds it (house number + first street word), checked against the quote."""
    m = re.match(r"(\d+)\s+(?:(?:N|S|E|W|WEST)\s+)?(\w+)", address.upper())
    if not m:
        return None, False
    return f"{m.group(1)} {m.group(2)}", bool(re.search(rf"\b{m.group(1)}\b.*\b{m.group(2)}\b", quote.upper()))


def loc(**kw):
    base = {"address": "5400 Olgers Road", "city": "Petersburg", "state": "VA", "zip": "23803", "kind": "plant",
            "source_url": URL, "quote": "Virginia Division 5400 Olgers Road Petersburg, VA 23803"}
    return {**base, **kw}


def report(*locations, found=True):
    return {"found": found, "name": "Tindall Corporation", "website": "tindallcorp.com", "summary": "Precast concrete",
            "note": None, "locations": list(locations)}


def check(*locations, **kw):
    return P.check(report(*locations, **kw), {P._norm_url(URL): PAGE}, addr=fake_addr)


# --- check(): only what the pages say ---------------------------------------------------------------------------
def test_a_quoted_address_is_kept_with_its_key_and_zip():
    p = check(loc())
    (kept,) = p["locations"]
    assert (kept["address"], kept["addr_key"], kept["zip"], kept["own_site"]) == ("5400 Olgers Road", "5400 OLGERS", "23803", True)
    assert p["found"] and p["domain"] == "tindallcorp.com" and p["dropped"] == 0


def test_a_quote_the_page_doesnt_contain_or_without_the_city_is_dropped():
    assert check(loc(quote="Virginia Division 5401 Olgers Road Petersburg, VA 23803"))["dropped"] == 1  # not on the page
    assert check(loc(city="Richmond"))["dropped"] == 1  # the city isn't in the quote
    assert check(loc(source_url="https://example.com/x"))["dropped"] == 1  # nothing was read from that page
    assert check(loc(state="Virginia"))["dropped"] == 1


def test_an_invented_street_or_zip_falls_back_to_the_city():
    (a,) = check(loc(address="12 Main Street"))["locations"]
    assert (a["address"], a["addr_key"], a["zip"], a["city"]) == (None, None, None, "Petersburg")
    (b,) = check(loc(zip="23899"))["locations"]
    assert b["address"] == "5400 Olgers Road" and b["zip"] is None
    (c,) = check(loc(address=None, zip=None, city="San Antonio", state="TX", quote="Texas Division San Antonio, TX"))["locations"]
    assert c["addr_key"] is None and c["city"] == "San Antonio"


def test_two_kinds_at_one_address_are_one_location():
    hq = loc(address="2273 Hayne Street", city="Spartanburg", state="SC", zip="29301", kind="headquarters",
             quote="Headquarters 2273 Hayne Street Spartanburg, SC 29301")
    (one,) = check(hq, {**hq, "kind": "plant"})["locations"]
    assert one["kind"] == "headquarters, plant"


def test_not_found_keeps_no_locations():
    p = check(loc(), found=False)
    assert not p["found"] and p["locations"] == [] and p["name"] is None


def test_the_cache_key_covers_the_prompt_and_the_model():
    ctx = {"name": "Tindell Corporation", "city": "Spartanburg", "state": "SC", "trade": None}
    assert P.profile_key(ctx, "m1") == P.profile_key(dict(ctx), "m1")
    assert P.profile_key(ctx, "m1") != P.profile_key(ctx, "m2")
    assert P.profile_key(ctx, "m1") != P.profile_key({**ctx, "city": "Greenville"}, "m1")


# --- research(): the Claude call loop --------------------------------------------------------------------------
class FakeClaude:
    """Returns the scripted responses in order and records the messages it was sent."""

    def __init__(self, *responses):
        self.responses, self.sent = list(responses), []
        self.beta = self
        self.messages = self

    def create(self, **kw):
        self.sent.append([dict(m) for m in kw["messages"]])
        return self.responses.pop(0)


def resp(stop, content, searches=0):
    return {"stop_reason": stop, "model": "claude-opus-5-5", "content": content,
            "usage": {"input_tokens": 100, "output_tokens": 10, "server_tool_use": {"web_search_requests": searches}}}


FETCH = {"type": "web_fetch_tool_result", "content": {"type": "web_fetch_result", "url": URL, "content": {
    "type": "document", "title": "Contact", "source": {"type": "text", "data": PAGE}}}}
REPORT = {"type": "tool_use", "name": "report_profile", "id": "t1", "input": report(loc())}
CTX = {"name": "Tindell Corporation", "city": "Spartanburg", "state": "SC", "trade": None, "osha_spelling": "TINDALL",
       "tier": "distinctive", "matched_at": []}


def test_a_paused_search_is_resumed_and_the_report_kept_with_the_pages_read():
    http = FakeClaude(resp("pause_turn", [FETCH], searches=2), resp("tool_use", [REPORT], searches=1))
    res = P.research(CTX, http)
    assert res["error"] is None and res["report"]["name"] == "Tindall Corporation" and res["searches"] == 3
    assert res["texts"][P._norm_url(URL)] == PAGE and res["titles"][P._norm_url(URL)] == "Contact"
    assert [m["role"] for m in http.sent[1]] == ["user", "assistant"]  # the paused turn went back as-is


def test_a_search_error_object_is_not_a_list_of_results():
    err = {"type": "web_search_tool_result", "content": {"type": "web_search_tool_result_error", "error_code": "unavailable"}}
    res = P.research(CTX, FakeClaude(resp("tool_use", [err, REPORT])))
    assert res["report"] and res["titles"] == {}


def test_no_report_gets_one_nudge_then_an_error():
    http = FakeClaude(resp("end_turn", [{"type": "text", "text": "Found it."}]), resp("tool_use", [REPORT]))
    assert P.research(CTX, http)["report"] and http.sent[1][-1]["content"].startswith("Report what you found")
    http = FakeClaude(resp("end_turn", []), resp("end_turn", []))
    assert P.research(CTX, http)["error"] == "no report (end_turn)"
    assert P.research(CTX, FakeClaude(resp("refusal", [])))["error"] == "refused"


def test_the_prompt_says_what_is_known():
    text = P.user_prompt({**CTX, "matched_at": ["PO BOX 1778, SPARTANBURG, SC, 29304"]})
    assert "'Tindell Corporation'" in text and "spell the name 'TINDALL'" in text and "PO BOX 1778" in text


# --- matching records to listed locations, and the questions --------------------------------------------------
PROFILE = {"name": "Tindall Corporation", "domain": "tindallcorp.com", "model": "claude-opus-5-5", "locations": [
    {"address": "5400 Olgers Road", "addr_key": "5400 OLGERS", "city": "Petersburg", "state": "VA", "zip": "23803",
     "kind": "plant", "source_url": URL, "quote": "Virginia Division\n5400 Olgers Road  Petersburg, VA 23803", "own_site": True},
    {"address": None, "addr_key": None, "city": "San Antonio", "state": "TX", "zip": None, "kind": "plant",
     "source_url": URL, "quote": "Texas Division San Antonio, TX", "own_site": True}]}


def est(key, name="TINDALL", address="5400 OLGERS RD", city="PETERSBURG", state="VA", zip5="23803", addr_key="5400 OLGERS", n=10):
    return {"establishment_key": key, "clean_name": name, "address": address, "city": city, "state": state, "zip5": zip5,
            "addr_key": addr_key, "insp_n": n, "first_seen": "2020-01-01", "last_seen": "2025-01-01",
            "primary_naics4": "3273", "related_only": True}


def test_records_match_a_listed_building_or_only_its_city():
    rows = [est("a"), est("b", zip5="99999"), est("c", city="SAN ANTONIO", state="TX", addr_key="9 ELM", zip5="78225"),
            est("d", state="NC"), est("e", addr_key="1 OTHER", city="PETERSBURG")]
    got = {k: v["level"] for k, v in ADJ.listed_records(PROFILE, rows).items()}
    # b: same building, another zip3 -> only its city; d: another state; e: another building in the listed city
    assert got == {"a": "address", "b": "city", "c": "city", "e": "city"}


def test_the_profile_question_names_records_red_flags_and_the_page():
    held = {"a": {"loc": {**PROFILE["locations"][0], "level": "address"}, "est": est("a"), "new": False},
            "v": {"loc": {**PROFILE["locations"][0], "level": "address"}, "est": est("v", name="TINDALL CORPORATION VIRGINIA DIVISION", n=2), "new": True},
            "c": {"loc": {**PROFILE["locations"][1], "level": "city"}, "est": est("c", city="SAN ANTONIO", state="TX"), "new": False}}
    by_level = {q["suggestion"]: q for q in ADJ.profile_questions({"entered_name": "Tindell Corporation"}, PROFILE, held, {"a": 3})}
    same, unsure = by_level["same"], by_level["unsure"]
    assert same["keys"] == ["a", "v"] and unsure["keys"] == ["c"]
    assert same["text"].startswith("Tindall Corporation lists these addresses on tindallcorp.com, and OSHA has records there: ")
    assert "'TINDALL' at 5400 OLGERS RD, PETERSBURG VA (10 inspections, red flags)" in same["text"]
    assert "'TINDALL CORPORATION VIRGINIA DIVISION' (another name)" in same["text"]
    assert "One of them includes serious red flags." in same["text"] and "answer each record below" in same["text"]
    assert same["rationale"] == "Listed on tindallcorp.com: “Virginia Division 5400 Olgers Road Petersburg, VA 23803”"
    assert same["sources"] == [{"url": URL, "title": None, "quote": "Virginia Division 5400 Olgers Road Petersburg, VA 23803"}]
    assert "lists San Antonio TX on tindallcorp.com" in unsure["text"] and "not at an address it lists" in unsure["text"]
    assert unsure["text"].endswith("Is this the same company as your sub 'Tindell Corporation'?")


# --- adjudication with a profile (local Postgres; warehouse lookups stubbed) --------------------------------------
@pytest.fixture
def sub():
    from ssi.store import pg
    pg.ensure_schema()
    with pg.conn() as c:
        p = c.execute("INSERT INTO app.project (name, state) VALUES (%s, 'SC') RETURNING *", [f"pytest profile {uuid.uuid4().hex[:6]}"]).fetchone()
        s = c.execute("""INSERT INTO app.project_sub (project_id, entered_name, entered_city, entered_state, profile_status)
                         VALUES (%s, 'Tindell Corporation', 'Spartanburg', 'SC', 'pending') RETURNING *""", [p["project_id"]]).fetchone()
        for key, name, city, state in (("a", "TINDALL", "PETERSBURG", "VA"), ("x", "TINDALL", "MOBILE", "AL")):
            ev = {"name": name, "city": city, "state": state, "address": "1 X ST", "zip": "00000", "years": ["2020-01-01", "2025-01-01"],
                  "inspections": 3, "naics4": "3273", "similarity": 1.0, "reason": "N1", "rule": "N1",
                  "query": {"clean": "TINDALL", "core": "TINDALL", "tier": "distinctive"}}
            c.execute("""INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale, evidence,
                                                    needs_adjudication, decided_by)
                         VALUES (%s, %s, 'possible', 'rule', 'N1', 'rule note', %s, true, 'rules')""",
                      [s["sub_id"], key, __import__("json").dumps(ev)])
    yield s
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = %s", [p["project_id"]])


@pytest.fixture
def warehouse_stub(monkeypatch):
    from ssi.matching import candidates as C
    from ssi.store import warehouse
    rows = {"a": est("a"), "x": est("x", city="MOBILE", state="AL", addr_key="9 ELM", zip5="36601"),
            "v": est("v", name="TINDALL CORPORATION VIRGINIA DIVISION", n=2)}
    monkeypatch.setattr(C, "establishments", lambda keys: [rows[k] for k in keys if k in rows])
    monkeypatch.setattr(C, "red_flag_counts", lambda keys: {"a": 2} if "a" in keys else {})
    monkeypatch.setattr(C, "at_listed_addresses", lambda locs, exclude, limit=20: [rows["v"]] if "v" not in exclude else [])
    monkeypatch.setattr(warehouse, "meta", lambda: {"build_id": "test"})


def _state(sub_id):
    from ssi.store import pg
    with pg.conn() as c:
        rows = {r["establishment_key"]: r for r in c.execute("SELECT * FROM app.sub_match WHERE sub_id = %s", [sub_id]).fetchall()}
        qs = c.execute("SELECT * FROM app.match_question WHERE sub_id = %s ORDER BY created_at", [sub_id]).fetchall()
    return rows, qs


@local_db
def test_listed_records_skip_the_ai_and_go_to_the_gc_in_one_question(sub, warehouse_stub):
    seen = []

    def llm(packet):
        seen.extend(packet["keys"])
        return {"decision": "different", "confidence": 0.95, "rationale": "Mobile AL, no shared address."}

    stats = ADJ.adjudicate(sub, llm=llm, packet_fn=lambda s, crow: {"keys": [r["establishment_key"] for r in crow], "lines": []},
                           profile=PROFILE)
    rows, qs = _state(sub["sub_id"])
    assert seen == ["x"] and stats["held"] == 2  # 'a' (listed) never reached the AI; 'v' found at the address
    assert rows["x"]["bucket"] == "excluded" and rows["x"]["method"] == "llm"
    assert {k: (rows[k]["bucket"], rows[k]["method"]) for k in ("a", "v")} == {"a": ("possible", "profile"), "v": ("possible", "profile")}
    assert rows["v"]["evidence"]["name"] == "TINDALL CORPORATION VIRGINIA DIVISION" and not rows["v"]["needs_adjudication"]
    (q,) = qs
    assert q["kind"] == "profile" and q["ai_suggestion"] == "same" and sorted(q["establishment_keys"]) == ["a", "v"]
    assert q["sources"][0]["url"] == URL  # the red-flagged 'a' is in this question, not a red-flag one

    from ssi.matching import run as M
    from ssi.matching.rules import Query
    M.persist(str(sub["sub_id"]), {"query": Query(clean="TINDALL", core="TINDALL", state="SC", city=None, trade=None,
                                                  tier="distinctive", initials_only=False, sibling=None, aliases=set()),
                                   "decisions": [], "note": None})
    rows, _ = _state(sub["sub_id"])
    assert rows["a"]["method"] == "profile" and rows["v"]["method"] == "profile"  # a re-match keeps them

    ADJ.answer_question(str(q["question_id"]), "yes")
    rows, _ = _state(sub["sub_id"])
    assert {k: (rows[k]["bucket"], rows[k]["method"]) for k in ("a", "v")} == {"a": ("matched", "gc"), "v": ("matched", "gc")}


@local_db
def test_without_a_profile_adjudication_is_unchanged(sub, warehouse_stub):
    seen = []
    ADJ.adjudicate(sub, llm=lambda p: seen.extend(p["keys"]) or {"decision": "unsure", "confidence": 0.5, "rationale": "x"},
                   packet_fn=lambda s, crow: {"keys": [r["establishment_key"] for r in crow], "lines": []}, profile=None)
    rows, qs = _state(sub["sub_id"])
    assert sorted(seen) == ["a", "x"] and "v" not in rows
    assert all(q["kind"] == "red_flag" for q in qs)


@local_db
def test_the_button_gives_an_open_question_the_profiles_evidence(sub, warehouse_stub):
    from ssi.store import pg
    ADJ.adjudicate(sub, llm=None, packet_fn=None, profile=None)  # 'a' is red-flagged: a red-flag question, no suggestion
    _, (q,) = _state(sub["sub_id"])
    assert q["kind"] == "red_flag" and q["ai_suggestion"] is None
    stats = ADJ.apply_profile(sub, PROFILE)
    _, qs = _state(sub["sub_id"])
    assert qs[0]["ai_suggestion"] == "same" and qs[0]["sources"][0]["url"] == URL  # the same question, now with evidence
    assert [x["kind"] for x in qs[1:]] == ["profile"] and qs[1]["establishment_keys"] == ["v"]  # 'v' asked separately
    assert "VIRGINIA DIVISION" in qs[1]["text"] and "'TINDALL' at" not in qs[1]["text"]  # ...and names only 'v'
    assert stats == {"held": 2, "questions": 1}
    assert ADJ.apply_profile(sub, PROFILE)["questions"] == 0  # idempotent
    with pg.conn() as c:
        assert c.execute("SELECT count(*) AS n FROM app.match_question WHERE sub_id = %s", [sub["sub_id"]]).fetchone()["n"] == 2
