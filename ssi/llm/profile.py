"""Company profile: who a sub is and where it works, from the web, with a quoted source for every location.

Built once per company by Claude with Anthropic's built-in web search (and web fetch for a locations page), cached
in app.company_profile, and used to ask the GC about the OSHA records at those locations
(ssi.matching.adjudicate.profile_questions). Nothing is matched from it automatically: the GC answers.

Every location must quote the page it came from, and the quote must be in text the call actually read (a fetched
page or a search citation) with the city in it; a street counts only if its house number and street are in the
quote too. Anything else is dropped (check()). Why and how: docs/company-profile.md.

Two backends (SSI_PROFILE_BACKEND): claude (the default; Claude with web search and fetch, ~$0.20 and ~30 s a
profile) or tavily (one Tavily search, then the adjudicator LLM reads the pages: ~$0.01 and a few seconds). Both
reports go through the same check().

Env: claude needs an Anthropic credential (ANTHROPIC_API_KEY, or CLAUDE_API_KEY) and takes SSI_PROFILE_MODEL (default
claude-sonnet-5-5); tavily needs TAVILY_API_KEY and the adjudicator LLM (ssi/llm/client.py). SSI_PROFILE=off switches
profiles off; SSI_DAILY_PROFILE_LIMIT caps them (default 100 a day, 30 with tavily to stay inside its free 1,000 a
month; every attempt counts)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from urllib.parse import urlsplit

import httpx

from ssi import config
from ssi.matching.rules import norm_city
from ssi.store import pg, warehouse

log = logging.getLogger(__name__)

PROMPT_VERSION = 2  # 2: fetch the company's own page before reporting (snippet-only locations can't be checked)
DEFAULT_MODEL = "claude-sonnet-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"  # as ssi/llm/anthropic_provider.py
TTL_DAYS = 90
BUILDING_STALE_MINUTES = 10  # a 'building' row older than this was abandoned
BUILDING_POLL_SECONDS = 3  # how often a request checks on another one building the same profile
MAX_ROUNDS = 5  # the first request, up to 3 pause_turn resumes, and one nudge to report

SYSTEM = """You identify a construction subcontractor from what a general contractor (GC) typed, and list the \
locations the company itself publishes.

Work in this order: search (two or three searches are usually enough) to find the company and its website; then \
open its own locations, contact or about page with web fetch; then report. Locations you only saw in search \
snippets can't be checked and are discarded, so fetch the page that lists them.

Finish by calling report_profile:
- found=false if nothing turns up, or several companies share the name and nothing you were given narrows it down. \
Say why in note.
- name: the company's name as it publishes it; website: its domain; summary: what it does, in a few words.
- locations: only places this company itself operates (headquarters, offices, branches, plants, yards, shops). \
Never parent, sister or affiliate companies, customers, or projects and job sites. Give each the page URL and a \
short quote copied exactly from that page that contains the address or at least the city.

