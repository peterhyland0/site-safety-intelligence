"""Adjudicator comparison: the current LLM vs Jev on the records the rules leave "possible".

Reuses the matching eval's silver pairs (eval/matching/run.py): the same tax ID in the injury filings means the
same company; the same name core with different tax IDs means different companies, in the same state or (--cross)
in two states, each tax ID filing in one state only. For each pair the
GC searches A's name, city and state. When the rules leave B uncertain, the pair goes to each adjudicator with
the packet the app would build (adjudicate.build_packet): the search, the records the rules matched (most
inspected first) and B's cluster (the uncertain records under B's name in B's state, B first).

Each answer goes through the app's thresholds (adjudicate.ai_bucket) and is graded on B's label:
  wrong merge      a different company matched: someone else's history attached to the sub (the worst error)
  wrong exclusion  the same company excluded: the sub's own history hidden
  resolved         settled either way, instead of left for the GC
P(same) is also scored as a ranking (AUC) and a probability (Brier). For the LLM it comes from the stated
confidence (same: c, different: 1 - c, unsure or rejected: 0.5); for Jev's choice, P(same) + P(unsure) / 2.
Raw answers are graded, red flags aside: the app asks the GC about a red-flagged cluster whatever the AI says.

Answers are cached in cache.jsonl (by adjudicator, model and packet), so re-runs regrade without new calls, and
the rules' cases in .cases.json (by warehouse build, sample sizes and the matching code), so they skip the
matching too. Doesn't use the app's daily token budget or its adjudication cache, and isn't traced in LangSmith.
Results: results.md / results.json here.

Seed 7 is the development set (results.md), where the app's Jev thresholds were picked. Any other seed is a
held-out check (results-seed<N>.md): it leaves out every pair, and every search, in the seed-7 set.

    uv run python -m eval.adjudication.run [--n 400] [--cross 1600] [--seed 7] [--only llm,jev] [--workers 4]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from eval.adjudication import jev
from eval.matching.run import build_pairs
from ssi import config
from ssi.llm import adjudicator
from ssi.llm import client as llm
from ssi.llm import jev as app_jev
from ssi.matching import adjudicate as ADJ
from ssi.matching import candidates as C
from ssi.matching import run as M
from ssi.store import warehouse

OUT = Path(__file__).parent
CACHE = OUT / "cache.jsonl"
DEV = {"seed": 7, "n": 400, "cross": 1600}  # the development set: results.md
VARIANTS = ["rules only", "llm", "jev-choice", "jev-tuned", "jev-noul"]
SWEEP = [0.95, 0.9, 0.85, 0.8, 0.7, 0.6]


def uncertain_cases(pairs: list[dict]) -> tuple[list[dict], dict]:
    """The pairs whose B the rules leave uncertain, each with its packet. Also counts B's rule outcome by pair
    type, with the rule that matched it."""
    cases, outcomes = [], {}
    for p in pairs:
        res = M.match(p["query_name"], p["query_city"], p["query_state"], None)
        q = res["query"]
        by_key = {x["row"]["establishment_key"]: x for x in res["decisions"]}
        b = by_key.get(p["b_key"])
        bucket = b["decision"].bucket if b and b["decision"] else "not_found"
        kind = outcomes.setdefault(p["kind"], {})
        kind[bucket] = kind.get(bucket, 0) + 1
        if bucket == M.MATCHED:
            kind[f"matched by {b['decision'].rule_id}"] = kind.get(f"matched by {b['decision'].rule_id}", 0) + 1
        if bucket != M.UNCERTAIN:
            continue
        matched = sorted((x for x in res["decisions"] if x["decision"] and x["decision"].bucket == M.MATCHED),
                         key=lambda x: -(x["row"]["insp_n"] or 0))[:5]
        name, state = b["row"]["clean_name"], b["row"]["state"]
        others = sorted((x for x in res["decisions"] if x["decision"] and x["decision"].bucket == M.UNCERTAIN
                         and x["row"]["clean_name"] == name and x["row"]["state"] == state and x is not b),
                        key=lambda x: -(x["row"].get("sim") or 0))
        cluster = [b, *others]
        sub = {"entered_name": p["query_name"], "entered_city": p["query_city"], "entered_state": p["query_state"]}
        keys = [x["row"]["establishment_key"] for x in cluster]
        packet = ADJ.build_packet(sub, [_evidence(x, q) for x in matched], [_evidence(x, q) for x in cluster], keys)
        flags = C.red_flag_counts(keys[:5])
        cases.append({**p, "packet": packet, "red_flagged": any(flags.values())})
    return cases, outcomes


def sample(n: int, cross: int, seed: int) -> list[dict]:
    """Silver pairs for a seed. Any seed but DEV's is held out from the DEV set: none of its pairs, and none of its
    searches (A), so no packet repeats. Same-state different companies are scarce (about 800 in all), so a held-out
    sample can have fewer than n of them."""
    if seed == DEV["seed"]:
        return build_pairs(n, seed, cross)
    dev = build_pairs(DEV["n"], DEV["seed"], DEV["cross"])
    seen, searches = {(p["a_key"], p["b_key"]) for p in dev}, {p["a_key"] for p in dev}
    want = {"same": n, "different": n, "other_state": cross}
    out = []
    for p in build_pairs(n + DEV["n"], seed, cross + DEV["cross"]):
        group = "other_state" if p["kind"] == "other_state_different_ein" else "same" if p["label"] else "different"
        if want[group] and (p["a_key"], p["b_key"]) not in seen and p["a_key"] not in searches:
            want[group] -= 1
            out.append(p)
    return out


def load_cases(n: int, cross: int, seed: int) -> tuple[int, list[dict], dict]:
    """(number of pairs, uncertain cases, rule outcomes), from .cases-<seed>.json when the build, sizes and
    matching code are the same as last time."""
    warehouse.open_warehouse()
    code = hashlib.sha256(b"".join(f.read_bytes() for f in sorted(Path(M.__file__).parent.glob("*.py")))).hexdigest()
    key = f"{warehouse.meta()['build_id']}|{seed}|{n}|{cross}|{code[:16]}"
    path = OUT / f".cases-{seed}.json"
    if path.exists():
        saved = json.loads(path.read_text())
        if saved.get("key") == key:
            return saved["pairs"], saved["cases"], saved["outcomes"]
    pairs = sample(n, cross, seed)
    cases, outcomes = uncertain_cases(pairs)
    path.write_text(json.dumps({"key": key, "pairs": len(pairs), "cases": cases, "outcomes": outcomes}, default=str))
    return len(pairs), cases, outcomes


def _evidence(x: dict, q) -> dict:
    """A decision's evidence through JSON, as the app stores it (dates become strings)."""
    return json.loads(json.dumps(M._evidence(x["row"], x["decision"], q), default=str))


