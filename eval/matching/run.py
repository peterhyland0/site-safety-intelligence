"""Matching evaluation on a silver-labelled set built from the data itself.

Labels come from OSHA's injury-tracking filings (ITA 300A), which carry the employer's tax ID (EIN):
  positive = two OSHA establishments that link exactly (name + zip) to ITA rows with the same EIN
  negative = two establishments with the same name core in the same state but different EINs
For each pair we search as the GC would (A's name, city, state) and grade where B lands.

Labels are "silver", not gold: big firms file under several EINs and sibling companies sometimes share
one, so a few labels are wrong in both directions. Results: eval/matching/results.md (and LangSmith if a
LANGSMITH_API_KEY is set).

    uv run python -m eval.matching.run [--n 150]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

from ssi.matching import run as M
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
            WHERE NOT x.is_placeholder AND x.city IS NOT NULL AND x.insp_n >= 1)
    """
    pos = warehouse.rows(base + """
      SELECT a.establishment_key AS a_key, b.establishment_key AS b_key, 1 AS label,
             CASE WHEN a.clean_name = b.clean_name THEN 'same_name_other_address' ELSE 'different_name' END AS kind
      FROM e a JOIN e b ON a.ein = b.ein AND a.establishment_key < b.establishment_key
      USING SAMPLE reservoir(4000 ROWS) REPEATABLE (7)""")
    neg = warehouse.rows(base + """
      SELECT a.establishment_key AS a_key, b.establishment_key AS b_key, 0 AS label,
             CASE WHEN a.clean_name = b.clean_name THEN 'same_name_different_ein' ELSE 'same_core_different_ein' END AS kind
      FROM e a JOIN e b ON a.name_core = b.name_core AND a.state = b.state AND a.ein <> b.ein
                        AND a.establishment_key < b.establishment_key AND a.name_core <> ''
      USING SAMPLE reservoir(4000 ROWS) REPEATABLE (7)""")
    rnd = random.Random(seed)
    rnd.shuffle(pos)
    rnd.shuffle(neg)
    pairs = pos[: n] + neg[: n]
    keys = list({p["a_key"] for p in pairs} | {p["b_key"] for p in pairs})
    info = {r["establishment_key"]: r for r in warehouse.rows(
        "SELECT establishment_key, display_name, clean_name, city, state FROM entity.establishment "
        "WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))", [keys])}
    for p in pairs:
        a, b = info[p["a_key"]], info[p["b_key"]]
        p.update(query_name=a["display_name"], query_city=a["city"], query_state=a["state"],
                 a_name=a["clean_name"], b_name=b["clean_name"], b_city=b["city"], b_state=b["state"])
    return pairs


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
    if not os.environ.get("LANGSMITH_API_KEY"):
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
    (OUT / "results.json").write_text(json.dumps({"metrics": m, "by_kind": by_kind, "seconds": round(time.time() - t)}, indent=2))
    lines = ["# Matching evaluation (silver labels from ITA EINs)", "",
             f"{m['pairs']} pairs ({m['positives']} positive, {m['negatives']} negative), {round(time.time() - t)} s.", "",
             "| Metric | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in m.items() if k not in ("pairs", "positives", "negatives")]
    lines += ["", "## Outcome by pair type", "", "| Pair type | matched | uncertain | excluded | not found |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {v['matched']} | {v['uncertain']} | {v['excluded']} | {v['not_found']} |" for k, v in by_kind.items()]
    lines += ["", "## Disagreements with the silver label (first 20)", "", "| Label | Query (A) | Candidate (B) | Outcome | Rule |", "|---|---|---|---|---|"]
    lines += [f"| {'same' if r['label'] else 'different'} | {r['a_name']} ({r['query_city']}, {r['query_state']}) | "
              f"{r['b_name']} ({r['b_city']}, {r['b_state']}) | {r['bucket']} | {r['rule']} |" for r in wrong[:20]]
    exp = to_langsmith(pairs)
    if exp:
        lines += ["", f"LangSmith experiment: `{exp}`"]
    (OUT / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    main()