Copy quotes verbatim. Don't fill in an address, zip or city you didn't read."""

REPORT_TOOL = {
    "name": "report_profile",
    "description": "Report the company and the locations it publishes. Call this once, at the end.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["found", "name", "website", "summary", "note", "locations"],
        "properties": {
            "found": {"type": "boolean"},
            "name": {"type": ["string", "null"]},
            "website": {"type": ["string", "null"]},
            "summary": {"type": ["string", "null"]},
            "note": {"type": ["string", "null"]},
            "locations": {"type": "array", "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["address", "city", "state", "zip", "kind", "source_url", "quote"],
                "properties": {
                    "address": {"type": ["string", "null"], "description": "Street address, without city/state/zip"},
                    "city": {"type": "string"},
                    "state": {"type": "string", "description": "Two-letter US state code"},
                    "zip": {"type": ["string", "null"]},
                    "kind": {"type": "string", "enum": ["headquarters", "office", "branch", "plant", "yard", "shop", "other"]},
                    "source_url": {"type": "string"},
                    "quote": {"type": "string", "description": "Verbatim text from source_url with the address or city"},
                },
            }},
        },
    },
}


def backend() -> str:
    return "tavily" if os.environ.get("SSI_PROFILE_BACKEND", "").strip().lower() == "tavily" else "claude"


def model() -> str:
    """The model in the cache key: Claude's, or the Tavily backend's version plus the LLM that reads the pages."""
    if backend() == "tavily":
        from ssi.llm import client as llm
        return f"tavily-v{TAVILY_VERSION}+{llm.get('adjudicator').model}"
    return os.environ.get("SSI_PROFILE_MODEL", "").strip() or DEFAULT_MODEL


def tools() -> list[dict]:
    return [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 4, "citations": {"enabled": True}},
            REPORT_TOOL]


def _api_key() -> str | None:
    return next((v for v in (os.environ.get(n, "").strip() for n in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")) if v), None)


def available() -> bool:
    if os.environ.get("SSI_PROFILE", "on").strip().lower() == "off":
        return False
    if backend() == "tavily":
        from ssi.llm import client as llm
        return bool(_tavily_key()) and llm.available("adjudicator")
    return bool(_api_key() or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def m3_check_enabled() -> bool:
    """The M3 web check (ssi.matching.adjudicate.check_m3): on with the Tavily backend (a cent a lookup), off with
    Claude (twenty cents) unless SSI_M3_WEB_CHECK=on; SSI_M3_WEB_CHECK=off switches it off."""
    v = os.environ.get("SSI_M3_WEB_CHECK", "").strip().lower()
    return available() and (v == "on" if v in ("on", "off") else backend() == "tavily")


def daily_limit() -> int:
    return int(os.environ.get("SSI_DAILY_PROFILE_LIMIT", "").strip() or (30 if backend() == "tavily" else 100))


# --- what the prompt is told -----------------------------------------------------------------------------------
def context(sub: dict, search_state: str | None, rows: list[dict]) -> dict:
    """Everything the prompt says about the sub: the GC's input, OSHA's spelling, and where its matched records are.
    `rows` are the sub's app.sub_match rows."""
    with_ev = [(r, r["evidence"]) for r in rows if r.get("evidence")]
    query = next((e["query"] for _, e in with_ev if e.get("query")), None) or {}
    matched = sorted((e for r, e in with_ev if r["bucket"] == "matched"), key=lambda e: -(e.get("inspections") or 0))[:5]
    return {
        "name": sub["entered_name"], "city": sub.get("entered_city"), "state": search_state,
        "trade": sub.get("trade"), "osha_spelling": query.get("clean"), "tier": query.get("tier"),
        "matched_at": [", ".join(x for x in (e.get("address"), e.get("city"), e.get("state"), e.get("zip")) if x)
                       for e in matched],
    }


def user_prompt(ctx: dict) -> str:
    lines = [(f"The GC's sub: name '{ctx['name']}', city '{ctx.get('city') or 'not given'}', "
              f"state '{ctx.get('state') or 'not given'}', trade '{ctx.get('trade') or 'not given'}'.")]
    if ctx.get("osha_spelling"):
        lines.append(f"OSHA's records spell the name '{ctx['osha_spelling']}'.")
    if ctx.get("matched_at"):
        lines.append("OSHA records already matched to this sub are at: " + "; ".join(ctx["matched_at"]) + ".")
    lines.append("Which company is this, and which locations does it list?")
    return "\n".join(lines)


def profile_key(ctx: dict, model_name: str) -> str:
    return hashlib.sha256(json.dumps({"v": PROMPT_VERSION, "model": model_name, **ctx}, sort_keys=True,
                                     default=str).encode()).hexdigest()


# --- the Claude call ---------------------------------------------------------------------------------------------
def client():
    import anthropic
    key = _api_key()  # else the SDK finds ANTHROPIC_AUTH_TOKEN or a login profile itself
    c = anthropic.Anthropic(timeout=180.0, max_retries=1, **({"api_key": key} if key else {}))  # a retry re-pays searches
    if config.TRACING:
        from langsmith.wrappers import wrap_anthropic
        c = wrap_anthropic(c)
    return c


def _as_dict(x) -> dict:
    return x if isinstance(x, dict) else x.model_dump(mode="json")


def _norm_url(url: str) -> str:
    u = urlsplit((url or "").strip())
    return (u.netloc.lower().removeprefix("www.") + u.path.rstrip("/")).lower()


