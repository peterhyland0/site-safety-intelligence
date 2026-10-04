"""The web check on a sub's undecided records: the sub page's "Check records on the web" button.

Suggest-only. Each group of records (one OSHA name at one place) is looked up on the web (ssi/llm/web_check.py) and
compared with the sub; the result goes to the GC as a question, with the page and the quote, and nothing is matched
or excluded until the GC answers:
  same       the page ties the record to the sub's company (its website, its parent's, or the AI's comparison):
             held as possible (method 'web'), in one question suggesting "same". An excluded record moves to
             possible, so it shows next to its question and a re-match keeps it.
  different  the page ties it to another company: a possible record is held (method 'web') in one question
             suggesting "different"; an excluded one stays excluded, with what was found.
  unsure     nothing settles it: the record stays as it is, with what was found.
Every checked record keeps the result in its evidence (web_check) and isn't checked again for 90 days; a search
that failed is tried again on the next press. Web questions don't hold up the verdict or the assistant: they're
suggestions, unlike the questions about red-flagged records.

Records the GC has decided, ones waiting for the adjudicator, and ones in an open question are left alone; a record
the GC moves while the check runs keeps the GC's bucket. A person's name (a sole proprietor) is never searched."""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from ssi.llm import web_check as W
from ssi.matching import adjudicate as ADJ
from ssi.matching import candidates as C
from ssi.store import pg

ELIGIBLE = ("rule", "llm", "llm_rejected")  # decided by the rules or the AI, not by the GC or another hold
CHECK_TTL_DAYS = 90


def _recent(mark: dict | None) -> bool:
    try:
        at = datetime.fromisoformat((mark or {}).get("at") or "")
    except ValueError:
        return False
    return datetime.now(UTC) - at < timedelta(days=CHECK_TTL_DAYS)


def _ev(r: dict) -> dict:
    return r.get("evidence") or {}


def is_person(rows: list[dict]) -> bool:
    return any((_ev(r).get("query") or {}).get("tier") == "person" for r in rows)


def candidates(rows: list[dict], open_questions: list[dict]) -> list[dict]:
    """The sub's records the button would check (app.sub_match rows): possible or excluded, decided by the rules or
    the AI, not waiting for the adjudicator or in an open question, and not checked in the last 90 days."""
    asked = {k for q in open_questions for k in q["establishment_keys"]}
    return [r for r in rows
            if r["establishment_key"] != "__note__" and r["method"] in ELIGIBLE
            and r["bucket"] in ("possible", "excluded") and not r["needs_adjudication"]
            and r["establishment_key"] not in asked and not _recent(_ev(r).get("web_check"))]


def info(rows: list[dict], open_questions: list[dict]) -> dict:
    """For the sub page: whether the check can run here, the records it would check, and the ones already checked."""
    checked = sum(1 for r in rows if r["method"] == "web" or _ev(r).get("web_check"))
    return {"available": W.available() and not is_person(rows), "unchecked": len(candidates(rows, open_questions)),
            "checked": checked}


def groups(rows: list[dict], flags: dict[str, int]) -> list[list[dict]]:
    """One group per OSHA name at a place (name, city, state): red-flagged groups first, then possible ones, then the
    most inspections."""
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        e = _ev(r)
        by[(e.get("name"), e.get("city"), e.get("state"))].append(r)

    def order(g: list[dict]) -> tuple:
        return (not any(flags.get(r["establishment_key"]) for r in g), not any(r["bucket"] == "possible" for r in g),
                -sum(_ev(r).get("inspections") or 0 for r in g))
    return sorted(by.values(), key=order)


def profile_first(sub: dict, project: dict) -> dict | None:
    """The sub's company profile, looked up first if it has none (one search), as "Look up this company" does: the
    locations it lists become a question of their own, and its website lets compare() settle most records in code."""
    from ssi.llm import profile as P
    if sub.get("profile_status") == "done":
        return P.load(sub.get("profile_id"))
    prof = P.for_sub(sub, project, force=True)
    if prof:
        if P.m3_check_enabled():  # as the lookup button: an M3 match it sends back waits for the adjudicator
            ADJ.check_m3(sub, prof, P.build)
        ADJ.apply_profile(sub, prof)
    return prof


def sub_context(sub: dict, project: dict, profile: dict | None) -> dict:
    from ssi.llm import profile as P
    return {"name": sub["entered_name"], "city": sub.get("entered_city"),
            "state": sub.get("entered_state") or project.get("state"),
            "profile_name": (profile or {}).get("name") if (profile or {}).get("found") else None,
            "domain": P.company_domain(profile)}


def _host(url: str | None) -> str:
    from ssi.llm import profile as P
    return P.domain(url) or "the web"


