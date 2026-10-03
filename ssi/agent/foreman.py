"""Foreman Q&A (wired up in the LLM phase)."""
from __future__ import annotations

from ssi.api import schemas as S


def answer(project: dict, question: str, history: list[dict]) -> S.AskResponse:
    return S.AskResponse(status="no_api_key", answer="The question assistant isn't configured yet.")