def _collect(content: list[dict], texts: dict[str, list[str]], titles: dict[str, str]) -> None:
    """Readable text per page from one response: fetched documents, search citations' cited text, titles."""
    for b in content:
        t = b.get("type")
        if t == "web_fetch_tool_result":
            res = b.get("content") or {}
            doc = res.get("content") or {}
            src = doc.get("source") or {}
            if res.get("type") == "web_fetch_result" and src.get("type") == "text" and src.get("data"):
                texts.setdefault(_norm_url(res.get("url")), []).append(src["data"])
                if doc.get("title"):
                    titles[_norm_url(res.get("url"))] = doc["title"]
        elif t == "web_search_tool_result" and isinstance(b.get("content"), list):  # an error is an object, not a list
            for r in b["content"]:
                if r.get("url") and r.get("title"):
                    titles.setdefault(_norm_url(r["url"]), r["title"])
        elif t == "text":
            for cit in b.get("citations") or []:
                if cit.get("url") and cit.get("cited_text"):
                    texts.setdefault(_norm_url(cit["url"]), []).append(cit["cited_text"])


def research(ctx: dict, http=None) -> dict:
    """{report, texts, titles, searches, usage, model, error}. `report` is report_profile's input or None."""
    if backend() == "tavily":
        return research_tavily(ctx)
    http = http or client()
    messages = [{"role": "user", "content": user_prompt(ctx)}]
    texts: dict[str, list[str]] = {}
    titles: dict[str, str] = {}
    out = {"report": None, "searches": 0, "usage": {"input_tokens": 0, "output_tokens": 0}, "model": model(),
           "error": None}
    nudged = False
    for _ in range(MAX_ROUNDS):
        resp = http.beta.messages.create(
            model=model(), betas=[FALLBACK_BETA], fallbacks="default", max_tokens=16000, system=SYSTEM,
            tools=tools(), tool_choice={"type": "auto"}, output_config={"effort": "medium"}, messages=messages)
        d = _as_dict(resp)
        u = d.get("usage") or {}
        out["usage"]["input_tokens"] += u.get("input_tokens") or 0
        out["usage"]["output_tokens"] += u.get("output_tokens") or 0
        out["searches"] += ((u.get("server_tool_use") or {}).get("web_search_requests") or 0)
        out["model"] = d.get("model") or out["model"]
        content = d.get("content") or []
        _collect(content, texts, titles)
        report = next((b.get("input") for b in content if b.get("type") == "tool_use" and b.get("name") == "report_profile"), None)
        if report is not None:
            out["report"] = report
            break
        stop = d.get("stop_reason")
        if stop == "refusal":
            out["error"] = "refused"
            break
        assistant = {"role": "assistant", "content": getattr(resp, "content", content)}
        if stop == "pause_turn":  # the server-side search loop paused: send the turn back and it resumes
            messages = [*messages, assistant]  # consecutive assistant turns are joined by the API
            continue
        if nudged:
            out["error"] = f"no report ({stop})"
            break
        nudged = True
        messages = [*messages, assistant, {"role": "user", "content": "Report what you found with report_profile."}]
    else:
        out["error"] = "too many rounds"
    out["texts"] = {k: "\n".join(v) for k, v in texts.items()}
    out["titles"] = titles
    return out


# --- the Tavily backend: one search, then the adjudicator LLM reads the pages -----------------------------------
# One basic Tavily search (1 credit) returns up to 5 pages' text; pages that don't name the company are dropped and
# the rest are cut to PAGE_CHARS. The adjudicator LLM writes report_profile's report from them, and check() holds
# it to exactly the text it was shown, as it does Claude's.
TAVILY_URL = "https://api.tavily.com"
TAVILY_VERSION = 2  # in the cache key: the query, the page selection and trimming, EXTRACT_SYSTEM
# 2: search the cleaned spelling, unquoted; a page needs only the name's first word (v1 dropped "317727255 - …"
#    names and pages that say "Sunrun" for SUNRUN INSTALLATION SERVICES)
PAGE_CHARS = 5000  # per page; long pages are mostly menus and footers
LEGAL_WORDS = {"INC", "LLC", "CO", "CORP", "CORPORATION", "COMPANY", "LTD", "LP", "LLP", "PLLC", "PC", "THE", "AND",
               "OF", "DBA"}

