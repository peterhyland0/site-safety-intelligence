"""Company profiles on the adjudication eval's uncertain cases: what web search adds, and where it should go.

For each distinct search A in eval/adjudication's cached cases (run eval.adjudication.run for the seed first), a
profile is built the way the app builds it (ssi.llm.profile: Claude with web search, every location checked against
the page it quotes) and cached in profiles.jsonl. Then each case's candidate B is graded three ways:

  today      the adjudicators as the app runs them, no profile (answers from eval/adjudication/cache.jsonl)
  question   the app's approach: B at an address the profile lists goes to the GC with "same" suggested (in a
             listed city: "unsure"); anything else is left to the adjudicator as today. The GC decides, so this
             grades the suggestions: same-company records suggested (recall), different ones (misleading)
  context    the profile as one more evidence line in the adjudicator's packet: DeepSeek and Jev decide with it,
             through the app's thresholds, and nothing waits for the GC (red flags aside, as always)

Labels are the silver tax-ID labels (see eval/adjudication/run.py). Searches are OSHA's spellings of A, not what a
GC types. Profiles cost money (Sonnet 5.5 with web search by default, SSI_PROFILE_MODEL to change): --limit runs a
pilot first.

    uv run python -m eval.profile.run --seed 7 --limit 40 [--workers 4]
    uv run python -m eval.profile.run --seed 7 --backend tavily --searches-of claude --limit 0   # Tavily on Claude's searches

--backend tavily builds the profiles with ssi.llm.profile's Tavily backend (one search, the adjudicator LLM reads the
pages) instead of Claude; --searches-of claude takes exactly the searches that already have a Claude profile, so the
two backends are compared on the same companies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from eval.adjudication import run as AR
from ssi import config
from ssi.llm import adjudicator
from ssi.llm import client as llm
from ssi.llm import jev as app_jev
from ssi.llm import profile as P
from ssi.matching import adjudicate as ADJ
from ssi.matching import candidates as C
from ssi.store import warehouse

OUT = Path(__file__).parent
PROFILES = OUT / "profiles.jsonl"
# per million tokens, by model family (tavily: DeepSeek V4.1 Flash reads the pages); per search: Claude's web search
# $10 per 1,000, a basic Tavily search 1 credit at $0.008
PRICES = {"claude-opus": (4.0, 20.0), "claude-sonnet": (2.0, 10.0), "claude-haiku": (1.0, 5.0), "tavily": (0.30, 1.20)}


def price(model: str) -> tuple[float, float]:
    return next((v for k, v in PRICES.items() if model.startswith(k)), (0.0, 0.0))


def search_usd(model: str) -> float:
    return 0.008 if model.startswith("tavily") else 0.01
NOT_LISTED = "A place this list doesn't include is not evidence of a different company: websites list today's sites."


def searches(cases: list[dict], limit: int | None, of: str | None = None) -> list[tuple]:
    """Distinct searches A, in a stable order; a pilot takes half from cases about the same company. `of`: only the
    searches with a cached profile from a model starting with it (e.g. "claude"), the first `limit` of them."""
    by = {}
    for c in cases:
        by.setdefault((c["query_name"], c["query_city"], c["query_state"]), []).append(c)
    keys = sorted(by, key=lambda k: hashlib.md5("|".join(str(x) for x in k).encode()).hexdigest())
    if of:
        done = {tuple(e["search"]) for e in load_profiles().values() if (e.get("model") or "").startswith(of)}
        keys = [k for k in keys if k in done]
        return keys[:limit] if limit else keys
    if not limit:
        return keys
    pos = [k for k in keys if any(c["label"] for c in by[k])]
    neg = [k for k in keys if k not in pos]
    return pos[: limit // 2] + neg[: limit - min(len(pos), limit // 2)]


def context(case: dict) -> dict:
    """What the app's prompt would be told, from the case's packet (the matched records' addresses)."""
    matched_at = []
    for line in case["packet"]["lines"]:
        m = re.match(r"Already matched OSHA record: '.*?' at (.*?); active", line["text"])
        if m:
            matched_at.append(re.sub(r"\s+", " ", m.group(1)).strip(" ,"))
    return {"name": case["query_name"], "city": case["query_city"], "state": case["query_state"], "trade": None,
            "osha_spelling": case["a_name"], "tier": None, "matched_at": matched_at[:5]}


def load_profiles() -> dict[str, dict]:
    if not PROFILES.exists():
        return {}
    return {e["key"]: e for e in map(json.loads, PROFILES.read_text().splitlines()) if e.get("key")}


def build_profiles(cases: list[dict], keys: list[tuple], workers: int, cached_only: bool = False) -> dict[tuple, dict]:
    """{search: checked profile (or None)}; new ones are built and appended to profiles.jsonl (none with cached_only)."""
    first = {}
    for c in cases:
        first.setdefault((c["query_name"], c["query_city"], c["query_state"]), c)
    cache, out, lock = load_profiles(), {}, threading.Lock()
    todo = []
    for k in keys:
        ctx = context(first[k])
        pk = P.profile_key(ctx, P.model())
        if pk in cache:
            out[k] = cache[pk]
        else:
            todo.append((k, ctx, pk))
    print(f"{len(keys)} searches: {len(keys) - len(todo)} profiles cached, {0 if cached_only else len(todo)} to build")
    if cached_only:
        return out

    def one(k, ctx, pk):
        t = time.time()
        res = P.research(ctx)
        prof = P.check(res["report"], res["texts"], res["titles"]) if not res["error"] else None
        entry = {"key": pk, "search": list(k), "ctx": ctx, "profile": prof, "error": res["error"], "searches": res["searches"],
                 "usage": res["usage"], "model": res["model"], "seconds": round(time.time() - t, 1)}
        with lock, PROFILES.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return k, entry

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, *t) for t in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                k, entry = fut.result()
                out[k] = entry
            except Exception as e:  # noqa: BLE001 - not cached: the next run tries again
                print(f"  profile failed: {type(e).__name__}: {str(e)[:160]}")
            if i % 5 == 0 or i == len(futures):
                print(f"  {i}/{len(futures)} profiles built")
    return out