def _short(quote: str, n: int = 160) -> str:
    return quote if len(quote) <= n else quote[:n].rsplit(" ", 1)[0] + "…"


def rationale(check: dict) -> str:
    found = f"{check['owner']} (“{_short(check['quote'])}”, {_host(check['url'])})" if check.get("quote") else None
    if check["verdict"] == "unsure":
        return f"Web search: {check['why']}" + (f"; found {found}" if found else "")
    return f"Web search: {found}; {check['why']}. Waiting for your answer"


def _relation(check: dict) -> str:
    return {"own": "", "parent": f", part of {check.get('parent') or 'its parent'}",
            "affiliate": ", an affiliate"}.get(check.get("relation") or "", "")


def web_questions(sub: dict, items: list[tuple[str, dict, dict]], flags: dict[str, int]) -> list[dict]:
    """At most two questions from one press: records the web ties to the sub (suggestion: same) and records it ties
    to other companies (suggestion: different). `items`: (key, establishment, check). Each names its records, who
    the pages say they belong to, and the pages, keyed to their records."""
    out = []
    for verdict in ("same", "different"):
        its = sorted((x for x in items if x[2]["verdict"] == verdict), key=lambda x: -(x[1].get("insp_n") or 0))
        if not its:
            continue
        named = []
        for k, e, ck in its[:ADJ.PROFILE_LIST_LIMIT]:
            n = e.get("insp_n") or 0
            extra = [f"{n} inspection{'s' if n != 1 else ''}"] + (["red flags"] if flags.get(k) else [])
            site = f", {ck['website']}" if ck.get("website") else ""
            named.append(f"'{e['clean_name']}' at {e.get('address') or 'no address'}, {e.get('city') or ''} "
                         f"{e.get('state') or ''} ({', '.join(extra)}): {ck['owner']}{site}{_relation(ck)}")
        more = f"; and {len(its) - ADJ.PROFILE_LIST_LIMIT} more" if len(its) > ADJ.PROFILE_LIST_LIMIT else ""
        n_red = sum(1 for k, _, _ in its if flags.get(k))
        several = len(its) > 1
        red = (f" {n_red} of them include serious red flags." if n_red > 1 else
               " One of them includes serious red flags." if n_red == 1 and several else
               " It includes serious red flags." if n_red else "")
        if verdict == "same":
            lead = (f"Web pages tie {'these OSHA records' if several else 'this OSHA record'} to your sub's company"
                    f"{' or its affiliates' if any(ck.get('relation') in ('parent', 'affiliate') for *_, ck in its) else ''}: ")
        else:
            lead = f"Web pages tie {'these OSHA records' if several else 'this OSHA record'} to another company: "
        text = (lead + "; ".join(named) + more + "." + red
                + (f" Are these the same company as your sub '{sub['entered_name']}'? If only some are, answer each "
                   "record below." if several else f" Is this the same company as your sub '{sub['entered_name']}'?"))
        sources: dict[tuple, dict] = {}
        for k, _, ck in its:
            s = sources.setdefault((ck["url"], ck["quote"]), {"url": ck["url"], "title": ck.get("title"),
                                                              "quote": ck["quote"], "owner": ck["owner"], "keys": []})
            s["keys"].append(k)
        quotes = list(dict.fromkeys(ck["quote"] for *_, ck in its))
        out.append({"text": text, "keys": [k for k, _, _ in its], "suggestion": verdict,
                    "rationale": "From a web search: " + " / ".join(f"“{_short(q)}”" for q in quotes[:2]),
                    "sources": list(sources.values())})
    return out


