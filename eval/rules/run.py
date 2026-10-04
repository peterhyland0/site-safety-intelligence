"""Each matching rule graded on its own: how often the records it matched, excluded or held back are the sub's.

The matching eval grades 300 pairs overall, and the rules that guard rare cases (people's names, joint ventures,
branches, related facilities) hardly ever come up in it. Here each search runs as a GC's would, and every record
the rules decide is filed under the rule that decided it, so each rule gets its own set:

  pools   where the searches come from. "general" samples every labelled establishment; the others are drawn
          where particular rules act (people's names, shared buildings, joint ventures, branch and OF <STATE>
          names, related facilities, names made only of common words, licence numbers), so those rules get
          enough cases to grade
  labels  silver, from ITA tax IDs as in eval/matching: a record is the same company when it files under the
          searched establishment's EIN. Only records with exactly one EIN are labelled. A "different" label is
          "local" when both EINs file in one state only: two local firms, the most reliable negatives
  caps    at most 3 labelled records per search, rule and bucket, so one national firm can't fill a rule's set

What the share of same-company records means depends on the bucket: for a rule that matches it's precision; for
one that excludes, the share wrongly excluded; for one that holds records back (uncertain), how often the
held-back record was the sub's (near 1, the rule could match; near 0, it could exclude).

Silver labels count a corporate family's divisions as different companies, which is where the sibling and branch
rules act. So the apparent errors (a matched record labelled different, an excluded one labelled same) are written
to review.jsonl for a person to judge: verdict "same", "family", "different" or "unsure". A verdict replaces the
silver label in the "after review" column, with a family counted as the same company, as a GC would treat it.

    uv run python -m eval.rules.run [--general 1500] [--per-pool 300] [--seed 7]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

from ssi.matching import run as M
from ssi.matching.rules import BRANCH_WORDS
from ssi.store import warehouse

OUT = Path(__file__).parent
REVIEW = OUT / "review.jsonl"
PER_SEARCH = 3  # labelled records per search, rule and bucket
REVIEW_PER_RULE = 25  # apparent errors written to review.jsonl per rule and bucket

# Every rule the matcher can decide with (ssi/matching/rules.py, ssi/matching/run.py), in reading order.
RULES = {
    "M1": "Same name, same state (distinctive, or the same city)",
    "M1b": "Same distinctive core, differing only by descriptor words",
    "M2": "At a matched address, the name differs only by spelling",
    "M3": "Same distinctive name in another state",
    "M3u": "M3 held back: a '<word> CONSTRUCTION / ELECTRIC' name under a trade code the sub's records lack",
    "L1": "Linked to the licence number entered",
    "X1": "A different real word in the name",
    "X2": "A different generic name",
    "X3": "A common name with different words",
    "X5": "A person's name in another city or state",
    "S1": "Differs only by OF <STATE> / AT <project>",
    "S2": "The sub's name plus BRANCH / DIVISION / OFFICE",
    "S3": "The sub's name plus a real word, at an address the sub uses",
    "S4": "The sub's name plus a state, or the record's own city",
    "P1": "A person's name without a city to tell people apart",
    "P2": "Another person's name at a matched address",
    "P3": "A company named after a person, in another city or state",
    "J1": "A joint venture at a member's address",
    "U3": "Same family name, a different trade word",
    "U2": "A common name with other words, same city",
    "U4": "The sub's common name in another state",
    "G1": "Initials-only names",
    "N1": "A related facility (not coded construction), by name",
    "R1": "A red-flagged record at an address the company uses",
    "U": "Anything else the rules can't settle",
}
BUCKETS = {
    M.MATCHED: ("Rules that match", "precision: the rest are records of another company counted in the sub's scorecard"),
    M.EXCLUDED: ("Rules that exclude", "the share wrongly excluded: the sub's own records hidden"),
    M.UNCERTAIN: ("Rules that hold records back",
                  "how often the held-back record was the sub's (near 1 the rule could match, near 0 it could exclude)"),
}

LABELLED = """
  WITH linked AS (
    SELECT DISTINCT k.establishment_key, y.ein
    FROM entity.ref_link k JOIN ref_ext.ita_establishment_year y ON y.establishment_id = k.ref_id
    WHERE k.source = 'ita' AND k.method = 'M1' AND y.ein IS NOT NULL),
  one_ein AS (SELECT establishment_key, min(ein) AS ein FROM linked GROUP BY 1 HAVING count(DISTINCT ein) = 1),
  e AS (SELECT o.ein, x.* FROM one_ein o JOIN entity.establishment x USING (establishment_key)
        WHERE NOT x.is_placeholder AND x.city IS NOT NULL AND x.insp_n >= 1)
