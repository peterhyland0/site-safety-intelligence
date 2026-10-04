"""Rule M3 audited on web evidence instead of tax IDs: is a same-name record in another state the same company?

M3 auto-matches a record with the same distinctive name in another state (ssi/matching/rules.py). The silver tax-ID
labels can't grade it: a national firm that files each state's injury reports under its own tax ID looks like two
companies. So each M3 match here is checked against company profiles (ssi.llm.profile, Tavily backend):

  same       A's profile lists a location in B's state, or A's and B's profiles give the same website
  different  both profiles found, with different websites, and A's lists nothing in B's state
  unknown    anything else (no profile, or one that doesn't settle it): a short list isn't evidence

B's profile is only built when A's doesn't settle it. The audit set, confirmed by running the rules (B's rule is M3):
  silver-different  cross-state pairs of different tax IDs, each filing in one state only; one pair per name, all names
  silver-same       cross-state pairs under one tax ID; one pair per name, a deterministic sample
  app               the app's own M3 matches (app.sub_match), checked against the sub's profile

Profiles are cached in profiles.jsonl; --max-searches stops before a run would spend more Tavily credits.

    uv run python -m eval.m3_audit.run [--same 25] [--max-searches 160] [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ssi import config
from ssi.llm import profile as P
from ssi.matching import run as M
from ssi.store import pg, warehouse

OUT = Path(__file__).parent
PROFILES = OUT / "profiles.jsonl"

PAIRS_SQL = """
  WITH linked AS (
    SELECT DISTINCT k.establishment_key, y.ein
    FROM entity.ref_link k JOIN ref_ext.ita_establishment_year y ON y.establishment_id = k.ref_id
    WHERE k.source = 'ita' AND k.method = 'M1' AND y.ein IS NOT NULL),
  one_ein AS (SELECT establishment_key, min(ein) AS ein FROM linked GROUP BY 1 HAVING count(DISTINCT ein) = 1),
  e AS (SELECT o.ein, x.* FROM one_ein o JOIN entity.establishment x USING (establishment_key)
        WHERE NOT x.is_placeholder AND x.city IS NOT NULL AND x.insp_n >= 1 AND NOT coalesce(x.related_only, false)),
  ein_states AS (SELECT ein, count(DISTINCT state) AS n_states FROM e GROUP BY 1),
  pairs AS (
    SELECT a.ein = b.ein AS same_company, a.clean_name, a.display_name AS a_display, a.city AS a_city,
           a.state AS a_state, a.address AS a_address, a.zip5 AS a_zip, a.establishment_key AS a_key,
           b.establishment_key AS b_key, b.display_name AS b_display, b.city AS b_city, b.state AS b_state,
           b.address AS b_address, b.zip5 AS b_zip, a.primary_naics4 = b.primary_naics4 AS same_trade,
           s.state_n, s.establishment_n,
           row_number() OVER (PARTITION BY a.clean_name, a.ein = b.ein
                              ORDER BY md5(a.establishment_key || b.establishment_key)) AS rn
    FROM e a JOIN e b ON a.clean_name = b.clean_name AND a.state <> b.state AND a.establishment_key < b.establishment_key
    JOIN ein_states sa ON sa.ein = a.ein JOIN ein_states sb ON sb.ein = b.ein
    JOIN entity.core_stats s ON s.name_core = a.name_core AND s.tier = 'distinctive'
    WHERE a.name_core <> '' AND (a.ein = b.ein OR (sa.n_states = 1 AND sb.n_states = 1)))
  SELECT * FROM pairs WHERE rn = 1 ORDER BY md5(clean_name)
