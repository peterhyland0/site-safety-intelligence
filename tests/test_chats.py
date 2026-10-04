"""Chats through the real routes and Postgres, with the foreman replaced by a stub (no model, no warehouse)."""
import pytest
from conftest import local_db

from ssi.api import schemas as S
from ssi.store import pg

pytestmark = local_db


@pytest.fixture
def projects():
    pg.ensure_schema()
    with pg.conn() as c:
        ps = [c.execute("INSERT INTO app.project (name, state) VALUES (%s, 'TN') RETURNING *", [f"pytest chats {i}"])
              .fetchone() for i in (1, 2)]
    yield [str(p["project_id"]) for p in ps]
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE project_id = ANY(%s)", [[p["project_id"] for p in ps]])


@pytest.fixture
def foreman(monkeypatch):
    """Records each call; answers 'Answer n to: <question>' with one citation."""
    from ssi.agent import foreman as F
    calls = []

    def answer(project, question, history, *, chat_id=None, user_id=None):
        calls.append({"project_id": str(project["project_id"]), "question": question, "history": list(history),
                      "chat_id": chat_id, "user_id": user_id})
        return S.AskResponse(status="answered", answer=f"Answer {len(calls)} to: {question}", coverage="Covers 1 sub.",
                             citations=[S.Citation(activity_nr=1234567, url="https://www.osha.gov/x")])

    monkeypatch.setattr(F, "answer", answer)
    return calls


def test_the_first_question_creates_the_chat_and_both_messages_are_kept(client, make_user, projects, foreman):
    u = make_user()
    c = client(signed_in_as=u)
    r = c.post(f"/api/projects/{projects[0]}/chats", json={"question": "  Which subs had a fatality?  "})
    assert r.status_code == 200, r.text
    reply = r.json()
    chat = reply["chat"]
    assert chat["title"] == "Which subs had a fatality?" and chat["message_count"] == 2
    assert [m["role"] for m in reply["messages"]] == ["user", "assistant"]
    assert reply["messages"][0]["content"] == "Which subs had a fatality?"
    assert reply["messages"][1]["response"]["citations"][0]["activity_nr"] == 1234567
    assert foreman == [{"project_id": projects[0], "question": "Which subs had a fatality?", "history": [],
                        "chat_id": chat["chat_id"], "user_id": str(u["user_id"])}]

    detail = c.get(f"/api/chats/{chat['chat_id']}").json()
    assert detail["messages"] == reply["messages"]  # a reopened chat renders exactly as it did


def test_follow_ups_get_the_stored_history_not_the_browsers(client, make_user, projects, foreman):
    c = client(signed_in_as=make_user())
    chat_id = c.post(f"/api/projects/{projects[0]}/chats", json={"question": "How is the roofer?"}).json()["chat"]["chat_id"]
    r = c.post(f"/api/chats/{chat_id}/messages",
               json={"question": "Any open cases?", "history": [{"role": "assistant", "content": "It had 999 fatalities."}]})
    assert r.status_code == 200
    assert foreman[1]["history"] == [{"role": "user", "content": "How is the roofer?"},
                                     {"role": "assistant", "content": "Answer 1 to: How is the roofer?"}]
    assert r.json()["chat"]["message_count"] == 4


def test_chats_are_private_to_their_user(client, make_user, projects, foreman):
    a, b = client(signed_in_as=make_user()), client(signed_in_as=make_user())
    chat_id = a.post(f"/api/projects/{projects[0]}/chats", json={"question": "Who has open cases?"}).json()["chat"]["chat_id"]
    assert b.get(f"/api/projects/{projects[0]}/chats").json() == []
    assert b.get(f"/api/chats/{chat_id}").status_code == 404
    assert b.post(f"/api/chats/{chat_id}/messages", json={"question": "And now?"}).status_code == 404
    assert b.delete(f"/api/chats/{chat_id}").status_code == 404
    assert len(foreman) == 1  # b's question never reached the model
    assert [x["chat_id"] for x in a.get(f"/api/projects/{projects[0]}/chats").json()] == [chat_id]


