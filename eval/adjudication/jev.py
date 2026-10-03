"""Jev for the comparison in run.py: the app's client (ssi/llm/jev.py) with a second question on the same request.

  decision  the app's Choice of same / different / unsure, with the LLM's guidance. Scored two ways in run.py:
            its top label and that label's probability through the app's LLM thresholds (adjudicate.ai_bucket),
            and its P(same) through the thresholds the app uses for Jev (ssi.llm.jev.decision).
  same      a Noul ("is this the same company?"): the probability of yes, through the LLM thresholds
            (>= 0.85 matched, <= 0.20 excluded, else possible). Kept for comparison; the app doesn't ask it.

Env as for the app: JEV_API_KEY, optional JEV_API_URL and TYPESAFE_DEFAULT_MODEL."""
from __future__ import annotations

import httpx

from ssi.llm import jev as app_jev
from ssi.llm.jev import USD_PER_M_INPUT, available, base_url, client, model, state  # noqa: F401 - re-exported

NOUL = {
    "type": "noul",
    "instructions": app_jev._guidance() + "\n\nAre the candidate records the same company as the sub?",
    "criteria": {"true": "The same company as the GC's sub.", "false": "A different company."},
}


def questions() -> dict:
    return {**app_jev.questions(), "same": NOUL}


def ask(packet: dict, http: httpx.Client, retries: int = 3) -> dict:
    """{model, answers, usage, seconds}; raises on a failed request after retrying 429s and 5xx."""
    return app_jev.ask(packet, http, questions(), retries)


def decisions(response: dict) -> dict[str, dict]:
    """Both questions as adjudicator-style answers: {variant: {decision, confidence, p_same}}."""
    choice = response["answers"]["decision"]
    p_yes = float(response["answers"]["same"]["noul"])
    return {
        "jev-choice": {"decision": choice["choice"], "confidence": float(choice["probabilities"][choice["choice"]]),
                       "p_same": app_jev.p_same(response)},
        "jev-noul": {"decision": "same" if p_yes >= 0.5 else "different", "confidence": max(p_yes, 1 - p_yes),
                     "p_same": p_yes},
    }
