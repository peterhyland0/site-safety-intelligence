"""Resolve a sub's UNCERTAIN records. Rules-only by default; an LLM adjudicator can be plugged in
(see ssi/llm). Red-flag override: an uncertain record carrying a fatality/willful/repeat/FTA flag is
never decided by machine, in either direction. It becomes a yes/no question to the GC (with the AI's
lean as a suggestion) and is not counted until answered; past a few, questions are grouped by name.

With a company profile (ssi/llm/profile.py), records at a location the company lists skip the AI and go to the
GC in one question, with the page that lists them; so do records found at those addresses under another name.
They're written with method 'profile' (possible until answered), which a re-match keeps. And an M3 match (the same
name in another state) in a state the profile doesn't list is checked on the web first (check_m3).

One request at a time resolves a sub (claim()), and a record the GC moves while the AI is working keeps the GC's
bucket."""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager

from ssi import config
from ssi.matching import candidates as C
from ssi.matching.rules import norm_city
from ssi.store import pg, warehouse

# llm(packet) -> {"decision": same|different|unsure, "confidence": float, "rationale": str} or None
LLMFn = Callable[[dict], dict | None]

CLAIM_STALE_MINUTES = 15  # a claim older than this was abandoned (the request died); the next request takes over
M3_CHECK_LIMIT = 5  # M3 groups (a name in a state) looked up per sub, most inspections first


@contextmanager
def claim(sub_id: str):
    """One lookup-and-adjudication per sub at a time. Yields the sub's row, read as the claim is taken, or None when
    another request is already at it. Two at once looked the company up twice, asked the GC the same question twice,
    and let the second adjudicate every record before the first one's profile arrived, so the profile was never used."""
    with pg.conn() as c:
        sub = c.execute(f"""UPDATE app.project_sub SET adjudicating_since = now()
                            WHERE sub_id = %s AND (adjudicating_since IS NULL
                              OR adjudicating_since < now() - interval '{CLAIM_STALE_MINUTES} minutes')
                            RETURNING *""", [sub_id]).fetchone()
    if sub is None:
        yield None
        return
    try:
        yield sub
    finally:
        with pg.conn() as c:  # only this request's claim: a newer request may have taken over a stale one
            c.execute("UPDATE app.project_sub SET adjudicating_since = NULL WHERE sub_id = %s AND adjudicating_since = %s",
                      [sub_id, sub["adjudicating_since"]])


def resolve(sub_id: str, project: dict, llm: LLMFn | None = None,
            packet_fn: Callable[[dict, list[dict]], dict] | None = None,
            profile_fn: Callable[[dict, dict], dict | None] | None = None,
            m3_fn: Callable[[dict, dict], dict] | None = None) -> dict | None:
    """The adjudication step for a sub, under its claim: look the company up (profile_fn), check its M3 matches against
    the profile (m3_fn: check_m3), then adjudicate, including any M3 match the check sent back. None when another
    request is already resolving the sub; its answer lands when that request finishes."""
    with claim(sub_id) as sub:
        if sub is None:
            return None
        profile = profile_fn(sub, project) if profile_fn else None
        if profile and m3_fn:
            m3_fn(sub, profile)
        return adjudicate(sub, llm=llm, packet_fn=packet_fn, profile=profile)