def profile_line(prof: dict) -> str:
    """The profile as one evidence line: only the checked locations, never raw page text."""
    locs = []
    for loc in prof["locations"]:
        where = ", ".join(x for x in (loc.get("address"), f"{loc['city']} {loc['state']}", loc.get("zip")) if x)
        locs.append(f"{loc['kind']} at {where}")
    head = f"Web profile of the company (quotes checked against its pages): '{prof['name']}'"
    head += f" ({prof['domain']})" if prof.get("domain") else ""
    head += f", {prof['summary']}" if prof.get("summary") else ""
    return f"{head}; lists: " + "; ".join(locs) + f". {NOT_LISTED}"


def with_profile(packet: dict, prof: dict) -> dict:
    """The packet with the profile as E2 (after the GC's sub), the other lines renumbered."""
    texts = [packet["lines"][0]["text"], profile_line(prof)] + [line["text"] for line in packet["lines"][1:]]
    return {**packet, "lines": [{"id": f"E{i + 1}", "text": t} for i, t in enumerate(texts)]}


def grade_llm(entry: dict | None, packet: dict) -> dict:
    if not entry:
        return {"bucket": "possible", "missing": True}
    ans = adjudicator.checked(entry["response"]["raw"], packet)
    return {"bucket": "possible" if ans.get("rejected") else ADJ.ai_bucket(ans), "rejected": bool(ans.get("rejected")),
            "note": f"{ans['decision']} {ans['confidence']:.2f}: {ans.get('rationale', '')}"}


