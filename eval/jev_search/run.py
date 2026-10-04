"""Jev as the search: a company name, city and state compared with every record in a slice of the warehouse.

The app finds candidates by blocking (ssi/matching/candidates.py: an exact alias, the same name core, or the
query's two rarest words with Jaro-Winkler >= 0.80) and only then runs the rules and the adjudicator. This tests
whether Jev could do the finding: no blocking, one Jev call per (search, record), P(same) for each.

At full size that is one call per record per search (about 216,000), so it runs on a small test set drawn from the
silver-labelled part of the warehouse (records whose injury filings carry one tax ID, as in eval/matching/run.py):
  searches  the A's of --queries silver pairs (eval.matching.run.build_pairs): half have another record under
            the same tax ID, half a lookalike (the same name core under another tax ID)
  pool      the pairs' records, each search's other records under its tax ID and its lookalikes (up to CAP of
            each), and --background random silver records
Each search is compared with every pool record but its own, so every pair has a silver label:
  same company  the same tax ID
  lookalike     another tax ID, the same name core
  other         another tax ID, another name core

Three finders are graded on the same pairs:
  rules         the app's search and rules (ssi.matching.run.match): found if matched or uncertain
  jaro-winkler  the clean names' similarity >= 0.80, the search's own cut-off, here with no blocking
  jev           P(same) (same + unsure / 2, as the app reads it) at the app's cut-offs: kept unless <= 0.20 in the
                search's state or <= 0.06 in another (what Jev wouldn't throw away); above 0.20 anywhere; and
                >= 0.85, what it would match

Searches come one per company (by tax ID), so a national firm with many pairs counts once. Seed 7 is the
adjudication eval's development set, where the app's Jev thresholds were picked; any other seed leaves out its
pairs and searches. With --missed the searches are the ones the app's search fails: a same-company record (B) it
doesn't find or excludes, from a scan of --scan same-company pairs (the rules' scan is kept in .missed-<seed>.json).

Answers are cached in cache.jsonl (by model, question and pair), so a re-run only pays for new pairs. Results:
results.md (seed 7), results-seed<N>.md, results-missed-seed<N>.md and their .json here.

    uv run python -m eval.jev_search.run [--queries 10] [--background 50] [--seed 7] [--workers 8]
    uv run python -m eval.jev_search.run --missed --queries 30 --seed 11

One search of your own, against the same test set, or every record in its state (each record is one call):

    uv run python -m eval.jev_search.run --name "NPL Construction" --city Tulsa --state OK [--pool state]
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

from eval.adjudication.run import DEV, auc, sample
from eval.matching.run import SILVER
from ssi.llm import jev
from ssi.matching import run as M
from ssi.store import warehouse

OUT = Path(__file__).parent
DEV_SEED = DEV["seed"]  # the adjudication eval's development set, where the app's Jev thresholds were picked
CACHE = OUT / "cache.jsonl"
CAP = 10                                # a search's other records, and its lookalikes, in the pool
FOUND_AT = jev.EXCLUDE_AT["same_state"]  # P(same) above this: Jev wouldn't exclude it, even in the sub's state
JW_AT = 0.80                            # candidates.search keeps a token hit at this similarity
RECORD_COLS = "establishment_key, display_name, clean_name, name_core, name_variants, city, state, insp_n"

GUIDANCE = """A general contractor looks up a subcontractor's OSHA inspection history by typing the company's \
name, city and state (E1). OSHA records have no company ID: the employer name is typed per inspection, so the \
same company appears under spelling variants, abbreviations and legal suffixes, and different companies share \
common names. Decide whether the OSHA record (E2) is the SAME company as the one searched for, a DIFFERENT \
company, or UNSURE.