def check_m3(sub: dict, profile: dict | None, build_fn: Callable[[dict], dict | None]) -> dict:
    """The M3 web check. M3 matches the same distinctive name in another state; the M3 audit (eval/m3_audit) found the
    wrong ones are other companies with their own websites. With the sub's own website known, for each M3 group (a
    name in a state), up to M3_CHECK_LIMIT, most inspections first:
      a state the profile lists              ->  matched (an M3u record the guard held back is restored)
      otherwise the record's company is looked up (build_fn: profile.build, cached):
        the sub's own website                ->  matched, the reason says so (M3u restored)
        another company's website            ->  possible, rule M3w, for the adjudicator (needs_adjudication)
        no website of its own                ->  as it was (a short or missing profile isn't evidence)
    M3u records (rules.m3_collides) are the guard's doubtful ones, already waiting for the adjudicator. Returns
    {checked, moved, confirmed}: lookups made, records sent back, records confirmed or restored."""
    # imported here: the matching package doesn't otherwise need the profile module
    from ssi.llm.profile import company_domain
    stats = {"checked": 0, "moved": 0, "confirmed": 0}
    site = company_domain(profile)
    if not site:
        return stats
    sub_id = str(sub["sub_id"])
    listed = {loc["state"] for loc in profile.get("locations") or []}
    with pg.conn() as c:
        rows = c.execute("""SELECT * FROM app.sub_match WHERE sub_id = %s AND method = 'rule' AND (
                              (rule_id = 'M3' AND bucket = 'matched') OR (rule_id = 'M3u' AND needs_adjudication))""",
                         [sub_id]).fetchall()
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        ev = r["evidence"] or {}
        if ev.get("state") and (ev["state"] not in listed or r["rule_id"] == "M3u"):
            groups[(ev.get("name"), ev["state"])].append(r)
    order = sorted(groups.items(), key=lambda kv: -sum((r["evidence"] or {}).get("inspections") or 0 for r in kv[1]))

    def confirm(c, grp: list[dict], why: str) -> None:
        for r in grp:
            reason = ((r["evidence"] or {}).get("reason") or "Same distinctive name, another state").rstrip(".")
            if r["rule_id"] == "M3u":
                reason = f"Same distinctive name, another state ({(r['evidence'] or {}).get('state')})"
            c.execute("""UPDATE app.sub_match SET bucket = 'matched', rule_id = 'M3', rationale = %s, needs_adjudication = false,
                                evidence = coalesce(evidence, '{}'::jsonb) || jsonb_build_object('rule', 'M3', 'reason', %s::text)
                         WHERE sub_id = %s AND establishment_key = %s AND method = 'rule' AND rule_id IN ('M3', 'M3u')""",
                      [f"{reason}; {why}", reason, sub_id, r["establishment_key"]])
        stats["confirmed"] += len(grp)

    for (name, state), grp in order[:M3_CHECK_LIMIT]:
        if state in listed:  # only M3u records get here: the profile itself lists the state
            with pg.conn() as c:
                confirm(c, grp, f"the company's profile lists {state}")
            continue
        top = max((r["evidence"] for r in grp), key=lambda e: e.get("inspections") or 0)
        at = ", ".join(x for x in (top.get("address"), top.get("city"), state, top.get("zip")) if x)
        theirs = company_domain(build_fn({"name": name, "city": top.get("city"), "state": state, "trade": None,
                                          "osha_spelling": name, "tier": None, "matched_at": [at] if top.get("address") else []}))
        stats["checked"] += 1
        with pg.conn() as c:
            if theirs == site:
                confirm(c, grp, f"the web check found its records there under {site} too")
            elif theirs:
                why = (f"Same name in another state ({state}), but the company there has its own website ({theirs}), "
                       f"not {site}: often another company")
                c.execute("""UPDATE app.sub_match SET bucket = 'possible', rule_id = 'M3w', rationale = %s,
                                    needs_adjudication = true, decided_by = 'rules', decided_at = now(),
                                    evidence = coalesce(evidence, '{}'::jsonb) || jsonb_build_object('rule', 'M3w', 'reason', %s::text)
                             WHERE sub_id = %s AND establishment_key = ANY(%s) AND method = 'rule' AND rule_id IN ('M3', 'M3u')""",
                          [why, why, sub_id, [r["establishment_key"] for r in grp]])
                stats["moved"] += sum(r["rule_id"] == "M3" for r in grp)
    return stats


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


# --- company profile: records at listed locations go to the GC ------------------------------------------------
PROFILE_LOOKUP_LIMIT = 20  # records found at listed addresses under other names, per sub
PROFILE_LIST_LIMIT = 8  # records named in a question's text (all are listed below it)


