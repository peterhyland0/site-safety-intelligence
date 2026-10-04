"""The foreman's tools and a sub's open match questions: only one whose answer can add a red flag holds up an answer,
as only those make the verdict Review. No database: the sub's data is what Q.compute would cache."""
from ssi.agent.tools import Toolbox
from ssi.matching import candidates as C
from ssi.queries import core as Q
from ssi.scoring.verdict import Facts, evaluate

SID = "sub-1"


def toolbox(monkeypatch, questions, flagged=()):
    monkeypatch.setattr(C, "red_flag_counts", lambda keys: {k: 1 for k in keys if k in flagged})
    f = Facts(as_of_year=2026, window_years=5, matched_establishments=1, inspections_all=3, inspections_window=1,
              rated_window=1, serious_plus_window=0, red_flags=[], hazards=[], open_serious_cases=[],
              **Q.question_facts(questions))
    tb = Toolbox({"project_id": "p"}, [{"sub_id": SID, "entered_name": "Acme Electric"}])
    tb.cache[SID] = {"scope": {"pending_questions": questions}, "facts": f, "reasons": evaluate(f)[1], "flags": []}
    return tb


def q(kind, keys, text=None):
    return {"kind": kind, "establishment_keys": keys, "text": text or f"{kind}: {', '.join(keys)}?"}


def red_flags(tb):
    return tb.run("red_flags", {"sub_id": SID, "kinds": []})


def test_questions_with_no_red_flag_at_stake_dont_hold_up_an_answer_and_it_notes_them(monkeypatch):
    # records at locations the company's profile lists, and a record a data update regrouped: possible, counted
    # neither way, like any possible record the GC isn't asked about
    tb = toolbox(monkeypatch, [q("profile", ["a", "b"]), q("remap", ["c"]), q("web", ["d"])])
    out = red_flags(tb)
    assert out["sub"] == "Acme Electric" and out["total"] == 0 and "status" not in out
    assert out["open_match_questions"]["questions"] == [
        "2 record(s) at locations the company lists need your confirmation", "1 possible match(es) need your confirmation"]


def test_a_question_with_a_red_flag_at_stake_holds_up_every_per_sub_tool_and_only_it_is_listed(monkeypatch):
    red, listed_flagged, listed = q("red_flag", ["r"]), q("profile", ["a", "b"]), q("profile", ["c"])
    tb = toolbox(monkeypatch, [listed, q("web", ["d"])])
    assert tb._precondition(SID) is None  # nothing at stake, not even with a web question

    tb = toolbox(monkeypatch, [listed_flagged, listed], flagged={"b"})  # one listed record has a red flag
    out = red_flags(tb)
    assert out["status"] == "needs_confirmation" and out["pending_questions"] == [listed_flagged["text"]]

    tb = toolbox(monkeypatch, [listed, red, {**red, "kind": None, "text": "asked before kinds"}])
    assert red_flags(tb)["pending_questions"] == [red["text"], "asked before kinds"]


def test_no_open_questions_no_note(monkeypatch):
    assert "open_match_questions" not in red_flags(toolbox(monkeypatch, []))