Weigh: exact vs similar names (a typo, an abbreviation, a generic word such as CONSTRUCTION dropped or added); \
the same city or region; the same state. Treat a different legal suffix (INC/LLC) as weak evidence. Names that \
differ by a location or project suffix ("... OF OREGON", "... AT MERIDIAN") are usually sibling companies, not \
the same one. A common name in a different state is usually a different company."""

QUESTIONS = {"decision": {
    "type": "choice",
    "instructions": GUIDANCE,
    "criteria": {
        "same": "The OSHA record is the company the GC searched for.",
        "different": "The OSHA record is a different company.",
        "unsure": "The evidence is too thin to tell.",
    },
}}


def packet(search: dict, record: dict) -> dict:
    """The pair in the app's packet shape (jev.state reads it): the search as E1, the record as E2."""
    other = [v for v in (record.get("name_variants") or []) if v != record["display_name"]][:3]
    also = f" (also typed as {', '.join(f'{v!r}' for v in other)})" if other else ""
    return {"sub": search["name"], "lines": [
        {"id": "E1", "text": f"GC's search: name '{search['name']}', city '{search['city']}', state '{search['state']}'"},
        {"id": "E2", "text": f"OSHA record: name '{record['display_name']}'{also}, city '{record['city']}', "
                             f"state '{record['state']}'"},
    ]}


def cache_key(model: str, p: dict) -> str:
    q = json.dumps(QUESTIONS, sort_keys=True)
    return hashlib.sha256(f"{model}|{q}|{json.dumps(p['lines'], sort_keys=True)}".encode()).hexdigest()


def load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    return {e["key"]: e for e in map(json.loads, CACHE.read_text().splitlines()) if e.get("key")}


def ask_all(packets: list[dict], workers: int) -> tuple[list[dict | None], list[str]]:
    """Jev's response for each packet (None if the call failed), from the cache or a new call; and the errors."""
    model, cache, errors = jev.model(), load_cache(), []
    keys = [cache_key(model, p) for p in packets]
    todo = {k: p for k, p in zip(keys, packets) if k not in cache}
    print(f"{len(packets)} comparisons: {len(todo)} new Jev calls, the rest cached", flush=True)
    lock = threading.Lock()
    http = jev.client()

    def call(k: str, p: dict) -> None:
        entry = {"key": k, "model": model, "response": jev.ask(p, http, QUESTIONS)}
        with lock:
            cache[k] = entry
            with CACHE.open("a") as f:
                f.write(json.dumps(entry) + "\n")

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(call, k, p) for k, p in todo.items()]
            for i, fut in enumerate(as_completed(futures), 1):
                try:
                    fut.result()
                except Exception as e:  # noqa: BLE001 - not cached, so the next run tries again
                    errors.append(f"{type(e).__name__}: {str(e)[:160]}")
                if i % 200 == 0 or i == len(futures):
                    print(f"  {i}/{len(futures)} calls done, {len(errors)} failed", flush=True)
    finally:
        http.close()
    return [cache[k]["response"] if k in cache else None for k in keys], errors


def tax_ids(keys: list[str]) -> dict[str, str]:
    return {r["establishment_key"]: r["ein"] for r in warehouse.rows(
        SILVER + " SELECT establishment_key, ein FROM e WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))", [keys])}


