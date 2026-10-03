"""Create the demo project through the real API code paths (matching, adjudication, verdicts).

Real Southeast specialty contractors chosen to cover each scenario the tool handles; companies only
(no sole proprietors named after a person). All facts shown come from public OSHA records.

    uv run python -m scripts.seed_demo
"""
from __future__ import annotations

from ssi.api import app as A
from ssi.api.schemas import ProjectCreate, QuestionAnswer, SubInput, SubsCreate
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
    ("Barnhart Crane & Rigging", "Memphis", "TN", "crane and rigging"),  # national, WA state plan; branch fatality via a GC answer
    ("Allison-Smith Company", "Smyrna", "GA", "electrical"),           # clean record
    ("Tindall Corporation", "Spartanburg", "SC", "precast concrete"),  # plants coded as manufacturing, confirmed by the GC
    ("Brasfield & Gorrie", "Birmingham", "AL", "general contractor"),  # JV partner: old history only
    ("Quality Roofing", "Nashville", "TN", "roofing"),                 # generic name
    ("J & J Drywall", "Nashville", "TN", "drywall"),                   # initials-only name
    ("Riverbend Glazing Co.", "Nashville", "TN", "glazing"),           # no OSHA record
]

# The demo GC's answers to the red-flag match questions the rules raise, keyed by sub and the OSHA name in the
# question, so the foreman eval runs against a reviewed project. A question not listed here stays open and is
# printed, so a rule change that raises a new one is visible.
GC_ANSWERS = {
    ("Barnhart Crane & Rigging", "BARNARD ROOFING"): "no",  # a roofer in Gray, TN
    ("Barnhart Crane & Rigging", "BARNHART CRANE RIGGING OKLAHOMA CITY BRANCH"): "yes",  # filed at Barnhart's Memphis HQ
    ("Brasfield & Gorrie", "EXCEL ELECTRICAL TECHNOLOGIES"): "no",  # an electrical contractor in Kennesaw, GA
    ("Tindall Corporation", "TINDALL"): "yes",  # Tindall's precast plants (Petersburg, Spartanburg, Conley, San Antonio)
}


def answer_questions(project_id: str) -> None:
    with pg.conn() as c:
        qs = c.execute("""SELECT q.question_id::text AS question_id, q.text, s.entered_name
                          FROM app.match_question q JOIN app.project_sub s USING (sub_id)
                          WHERE s.project_id = %s AND q.answer IS NULL ORDER BY q.created_at""", [project_id]).fetchall()
    for q in qs:
        ans = next((a for (sub, osha), a in GC_ANSWERS.items() if sub == q["entered_name"] and f"under '{osha}'" in q["text"]), None)
        if ans:
            A.answer(q["question_id"], QuestionAnswer(answer=ans))
        else:
            print(f"  open question (no demo answer): {q['entered_name']}: {q['text'][:120]}")


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
    answer_questions(p.project_id)
    detail = A.get_project(p.project_id)
    print(f"project {p.project_id}")
    for c in detail.subs:
        print(f"  {c.verdict_label:16s} {c.entered_name:30s} est={c.matched_establishments:3d} insp={c.matched_inspections:4d} "
              f"q={c.pending_questions} | " + "; ".join(r.label for r in c.reasons[:2]))


if __name__ == "__main__":
    main()