EXTRACT_SYSTEM = """You identify a construction subcontractor from what a general contractor (GC) typed, using the \
web search results you're given, and list the locations the company itself publishes.

Report:
- found=false if the results aren't about this company, or several companies share the name and nothing you were \
given narrows it down. Say why in note.
- name: the company's name as it publishes it; website: its domain; summary: what it does, in a few words.
- locations: only places this company itself operates (headquarters, offices, branches, plants, yards, shops). \
Never parent, sister or affiliate companies, customers, or projects and job sites. Give each the URL of the result \
it came from, exactly as given, and a short quote copied exactly from that result's text that contains the address \
or at least the city.

Copy quotes verbatim. Don't fill in an address, zip or city you didn't read."""


def _tavily_key() -> str | None:
    return os.environ.get("TAVILY_API_KEY", "").strip() or None


def search_name(ctx: dict) -> str:
    """The warehouse's cleaned spelling when known (no legal words or record numbers), else what the GC typed without
    a leading record number ("317727255 - PERFORMANCE CONTRACTING INC")."""
    return (ctx.get("osha_spelling") or "").strip() or re.sub(r"^\W*\d+\s*-\s*", "", ctx["name"]).strip()


def tavily_query(ctx: dict) -> str:
    return " ".join(x for x in (search_name(ctx), ctx.get("city"), ctx.get("state"), "contractor locations") if x)


def name_words(name: str) -> list[str]:
    """The name's words in order, without legal words."""
    words = re.findall(r"[A-Z0-9]+", (name or "").upper().replace("&", " AND "))
    return list(dict.fromkeys(w for w in words if w not in LEGAL_WORDS and (len(w) > 1 or w.isdigit())))


def tavily_search(query: str, http: httpx.Client | None = None, exclude: tuple[str, ...] = ("osha.gov",)) -> dict:
    """One basic search (1 credit), up to 5 results with their pages' text; never pages from `exclude`."""
    body = {"query": query, "search_depth": "basic", "max_results": 5, "include_raw_content": "text",
            "include_answer": False, "exclude_domains": list(exclude), "country": "united states", "include_usage": True}
    own = http is None
    http = http or httpx.Client(base_url=TAVILY_URL, timeout=30.0, headers={"Authorization": f"Bearer {_tavily_key()}"})
    try:
        for attempt in range(2):
            r = http.post("/search", json=body)
            if (r.status_code == 429 or r.status_code >= 500) and attempt == 0:
                time.sleep(2)
                continue
            if r.is_error:
                raise RuntimeError(f"Tavily HTTP {r.status_code}: {r.text[:200]}")
            return r.json()
    finally:
        if own:
            http.close()
    raise AssertionError("unreachable")


def pages(resp: dict, name: str) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """(texts, titles, urls) keyed by normalised URL, for the results with the name's first word (SUNRUN, HOEKSTRA,
    NPL); texts cut to PAGE_CHARS. Whether a page is really the company is for the LLM and check()."""
    want = name_words(name)[:1]
    texts, titles, urls = {}, {}, {}
    for r in resp.get("results") or []:
        text = re.sub(r"\s+", " ", r.get("raw_content") or r.get("content") or "").strip()[:PAGE_CHARS]
        title = (r.get("title") or "").strip()
        hay = f"{title} {text}".upper()
        if not (r.get("url") and text) or not all(re.search(rf"\b{re.escape(w)}\b", hay) for w in want):
            continue
        k = _norm_url(r["url"])
        texts[k], titles[k], urls[k] = text, title, r["url"]
    return texts, titles, urls


def research_tavily(ctx: dict, http: httpx.Client | None = None, provider=None) -> dict:
    """research()'s result from one Tavily search and one call to the adjudicator LLM."""
    out = {"report": None, "searches": 1, "usage": {"input_tokens": 0, "output_tokens": 0}, "model": model(),
           "error": None, "texts": {}, "titles": {}}
    resp = tavily_search(tavily_query(ctx), http)
    out["credits"] = (resp.get("usage") or {}).get("credits") or 1
    texts, titles, urls = pages(resp, search_name(ctx))
    out["texts"], out["titles"] = texts, titles
    if not texts:
        out["report"] = {"found": False, "name": None, "website": None, "summary": None, "locations": [],
                         "note": "No search result names the company."}
        return out
    if provider is None:
        from ssi.llm import client as llm
        provider = llm.get("adjudicator")
    results = "\n\n".join(f"[{i}] URL: {urls[k]}\nTitle: {titles[k] or '-'}\nText: {texts[k]}"
                           for i, k in enumerate(texts, 1))
    report, usage = provider.structured(EXTRACT_SYSTEM, f"{user_prompt(ctx)}\n\nSearch results:\n\n{results}",
                                        REPORT_TOOL["input_schema"], max_tokens=4096)
    out["usage"] = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
    if report is None:
        out["error"] = "no report"
    else:
        out["report"] = report
    return out


