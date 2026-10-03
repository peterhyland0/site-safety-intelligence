"""Foreman tools = the named queries, exposed with strict schemas. The `sub_id` parameter is an enum
of THIS project's subs, so the model cannot query a company outside the project by accident."""
from __future__ import annotations

from ssi.llm.base import ToolSpec
from ssi.matching import run as M
from ssi.queries import core as Q

RED_FLAG_KINDS = ["fatality_cited", "fatality_inspected_not_cited", "fatcat_cited", "willful", "repeat", "fta"]


def specs(sub_ids: list[str], hazard_codes: list[str]) -> list[ToolSpec]:
    sub = {"type": "string", "enum": sub_ids, "description": "The project sub's id (from the project context)"}
    obj = lambda props, req: {"type": "object", "properties": props, "required": req, "additionalProperties": False}  # noqa: E731
    return [
        ToolSpec("compare_subs", "Scorecard for every sub on the project: verdict, top reasons, inspection counts, "
                 "serious-citation rate vs the trade median, red-flag counts. Use for 'which subs…' and comparisons.",
                 obj({}, [])),
        ToolSpec("sub_summary", "One sub's verdict with reasons (and the inspection IDs behind each), counts all-time "
                 "and in the project window, rate vs trade, states, years active, records not counted.",
                 obj({"sub_id": sub}, ["sub_id"])),
        ToolSpec("red_flags", "A sub's catastrophic or repeated-offence events: fatalities (cited or not), "
                 "fatality/catastrophe investigations, willful, repeat, failure-to-abate. Newest first.",
                 obj({"sub_id": sub, "kinds": {"type": "array", "items": {"type": "string", "enum": RED_FLAG_KINDS}}},
                     ["sub_id", "kinds"])),
        ToolSpec("citations_by_hazard", "A sub's citations grouped by hazard (fall protection, scaffolds, ladders, "
                 "electrical, excavation…). Give a hazard code to list that hazard's inspections.",
                 obj({"sub_id": sub, "hazard": {"type": "string", "enum": hazard_codes + ["any"]}},
                     ["sub_id", "hazard"])),
        ToolSpec("fatality_history", "A sub's fatality and accident investigations, whether the sub was cited, how "
                 "many employers were on the site, and the accident narrative when published.",
                 obj({"sub_id": sub}, ["sub_id"])),
        ToolSpec("trend_by_year", "A sub's inspections, citations and serious citations per year.",
                 obj({"sub_id": sub}, ["sub_id"])),
        ToolSpec("injury_rates", "A sub's self-reported injury rates (TRIR, DART) per year from OSHA's 300A filings, "
                 "with the industry rate for its trade, plus any state contractor licence on file.",
                 obj({"sub_id": sub}, ["sub_id"])),
        ToolSpec("open_cases", "A sub's inspections that are still open (citations may still change).",
                 obj({"sub_id": sub}, ["sub_id"])),
        ToolSpec("inspection_list", "A sub's inspections, newest first (lists up to 20; total and with_citations count all), "
                 "optionally since a year.",
                 obj({"sub_id": sub, "since_year": {"type": "integer"}}, ["sub_id", "since_year"])),
        ToolSpec("inspection_detail", "Every citation in one inspection, plus any accident narrative.",
                 obj({"activity_nr": {"type": "integer"}}, ["activity_nr"])),
        ToolSpec("lookup_company", "Look up a company that is NOT on this project. Needs name, city and state; "
                 "results are an unconfirmed, rules-only match.",
                 obj({"name": {"type": "string"}, "city": {"type": "string"}, "state": {"type": "string"}},
                     ["name", "city", "state"])),
        ToolSpec("ask_which_sub", "When the question could mean several subs (e.g. two electricians), ask the "
                 "foreman which one by listing the candidate sub ids.",
                 obj({"sub_ids": {"type": "array", "items": sub}}, ["sub_ids"])),
        ToolSpec("report_unanswerable", "Use when no tool can answer the question; logs it so the capability can be added.",
                 obj({"reason": {"type": "string"}}, ["reason"])),
    ]


