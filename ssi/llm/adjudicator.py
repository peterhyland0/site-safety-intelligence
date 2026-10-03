"""LLM adjudicator for UNCERTAIN match clusters (wired up in the LLM phase)."""
from __future__ import annotations


def available() -> bool:
    return False


def decide(packet: dict) -> dict | None:
    return None