# --- checking the report against what was read --------------------------------------------------------------
def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").upper()).strip()


# listings and social sites, not a company's own website: never evidence of which company it is (eval/m3_audit)
DIRECTORIES = ("buildzoom.com", "procore.com", "linkedin.com", "facebook.com", "bbb.org", "yelp.com", "mapquest.com",
               "bizapedia.com", "dnb.com", "zoominfo.com", "manta.com", "opencorporates.com", "yellowpages.com",
               "angi.com", "houzz.com", "instagram.com", "x.com", "twitter.com")


def company_domain(profile: dict | None) -> str | None:
    """A found profile's own website, or None (not found, no website, or a directory or social site)."""
    d = (profile or {}).get("domain") if (profile or {}).get("found") else None
    return None if d and any(d == x or d.endswith("." + x) for x in DIRECTORIES) else d


def domain(website: str | None) -> str | None:
    if not website:
        return None
    host = urlsplit(website if "//" in website else "//" + website).netloc.lower().removeprefix("www.")
    return host or None


def _addr(address: str, quote: str) -> tuple[str | None, bool]:
    """The address's warehouse addr_key, and whether its house number and street word are in the quote."""
    r = warehouse.one("SELECT addr_key(?) AS k, addr_split_dir(clean_addr(?)) AS q", [address, quote])
    key = r["k"] if r else None
    if not key or key.startswith("POBOX"):
        return key, False
    num, word = key.split(" ", 1)
    return key, bool(re.search(rf"\b{re.escape(num)}\b.*\b{re.escape(word)}\b", r["q"] or ""))


def check(report: dict | None, texts: dict[str, str], titles: dict[str, str] | None = None, addr=_addr) -> dict:
    """The profile kept from the report: only locations whose quote is in text read from that page, with the city
    in it. A street (and zip) is kept only if the quote has it too; otherwise the location is kept at city level."""
    report = report or {}
    titles = titles or {}
    site = domain(report.get("website"))
    locations, dropped = [], 0
    for loc in report.get("locations") or []:
        url = loc.get("source_url") or ""
        quote = (loc.get("quote") or "").strip()
        page = _squash(texts.get(_norm_url(url), ""))
        city = norm_city(loc.get("city") or "")
        state = (loc.get("state") or "").strip().upper()
        if not (quote and city and len(state) == 2 and _squash(quote) in page and city in norm_city(quote)):
            dropped += 1
            continue
        address, key, zip5 = None, None, None
        if loc.get("address"):
            key, ok = addr(loc["address"], quote)
            if ok:
                address = loc["address"].strip()
                z = re.sub(r"\D", "", loc.get("zip") or "")[:5]
                zip5 = z if len(z) == 5 and z in re.sub(r"\D", " ", quote).split() else None
            else:
                key = None
        host = _norm_url(url).split("/", 1)[0]
        same = next((x for x in locations if (x["addr_key"], x["zip"], norm_city(x["city"]), x["state"])
                     == (key, zip5, city, state)), None)
        if same:  # e.g. headquarters and a division at one address: one location, both kinds
            kind = loc.get("kind") or "other"
            same["kind"] += "" if kind in same["kind"].split(", ") else f", {kind}"
            continue
        locations.append({
            "address": address, "addr_key": key, "city": (loc.get("city") or "").strip(), "state": state,
            "zip": zip5, "kind": loc.get("kind") or "other", "source_url": url, "quote": quote[:300],
            "own_site": bool(site) and (host == site or host.endswith("." + site)),
            "title": titles.get(_norm_url(url)),
        })
    found = bool(report.get("found")) and bool(report.get("name"))
    return {"found": found, "name": report.get("name") if found else None, "website": report.get("website"),
            "domain": site, "summary": report.get("summary"), "note": report.get("note"),
            "locations": locations if found else [], "dropped": dropped}


# --- cache and build ---------------------------------------------------------------------------------------------
def load(profile_id) -> dict | None:
    if not profile_id:
        return None
    with pg.conn() as c:
        r = c.execute("SELECT * FROM app.company_profile WHERE profile_id = %s", [profile_id]).fetchone()
    return _row(r) if r else None