"""


def silver_pairs(n_same: int) -> list[dict]:
    """One pair per name: every silver-different name, the first n_same silver-same names; only those the rules
    match by M3 (B in A's search, rule M3)."""
    rows = warehouse.rows(PAIRS_SQL)
    out, same_kept = [], 0
    for r in rows:
        if r["same_company"] and same_kept >= n_same:
            continue
        res = M.match(r["a_display"], r["a_city"], r["a_state"], None)
        d = next((x["decision"] for x in res["decisions"] if x["row"]["establishment_key"] == r["b_key"]), None)
        if d and d.rule_id == "M3":
            out.append({**r, "group": "silver-same" if r["same_company"] else "silver-different"})
            same_kept += r["same_company"]
    return out


def app_items() -> list[dict]:
    """The app's M3 matches, one item per (sub, OSHA name, state): OSHA records are often job sites, so the state is
    what a profile can confirm."""
    with pg.conn() as c:
        rows = c.execute("""
          SELECT s.entered_name, s.entered_city, coalesce(s.entered_state, p.state) AS sub_state,
                 m.evidence->>'name' AS osha_name, m.evidence->>'state' AS b_state, min(m.evidence->>'city') AS b_city,
                 min(m.evidence->>'address') AS b_address
          FROM app.sub_match m JOIN app.project_sub s USING (sub_id) JOIN app.project p USING (project_id)
          WHERE m.rule_id = 'M3' GROUP BY 1, 2, 3, 4, 5 ORDER BY 1, 4, 5""").fetchall()
    return [{"group": "app", "clean_name": r["osha_name"], "a_display": r["entered_name"], "a_city": r["entered_city"],
             "a_state": r["sub_state"], "a_address": None, "a_zip": None, "b_display": r["osha_name"],
             "b_city": r["b_city"], "b_state": r["b_state"], "b_address": r["b_address"], "b_zip": None,
             "same_trade": None, "state_n": None, "establishment_n": None} for r in rows]


def ctx(name: str, city: str | None, state: str | None, spelling: str | None, address: str | None, zip5: str | None) -> dict:
    at = ", ".join(x for x in (address, city, state, zip5) if x)
    return {"name": name, "city": city, "state": state, "trade": None, "osha_spelling": spelling, "tier": None,
            "matched_at": [at] if address else []}


def load_profiles() -> dict[str, dict]:
    if not PROFILES.exists():
        return {}
    return {e["key"]: e for e in map(json.loads, PROFILES.read_text().splitlines()) if e.get("key")}


def profiles_for(ctxs: list[dict], cache: dict, workers: int, budget: list[int]) -> dict[str, dict | None]:
    """{profile key: checked profile}; builds the ones not cached while the search budget lasts."""
    lock, out = threading.Lock(), {}
    todo = []
    for c in ctxs:
        k = P.profile_key(c, P.model())
        if k in cache:
            out[k] = cache[k]["profile"]
        elif k not in {t[0] for t in todo}:
            todo.append((k, c))
    if len(todo) > budget[0]:
        raise SystemExit(f"{len(todo)} new searches needed, {budget[0]} left in --max-searches: raise it or lower --same")
    budget[0] -= len(todo)

    def one(k, c):
        res = P.research_tavily(c)
        prof = P.check(res["report"], res["texts"], res["titles"]) if not res["error"] else None
        entry = {"key": k, "ctx": c, "profile": prof, "error": res["error"], "credits": res.get("credits"),
                 "usage": res["usage"], "model": res["model"]}
        with lock:
            cache[k] = entry
            with PROFILES.open("a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return k, prof

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(one, *t) for t in todo]):
            try:
                k, prof = fut.result()
                out[k] = prof
            except Exception as e:  # noqa: BLE001 - not cached: the next run tries again
                print(f"  profile failed: {type(e).__name__}: {str(e)[:160]}")
    return out


def domain(p: dict | None) -> str | None:
    return P.company_domain(p)


