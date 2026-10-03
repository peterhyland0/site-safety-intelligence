"""Re-run matching for existing subs after a rules or data change, keeping every GC and AI decision.

Dry run by default: shows, per sub, the records whose rule decision would change. --apply rewrites the
rule decisions (decisions made by the GC or the AI reviewer are kept), then sends newly uncertain
records through the adjudicator, which turns red-flagged ones into GC questions.

    uv run python -m scripts.rematch                              # every project, dry run
    uv run python -m scripts.rematch --project "Demo: Hospital expansion, Nashville TN" --apply
"""
from __future__ import annotations

import argparse

from ssi.matching import adjudicate as ADJ
from ssi.matching import candidates as C
from ssi.matching.run import EXCLUDED, MATCHED, UNCERTAIN, match, match_and_persist
from ssi.store import pg, warehouse

BUCKET = {MATCHED: "matched", UNCERTAIN: "possible", EXCLUDED: "excluded"}


def plan(sub: dict, project_state: str | None) -> list[dict]:
    """Rule decisions that would change for this sub (GC and AI decisions are never touched)."""
    with pg.conn() as c:
        stored = {r["establishment_key"]: r for r in c.execute(
            "SELECT * FROM app.sub_match WHERE sub_id = %s AND establishment_key <> '__note__'", [sub["sub_id"]]).fetchall()}
    res = match(sub["entered_name"], sub.get("entered_city"), sub.get("entered_state") or project_state,
                sub.get("trade"), sub.get("licence"))
    changes = []
    for x in res["decisions"]:
        k, d = x["row"]["establishment_key"], x["decision"]
        old = stored.get(k)
        if old and old["method"] != "rule":
            continue  # the GC's or the AI's decision stands
        new_bucket = BUCKET[d.bucket]
        if old and old["bucket"] == new_bucket and old["rule_id"] == d.rule_id:
            continue
        if not old and d.bucket == EXCLUDED:
            continue  # a new lookalike that stays out changes nothing the GC sees
        changes.append({"key": k, "name": x["row"]["display_name"], "place": f"{x['row']['city']}, {x['row']['state']}",
                        "old": f"{old['bucket']}/{old['rule_id']}" if old else "-", "new": f"{new_bucket}/{d.rule_id}"})
    flags = C.red_flag_counts([ch["key"] for ch in changes])
    for ch in changes:
        ch["red_flags"] = flags.get(ch["key"], 0)
    return changes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", help="project name (default: every project)")
    ap.add_argument("--apply", action="store_true", help="write the new decisions (default: dry run)")
    a = ap.parse_args()
    warehouse.open_warehouse()
    with pg.conn() as c:
        projects = c.execute("SELECT * FROM app.project WHERE %s::text IS NULL OR name = %s ORDER BY created_at",
                             [a.project, a.project]).fetchall()
    if not projects:
        raise SystemExit(f"No project named {a.project!r}")
    from ssi.llm import adjudicator  # optional: without a model, uncertain records stay 'possible'
    llm = adjudicator.decide if adjudicator.available() else None
    for p in projects:
        with pg.conn() as c:
            subs = c.execute("SELECT * FROM app.project_sub WHERE project_id = %s ORDER BY position", [p["project_id"]]).fetchall()
        print(f"\n== {p['name']} ({len(subs)} subs){'' if a.apply else '  [dry run]'}")
        for s in subs:
            changes = plan(s, p["state"])
            if not changes:
                continue
            print(f"  {s['entered_name']}")
            for ch in changes:
                flag = f"  [{ch['red_flags']} red flags]" if ch["red_flags"] else ""
                print(f"    {ch['name'][:48]:48s} {ch['place'][:24]:24s} {ch['old']:>16s} -> {ch['new']}{flag}")
            if a.apply:
                match_and_persist(s, p["state"])
                stats = ADJ.adjudicate(s, llm=llm, packet_fn=ADJ.evidence_packet)
                print(f"    applied; adjudicated {stats['clusters']} uncertain group(s), {stats['questions']} new GC question(s)")


if __name__ == "__main__":
    main()
