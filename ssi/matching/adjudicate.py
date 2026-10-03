"""Resolve a sub's UNCERTAIN records. Rules-only by default; an LLM adjudicator can be plugged in
(see ssi/llm). Red-flag override: an uncertain record carrying a fatality/willful/repeat/FTA flag is
never decided by machine, in either direction. It becomes a yes/no question to the GC (with the AI's
lean as a suggestion) and is not counted until answered; past a few, questions are grouped by name."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from ssi import config
from ssi.matching import candidates as C
from ssi.store import pg

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
    places = list(dict.fromkeys(", ".join(x for x in ((r["evidence"] or {}).get("city"), (r["evidence"] or {}).get("state")) if x)
                                for r in ev_rows))
    facility = ""
    # only for a facility linked by the sub's own company name (N1), not one flagged for sharing an address
    if any((r["evidence"] or {}).get("related_only") and (r["evidence"] or {}).get("rule") == "N1" for r in ev_rows):
        code = ev.get("naics4")
        several = len(ev_rows) > 1
        facility = ((" These facilities aren't coded as construction" if several else " This facility isn't coded as construction")
                    + (f" (industry code {code})" if code and not several else "")
                    + (": they may be plants, yards or shops of the same company." if several
                       else ": it may be a plant, yard or shop of the same company."))
    if len(places) <= 1:
        place = ", ".join(x for x in (ev.get("address"), ev.get("city"), ev.get("state")) if x) or "no address on file"
        return (f"OSHA has {n} inspection(s) {first}–{last} under '{ev.get('name')}' ({place}) that include serious red flags."
                f"{facility} Is this the same company as your sub '{sub['entered_name']}'?")
    where = "; ".join(p or "no address" for p in places[:5]) + (f" and {len(places) - 5} more places" if len(places) > 5 else "")
    return (f"OSHA has {n} inspection(s) {first}–{last} under '{ev.get('name')}' in {where} that include serious red flags."
            f"{facility} Are these the same company as your sub '{sub['entered_name']}'? If only some are, answer each "
            f"record below.")


RedCluster = tuple[list[dict], dict | None, str | None, int]  # rows, AI decision, rationale, red-flag count


def questions_for(sub: dict, red: list[RedCluster]) -> list[tuple[str, list[str], str | None, str | None]]:
    """Every red-flagged uncertain cluster reaches the GC. Up to QUESTION_GROUP_THRESHOLD clusters get a
    question each; past that, one question per OSHA name (all its states), so none is dropped.
    Returns (text, establishment keys, AI suggestion, AI rationale), most red flags first."""
    person = any(((r["evidence"] or {}).get("query") or {}).get("tier") == "person" for c in red for r in c[0])
    if person or len(red) <= config.QUESTION_GROUP_THRESHOLD:
        groups = [[c] for c in red]  # a person's name is never grouped: each record is likely a different person
    else:
        by_name: dict[str | None, list[RedCluster]] = defaultdict(list)
        for c in red:
            by_name[(c[0][0]["evidence"] or {}).get("name")].append(c)
        groups = list(by_name.values())
    groups.sort(key=lambda g: -sum(c[3] for c in g))
    out = []
    for g in groups:
        rows = [r for c in g for r in c[0]]
        leans = [c[1]["decision"] for c in g if c[1] and not c[1].get("rejected")]
        suggestion = leans[0] if len(leans) == len(g) and len(set(leans)) == 1 else None
        rationale = g[0][2] if len(g) == 1 and g[0][1] else None
        out.append((question_text(sub, rows), [r["establishment_key"] for r in rows], suggestion, rationale))
    return out


MATCH_AT, EXCLUDE_AT = 0.85, 0.80  # a wrong "same" costs more than a wrong "different"


def ai_bucket(decision: dict) -> str:
    """Where a validated AI answer puts a cluster (red flags aside): confident enough, or left possible."""
    conf = float(decision.get("confidence") or 0)
    if decision["decision"] == "same" and conf >= MATCH_AT:
        return "matched"
    if decision["decision"] == "different" and conf >= EXCLUDE_AT:
        return "excluded"
    return "possible"


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
    updates, red = [], []
    for i, (_, crow) in enumerate(clusters):
        keys = [r["establishment_key"] for r in crow]
        n_flags = sum(flags.get(k, 0) for k in keys)
        decision = None
        if llm and packet_fn and i < config.ADJUDICATE_MAX_CLUSTERS:
            packet = packet_fn(sub, crow)
            packet["red_flagged"] = n_flags > 0  # goes to the LLM, whose reason the GC reads (adjudicator.decide)
            decision = llm(packet)
            stats["llm_calls"] += 1
        bucket, method, conf, rationale = "possible", "rule", None, crow[0]["rationale"]
        if decision:
            conf = float(decision.get("confidence") or 0)
            rationale = decision.get("rationale") or rationale
            if decision.get("rejected"):
                method = "llm_rejected"
            else:
                method, bucket = "llm", ai_bucket(decision)
        if n_flags:  # red-flag override: never settled by machine, whichever way the AI leans
            bucket = "possible"
            red.append((crow, decision, rationale if decision else None, n_flags))
        decided_by = (decision or {}).get("decided_by") or (_ai_label() if method.startswith("llm") else "rules")
        updates.append((bucket, method, conf, rationale, keys, decided_by))
    questions = questions_for(sub, red)
    with pg.conn() as c:
        for bucket, method, conf, rationale, keys, decided_by in updates:
            c.execute("""UPDATE app.sub_match SET bucket = %s, method = %s, confidence = %s, rationale = %s,
                                needs_adjudication = false, decided_by = %s, decided_at = now()
                         WHERE sub_id = %s AND establishment_key = ANY(%s)""",
                      [bucket, method, conf, rationale, decided_by, sub_id, keys])
        open_keys = {k for r in c.execute("SELECT establishment_keys FROM app.match_question WHERE sub_id = %s AND answer IS NULL",
                                          [sub_id]).fetchall() for k in r["establishment_keys"]}
        for text, keys, suggestion, rationale in questions:
            if set(keys) <= open_keys:
                continue  # already waiting for the GC
            c.execute("""INSERT INTO app.match_question (sub_id, establishment_keys, text, ai_suggestion, ai_rationale)
                         VALUES (%s, %s, %s, %s, %s)""", [sub_id, keys, text, suggestion, rationale])
            stats["questions"] += 1  # count only questions actually asked
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
                     WHERE sub_id = %s AND %s = ANY(establishment_keys) AND answer IS NULL
                       AND cardinality(establishment_keys) = 1""",
                  ["yes" if bucket == "matched" else "no", sub_id, establishment_key])
        # a grouped question ("these records under one name") stays open for the rest of its records
        c.execute("""UPDATE app.match_question SET establishment_keys = array_remove(establishment_keys, %s)
                     WHERE sub_id = %s AND %s = ANY(establishment_keys) AND answer IS NULL""",
                  [establishment_key, sub_id, establishment_key])


