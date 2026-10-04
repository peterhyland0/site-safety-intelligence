"""Foreman Q&A: plain-English questions about the project's subs, answered only through named queries.

Guards enforced in code, not in the prompt:
  1. precondition - a sub with an unanswered match question that could add a red flag returns needs_confirmation
                    from every tool (its other open questions don't: results note them instead);
  2. grounding    - every number/date/ID in the answer must appear in the tool results (one retry, then a
                    deterministic fallback);
  3. citations    - inspection IDs in the answer become osha.gov links;
  4. coverage     - the "what this is based on" sentence is appended by code, never written by the model.
"""
from __future__ import annotations

import json
import time

from ssi import config
from ssi.agent import grounding
from ssi.agent.tools import Toolbox, specs
from ssi.api import schemas as S
from ssi.llm import client as llm
from ssi.queries import core as Q
from ssi.store import pg, warehouse

MAX_TURNS = 6

SYSTEM = """You answer a construction foreman's questions, asked on a phone on a job site, about the OSHA \
safety history of the subcontractors ("subs") on their project.

How to answer:
- Use the tools for every fact. Quote figures exactly as the tools return them; never calculate, estimate or \
round new numbers yourself (a code check rejects any figure that isn't in the tool results).
- Cite inspection IDs in parentheses, e.g. (#1234567), for any specific event you mention.
- Keep it short and plain: lead with the direct answer, then at most 4 bullets. No preamble.
- Neutral wording: "OSHA's record shows…", never "dangerous" or "unsafe".
- No OSHA record is not a clean record: OSHA inspects few employers, so say the history is unknown and \
suggest asking the sub for its EMR, TRIR and OSHA 300 logs.
- A fatality on a shared site doesn't mean this sub caused it: say whether the sub was cited.
- Open cases (citations not final yet) are provisional; say so when you mention them.
- If the question could mean more than one sub (e.g. "the electrician" with two electrical subs), call \
ask_which_sub instead of guessing.
- Never assume a name that only partly matches means a project sub ("Lee Electric" is not "Lee Steel \
Erectors"): ask whether they mean that sub or a company that isn't on the project.
- For a company that is not on the project, you need its name, city and state before calling \
lookup_company; ask for whatever is missing, and say its result is unconfirmed.
- When you name a sub, use its name from the project list.
- If a tool returns needs_confirmation, tell the foreman the GC has to confirm that sub's possible matches \
with red flags first.
- If a result has open_match_questions, add one line saying those records wait for the GC's answer and \
aren't counted.
- If no tool can answer, call report_unanswerable and say what you can't answer."""

HAZARD_FALLBACK = ["fall_protection", "scaffolds", "ladders", "electrical", "excavation_trenching", "cranes_rigging",
                   "ppe", "health_silica_lead_asbestos_noise", "heat", "hazcom", "safety_program_training",
                   "recordkeeping", "general_duty", "fire_explosion", "motor_vehicles_equipment",
                   "steel_concrete_masonry", "other"]


def _hazard_codes() -> list[str]:
    try:
        codes = [r["hazard_code"] for r in warehouse.rows("SELECT hazard_code FROM ref.hazard_category ORDER BY 1")]
    except Exception:
        codes = []
    return codes or HAZARD_FALLBACK


def _traceable(fn):
    if config.TRACING:
        from langsmith import traceable
        return traceable(name="foreman.answer", run_type="chain")(fn)
    return fn


def _context(project: dict, subs: list[dict]) -> str:
    lines = [f"Project: {project['name']} (job-site state {project['state'] or 'not set'}; "
             f"lookback window {project['lookback_years']} years). OSHA data as of {warehouse.meta()['data_as_of']}.",
             "Subs on this project (use these ids):"]
    for s in subs:
        where = ", ".join(x for x in (s["entered_city"], s["entered_state"]) if x)
        lines.append(f"- sub_id {s['sub_id']}: {s['entered_name']}" + (f" ({where})" if where else "")
                     + (f", trade: {s['trade']}" if s["trade"] else ""))
    return "\n".join(lines)


def _fallback_text(outputs: list) -> str:
    """Deterministic rendering used when the model's answer can't be verified (or never arrives)."""
    for out in reversed(outputs):
        if "subs" in out:
            return "Here is the scorecard straight from the data:\n" + "\n".join(
                f"- {r['sub']}: {r['verdict']}" + (f" ({'; '.join(r['top_reasons'])})" if r["top_reasons"] else "")
                for r in out["subs"])
        if "reasons" in out:
            return f"{out['sub']}: {out['verdict']}\n" + "\n".join(f"- {r['label']}" for r in out["reasons"][:4])
        rows = out.get("events") or out.get("cases") or out.get("inspections") or out.get("inspection_list")
        if rows and isinstance(rows, list) and isinstance(rows[0], dict) and "inspection_id" in rows[0]:
            return "Straight from the records:\n" + "\n".join(
                f"- #{r['inspection_id']}, " + ", ".join(str(r[k]) for k in ("kind", "status", "date", "opened", "city",
                                                                            "state") if r.get(k))
                + (f", {r['citations']} citations" if isinstance(r.get("citations"), int) else "")
                for r in rows[:8])
    return "I couldn't verify the figures for that answer. Please check the sub's detail page."


