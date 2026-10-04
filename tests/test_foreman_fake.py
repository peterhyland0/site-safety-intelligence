"""End-to-end foreman loop with a scripted fake model (no API spend): tools run against the real
warehouse and Postgres; checks the grounding retry, the deterministic fallback and clarify."""
import json
from urllib.parse import urlsplit

import pytest

from ssi import config
from ssi.llm.base import Reply, ToolCall

pytestmark = [
    pytest.mark.skipif(config.current_warehouse() is None, reason="needs a built warehouse"),
    # this test creates tables and writes rows: never point it at a hosted database
    pytest.mark.skipif(urlsplit(config.DATABASE_URL).hostname not in ("localhost", "127.0.0.1", "::1"),
                       reason="writes to the app database; runs only against a local Postgres"),
]


class Fake:
    name, model = "fake", "fake-model"

    def __init__(self, script):
        self.script, self.calls = list(script), []

    def chat(self, system, messages, tools, max_tokens=4000):
        self.calls.append(messages)
        step = self.script.pop(0)
        return step(tools) if callable(step) else step

    def user_message(self, text):
        return {"role": "user", "content": text}

    def tool_results(self, results):
        return [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": c.id, "content": b} for c, b, _ in results]}]


def _add_brasfield():
    from ssi.api.app import add_subs, create_project
    from ssi.api.schemas import ProjectCreate, SubInput, SubsCreate
    from ssi.store import pg, warehouse
    warehouse.open_warehouse()
    pg.ensure_schema()
    p = create_project(ProjectCreate(name="pytest foreman", state="AL", lookback_years=5))
    cards = add_subs(p.project_id, SubsCreate(rows=[SubInput(name="Brasfield & Gorrie", city="Birmingham", state="AL")]))
    with pg.conn() as c:
        proj = c.execute("SELECT * FROM app.project WHERE project_id = %s", [p.project_id]).fetchone()
    return proj, cards[0].sub_id


def _drop(proj):
    from ssi.store import pg
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = %s", [proj["project_id"]])


@pytest.fixture(scope="module")
def project():
    """Brasfield & Gorrie, resolved as the app resolves it (rules only here), with the GC's answer to its red-flag
    question: until then the foreman holds up any answer about it."""
    from ssi.matching import adjudicate as ADJ
    from ssi.store import pg
    proj, sub_id = _add_brasfield()
    with pg.conn() as c:
        sub = c.execute("SELECT * FROM app.project_sub WHERE sub_id = %s", [sub_id]).fetchone()
    ADJ.adjudicate(sub)
    with pg.conn() as c:
        qs = c.execute("SELECT question_id FROM app.match_question WHERE sub_id = %s AND answer IS NULL", [sub_id]).fetchall()
    for q in qs:
        ADJ.answer_question(str(q["question_id"]), "no")
    yield proj, sub_id
    _drop(proj)


@pytest.fixture
def unresolved():
    """Brasfield & Gorrie as added: a red-flagged possible record the adjudicator hasn't seen yet."""
    proj, sub_id = _add_brasfield()
    yield proj, sub_id
    _drop(proj)


def run(monkeypatch, project, script, question="How is Brasfield doing?", **ids):
    from ssi.agent import foreman
    from ssi.llm import client as llm
    fake = Fake(script)
    monkeypatch.setattr(llm, "available", lambda role="foreman": True)
    monkeypatch.setattr(llm, "budget_ok", lambda share=1.0: True)
    monkeypatch.setattr(llm, "get", lambda role="foreman": fake)
    monkeypatch.setattr(llm, "record_usage", lambda *a: None)
    monkeypatch.setattr(llm, "model_label", lambda role="foreman": "fake")
    return foreman.answer(project[0], question, [], **ids), fake


def summary_call(sub_id):
    return Reply("", [ToolCall("t1", "sub_summary", {"sub_id": sub_id})], {"role": "assistant", "content": "tool"}, "tool_use")


def test_grounded_answer_with_coverage(monkeypatch, project):
    def final(tools):
        return Reply("Brasfield & Gorrie: Review, based on older history.", [], {"role": "assistant", "content": "x"}, "end_turn")
    resp, _ = run(monkeypatch, project, [summary_call(project[1]), final])
    assert resp.status == "answered" and "Based on" in resp.coverage and resp.tools_used == ["sub_summary"]


def test_invented_number_triggers_retry_then_fallback(monkeypatch, project):
    bad = Reply("They had 987 willful violations.", [], {"role": "assistant", "content": "x"}, "end_turn")
    resp, fake = run(monkeypatch, project, [summary_call(project[1]), bad, bad])
    assert resp.status == "guard_failed" and "987" not in resp.answer
    assert "don't appear in the tool results" in json.dumps(fake.calls[-1])


def test_clarify(monkeypatch, project):
    ask = Reply("", [ToolCall("t1", "ask_which_sub", {"sub_ids": [project[1]]})], {"role": "assistant", "content": "x"}, "tool_use")
    resp, _ = run(monkeypatch, project, [ask], question="How's the electrician?")
    assert resp.status == "clarify" and resp.clarify_options[0].sub_id == project[1]


def test_question_log_names_the_chat_and_user(monkeypatch, project):
    import uuid

    from ssi.store import pg
    chat_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())  # the log has no foreign keys: it outlives both
    final = Reply("Brasfield & Gorrie: Review.", [], {"role": "assistant", "content": "x"}, "end_turn")
    run(monkeypatch, project, [summary_call(project[1]), final], chat_id=chat_id, user_id=user_id)
    with pg.conn() as c:
        row = c.execute("SELECT user_id::text, status FROM app.question_log WHERE chat_id = %s", [chat_id]).fetchone()
    assert row == {"user_id": user_id, "status": "answered"}


def test_a_red_flag_the_adjudicator_hasnt_seen_holds_up_the_answer(monkeypatch, unresolved):
    # it becomes the GC's question whichever way the AI leans, so the foreman doesn't answer as if it weren't there
    def final(tools):
        return Reply("Brasfield & Gorrie: no fatalities.", [], {"role": "assistant", "content": "x"}, "end_turn")
    resp, _ = run(monkeypatch, unresolved, [summary_call(unresolved[1]), final])
    assert resp.status == "needs_confirmation"


def test_compare_subs_gives_no_figures_for_a_held_sub(unresolved, project):
    from ssi.agent.tools import Toolbox
    from ssi.store import pg

    def compare(proj, sub_id):
        with pg.conn() as c:
            sub = c.execute("SELECT * FROM app.project_sub WHERE sub_id = %s", [sub_id]).fetchone()
        return Toolbox(proj, [sub]).run("compare_subs", {})
    out = compare(*unresolved)  # "which subs had fatalities?" mustn't read an empty count as none
    assert out["status"] == "needs_confirmation" and out["held"] == ["Brasfield & Gorrie"]
    (row,) = out["subs"]
    assert row["status"] == "needs_confirmation" and "fatality_investigations" not in row and "red_flags" not in row
    out = compare(*project)  # resolved and answered: the figures
    assert "status" not in out and "fatality_investigations" in out["subs"][0]