def listed_records(profile: dict, rows: list[dict]) -> dict[str, dict]:
    """{establishment_key: location} for warehouse rows at a location the profile lists: the same building
    (addr_key, and zip3 when both have a zip) or, weaker, the same city and state. A building beats a city."""
    out = {}
    for r in rows:
        best = None
        for loc in profile.get("locations") or []:
            if loc["state"] != (r.get("state") or ""):
                continue
            if loc.get("addr_key") and r.get("addr_key") == loc["addr_key"] and (
                    not loc.get("zip") or not r.get("zip5") or loc["zip"][:3] == r["zip5"][:3]):
                best = {**loc, "level": "address"}
                break
            if best is None and norm_city(loc["city"]) == norm_city(r.get("city") or ""):
                best = {**loc, "level": "city"}
        if best:
            out[r["establishment_key"]] = best
    return out


def _holds(sub_id: str, profile: dict, rows: list[dict]) -> dict[str, dict]:
    """The records a profile sends to the GC: `rows` (app.sub_match) at listed locations, plus records at listed
    addresses on the company's own site under any name the sub has no row for (capped). {key: {loc, est, new}}."""
    est = {e["establishment_key"]: e for e in C.establishments([r["establishment_key"] for r in rows])}
    held = {k: {"loc": loc, "est": est[k], "new": False} for k, loc in listed_records(profile, list(est.values())).items()}
    with pg.conn() as c:
        have = {r["establishment_key"] for r in c.execute(
            "SELECT establishment_key FROM app.sub_match WHERE sub_id = %s", [sub_id]).fetchall()}
    own = [loc for loc in profile.get("locations") or [] if loc.get("own_site")]
    for e in C.at_listed_addresses(own, exclude=have | set(held), limit=PROFILE_LOOKUP_LIMIT):
        loc = listed_records(profile, [e]).get(e["establishment_key"])
        if loc and loc["level"] == "address":
            held[e["establishment_key"]] = {"loc": loc, "est": e, "new": True}
    return held


def _place(loc: dict) -> str:
    return ", ".join(x for x in (loc.get("address"), f"{loc['city']} {loc['state']}") if x)


def _site(profile: dict) -> str:
    return profile.get("domain") or profile.get("website") or "its website"


def profile_questions(sub: dict, profile: dict, held: dict[str, dict], flags: dict[str, int]) -> list[dict]:
    """One question for records at addresses the company lists (suggestion: same), one for records only in a city it
    lists (suggestion: unsure). Each names the records, their red flags, and the pages that list the locations."""
    out = []
    for level, suggestion in (("address", "same"), ("city", "unsure")):
        items = sorted(((k, h) for k, h in held.items() if h["loc"]["level"] == level),
                       key=lambda kh: -(kh[1]["est"].get("insp_n") or 0))
        if not items:
            continue
        named = []
        for k, h in items[:PROFILE_LIST_LIMIT]:
            e = h["est"]
            n = e.get("insp_n") or 0
            extra = [f"{n} inspection{'s' if n != 1 else ''}"] + (["red flags"] if flags.get(k) else [])
            other = " (another name)" if h["new"] else ""
            named.append(f"'{e['clean_name']}'{other} at {e.get('address') or 'no address'}, {e.get('city') or ''} "
                         f"{e.get('state') or ''} ({', '.join(extra)})")
        more = f"; and {len(items) - PROFILE_LIST_LIMIT} more" if len(items) > PROFILE_LIST_LIMIT else ""
        n_red = sum(1 for k, _ in items if flags.get(k))
        red = (f" {n_red} of them include serious red flags." if n_red > 1 else
               " One of them includes serious red flags." if n_red == 1 and len(items) > 1 else
               " It includes serious red flags." if n_red else "")
        several = len(items) > 1
        if level == "address":
            lead = f"{profile['name']} lists {'these addresses' if several else 'this address'} on {_site(profile)}, and OSHA has records there: "
        else:
            cities = "; ".join(dict.fromkeys(f"{h['loc']['city']} {h['loc']['state']}" for _, h in items))
            lead = (f"{profile['name']} lists {cities} on {_site(profile)}, and OSHA has records there under a similar name, "
                    f"but not at an address it lists: ")
        text = (lead + "; ".join(named) + more + "." + red
                + (f" Are these the same company as your sub '{sub['entered_name']}'? If only some are, answer each record below."
                   if several else f" Is this the same company as your sub '{sub['entered_name']}'?"))
        quotes = list(dict.fromkeys(" ".join(h["loc"]["quote"].split()) for _, h in items))
        sources = list({h["loc"]["source_url"]: {"url": h["loc"]["source_url"], "title": h["loc"].get("title"),
                                                 "quote": " ".join(h["loc"]["quote"].split())} for _, h in items}.values())
        out.append({"text": text, "keys": [k for k, _ in items], "suggestion": suggestion,
                    "rationale": f"Listed on {_site(profile)}: " + " / ".join(f"“{q}”" for q in quotes[:2]),
                    "sources": sources})
    return out