def grade_jev(entry: dict | None, same_state: bool) -> dict:
    if not entry:
        return {"bucket": "possible", "missing": True}
    p = app_jev.p_same(entry["response"])
    return {"bucket": ADJ.ai_bucket(app_jev.decision(p, same_state)), "note": f"P(same) {p:.2f}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--limit", type=int, default=40, help="distinct searches (0 = all; each one is a profile to pay for)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cached-only", action="store_true", help="grade only searches with a cached profile: no new Claude calls")
    ap.add_argument("--backend", choices=["claude", "tavily"], default="claude", help="how profiles are built (ssi.llm.profile)")
    ap.add_argument("--searches-of", metavar="MODEL", help="only searches already profiled by this model family, e.g. claude")
    a = ap.parse_args()
    os.environ["SSI_PROFILE_BACKEND"] = a.backend
    config.TRACING = False
    cases_file = AR.OUT / f".cases-{a.seed}.json"
    if not cases_file.exists():
        raise SystemExit(f"Run `uv run python -m eval.adjudication.run --seed {a.seed}` first (it caches the cases).")
    cases = json.loads(cases_file.read_text())["cases"]
    keys = searches(cases, a.limit or None, a.searches_of)
    profiles = build_profiles(cases, keys, a.workers, a.cached_only)
    keys = [k for k in keys if k in profiles] if a.cached_only else keys
    cases = [c for c in cases if (c["query_name"], c["query_city"], c["query_state"]) in profiles]
    warehouse.open_warehouse()
    est = {e["establishment_key"]: e for e in C.establishments([c["b_key"] for c in cases])}

    # answers: today's from the adjudication cache; with the profile, new calls (cached there too)
    AR.PROVIDERS["llm"] = llm.get("adjudicator")
    llm_model, jev_model = AR.PROVIDERS["llm"].model, app_jev.model()
    answers, lock, http = AR.load_cache(), threading.Lock(), app_jev.client()
    jobs = []
    for c in cases:
        prof = (profiles[(c["query_name"], c["query_city"], c["query_state"])] or {}).get("profile")
        c["prof"] = prof if prof and prof.get("found") and prof.get("locations") else None
        c["packet_p"] = with_profile(c["packet"], c["prof"]) if c["prof"] else c["packet"]
        for name, m, packet in (("llm", llm_model, c["packet"]), ("llm", llm_model, c["packet_p"]),
                                ("jev", jev_model, c["packet"]), ("jev", jev_model, c["packet_p"])):
            k = AR.cache_key(name, m, packet)
            if k not in answers and (k, name) not in {(j[0], j[1]) for j in jobs}:
                jobs.append((k, name, packet))
    print(f"{len(jobs)} adjudicator calls to make")

    def call(k, name, packet):
        resp = AR.ask_llm(packet, "llm") if name == "llm" else app_jev.ask(packet, http)
        entry = {"key": k, "adjudicator": name, "model": llm_model if name == "llm" else jev_model, "response": resp}
        with lock:
            answers[k] = entry
            with AR.CACHE.open("a") as f:
                f.write(json.dumps(entry) + "\n")

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for fut in as_completed([pool.submit(call, *j) for j in jobs]):
            try:
                fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  call failed: {type(e).__name__}: {str(e)[:160]}")
    http.close()

    rows = []
    for c in cases:
        same_state = c["query_state"] == c["b_state"]
        listed = ADJ.listed_records(c["prof"], [est[c["b_key"]]]).get(c["b_key"]) if c["prof"] and c["b_key"] in est else None
        jev_today = grade_jev(answers.get(AR.cache_key("jev", jev_model, c["packet"])), same_state)
        rows.append({
            "label": c["label"], "other_state": not same_state, "found": bool(c["prof"]),
            "a": f"{c['a_name']} ({c['query_city']}, {c['query_state']})", "b": f"{c['b_name']} ({c['b_city']}, {c['b_state']})",
            "listed": listed["level"] if listed else None,
            "llm today": grade_llm(answers.get(AR.cache_key("llm", llm_model, c["packet"])), c["packet"]),
            "llm context": grade_llm(answers.get(AR.cache_key("llm", llm_model, c["packet_p"])), c["packet_p"]),
            "jev today": jev_today,
            "jev context": grade_jev(answers.get(AR.cache_key("jev", jev_model, c["packet_p"])), same_state),
            # the app today: listed records go to the GC (address: "same" suggested), the rest to Jev as before
            "question": ({"bucket": "asked same"} if listed and listed["level"] == "address" else
                         {"bucket": "asked unsure"} if listed else jev_today),
        })
    report(a, rows, profiles, keys)