def _log(project_id, question, status, answer, tool_log, ungrounded, usage, started, chat_id, user_id):
    with pg.conn() as c:
        c.execute("""INSERT INTO app.question_log (project_id, question, status, answer, tools, ungrounded, model,
                                                    input_tokens, output_tokens, latency_ms, chat_id, user_id)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                  [project_id, question, status, answer, json.dumps(tool_log, default=str), json.dumps(ungrounded),
                   llm.model_label("foreman"), usage[0], usage[1], int((time.time() - started) * 1000), chat_id,
                   user_id])


@_traceable
def answer(project: dict, question: str, history: list[dict], *, chat_id: str | None = None,
           user_id: str | None = None) -> S.AskResponse:
    """`history` is the chat's earlier messages ({role, content}, oldest first), read from the database."""
    started = time.time()
    if not llm.available("foreman"):
        return S.AskResponse(status="no_api_key", answer="The question assistant needs an AI key, which isn't set up "
                             "on this deployment. The scorecard and sub pages still show everything.")
    if not llm.budget_ok():
        return S.AskResponse(status="no_api_key", answer="Today's question budget is used up. The scorecard and sub "
                             "pages still show everything.")
    with pg.conn() as c:
        subs = c.execute("SELECT * FROM app.project_sub WHERE project_id = %s ORDER BY position", [project["project_id"]]).fetchall()
    if not subs:
        return S.AskResponse(status="answered", answer="There are no subs on this project yet. Add them on the scorecard first.")

    provider = llm.get("foreman")
    tb = Toolbox(project, subs)
    tools = specs([str(s["sub_id"]) for s in subs], _hazard_codes())
    system = SYSTEM + "\n\n" + _context(project, subs)
    messages = [provider.user_message(h["content"]) if h.get("role") == "user" else {"role": "assistant", "content": h["content"]}
                for h in history[-8:] if h.get("content")]
    messages.append(provider.user_message(question))

    outputs, tool_log, clarify, status = [], [], [], "answered"
    usage = [0, 0]
    retried, nudged, final, ungrounded = False, False, "", []
    history_text = " ".join(h.get("content", "") for h in history) + " " + question
    for _ in range(MAX_TURNS):
        reply = provider.chat(system, messages, tools)
        usage[0] += reply.input_tokens
        usage[1] += reply.output_tokens
        if reply.stop_reason == "refusal":
            final, status = "I can't help with that question.", "unanswerable"
            break
        if reply.tool_calls:
            messages.append(reply.assistant_message)
            results = []
            for call in reply.tool_calls:
                try:
                    out = tb.run(call.name, call.input)
                    err = "error" in out
                except Exception as e:  # a failed tool goes back to the model as an error result
                    out, err = {"error": str(e)}, True
                outputs.append(out)
                tool_log.append({"tool": call.name, "input": call.input, "error": err})
                if call.name == "ask_which_sub":
                    clarify = out.get("clarify", [])
                if call.name == "report_unanswerable":
                    status = "unanswerable"
                results.append((call, json.dumps(out, default=str), err))
            messages.extend(provider.tool_results(results))
            if clarify:
                final, status = "Which sub do you mean?", "clarify"
                break
            continue
        final = reply.text.strip()
        if not final:  # the model occasionally ends its turn with no text: ask once, then fall back
            if not nudged:
                nudged = True
                messages.append(provider.user_message("Please give the foreman your answer now, using only the "
                                                      "tool results above."))
                continue
            final, status = _fallback_text(outputs), "guard_failed"
            break
        ungrounded = grounding.check(final, outputs, history_text)
        if ungrounded and not retried:
            retried = True
            messages.append(reply.assistant_message)
            messages.append(provider.user_message(
                "Some figures in your answer don't appear in the tool results: " + ", ".join(ungrounded[:10])
                + ". Rewrite the answer quoting only figures that appear in the tool results."))
            continue
        if ungrounded:
            final, status = _fallback_text(outputs), "guard_failed"
        break
    else:  # out of turns: never return an empty or unverified answer
        if not final or ungrounded:
            final, status = _fallback_text(outputs), "guard_failed"

    if any(o.get("status") == "needs_confirmation" for o in outputs) and status == "answered":
        status = "needs_confirmation"
    ids = grounding.cited_ids(final, outputs)
    coverage = None
    if len(tb.used_subs) == 1:
        coverage = Q.coverage(tb.data(tb.used_subs[0])).sentence
    elif tb.used_subs:
        m = warehouse.meta()
        coverage = (f"Covers {len(tb.used_subs)} subs' matched OSHA records; data as of {m['data_as_of']}; "
                    f"accident details published through {m['accident_detail_through']}.")
    llm.record_usage(*usage)
    _log(project["project_id"], question, status, final, tool_log, ungrounded, usage, started, chat_id, user_id)
    return S.AskResponse(status=status, answer=final, coverage=coverage,
                         citations=[S.Citation(activity_nr=i, url=Q.url(i)) for i in ids],
                         clarify_options=[S.ClarifyOption(sub_id=c["sub_id"], name=c["name"]) for c in clarify],
                         tools_used=list(dict.fromkeys(t["tool"] for t in tool_log)))