"""
SHARED_ADDRESS = """(SELECT addr_key FROM entity.establishment WHERE addr_key IS NOT NULL
                     GROUP BY 1 HAVING count(DISTINCT clean_name) BETWEEN 2 AND 10)"""
BRANCHY = "regexp_matches(clean_name, '\\b(" + "|".join(sorted(BRANCH_WORDS)) + ")\\b')"
# name -> (filter on e, licence column or NULL). Searches start from construction records, as a GC's sub would.
POOLS = {
    "general": ("TRUE", "NULL"),
    "person": ("name_core IN (SELECT name_core FROM entity.core_stats WHERE tier = 'person')", "NULL"),
    "shared address": (f"addr_key IN {SHARED_ADDRESS}", "NULL"),
    "joint venture": ("is_jv OR addr_key IN (SELECT addr_key FROM entity.establishment WHERE is_jv AND addr_key IS NOT NULL)",
                      "NULL"),
    "branch or sibling": (("name_core IN (SELECT name_core FROM entity.establishment WHERE name_core <> '' AND "
                           f"(sibling_suffix IS NOT NULL OR {BRANCHY}))"), "NULL"),
    "related facility": ("name_core IN (SELECT name_core FROM entity.establishment WHERE related_only AND name_core <> '')",
                         "NULL"),
    "common name": ("coalesce(name_core, '') = ''", "NULL"),
    "licence": (("establishment_key IN (SELECT establishment_key FROM entity.ref_link "
                 "WHERE source LIKE 'licence:%' AND method = 'M1')"),
                ("(SELECT min(ref_id) FROM entity.ref_link k WHERE k.establishment_key = e.establishment_key "
                 "AND k.source LIKE 'licence:%' AND k.method = 'M1')")),
}


def h(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def searches(general: int, per_pool: int, seed: int) -> list[dict]:
    """The searches, one per establishment (and licence), in pool order: a search drawn by an earlier pool isn't
    run twice."""
    out: dict[tuple, dict] = {}
    for pool, (where, licence) in POOLS.items():
        n = general if pool == "general" else per_pool
        for r in warehouse.rows(LABELLED + f"""
              SELECT establishment_key AS a_key, ein, display_name, city, state, {licence} AS licence FROM e
              WHERE NOT coalesce(related_only, false) AND ({where})
              ORDER BY md5(establishment_key || ? || ?) LIMIT ?""", [pool, str(seed), n]):
            # the pool is in the hash: with one order for all, a targeted pool's first picks are mostly ones
            # the general sample already drew
            out.setdefault((r["a_key"], r["licence"]), {**r, "pool": pool})
    return list(out.values())


def labels() -> tuple[dict[str, str], dict[str, int]]:
    """EIN of every labelled establishment, and the number of states each EIN files in."""
    rows = warehouse.rows(LABELLED + "SELECT establishment_key, ein, state FROM e")
    states: dict[str, set] = defaultdict(set)
    for r in rows:
        states[r["ein"]].add(r["state"])
    return {r["establishment_key"]: r["ein"] for r in rows}, {k: len(v) for k, v in states.items()}


def decisions(s: dict, ein_of: dict[str, str], n_states: dict[str, int]) -> list[dict]:
    """Every record the rules decide for one search, except the searched establishment itself."""
    res = M.match(s["display_name"], s["city"], s["state"], None, s["licence"])
    out = []
    for x in res["decisions"]:
        r, d = x["row"], x["decision"]
        if d is None or r["establishment_key"] == s["a_key"]:
            continue
        b_ein = ein_of.get(r["establishment_key"])
        out.append({
            "pool": s["pool"], "a_key": s["a_key"], "a_ein": s["ein"], "b_key": r["establishment_key"], "rule": d.rule_id,
            "bucket": d.bucket, "label": None if b_ein is None else int(b_ein == s["ein"]),
            "local": b_ein is not None and b_ein != s["ein"] and n_states.get(b_ein) == 1 and n_states.get(s["ein"]) == 1,
            "a": f"{s['display_name']} ({s['city']}, {s['state']})" + (f" licence {s['licence']}" if s["licence"] else ""),
            "b": f"{r['display_name']} ({r.get('address') or ''}, {r.get('city') or ''}, {r.get('state') or ''})"})
    return out


def capped(rows: list[dict], k: int = PER_SEARCH) -> list[dict]:
    """At most k labelled records per search, rule and bucket, picked by a hash of the pair (deterministic)."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["label"] is not None:
            groups[(r["a_key"], r["rule"], r["bucket"])].append(r)
    return [r for g in groups.values() for r in sorted(g, key=lambda r: h(r["a_key"], r["b_key"]))[:k]]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if not n:
        return None
    p, d = k / n, 1 + z * z / n
    c, w = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - w), 2), round(min(1.0, c + w), 2)


