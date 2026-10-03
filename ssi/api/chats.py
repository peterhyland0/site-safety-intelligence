"""The foreman's chats: each user's conversations about a project, kept in Postgres and private to that user.

A chat is created by its first question. The history the foreman sees is read from app.chat_message, never
taken from the browser. No connection is held while the model answers (seconds), so a slow answer doesn't
tie up the pool.
"""
from __future__ import annotations

import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response

from ssi.api import schemas as S
from ssi.api.auth import current_user
from ssi.store import pg

router = APIRouter(prefix="/api")

HISTORY_MESSAGES = 12  # earlier messages loaded as context (the foreman keeps the last 8)
LIST_LIMIT = 50
TITLE_CHARS = 80

_SUMMARY = """SELECT c.*, (SELECT count(*) FROM app.chat_message m WHERE m.chat_id = c.chat_id) AS message_count
              FROM app.chat c"""


def _uuid(value: str, what: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise HTTPException(404, f"{what} not found")


def _project(c, project_id: str) -> dict:
    p = c.execute("SELECT * FROM app.project WHERE project_id = %s", [_uuid(project_id, "Project")]).fetchone()
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _chat(c, chat_id: str, user: dict) -> dict:
    # someone else's chat is "not found", so chat ids reveal nothing
    row = c.execute(_SUMMARY + " WHERE c.chat_id = %s AND c.user_id = %s",
                    [_uuid(chat_id, "Chat"), user["user_id"]]).fetchone()
    if not row:
        raise HTTPException(404, "Chat not found")
    return row


def _title(question: str) -> str:
    q = re.sub(r"\s+", " ", question).strip()
    if len(q) <= TITLE_CHARS:
        return q
    cut = q[:TITLE_CHARS - 1]
    return (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,;:") + "…"


def _summary(row: dict) -> S.ChatSummary:
    return S.ChatSummary(chat_id=str(row["chat_id"]), project_id=str(row["project_id"]), title=row["title"],
                         created_at=row["created_at"].isoformat(), updated_at=row["updated_at"].isoformat(),
                         message_count=row["message_count"])


def _message(row: dict) -> S.ChatMessage:
    return S.ChatMessage(message_id=row["message_id"], role=row["role"], content=row["content"],
                         response=S.AskResponse.model_validate(row["response"]) if row["response"] else None,
                         created_at=row["created_at"].isoformat())


def _answer(project: dict, question: str, history: list[dict], chat_id: str, user: dict) -> S.AskResponse:
    from ssi.agent import foreman  # imported lazily, like the ask route was: pulls in the LLM providers
    return foreman.answer(project, question, history, chat_id=chat_id, user_id=str(user["user_id"]))


def _save_turn(c, chat_id: str, question: str, resp: S.AskResponse) -> S.ChatReply:
    rows = [c.execute("""INSERT INTO app.chat_message (chat_id, role, content, response) VALUES (%s, %s, %s, %s)
                         RETURNING *""", [chat_id, role, content, response]).fetchone()
            for role, content, response in (("user", question, None),
                                            ("assistant", resp.answer, json.dumps(resp.model_dump())))]
    chat = c.execute(_SUMMARY + " WHERE c.chat_id = %s", [chat_id]).fetchone()
    return S.ChatReply(chat=_summary(chat), messages=[_message(r) for r in rows])


@router.get("/projects/{project_id}/chats", response_model=list[S.ChatSummary])
def list_chats(project_id: str, user: dict = Depends(current_user)):
    with pg.conn() as c:
        p = _project(c, project_id)
        rows = c.execute(_SUMMARY + " WHERE c.user_id = %s AND c.project_id = %s ORDER BY c.updated_at DESC LIMIT %s",
                         [user["user_id"], p["project_id"], LIST_LIMIT]).fetchall()
    return [_summary(r) for r in rows]


@router.post("/projects/{project_id}/chats", response_model=S.ChatReply)
def create_chat(project_id: str, body: S.ChatAsk, user: dict = Depends(current_user)):
    with pg.conn() as c:
        project = _project(c, project_id)
    chat_id = str(uuid.uuid4())  # chosen now so the question log can name the chat before it's saved
    resp = _answer(project, body.question, [], chat_id, user)
    with pg.conn() as c:
        c.execute("INSERT INTO app.chat (chat_id, user_id, project_id, title) VALUES (%s, %s, %s, %s)",
                  [chat_id, user["user_id"], project["project_id"], _title(body.question)])
        return _save_turn(c, chat_id, body.question, resp)


@router.get("/chats/{chat_id}", response_model=S.ChatDetail)
def get_chat(chat_id: str, user: dict = Depends(current_user)):
    with pg.conn() as c:
        chat = _chat(c, chat_id, user)
        msgs = c.execute("SELECT * FROM app.chat_message WHERE chat_id = %s ORDER BY message_id",
                         [chat["chat_id"]]).fetchall()
    return S.ChatDetail(**_summary(chat).model_dump(), messages=[_message(m) for m in msgs])


@router.post("/chats/{chat_id}/messages", response_model=S.ChatReply)
def send_message(chat_id: str, body: S.ChatAsk, user: dict = Depends(current_user)):
    with pg.conn() as c:
        chat = _chat(c, chat_id, user)
        project = _project(c, str(chat["project_id"]))
        history = c.execute("""SELECT role, content FROM (
                                 SELECT * FROM app.chat_message WHERE chat_id = %s ORDER BY message_id DESC LIMIT %s
                               ) m ORDER BY message_id""", [chat["chat_id"], HISTORY_MESSAGES]).fetchall()
    resp = _answer(project, body.question, history, str(chat["chat_id"]), user)
    with pg.conn() as c:
        # deleted while the model was answering: nothing to add it to
        if not c.execute("UPDATE app.chat SET updated_at = now() WHERE chat_id = %s RETURNING chat_id",
                         [chat["chat_id"]]).fetchone():
            raise HTTPException(404, "Chat not found")
        return _save_turn(c, str(chat["chat_id"]), body.question, resp)


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str, user: dict = Depends(current_user)):
    with pg.conn() as c:
        if not c.execute("DELETE FROM app.chat WHERE chat_id = %s AND user_id = %s RETURNING chat_id",
                         [_uuid(chat_id, "Chat"), user["user_id"]]).fetchone():
            raise HTTPException(404, "Chat not found")
    return Response(status_code=204)