def check_records(sub: dict, project: dict, profile: dict | None = None,
                  lookup_fn: Callable[[list[dict]], dict] | None = None,
                  compare_fn: Callable[[dict, dict], dict] | None = None) -> dict:
    """One press of the button, under the sub's claim: look up its candidate groups (up to web_check.PER_PRESS new
    searches), compare each with the sub, write what was found and ask the GC. Returns the press's counts:
    {searched, checked_groups, same, different, unsure (records), left (records still to check), limit_reached,
    questions}."""
    lookup_fn = lookup_fn or W.lookup_many
    compare_fn = compare_fn or W.compare
    sub_id = str(sub["sub_id"])
    stats = {"searched": 0, "checked_groups": 0, "same": 0, "different": 0, "unsure": 0, "left": 0,
             "limit_reached": False, "questions": 0}
    with pg.conn() as c:
        rows = c.execute("SELECT * FROM app.sub_match WHERE sub_id = %s", [sub_id]).fetchall()
        open_qs = ADJ._open_questions(c, sub_id)
    if is_person(rows):
        return stats
    cands = candidates(rows, open_qs)
    est = {e["establishment_key"]: e for e in C.establishments([r["establishment_key"] for r in cands])}
    cands = [r for r in cands if r["establishment_key"] in est]  # a record that has left the data can't be looked up
    # a record under a person's name is many people's, and searching it would look a person up: it's marked, so the
    # button doesn't offer it again
    person = [r["establishment_key"] for r in cands if C.is_person_core(est[r["establishment_key"]].get("name_core") or "")]
    if person:
        skipped = json.dumps({"verdict": "skipped", "why": "a person's name: not searched",
                              "at": datetime.now(UTC).isoformat()})
        with pg.conn() as c:
            c.execute("""UPDATE app.sub_match SET evidence = coalesce(evidence, '{}'::jsonb) || jsonb_build_object('web_check', %s::jsonb)
                         WHERE sub_id = %s AND establishment_key = ANY(%s) AND method = ANY(%s)""",
                      [skipped, sub_id, person, list(ELIGIBLE)])
    cands = [r for r in cands if r["establishment_key"] not in person]
    if not cands:
        return stats
    flags = C.red_flag_counts([r["establishment_key"] for r in cands])
    grps = groups(cands, flags)
    reps = [max(g, key=lambda r: est[r["establishment_key"]].get("insp_n") or 0) for g in grps]
    queries = [W.record_query(est[r["establishment_key"]]) for r in reps]
    looked = lookup_fn(queries)
    stats.update(searched=looked["searched"], limit_reached=looked["limit_reached"])
    ctx = sub_context(sub, project, profile)
    todo = []
    for g, q, res in zip(grps, queries, looked["results"]):
        if res is None:
            stats["left"] += len(g)
        else:
            todo.append((g, W.identity(res, q)))
    with ThreadPoolExecutor(max_workers=W.WORKERS) as pool:  # most are settled in code; the rest are short LLM calls
        found = [(g, {**ident, **cmp}) for (g, ident), cmp in
                 zip(todo, pool.map(lambda t: compare_fn(t[1], ctx), todo))]
    stats["checked_groups"] = len(found)
    by = f"web:{W.model()}"
    now = datetime.now(UTC).isoformat()
    items: list[tuple[str, dict, dict]] = []
    with pg.conn() as c:
        for g, ck in found:
            keys = [r["establishment_key"] for r in g]
            mark = json.dumps({"verdict": ck["verdict"], "owner": ck.get("owner"), "website": ck.get("website"),
                               "relation": ck.get("relation"), "url": ck.get("url"), "quote": ck.get("quote"),
                               "why": ck.get("why"), "at": now})
            why = rationale(ck)
            # the guard: a record the GC (or anything else) moved meanwhile isn't touched
            guard = "sub_id = %s AND establishment_key = ANY(%s) AND method = ANY(%s) AND NOT needs_adjudication"
            if ck["verdict"] == "same":
                done = c.execute(f"""UPDATE app.sub_match SET bucket = 'possible', method = 'web', confidence = NULL,
                                            rationale = %s, decided_by = %s, decided_at = now(),
                                            evidence = coalesce(evidence, '{{}}'::jsonb) || jsonb_build_object('web_check', %s::jsonb)
                                     WHERE {guard} RETURNING establishment_key""",
                                 [why, by, mark, sub_id, keys, list(ELIGIBLE)]).fetchall()
            elif ck["verdict"] == "different":
                done = c.execute(f"""UPDATE app.sub_match SET
                                            method = CASE WHEN bucket = 'possible' THEN 'web' ELSE method END,
                                            confidence = CASE WHEN bucket = 'possible' THEN NULL ELSE confidence END,
                                            rationale = CASE WHEN bucket = 'possible' THEN %s ELSE rationale END,
                                            decided_by = CASE WHEN bucket = 'possible' THEN %s ELSE decided_by END,
                                            evidence = coalesce(evidence, '{{}}'::jsonb) || jsonb_build_object('web_check', %s::jsonb)
                                     WHERE {guard} RETURNING establishment_key, method""",
                                 [why, by, mark, sub_id, keys, list(ELIGIBLE)]).fetchall()
            else:
                done = c.execute(f"""UPDATE app.sub_match SET
                                            evidence = coalesce(evidence, '{{}}'::jsonb) || jsonb_build_object('web_check', %s::jsonb)
                                     WHERE {guard} RETURNING establishment_key""",
                                 [mark, sub_id, keys, list(ELIGIBLE)]).fetchall()
            stats[ck["verdict"]] += len(done)
            asked = [r["establishment_key"] for r in done
                     if ck["verdict"] == "same" or (ck["verdict"] == "different" and r["method"] == "web")]
            items += [(k, est[k], ck) for k in asked]
        open_keys = {k for q in ADJ._open_questions(c, sub_id) for k in q["establishment_keys"]}
        stats["questions"] = ADJ._ask(c, sub_id, web_questions(sub, items, flags), open_keys, kind="web")
    return stats
