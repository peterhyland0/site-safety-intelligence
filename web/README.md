# web/: Site Safety Intelligence front end

Vite + React + TypeScript + Tailwind CSS v4 + react-router. Mobile-first (designed at 375 px), light and dark
via `prefers-color-scheme`, system font stack, no UI kit. In production FastAPI serves `web/dist` at `/`
(with an SPA fallback to `index.html`) and the API at `/api` on the same origin, so the app only uses relative
`/api/...` URLs.

## Run

Requires Node 20+.

```bash
cd web
npm install

# Mock mode: no backend needed, fixtures from src/mock/
npm run dev:mock            # = VITE_MOCK=1 vite  → http://localhost:5173

# Real mode: Vite proxies /api to the FastAPI app on :8000 (override with SSI_API_URL)
npm run dev

npm run build               # type-checks, then writes web/dist (served by FastAPI)
npm run typecheck
npm run lint
npm test                    # vitest + Testing Library
```

A mock build (`VITE_MOCK=1 npm run build`) is a fully static demo; the normal build tree-shakes the mock
code out entirely.

## Pages

| Route | What it is |
|---|---|
| `/` | Projects list and "New project" (name, job-site state, lookback 3/5/10 years) |
| `/projects/:projectId` | GC scorecard: lookback toggle, data-as-of, bulk "Add subs" paste box with preview, ranked sub cards, CSV export, link to the foreman assistant. Subs with `match_status: needs_adjudication` show "Resolving N uncertain records…" while the page calls `/adjudicate` (max 2 at a time) and swaps in the returned card. |
| `/projects/:projectId/subs/:subId` | Sub detail: verdict, every reason with evidence links, yes/no match questions, red flags, yearly trend chart, hazards, open cases (provisional), injury rates and licence, the three match buckets with a bucket override, the paged inspection list (rows expand to citations and accident narratives), data-quality notes |
| `/projects/:projectId/ask` | Foreman chat, phone-first: suggested questions, markdown answers, osha.gov citation chips, coverage line, clarify options as buttons ("I mean …"), friendly copy for `needs_confirmation`, `unanswerable`, `guard_failed`, `no_api_key` |
| `/methodology` | Verdict rules, matching buckets, sources and limits |

## Structure

```
src/
  api/types.ts        TypeScript mirror of ssi/api/schemas.py (same field names; change both together)
  api/client.ts       typed fetch wrapper, friendly errors (401/403 → "Access required"), mock switch
  api/useApi.ts       tiny fetch hook: keeps previous data on reload (no skeleton flash), drops stale responses
  pages/              one file per route
  components/         SubCard, VerdictChip, AddSubsBox, TrendChart, InspectionList, MatchBuckets, EvidenceSections, …
  lib/parseSubs.ts    bulk paste parser (commas or tabs, "Dallas TX", "ABC, Inc.", header rows, state names, dupes)
  lib/markdown.tsx    small markdown → React renderer for answers (no innerHTML; http(s)/relative links only)
  lib/useAdjudication.ts  queue for POST /adjudicate
  mock/               in-memory backend for VITE_MOCK=1
  test/               vitest specs (parser, markdown, scorecard, chat)
```

## Design notes

- **Verdicts never rely on colour alone.** Each chip has an icon and text. "No OSHA record" is deliberately
  different from "No flags": dashed outline, a question-mark icon, neutral colour and the sentence "unknown, not
  clean"; it sorts above clean records so the GC follows up.
- Tone is neutral: labels and reasons come from the server ("Fatality investigation where this employer was cited
  for serious violations (2022)"); the UI adds no adjectives.
- Blank penalties render as "not recorded", never $0. Open cases are marked provisional everywhere.
- The trend chart is three small-multiple column charts (inspections, citations, serious+) on one year axis, one
  colour, a shaded lookback window, hover/tap and arrow-key readout, and a "Show as table" twin.
- Contrast was checked for the text and verdict token pairs (≥ 4.5:1 in both themes); focus rings are visible;
  primary tap targets are 44 px+ and chips 32 px+.

## Mock mode

`src/mock/fixtures.ts` holds one fictional demo project ("Riverside Medical Office Building", TX) with nine subs
and an empty WA project. `derive.ts` computes every response (cards, detail, trend, hazards, red flags, coverage)
from the same inspections, with verdict rules mirroring `ssi/scoring/verdict.py` (minus the p90, ITA and licence
rules), so the scorecard, detail pages and answers always agree:

| Sub | Shows |
|---|---|
| Summit Ridge Roofing | High concern: cited fatality (accident narrative, shared site), open case, recurring falls |
| Lone Star Framing | Review: repeat fall-protection citation. Switch the lookback to 10 years and a second repeat makes it High concern |
| Cascade Steel Erectors | WA state-plan inspections (WAC codes), WA L&I licence, ID-prefixed name note |
| Trinity Concrete | Pending yes/no match question (a possible record with a willful citation); "yes" makes it High concern |
| ABC Drywall | Generic name: starts as `needs_adjudication`, resolves after ~2 s to "+4 possible-match inspections, not counted" |
| Gulf Coast Mechanical | ITA injury rates (TRIR/DART vs industry rate) with one implausible year flagged |
| Hill Country Glazing | No OSHA record |
| Pecos Masonry | No recent record (2011 and 2014 only, pre-2014 9-digit activity numbers) |
| Brazos Electric | No flags |

Pasting one of these names into any project finds the same record; any other name comes back as "No OSHA record".
The mock assistant answers the four suggested questions, sub names and trades ("the roofer"), hazards (falls,
ladders, scaffolds, trenching), "Dallas" (clarify), and returns `needs_confirmation` for Trinity until its question
is answered. Add `#nokey` or `#guard` to a question to see the `no_api_key` and `guard_failed` states. Mock mode
starts signed in as a demo user; after signing out, any email and password signs back in. Mock state (including
saved chats) resets on reload.

## Contract notes

- Response shapes follow `ssi/api/app.py`: PATCH project → `Project`; adjudicate, match override and question
  answer → the re-scored `SubCard`; DELETE sub → `{ok: true}`. After a mutation the page refetches so ordering and
  counts stay right.
- `GET …/inspections?offset=&limit=` pages after the first page embedded in `SubDetail` (25 per page); the list
  stops when a page comes back short or `coverage.inspections_all_time` is reached.
- `ItaYear.peer_trir` is the pooled industry rate (all filers' cases ÷ hours), labelled "Industry rate".
- Chats live on the server, one per conversation and private to the signed-in user. The first question creates
  the chat (`POST /api/projects/{id}/chats`), later ones go to `POST /api/chats/{id}/messages`, and the browser
  sends only the question: the server adds the earlier turns. `sessionStorage` keeps just the id of the chat each
  project has open in this tab, so a reload, the docked panel and the `/ask` page reopen the same one.
- Every request carries `X-SSI-Client: web` (the API refuses writes without it). A 401 from any request means the
  session ended and shows the sign-in page.
