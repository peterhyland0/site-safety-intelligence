"""Create the demo project through the real API code paths (matching, adjudication, verdicts).

Real Southeast specialty contractors chosen to cover each scenario the tool handles; companies only
(no sole proprietors named after a person). All facts shown come from public OSHA records.

    uv run python -m scripts.seed_demo
"""
from __future__ import annotations

from ssi.api import app as A
from ssi.api.schemas import ProjectCreate, SubInput, SubsCreate
from ssi.store import pg, warehouse

DEMO_NAME = "Demo: Hospital expansion, Nashville TN"

SUBS = [
    # name, city, state, trade                         scenario
    ("Jake Marshall LLC", "Chattanooga", "TN", "mechanical"),          # cited fatality + open case
    ("31-W Insulation Co.", "Goodlettsville", "TN", "insulation"),     # cited fatality
    ("Fugate Construction LLC", "Georgetown", "TN", "framing"),        # repeat violations, recent
    ("Cooper Steel Fabricators", "Shelbyville", "TN", "structural steel"),  # open serious case
    ("Dixie Roofing, Inc.", "LaFollette", "TN", "roofing"),            # many inspections + injury rates
    ("McKenney's, Inc.", "Atlanta", "GA", "mechanical"),               # injury rates, mostly clean
    ("Barnhart Crane & Rigging", "Memphis", "TN", "crane and rigging"),  # national, multi-state, WA state plan
    ("Allison-Smith Company", "Smyrna", "GA", "electrical"),           # clean record
    ("Tindall Corporation", "Spartanburg", "SC", "precast concrete"),  # clean + injury rates
    ("Brasfield & Gorrie", "Birmingham", "AL", "general contractor"),  # JV partner: old history only
    ("Quality Roofing", "Nashville", "TN", "roofing"),                 # generic name
    ("J & J Drywall", "Nashville", "TN", "drywall"),                   # initials-only name
    ("Riverbend Glazing Co.", "Nashville", "TN", "glazing"),           # no OSHA record
]


def main() -> None:
    warehouse.open_warehouse()
    pg.ensure_schema()
    with pg.conn() as c:
        c.execute("DELETE FROM app.project WHERE name = %s", [DEMO_NAME])
    p = A.create_project(ProjectCreate(name=DEMO_NAME, state="TN", lookback_years=5))
    cards = A.add_subs(p.project_id, SubsCreate(rows=[SubInput(name=n, city=ci, state=st, trade=t) for n, ci, st, t in SUBS]))
    for card in cards:
        if card.match_status == "needs_adjudication":
            A.adjudicate_sub(p.project_id, card.sub_id)
    detail = A.get_project(p.project_id)
    print(f"project {p.project_id}")
    for c in detail.subs:
        print(f"  {c.verdict_label:16s} {c.entered_name:30s} est={c.matched_establishments:3d} insp={c.matched_inspections:4d} "
              f"q={c.pending_questions} | " + "; ".join(r.label for r in c.reasons[:2]))


if __name__ == "__main__":
    main()