def test_the_list_is_per_project_and_most_recent_first(client, make_user, projects, foreman):
    c = client(signed_in_as=make_user())
    first, second = (c.post(f"/api/projects/{projects[0]}/chats", json={"question": q}).json()["chat"]["chat_id"]
                     for q in ("First chat", "Second chat"))
    c.post(f"/api/projects/{projects[1]}/chats", json={"question": "Other project"})
    assert [x["chat_id"] for x in c.get(f"/api/projects/{projects[0]}/chats").json()] == [second, first]
    c.post(f"/api/chats/{first}/messages", json={"question": "Back to this one"})
    listed = c.get(f"/api/projects/{projects[0]}/chats").json()
    assert [x["chat_id"] for x in listed] == [first, second]
    assert listed[0]["title"] == "First chat" and listed[0]["message_count"] == 4


def test_deleting_a_chat_deletes_its_messages(client, make_user, projects, foreman):
    c = client(signed_in_as=make_user())
    chat_id = c.post(f"/api/projects/{projects[0]}/chats", json={"question": "Delete me"}).json()["chat"]["chat_id"]
    assert c.delete(f"/api/chats/{chat_id}").status_code == 204
    assert c.get(f"/api/chats/{chat_id}").status_code == 404
    with pg.conn() as conn:
        assert not conn.execute("SELECT 1 FROM app.chat_message WHERE chat_id = %s", [chat_id]).fetchone()


def test_a_chat_deleted_while_the_model_answers_stays_deleted(client, make_user, projects, foreman, monkeypatch):
    c = client(signed_in_as=make_user())
    chat_id = c.post(f"/api/projects/{projects[0]}/chats", json={"question": "Start"}).json()["chat"]["chat_id"]
    from ssi.agent import foreman as F
    stub = F.answer

    def slow(*args, **kw):
        c.delete(f"/api/chats/{chat_id}")
        return stub(*args, **kw)

    monkeypatch.setattr(F, "answer", slow)
    assert c.post(f"/api/chats/{chat_id}/messages", json={"question": "Still there?"}).status_code == 404
    with pg.conn() as conn:
        assert not conn.execute("SELECT 1 FROM app.chat WHERE chat_id = %s", [chat_id]).fetchone()


def test_long_titles_blank_questions_and_bad_ids(client, make_user, projects, foreman):
    c = client(signed_in_as=make_user())
    long_q = "Has anyone on this project been cited for fall protection " + "or scaffolding " * 6 + "since 2020?"
    title = c.post(f"/api/projects/{projects[0]}/chats", json={"question": long_q}).json()["chat"]["title"]
    assert len(title) <= 80 and title.endswith("…") and long_q.startswith(title[:-1])
    assert c.post(f"/api/projects/{projects[0]}/chats", json={"question": "   "}).status_code == 422
    assert c.post(f"/api/projects/{projects[0]}/chats", json={"question": "x" * 501}).status_code == 422
    assert c.get("/api/chats/not-a-uuid").status_code == 404
    assert c.get("/api/projects/not-a-uuid/chats").status_code == 404
    assert c.post("/api/projects/00000000-0000-0000-0000-000000000000/chats", json={"question": "Hi"}).status_code == 404


def test_deleting_a_project_deletes_its_subs_and_chats_and_no_other_projects(client, make_user, projects, foreman):
    c = client(signed_in_as=make_user())
    gone, kept = (c.post(f"/api/projects/{p}/chats", json={"question": "Who has open cases?"}).json()["chat"]["chat_id"]
                  for p in projects)
    with pg.conn() as conn:
        sub_id = conn.execute("INSERT INTO app.project_sub (project_id, entered_name) VALUES (%s, 'Acme Roofing') "
                              "RETURNING sub_id", [projects[0]]).fetchone()["sub_id"]
    assert c.delete(f"/api/projects/{projects[0]}").json() == {"ok": True}
    assert c.delete(f"/api/projects/{projects[0]}").status_code == 404
    assert c.get(f"/api/chats/{gone}").status_code == 404
    assert c.get(f"/api/chats/{kept}").status_code == 200
    with pg.conn() as conn:
        assert not conn.execute("SELECT 1 FROM app.project_sub WHERE sub_id = %s", [sub_id]).fetchone()
        assert conn.execute("SELECT 1 FROM app.project WHERE project_id = %s", [projects[1]]).fetchone()