def chosen_pairs(queries: int, seed: int) -> list[dict]:
    """Silver pairs whose A's are the searches: as many with a same-company B as with a lookalike B, one search per
    company (by tax ID), so a national firm with many pairs counts once."""
    pairs = sample(queries, 0, seed)
    eins = tax_ids([p["a_key"] for p in pairs])
    out, companies = [], set()
    for label, want in ((1, max(queries // 2, 1)), (0, queries - max(queries // 2, 1))):
        for p in (p for p in pairs if p["label"] == label):
            if sum(q["label"] == label for q in out) >= want:
                break
            if eins[p["a_key"]] not in companies:
                companies.add(eins[p["a_key"]])
                out.append(p)
    return out


def missed_pairs(queries: int, seed: int, scan: int) -> tuple[list[dict], int]:
    """Same-company silver pairs whose B the app's search doesn't find, or excludes, one per company, up to
    `queries`; and how many pairs were checked to find them. The scan runs the rules on each pair, so the result is
    kept in .missed-<seed>.json while the build, sizes and matching code stay the same."""
    warehouse.open_warehouse()
    code = hashlib.sha256(b"".join(f.read_bytes() for f in sorted(Path(M.__file__).parent.glob("*.py")))).hexdigest()
    key = f"{warehouse.meta()['build_id']}|{seed}|{queries}|{scan}|{code[:16]}"
    path = OUT / f".missed-{seed}.json"
    if path.exists() and (saved := json.loads(path.read_text())).get("key") == key:
        return saved["pairs"], saved["checked"]
    pos = [p for p in sample(scan, 0, seed) if p["label"] == 1]
    eins = tax_ids([p["a_key"] for p in pos])
    out, companies, checked = [], set(), 0
    for p in pos:
        if len(out) >= queries:
            break
        if eins[p["a_key"]] in companies:
            continue
        checked += 1
        if checked % 100 == 0:
            print(f"  rules: {checked} same-company pairs checked, {len(out)} missed", flush=True)
        res = M.match(p["query_name"], p["query_city"], p["query_state"], None)
        b = next((x["decision"].bucket for x in res["decisions"]
                  if x["decision"] and x["row"]["establishment_key"] == p["b_key"]), "not_found")
        if b in (M.EXCLUDED, "not_found"):
            companies.add(eins[p["a_key"]])
            out.append({**p, "rules": b})
    path.write_text(json.dumps({"key": key, "checked": checked, "pairs": out}, default=str))
    return out, checked


def test_set(queries: int, background: int, seed: int, missed: bool = False,
             scan: int = 2000) -> tuple[list[dict], list[dict]]:
    """(searches, pool), both silver records with their tax ID (ein). With `missed`, the searches are ones whose
    same-company record the app's search misses."""
    warehouse.open_warehouse()
    pairs = missed_pairs(queries, seed, scan)[0] if missed else chosen_pairs(queries, seed)
    a_keys = list(dict.fromkeys(p["a_key"] for p in pairs))
    pinned = sorted({p["a_key"] for p in pairs} | {p["b_key"] for p in pairs})
    pool = warehouse.rows(SILVER + f""",
      q AS (SELECT ein, name_core FROM e WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))),
      mates AS (SELECT e.* FROM e JOIN q USING (ein)
                QUALIFY row_number() OVER (PARTITION BY e.ein ORDER BY e.insp_n DESC, e.establishment_key) <= ?),
      looks AS (SELECT e.* FROM e JOIN q ON e.name_core = q.name_core AND e.ein <> q.ein AND q.name_core <> ''
                QUALIFY row_number() OVER (PARTITION BY q.name_core ORDER BY md5(e.establishment_key || ?)) <= ?),
      bg AS (SELECT * FROM e ORDER BY md5(e.establishment_key || ?) LIMIT ?),
      pinned AS (SELECT * FROM e WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))),
      everyone AS (SELECT * FROM pinned UNION ALL SELECT * FROM mates UNION ALL SELECT * FROM looks
                   UNION ALL SELECT * FROM bg)
      SELECT DISTINCT ON (establishment_key) ein, {RECORD_COLS} FROM everyone ORDER BY establishment_key""",
        [a_keys, CAP, str(seed), CAP, f"bg{seed}", background, pinned])
    by_key = {r["establishment_key"]: r for r in pool}
    searches = [{**by_key[k], "name": by_key[k]["display_name"]} for k in a_keys]
    return searches, pool


def state_pool(state: str) -> list[dict]:
    """Every record in a state, silver or not (no tax ID)."""
    warehouse.open_warehouse()
    return warehouse.rows(f"""SELECT NULL AS ein, {RECORD_COLS} FROM entity.establishment
                              WHERE state = upper(?) AND NOT is_placeholder ORDER BY establishment_key""", [state])


def pairs_for(searches: list[dict], pool: list[dict]) -> list[dict]:
    """Every (search, pool record) but a search's own record, labelled by tax ID when both have one."""
    out = []
    for s in searches:
        for r in pool:
            if r["establishment_key"] == s.get("establishment_key"):
                continue
            label = int(r["ein"] == s["ein"]) if s.get("ein") and r.get("ein") else None
            look = bool(s.get("name_core")) and r["name_core"] == s["name_core"]
            out.append({"search": s, "record": r, "label": label,
                        "kind": {1: "same company", 0: "lookalike" if look else "other"}.get(label),
                        "same_state": r["state"] == s["state"], "same_name": r["clean_name"] == s.get("clean_name")})
    return out


def score(pairs: list[dict], workers: int) -> list[str]:
    """Adds jev (P(same), None if the call failed), jw (Jaro-Winkler of the clean names) and rules (the record's
    bucket in the app's search, not_found if the search doesn't reach it) to each pair. Returns Jev's errors."""
    responses, errors = ask_all([packet(p["search"], p["record"]) for p in pairs], workers)
    for p, r in zip(pairs, responses):
        p["jev"] = jev.p_same(r) if r else None
        p["seconds"], p["tokens"] = (r["seconds"], r["usage"].get("input_tokens") or 0) if r else (None, None)
        p["served_by"] = r.get("model") if r else None
    for s in {id(p["search"]): p["search"] for p in pairs}.values():
        mine = [p for p in pairs if p["search"] is s]
        jw = {r["k"]: r["jw"] for r in warehouse.rows(
            """SELECT establishment_key AS k, jaro_winkler_similarity(clean_name, clean_name(?)) AS jw
               FROM entity.establishment WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))""",
            [s["name"], [p["record"]["establishment_key"] for p in mine]])}
        res = M.match(s["name"], s["city"], s["state"], None)
        bucket = {x["row"]["establishment_key"]: x["decision"].bucket for x in res["decisions"] if x["decision"]}
        for p in mine:
            k = p["record"]["establishment_key"]
            p["jw"], p["rules"] = jw.get(k) or 0.0, bucket.get(k, "not_found")
    return errors


def jev_kept(p: dict) -> bool:
    """What the app's Jev thresholds wouldn't exclude: P(same) above 0.20 in the search's state, 0.06 elsewhere."""
    return p["jev"] is not None and p["jev"] > jev.EXCLUDE_AT["same_state" if p["same_state"] else "other_state"]


RULES = "Rules (the app's search)"
JEV_KEPT = "Jev, the app's cut-offs"
FINDERS = {
    RULES: lambda p: p["rules"] in (M.MATCHED, M.UNCERTAIN),
    f"Jaro-Winkler ≥ {JW_AT}": lambda p: p["jw"] >= JW_AT,
    JEV_KEPT: jev_kept,
    f"Jev P(same) > {FOUND_AT}": lambda p: p["jev"] is not None and p["jev"] > FOUND_AT,
    f"Jev P(same) ≥ {jev.MATCH_AT}": lambda p: p["jev"] is not None and p["jev"] >= jev.MATCH_AT,
}


def groups(pairs: list[dict]) -> list[tuple[str, list[dict]]]:
    same = [p for p in pairs if p["label"] == 1]
    out = [("Same company", same)]
    for name_ok, state_ok, label in [(True, True, "same name, same state"), (True, False, "same name, other state"),
                                     (False, True, "other name, same state"), (False, False, "other name, other state")]:
        g = [p for p in same if p["same_name"] == name_ok and p["same_state"] == state_ok]
        if g:
            out.append((f"  {label}", g))
    for bucket, label in (("not_found", "the rules don't find"), (M.EXCLUDED, "the rules exclude")):
        g = [p for p in same if p["rules"] == bucket]
        if g:
            out.append((f"  {label}", g))
    out += [("Lookalike (same name core, other tax ID)", [p for p in pairs if p["kind"] == "lookalike"]),
            ("Other record", [p for p in pairs if p["kind"] == "other"])]
    return [(name, g) for name, g in out if g]


def ranked_first(pairs: list[dict], field: str) -> float | None:
    """The share of same-company records that score above every other company's record in their search (a tie
    counts against): what a search ranked by the field would list before any wrong record."""
    hits = total = 0
    for s in {id(p["search"]): p["search"] for p in pairs}.values():
        mine = [p for p in pairs if p["search"] is s and p[field] is not None]
        wrong = [q[field] for q in mine if q["label"] == 0]
        for p in (p for p in mine if p["label"] == 1):
            total += 1
            hits += all(w < p[field] for w in wrong)
    return round(hits / total, 3) if total else None


def _round(x: float | None) -> float | None:
    return None if x is None else round(x, 3)


def grade(pairs: list[dict]) -> dict:
    out = {"groups": {name: {"n": len(g), **{f: sum(map(fn, g)) for f, fn in FINDERS.items()}}
                      for name, g in groups(pairs)}}
    hard = [p for p in pairs if p["kind"] in ("same company", "lookalike")]
    for field in ("jw", "jev"):
        scored = [p for p in pairs if p[field] is not None]
        out[field] = {
            "auc": _round(auc([(p[field], p["label"]) for p in scored])),
            "auc_vs_lookalikes": _round(auc([(p[field], p["label"]) for p in hard if p[field] is not None])),
            "ranked_first": ranked_first(pairs, field),
        }
    secs = sorted(p["seconds"] for p in pairs if p.get("seconds") is not None)
    out["jev"] |= {"missing": sum(p["jev"] is None for p in pairs),
                   "median_s": round(statistics.median(secs), 3) if secs else None,
                   "tokens": sum(p["tokens"] or 0 for p in pairs)}
    return out


def place(r: dict) -> str:
    return f"{(r['city'] or '?').title()}, {r['state']}"


def scale(g: dict, pairs: list[dict], workers: int) -> str:
    """What one search against every record would cost, from this run's tokens and times."""
    n = warehouse.one("SELECT count(*) AS n FROM entity.establishment WHERE NOT is_placeholder")["n"]
    answered = [p for p in pairs if p["tokens"]]
    if not answered or not g["jev"]["median_s"]:
        return ""
    tokens = n * sum(p["tokens"] for p in answered) / len(answered)
    minutes = n * g["jev"]["median_s"] / workers / 60
    other = [p for p in pairs if p["kind"] == "other" and p["jev"] is not None]
    wrong = sum(map(jev_kept, other))
    noise = (f" Jev kept {wrong} of {len(other):,} unrelated records here, about "
             + (f"{n * wrong / len(other):,.0f}" if wrong else f"fewer than {3 * n / len(other):,.0f} (none seen)")
             + " a search at full size.") if other else ""
    return (f"At full size one search is {n:,} calls: about {tokens / 1e6:.0f}M input tokens "
            f"(≈ ${tokens * jev.USD_PER_M_INPUT / 1e6:.2f} at list price) and {minutes:.0f} minutes at {workers} "
            f"parallel calls and this run's median {g['jev']['median_s']} s a call." + noise)


def report(pairs: list[dict], searches: list[dict], pool: list[dict], g: dict, errors: list[str], args, secs: int,
           checked: int | None = None) -> list[str]:
    names = list(FINDERS)
    n_pairs = len(pairs)
    served = sorted({p["served_by"] for p in pairs if p.get("served_by")})
    held_out = args.seed != DEV_SEED
    lines = ["# Jev as the search (silver labels from ITA EINs)" + (": what the app's search misses" if args.missed else ""), "",
             (f"Seed {args.seed}" + (f", held out from the seed-{DEV_SEED} set where the app's Jev thresholds were "
                                     f"picked (no shared pair or search)" if held_out else
                                     ", the set where the app's Jev thresholds were picked") + ". "
              + (f"Searches whose same-company record the app's search doesn't find or excludes, from {checked:,} "
                 f"same-company pairs checked (one search per company). " if args.missed else "")
              + f"{len(searches)} searches ({len({s['ein'] for s in searches})} companies), each compared with every "
              f"other record in a pool of {len(pool)} ({n_pairs:,} pairs), with no blocking. Jev: `{jev.model()}`"
              + (f" (served by {', '.join(served)})" if served else "") + f". {secs} s."), "",
             ("Found: how many records each finder would show the GC as a possible match. \"Jev, the app's cut-offs\" "
              f"keeps a record unless P(same) ≤ {jev.EXCLUDE_AT['same_state']} in the search's state or ≤ "
              f"{jev.EXCLUDE_AT['other_state']} in another, as the app does."), "",
             "| Pairs | n | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    lines += [f"| {name} | {c['n']} | " + " | ".join(str(c[f]) for f in names) + " |" for name, c in g["groups"].items()]
    lines += ["", "Ranking, Jaro-Winkler against Jev's P(same):", "", "| | Jaro-Winkler | Jev |", "|---|---|---|",
              f"| AUC, same company vs every other record | {g['jw']['auc']} | {g['jev']['auc']} |",
              f"| AUC, same company vs lookalikes | {g['jw']['auc_vs_lookalikes']} | {g['jev']['auc_vs_lookalikes']} |",
              (f"| Same-company records ranked above every other company's record in their search | "
               f"{g['jw']['ranked_first']} | {g['jev']['ranked_first']} |"),
              "", (f"Jev: {g['jev']['tokens']:,} input tokens (≈ ${g['jev']['tokens'] * jev.USD_PER_M_INPUT / 1e6:.4f}), "
                   f"median {g['jev']['median_s']} s a call, {g['jev']['missing']} calls failed."),
              scale(g, pairs, args.workers), ""]

    def row(p: dict) -> str:
        s, r = p["search"], p["record"]
        return (f"| {s['name']} ({place(s)}) | {r['display_name']} ({place(r)}) | "
                f"{p['jev'] if p['jev'] is None else round(p['jev'], 2)} | {p['jw']:.2f} | {p['rules']} |")

    found, rules = FINDERS[JEV_KEPT], FINDERS[RULES]
    same = [p for p in pairs if p["label"] == 1]
    sections = [
        ("Same company, found by Jev and not by the rules", [p for p in same if found(p) and not rules(p)]),
        ("Same company, found by the rules and not by Jev", [p for p in same if rules(p) and not found(p)]),
        ("Same company, found by neither", [p for p in same if not rules(p) and not found(p)]),
        ("Different companies Jev rates highest", sorted((p for p in pairs if p["label"] == 0 and p["jev"] is not None),
                                                         key=lambda p: -p["jev"])[:15]),
    ]
    for title, rows in sections:
        lines += [f"## {title} ({len(rows)}{', first 15' if len(rows) > 15 else ''})", ""]
        if rows:
            lines += ["| Search | Record | Jev P(same) | Jaro-Winkler | Rules |", "|---|---|---|---|---|"]
            lines += [row(p) for p in rows[:15]]
            lines += [""]
    if errors:
        lines += [f"## Failed calls ({len(errors)}, retried on the next run)", ""] + [f"- {e}" for e in errors[:10]] + [""]
    lines += [("Labels are silver: big firms file under several tax IDs and sibling companies sometimes share one, "
               "and a record under another name with the same tax ID can't be found from a name at all. Read the "
               "lists before trusting a small difference.")]
    return lines


def one_search(args) -> None:
    search = {"name": args.name, "city": args.city, "state": args.state.upper()}
    pool = (test_set(args.queries, args.background, args.seed, args.missed, args.scan)[1] if args.pool == "sample"
            else state_pool(args.state))
    if len(pool) > args.max_calls:
        raise SystemExit(f"{len(pool):,} records is more than --max-calls {args.max_calls:,} (one Jev call each)")
    pairs = pairs_for([search], pool)
    errors = score(pairs, args.workers)
    shown = sorted((p for p in pairs if (p["jev"] or 0) > args.show or FINDERS[RULES](p)),
                   key=lambda p: -(p["jev"] or 0))
    print(f"\n{args.name} ({args.city}, {search['state']}) against {len(pool):,} records: {len(shown)} with "
          f"Jev P(same) > {args.show} or found by the rules\n")
    print("| Jev P(same) | Jaro-Winkler | Rules | Record | Inspections |\n|---|---|---|---|---|")
    for p in shown[:args.top]:
        r = p["record"]
        print(f"| {p['jev'] if p['jev'] is None else round(p['jev'], 2)} | {p['jw']:.2f} | {p['rules']} | "
              f"{r['display_name']} ({place(r)}) | {r['insp_n']} |")
    if errors:
        print(f"\n{len(errors)} Jev calls failed (retried on the next run): {errors[0]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=int, default=10, help="searches in the test set")
    ap.add_argument("--background", type=int, default=50, help="random silver records added to the pool")
    ap.add_argument("--seed", type=int, default=DEV_SEED,
                    help=f"sample seed; any but {DEV_SEED} is held out from the set the app's Jev thresholds were picked on")
    ap.add_argument("--missed", action="store_true",
                    help="searches whose same-company record the app's search doesn't find or excludes")
    ap.add_argument("--scan", type=int, default=2000, help="for --missed: same-company pairs to look through")
    ap.add_argument("--workers", type=int, default=8, help="concurrent Jev calls")
    ap.add_argument("--name", help="one search of your own (with --city and --state) instead of the graded test set")
    ap.add_argument("--city")
    ap.add_argument("--state")
    ap.add_argument("--pool", choices=["sample", "state"], default="sample",
                    help="for --name: the test set's pool, or every record in --state")
    ap.add_argument("--max-calls", type=int, default=5000, help="for --name: refuse a pool larger than this")
    ap.add_argument("--show", type=float, default=FOUND_AT, help="for --name: list records with P(same) above this")
    ap.add_argument("--top", type=int, default=30, help="for --name: list at most this many records")
    args = ap.parse_args()
    if not jev.available():
        raise SystemExit("JEV_API_KEY is not set")
    if args.name:
        if not (args.city and args.state):
            raise SystemExit("--name needs --city and --state")
        return one_search(args)
    t = time.time()
    searches, pool = test_set(args.queries, args.background, args.seed, args.missed, args.scan)
    checked = missed_pairs(args.queries, args.seed, args.scan)[1] if args.missed else None  # kept from test_set
    pairs = pairs_for(searches, pool)
    errors = score(pairs, args.workers)
    g = grade(pairs)
    secs = round(time.time() - t)
    lines = report(pairs, searches, pool, g, errors, args, secs, checked)
    stem = "results" + ("-missed" if args.missed else "") + (f"-seed{args.seed}" if args.missed or args.seed != DEV_SEED else "")
    (OUT / f"{stem}.json").write_text(json.dumps({
        "seed": args.seed, "held_out": args.seed != DEV_SEED, "missed": args.missed, "checked": checked,
        "searches": len(searches), "pool": len(pool), "pairs": len(pairs), "model": jev.model(),
        "thresholds": {"jev_found": FOUND_AT, "jev_kept": jev.EXCLUDE_AT, "jev_match": jev.MATCH_AT,
                       "jaro_winkler": JW_AT}, **g,
        "errors": errors, "seconds": secs,
        "same_company": [{"search": f"{p['search']['name']} ({place(p['search'])})",
                          "record": f"{p['record']['display_name']} ({place(p['record'])})",
                          "jev": p["jev"], "jw": round(p["jw"], 3), "rules": p["rules"]}
                         for p in pairs if p["label"] == 1]}, indent=2))
    (OUT / f"{stem}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:26]))


if __name__ == "__main__":
    main()