def evidence_packet(sub: dict, crow: list[dict]) -> dict:
    """Identity evidence only (never safety history), with IDs the model must cite, plus facts for a reason
    written in code (packet_facts)."""
    with pg.conn() as c:
        anchor = c.execute("""SELECT evidence FROM app.sub_match WHERE sub_id = %s AND bucket = 'matched'
                              ORDER BY (evidence->>'inspections')::int DESC NULLS LAST LIMIT 5""", [str(sub["sub_id"])]).fetchall()
        project = c.execute("SELECT state FROM app.project WHERE project_id = %s", [sub.get("project_id")]).fetchone()
    anchors, cluster = [a["evidence"] for a in anchor], [r["evidence"] for r in crow]
    packet = build_packet(sub, anchors, cluster, [r["establishment_key"] for r in crow])
    # the search used the sub's state, or the project's when the GC gave none (run.match_and_persist)
    packet["facts"] = packet_facts(anchors, cluster, sub.get("entered_state") or (project or {}).get("state"))
    return packet


def packet_facts(anchors: list[dict], cluster: list[dict], search_state: str | None) -> dict:
    """The cluster (one name in one state, possibly several cities) against the sub's search and its matched
    records, for the reason line written in code (ssi.llm.jev.rationale) and Jev's threshold (in the sub's state
    or not). Never shown to a model."""
    state = (search_state or "").strip().upper() or None
    their_state = cluster[0].get("state")
    cities = list(dict.fromkeys((c.get("city") or "").title() for c in cluster if c.get("city")))
    where = (" and ".join(cities) if len(cities) <= 2 else f"{len(cities)} places in") if cities else ""
    addresses = {a["address"].upper() for a in anchors if a.get("address")}
    trades = sorted({c["naics4"] for c in cluster if c.get("naics4")})
    return {
        "place": (f"{where}, {their_state}" if where and their_state and len(cities) <= 2
                  else f"{where} {their_state}" if where and their_state else where or their_state or None),
        "sub_state": state,
        "same_state": their_state == state if state and their_state else None,
        "anchor_addresses": bool(addresses),
        "shared_address": any(c.get("address") and c["address"].upper() in addresses for c in cluster),
        "trade": ", ".join(trades) or None,
        "anchor_trades": sorted({a["naics4"] for a in anchors if a.get("naics4")}),
    }


def build_packet(sub: dict, anchors: list[dict], cluster: list[dict], keys: list[str]) -> dict:
    """The evidence lines from evidence dicts: the GC's input, records already matched (most inspected first),
    then up to 5 candidates. Shared with eval/adjudication, which builds packets without a saved sub."""
    lines = []
    def add(text):
        lines.append({"id": f"E{len(lines) + 1}", "text": text})
    add(f"GC's sub: name '{sub['entered_name']}', city '{sub.get('entered_city') or 'not given'}', "
        f"state '{sub.get('entered_state') or 'not given'}', trade '{sub.get('trade') or 'not given'}'")
    for e in anchors:
        add(f"Already matched OSHA record: '{e['name']}' at {e.get('address') or 'no address'}, {e.get('city') or ''} "
            f"{e.get('state') or ''} {e.get('zip') or ''}; active {e['years'][0]}–{e['years'][1]}; trade code {e.get('naics4') or 'unknown'}")
    for e in cluster[:5]:
        add(f"Candidate OSHA record: '{e['name']}' at {e.get('address') or 'no address'}, {e.get('city') or ''} "
            f"{e.get('state') or ''} {e.get('zip') or ''}; active {e['years'][0]}–{e['years'][1]}; "
            f"{e.get('inspections')} inspection(s); trade code {e.get('naics4') or 'unknown'}; "
            f"name similarity {e.get('similarity')}; rule note: {e.get('reason')}")
    return {"lines": lines, "sub": sub["entered_name"], "keys": keys}
