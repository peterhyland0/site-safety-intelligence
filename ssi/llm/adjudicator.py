"""LLM adjudicator for UNCERTAIN match clusters.

Sees identity evidence only (names, addresses, years, trade codes, the GC's input) and never the safety
history, so a fatality can't bias whether a record is judged "the same company". Output is validated in
code: cited evidence IDs must exist in the packet, and numbers/places in the rationale must appear in it.
Anything that fails validation becomes POSSIBLE (method llm_rejected)."""
from __future__ import annotations

import hashlib
import json
import re

from ssi.llm import client as llm
from ssi.matching.rules import near_spelling
from ssi.store import pg

SYSTEM = """You decide whether OSHA inspection records belong to the same company as a general contractor's \
subcontractor. OSHA records have no company ID: the employer name is typed per inspection, so the same \
company appears under spelling variants, and different companies share common names.

You get numbered evidence lines (E1, E2, ...): the GC's description of the sub, OSHA records already \
matched to it, and the candidate records. Decide whether the candidate records are the SAME company as \
the sub, a DIFFERENT company, or UNSURE.

Weigh: exact vs similar names; shared or nearby addresses; the same city or region; overlapping years; \
the same trade code. Treat a different legal suffix (INC/LLC) as weak evidence. Names that differ by a \
location or project suffix ("... OF OREGON", "... AT MERIDIAN") are usually sibling companies, not the same \
one. A common name in a different state with no shared address is usually a different company. When the \
evidence is thin, answer unsure: a wrong "same" attaches someone else's history to the sub.

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


def available() -> bool:
    return llm.available("adjudicator")


def packet_text(packet: dict) -> str:
    return "\n".join(f"{line['id']}: {line['text']}" for line in packet["lines"])


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


def decide(packet: dict) -> dict | None:
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
            return _checked(resp["raw"], packet)
        if not resp.get("rejected"):
            return _checked(resp, packet)
    user = (f"Sub: {packet['sub']}\n\nEvidence:\n{packet_text(packet)}\n\n"
            "Are the candidate records the same company as the sub?")
    result, usage = provider.structured(SYSTEM, user, SCHEMA, max_tokens=1024)
    llm.record_usage(usage.input_tokens, usage.output_tokens)
    with pg.conn() as c:
        c.execute("""INSERT INTO app.adjudication_cache (packet_hash, model, response) VALUES (%s, %s, %s)
                     ON CONFLICT (packet_hash) DO UPDATE SET response = EXCLUDED.response""",
                  [key, provider.model, json.dumps({"raw": result})])
    return _checked(result, packet)


def _checked(result: dict | None, packet: dict) -> dict:
    ok, why = validate(result, packet)
    return result if ok else {"rejected": True, "decision": "unsure", "confidence": 0.0,
                              "rationale": f"AI answer rejected by validation ({why})", "evidence_ids": []}