def apparent_error(r: dict) -> bool:
    return (r["bucket"] == M.MATCHED and r["label"] == 0) or (r["bucket"] == M.EXCLUDED and r["label"] == 1)


def review_key(r: dict) -> tuple[str, str, str]:
    return r["a_key"], r["b_key"], r["rule"]


def load_review(path: Path = REVIEW) -> dict[tuple, dict]:
    if not path.exists():
        return {}
    entries = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {review_key(e): e for e in entries}


def merge_review(existing: dict[tuple, dict], rows: list[dict], per_rule: int = REVIEW_PER_RULE) -> dict[tuple, dict]:
    """Entries with a verdict are kept whatever happens; unjudged ones only while they're still apparent errors.
    New apparent errors are added, up to per_rule for each rule and bucket."""
    errors = sorted((r for r in rows if apparent_error(r)), key=lambda r: h(r["a_key"], r["b_key"]))
    current = {review_key(r) for r in errors}
    out = {k: e for k, e in existing.items() if e.get("verdict") or k in current}
    have = Counter((e["rule"], e["bucket"]) for e in out.values())
    for r in errors:
        k = review_key(r)
        if k in out or have[(r["rule"], r["bucket"])] >= per_rule:
            continue
        out[k] = {"rule": r["rule"], "bucket": r["bucket"], "silver": "same" if r["label"] else "different",
                  "a": r["a"], "b": r["b"], "a_key": r["a_key"], "b_key": r["b_key"], "verdict": None, "note": ""}
        have[(r["rule"], r["bucket"])] += 1
    return out


def reviewed_label(r: dict, review: dict[tuple, dict]) -> int:
    v = (review.get(review_key(r)) or {}).get("verdict")
    return 1 if v in ("same", "family") else 0 if v == "different" else r["label"]


def summarise(fired: list[dict], graded: list[dict], review: dict[tuple, dict]) -> list[dict]:
    """One row per rule and bucket: how often it fired, and its labelled records' share of same-company ones."""
    out = []
    keys = sorted({(r["rule"], r["bucket"]) for r in fired},
                  key=lambda k: (list(BUCKETS).index(k[1]), list(RULES).index(k[0]) if k[0] in RULES else 99, k[0]))
    for rule, bucket in keys:
        f = [r for r in fired if r["rule"] == rule and r["bucket"] == bucket]
        g = [r for r in graded if r["rule"] == rule and r["bucket"] == bucket]
        same = sum(r["label"] for r in g)
        errs = [r for r in g if apparent_error(r)]
        verdicts = Counter((review.get(review_key(r)) or {}).get("verdict") for r in errs)
        reviewed = sum(n for v, n in verdicts.items() if v)
        after = sum(reviewed_label(r, review) for r in g)
        out.append({
            "rule": rule, "bucket": bucket, "searches": len({r["a_key"] for r in f}), "records": len(f),
            "labelled": len(g), "firms": len({r["a_ein"] for r in g}), "same": same, "different": len(g) - same,
            "different_local": sum(r["local"] for r in g), "share_same": round(same / len(g), 3) if g else None,
            "ci": wilson(same, len(g)), "apparent_errors": len(errs), "reviewed": reviewed,
            "verdicts": {v: n for v, n in verdicts.items() if v},
            "share_same_after_review": round(after / len(g), 3) if g and reviewed else None})
    return out


