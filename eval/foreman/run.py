"""Foreman evaluation: 20 questions against the demo project, graded in code.

Spends API credit (one conversation per question), so run it deliberately:
    uv run python -m eval.foreman.run            # needs an LLM key; logs to LangSmith if LANGSMITH_API_KEY is set

Graders: expected tool used, expected status (answered / clarify / needs_confirmation / unanswerable),
grounded (the code-side number check passed), required phrases present, forbidden phrases absent.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ssi import config
from ssi.agent import foreman
from ssi.llm import client as llm
from ssi.store import pg, warehouse

HERE = Path(__file__).parent
DEMO = "Demo: Hospital expansion, Nashville TN"


KEYS = ["tool_ok", "status_ok", "grounded", "mentions_ok", "language_ok"]


def grade(item: dict, resp: dict) -> dict:
    ans = resp["answer"].lower()
    return {
        "tool_ok": (not item["tools"]) or any(t in resp["tools_used"] for t in item["tools"]),
        "status_ok": resp["status"] in ([item["status"]] if isinstance(item["status"], str) else item["status"]),
        "grounded": resp["status"] != "guard_failed",
        "mentions_ok": all(m.lower() in ans for m in item.get("mentions", []))
                       and (not item.get("mentions_any") or any(m.lower() in ans for m in item["mentions_any"])),
        "language_ok": not any(m.lower() in ans for m in item.get("must_not", [])),
    }


def main() -> None:
    if not llm.available("foreman"):
        raise SystemExit("No LLM configured (ANTHROPIC_API_KEY, or SSI_LLM_PROVIDER=openai_compat + SSI_LLM_BASE_URL).")
    warehouse.open_warehouse()
    with pg.conn() as c:
        project = c.execute("SELECT * FROM app.project WHERE name = %s", [DEMO]).fetchone()
    if not project:
        raise SystemExit("Seed the demo project first: uv run python -m scripts.seed_demo")
    text = (HERE / "questions.json").read_text()
    items = json.loads(text)
    rows, answers = [], {}
    for item in items:
        t = time.time()
        resp = foreman.answer(project, item["q"], []).model_dump()
        answers[item["q"]] = resp
        rows.append({"q": item["q"], "status": resp["status"], "tools": resp["tools_used"], "answer": resp["answer"],
                     "seconds": round(time.time() - t, 1), **grade(item, resp)})
        print(f"{rows[-1]['status']:18s} {rows[-1]['seconds']:5.1f}s {item['q']}")
    summary = {k: f"{sum(r[k] for r in rows)}/{len(rows)}" for k in KEYS}
    secs = sorted(r["seconds"] for r in rows)
    lines = ["# Foreman evaluation", "", (f"Model: {llm.model_label('foreman')}. {len(rows)} questions. "
                                          f"Median {secs[len(secs) // 2]}s per answer, slowest {secs[-1]}s."), "",
             "| Check | Passed |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary.items()]
    lines += ["", "| Question | Status | Tools | Pass |", "|---|---|---|---|"]
    lines += [f"| {r['q']} | {r['status']} | {', '.join(r['tools'])} | {'✅' if all(r[k] for k in KEYS) else '❌'} |"
              for r in rows]
    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    (HERE / "results.json").write_text(json.dumps(rows, indent=2))
    if config.TRACING:
        # Log the answers above as a LangSmith experiment (no second round of model calls). The dataset name
        # carries a hash of questions.json, so editing an expectation creates a new dataset version.
        from langsmith import Client
        client = Client()
        name = "ssi-foreman-questions-" + hashlib.sha1(text.encode()).hexdigest()[:8]
        if not client.has_dataset(dataset_name=name):
            client.create_dataset(dataset_name=name)
            client.create_examples(dataset_name=name, examples=[{"inputs": {"question": i["q"]}, "outputs": i} for i in items])

        def evaluator(key):
            def ev(outputs, reference_outputs):
                return {"key": key, "score": int(grade(reference_outputs, outputs)[key])}
            ev.__name__ = key
            return ev

        client.evaluate(lambda inputs: answers[inputs["question"]], data=name, experiment_prefix="foreman",
                        evaluators=[evaluator(k) for k in KEYS],
                        metadata={"model": llm.model_label("foreman")})
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