def verdict(a: dict | None, b: dict | None, b_state: str) -> tuple[str, str]:
    a_states = {x["state"] for x in (a or {}).get("locations") or []} if (a or {}).get("found") else set()
    if b_state in a_states:
        return "same", f"A's profile lists {b_state}"
    if domain(a) and domain(a) == domain(b):
        return "same", f"same website ({domain(a)})"
    if domain(a) and domain(b):
        return "different", f"websites {domain(a)} and {domain(b)}; A's profile lists {', '.join(sorted(a_states)) or 'no state'}"
    if not (a or {}).get("found"):
        return "unknown", "no profile for A"
    return "unknown", f"A's profile ({domain(a) or 'no website'}) lists {', '.join(sorted(a_states)) or 'no state'}; B not settled"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--same", type=int, default=25, help="silver-same names to sample")
    ap.add_argument("--max-searches", type=int, default=160, help="new Tavily searches this run may spend")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.environ["SSI_PROFILE_BACKEND"] = "tavily"
    config.TRACING = False
    warehouse.open_warehouse()
    items = silver_pairs(a.same) + app_items()
    by_group = {g: sum(i["group"] == g for i in items) for g in ("silver-different", "silver-same", "app")}
    print(f"audit set (confirmed M3): {by_group}")
    cache, budget = load_profiles(), [a.max_searches]

    # round 1: A's profile for every item
    for i in items:
        i["a_ctx"] = ctx(i["a_display"], i["a_city"], i["a_state"], i["clean_name"], i["a_address"], i["a_zip"])
    pa = profiles_for([i["a_ctx"] for i in items], cache, a.workers, budget)
    for i in items:
        i["a_prof"] = pa.get(P.profile_key(i["a_ctx"], P.model()))
    # round 2: B's profile only where A's doesn't settle it
    need_b = [i for i in items if verdict(i["a_prof"], None, i["b_state"])[0] != "same" and domain(i["a_prof"])]
    for i in need_b:
        i["b_ctx"] = ctx(i["b_display"], i["b_city"], i["b_state"], i["clean_name"], i["b_address"], i["b_zip"])
    pb = profiles_for([i["b_ctx"] for i in need_b], cache, a.workers, budget)
    for i in items:
        i["b_prof"] = pb.get(P.profile_key(i["b_ctx"], P.model())) if i.get("b_ctx") else None
        i["verdict"], i["why"] = verdict(i["a_prof"], i["b_prof"], i["b_state"])
    report(items, a.max_searches - budget[0])


def report(items: list[dict], spent: int) -> None:
    groups = ("silver-different", "silver-same", "app")
    lines = ["# Rule M3 on web evidence", "",
             (f"{len(items)} M3 matches (confirmed by running the rules), checked against Tavily company profiles. "
              f"{spent} new searches this run. 'same': A's profile lists B's state, or both profiles give one website; "
              "'different': two profiles with different websites and nothing in B's state; 'unknown': not settled."), "",
             "| Group | n | same | different | unknown |", "|---|---|---|---|---|"]
    for g in groups:
        sub = [i for i in items if i["group"] == g]
        lines.append(f"| {g} | {len(sub)} | " + " | ".join(str(sum(i['verdict'] == v for i in sub))
                                                         for v in ("same", "different", "unknown")) + " |")
    for g in groups:
        sub = [i for i in items if i["group"] == g]
        lines += ["", f"## {g} ({len(sub)})", "", "| Verdict | Name | A | B | Same trade | Core in states | Why |",
                  "|---|---|---|---|---|---|---|"]
        lines += [f"| {i['verdict']} | {i['clean_name']} | {i['a_city']}, {i['a_state']} | {i['b_city']}, {i['b_state']} | "
                  f"{i['same_trade']} | {i['state_n']} | {i['why']} |"
                  for i in sorted(sub, key=lambda i: (i["verdict"], i["clean_name"]))]
    (OUT / "results.md").write_text("\n".join(lines) + "\n")
    keep = ("group", "clean_name", "a_display", "a_city", "a_state", "b_city", "b_state", "same_trade", "state_n",
            "establishment_n", "verdict", "why")
    (OUT / "results.json").write_text(json.dumps([{k: i.get(k) for k in keep} for i in items], indent=1, default=str))
    print("\n".join(lines[:9]))


if __name__ == "__main__":
    main()