def cache_key(name: str, model: str, packet: dict) -> str:
    return hashlib.sha256(f"{name}|{model}|{json.dumps(packet['lines'], sort_keys=True)}".encode()).hexdigest()


def load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    return {e["key"]: e for e in map(json.loads, CACHE.read_text().splitlines()) if e.get("key")}


def ask_llm(packet: dict) -> dict:
    t = time.time()
    raw, usage = llm.get("adjudicator").structured(adjudicator.SYSTEM, adjudicator.user_prompt(packet),
                                                   adjudicator.SCHEMA, max_tokens=1024)
    return {"raw": raw, "seconds": round(time.time() - t, 3),
            "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}}


def collect(cases: list[dict], which: list[str], workers: int) -> tuple[dict[str, dict], dict[str, str], list[str]]:
    """Every (adjudicator, packet) answer, from the cache or a new call. Returns (cache, models, errors)."""
    cache, models, errors = load_cache(), {}, []
    if "llm" in which:
        models["llm"] = llm.get("adjudicator").model
    http = None
    if "jev" in which:
        models["jev"], http = jev.model(), jev.client()
    jobs = {}
    for c in cases:
        for name in which:
            k = cache_key(name, models[name], c["packet"])
            if k not in cache:
                jobs[k] = (name, c["packet"])
    print(f"{len(jobs)} new calls ({sum(1 for n, _ in jobs.values() if n == 'llm')} LLM, "
          f"{sum(1 for n, _ in jobs.values() if n == 'jev')} Jev); the rest cached")
    lock = threading.Lock()

    def call(k: str, name: str, packet: dict) -> None:
        resp = ask_llm(packet) if name == "llm" else jev.ask(packet, http)
        entry = {"key": k, "adjudicator": name, "model": models[name], "response": resp}
        with lock:
            cache[k] = entry
            with CACHE.open("a") as f:
                f.write(json.dumps(entry) + "\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(call, k, *job): job[0] for k, job in jobs.items()}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                fut.result()
            except Exception as e:  # noqa: BLE001 - not cached, so the next run tries again
                errors.append(f"{futures[fut]}: {type(e).__name__}: {str(e)[:160]}")
            if i % 25 == 0 or i == len(futures):
                print(f"  {i}/{len(futures)} calls done, {len(errors)} failed")
    if http:
        http.close()
    return cache, models, errors


def predictions(case: dict, cache: dict[str, dict], models: dict[str, str]) -> dict[str, dict]:
    """{variant: {bucket, p_same, seconds, tokens, note}} for one case; a missing answer stays possible."""
    out = {"rules only": {"bucket": "possible", "p_same": 0.5}}
    if "llm" in models:
        e = cache.get(cache_key("llm", models["llm"], case["packet"]))
        if not e:
            out["llm"] = {"bucket": "possible", "p_same": 0.5, "missing": True}
        else:
            r = e["response"]
            ans = adjudicator.checked(r["raw"], case["packet"])  # checks run at grading, like the app's cache
            p = 0.5 if ans.get("rejected") or ans["decision"] == "unsure" else (
                ans["confidence"] if ans["decision"] == "same" else 1 - ans["confidence"])
            out["llm"] = {"bucket": "possible" if ans.get("rejected") else ADJ.ai_bucket(ans), "p_same": p,
                          "rejected": bool(ans.get("rejected")), "seconds": r["seconds"],
                          "tokens": r["usage"]["input_tokens"] + r["usage"]["output_tokens"],
                          "note": f"{ans['decision']} {ans['confidence']:.2f}: {ans.get('rationale', '')}"}
    if "jev" in models:
        e = cache.get(cache_key("jev", models["jev"], case["packet"]))
        for variant, ans in (jev.decisions(e["response"]).items() if e else ()):
            out[variant] = {"bucket": ADJ.ai_bucket(ans), "p_same": ans["p_same"], "seconds": e["response"]["seconds"],
                            "input_tokens": e["response"]["usage"].get("input_tokens") or 0,
                            "note": f"{ans['decision']} {ans['confidence']:.2f} (P(same) {ans['p_same']:.2f})",
                            "served_by": e["response"].get("model")}
        if e:  # the choice's P(same) at the app's Jev thresholds (picked on DEV), stricter in another state
            p = out["jev-choice"]["p_same"]
            ans = app_jev.decision(p, case["query_state"] == case["b_state"])
            out["jev-tuned"] = {**out["jev-choice"], "bucket": ADJ.ai_bucket(ans),
                                "note": f"{ans['decision']} (P(same) {p:.2f})"}
        else:
            out |= {v: {"bucket": "possible", "p_same": 0.5, "missing": True}
                    for v in ("jev-choice", "jev-tuned", "jev-noul")}
    return out


def auc(scores: list[tuple[float, int]]) -> float | None:
    pos = [s for s, y in scores if y == 1]
    neg = [s for s, y in scores if y == 0]
    if not pos or not neg:
        return None
    return sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg) / (len(pos) * len(neg))


def metrics(rows: list[dict]) -> dict:
    """rows: {label, bucket, p_same, ...} for one adjudicator."""
    pos = [r for r in rows if r["label"] == 1]
    neg = [r for r in rows if r["label"] == 0]
    right_match = sum(r["bucket"] == "matched" for r in pos)
    wrong_merge = sum(r["bucket"] == "matched" for r in neg)
    right_excl = sum(r["bucket"] == "excluded" for r in neg)
    wrong_excl = sum(r["bucket"] == "excluded" for r in pos)
    secs = sorted(r["seconds"] for r in rows if r.get("seconds") is not None)
    a = auc([(r["p_same"], r["label"]) for r in rows])
    return {
        "wrong_merges": wrong_merge, "wrong_exclusions": wrong_excl,
        "same_matched": right_match, "different_excluded": right_excl,
        "resolved": round(sum(r["bucket"] != "possible" for r in rows) / len(rows), 3) if rows else None,
        "match_precision": round(right_match / (right_match + wrong_merge), 3) if right_match + wrong_merge else None,
        "exclude_precision": round(right_excl / (right_excl + wrong_excl), 3) if right_excl + wrong_excl else None,
        "auc": round(a, 3) if a is not None else None,
        "brier": round(sum((r["p_same"] - r["label"]) ** 2 for r in rows) / len(rows), 3) if rows else None,
        "rejected": sum(bool(r.get("rejected")) for r in rows),
        "missing": sum(bool(r.get("missing")) for r in rows),
        "median_s": round(statistics.median(secs), 2) if secs else None,
        "p90_s": round(secs[int(0.9 * (len(secs) - 1))], 2) if secs else None,
    }


def sweep(rows: list[dict]) -> list[str]:
    """Matched if P(same) >= t: 'same-company matched / different-company matched' at each t."""
    pos = sum(r["label"] == 1 for r in rows)
    return [f"{sum(r['label'] == 1 and r['p_same'] >= t for r in rows)}/{pos} · "
            f"{sum(r['label'] == 0 and r['p_same'] >= t for r in rows)}" for t in SWEEP]


GROUPS = [("Same company, same state", 1, False), ("Same company, other state", 1, True),
          ("Different company, same state", 0, False), ("Different company, other state", 0, True)]


def by_place(cases: list[dict], variants: list[str]) -> list[tuple[str, int, dict[str, str]]]:
    """'matched · possible · excluded' per variant, by label and whether B is in A's state."""
    out = []
    for name, lab, other in GROUPS:
        group = [c for c in cases if c["label"] == lab and (c["query_state"] != c["b_state"]) == other]
        if group:
            out.append((name, len(group), {v: " · ".join(str(sum(c["pred"][v]["bucket"] == b for c in group))
                                                         for b in ("matched", "possible", "excluded")) for v in variants}))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="silver pairs per class (only the uncertain ones are adjudicated)")
    ap.add_argument("--cross", type=int, default=1600,
                    help="cross-state different-company pairs (about 6%% reach the adjudicator; 0 skips them)")
    ap.add_argument("--only", default="llm,jev", help="adjudicators to run: llm, jev, or both")
    ap.add_argument("--workers", type=int, default=4, help="concurrent calls")
    ap.add_argument("--seed", type=int, default=DEV["seed"],
                    help=f"sample seed; {DEV['seed']} is the development set, any other is held out from it")
    a = ap.parse_args()
    t0 = time.time()
    config.TRACING = False  # hundreds of one-shot calls would use up the LangSmith plan's monthly traces
    which = []
    for name in a.only.split(","):
        ok = llm.available("adjudicator") if name == "llm" else jev.available() if name == "jev" else None
        if ok is None:
            raise SystemExit(f"Unknown adjudicator {name!r} (llm, jev)")
        if ok:
            which.append(name)
        else:
            print(f"Skipping {name}: " + ("no adjudicator LLM configured (see ssi/llm/client.py)" if name == "llm"
                                          else "JEV_API_KEY is not set"))
    n_pairs, cases, outcomes = load_cases(a.n, a.cross, a.seed)
    held_out = a.seed != DEV["seed"]
    stem = "results" if not held_out else f"results-seed{a.seed}"
    n_pos = sum(c["label"] for c in cases)
    print(f"{n_pairs} silver pairs; the rules leave {len(cases)} uncertain ({n_pos} same company, "
          f"{len(cases) - n_pos} different); {len({json.dumps(c['packet']['lines']) for c in cases})} distinct packets")
    cache, models, errors = collect(cases, which, a.workers) if which else ({}, {}, [])
    for c in cases:
        c["pred"] = predictions(c, cache, models)
    variants = [v for v in VARIANTS if all(v in c["pred"] for c in cases)]
    rows = {v: [{"label": c["label"], **c["pred"][v]} for c in cases] for v in variants}
    m = {v: metrics(rows[v]) for v in variants}
    served = sorted({c["pred"][v].get("served_by") for c in cases for v in variants if c["pred"][v].get("served_by")})
    cost = {"llm_tokens": sum(r.get("tokens") or 0 for r in rows.get("llm", [])),
            "jev_input_tokens": sum(r.get("input_tokens") or 0 for r in rows.get("jev-noul", []))}
    secs = round(time.time() - t0)
    (OUT / f"{stem}.json").write_text(json.dumps({
        "seed": a.seed, "held_out": held_out, "jev_thresholds": {"match": app_jev.MATCH_AT, **app_jev.EXCLUDE_AT},
        "pairs": n_pairs, "rule_outcomes": outcomes, "uncertain": len(cases), "uncertain_same": n_pos,
        "red_flagged": sum(c["red_flagged"] for c in cases), "models": models, "jev_served_by": served,
        "metrics": m, "sweep": {v: dict(zip(map(str, SWEEP), sweep(rows[v]))) for v in variants
                                if v not in ("rules only", "jev-tuned")},
        "by_place": {name: {"n": n, **cells} for name, n, cells in by_place(cases, variants)},
        "tokens": cost, "errors": errors, "seconds": secs,
        "cases": [{"a": c["a_name"], "a_place": f"{c['query_city']}, {c['query_state']}", "b": c["b_name"],
                   "b_place": f"{c['b_city']}, {c['b_state']}", "label": c["label"], "red_flagged": c["red_flagged"],
                   **{v: {"bucket": c["pred"][v]["bucket"], "p_same": round(c["pred"][v]["p_same"], 3)}
                      for v in variants if v != "rules only"}} for c in cases]}, indent=2))

    label = {"llm": f"LLM ({llm.model_label('adjudicator')})" if "llm" in models else "LLM",
             "jev-choice": "Jev choice", "jev-tuned": "Jev choice, tuned", "jev-noul": "Jev yes/no",
             "rules only": "Rules only"}
    head = "| | " + " | ".join(label[v] for v in variants) + " |"
    rule = "|---|" + "---|" * len(variants)

    def row(name: str, key: str) -> str:
        return f"| {name} | " + " | ".join(str(m[v][key]) for v in variants) + " |"

    n_neg = len(cases) - n_pos
    lines = ["# Adjudicator comparison (silver labels from ITA EINs)", "",
             (f"Seed {a.seed}: held out from the seed-{DEV['seed']} development set (no shared pair or search), "
              f"so Jev's tuned thresholds were fixed before this sample was drawn." if held_out else
              f"Seed {a.seed}: the development set, where the app's Jev thresholds were picked."), "",
             (f"{n_pairs} silver pairs; the rules leave **{len(cases)}** uncertain ({n_pos} same company, {n_neg} "
              f"different). Those go to each adjudicator with the packet the app would build. "
              f"{sum(c['red_flagged'] for c in cases)} carry red flags (the app asks the GC about those whatever the AI "
              f"says). {secs} s."), "",
             f"Models: {', '.join(f'{k}: `{v}`' for k, v in models.items()) or 'none'}"
             + (f" (Jev served by {', '.join(served)})" if served else "") + ".", "",
             head, rule,
             row(f"Wrong merges (of {n_neg} different)", "wrong_merges"),
             row(f"Wrong exclusions (of {n_pos} same)", "wrong_exclusions"),
             row(f"Same company matched (of {n_pos})", "same_matched"),
             row(f"Different company excluded (of {n_neg})", "different_excluded"),
             row("Resolved (share not left possible)", "resolved"),
             row("Precision of matches", "match_precision"),
             row("Precision of exclusions", "exclude_precision"),
             row("AUC of P(same)", "auc"),
             row("Brier score of P(same) (lower is better)", "brier"),
             row("Answers rejected by validation", "rejected"),
             row("Answers missing (call failed)", "missing"),
             row("Median seconds per packet", "median_s"),
             row("p90 seconds per packet", "p90_s"), "",
             (f"Tokens: LLM {cost['llm_tokens']:,} (in + out); Jev {cost['jev_input_tokens']:,} input "
              f"(≈ ${cost['jev_input_tokens'] * jev.USD_PER_M_INPUT / 1e6:.4f} at list price; output is free)."), "",
             ("Thresholds are the app's (`adjudicate.ai_bucket`): same ≥ 0.85 → matched, different ≥ 0.80 → excluded. "
              f"\"Jev choice, tuned\" is what the app does with Jev (`ssi.llm.jev.decision`): the choice's P(same), "
              f"excluded at ≤ {app_jev.EXCLUDE_AT['same_state']} in the sub's state and ≤ "
              f"{app_jev.EXCLUDE_AT['other_state']} in another, matched at ≥ {app_jev.MATCH_AT}."), ""]
    kinds = {"same_name_other_address": "Same company, same name", "different_name": "Same company, other name",
             "same_name_different_ein": "Different company, same name, same state",
             "same_core_different_ein": "Different company, same name core, same state",
             "other_state_different_ein": "Different company, same name core, other state"}
    lines += ["## What the rules do with each pair type", "",
              "Only the uncertain ones reach the adjudicator.", "",
              "| Pairs | matched | uncertain | excluded | not found | matched by rule |", "|---|---|---|---|---|---|"]
    for kind, name in kinds.items():
        o = outcomes.get(kind)
        if o:
            by_rule = ", ".join(f"{k.removeprefix('matched by ')} {v}" for k, v in sorted(o.items()) if k.startswith("matched by "))
            lines.append(f"| {name} | {o.get('matched', 0)} | {o.get('uncertain', 0)} | {o.get('excluded', 0)} | "
                         f"{o.get('not_found', 0)} | {by_rule} |")
    lines += [""]
    swept = [v for v in variants if v != "rules only"]
    if swept:
        lines += ["## By label and place", "",
                  ("Outcomes as matched · possible · excluded. The other-state different companies are two local firms "
                   "(each tax ID files in one state), so a national firm's own namesakes aren't among them."),
                  "", "| Pairs | n | " + " | ".join(label[v] for v in swept) + " |", "|---|---|" + "---|" * len(swept)]
        lines += [f"| {name} | {n} | " + " | ".join(cells[v] for v in swept) + " |"
                  for name, n, cells in by_place(cases, swept)]
        lines += [""]
        lines += ["## Matching at other thresholds", "",
                  "Matched if P(same) ≥ t: same-company records matched / different-company records matched.", "",
                  "| t | " + " | ".join(label[v] for v in swept if v != "jev-tuned") + " |",
                  "|---|" + "---|" * len([v for v in swept if v != "jev-tuned"])]
        cols = {v: sweep(rows[v]) for v in swept}
        lines += [f"| {t} | " + " | ".join(cols[v][i] for v in swept if v != "jev-tuned") + " |"
                  for i, t in enumerate(SWEEP)]
    for v in swept:
        wrong = [c for c in cases if (c["label"] == 0 and c["pred"][v]["bucket"] == "matched")
                 or (c["label"] == 1 and c["pred"][v]["bucket"] == "excluded")]
        lines += ["", f"## {label[v]}: disagreements with the silver label ({len(wrong)}, first 15)", ""]
        if wrong:
            lines += ["| Label | Search (A) | Candidate (B) | Answer |", "|---|---|---|---|"]
            lines += [f"| {'same' if c['label'] else 'different'} | {c['a_name']} ({c['query_city']}, {c['query_state']}) | "
                      f"{c['b_name']} ({c['b_city']}, {c['b_state']}) | {c['pred'][v].get('note', '').replace('|', '/').replace(chr(10), ' ')} |"
                      for c in wrong[:15]]
    if errors:
        lines += ["", f"## Failed calls ({len(errors)}, retried on the next run)", ""] + [f"- {e}" for e in errors[:10]]
    lines += ["", ("Labels are silver: big firms file under several tax IDs and sibling companies sometimes share one, "
                   "so some \"disagreements\" are label errors. Read them before trusting a small difference.")]
    (OUT / f"{stem}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:22]))


if __name__ == "__main__":
    main()
