"""The web check (ssi/llm/web_check.py) on the 43 records Clark Construction Group's lookup returned, each checked by
hand on the web (gold.jsonl: 26 Clark's own, 3 likely Clark's, 14 other companies; the evidence for each is noted).

As the app does, records are grouped by OSHA name at a place, and each group gets one Tavily search and the identify
call; the result is compared with the sub using Clark's company profile (one more search). The identify answers are
cached in lookups.jsonl (profile.json for the profile) and the comparison calls in compares.jsonl, so a re-run costs
nothing. Tavily's raw responses are kept in searches.jsonl, by query, so a change to the page excerpts or the
prompts re-runs without a search too; that file is local (28 MB of page text, not committed).
--max-searches stops before a run would spend more Tavily credits than that.

Reports per record the hand verdict against the check's, and:
  wrong "same"       another company's record suggested as the sub's: the error that matters
  wrong "different"  the sub's own record suggested as another company's
  unsure             nothing settled it (the record stays where it is)
split by where the app has the record (possible / excluded) and what it is (office, job site, subsidiary, other).

    uv run python -m eval.web_check.run [--max-searches 45] [--workers 6]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ssi import config
from ssi.llm import client as llm
from ssi.llm import profile as P
from ssi.llm import web_check as W
from ssi.store import warehouse

OUT = Path(__file__).parent
LOOKUPS, COMPARES, PROFILE = OUT / "lookups.jsonl", OUT / "compares.jsonl", OUT / "profile.json"
SEARCHES = OUT / "searches.jsonl"
SUB = {"entered_name": "Clark Construction Group", "entered_city": "Bethesda", "entered_state": "MD"}
PROFILE_CTX = {"name": "Clark Construction Group", "city": "Bethesda", "state": "MD", "trade": None,
               "osha_spelling": "CLARK CONSTRUCTION GROUP", "tier": "generic",
               "matched_at": ["7500 OLD GEORGETOWN RD, BETHESDA, MD, 20814"]}


P_COLS = "establishment_key, clean_name, display_name, address, city, state, zip5, insp_n"


def resolve(g: dict) -> dict:
    """The warehouse record a hand-checked line is about: its name, city and state, house number (or PO box), zip
    when given, and inspections when two records are left (7900 WEST PARK DR and 7900 WESTPARK DR)."""
    num = re.match(r"(?:PO Box )?(\d+)", g["address"], re.IGNORECASE).group(1)
    rows = warehouse.rows(f"""SELECT {P_COLS} FROM entity.establishment e WHERE clean_name = ? AND state = ? AND city = ?
                              AND regexp_matches(coalesce(address, ''), ?)""",
                          [g["name"], g["state"], g["city"], rf"(^|PO BOX ){num}\b"])
    rows = [r for r in rows if not g["zip"] or r["zip5"] == g["zip"]]
    if len(rows) > 1:
        rows = [r for r in rows if r["insp_n"] == g["inspections"]]
    if len(rows) != 1:
        raise SystemExit(f"record {g['n']} ({g['name']}, {g['address']}) matches {len(rows)} warehouse records")
    return rows[0]


def jsonl(path: Path) -> dict[str, dict]:
    return {e["key"]: e for e in map(json.loads, path.read_text().splitlines())} if path.exists() else {}


def sub_profile() -> dict:
    if PROFILE.exists():
        return json.loads(PROFILE.read_text())
    res = P.research_tavily(PROFILE_CTX)
    prof = P.check(res["report"], res["texts"], res["titles"])
    PROFILE.write_text(json.dumps(prof, indent=1, default=str))
    return prof


def cache_searches() -> dict[str, dict]:
    """profile.tavily_search with Tavily's raw responses kept in searches.jsonl, by query: the web check calls it
    through the profile module, so this serves the eval's every search."""
    cache, lock, search = jsonl(SEARCHES), threading.Lock(), P.tavily_search

    def cached(query: str, http=None, exclude=("osha.gov",)) -> dict:
        key = hashlib.sha256(json.dumps([query, list(exclude)]).encode()).hexdigest()
        if key not in cache:
            resp = search(query, http, exclude=exclude)
            with lock:
                cache[key] = {"key": key, "query": query, "response": resp}
                with SEARCHES.open("a") as f:
                    f.write(json.dumps(cache[key]) + "\n")
        return cache[key]["response"]
    P.tavily_search = cached
    return cache