def report(summary: list[dict], graded: list[dict], review: dict[tuple, dict], meta: dict) -> str:
    pools = ", ".join(f"{p} {n}" for p, n in meta["pools"].items())
    lines = ["# Matching rules, one at a time (silver labels from ITA EINs)", "",
             (f"{meta['searches']} searches ({pools}) on warehouse {meta['build_id']}: {meta['records']:,} records "
              f"decided, {meta['labelled']:,} of them labelled; {meta['graded']:,} graded after the cap of {PER_SEARCH} "
              f"per search, rule and bucket. {meta['seconds']} s."), "",
             ("The targeted pools oversample the cases their rules act on, so each share describes a rule where it "
              "acts, not a GC's usual mix. Intervals are 95% (Wilson) and treat records as independent, which they "
              "aren't when a few firms supply most of a rule's records (firms: distinct tax IDs searched). A rule "
              "with under ~30 labelled records, or a handful of firms, settles little. Silver labels count a "
              "corporate family's divisions as different companies."), ""]
    for bucket, (title, meaning) in BUCKETS.items():
        rows = [s for s in summary if s["bucket"] == bucket]
        if not rows:
            continue
        lines += [f"## {title}", "", f"Share same = {meaning}.", "",
                  "| Rule | What it does | Searches | Records | Labelled (firms) | Same | Different (local) | Share same [95% CI] | After review |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for s in rows:
            ci = f" [{s['ci'][0]}–{s['ci'][1]}]" if s["ci"] else ""
            after = (f"{s['share_same_after_review']} ({s['reviewed']} of {s['apparent_errors']} reviewed)"
                     if s["reviewed"] else (f"0 of {s['apparent_errors']} reviewed" if s["apparent_errors"] else ""))
            lines.append(f"| {s['rule']} | {RULES.get(s['rule'], '')} | {s['searches']} | {s['records']} | {s['labelled']} ({s['firms']}) | "
                         f"{s['same']} | {s['different']} ({s['different_local']}) | "
                         f"{'' if s['share_same'] is None else s['share_same']}{ci} | {after} |")
        lines.append("")
    fired = {s["rule"] for s in summary}
    never = [r for r in RULES if r not in fired]
    if never:
        lines += ["## Rules that never fired in these searches", "",
                  ", ".join(f"{r} ({RULES[r]})" for r in never) + ".", ""]
    lines += ["## Apparent errors (first 8 per rule)", "",
              ("A matched record labelled different, or an excluded one labelled same. Many are a family's divisions "
               "filing under their own EINs; review.jsonl holds them for a verdict."), ""]
    for s in summary:
        errs = sorted((r for r in graded if r["rule"] == s["rule"] and r["bucket"] == s["bucket"] and apparent_error(r)),
                      key=lambda r: h(r["a_key"], r["b_key"]))
        if not errs:
            continue
        lines += [f"### {s['rule']} ({s['bucket']}): {len(errs)}", "", "| Silver | Search (A) | Record (B) | Verdict |",
                  "|---|---|---|---|"]
        lines += [f"| {'same' if r['label'] else 'different'}{' (local firms)' if r['local'] else ''} | {r['a']} | {r['b']} | "
                  f"{(review.get(review_key(r)) or {}).get('verdict') or ''} |" for r in errs[:8]]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--general", type=int, default=1500, help="searches drawn from every labelled establishment")
    ap.add_argument("--per-pool", type=int, default=300, help="searches drawn for each targeted pool")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    t = time.time()
    warehouse.open_warehouse()
    ein_of, n_states = labels()
    ss = searches(a.general, a.per_pool, a.seed)
    fired = []
    for i, s in enumerate(ss, 1):
        fired += decisions(s, ein_of, n_states)
        if i % 250 == 0:
            print(f"  {i}/{len(ss)} searches, {len(fired):,} records", flush=True)
    graded = capped(fired)
    review = merge_review(load_review(), graded)
    REVIEW.write_text("".join(json.dumps(e) + "\n" for e in sorted(review.values(), key=lambda e: (e["rule"], e["a"], e["b"]))))
    summary = summarise(fired, graded, review)
    meta = {"build_id": warehouse.meta()["build_id"], "seed": a.seed, "searches": len(ss),
            "pools": dict(Counter(s["pool"] for s in ss)), "records": len(fired),
            "labelled": sum(r["label"] is not None for r in fired), "graded": len(graded), "seconds": round(time.time() - t)}
    (OUT / "results.json").write_text(json.dumps({"meta": meta, "rules": summary}, indent=1))
    (OUT / "results.md").write_text(report(summary, graded, review, meta) + "\n")
    print(report(summary, graded, review, meta).split("## Apparent errors")[0])


if __name__ == "__main__":
    main()
