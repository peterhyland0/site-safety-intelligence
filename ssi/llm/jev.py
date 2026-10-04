"""Jev, TypeSafe AI's decision model, as the match adjudicator for clusters without red flags.

One request per evidence packet: the packet is the state, and one Choice question (same / different / unsure)
carries the LLM adjudicator's guidance. Jev answers with probabilities and no text, so nothing it returns can
invent a name or a place; the reason the GC sees is written here from the evidence (rationale()). Why Jev, and
how it was tested against the LLM: docs/adjudicator.md.

Env: JEV_API_KEY (or the official SDK's TYPESAFE_API_KEY); optional JEV_API_URL / TYPESAFE_BASE_URL (default
https://api.typesafe.ai, or https://openrouter.ai/api with an OpenRouter key; a URL ending in /v1/systemone works
too) and TYPESAFE_DEFAULT_MODEL (default jev-latest). Plain httpx: it's one POST, and httpx is already a dependency."""
from __future__ import annotations

import hashlib
import json
import os
import time
from functools import cache

import httpx

from ssi import config  # noqa: F401 - loads .env, as the other providers do

DEFAULT_BASE_URL = "https://api.typesafe.ai"
USD_PER_M_INPUT = 0.042  # list price, October 2026; output is free

# Thresholds on P(same), picked on the development sample of eval/adjudication (seed 7) and checked on a
# held-out one (seed 11). A record outside the sub's state needs a much lower P(same) to be excluded: that's
# where a national firm's own branches are (NPL Construction, NVR), and a wrongly excluded branch hides the
# sub's own history, while a lookalike left possible isn't counted.
MATCH_AT = 0.85
EXCLUDE_AT = {"same_state": 0.20, "other_state": 0.06}
# The version those thresholds were tuned on. TypeSafe only offers aliases (jev-latest, jev-preview), so a new
# version arrives unannounced: adjudicator.decide_jev logs a warning when another one answers. Re-run
# eval/adjudication then.
TUNED_ON = "jev-1.13.0"


def _guidance() -> str:
    from ssi.llm.adjudicator import GUIDANCE  # the LLM's guidance, without its output rules
    return GUIDANCE


@cache
def questions() -> dict:
    return {"decision": {
        "type": "choice",
        "instructions": _guidance(),
        "criteria": {
            "same": "The candidate records are the same company as the GC's sub.",
            "different": "The candidate records are a different company from the GC's sub.",
            "unsure": "The evidence is too thin to tell.",
        },
    }}


def questions_hash() -> str:
    """Part of the cache key, so a change to the question or the guidance asks again."""
    return hashlib.sha256(json.dumps(questions(), sort_keys=True).encode()).hexdigest()[:16]


def _env(*names: str) -> str:
    return next((v for v in (os.environ.get(n, "").strip() for n in names) if v), "")


def available() -> bool:
    return bool(_env("JEV_API_KEY", "TYPESAFE_API_KEY"))


def model() -> str:
    return _env("TYPESAFE_DEFAULT_MODEL") or "jev-latest"


def base_url() -> str:
    url = (_env("JEV_API_URL", "TYPESAFE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    for suffix in ("/v1/systemone", "/v1"):
        url = url.removesuffix(suffix)
    return url


def client() -> httpx.Client:
    return httpx.Client(base_url=base_url(), timeout=30.0,
                        headers={"Authorization": f"Bearer {_env('JEV_API_KEY', 'TYPESAFE_API_KEY')}"})


def state(packet: dict) -> dict:
    return {"sub": packet["sub"], "evidence": {line["id"]: line["text"] for line in packet["lines"]}}


def ask(packet: dict, http: httpx.Client | None = None, qs: dict | None = None, retries: int = 3) -> dict:
    """{model, answers, usage, seconds}; raises on a failed request after retrying 429s and 5xx."""
    body = {"state": state(packet), "model": model(), "questions": qs or questions()}
    own = http is None
    http = http or client()
    try:
        for attempt in range(retries + 1):
            t = time.time()
            r = http.post("/v1/systemone", json=body)
            if (r.status_code == 429 or r.status_code >= 500) and attempt < retries:
                time.sleep(float(r.headers.get("retry-after") or 2 ** attempt))
                continue
            if r.is_error:
                raise RuntimeError(f"Jev HTTP {r.status_code}: {r.text[:200]}")
            out = r.json()
            return {"model": out.get("model"), "answers": out["answers"], "usage": out.get("usage") or {},
                    "seconds": round(time.time() - t, 3)}
    finally:
        if own:
            http.close()
    raise AssertionError("unreachable")


def p_same(response: dict) -> float:
    """P(same) from the choice: 'unsure' counts half."""
    probs = response["answers"]["decision"]["probabilities"]
    return float(probs.get("same", 0)) + 0.5 * float(probs.get("unsure", 0))


def decision(p: float, same_state: bool | None) -> dict:
    """P(same) as an adjudicator answer that adjudicate.ai_bucket reads the way the thresholds above intend.
    An unknown state counts as another state (the stricter threshold)."""
    limit = EXCLUDE_AT["same_state" if same_state else "other_state"]
    if p >= MATCH_AT:
        return {"decision": "same", "confidence": round(p, 4)}
    if p <= limit:
        return {"decision": "different", "confidence": round(1 - p, 4)}
    return {"decision": "unsure", "confidence": round(max(p, 1 - p), 4)}


def rationale(p: float, verdict: str, facts: dict) -> str:
    """The reason line, written from the packet's evidence (adjudicate.packet_facts), never from the model. Each fact
    is sorted by which way it points, for or against the same company, so one that cuts against the verdict reads
    as weighed, not as a contradiction. The side that agrees with the verdict comes first."""
    lead = {"same": "Likely the same company", "different": "Likely a different company"}.get(verdict, "Unclear")
    pro, con, where = [], [], ""
    place = facts.get("place")
    if place and facts.get("same_state") is False:
        con.append(f"{place}, outside the sub's state" + (f" ({facts['sub_state']})" if facts.get("sub_state") else ""))
    elif place and facts.get("same_state"):
        pro.append(f"{place}, in the sub's state")
    elif place:
        where = f" In {place}."  # the sub's state isn't known: no side
    if facts.get("anchor_addresses"):
        if facts.get("shared_address"):
            pro.append("shares an address with the sub's matched records")
        else:
            con.append("no address in common with the sub's matched records")
    trades, theirs = (facts.get("trade") or "").split(", "), facts.get("anchor_trades") or []
    common = [t for t in trades if t in theirs]
    if trades != [""] and theirs:
        if trades == theirs:
            pro.append(f"same trade code ({', '.join(trades)})")
        elif common:
            pro.append(f"shares a trade code ({', '.join(common)})")
        else:
            con.append(f"trade code {', '.join(trades)}, the matched records' {', '.join(theirs)}")
    sides = [("For", pro), ("Against", con)]
    if verdict == "different":
        sides.reverse()
    return (f"{lead}: Jev puts the chance it's the same company at {round(p * 100)}%.{where}"
            + "".join(f" {label}: {'; '.join(items)}." for label, items in sides if items))
