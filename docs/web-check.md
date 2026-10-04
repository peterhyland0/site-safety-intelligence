# Web check: asking the web whose record it is

**What it does.** The Matches section of a sub's page has a button, "Check N records on the web". For each of the
sub's undecided records (possible or excluded, decided by the rules or the AI) it runs one web search for the record's
name and address and asks which company the pages tie to that place. What it finds comes back as a question to the
GC, with the page and a quote under each record:

> Web pages tie these OSHA records to your sub's company or its affiliates: 'CLARK CONSTRUCTION GROUP CALIFORNIA' at
> 7677 OAKPORT ST, OAKLAND CA (9 inspections, red flags): Clark Construction Group - California, part of Clark
> Construction Group; 'CLARK CONSTRUCTION GROUP' at 800 K ST NW, WASHINGTON DC (5 inspections): Clark Construction
> Group, clarkconstruction.com; … Are these the same company as your sub 'Clark Construction Group'?

It only suggests. Nothing is matched or excluded until the GC answers, and a Yes or No is a GC decision that survives
data refreshes. Code: [ssi/llm/web_check.py](../ssi/llm/web_check.py) (the search, the checks, the comparison, the
cache) and [ssi/matching/verify.py](../ssi/matching/verify.py) (which records, what's written, the questions).

## Why

Rules and the adjudicator see only OSHA's data, and a generic name leaves many records undecided. For Clark
Construction Group (Bethesda MD), 26 of the 43 possible and excluded records were Clark's own: job sites (800 K St NW),
offices (McLean VA), its state entities ("CLARK CONSTRUCTION GROUP - CALIFORNIA, LP", which rule X1 excludes for the
extra word) and subsidiaries. 14 were other Clarks (Lansing MI, McComb MS). The GC was checking them one by one in a
search engine's AI mode. That worked, with two failures this design avoids: the assistant was handed the app's own
labels ("X3, different company") and repeated them, and it had no way to show where an answer came from.

## How it runs

```
"Check N records on the web" (POST /api/projects/{p}/subs/{s}/web-check, under the sub's claim)
  0. no company profile yet? look the company up first (one search; as "Look up this company")
  1. candidates: possible/excluded, method rule|llm|llm_rejected, not waiting for the AI, not in an open question,
     not checked in 90 days; one group per OSHA name at a place, red-flagged first, then possible, then most inspections
  2. identify, per group (cached per record, so one search serves every sub with it):
       Tavily basic search "<name> <street> <city> <state>" (osha.gov, dol.gov excluded) → pages naming the company
       → the adjudicator LLM: which company is at this place? It's told nothing about the sub or the app's buckets
  3. checks (identity()): the quote must be verbatim on the page it cites, name the record's city or street, and
     name the company; a website counts only if a page shows it and it isn't a directory (LinkedIn, BuildZoom…)
  4. compare with the sub (compare()): the company's or its parent's website is the sub's (from its profile) → same;
     a website of its own and no parent → different; otherwise a short LLM call with no pages → same / affiliate /
     different / unsure
  5. write, and ask (one transaction; a record the GC moved meanwhile isn't touched)
```

| Result | Record possible | Record excluded |
|---|---|---|
| same (own, parent or affiliate) | held: possible, method `web`, in a "same" question | moved to possible, method `web`, in the "same" question |
| different | held: possible, method `web`, in a "different" question | stays excluded; the finding is kept |
| unsure | stays as it is; the finding is kept | stays as it is; the finding is kept |

Every checked record keeps what was found in its evidence (`web_check`: verdict, company, page, quote) and isn't
checked again for 90 days. A failed search leaves no mark, so the next press tries it again. A re-match keeps `web`
rows as it keeps every non-rule row.

**Web questions don't hold anything up.** Questions about red-flagged records keep a sub's verdict at Review and stop
the foreman assistant from answering about it until the GC confirms. Web questions do neither: they're suggestions
about records that don't count yet.

## Limits and cost

- One Tavily basic search (1 credit) and one or two adjudicator LLM calls per record group; cached in
  `app.web_lookup` for 90 days.
- A press starts at most 25 new searches, and none after 60 seconds; it returns within about 80 seconds (Vercel's
  proxy gives up at 120). A search still running finishes in the background and is cached for the next press, which
  continues where this one stopped.
- `SSI_DAILY_WEB_CHECK_LIMIT` (default 100 a day) counts every search started, failed ones included, apart from the
  company profiles' own limit. Tavily's free tier is 1,000 searches a month.
- `SSI_WEB_CHECK=off` hides the button. It needs `TAVILY_API_KEY` and the adjudicator LLM.

## Privacy

A sub whose name is a person's (a sole proprietor) is never searched, and neither is a record whose name is a
person's. Only a record's name and address go to the search; the sub's name goes only to the comparison call, with no
pages.

## How well it works

On the 43 records Clark Construction Group's lookup returned, each checked by hand ([eval/web_check](../eval/web_check/results.md),
36 searches, DeepSeek V4.1 Flash reading the pages):

| Records | n | right | wrong "same" | wrong "different" | unsure |
|---|---|---|---|---|---|
| Clark's own | 26 | 20 | 0 | 0 | 6 |
| likely Clark's | 3 | 0 | 0 | 0 | 3 |
| other companies | 14 | 9 | 0 | 0 | 5 |
| excluded in the app | 25 | 16 | 0 | 0 | 9 |

- **No wrong answers either way.** The number that matters most is a wrong "same": it puts another company's history
  in front of the GC as the sub's. The first version made one: a roofer in Sioux Falls, "Clark Construction, LLC",
  which the name-only comparison took for Clark Construction Group. A "same" now needs the sub's website or a parent
  the page names; alike names alone are "unsure". That rule also turned two right answers (Clark Concrete, Reno) into
  "unsure".
- **7 of Clark's 10 own excluded records come back "same"** (the California, Chicago and Texas entities, the Golden
  office under Guy F. Atkinson): the records the rules can't reach.
- **Unsure is mostly the search, not the check:** job sites (1901 S Bell St, Sacramento) and PO boxes rarely have a
  page that names the builder at that address.
- Matching the company's name anywhere on a page, not just in the excerpt, found 800 K St (Clark's projects page) and
  Clark's own Bethesda office, which the first version missed.

Re-running the eval costs nothing: its answers are cached in eval/web_check/lookups.jsonl, and Tavily's raw
responses locally in searches.jsonl, so changes to the excerpts or prompts re-run without a search on the machine that
ran it.