def _evidence_for(e: dict, query: dict | None, reason: str) -> dict:
    """A found record's evidence, in the shape run._evidence stores for rule decisions."""
    return {"rule": "PROFILE", "reason": reason, "similarity": None, "name": e["clean_name"], "state": e["state"],
            "city": e["city"], "zip": e["zip5"], "address": e["address"], "years": [e["first_seen"], e["last_seen"]],
            "inspections": e["insp_n"], "naics4": e["primary_naics4"], "related_only": bool(e.get("related_only")),
            "query": query or {}}


def _write_holds(c, sub: dict, profile: dict, held: dict[str, dict], query: dict | None) -> None:
    """Held records: possible, method 'profile', waiting for the GC. Records new to the sub get a row."""
    sub_id = str(sub["sub_id"])
    by = f"profile:{profile.get('model') or 'unknown'}"
    build_id = warehouse.meta()["build_id"]
    nrs = C.members([k for k, h in held.items() if h["new"]])
    for k, h in held.items():
        loc = h["loc"]
        reason = (f"{'At an address' if loc['level'] == 'address' else 'In a city'} {profile['name']} lists on "
                  f"{_site(profile)} ({_place(loc)}); waiting for your answer")
        if h["new"]:
            c.execute("""INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale, evidence,
                                                    needs_adjudication, decided_by, build_id, activity_nrs)
                         VALUES (%s, %s, 'possible', 'profile', 'PROFILE', %s, %s, false, %s, %s, %s)
                         ON CONFLICT (sub_id, establishment_key) DO NOTHING""",
                      [sub_id, k, reason, json.dumps(_evidence_for(h["est"], query, reason), default=str), by, build_id,
                       nrs.get(k)])
        else:
            c.execute("""UPDATE app.sub_match SET bucket = 'possible', method = 'profile', rationale = %s, confidence = NULL,
                                needs_adjudication = false, decided_by = %s, decided_at = now()
                         WHERE sub_id = %s AND establishment_key = %s AND method NOT IN ('gc', 'remap', 'web')""",
                      [reason, by, sub_id, k])


