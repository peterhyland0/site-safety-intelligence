"""End-to-end foreman loop with a scripted fake model (no API spend): tools run against the real
warehouse and Postgres; checks the grounding retry, the deterministic fallback and clarify."""
import json

import pytest

from ssi import config
from ssi.llm.base import Reply, ToolCall

pytestmark = pytest.mark.skipif(config.current_warehouse() is None, reason="needs a built warehouse")


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


@pytest.fixture(scope="module")
def project():
    from ssi.api.app import add_subs, create_project
    from ssi.api.schemas import ProjectCreate, SubInput, SubsCreate
    from ssi.store import pg, warehouse
    warehouse.open_warehouse()
    pg.ensure_schema()
    p = create_project(ProjectCreate(name="pytest foreman", state="AL", lookback_years=5))
    cards = add_subs(p.project_id, SubsCreate(rows=[SubInput(name="Brasfield & Gorrie", city="Birmingham", state="AL")]))
    with pg.conn() as c:
        proj = c.execute("SELECT * FROM app.project WHERE project_id = %s", [p.project_id]).fetchone()
    yield proj, cards[0].sub_id
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = %s", [p.project_id])


def run(monkeypatch, project, script, question="How is Brasfield doing?"):
    from ssi.agent import foreman
    from ssi.llm import client as llm
    fake = Fake(script)
    monkeypatch.setattr(llm, "available", lambda role="foreman": True)
    monkeypatch.setattr(llm, "budget_ok", lambda: True)
    monkeypatch.setattr(llm, "get", lambda role="foreman": fake)
    monkeypatch.setattr(llm, "record_usage", lambda *a: None)
    monkeypatch.setattr(llm, "model_label", lambda role="foreman": "fake")
    return foreman.answer(project[0], question, []), fake


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
