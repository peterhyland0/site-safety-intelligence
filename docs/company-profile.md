# Company profiles: asking the GC about a sub's other locations

**What it does.** When a new sub has uncertain OSHA records, Claude looks the company up on the web and builds a
short profile: its name, website, what it does, and the locations it lists, each with a quote from the page it came
from. OSHA records at those locations skip the AI adjudicator and go to the GC in one question:

> Tindall Corporation lists these addresses on tindallcorp.com, and OSHA has records there: 'TINDALL' at 5400 OLGERS
> RD, PETERSBURG VA (10 inspections, red flags); 'TINDALL CORPORATION VIRGINIA DIVISION' (another name) at 5400
> OLGERS RD, PETERSBURG VA (2 inspections); … Are these the same company as your sub 'Tindell Corporation'?

Nothing is matched from the web on its own: the GC's answer decides, and a Yes is a GC decision that survives data
refreshes. Code: [ssi/llm/profile.py](../ssi/llm/profile.py) (the search and the checks),
[ssi/matching/adjudicate.py](../ssi/matching/adjudicate.py) (`listed_records`, `profile_questions`, `apply_profile`),
[ssi/matching/candidates.py](../ssi/matching/candidates.py) (`at_listed_addresses`).

## Why

The rules and the adjudicator only see OSHA's data: names, addresses, years and trade codes. They can't tell that
"TINDALL, 5400 Olgers Rd, Petersburg VA" is a plant of Tindall Corporation of Spartanburg SC, though Tindall's website
lists it. So a sub's own history at its other locations mostly stayed "possible" and uncounted: on the held-out
adjudicator eval, Jev left 65 of 74 same-company records possible. The adjudicators' remaining mistakes are national
firms' branches in other states (NPL Construction, NVR). Both are facts the company publishes.

## How it runs

```
GC adds sub ─► rules (instant): the scorecard appears; uncertain records wait for the "Resolving…" step
                 └─► "Resolving…" (POST /adjudicate):
                       1. profile: Claude with web search (~20-40 s; cached per company; skipped for a person's name,
                          a sub with no uncertain records, or past the daily limit; a failure just carries on)
                       2. address lookup: OSHA records at the profile's addresses under any name (company's own site only)
                       3. records at listed locations skip the AI → one question to the GC
                       4. the AI on the rest, and red-flag questions, as before
```

- **Searched before the AI**, so a listed branch can't be excluded by the AI first, and each question is complete when
  it's created. The rules still run first: they decide in under a second whether a search is needed at all.
- **Subs added before profiles** get a "Look up this company" button on their page. It asks about their undecided
  possible and excluded records (including ones the AI excluded), and an open red-flag question about exactly those
  records gets the profile's evidence as its suggestion instead of a second question.
- **Records the profile routes to the GC** are written with method `profile` (possible until answered), which a
  re-match keeps, so the question's records stay put after a data refresh.

## What is checked

The profile comes from one Claude call (`claude-opus-5-5` by default) with Anthropic's web search and web fetch tools,
ending with a strict `report_profile` tool call. Then, in code:
- each location must quote text the call actually read from that page (a fetched page or a search citation), and the
  city must be in the quote; otherwise it's dropped;
- a street address and zip count only if the quote has them too; otherwise the location is kept at city level;
- the prompt asks for the company's own locations only, never parent, sister or affiliate companies, customers or
  job sites;
- the address lookup only uses locations quoted from the company's own site, skips shared office buildings, and is
  capped at 20 records per sub.

Records at a listed **address** are asked about with the suggestion "same"; records only in a listed **city** are asked
separately, with "unsure", since a common name can recur in one city.

## Cost and limits

About $0.20 a profile on Opus 5.5 (≈38k input tokens, mostly the pages it reads, plus 1-2 searches), ~20-40 s.
Profiles are cached for 90 days per company (rows in `app.company_profile` are immutable versions).
`SSI_DAILY_PROFILE_LIMIT` (default 100 a day) caps spending; `SSI_PROFILE=off` switches the step off;
`SSI_PROFILE_MODEL` changes the model (e.g. `claude-sonnet-5-5`).

## Privacy

The name, city and state a GC types, OSHA's spelling and the addresses of records already matched are sent to
Anthropic, whose web search runs the queries. Person-name subs (sole proprietors) are never looked up.

## Evaluation

An evaluation on the adjudicator eval's samples is in progress (eval/profile/, separate work): it compares no profile,
this question approach (graded on how often the suggestions point the right way, on the silver tax-ID labels), and
the profile as extra evidence for the AI adjudicator instead.

## Kept for later

- **Other names:** searching OSHA for names the company's site gives (former names, DBAs), only in the states it
  lists, distinctive names only, results into the question only. If the eval shows the address lookup missing a lot.
- **Automatic matching:** the GC confirms a profile once and a rule matches records at its listed addresses. Only if
  questions prove too many clicks; design notes in the plan (red-flagged records would still be questions, and it needs
  guards against a running adjudication overwriting the re-match).
- **Registries:** state business registries (OpenCorporates) or SAM.gov as sources alongside the web.
