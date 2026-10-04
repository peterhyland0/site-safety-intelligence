# Company profiles: asking the GC about a sub's other locations

**What it does.** When the GC ticks "Look up each company on the web first" while adding subs (off by default, since
each lookup costs Claude credits; shown only when the server has a Claude key) and a new sub has uncertain OSHA
records, Claude looks the company up on the web and builds a short profile: its name, website, what it does, and the
locations it lists, each with a quote from the page it came from. OSHA records at those locations skip the AI
adjudicator and go to the GC in one question:

> Tindall Corporation lists these addresses on tindallcorp.com, and OSHA has records there: 'TINDALL' at 5400 OLGERS
> RD, PETERSBURG VA (10 inspections, red flags); 'TINDALL CORPORATION VIRGINIA DIVISION' (another name) at 5400
> OLGERS RD, PETERSBURG VA (2 inspections); … Are these the same company as your sub 'Tindell Corporation'?

Nothing else is matched from the web on its own: the GC's answer decides, and a Yes is a GC decision that survives
data refreshes. The exception is a record under the sub's own name at an address on the company's own site, with no
red flags (rule M4): the name and the company's page agree, so it's matched, not asked. The website is the model's
pick, so M4 needs the site to list the company in the sub's state (and in its city, for a name that isn't distinctive):
a Denver QUALITY ROOFING found for a Nashville sub matches nothing. A record the rules excluded is asked, not matched.
Clark Construction Group's
profile question had asked about 'CLARK CONSTRUCTION GROUP' at each office on clarkconstruction.com (McLean, El Paso,
Houston, Chicago, Kansas City, Richmond). Code: [ssi/llm/profile.py](../ssi/llm/profile.py) (the search and the checks),
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
- **Subs added without the lookup** (or before profiles existed) get a "Look up this company" button on their page. It
  asks about their undecided possible and excluded records (including ones the AI excluded), and an open red-flag
  question about exactly those records gets the profile's evidence as its suggestion instead of a second question.
- **Records the profile routes to the GC** are written with method `profile` (possible until answered), which a
  re-match keeps, so the question's records stay put after a data refresh. If the rules later match one on OSHA's
  data alone (a rule change), and it has no red flags, the rule's match replaces the hold and the record leaves its
  question.
- **One company name, one answer** (rule C1). A question about a record under another company's distinctive name (an
  affiliate the site lists, like Guy F. Atkinson on clarkconstruction.com) covers that name's other records too: they
  join the question, red flags and all, and the GC's yes or no carries to them. Clark's question had named Atkinson's
  Costa Mesa office only, leaving out its 23 inspections at Clark's own head office and a 2018 cited fatality in Irvine.
  An answer (or a record moved by hand) carries only to records the GC hasn't decided and the sub hasn't matched, never
  to a red-flagged record that wasn't in the question, and a yes only within the states it was about. A name the sub's
  matched records go by is the sub's own (WHITING TURNER CONTRACTING for "Whiting-Turner"): excluding one of its
  records is about that place, and carries nowhere.
- **Saved profiles follow cleaning changes.** A location's address key is worked out again from its address each time
  it's used, so a profile saved before a rule change (7900 WESTPARK, now 7900 PARK) still finds its records.

## What is checked

The profile comes from one Claude call (`claude-sonnet-5-5` by default) with Anthropic's web search and web fetch tools,
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

About $0.20 a profile on Sonnet 5.5 (≈80k input tokens, mostly the pages it reads, plus 2-3 searches), median ~30 s
and under a minute (43 profiles in [eval/profile](../eval/profile/results-seed7-cached.md)).
Profiles are cached for 90 days per company (rows in `app.company_profile` are immutable versions).
`SSI_DAILY_PROFILE_LIMIT` (default 100 a day) caps spending; `SSI_PROFILE=off` switches the step off;
`SSI_PROFILE_MODEL` changes the model (e.g. `claude-opus-5-5`).

## The M3 web check

Rule M3 matches the same distinctive name in another state. With a profile, an M3 record in a state the profile
doesn't list has its own company looked up (`adjudicate.check_m3`, up to 5 a sub, matched records before the guard's,
cached like any profile): another company's website sends it back to the adjudicator (rule M3w), the sub's own
website confirms it, no website leaves it as it was. Records the rules' M3 guard held back (M3u) are restored when
the profile lists their state or the lookup finds the sub's website. Records the address check held back (M3a:
another company's office) aren't looked up; they wait for the adjudicator. Why: [eval/m3_audit/review.md](../eval/m3_audit/review.md). On by default with the
Tavily backend; with Claude (twenty cents a lookup) only with `SSI_M3_WEB_CHECK=on`.

## Two backends

`SSI_PROFILE_BACKEND` picks how a profile is built; both reports go through the same checks above.

- **claude** (the default): Claude with web search and web fetch, as described above.
- **tavily**: one basic Tavily search (5 results, page text cut to 5,000 characters, `osha.gov` excluded, results
  without the name's first word dropped, apostrophes aside or with its first two words run together), then the
  adjudicator LLM (DeepSeek V4.1 Flash) writes the same `report_profile` report from those pages, and the checks hold
  it to exactly the text it was shown. It searches the warehouse's cleaned spelling when known (record numbers and
  legal words gone, OSHA's apostrophes kept: MCKENNEY'S, since a search for MCKENNEYS finds nothing), unquoted. A GC's
  slip is searched as the spelling correction fixed it ("Aboe Board" as ABOVE BOARD CONTRACTING). Needs
  `TAVILY_API_KEY`.

Compared on the same 43 companies (eval/profile, seed 7; [Claude](../eval/profile/results-seed7-cached.md),
[Tavily](../eval/profile/results-seed7-tavily.md)):

| | Claude (Sonnet 5.5) | Tavily + DeepSeek |
|---|---|---|
| Found the company | 43 of 43 | 40 of 43 |
| Locations a found profile (share from the company's own site) | 1.8 (100%) | 4.4 (69%) |
| Cost a profile / median time | $0.20 / 32 s | $0.01 / 3 s |
| Jev with the profile (61 cases): same matched, wrong exclusions, wrong merges, lookalikes excluded | 3, 0, 0, 24 | 2, 1, 1, 25 |
| Question approach: same-company records asked about, misleading "same" suggestions | 3, 4 | 6, 3 |

Close on a small sample. Only own-site locations drive the address lookup, so Tavily's directory listings add
context and city-level questions, not lookups. Tavily's one extra wrong exclusion is NPL Construction: its profile gave the parent's site
(centuri.com) and only Tulsa and Greenwood, and Jev read the short list as evidence against Las Vegas. Its one wrong
merge is Big-D Construction in Salt Lake City, where the company's own pages list both offices, so the silver label
(different tax IDs) is likely the error. A sparse profile can mislead either backend.

## Privacy

The name, city and state a GC types, OSHA's spelling and the addresses of records already matched are sent to
Anthropic, whose web search runs the queries (with tavily: the name, city and state go to Tavily, and its pages to the
adjudicator LLM). Person-name subs (sole proprietors) are never looked up.

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
