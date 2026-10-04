"""Adjudicator for UNCERTAIN match clusters: Jev for ordinary clusters, the LLM for red-flagged ones.

decide() routes each cluster. A red-flagged cluster becomes a question to the GC, who reads the AI's reason, so
it goes to the LLM, whose written reason is checked below. The rest go to Jev (ssi/llm/jev.py) when a Jev key is
set: it was more accurate than the LLM on held-out silver pairs, about 3.5x faster, and writes no text, so its
reason line is written in code from the evidence (docs/adjudicator.md). SSI_ADJUDICATOR=llm sends everything to
the LLM; a failed Jev call falls back to it. A failed LLM call leaves that one cluster possible (a red-flagged one
still becomes a GC question), so one timeout doesn't lose the decisions on the sub's other clusters.

Either way the adjudicator sees identity evidence only (names, addresses, years, trade codes, the GC's input)
and never the safety history, so a fatality can't bias whether a record is judged "the same company". The LLM's
output is validated in code: cited evidence IDs must exist in the packet, and numbers/places in the rationale
must appear in it. Anything that fails validation becomes POSSIBLE (method llm_rejected)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re

from ssi.llm import client as llm
from ssi.llm import jev
from ssi.matching.rules import near_spelling
from ssi.store import pg

# GUIDANCE is how to judge; SYSTEM adds the output rules. The Jev comparison (eval/adjudication) sends GUIDANCE alone.
GUIDANCE = """You decide whether OSHA inspection records belong to the same company as a general contractor's \
subcontractor. OSHA records have no company ID: the employer name is typed per inspection, so the same \
company appears under spelling variants, and different companies share common names.

You get numbered evidence lines (E1, E2, ...): the GC's description of the sub, OSHA records already \
matched to it, and the candidate records. Decide whether the candidate records are the SAME company as \
the sub, a DIFFERENT company, or UNSURE.

Weigh: exact vs similar names; shared or nearby addresses; the same city or region; overlapping years; \
the same trade code. Treat a different legal suffix (INC/LLC) as weak evidence. Names that differ by a \
location or project suffix ("... OF OREGON", "... AT MERIDIAN") are usually sibling companies, not the same \
one. A common name in a different state with no shared address is usually a different company. When the \
evidence is thin, answer unsure: a wrong "same" attaches someone else's history to the sub."""

SYSTEM = GUIDANCE + """

Cite the evidence lines you relied on by ID. Keep the rationale to one or two short sentences, and only \
mention names, places, years and numbers that appear in the evidence."""

SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["same", "different", "unsure"]},
        "confidence": {"type": "number"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["decision", "confidence", "evidence_ids", "rationale"],
    "additionalProperties": False,
}


log = logging.getLogger(__name__)


def use_jev() -> bool:
    """Jev handles ordinary clusters when its key is set, unless SSI_ADJUDICATOR=llm."""
    return os.environ.get("SSI_ADJUDICATOR", "jev").strip().lower() != "llm" and jev.available()


def available() -> bool:
    return llm.available("adjudicator") or use_jev()


def decide(packet: dict) -> dict | None:
    """The answer for one cluster from whichever adjudicator handles it (see the module docstring), or None (the
    cluster stays possible)."""
    has_llm = llm.available("adjudicator")
    if use_jev() and not (packet.get("red_flagged") and has_llm):
        try:
            return decide_jev(packet)
        except Exception as e:  # noqa: BLE001 - any failure: the LLM, or leave the cluster possible
            log.warning("Jev failed (%s: %s); %s", type(e).__name__, e, "using the LLM" if has_llm else "left possible")
    if not has_llm:
        return None
    try:
        return decide_llm(packet)
    except Exception as e:  # noqa: BLE001 - a timeout or 5xx on one cluster: leave it possible, go on with the rest
        log.warning("LLM adjudicator failed (%s: %s); left possible", type(e).__name__, e)
        return None


def decide_jev(packet: dict) -> dict | None:
    """Jev's answer through its thresholds, with a reason written from the evidence; cached like the LLM's."""
    if not llm.budget_ok():
        return None
    model = jev.model()
    key = hashlib.sha256(f"jev|{model}|{jev.questions_hash()}|{json.dumps(packet['lines'], sort_keys=True)}"
                         .encode()).hexdigest()
    with pg.conn() as c:
        hit = c.execute("SELECT response FROM app.adjudication_cache WHERE packet_hash = %s", [key]).fetchone()
    resp = (hit["response"] or {}).get("jev") if hit else None
    if not resp:
        resp = jev.ask(packet)
        u = resp["usage"]
        llm.record_usage(u.get("input_tokens") or 0, u.get("output_tokens") or 0)
        with pg.conn() as c:
            c.execute("""INSERT INTO app.adjudication_cache (packet_hash, model, response) VALUES (%s, %s, %s)
                         ON CONFLICT (packet_hash) DO UPDATE SET response = EXCLUDED.response""",
                      [key, model, json.dumps({"jev": resp})])
    return jev_answer(resp, packet)


_warned: set[str] = set()


def jev_answer(resp: dict, packet: dict) -> dict:
    served = resp.get("model") or jev.model()
    if served != jev.TUNED_ON and served not in _warned:
        _warned.add(served)
        log.warning("Jev answered as %s; its thresholds were tuned on %s: re-run eval/adjudication", served, jev.TUNED_ON)
    facts = packet.get("facts") or {}
    p = jev.p_same(resp)
    answer = jev.decision(p, facts.get("same_state"))
    return {**answer, "p_same": round(p, 4), "evidence_ids": [],
            "rationale": jev.rationale(p, answer["decision"], facts),
            "decided_by": f"ai:jev:{served}"}