class Toolbox:
    def __init__(self, project: dict, subs: list[dict]):
        self.project = project
        self.subs = {str(s["sub_id"]): s for s in subs}
        self.cache: dict[str, dict] = {}
        self.used_subs: list[str] = []

    def data(self, sub_id: str) -> dict:
        if sub_id not in self.cache:
            self.cache[sub_id] = Q.compute(self.subs[sub_id], self.project)
        if sub_id not in self.used_subs:
            self.used_subs.append(sub_id)
        return self.cache[sub_id]

    def _precondition(self, sub_id: str) -> dict | None:
        d = self.data(sub_id)
        pending = d["scope"]["pending_questions"]
        if pending:
            return {"status": "needs_confirmation", "sub": self.subs[sub_id]["entered_name"],
                    "pending_questions": [q["text"] for q in pending],
                    "note": "The GC must confirm possible matches before this sub's history can be answered."}
        return None

    def run(self, name: str, args: dict) -> dict:
        fn = getattr(self, "t_" + name, None)
        if fn is None:
            return {"error": f"unknown tool {name}"}
        if "sub_id" in args:
            if args["sub_id"] not in self.subs:
                return {"error": "sub_id is not on this project"}
            pre = self._precondition(args["sub_id"])
            if pre:
                return pre
            out = fn(**args)
            if isinstance(out, dict) and "sub" not in out:  # name the sub in every per-sub result
                out = {"sub": self.subs[args["sub_id"]]["entered_name"], **out}
            return out
        return fn(**args)

    # --- tools ---------------------------------------------------------------------------------------
    def t_compare_subs(self) -> dict:
        rows = []
        for sid, s in self.subs.items():
            c = Q.card(s, self.project, self.data(sid))
            rows.append({"sub_id": sid, "sub": s["entered_name"], "verdict": c.verdict_label,
                         "top_reasons": [r.label for r in c.reasons[:2]], "matched_inspections": c.matched_inspections,
                         "inspections_last_window": c.inspections_in_window, "window_years": c.window_years,
                         "serious_per_inspection": c.serious_plus_rate, "trade_median": c.trade_p50,
                         "red_flags": c.red_flag_count, "possible_records_not_counted": c.possible_inspections,
                         "pending_match_questions": c.pending_questions})
        return {"subs": rows}

    def t_sub_summary(self, sub_id: str) -> dict:
        d = self.data(sub_id)
        c = Q.card(self.subs[sub_id], self.project, d)
        rate, p50 = c.serious_plus_rate, c.trade_p50
        return {"sub": c.entered_name, "osha_name": c.display_name, "verdict": c.verdict_label,
                "reasons": [{"label": r.label, "severity": r.severity, "inspection_ids": r.evidence[:10]} for r in d["reasons"]],
                "matched_records": c.matched_establishments, "inspections_all_time": c.matched_inspections,
                "inspections_in_window": c.inspections_in_window, "window_years": c.window_years,
                "serious_per_inspection": rate, "trade": c.trade_label, "trade_median": p50, "trade_p75": c.trade_p75,
                "rate_vs_median": (f"{rate / p50:.1f}x" if rate is not None and p50 else None),
                "states": c.states, "first_year": c.first_year, "last_year": c.last_year,
                "possible_inspections_not_counted": c.possible_inspections,
                "pending_match_questions": c.pending_questions,
                "possible_note": ("Possible records might be this sub but weren't confirmed, so they don't count toward "
                                  "the verdict. The GC is only asked about possible records that carry red flags; "
                                  "pending_match_questions says whether any are waiting."),
                "coverage": Q.coverage(d).sentence}

    def t_red_flags(self, sub_id: str, kinds: list[str]) -> dict:
        flags = [f for f in self.data(sub_id)["flags"] if not kinds or f.kind in kinds]
        return {"total": len(flags), "shown": min(len(flags), 25), "events": [
            {"kind": f.label, "date": f.event_date, "inspection_id": f.activity_nr, "standard": f.standard,
             "hazard": f.hazard_label, "penalty_current": f.penalty_current, "case_open": f.case_open,
             "employers_on_site": f.shared_site_n} for f in flags[:25]]}

    def t_citations_by_hazard(self, sub_id: str, hazard: str) -> dict:
        d = self.data(sub_id)
        if hazard and hazard != "any":
            rows = Q.inspections(d["keys"], limit=20, hazard=hazard)
            h = next((x for x in d["hazards"] if x.hazard_code == hazard), None)
            return {"hazard": hazard, "label": h.label if h else hazard, "citations": h.citations if h else 0,
                    "serious": h.serious_plus if h else 0, "inspections": h.inspections if h else 0,
                    "first_year": h.first_year if h else None, "last_year": h.last_year if h else None,
                    "inspection_list": [{"inspection_id": r.activity_nr, "date": r.open_date, "city": r.site_city,
                                         "state": r.site_state, "citations": r.citations} for r in rows]}
        return {"hazards": [{"hazard": h.hazard_code, "label": h.label, "citations": h.citations, "serious": h.serious_plus,
                             "inspections": h.inspections, "first_year": h.first_year, "last_year": h.last_year,
                             "top_standards": h.top_standards} for h in d["hazards"][:15]]}

    def t_fatality_history(self, sub_id: str) -> dict:
        d = self.data(sub_id)
        fat = [f for f in d["flags"] if f.kind in ("fatality_cited", "fatality_inspected_not_cited", "fatcat_cited")]
        out = []
        for f in fat[:10]:
            det = Q.inspection_detail(f.activity_nr)
            acc = det.accidents[0] if det and det.accidents else None
            out.append({"inspection_id": f.activity_nr, "date": f.event_date, "status": f.label,
                        "employers_on_site": f.shared_site_n,
                        "serious_citations": det.serious_plus if det else None,
                        "narrative": (acc.narrative or acc.description or "")[:400] if acc else "not published"})
        return {"total": len(fat), "events": out,
                "note": (f"Covers OSHA inspections since {Q.warehouse.meta()['history_since']}; accident narratives are "
                         f"published through {Q.warehouse.meta()['accident_detail_through']}.")}

    def t_trend_by_year(self, sub_id: str) -> dict:
        return {"years": [y.model_dump() for y in Q.trend(self.data(sub_id)["keys"])][-15:]}

    def t_injury_rates(self, sub_id: str) -> dict:
        d = self.data(sub_id)
        return {"years": [{"year": r.year, "trir": r.trir, "dart": r.dart, "industry_trir": r.peer_trir,
                           "hours": r.hours, "establishments": r.establishment_name, "excluded_as_implausible": r.flagged}
                          for r in d["rates"]][-6:],
                "note": "Self-reported OSHA 300A summaries; firms under 20 employees usually don't file, so no rate "
                        "means not filed, not zero injuries.",
                "licences": [l.model_dump() for l in d["licences"][:3]]}

    def t_open_cases(self, sub_id: str) -> dict:
        rows = Q.inspections(self.data(sub_id)["keys"], limit=20, open_only=True)
        return {"open_cases": len(rows), "cases": [{"inspection_id": r.activity_nr, "opened": r.open_date,
                "city": r.site_city, "state": r.site_state, "citations": r.citations, "serious": r.serious_plus,
                "penalty_current": r.penalty_current} for r in rows]}

    def t_inspection_list(self, sub_id: str, since_year: int) -> dict:
        rows = Q.inspections(self.data(sub_id)["keys"], limit=1000, since_year=since_year or None)
        return {"total": len(rows), "with_citations": sum(1 for r in rows if r.citations), "shown": min(len(rows), 20),
                "inspections": [{"inspection_id": r.activity_nr, "opened": r.open_date, "type": r.insp_type_label,
                                 "city": r.site_city, "state": r.site_state, "citations": r.citations,
                                 "serious": r.serious_plus, "open": r.is_open} for r in rows[:20]]}

    def t_inspection_detail(self, activity_nr: int) -> dict:
        det = Q.inspection_detail(activity_nr)
        if not det:
            return {"error": "inspection not found"}
        keys = {k for sid in self.subs for k in self.data(sid)["keys"]}
        owner = Q.warehouse.one("SELECT establishment_key FROM osha.inspection WHERE activity_nr = ?", [activity_nr])
        return {"inspection_id": det.activity_nr, "on_project": bool(owner and owner["establishment_key"] in keys),
                "employer": det.establishment_name, "opened": det.open_date, "type": det.insp_type_label,
                "open": det.is_open, "citations": [{"type": c.viol_type_label, "standard": c.standard, "hazard": c.hazard_label,
                                                    "penalty_current": c.penalty_current, "deleted": c.is_deleted}
                                                   for c in det.citation_rows[:30]],
                "accident": ({"date": det.accidents[0].event_date, "narrative": (det.accidents[0].narrative or "")[:500]}
                             if det.accidents else None)}

    def t_lookup_company(self, name: str, city: str, state: str) -> dict:
        res = M.match(name, city, state, None)
        matched = [x["row"] for x in res["decisions"] if x["decision"].bucket == "matched"]
        keys = [r["establishment_key"] for r in matched]
        flags = Q.red_flags(keys)
        return {"unconfirmed": True, "query": {"name": name, "city": city, "state": state},
                "matched_records": len(keys), "inspections": sum(r["insp_n"] for r in matched),
                "red_flags": [{"kind": f.label, "date": f.event_date, "inspection_id": f.activity_nr} for f in flags[:10]],
                "note": "Rules-only match for a company not on the project; confirm before relying on it."}

    def t_ask_which_sub(self, sub_ids: list[str]) -> dict:
        return {"clarify": [{"sub_id": s, "name": self.subs[s]["entered_name"]} for s in sub_ids if s in self.subs]}

    def t_report_unanswerable(self, reason: str) -> dict:
        return {"logged": True, "reason": reason}