def report(a, rows: list[dict], profiles: dict, keys: list) -> None:
    built = [profiles[k] for k in keys if profiles.get(k)]
    found = [e for e in built if (e.get("profile") or {}).get("found")]
    usage = {"input": sum(e["usage"]["input_tokens"] for e in built), "output": sum(e["usage"]["output_tokens"] for e in built),
             "search": sum(e.get("searches") or 0 for e in built)}
    cost = sum(e["usage"]["input_tokens"] * price(e["model"])[0] / 1e6 + e["usage"]["output_tokens"] * price(e["model"])[1] / 1e6
               + (e.get("searches") or 0) * search_usd(e["model"]) for e in built)
    models = sorted({e["model"] for e in built})
    secs = sorted(e.get("seconds") or 0 for e in built)
    variants = ["llm today", "llm context", "jev today", "jev context", "question"]

    def tally(v, subset):
        pos = [r for r in subset if r["label"] == 1]
        neg = [r for r in subset if r["label"] == 0]
        b = lambda r: r[v]["bucket"]
        return {
            "same matched": sum(b(r) == "matched" for r in pos), "same asked (same)": sum(b(r) == "asked same" for r in pos),
            "same asked (unsure)": sum(b(r) == "asked unsure" for r in pos),
            "same excluded (wrong)": sum(b(r) == "excluded" for r in pos),
            "different matched (wrong merge)": sum(b(r) == "matched" for r in neg),
            "different asked (same, misleading)": sum(b(r) == "asked same" for r in neg),
            "different asked (unsure)": sum(b(r) == "asked unsure" for r in neg),
            "different excluded": sum(b(r) == "excluded" for r in neg),
            "rejected": sum(bool(r[v].get("rejected")) for r in subset),
        }

    n_pos = sum(r["label"] for r in rows)
    lines = [f"# Company profiles on the adjudication eval (seed {a.seed}{', pilot' if a.limit else ''})", "",
             (f"{len(keys)} distinct searches; {len(built)} profiles built ({len(keys) - len(built)} failed, retried on the "
              f"next run), {len(found)} found the company. {len(rows)} uncertain cases from those searches ({n_pos} same company, {len(rows) - n_pos} "
              f"different); {sum(r['found'] for r in rows)} have a profile, {sum(bool(r['listed']) for r in rows)} "
              f"have B at a listed location ({sum(r['listed'] == 'address' for r in rows)} at an address)."), "",
             (f"Profiles by {', '.join(models)}: {usage['input']:,} input and {usage['output']:,} output tokens, {usage['search']} searches, "
              f"≈ ${cost:.2f} (≈ ${cost / max(len(built), 1):.2f} a profile); median "
              f"{secs[len(secs) // 2] if secs else 0:.0f} s, slowest {secs[-1] if secs else 0:.0f} s."), "",
             "Counts of B records. 'asked' means the GC is asked (the question approach); nothing else waits for the GC.", ""]
    for title, subset in (("All cases", rows), ("Cases with a profile", [r for r in rows if r["found"]])):
        t = {v: tally(v, subset) for v in variants}
        lines += [f"## {title} ({len(subset)})", "", "| | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
        lines += [f"| {m} | " + " | ".join(str(t[v][m]) for v in variants) + " |" for m in t[variants[0]]]
        lines += [""]
    changed = [r for r in rows if r["found"] and (r["llm today"]["bucket"] != r["llm context"]["bucket"]
                                                 or r["jev today"]["bucket"] != r["jev context"]["bucket"])]
    lines += [f"## Where the profile changed an adjudicator's answer ({len(changed)})", "",
              "| Label | Search (A) | Candidate (B) | Listed | DeepSeek today → with profile | Jev today → with profile |",
              "|---|---|---|---|---|---|"]
    lines += [f"| {'same' if r['label'] else 'different'} | {r['a']} | {r['b']} | {r['listed'] or '-'} | "
              f"{r['llm today']['bucket']} → {r['llm context']['bucket']} | {r['jev today']['bucket']} → {r['jev context']['bucket']} |"
              for r in changed[:40]]
    stem = (f"results-seed{a.seed}{'-tavily' if a.backend == 'tavily' else ''}"
            f"{'-pilot' if a.limit else '-cached' if a.cached_only else ''}")
    (OUT / f"{stem}.md").write_text("\n".join(lines) + "\n")
    (OUT / f"{stem}.json").write_text(json.dumps({"rows": rows, "usage": usage, "cost_usd": round(cost, 2)}, indent=1, default=str))
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