def _ask(c, sub_id: str, questions: list[dict], open_keys: set[str], kind: str = "profile") -> int:
    asked = 0
    for q in questions:
        keys = [k for k in q["keys"] if k not in open_keys]
        if not keys:
            continue  # already waiting for the GC
        c.execute("""INSERT INTO app.match_question (sub_id, establishment_keys, text, ai_suggestion, ai_rationale, kind, sources)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                  [sub_id, keys, q["text"], q["suggestion"], q["rationale"], kind, json.dumps(q["sources"])])
        asked += 1
    return asked


def _open_questions(c, sub_id: str) -> list[dict]:
    return c.execute("SELECT * FROM app.match_question WHERE sub_id = %s AND answer IS NULL", [sub_id]).fetchall()


def apply_profile(sub: dict, profile: dict) -> dict:
    """For a sub adjudicated before it had a profile (the "Look up this company" button): its possible and excluded
    records the GC hasn't decided, at listed locations, go to the GC with the profile. An open question about exactly
    those records gets the profile as its suggestion instead of a second question. Records the web check is asking
    about (method 'web') keep their question."""
    sub_id = str(sub["sub_id"])
    stats = {"held": 0, "questions": 0}
    if not profile or not profile.get("locations"):
        return stats
    with pg.conn() as c:
        rows = c.execute("""SELECT * FROM app.sub_match WHERE sub_id = %s AND method NOT IN ('gc', 'remap', 'web')
                            AND bucket IN ('possible', 'excluded') AND establishment_key <> '__note__'""", [sub_id]).fetchall()
    held = _holds(sub_id, profile, rows)
    if not held:
        return stats
    flags = C.red_flag_counts(list(held))
    query = next(((r["evidence"] or {}).get("query") for r in rows if (r["evidence"] or {}).get("query")), None)
    with pg.conn() as c:
        open_qs = _open_questions(c, sub_id)
        for q in open_qs:  # an open question entirely about held records: give it the profile's evidence
            sub_held = {k: held[k] for k in q["establishment_keys"] if k in held}
            if q["establishment_keys"] and len(sub_held) == len(q["establishment_keys"]) and q.get("kind") != "web":
                pq = profile_questions(sub, profile, sub_held, flags)
                if len(pq) == 1:
                    c.execute("""UPDATE app.match_question SET ai_suggestion = %s, ai_rationale = %s, sources = %s
                                 WHERE question_id = %s""",
                              [pq[0]["suggestion"], pq[0]["rationale"], json.dumps(pq[0]["sources"]), q["question_id"]])
        open_keys = {k for q in open_qs for k in q["establishment_keys"]}
        _write_holds(c, sub, profile, held, query)
        stats["held"] = len(held)
        fresh = {k: h for k, h in held.items() if k not in open_keys}  # the question text names only what it asks
        stats["questions"] = _ask(c, sub_id, profile_questions(sub, profile, fresh, flags), open_keys)
    return stats


def adjudicate(sub: dict, llm: LLMFn | None = None, packet_fn: Callable[[dict, list[dict]], dict] | None = None,
               profile: dict | None = None) -> dict:
    sub_id = str(sub["sub_id"])
    with pg.conn() as c:
        rows = c.execute("SELECT * FROM app.sub_match WHERE sub_id = %s AND needs_adjudication", [sub_id]).fetchall()
    if not rows:
        with pg.conn() as c:
            c.execute("UPDATE app.project_sub SET adjudicated_at = now() WHERE sub_id = %s", [sub_id])
        return {"clusters": 0, "questions": 0, "llm_calls": 0}
    held = _holds(sub_id, profile, rows) if profile and profile.get("locations") else {}
    flags = C.red_flag_counts([r["establishment_key"] for r in rows] + [k for k, h in held.items() if h["new"]])
    query = next(((r["evidence"] or {}).get("query") for r in rows if (r["evidence"] or {}).get("query")), None)
    rows = [r for r in rows if r["establishment_key"] not in held]  # listed records skip the AI
    clusters = sorted(_clusters(rows).items(), key=lambda kv: -sum((r["evidence"] or {}).get("inspections") or 0 for r in kv[1]))
    stats = {"clusters": len(clusters), "questions": 0, "llm_calls": 0, "held": len(held)}
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
    with pg.conn() as c:
        for bucket, method, conf, rationale, keys, decided_by in updates:
            # only records still waiting: the GC may have moved one while the AI was working, and the GC's call stands
            c.execute("""UPDATE app.sub_match SET bucket = %s, method = %s, confidence = %s, rationale = %s,
                                needs_adjudication = false, decided_by = %s, decided_at = now()
                         WHERE sub_id = %s AND establishment_key = ANY(%s) AND needs_adjudication AND method <> 'gc'""",
                      [bucket, method, conf, rationale, decided_by, sub_id, keys])
        # ... and a record the GC has decided isn't asked about
        gc = {r["establishment_key"] for r in c.execute(
            "SELECT establishment_key FROM app.sub_match WHERE sub_id = %s AND method = 'gc'", [sub_id]).fetchall()}
        red = [(rest, d, why, sum(flags.get(r["establishment_key"], 0) for r in rest))
               for crow, d, why, _ in red if (rest := [r for r in crow if r["establishment_key"] not in gc])]
        questions = questions_for(sub, red)
        open_keys = {k for q in _open_questions(c, sub_id) for k in q["establishment_keys"]}
        if held:
            _write_holds(c, sub, profile, held, query)
            # the question text names only what it asks
            fresh = {k: h for k, h in held.items() if k not in open_keys and k not in gc}
            stats["questions"] += _ask(c, sub_id, profile_questions(sub, profile, fresh, flags), open_keys)
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