def packet_text(packet: dict) -> str:
    return "\n".join(f"{line['id']}: {line['text']}" for line in packet["lines"])


def user_prompt(packet: dict) -> str:
    return (f"Sub: {packet['sub']}\n\nEvidence:\n{packet_text(packet)}\n\n"
            "Are the candidate records the same company as the sub?")


def validate(result: dict | None, packet: dict) -> tuple[bool, str]:
    """Code-side checks on the model's answer. Returns (ok, reason)."""
    if not result:
        return False, "no answer"
    if result.get("decision") not in ("same", "different", "unsure"):
        return False, "bad decision"
    conf = result.get("confidence")
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        return False, "confidence out of range"
    ids = {line["id"] for line in packet["lines"]}
    cited = result.get("evidence_ids") or []
    if not cited or not set(cited) <= ids:
        return False, "cites evidence that was not provided"
    rationale = result.get("rationale") or ""
    if len(rationale) > 400:
        return False, "rationale too long"
    text = packet_text(packet).upper()
    for num in re.findall(r"\d[\d,.]*", rationale):
        if num.strip(".,").replace(",", "") not in text.replace(",", ""):
            return False, f"mentions {num}, which is not in the evidence"
    evidence_words = set(re.findall(r"[A-Z]{3,}", text))
    checked = _states_to_codes(rationale)  # "Tennessee" is the evidence's "TN"
    for m in re.finditer(r"\b[A-Z][A-Za-z]{2,}\b", checked):
        word, w = m.group(), m.group().upper()
        if w in COMMON_WORDS or w.startswith("E") and w[1:].isdigit():
            continue
        if _starts_sentence(checked, m.start()):  # "Although", "Thin", "Given": capitalised, not a name
            continue
        if w in text or any(near_spelling(w, e) for e in evidence_words):  # "Houston" for the GC's "heuston"
            continue
        return False, f"mentions '{word}', which is not in the evidence"
    return True, "ok"


US_STATES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA", "COLORADO": "CO",
    "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
    "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO",
    "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC",
}


def _states_to_codes(s: str) -> str:
    """Write state names as the 2-letter codes the evidence uses (codes are too short to be checked)."""
    for name in sorted(US_STATES, key=len, reverse=True):
        s = re.sub(rf"\b{name}\b", US_STATES[name], s, flags=re.IGNORECASE)
    return s


def _starts_sentence(s: str, i: int) -> bool:
    before = s[:i].rstrip()
    return not before or before[-1] in ".!?:;(\"'\u2014-"


COMMON_WORDS = {
    "THE", "SAME", "DIFFERENT", "UNSURE", "OSHA", "COMPANY", "COMPANIES", "RECORD", "RECORDS", "CANDIDATE", "NAME",
    "NAMES", "ADDRESS", "ADDRESSES", "STATE", "CITY", "TRADE", "CODE", "YEARS", "YEAR", "SUB", "SUBCONTRACTOR", "GC",
    "BOTH", "THIS", "THESE", "THAT", "THEY", "NO", "NOT", "LIKELY", "SIMILAR", "MATCHED", "MATCH", "SHARED", "SHARE",
    "OVERLAPPING", "OVERLAP", "ALREADY", "SPELLING", "VARIANT", "LEGAL", "SUFFIX", "SIBLING", "EVIDENCE", "WITH", "BUT",
    "AND", "ONE", "TWO", "ACTIVE", "ONLY", "ALSO", "COMMON", "GENERIC", "LOCATION", "PROJECT", "INC", "LLC",
}


def decide_llm(packet: dict) -> dict | None:
    """Returns {decision, confidence, rationale, evidence_ids} or {rejected: True, ...}; cached."""
    if not llm.budget_ok():
        return None
    provider = llm.get("adjudicator")
    key = hashlib.sha256((provider.model + "|" + json.dumps(packet["lines"], sort_keys=True)).encode()).hexdigest()
    with pg.conn() as c:
        hit = c.execute("SELECT response FROM app.adjudication_cache WHERE packet_hash = %s", [key]).fetchone()
    # The cache keeps the model's raw answer and the checks run on every read, so a fix to validate()
    # applies to cached answers without new model calls. (Older entries stored only a rejection: ask again.)
    if hit:
        resp = hit["response"] or {}
        if "raw" in resp:
            return checked(resp["raw"], packet)
        if not resp.get("rejected"):
            return checked(resp, packet)
    result, usage = provider.structured(SYSTEM, user_prompt(packet), SCHEMA, max_tokens=1024)
    llm.record_usage(usage.input_tokens, usage.output_tokens)
    with pg.conn() as c:
        c.execute("""INSERT INTO app.adjudication_cache (packet_hash, model, response) VALUES (%s, %s, %s)
                     ON CONFLICT (packet_hash) DO UPDATE SET response = EXCLUDED.response""",
                  [key, provider.model, json.dumps({"raw": result})])
    return checked(result, packet)


def checked(result: dict | None, packet: dict) -> dict:
    ok, why = validate(result, packet)
    return result if ok else {"rejected": True, "decision": "unsure", "confidence": 0.0,
                              "rationale": f"AI answer rejected by validation ({why})", "evidence_ids": []}