class CachedCompare:
    """The adjudicator LLM for the comparison calls, with answers cached in compares.jsonl."""

    def __init__(self):
        self.provider, self.cache, self.lock = llm.get("adjudicator"), jsonl(COMPARES), threading.Lock()
        self.model = self.provider.model

    def structured(self, system, user, schema, max_tokens=1024):
        from ssi.llm.base import Usage
        key = hashlib.sha256(f"{self.model}|{system}|{user}".encode()).hexdigest()
        if key in self.cache:
            return self.cache[key]["answer"], Usage(0, 0, 0)
        ans, usage = self.provider.structured(system, user, schema, max_tokens)
        with self.lock:
            self.cache[key] = {"key": key, "user": user, "answer": ans}
            with COMPARES.open("a") as f:
                f.write(json.dumps(self.cache[key]) + "\n")
        return ans, usage


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-searches", type=int, default=45, help="new Tavily searches this run may spend")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    config.TRACING = False
    llm.budget_ok = lambda: True  # no app database: the eval's own caches stand in for the token counters
    llm.record_usage = lambda i, o: None
    warehouse.open_warehouse()
    gold = [json.loads(line) for line in (OUT / "gold.jsonl").read_text().splitlines()]
    for g in gold:
        g["est"] = resolve(g)
    groups: dict[tuple, list[dict]] = {}
    for g in gold:  # as verify.groups: one OSHA name at one place
        e = g["est"]
        groups.setdefault((e["clean_name"], e["city"], e["state"]), []).append(g)
    m = W.model()
    cache, searched = jsonl(LOOKUPS), cache_searches()
    todo = []
    for grp in groups.values():
        rep = max(grp, key=lambda g: g["est"]["insp_n"] or 0)
        q = W.record_query(rep["est"])
        for g in grp:
            g["query"], g["lookup"] = q, W.lookup_key(q, m)
        if rep["lookup"] not in cache and rep["lookup"] not in {k for k, _ in todo}:
            todo.append((rep["lookup"], q))
    spend = sum(1 for _, q in todo if hashlib.sha256(json.dumps([W.search_text(q), list(W.EXCLUDE)]).encode()
                                                  ).hexdigest() not in searched) + (not PROFILE.exists())
    print(f"{len(gold)} records in {len(groups)} groups; {spend} new searches needed")
    if spend > a.max_searches:
        raise SystemExit(f"{spend} new searches needed, more than --max-searches {a.max_searches}")
    prof = sub_profile()
    print(f"the sub's website: {P.company_domain(prof)}")
    lock = threading.Lock()

    def one(key: str, q: dict) -> None:
        res = W.research(q)
        with lock:
            cache[key] = {"key": key, "query": q, "result": res}
            with LOOKUPS.open("a") as f:
                f.write(json.dumps(cache[key], default=str) + "\n")

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for fut in as_completed([pool.submit(one, k, q) for k, q in todo]):
            if fut.exception():  # not cached: the next run tries again
                print(f"  search failed: {type(fut.exception()).__name__}: {str(fut.exception())[:160]}")
    from ssi.matching.verify import sub_context
    ctx = sub_context(SUB, {"state": "MD"}, prof)
    compare = CachedCompare()
    for g in gold:
        hit = cache.get(g["lookup"])
        if not hit:
            g["verdict"], g["why"], g["owner"] = "not searched", "", None
            continue
        ident = W.identity(hit["result"], g["query"])
        out = W.compare(ident, ctx, provider=compare)
        g.update(verdict=out["verdict"], relation=out["relation"], why=out["why"], owner=ident["owner"],
                 url=ident["url"], quote=ident["quote"])
    report(gold)


def truth(g: dict) -> str:
    return "different" if g["label"] == "different" else "same"


def report(gold: list[dict]) -> None:
    def counts(rows: list[dict]) -> dict:
        c = Counter()
        for g in rows:
            c["n"] += 1
            if g["verdict"] == "unsure" or g["verdict"] == "not searched":
                c["unsure"] += 1
            elif g["verdict"] == truth(g):
                c["right"] += 1
            else:
                c["wrong_" + g["verdict"]] += 1
        return c

    def line(label: str, rows: list[dict]) -> str:
        c = counts(rows)
        return f"| {label} | {c['n']} | {c['right']} | {c['wrong_same']} | {c['wrong_different']} | {c['unsure']} |"

    head = ["| Records | n | right | wrong \"same\" | wrong \"different\" | unsure |", "|---|---|---|---|---|---|"]
    lines = ["# Web check on Clark Construction Group's records", "",
             (f"{len(gold)} records Clark's lookup returned, each checked by hand ([gold.jsonl](gold.jsonl)), against "
              f"the web check ([ssi/llm/web_check.py](../../ssi/llm/web_check.py)) with Clark's profile "
              f"({P.company_domain(json.loads(PROFILE.read_text()))}). One search per record group; "
              f"model {W.model()}."), "", *head,
             line("all", gold),
             line("Clark's own (hand)", [g for g in gold if g["label"] == "same"]),
             line("likely Clark's (hand)", [g for g in gold if g["label"] == "likely"]),
             line("other companies (hand)", [g for g in gold if g["label"] == "different"]),
             line("possible in the app", [g for g in gold if g["bucket"] == "possible"]),
             line("excluded in the app", [g for g in gold if g["bucket"] == "excluded"])]
    for kind in ("office", "job site", "subsidiary", "other"):
        lines.append(line(f"kind: {kind}", [g for g in gold if g["kind"] == kind]))
    lines += ["", "\"likely\" records count as Clark's.", "",
              "| # | OSHA name | Place | App | Hand | Check | Company found | Why |", "|---|---|---|---|---|---|---|---|"]
    for g in gold:
        mark = "" if g["verdict"] in ("unsure", "not searched") or g["verdict"] == truth(g) else " ❌"
        lines.append(f"| {g['n']} | {g['name']} | {g['address']}, {g['city'].title()} {g['state']} | {g['bucket']} | "
                     f"{g['label']} | {g['verdict']}{mark} | {g.get('owner') or ''} | {(g.get('why') or '').replace('|', '/')} |")
    (OUT / "results.md").write_text("\n".join(lines) + "\n")
    keep = ("n", "name", "address", "city", "state", "bucket", "label", "kind", "verdict", "relation", "owner", "url",
            "quote", "why")
    (OUT / "results.json").write_text(json.dumps([{k: g.get(k) for k in keep} for g in gold], indent=1, default=str))
    print("\n".join(lines[:15]))


if __name__ == "__main__":
    main()
