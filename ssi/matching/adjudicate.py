"""Resolve a sub's UNCERTAIN records. Rules-only by default; an LLM adjudicator can be plugged in
(see ssi/llm). Red-flag override: an uncertain record carrying a fatality/willful/repeat/FTA flag is
never decided by machine; it becomes a yes/no question to the GC and is not counted until answered."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Callable

from ssi import config
from ssi.matching import candidates as C
from ssi.store import pg, warehouse

# llm(packet) -> {"decision": same|different|unsure, "confidence": float, "rationale": str} or None
LLMFn = Callable[[dict], dict | None]


def _clusters(rows: list[dict]) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        ev = r["evidence"] or {}
        out[(ev.get("name"), ev.get("state"))].append(r)
    return out


def _ai_label() -> str:
    from ssi.llm import client as llm
    return "ai:" + llm.model_label("adjudicator")


def question_text(sub: dict, ev_rows: list[dict]) -> str:
    ev = ev_rows[0]["evidence"] or {}
    first = min((r["evidence"]["years"][0] or "") for r in ev_rows)[:4]
    last = max((r["evidence"]["years"][1] or "") for r in ev_rows)[:4]
    n = sum(r["evidence"]["inspections"] or 0 for r in ev_rows)
    place = ", ".join(x for x in (ev.get("address"), ev.get("city"), ev.get("state")) if x) or "no address on file"
    return (f"OSHA has {n} inspection(s) {first}–{last} under '{ev.get('name')}' ({place}) that include serious red flags. "
            f"Is this the same company as your sub '{sub['entered_name']}'?")


def adjudicate(sub: dict, llm: LLMFn | None = None, packet_fn: Callable[[dict, list[dict]], dict] | None = None) -> dict:
    sub_id = str(sub["sub_id"])
    with pg.conn() as c:
        rows = c.execute("SELECT * FROM app.sub_match WHERE sub_id = %s AND needs_adjudication", [sub_id]).fetchall()
    if not rows:
        with pg.conn() as c:
            c.execute("UPDATE app.project_sub SET adjudicated_at = now() WHERE sub_id = %s", [sub_id])
        return {"clusters": 0, "questions": 0, "llm_calls": 0}
    flags = C.red_flag_counts([r["establishment_key"] for r in rows])
    clusters = sorted(_clusters(rows).items(), key=lambda kv: -sum((r["evidence"] or {}).get("inspections") or 0 for r in kv[1]))
    stats = {"clusters": len(clusters), "questions": 0, "llm_calls": 0}
    with pg.conn() as c:
        for i, (_, crow) in enumerate(clusters):
            keys = [r["establishment_key"] for r in crow]
            has_flags = any(flags.get(k) for k in keys)
            decision = None
            if llm and packet_fn and i < config.ADJUDICATE_MAX_CLUSTERS:
                decision = llm(packet_fn(sub, crow))
                stats["llm_calls"] += 1
            bucket, method, conf, rationale = "possible", "rule", None, crow[0]["rationale"]
            if decision:
                conf = float(decision.get("confidence") or 0)
                rationale = decision.get("rationale") or rationale
                if decision.get("rejected"):
                    method = "llm_rejected"
                else:
                    method = "llm"
                    if decision["decision"] == "same" and conf >= 0.85:
                        bucket = "matched"
                    elif decision["decision"] == "different" and conf >= 0.80:
                        bucket = "excluded"
            if has_flags and bucket != "excluded" and stats["questions"] >= config.MAX_QUESTIONS_PER_SUB:
                bucket = "possible"  # too many lookalikes to ask about: visible, flagged, not counted
            elif has_flags and bucket != "excluded":
                bucket = "possible"  # red-flag override: the GC decides
                c.execute("""INSERT INTO app.match_question (sub_id, establishment_keys, text, ai_suggestion, ai_rationale)
                             VALUES (%s, %s, %s, %s, %s)""",
                          [sub_id, keys, question_text(sub, crow),
                           decision.get("decision") if decision and not decision.get("rejected") else None,
                           rationale if decision else None])
                stats["questions"] += 1
            c.execute("""UPDATE app.sub_match SET bucket = %s, method = %s, confidence = %s, rationale = %s,
                                needs_adjudication = false, decided_by = %s, decided_at = now()
                         WHERE sub_id = %s AND establishment_key = ANY(%s)""",
                      [bucket, method, conf, rationale, _ai_label() if method.startswith("llm") else "rules",
                       sub_id, keys])
        c.execute("UPDATE app.project_sub SET adjudicated_at = now() WHERE sub_id = %s", [sub_id])
    return stats


def answer_question(question_id: str, answer: str) -> dict:
    with pg.conn() as c:
        q = c.execute("SELECT * FROM app.match_question WHERE question_id = %s", [question_id]).fetchone()
        if not q:
            raise KeyError(question_id)
        c.execute("UPDATE app.match_question SET answer = %s, answered_at = now() WHERE question_id = %s",
                  [answer, question_id])
        c.execute("""UPDATE app.sub_match SET bucket = %s, method = 'gc', decided_by = 'gc', decided_at = now(),
                            needs_adjudication = false, rationale = %s
                     WHERE sub_id = %s AND establishment_key = ANY(%s)""",
                  ["matched" if answer == "yes" else "excluded",
                   "Confirmed by the GC" if answer == "yes" else "Rejected by the GC", q["sub_id"], q["establishment_keys"]])
    return q


def override(sub_id: str, establishment_key: str, bucket: str) -> None:
    with pg.conn() as c:
        c.execute("""UPDATE app.sub_match SET bucket = %s, method = 'gc', decided_by = 'gc', decided_at = now(),
                            needs_adjudication = false, rationale = 'Set by the GC'
                     WHERE sub_id = %s AND establishment_key = %s""", [bucket, sub_id, establishment_key])
        # answering by override also settles any open question about that record
        c.execute("""UPDATE app.match_question SET answer = %s, answered_at = now()
                     WHERE sub_id = %s AND %s = ANY(establishment_keys) AND answer IS NULL""",
                  ["yes" if bucket == "matched" else "no", sub_id, establishment_key])


def evidence_packet(sub: dict, crow: list[dict]) -> dict:
    """Identity evidence only (never safety history), with IDs the model must cite."""
    with pg.conn() as c:
        anchor = c.execute("""SELECT evidence FROM app.sub_match WHERE sub_id = %s AND bucket = 'matched'
                              ORDER BY (evidence->>'inspections')::int DESC NULLS LAST LIMIT 5""", [str(sub["sub_id"])]).fetchall()
    lines = []
    def add(text):
        lines.append({"id": f"E{len(lines) + 1}", "text": text})
    add(f"GC's sub: name '{sub['entered_name']}', city '{sub.get('entered_city') or 'not given'}', "
        f"state '{sub.get('entered_state') or 'not given'}', trade '{sub.get('trade') or 'not given'}'")
    for a in anchor:
        e = a["evidence"]
        add(f"Already matched OSHA record: '{e['name']}' at {e.get('address') or 'no address'}, {e.get('city') or ''} "
            f"{e.get('state') or ''} {e.get('zip') or ''}; active {e['years'][0]}–{e['years'][1]}; trade code {e.get('naics4') or 'unknown'}")
    for r in crow[:5]:
        e = r["evidence"]
        add(f"Candidate OSHA record: '{e['name']}' at {e.get('address') or 'no address'}, {e.get('city') or ''} "
            f"{e.get('state') or ''} {e.get('zip') or ''}; active {e['years'][0]}–{e['years'][1]}; "
            f"{e.get('inspections')} inspection(s); trade code {e.get('naics4') or 'unknown'}; "
            f"name similarity {e.get('similarity')}; rule note: {e.get('reason')}")
    return {"lines": lines, "sub": sub["entered_name"], "keys": [r["establishment_key"] for r in crow]}
