"""Matching evaluation on a silver-labelled set built from the data itself.

Labels come from OSHA's injury-tracking filings (ITA 300A), which carry the employer's tax ID (EIN):
  positive = two OSHA establishments that link exactly (name + zip) to ITA rows with the same EIN
  negative = two establishments with the same name core in the same state but different EINs
For each pair we search as the GC would (A's name, city, state) and grade where B lands.

Those searches use OSHA's own spellings, so two more checks cover a GC's typos:
  typos   = a slip in a distinctive OSHA name (one letter dropped, doubled or swapped): the typo should
            match what the correct spelling matches, and never more
  licence = licensed contractors (WA, CA, OR) with no OSHA record whose name is one letter from an OSHA
            name in the same city: at the same address it is the same company (a slip to catch);
            elsewhere it is usually another company (a lookalike to keep out)

Labels are "silver", not gold: big firms file under several EINs and sibling companies sometimes share
one, so a few labels are wrong in both directions. Results: eval/matching/results.md (and LangSmith if a
LANGSMITH_API_KEY is set).

    uv run python -m eval.matching.run [--n 150] [--typos 400]
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from ssi import config
from ssi.matching import run as M
from ssi.matching.rules import norm_city, tokens
from ssi.store import warehouse

OUT = Path(__file__).parent


def build_pairs(n: int, seed: int = 7) -> list[dict]:
    warehouse.open_warehouse()
    base = """
      WITH linked AS (
        SELECT DISTINCT k.establishment_key, y.ein
        FROM entity.ref_link k JOIN ref_ext.ita_establishment_year y ON y.establishment_id = k.ref_id
        WHERE k.source = 'ita' AND k.method = 'M1' AND y.ein IS NOT NULL),
      one_ein AS (SELECT establishment_key, min(ein) AS ein FROM linked GROUP BY 1 HAVING count(DISTINCT ein) = 1),
      e AS (SELECT o.ein, x.* FROM one_ein o JOIN entity.establishment x USING (establishment_key)
            WHERE NOT x.is_placeholder AND x.city IS NOT NULL AND x.insp_n >= 1
              AND NOT coalesce(x.related_only, false))  -- construction records only: related facilities are never auto-matched
    """
    pos = warehouse.rows(base + """
      SELECT a.establishment_key AS a_key, b.establishment_key AS b_key, 1 AS label,
             CASE WHEN a.clean_name = b.clean_name THEN 'same_name_other_address' ELSE 'different_name' END AS kind
      FROM e a JOIN e b ON a.ein = b.ein AND a.establishment_key < b.establishment_key
      ORDER BY md5(a.establishment_key || b.establishment_key || ?) LIMIT ?""", [str(seed), n])
    neg = warehouse.rows(base + """
      SELECT a.establishment_key AS a_key, b.establishment_key AS b_key, 0 AS label,
             CASE WHEN a.clean_name = b.clean_name THEN 'same_name_different_ein' ELSE 'same_core_different_ein' END AS kind
      FROM e a JOIN e b ON a.name_core = b.name_core AND a.state = b.state AND a.ein <> b.ein
                        AND a.establishment_key < b.establishment_key AND a.name_core <> ''
      ORDER BY md5(a.establishment_key || b.establishment_key || ?) LIMIT ?""", [str(seed), n])
    # Deterministic sample: pairs ordered by a hash of their (stable) establishment keys. DuckDB's
    # REPEATABLE reservoir sample isn't repeatable across runs with multiple threads.
    pairs = pos + neg
    keys = list({p["a_key"] for p in pairs} | {p["b_key"] for p in pairs})
    info = {r["establishment_key"]: r for r in warehouse.rows(
        "SELECT establishment_key, display_name, clean_name, city, state FROM entity.establishment "
        "WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))", [keys])}
    for p in pairs:
        a, b = info[p["a_key"]], info[p["b_key"]]
        p.update(query_name=a["display_name"], query_city=a["city"], query_state=a["state"],
                 a_name=a["clean_name"], b_name=b["clean_name"], b_city=b["city"], b_state=b["state"])
    return pairs


def matched_keys(name: str, city: str | None, state: str | None) -> dict[str, str]:
    res = M.match(name, city, state, None)
    return {x["row"]["establishment_key"]: x["row"]["display_name"] for x in res["decisions"] if x["decision"].bucket == M.MATCHED}


def typo_cases(n: int, seed: int = 11) -> list[dict]:
    """A GC-style slip in the longest word of a distinctive OSHA name, past its third letter."""
    rows = warehouse.rows("""
      SELECT e.establishment_key, e.clean_name, e.name_core, e.city, e.state FROM entity.establishment e
      JOIN entity.core_stats s USING (name_core)
      WHERE s.tier = 'distinctive' AND NOT e.is_placeholder AND e.city IS NOT NULL AND NOT coalesce(e.related_only, false)
        AND regexp_matches(e.name_core, '^[A-Z ]+$') AND length(replace(e.name_core, ' ', '')) >= 7
      ORDER BY md5(e.establishment_key) LIMIT ?""", [n])
    rnd = random.Random(seed)
    cases = []
    for e in rows:
        words = tokens(e["name_core"])
        w = max(words, key=len)
        if len(w) < 5:
            continue
        i = rnd.randrange(3, len(w) - 1)
        kind = rnd.choice(["drop", "double", "swap"])
        slip = {"drop": w[:i] + w[i + 1:], "double": w[:i] + w[i] + w[i:], "swap": w[:i] + w[i + 1] + w[i] + w[i + 2:]}[kind]
        if slip != w:
            typo = " ".join(slip if t == w else t for t in tokens(e["clean_name"]))
            cases.append({"correct": e["clean_name"], "typo": typo, "city": e["city"], "state": e["state"]})
    return cases


def grade_typos(cases: list[dict]) -> dict:
    out = {"cases": len(cases), "same_as_correct_spelling": 0, "fewer_matches": 0, "extra_matches": 0, "extra_examples": []}
    for c in cases:
        want = matched_keys(c["correct"], c["city"], c["state"])
        got = matched_keys(c["typo"], c["city"], c["state"])
        if got == want:
            out["same_as_correct_spelling"] += 1
        elif set(got) < set(want):
            out["fewer_matches"] += 1  # left for the AI reviewer and the GC, as any unsure record
        else:
            out["extra_matches"] += 1
            out["extra_examples"].append(f"{c['typo']} ({c['city']}, {c['state']}) matched "
                                         + ", ".join(got[k] for k in set(got) - set(want)))
    return out


def licence_cases() -> list[dict]:
    """Licensed contractors with no OSHA record whose name is one letter (any edit) from exactly one
    distinctive OSHA name with a record in the same city."""
    return warehouse.rows("""
      WITH lic AS (
        SELECT name_core(clean_name) AS core, upper(city) AS city, state, list(DISTINCT addr_key) AS addrs, any_value(name) AS name
        FROM ref_ext.licence WHERE clean_name IS NOT NULL AND city IS NOT NULL GROUP BY 1, 2, 3),
      est AS (
        SELECT e.name_core AS core, upper(e.city) AS city, e.state, list(DISTINCT e.addr_key) AS addrs
        FROM entity.establishment e JOIN entity.core_stats s ON s.name_core = e.name_core
        WHERE s.tier = 'distinctive' AND e.name_core <> '' GROUP BY 1, 2, 3),
      hits AS (
        SELECT l.core AS lic_core, l.name, l.city, l.state, x.core AS osha_core,
               len(list_intersect(l.addrs, x.addrs)) > 0 AS same_address,
               count(*) OVER (PARTITION BY l.core, l.city, l.state) AS n_names
        FROM lic l JOIN est x ON x.city = l.city AND x.state = l.state
         AND abs(length(x.core) - length(l.core)) <= 1 AND damerau_levenshtein(x.core, l.core) = 1
        WHERE l.core <> '' AND l.core NOT IN (SELECT DISTINCT name_core FROM entity.establishment))
      SELECT * FROM hits WHERE n_names = 1 ORDER BY lic_core, city""")


def grade_licence(cases: list[dict]) -> dict:
    out = {"slips_same_address": 0, "slips_matched": 0, "lookalikes_other_address": 0, "lookalikes_matched": 0,
           "lookalike_examples": []}
    for c in cases:
        res = M.match(c["name"], c["city"], c["state"], None)
        hit = any(x["decision"].bucket == M.MATCHED and x["row"]["name_core"] == c["osha_core"]
                  and norm_city(x["row"]["city"]) == norm_city(c["city"]) for x in res["decisions"])
        kind = "slips" if c["same_address"] else "lookalikes"
        out[f"{kind}_{'same_address' if c['same_address'] else 'other_address'}"] += 1
        out[f"{kind}_matched"] += hit
        if hit and not c["same_address"]:
            out["lookalike_examples"].append(f"{c['name']} ({c['city'].title()}, {c['state']}) matched {c['osha_core']}")
    return out


def predict(p: dict) -> dict:
    res = M.match(p["query_name"], p["query_city"], p["query_state"], None)
    for x in res["decisions"]:
        if x["row"]["establishment_key"] == p["b_key"]:
            return {"bucket": x["decision"].bucket, "rule": x["decision"].rule_id}
    return {"bucket": "not_found", "rule": None}


def metrics(rows: list[dict]) -> dict:
    pos = [r for r in rows if r["label"] == 1]
    neg = [r for r in rows if r["label"] == 0]
    tp = sum(r["bucket"] == "matched" for r in pos)
    fp = sum(r["bucket"] == "matched" for r in neg)
    return {
        "pairs": len(rows), "positives": len(pos), "negatives": len(neg),
        "matched_precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "matched_recall": round(tp / len(pos), 3) if pos else None,
        "candidate_recall": round(sum(r["bucket"] != "not_found" for r in pos) / len(pos), 3) if pos else None,
        "positives_left_uncertain": round(sum(r["bucket"] == "uncertain" for r in pos) / len(pos), 3) if pos else None,
        "false_exclusion_rate": round(sum(r["bucket"] == "excluded" for r in pos) / len(pos), 3) if pos else None,
        "negatives_kept_out": round(sum(r["bucket"] != "matched" for r in neg) / len(neg), 3) if neg else None,
    }


def to_langsmith(pairs: list[dict]) -> str | None:
    if not config.TRACING:
        return None
    from langsmith import Client
    client = Client()
    name = "ssi-matching-silver"
    if not client.has_dataset(dataset_name=name):
        client.create_dataset(dataset_name=name, description="Silver pairs labelled by ITA EIN (see eval/matching/run.py)")
        client.create_examples(dataset_name=name, examples=[
            {"inputs": {k: p[k] for k in ("query_name", "query_city", "query_state", "b_key")},
             "outputs": {"label": p["label"], "kind": p["kind"]}} for p in pairs])

    def target(inputs: dict) -> dict:
        return predict({**inputs})

    def not_wrong(outputs: dict, reference_outputs: dict) -> bool:
        # positives must not be excluded; negatives must not be matched
        return outputs["bucket"] != ("excluded" if reference_outputs["label"] == 1 else "matched")

    def summary(outputs: list[dict], reference_outputs: list[dict]) -> dict:
        rows = [{**o, **r} for o, r in zip(outputs, reference_outputs)]
        m = metrics(rows)
        return {"key": "matched_precision", "score": m["matched_precision"]}

    res = client.evaluate(target, data=name, evaluators=[not_wrong], summary_evaluators=[summary],
                          experiment_prefix="rules", max_concurrency=2)
    return getattr(res, "experiment_name", None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="pairs per class")
    ap.add_argument("--typos", type=int, default=400, help="OSHA names to misspell (0 skips the typo checks)")
    a = ap.parse_args()
    t = time.time()
    pairs = build_pairs(a.n)
    rows = []
    for p in pairs:
        rows.append({**p, **predict(p)})
    m = metrics(rows)
    by_kind = {}
    for kind in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == kind]
        by_kind[kind] = {b: sum(r["bucket"] == b for r in sub) for b in ("matched", "uncertain", "excluded", "not_found")}
    wrong = [r for r in rows if (r["label"] == 0 and r["bucket"] == "matched") or (r["label"] == 1 and r["bucket"] == "excluded")]
    typos = grade_typos(typo_cases(a.typos)) if a.typos else None
    licence = grade_licence(licence_cases()) if a.typos else None
    (OUT / "results.json").write_text(json.dumps({"metrics": m, "by_kind": by_kind, "typos": typos, "licence": licence,
                                                  "seconds": round(time.time() - t)}, indent=2))
    lines = ["# Matching evaluation (silver labels from ITA EINs)", "",
             f"{m['pairs']} pairs ({m['positives']} positive, {m['negatives']} negative), {round(time.time() - t)} s.", "",
             "| Metric | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in m.items() if k not in ("pairs", "positives", "negatives")]
    lines += ["", "## Outcome by pair type", "", "| Pair type | matched | uncertain | excluded | not found |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {v['matched']} | {v['uncertain']} | {v['excluded']} | {v['not_found']} |" for k, v in by_kind.items()]
    lines += ["", "## Disagreements with the silver label (first 20)", "", "| Label | Query (A) | Candidate (B) | Outcome | Rule |", "|---|---|---|---|---|"]
    lines += [f"| {'same' if r['label'] else 'different'} | {r['a_name']} ({r['query_city']}, {r['query_state']}) | "
              f"{r['b_name']} ({r['b_city']}, {r['b_state']}) | {r['bucket']} | {r['rule']} |" for r in wrong[:20]]
    if typos:
        lines += ["", "## Typos", "",
                  f"{typos['cases']} slips in distinctive OSHA names, searched with the name's city and state.", "",
                  "| Outcome | Count |", "|---|---|",
                  f"| same matches as the correct spelling | {typos['same_as_correct_spelling']} |",
                  f"| fewer (the rest left for the AI reviewer and the GC) | {typos['fewer_matches']} |",
                  f"| a match the correct spelling doesn't make | {typos['extra_matches']} |"]
        lines += [f"- {x}" for x in typos["extra_examples"][:10]]
        lines += ["", "Licensed contractors with no OSHA record, one letter from an OSHA name in the same city:", "",
                  "| Case | Matched automatically |", "|---|---|",
                  f"| same address (a slip) | {licence['slips_matched']} of {licence['slips_same_address']} |",
                  f"| another address (usually another company) | {licence['lookalikes_matched']} of {licence['lookalikes_other_address']} |"]
        lines += [f"- {x}" for x in licence["lookalike_examples"][:10]]
    exp = to_langsmith(pairs)
    if exp:
        lines += ["", f"LangSmith experiment: `{exp}`"]
    (OUT / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    main()
