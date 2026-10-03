"""FastAPI app: the GC scorecard API, the foreman's ask endpoint, and the static SPA (web/dist)."""
from __future__ import annotations

import base64
import csv
import io
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ssi import config
from ssi.api import duplicates
from ssi.api import schemas as S
from ssi.llm import client as llm_client
from ssi.matching import adjudicate as ADJ
from ssi.matching.run import match_and_persist
from ssi.queries import core as Q
from ssi.store import pg, warehouse

WEB_DIST = config.REPO_ROOT / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    warehouse.open_warehouse()
    pg.ensure_schema()
    yield
    pg.close()


app = FastAPI(title="Site Safety Intelligence", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    user, pw = os.environ.get("BASIC_AUTH_USER"), os.environ.get("BASIC_AUTH_PASS")
    if user and pw and request.url.path != "/api/health":
        header = request.headers.get("authorization", "")
        ok = False
        if header.lower().startswith("basic "):
            try:
                u, _, p = base64.b64decode(header[6:]).decode().partition(":")
                ok = secrets.compare_digest(u, user) and secrets.compare_digest(p, pw)
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Site Safety Intelligence"'})
    return await call_next(request)


# --- helpers ---------------------------------------------------------------------------------------
def _project(project_id: str) -> dict:
    with pg.conn() as c:
        p = c.execute("""SELECT p.*, (SELECT count(*) FROM app.project_sub s WHERE s.project_id = p.project_id) AS sub_count
                         FROM app.project p WHERE project_id = %s""", [project_id]).fetchone()
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _sub(project_id: str, sub_id: str) -> dict:
    with pg.conn() as c:
        s = c.execute("SELECT * FROM app.project_sub WHERE sub_id = %s AND project_id = %s", [sub_id, project_id]).fetchone()
    if not s:
        raise HTTPException(404, "Sub not found")
    return s


def _project_model(p: dict) -> S.Project:
    return S.Project(project_id=str(p["project_id"]), name=p["name"], state=p["state"], lookback_years=p["lookback_years"],
                     created_at=p["created_at"].isoformat(), sub_count=p.get("sub_count") or 0)


def _cards(project: dict) -> list[S.SubCard]:
    with pg.conn() as c:
        subs = c.execute("SELECT * FROM app.project_sub WHERE project_id = %s ORDER BY position, created_at",
                         [project["project_id"]]).fetchall()
    # each card runs ~a dozen small warehouse queries; DuckDB cursors are thread-safe, so do subs in parallel
    with ThreadPoolExecutor(max_workers=8) as ex:
        cards = list(ex.map(lambda s: Q.card(s, project), subs))
    order = {"high": 0, "review": 1, "no_record": 2, "no_recent": 3, "no_flags": 4}
    return sorted(cards, key=lambda c: (order[c.verdict], -sum(r.severity == "high" for r in c.reasons),
                                        -c.red_flag_count, c.entered_name.lower()))


def _bucket_rows(d: dict, bucket: str) -> list[S.MatchedEstablishment]:
    sc = d["scope"]
    keys = sc[bucket]
    if not keys:
        return []
    ests = {e["establishment_key"]: e for e in warehouse.rows(
        """SELECT establishment_key, display_name, name_variants, address, city, state, zip5, primary_naics4,
                  first_seen::VARCHAR AS first_seen, last_seen::VARCHAR AS last_seen, insp_n,
                  coalesce(related_only, false) AS related_only
           FROM entity.establishment WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))""", [keys])}
    from ssi.matching import candidates as C
    flagged = C.red_flag_counts(keys)
    from ssi.matching.trades import NAICS4_LABELS
    out = []
    for k in keys:
        e, m = ests.get(k), sc["rows"][k]
        if not e:
            continue  # stale key (warehouse rebuilt with different cleaning rules)
        out.append(S.MatchedEstablishment(
            establishment_key=k, display_name=e["display_name"], name_variants=list(e["name_variants"] or [])[:8],
            address=e["address"], city=e["city"], state=e["state"], zip=e["zip5"],
            trade_label=NAICS4_LABELS.get(e["primary_naics4"] or ""), first_seen=e["first_seen"], last_seen=e["last_seen"],
            inspections=e["insp_n"], bucket=bucket, method=m["method"], rule_id=m["rule_id"],
            confidence=m["confidence"], rationale=m["rationale"], has_red_flags=bool(flagged.get(k)),
            related_only=bool(e["related_only"]), industry_code=e["primary_naics4"]))
    return sorted(out, key=lambda x: -x.inspections)


def _detail(sub: dict, project: dict) -> S.SubDetail:
    d = Q.compute(sub, project)
    keys = d["keys"]
    sc = d["scope"]
    dq = []
    if sc.get("note"):
        dq.append(sc["note"])
    if d["benchmark"] is None and keys:
        dq.append("Too few comparable firms to benchmark this trade.")
    meta = warehouse.meta()
    if any(f.kind.startswith("fatality") for f in d["flags"]) or keys:
        dq.append(f"OSHA's published accident details run through {meta['accident_detail_through']}; "
                  "later fatality investigations show without narratives.")
    return S.SubDetail(
        card=Q.card(sub, project, d), reasons=d["reasons"], coverage=Q.coverage(d),
        questions=[S.MatchQuestion(question_id=str(q["question_id"]), text=q["text"], establishment_keys=q["establishment_keys"],
                                   ai_suggestion=q["ai_suggestion"], ai_rationale=q["ai_rationale"])
                   for q in sc["pending_questions"]],
        matched=_bucket_rows(d, "matched"), possible=_bucket_rows(d, "possible"), excluded=_bucket_rows(d, "excluded"),
        red_flags=d["flags"][:100], trend=Q.trend(keys), hazards=d["hazards"],
        open_cases=Q.inspections(keys, limit=50, open_only=True), inspections=Q.inspections(keys, limit=25),
        injury_rates=d["rates"], licences=d["licences"], dq_warnings=dq)


# --- routes ----------------------------------------------------------------------------------------
@app.get("/api/health", response_model=S.Health)
def health():
    db_ok = True
    try:
        with pg.conn() as c:
            c.execute("SELECT 1")
    except Exception:
        db_ok = False
    m = warehouse.meta()
    return S.Health(status="ok" if db_ok else "degraded", data_as_of=m["data_as_of"], build_id=m["build_id"],
                    llm_enabled=llm_client.available("foreman"), db_ok=db_ok)


@app.get("/api/projects", response_model=list[S.Project])
def list_projects():
    with pg.conn() as c:
        ps = c.execute("""SELECT p.*, (SELECT count(*) FROM app.project_sub s WHERE s.project_id = p.project_id) AS sub_count
                          FROM app.project p ORDER BY created_at DESC""").fetchall()
    return [_project_model(p) for p in ps]


@app.post("/api/projects", response_model=S.Project)
def create_project(body: S.ProjectCreate):
    with pg.conn() as c:
        p = c.execute("INSERT INTO app.project (name, state, lookback_years) VALUES (%s, %s, %s) RETURNING *",
                      [body.name, (body.state or "").upper() or None, body.lookback_years]).fetchone()
    return _project_model({**p, "sub_count": 0})


@app.get("/api/projects/{project_id}", response_model=S.ProjectDetail)
def get_project(project_id: str):
    p = _project(project_id)
    m = warehouse.meta()
    return S.ProjectDetail(project=_project_model(p), subs=_cards(p), data_as_of=m["data_as_of"],
                           history_since=m.get("history_since"))


@app.patch("/api/projects/{project_id}", response_model=S.Project)
def update_project(project_id: str, body: S.ProjectUpdate):
    _project(project_id)
    with pg.conn() as c:
        if body.name is not None:
            c.execute("UPDATE app.project SET name = %s WHERE project_id = %s", [body.name, project_id])
        if body.lookback_years is not None:
            c.execute("UPDATE app.project SET lookback_years = %s WHERE project_id = %s", [body.lookback_years, project_id])
    return _project_model(_project(project_id))


@app.post("/api/projects/{project_id}/subs", response_model=list[S.SubCard])
def add_subs(project_id: str, body: S.SubsCreate):
    p = _project(project_id)
    rows = [r for r in body.rows if r.name.strip()]
    states = [(r.state or p["state"] or "").strip().upper()[:2] or None for r in rows]
    created = []
    with pg.conn() as c:
        existing = c.execute("SELECT sub_id, entered_name, entered_state FROM app.project_sub WHERE project_id = %s",
                             [project_id]).fetchall()
        keys = duplicates.name_keys([r.name for r in rows] + [e["entered_name"] for e in existing])
        repeats = duplicates.find(
            [{"name": r.name.strip(), "key": k, "state": st} for r, k, st in zip(rows, keys, states)],
            [{"sub_id": e["sub_id"], "name": e["entered_name"], "key": k, "state": e["entered_state"]}
             for e, k in zip(existing, keys[len(rows):])])
        if repeats:  # nothing is added: the GC fixes or removes the repeated rows and sends the batch again
            n = len(repeats)
            raise HTTPException(409, {"message": f"{n} of these {'is' if n == 1 else 'are'} already on this project. "
                                                 "Remove or change the highlighted rows, then add again.",
                                      "duplicates": repeats})
        start = c.execute("SELECT coalesce(max(position), 0) AS m FROM app.project_sub WHERE project_id = %s",
                          [project_id]).fetchone()["m"]
        for i, (row, state) in enumerate(zip(rows, states)):
            s = c.execute("""INSERT INTO app.project_sub (project_id, entered_name, entered_city, entered_state, trade, licence, position)
                             VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                          [project_id, row.name.strip(), (row.city or "").strip() or None, state, row.trade, row.licence,
                           start + i + 1]).fetchone()
            created.append(s)
    for s in created:
        match_and_persist(s, p["state"])
    return [Q.card(s, p) for s in created]


@app.delete("/api/projects/{project_id}/subs/{sub_id}")
def delete_sub(project_id: str, sub_id: str):
    _sub(project_id, sub_id)
    with pg.conn() as c:
        c.execute("DELETE FROM app.project_sub WHERE sub_id = %s", [sub_id])
    return {"ok": True}


@app.get("/api/projects/{project_id}/subs/{sub_id}", response_model=S.SubDetail)
def get_sub(project_id: str, sub_id: str):
    return _detail(_sub(project_id, sub_id), _project(project_id))


@app.get("/api/projects/{project_id}/subs/{sub_id}/inspections", response_model=list[S.InspectionRow])
def sub_inspections(project_id: str, sub_id: str, offset: int = 0, limit: int = 25):
    _sub(project_id, sub_id)
    keys = Q.scope(sub_id)["matched"]
    return Q.inspections(keys, offset=offset, limit=min(limit, 100))


@app.post("/api/projects/{project_id}/subs/{sub_id}/adjudicate", response_model=S.SubCard)
def adjudicate_sub(project_id: str, sub_id: str):
    p, s = _project(project_id), _sub(project_id, sub_id)
    from ssi.llm import adjudicator  # imported lazily: optional dependency on the LLM provider
    ADJ.adjudicate(s, llm=adjudicator.decide if adjudicator.available() else None, packet_fn=ADJ.evidence_packet)
    return Q.card(s, p)


@app.post("/api/projects/{project_id}/subs/{sub_id}/matches/{establishment_key}", response_model=S.SubCard)
def override_match(project_id: str, sub_id: str, establishment_key: str, body: S.MatchOverride):
    p, s = _project(project_id), _sub(project_id, sub_id)
    ADJ.override(sub_id, establishment_key, body.bucket)
    return Q.card(s, p)


@app.post("/api/questions/{question_id}/answer", response_model=S.SubCard)
def answer(question_id: str, body: S.QuestionAnswer):
    try:
        q = ADJ.answer_question(question_id, body.answer)
    except KeyError:
        raise HTTPException(404, "Question not found")
    with pg.conn() as c:
        s = c.execute("SELECT * FROM app.project_sub WHERE sub_id = %s", [q["sub_id"]]).fetchone()
    return Q.card(s, _project(str(s["project_id"])))


@app.get("/api/inspections/{activity_nr}", response_model=S.InspectionDetail)
def inspection(activity_nr: int):
    d = Q.inspection_detail(activity_nr)
    if not d:
        raise HTTPException(404, "Inspection not found")
    return d


@app.post("/api/projects/{project_id}/ask", response_model=S.AskResponse)
def ask(project_id: str, body: S.AskRequest):
    p = _project(project_id)
    from ssi.agent import foreman
    return foreman.answer(p, body.question, body.history)


@app.get("/api/projects/{project_id}/export.csv")
def export(project_id: str):
    p = _project(project_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sub", "osha_name", "verdict", "reasons", "matched_inspections", "inspections_in_window",
                "serious_plus_per_inspection", "trade_median", "red_flags", "possible_not_counted", "states", "years"])
    for c in _cards(p):
        w.writerow([c.entered_name, c.display_name or "", c.verdict_label, " | ".join(r.label for r in c.reasons),
                    c.matched_inspections, c.inspections_in_window, c.serious_plus_rate if c.serious_plus_rate is not None else "",
                    c.trade_p50 if c.trade_p50 is not None else "", c.red_flag_count, c.possible_inspections,
                    " ".join(c.states), f"{c.first_year or ''}-{c.last_year or ''}"])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{p["name"]}-subs.csv"'})


# --- SPA -------------------------------------------------------------------------------------------
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = WEB_DIST / path
        if path and f.is_file() and WEB_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(WEB_DIST / "index.html")