def _row(r: dict) -> dict:
    p = dict(r["profile"] or {})
    return {**p, "profile_id": str(r["profile_id"]), "status": r["status"], "model": r["model"],
            "built_at": r["created_at"].isoformat() if r.get("created_at") else None}


def build(ctx: dict, http=None) -> dict | None:
    """The cached profile for this context, or a new one. When another request is building the same profile, waits
    for its result (until it finishes, fails, or is abandoned) rather than going on without one. None when the daily
    limit is reached or the search failed (the caller goes on without)."""
    m = model()
    key = profile_key(ctx, m)
    while True:
        with pg.conn() as c:
            c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [key])  # one builder per company at a time
            hit = c.execute(f"""SELECT * FROM app.company_profile WHERE profile_key = %s AND (
                                  (status IN ('found', 'not_found') AND created_at > now() - interval '{TTL_DAYS} days')
                                  OR (status = 'building' AND created_at > now() - interval '{BUILDING_STALE_MINUTES} minutes'))
                                ORDER BY created_at DESC LIMIT 1""", [key]).fetchone()
            if hit and hit["status"] != "building":
                return _row(hit)
            if not hit:
                today = c.execute("SELECT count(*) AS n FROM app.company_profile WHERE created_at >= current_date"
                                  ).fetchone()["n"]
                if today >= daily_limit():
                    log.warning("company profile limit reached (%s today)", today)
                    return None
                pid = c.execute("""INSERT INTO app.company_profile (profile_key, query, status, model)
                                   VALUES (%s, %s, 'building', %s) RETURNING profile_id""",
                                [key, json.dumps(ctx, default=str), m]).fetchone()["profile_id"]
                break
        time.sleep(BUILDING_POLL_SECONDS)  # the same company from another sub: use that search, don't pay twice
    try:
        res = research(ctx, http)
        prof = check(res["report"], res["texts"], res["titles"]) if not res["error"] else None
        status = "error" if prof is None else "found" if prof["found"] else "not_found"
        stored = prof or {"error": res["error"]}
        stored["usage"] = res["usage"]
    except Exception as e:  # noqa: BLE001 - a failed search never blocks adjudication
        log.warning("company profile failed (%s: %s)", type(e).__name__, e)
        status, stored, res = "error", {"error": f"{type(e).__name__}: {str(e)[:200]}"}, {"searches": 0, "model": m}
    with pg.conn() as c:
        r = c.execute("""UPDATE app.company_profile SET status = %s, profile = %s, searches = %s, model = %s
                         WHERE profile_id = %s RETURNING *""",
                      [status, json.dumps(stored, default=str), res.get("searches") or 0, res.get("model") or m, pid]).fetchone()
    return _row(r) if status != "error" else None


def for_sub(sub: dict, project: dict, force: bool = False) -> dict | None:
    """The profile to adjudicate a sub with. Built for a new sub (profile_status 'pending') with uncertain records,
    or on the "Look up this company" button (force) when it has undecided possible or excluded records; never for a
    person's name. The outcome is recorded on project_sub: done | skipped | error. None: nothing to use."""
    status = sub.get("profile_status")
    if status == "done" and not force:
        return load(sub.get("profile_id"))
    if status != "pending" and not force:
        return None
    sub_id = str(sub["sub_id"])
    with pg.conn() as c:
        rows = c.execute("SELECT * FROM app.sub_match WHERE sub_id = %s AND establishment_key <> '__note__'",
                         [sub_id]).fetchall()
    ctx = context(sub, sub.get("entered_state") or project.get("state"), rows)
    wanted = (any(r["method"] not in ("gc", "remap") and r["bucket"] in ("possible", "excluded") for r in rows) if force
              else any(r["needs_adjudication"] for r in rows))
    prof = None
    if available() and wanted and ctx.get("tier") != "person":
        prof = build(ctx)
        new_status = "done" if prof else "error"
    else:
        new_status = "skipped"
    with pg.conn() as c:
        c.execute("UPDATE app.project_sub SET profile_status = %s, profile_id = %s WHERE sub_id = %s",
                  [new_status, prof["profile_id"] if prof else sub.get("profile_id"), sub_id])
    return prof
