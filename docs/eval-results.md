# Evaluation results, and what each one changed

Every evaluation, audit and measured comparison in the project in one place: what was measured, what came out,
and what the app does differently because of it. The full tables stay where they were produced; this file links
to them. Figures are from the 10-year warehouse unless a section says otherwise (October 2026).

## Contents

- [The decisions at a glance](#the-decisions-at-a-glance)
- [1. How the labels work, and their limits](#1-how-the-labels-work-and-their-limits)
- [2. Before the matcher: why rules first and fuzzy only for candidates](#2-before-the-matcher-why-rules-first-and-fuzzy-only-for-candidates)
- [3. Matching rules](#3-matching-rules)
- [4. Pipeline, outlier and code reviews](#4-pipeline-outlier-and-code-reviews)
- [5. The AI adjudicator: DeepSeek vs GLM vs Kimi vs Jev](#5-the-ai-adjudicator-deepseek-vs-glm-vs-kimi-vs-jev)
- [6. The foreman (GLM 5.3)](#6-the-foreman-glm-53)
- [7. Company profiles: Claude vs Tavily, questions vs context](#7-company-profiles-claude-vs-tavily-questions-vs-context)
- [8. Other public data](#8-other-public-data)
- [9. Speed](#9-speed)
- [10. Cost](#10-cost)
- [11. Not evaluated yet, or still open](#11-not-evaluated-yet-or-still-open)
- [Re-running the evals](#re-running-the-evals)

---

## The decisions at a glance

| Decision | Evidence | Section |
|---|---|---|
| Rules decide first; fuzzy matching only suggests candidates | Jaro-Winkler ≥ 0.95 spot check: 14 of 20 right, 3 clearly wrong | [2](#2-before-the-matcher-why-rules-first-and-fuzzy-only-for-candidates) |
| Generic words split into *descriptors* (GENERAL, CONTRACTORS) and *trade words* (ROOFING, TILE) | First matching eval: trade-word auto-matches were the real error; precision 0.87 → 0.90 (all years) | [3.2](#32-what-the-first-run-taught) |
| People's names need a city or address to match | "Juan Garcia, TX" auto-matched 24 records in 13 states, including another person's fatality | [3.3](#33-why-each-rule-exists) |
| M2 no longer merges JVs, swapped trade words or different people at one address (J1, U3, P2) | 1,990 differently named pairs in one building: 7 JVs, 9 sister companies, 10 different people among the typos | [3.3](#33-why-each-rule-exists) |
| Spelling correction tries the GC's city first, and changes only the misspelt word | BRINKMMAN matched St. Louis's BRINKMANN; "Aboe Board" matched a California roofer. After: a slip gets the right spelling's matches 356 of 383, and never extra ones | [3.4](#34-a-gcs-typos) |
| A company named after a person keeps its other offices as uncertain, not excluded (P3) | Per-rule eval: X5 excluded the company's own records in all 24 labelled cases (David E. Harvey Builders, Robert J. Devereaux Corp.); after P3, 24 of 24 are held for review and X5 keeps only bare names | [3.3](#33-why-each-rule-exists) |
| Red-flagged uncertain records always go to the GC, never decided by the AI | A confident AI "different" hid a lookalike's red flags from Barnhart's GC on the demo | [3.3](#33-why-each-rule-exists) |
| Jev 1.13 adjudicates uncertain groups without red flags | Held out: 0 wrong merges / 9 wrong exclusions / 130 lookalikes cleared, against DeepSeek's 2 / 13 / 110; 3.5× faster; ≈ $0.05 per 1,000 groups | [5](#5-the-ai-adjudicator-deepseek-vs-glm-vs-kimi-vs-jev) |
| DeepSeek V4.1 Flash keeps the red-flagged groups | The GC reads the AI's reason on those; Jev writes no text | [5.6](#56-why-red-flagged-groups-stay-on-deepseek) |
| Jev used as a three-way choice with tuned thresholds, stricter outside the sub's state | Development sample: 3 wrong exclusions tuned, against 16 untuned and 22 for a yes/no question | [5.4](#54-which-way-to-ask-jev) |
| GLM 5.3 and Kimi K3 not adopted as adjudicators (yet) | Fewest wrong exclusions (2 of 58), but fewer lookalikes cleared, 10–30× slower, ~1 answer in 10 fails the checks; Kimi merged 2 companies | [5.7](#57-why-not-the-larger-llms) |
| Up to 50 AI-adjudicated groups a sub (was 15) | Jev at ~0.25 s and a fraction of a cent a group | [5.9](#59-other-changes-the-adjudicator-eval-drove) |
| Foreman runs at low reasoning effort | 20 eval questions: output tokens 17,185 → 3,643, median 2.9 s → 1.6 s, same checks passed | [6.3](#63-why-low-reasoning-effort) |
| Grounding accepts written-out dates and row counts; empty replies get a nudge then a fallback | Foreman eval first run: grounded 17/20, status 15/20 → 20/20 | [6.2](#62-what-each-run-changed) |
| Company profiles default to Claude Sonnet 5.5 (was Opus 5.5), and the web lookup is opt-in | ≈ $0.20 a profile, 32 s median; each lookup spends credits | [7](#7-company-profiles-claude-vs-tavily-questions-vs-context) |
| A profile's locations become GC questions, not automatic matches | Built that way before the eval; since then, the profile as extra AI evidence took DeepSeek's wrong merges from 1 to 3 | [7.3](#73-three-ways-to-use-a-profile) |
| A tax ID (EIN) is evidence, never an automatic merge | One firm files under 23 EINs; some EINs are junk | [8](#8-other-public-data) |

---

## 1. How the labels work, and their limits

There is no answer key for "is this OSHA record the GC's sub?", so the matching and adjudication evals build
**silver labels** from OSHA's injury filings (ITA 300A), which carry the employer's tax ID
([eval/matching/run.py](../eval/matching/run.py)):

- **Same company:** two OSHA establishments that link exactly (name + zip) to ITA rows with the same EIN.
- **Different company, same state:** same name core and state, different EINs.
- **Different company, other state** (added for the adjudicator eval): the same name core in two states, different
  EINs, each EIN filing in one state only. That leaves out national firms that file under several EINs, the main
  source of wrong labels.

Each pair is searched the way a GC would (A's name, city, state), and the eval grades where B lands.

**The labels are wrong in a known direction.** "Different EIN" means "different legal entity", not what a GC means by
a different company. The data-sources research ([report](../reports/OSHA%20subcontractor%20matching%20data%20sources.md))
read the 18 "wrong" auto-matches by hand: **17 are the same corporate family** (four D.R. Horton divisions, Hagerman,
Lobar, Christman, Doran…). Counting those as related rather than wrong, matched precision is **0.99 (98 of 99)**, not
0.845. The labels also contradict each other: DR HORTON in High Point and Kingsport is a positive pair, DR HORTON in
Charlotte and Raleigh a negative one. So small differences between runs need the disagreements read before they're
trusted, and each results file lists them.

**Development and held-out samples.** The adjudication eval draws pairs by seed. Seed 7 is the development sample
where thresholds were picked; seed 11 shares no pair and no search with it and was only used to check them.

---

## 2. Before the matcher: why rules first and fuzzy only for candidates

Measured while exploring the data ([thought-process.md](thought-process.md) §5):

| Measured | Result | Decision |
|---|---|---|
| Cleanup funnel on construction inspections since 2015 | 265,936 raw names → 198,377 after stripping ID prefixes, punctuation and legal suffixes (−25%; −32% across all years) | **Rules first.** The quirks are predictable, and rules are free, testable and give the same answer every time. An LLM is kept for the leftovers |
| Jaro-Winkler ≥ 0.95 within a state | Only 5,406 more near-duplicates (2.7% more merging). A 20-pair spot check: 14 right, 3 clearly wrong (`C AND A` vs `C AND S CONSTRUCTION`), 3 unclear | **Fuzzy matching suggests candidates, never merges** |
| Brasfield & Gorrie, grouped on identical cleaned name + address + zip | 58 establishments plus 1 lookalike (Brasfield Construction, Tennessee: a different company) | **Establishments only group exact matches.** Splitting too much costs some review; merging too much silently attaches someone else's history, possibly a fatality |
| Embeddings of company names (reasoned, not run) | They mostly capture trade words ("Smith Roofing" ≈ "Jones Roofing") | **No embedding stage** |
| An LLM adjudicator over 1.2M names (reasoned) | Slow and costly | **The AI runs only on a GC's subs**, and only on what the rules leave uncertain |

The cleaning rules now cut distinct names since 2015 from 265,936 to 194,358 (−27%).

---

## 3. Matching rules

### 3.1 The matching eval

300 silver pairs (150 same company, 150 different), deterministic sample. Full table:
[eval/matching/results.md](../eval/matching/results.md).

| Metric | 10-year data (current) | All years (earlier sample) | Meaning |
|---|---|---|---|
| Precision of automatic matches | **0.845** | 0.90 | Of records auto-matched, the share with the same EIN |
| Recall of automatic matches | 0.653 | | Same-company records auto-matched |
| Candidate recall | 0.947 | 0.95 | The right record was found at all |
| False exclusions | 0.013 | 0.013 | Same-company records wrongly excluded (DR HORTON INC GREENSBORO, a city used as a division name) |
| Different companies kept out | 0.88 | 0.93 | Not auto-matched |
| Same-company records left "possible" | 0.28 | 0.33 | Sent to the AI or the GC, not counted |

Precision is lower on 10-year data because, with less history, fewer spelling variants exist per name, so more names
count as "distinctive" and auto-match across a family's offices.

An earlier version sampled with DuckDB's "repeatable" sampling, which isn't repeatable across runs with multiple
threads: numbers moved by a few points between identical runs. Pairs are now ordered by a hash of their keys.

### 3.2 What the first run taught

Auto-matching names that differed only by **trade** words (`WAUSAU HOMES` vs `WAUSAU TILE`, `TURNKEY CONSTRUCTION` vs
`TURNKEY ELECTRIC`) was the real error. Generic words were split into **descriptors** (GENERAL, CONTRACTORS,
SERVICES), which may differ (rule M1b), and **trade words**, which may not (U3). Precision on all-years data rose
from **0.87 to 0.90**.

### 3.3 Why each rule exists

The rules are in [ssi/matching/rules.py](../ssi/matching/rules.py); what each does is in the
[README](../README.md#3-matching-subs-to-osha-records). This is the evidence behind each one; how often each one is
right on real records is in [§3.6](#36-each-rule-on-its-own).

| Rule | Bucket | Why it's there |
|---|---|---|
| **Distinctiveness** (used by M1, M3) | | Measured from the data, not hand-listed: the number of distinct full names sharing a core. `BRASFIELD GORRIE` has 3 (distinctive); `CLARK` 112 and `ABC` 114 (generic). Generic names need a city match to auto-match |
| **M1** same full name, same state | Matched | The baseline: on the development sample it made 142 of the 285 auto-matches of same-company, same-name pairs (M3 made the other 143) |
| **M1b** differs only by descriptor words | Matched | The first eval run (above): descriptors may differ, trade words may not |
| **M2** at a matched address, name differs by spelling | Matched | Typos at the company's own address (`GORIE`, `VAUGN`). The [name-matching audit](name-matching-audit.md) collected all 1,990 differently named pairs sharing a non-shared building: mostly real typos, but also the cases J1, U3 and P2 now carve out |
| **M3** same distinctive name, another state | Matched | "Also operates in…". The adjudicator eval's cross-state pairs showed its cost: it auto-matched **51 of 1,600** pairs of different local firms (development) and 60 of 1,333 (held out), e.g. Quinn Construction PA/TN, Straub Construction CA/KS. An audit on web evidence is written but not yet run ([§11](#11-not-evaluated-yet-or-still-open)) |
| **L1** linked to the GC's licence number | Matched | A GC can pin a sub when the name is ambiguous |
| **S1** differs only by `OF <STATE>` / `AT <project>` | Uncertain | The code review found Hoffman Construction's OF OREGON records among 48 *excluded*: the place word stayed in the name core, so S1 never fired. Now Hoffman's Oregon, Washington and California companies and 20 regional Pulte records are possible |
| **S2** the sub's name + BRANCH / DIVISION / OFFICE | Uncertain, never excluded | The pipeline review: a rule excluded Barnhart's own Oklahoma City branch, which carried a fatality |
| **S3** the sub's name + a real word, at an address the sub uses | Uncertain, never excluded | A GC's "D.R. Horton" excluded `D R HORTON INC PORTLAND`, 17 inspections and 7 red flags at D.R. Horton's head office: 0.88 similar, short of M2's 0.93, so X1 called it another company. The head office holds ten of the group's names, so it counts as a shared office and wasn't searched at all; a shared office now pulls in these records only, for a distinctive name, and never as a match |
| **P1 / X5** a person's name matches only in the GC's city or at a matched address | Matched / Excluded / Uncertain | The pipeline review: "Juan Garcia, TX" auto-matched **24 records in 13 states**, including another person's cited fatality; "JOSE HERNANDEZ" is 49 records in 17 states. After: 0 auto-matches without a city. The audit then found people the rule missed: ALEX PEREZ (7 establishments, 5 states, rated "distinctive", so M3 matched across states) and J LOPEZ (8 in 7 states). 113 given names and an initial + surname rule added; cores rated person 20,988 → 24,398. Place names (SAN ANTONIO, ST GEORGE: 27 cores) are no longer people, since X5 had excluded a company's own branch. A misspelt city ("heuston") makes a person uncertain, not excluded |
| **P2** another person's name at a matched address | Uncertain | The audit: 10 of the M2 pairs were different people (`MARIO` / `MAURICIO CONTRERAS`, `SERGIO CAZARES` / `… SR`) |
| **P3** a company named after a person, in another city or state | Uncertain | The per-rule eval ([§3.6](#36-each-rule-on-its-own)): X5 excluded the company's own records in all 24 labelled cases (13 firms). In the warehouse, 8% of bare person names recur in another city, spread wide (JOSE GARCIA: 36 cities); 3.4% of person names with a trade or company word do, and the widest are real firms (David Weekley Homes, Stanley Martin Homes, Edward Rose & Sons). Bare names with a legal form on every record that recur are firms too (Oscar W. Larson, James N. Gray); common names carry one only sometimes (JOSE MARTINEZ: 2 of 37). So P3 needs a company word on both sides, or a legal form both typed and on the record. Unsure rather than matched: a few such names are several people's (JOSE GARCIA CONSTRUCTION, 3 states) |
| **J1** a joint venture at a member's address | Uncertain | The audit: M2 had merged **7 JVs into their members**. A JV is its own company |
| **U3** same family name, different trade word | Uncertain | The first eval run (WAUSAU HOMES / TILE), and the audit: 9 sister companies at one address (`EENIGENBURG FRAMING` / `ROOFING`) that M2 merged when the names were long enough to score ≥ 0.93 |
| **U4** the sub's common name in another state | Uncertain, never excluded | The per-rule eval ([§3.6](#36-each-rule-on-its-own)): X4 excluded these as another company, and with a pool of common-name searches 18 of 72 labelled records, from 36 firms, were the sub's own: about as often as for U. On all 533 common-name searches the eval can draw, 39 of 136 were, all from 6 firms of 61 (Premier Roofing's offices in Omaha, St Louis, Denver and Fort Collins; Power Home Solar's in Michigan and North Carolina), and 8 of the 18 red-flagged ones. A question, so a red-flagged one reaches the GC and the rest the adjudicator and the web check. The cost: plain "Quality Roofing" in Nashville gets 15 possible records, none counted, 2 of them red-flagged |
| **X1–X3** different real word, different generic name, common name with other words | Excluded | Keep lookalikes out: 0.88 of different-company pairs kept out |
| **R1** a red-flagged record at the company's address is never excluded by a rule | Uncertain → GC | The Barnhart branch fatality above |
| **Red flags always reach the GC** (any uncertain record with a fatality, willful, repeat or failure-to-abate) | GC question | An earlier version let a confident AI "different" exclude a red-flagged record and capped questions at 3: on the demo that hid a lookalike's red flags from Barnhart's GC. Now the AI's lean is only a suggestion, and past 3 questions they're grouped one per OSHA name rather than dropped |
| **N1** related facilities (in scope by name, not coded construction) | Uncertain | The outlier review: `related_name` pulled in US Postal (1,454 records), Amazon, Dollar Tree. Now only firms with ≥ 20% construction-coded inspections (Tindall: 51%): 28,726 → 10,713 records |
| **Each of a sub's names rated on its own** | | The code review: "… Holdings LLC dba Quality Roofing", Nashville, borrowed the legal name's rarity and auto-matched **15 QUALITY ROOFING records in 11 states**. Now none matched, as for plain "Quality Roofing" (1 possible and 14 excluded then; 15 possible since U4) |
| **An address-aware "uncertain" replaces a name-only "excluded"** | | The audit: the same record was uncertain or excluded depending on which search found it first |

### 3.4 A GC's typos

The silver pairs search with OSHA's own spellings, so two more checks cover a GC's slips (same results file):

| Check | Before the city-anchored fix | After | After the name audit |
|---|---|---|---|
| Slips in distinctive OSHA names: same matches as the correct spelling | 25 of 381 | 324 of 381 | **356 of 383** |
| … a match the correct spelling doesn't make | 1 | **0** | **0** |
| Licensed contractors one letter from an OSHA name in the same city, same address (a slip): auto-matched | 2 of 75 | 19 of 75 | 22 of 66 |
| … at another address (usually another company): auto-matched | 0 of 128 | 4 of 128 | 5 of 119 |

The thresholds behind spelling correction each came from a failure:

| Setting | Why |
|---|---|
| OSHA's spelling must have ≥ 10 inspections and ≥ 10× the GC's | A lower bar "corrected" COLMEX (a real Florida company) to COMEX (an Iowa one) |
| A one-letter slip counts only with a record in the GC's city | `McKennys, Atlanta` → MCKENNEY'S (9 inspections) |
| A *replaced* letter doesn't count as a slip | Among 141,727 licensed contractors (WA, CA, OR) with no OSHA record, a name one replaced letter from an OSHA name in the same city was usually another company (BORA/KORA, AECON/AECOM, HB/SB STRUCTURES) |
| Similar names must also be within one letter in length (`near_spelling`) | COLMEX counted as a slip of COLE |
| The city is tried before volume | "Brinkmman Construction, Wheat Ridge" was searched as BRINKMANN (25 inspections, a St. Louis builder) and auto-matched; it's BRINKMAN, with a record in Wheat Ridge |
| Only the misspelt word changes; the sub's other names stay | The correction took the most-inspected record's whole name: "Aboe Board Contracting, Portsmouth RI" auto-matched a California roofer and left the Portsmouth company possible. `ALPHA ROOFING EXPERTS` was searched as `ALPHA EXPERT`, losing ROOFING |

### 3.5 The name-matching audit

The cleaning macros, the person-name rule and the rules were run over every name in the warehouse (237,113 raw
names, 121,108 cores). Full findings: [name-matching-audit.md](name-matching-audit.md).

| | Before | After |
|---|---|---|
| Raw names cleaned differently | | 643 (116 old names merge into their twin) |
| Establishments | 218,004 | 217,931 |
| Cores rated person / distinctive | 20,988 / 91,036 | 24,398 / 87,483 |
| Matching eval precision / recall | 0.845 / 0.653 | 0.845 / 0.653 (the 300 pairs rarely contain these cases) |
| A GC's slip gets the correct spelling's matches | 325 of 381 | 356 of 383 |
| `describe_query` (each sub's name) | 306 ms | 10 ms |
| Matching eval run time | 469 s | 114 s |

The biggest cleaning finds: legal forms the cleaner missed (`L.C.`, `LLLP`, `PLC`, cut-off `INCORPORA…`: 247 names,
58 merge with a twin; `ADELPHI CONSTRUCTION LC` was being *excluded* for a GC entering "Adelphi Construction"),
`A-1` ≠ `A1` (279 names), and `R G P INC` cleaning to just `R`. On the code before the fixes, 12 of 19 end-to-end
scenarios, 59 cleaning cases and 18 rule tests fail.

### 3.6 Each rule on its own

The evals above grade the rules together, and the cases the rarer rules guard (people's names, joint ventures,
branches) hardly ever appear in their samples. [eval/rules/run.py](../eval/rules/run.py) grades each rule separately.
It runs searches the way a GC would, starting from 3,262 establishments that file injury reports under one tax ID:
1,500 drawn at random, and the rest from pools where particular rules act (people's names, shared buildings, joint
ventures, branch and OF <STATE> names, related facilities, names made only of common words, licence numbers). Every
record the rules decide is filed under the rule that decided it and labelled by tax ID, with at most 3 per search and
rule so that one national firm can't fill a rule's set. 140,808 records were decided, 23,598 labelled and 8,008
graded, in about 7 minutes with no model calls. Full table and examples: [eval/rules/results.md](../eval/rules/results.md).

Share of a rule's labelled records that were the same company (firms = distinct tax IDs searched):

| Rule | Bucket | Labelled (firms) | Share same [95%] | Means |
|---|---|---|---|---|
| M1 same name, same state | matched | 879 (547) | 0.995 [0.99–1.0] | precision |
| L1 licence number | matched | 114 (80) | 1.0 [0.97–1.0] | precision |
| M3 distinctive name, other state | matched | 461 (120) | 0.78 [0.74–0.81] | precision |
| M2 spelling variant at a matched address | matched | 36 (26) | 0.67 [0.5–0.8] | precision |
| M1b descriptor words differ | matched | 43 (21) | 0.44 [0.3–0.59] | precision |
| X1 a different real word | excluded | 3,510 (1,339) | 0.006 [0.0–0.01] | wrongly excluded |
| X3 common name, other words | excluded | 1,216 (476) | 0.001 [0.0–0.0] | wrongly excluded |
| X4 common name, other state (before U4) | excluded | 17 (7) | 0.59 [0.36–0.78] | wrongly excluded |
| X5 person's name, other city (before P3) | excluded | 24 (13) | 1.0 [0.86–1.0] | wrongly excluded |
| X5, with P3 | excluded | 0 (23 records, none labelled) | – | wrongly excluded |
| N1 related facility by name | possible | 315 (118) | 0.85 [0.81–0.89] | held back, but the sub's |
| P3 company named after a person, elsewhere | possible | 24 (13) | 1.0 [0.86–1.0] | held back, but the sub's |
| M3u M3's guard for colliding names | possible | 24 (15) | 0.58 [0.39–0.76] | held back, but the sub's |
| G1 initials-only | possible | 61 (31) | 0.51 [0.39–0.63] | held back, but the sub's |
| U anything else | possible | 380 (183) | 0.27 [0.23–0.32] | held back, but the sub's |
| U4 the sub's common name, other state | possible | 72 (36) | 0.25 [0.16–0.36] | held back, but the sub's |
| S3 the sub's name + a word, at its address | possible | 50 (30) | 0.38 [0.26–0.52] | held back, but the sub's |
| U2 common name, same city | possible | 29 (21) | 0.17 [0.08–0.35] | held back, but the sub's |
| U3 trade word differs | possible | 149 (92) | 0.13 [0.09–0.2] | held back, but the sub's |
| R1 red-flag safety net | possible | 51 (29) | 0.06 [0.02–0.16] | held back, but the sub's |
| S1 OF <STATE> / AT <project> | possible | 479 (209) | 0.01 [0.0–0.02] | held back, but the sub's |

Too few labels to grade: S2 (2, from one firm), P1 (2), J1 (85 records, none labelled: a JV files under its own tax
ID). P2 and X2 never fired.

**S3** (the sub's name plus a word, at an address it uses) holds back records that were the sub's 38% of the time, too
often to exclude and too seldom to match, which is why it asks. With it J1 went from 3 records to 85: joint ventures
named after a member at the member's address (GILBANE ANT YAPI JOINT VENTURE at Gilbane's) used to fall through to
X1. Together they took 244 records from X1 and 24 from R1's red-flag net, and reached 48 at shared offices that no
search had found before.

What the examples show:

- **M1, L1, X1 and X3 hold up**: 99–100% right on hundreds of labelled records from hundreds of firms.
- **Most of M1b's, M2's and M3's "wrong" matches are corporate families** (BrandSafway, Hensel Phelps, Christman,
  Hagerman), so their shares are lower bounds until the review below. M3's 40 errors between local firms (both tax
  IDs file in one state) are the reliable ones.
- **X5 excluded the company's own records all 24 times** (13 firms). These are companies named after people: David E.
  Harvey Builders (Bethesda and Houston), The Fred Christen & Sons Company (Detroit and Toledo), William Molnar
  Roofing. It's the gap the [name audit](name-matching-audit.md#what-is-left-known-not-fixed) noted, now measured.
  The sample leans this way: a tax ID needs an injury filing, which firms under 20 employees rarely make, so the
  sole proprietors X5 is meant for are barely in it. **Fixed by rule P3** ([§3.3](#33-why-each-rule-exists)): all 24
  are now held back for the adjudicator or the GC, and X5 still excludes 23 records in these searches, all bare names
  without a label. 91 records across 54 searches moved from excluded to uncertain. The matching eval's 300 pairs
  don't change (none is a person-named company).
- **X4's 10 wrong exclusions were two firms** (Premier Roofing, Power Home Solar), each operating in several states
  under one tax ID, from 7 firms in all. A pool of common-name searches gave it 72 labelled records from 36 firms:
  18 were the sub's own, 0.25, as often as for U and far from X1's and X3's 0.006 and 0.001. **Now rule U4**
  ([§3.3](#33-why-each-rule-exists)) holds them back.
- **S1 holds back almost only other companies**: 474 of 479, 455 of them local firms, and 20,424 records from 415
  searches. It fires on any `<word> … OF <PLACE>` name: University Mechanical Contractors against the University of
  South Carolina, Consolidated Construction Co. of Alabama against a Michigan electrical contractor, and City of
  Pasadena alone held back 242. They're left possible, so the cost is clutter and adjudicator calls, not a wrong count.
- **N1 holds back records that are the sub's own 85% of the time** (118 firms). It was added when related
  facilities by name pulled in US Postal and Amazon, before the ≥ 20% construction filter, so it may now be more
  cautious than it needs to be.
- **M3u**: of the 24 records it held back, 14 shared the sub's tax ID; the other 10 were all local firms, the
  reliable negatives.

**Silver labels can't grade every rule.** A tax ID needs an injury filing (about 9% of establishments, mostly firms
with 20+ employees), so the rules for small firms and people (P1, P2, X5, J1, S2) get few or biased labels; those need
hand-labelled sets. For the rules at a family's edges, a person has to judge: each run writes the apparent errors (a
matched record labelled different, an excluded one labelled same) to [eval/rules/review.jsonl](../eval/rules/review.jsonl)
with an empty verdict (`same`, `family`, `different` or `unsure`). Verdicts are kept across runs and replace the
silver label in the "after review" column, with a family counted as the same company.

---

## 4. Pipeline, outlier and code reviews

Three reviews checked the work rather than a model. Each finding has a test, and a build check where the data can
regress. The full tables are in the [README](../README.md#8-evaluation); the ones that moved numbers:

| Review | Measured | Changed |
|---|---|---|
| Pipeline | Rebuilt every step from the raw files and diffed: no in-scope row lost, penalties reconcile to the cent | Build checks now recount independently (scope from keys, citations from the raw file, red flags from live citations) |
| Pipeline | 586 fatality/catastrophe investigations after OSHA's accident detail ends had no flag | Flagged pending or not cited; a build check requires a flag on every one |
| Pipeline | Rebuilding from the same files changed 2,771 companies' main trade (random tie-breaks) | Fixed tie order; builds fingerprint inputs and tables (two consecutive builds identical) |
| Pipeline | The 10-year cut came before "is this a construction company?", dropping 5,817 recent inspections | Scope decided from every year, then 10 years kept |
| Pipeline | The 2026 load restarts injury line numbers per employer: two deaths shown as one | Victims split on sex or age; a build check fails on a mixed row |
| Outlier | Arizona and Iowa case numbers in front of names: 1,184 records became one-inspection companies; the matcher missed 10 of 12 Arizona companies' cited fatality records | Stripped: all 21 such companies now match their fatality record (19) or get a GC question (2) |
| Outlier | 18,550 "inspections" (5.5%) were files where OSHA didn't inspect; a sub with only those read "No flags" | Never counted; only such files = No OSHA record |
| Outlier | "Open case" read as provisional, but 26,055 of 29,564 open serious cases were final | Provisional = open with a citation not yet final |
| Outlier | Self-reported 300A deaths unused: 435 construction firms, 533 deaths (Karvo Companies: 6 in 2023, no OSHA fatality record) | Review flag when no OSHA fatality investigation is within a year |
| Outlier | A safety and a health inspection of one visit counted as two: 13 firms High for "repeats in 2 separate inspections" from one visit | Repeats and hazard patterns count visits |
| Outlier | 55 fatality investigations "still open" for up to 10 years | After 7 months without citations: "not cited" |
| Code | A cited fatality split across two inspections of one visit read "not cited" | Cited means cited on the visit: 12 statuses corrected, 6 duplicate site flags gone |
| Code | Accents cut out of a GC's names (`Muñoz` → `MU OZ`; `José Hernández` became a "distinctive" non-person) | Accents folded |
| Code | The foreman's grounding check passed an invented `#9999999` and chipped a truncated real ID | IDs checked whole against the tools' IDs. Replaying the 20 eval answers: same passes and fails as before |

Not fixed, by choice: 936 federal citations recorded as serious carry willful/repeat-level penalties, the mark of a
reclassification in settlement. That's an inference, so it's documented in [data-profile.md](data-profile.md), not
flagged.

---

## 5. The AI adjudicator: DeepSeek vs GLM vs Kimi vs Jev

The rules leave some candidates uncertain. Those are grouped by name and state, and each group goes to an
adjudicator with an evidence packet (identity evidence only, never safety history). The errors, worst first:
a **wrong merge** attaches someone else's history; a **wrong exclusion** hides the sub's own; a lookalike left
**possible** only adds clutter. Full write-up: [adjudicator.md](adjudicator.md).

### 5.1 Setup

[eval/adjudication/run.py](../eval/adjudication/run.py) takes the silver pairs plus the cross-state ones, runs the
rules, and sends only the uncertain pairs to each adjudicator with the packet the app builds. Answers go through the
app's thresholds.

| Sample | Silver pairs | Uncertain after the rules | Same / different | Red-flagged |
|---|---|---|---|---|
| Seed 7, development ([results](../eval/adjudication/results.md)) | 2,400 | 302 | 87 / 215 | 46 |
| Seed 11, held out ([results](../eval/adjudication/results-seed11.md)) | 1,931 | 246 | 74 / 172 | 23 |

Compared: DeepSeek V4.1 Flash (the app's LLM), GLM 5.3 and Kimi K3 (same prompt and checks, 8,192 output tokens to
reason), and Jev 1.13 (TypeSafe's decision model: returns a probability per label, no text). LLM thresholds:
"same" at ≥ 0.85 → matched, "different" at ≥ 0.80 → excluded. The cross-state pairs were added after the first round:
without them every cross-state pair was the same company, so the guidance's "a common name in another state is
usually a different company" could only be shown to cost, never to save.

### 5.2 Held-out results

| Seed 11, 246 uncertain | DeepSeek V4.1 Flash | GLM 5.3 | Kimi K3 | Jev, as the app uses it |
|---|---|---|---|---|
| **Wrong merges** (of 172 different) | 2 | **0** | 2 | **0** |
| **Wrong exclusions** (of 74 same) | 13 | **2** | **2** | 9 |
| Lookalikes excluded (of 172) | 110 | 98 | 111 | **130** |
| Same-company records matched (of 74) | 4 | 3 | 5 | 0 |
| Share resolved (not left possible) | 0.52 | 0.42 | 0.49 | **0.57** |
| Precision of exclusions | 0.89 | 0.98 | 0.98 | 0.94 |
| AUC of P(same) | 0.77 | **0.87** | 0.86 | 0.84 |
| Brier score (lower is better) | 0.17 | **0.14** | 0.15 | 0.20 |
| Answers rejected by validation | 1 | 25 | 22 | 0 |
| Median / p90 seconds a group | 0.84 / 1.15 | 2.7 / 17.8 | 7.4 / 21.3 | **0.23 / 0.28** |
| Tokens a group, in / out | 690 / 100 | 710 / 1,530 | 780 / 390 | 1,250 / 0 |
| Cost per 1,000 groups | $0.33 | not priced (self-hosted) | $8 | **$0.05** |

By where the pair is (matched · possible · excluded):

| Pairs | n | DeepSeek | GLM 5.3 | Kimi K3 | Jev |
|---|---|---|---|---|---|
| Different company, same state | 62 | 2 · 39 · 21 | 0 · 47 · 15 | 1 · 43 · 18 | 0 · 20 · **42** |
| Different company, other state | 110 | 0 · 21 · 89 | 0 · 27 · 83 | 1 · 16 · 93 | 0 · 22 · 88 |
| Same company, same state | 16 | 4 · 11 · 1 | 3 · 13 · 0 | 5 · 11 · 0 | 0 · 16 · 0 |
| Same company, other state | 58 | 0 · 46 · 12 | 0 · 56 · 2 | 0 · 56 · 2 | 0 · 49 · 9 |

### 5.3 Development results

| Seed 7, 302 uncertain | DeepSeek | GLM 5.3 | Kimi K3 | Jev, as the app uses it |
|---|---|---|---|---|
| Wrong merges (of 215) | 1 | 1 | 3 | **0** |
| Wrong exclusions (of 87) | 9 | **0** | 3 | 3 |
| Lookalikes excluded | 137 | 114 | 119 | **154** |
| AUC / Brier | 0.80 / 0.16 | **0.89 / 0.13** | 0.87 / 0.14 | 0.85 / 0.18 |
| Answers rejected | 6 | 27 | 38 | 0 |
| Median seconds a group | 0.89 | 3.8 | 11.8 | **0.25** |

### 5.4 Which way to ask Jev

Three ways of asking Jev were compared. The thresholds were picked on seed 7 and frozen before seed 11 was drawn.

| | Wrong exclusions, dev / held out | Lookalikes excluded, dev / held out |
|---|---|---|
| Yes/no question, LLM thresholds | 22 / 26 | 165 / 137 |
| Same/different/unsure choice, LLM thresholds | 16 / 17 | 160 / 132 |
| **Choice, tuned thresholds** (what the app does) | **3 / 9** | 154 / 130 |

Tuned: P(same) = P("same") + half of P("unsure"); matched at ≥ 0.85; excluded at ≤ 0.20 in the sub's state and
≤ 0.06 in another (where a national firm's own branches are). Jev's P(same) didn't reach 0.85 on any pair in either
sample, so in practice it never matches.

**The other-state threshold looked better than it was:** wrongly excluded branches went from 2 of 66 (development)
to 9 of 58 (held out). The same-state threshold held exactly. The remaining 9 are national firms' branches: NPL
Construction six times, NVR twice, PAR Electrical once.

### 5.5 Why Jev, for groups without red flags

1. **More accurate where it acts.** Held out, 20 more lookalikes excluded and 4 fewer wrong exclusions than DeepSeek.
2. **No wrong merges** on either sample. DeepSeek's two merged corporate families under different EINs (Barton Malow /
   Barton Malow Builders; Stellar Contracting / Stellar Group).
3. **Better separation** (AUC 0.84 against 0.77). DeepSeek's confidence comes in a few round numbers (0.80, 0.85,
   0.90), so there's little to tune.
4. **3.5× faster** (0.23 s against 0.8 s a group): a shorter "Resolving N uncertain records…" wait.
5. **Nothing to make up.** Jev returns probabilities for fixed labels; DeepSeek's text needs a validator, which
   rejected 1–6 answers a run, leaving those groups undecided.
6. **Cost.** About a cent for a 250-group run (307k input tokens at $0.042 per million; output is free), no GPU to
   host.

What it gives up, and how that's handled: no written reason (the reason line is written in code from the evidence,
facts sorted For and Against, so it's true by construction); probabilities not calibrated on this task (Brier 0.20),
so thresholds are empirical cut-offs; the packet goes to a third party with no published retention policy; a young
closed model behind an alias (every decision records `ai:jev:jev-1.13.0`, and another version logs a warning).

A finding that shaped the reason line: **a shared trade code is weak evidence.** Held out, 80% of same-company pairs
shared the sub's code, but so did 34% of lookalikes, and the pairs sharing one split 59 same, 58 different. So the
reason line lists it as one fact among others, not as the deciding one.

### 5.6 Why red-flagged groups stay on DeepSeek

They're the one place a person reads the AI's reasoning to decide: about 1 group in 10 (46 of 302 development, 23
of 246 held out). DeepSeek's reason is checked in code (cited evidence must exist; every name and number must appear
in it). Without an LLM configured, Jev takes them too, with the code-written reason.

There was no head-to-head eval behind DeepSeek V4.1 Flash as the first adjudicator LLM; it was set up as the model
for "many short same/different/unsure calls" when each role got its own endpoint. This eval is the first comparison.

### 5.7 Why not the larger LLMs

GLM 5.3 and Kimi K3 are the most accurate when they act (2 wrong exclusions held out, against Jev's 9 and DeepSeek's
13) and rank same against different best. They weren't adopted because:

- they clear fewer lookalikes (98–111 against Jev's 130), so more clutter is left possible;
- they're 10–30× slower (p90 around 20 s a group); GLM 5.3 writes ~1,530 output tokens a group, mostly reasoning;
- about 1 answer in 10 fails the checks (no parseable answer, a rationale over 400 characters, or a word not in the
  evidence such as "ZIP" or "NYC"), so that group stays possible. Several were correct "same" calls on Turner and NVR
  branches;
- **Kimi K3 merged 2 different companies** held out (Stellar Contracting / Stellar Group; Motor City Electric /
  Motor City Electric Utilities), the worst error.

### 5.8 The split that looks best, and why it isn't used yet

Jev in the sub's state and GLM 5.3 outside it (where the national-branch errors are):

| | Wrong merges | Wrong exclusions | Lookalikes excluded |
|---|---|---|---|
| Held out | 0 | 2 | 125 |
| Development | 0 | 1 | 154 |
| Jev alone, held out | 0 | 9 | 130 |

It was found *after* looking at the held-out results, so it needs a fresh sample before the app adopts it.

### 5.9 Other changes the adjudicator eval drove

- **AI cap raised from 15 to 50 groups a sub** (`ADJUDICATE_MAX_CLUSTERS`), most inspections first: at ~0.25 s and a
  fraction of a cent a group, smaller lookalike groups get cleared too. The rest stay possible; red flags still
  reach the GC.
- **Rule M3's cost made visible:** see [§3.3](#33-why-each-rule-exists).
- **A failed AI call loses only its own group** (left possible; a red-flagged one still becomes a GC question),
  rather than the decisions on the sub's other groups.
- **Re-run triggers:** a new Jev version in the logs, a change to the guidance or the packet, or a rules change that
  alters what reaches the adjudicator. Answers are cached, so a re-run only pays for new ones.

---

## 6. The foreman (GLM 5.3)

### 6.1 Setup

20 questions against the demo project ([eval/foreman/](../eval/foreman/)), each with expected tools, an expected status
(answered, clarify, needs confirmation, unanswerable) and phrases that must or mustn't appear. Graded in code. It's a
smoke test, not a benchmark: small enough to read every answer, which is how most of the issues below were found.

### 6.2 What each run changed

| Check | First run | 20/20 run | Latest run ([results](../eval/foreman/results.md)) |
|---|---|---|---|
| Used an expected tool | 20/20 | 20/20 | 19/20 |
| Expected status | 15/20 | 20/20 | 20/20 |
| Grounded (passed the number check) | 17/20 | 20/20 | 20/20 |
| Required phrases present | 14/20 | 20/20 | 20/20 |
| No forbidden phrases | 20/20 | 20/20 | 20/20 |
| Median / slowest answer | | 2.6 s / 6.9 s | 2.2 s / 10.9 s |

The latest run is on the re-seeded demo, whose GC questions are answered. Its one tool miss is "Has Brasfield had
any recent problems?", answered correctly through `compare_subs` and `open_cases` rather than the expected tool.

| Found in a run | Changed |
|---|---|
| The number check read "-11" in "2025-11-13" as minus eleven, rejecting answers that wrote the date out | Dates count by their parts; so does the number of rows a tool returned |
| The model sometimes ended its turn with no text | One nudge, then a fallback rendered from the tool results: never a blank answer |
| Counts the model added up itself failed grounding | `inspection_list` returns its own total and the number with citations; the prompt says "quote, never compute" |
| Tool results didn't name the sub ("the insulation sub") | Every per-sub result carries the name |
| "Smith Electric" was answered as Allison-Smith | The prompt says to ask; the eval forbids "assuming you mean" |
| "Possible" records read as needing GC action | The tool says they only need the GC when they carry red flags |
| "Which subs had a fatality?" called a per-sub tool 13 times (about four model rounds) | `compare_subs` carries each sub's fatality investigations by outcome and its open cases: one call |
| Three expectations were wrong, not the model | Changed in `questions.json`, each in its git history |

### 6.3 Why low reasoning effort

GLM 5.3's chat template always reasons, at maximum effort by default: about 80% of output tokens never reached the
foreman, and the slowest answers took 20 s.

| Same 20 questions, same data | Default (max) | Low effort |
|---|---|---|
| Output tokens | 17,185 | **3,643** |
| Median answer | 2.9 s | **1.6 s** |
| Slowest answer | 10.4 s | **5.6 s** |
| Checks passed | | same or more |

`enable_thinking=false` isn't the switch for this model: the template ignores it, the server stops separating the
reasoning, and it lands in the answer. Text before a stray `</think>` is now dropped. The adjudicator keeps the
server's default effort.

### 6.4 Named queries, and the model choice

Named queries over text-to-SQL is a design choice, not an eval result: free-form SQL can silently use the wrong
company, miss state codes or count deleted citations, and gives different answers to the same question. The eval
checks that the guards hold rather than comparing the two.

There's no recorded eval comparing models for the foreman. GLM 5.3 was chosen for the role (a multi-step
conversation with tool calls) when each role got its own endpoint; Claude Sonnet 5.5 is the supported alternative
through the Anthropic SDK.

---

## 7. Company profiles: Claude vs Tavily, questions vs context

### 7.1 Why profiles

The rules and adjudicators see only OSHA's data, so a sub's own records at its other locations mostly stay possible:
held out, **Jev left 65 of 74 same-company records possible**, and its remaining wrong exclusions are national firms'
branches in other states. Both are facts a company publishes on its website. Full write-up:
[company-profile.md](company-profile.md).

### 7.2 Runs

[eval/profile/run.py](../eval/profile/run.py) builds a profile for each distinct search in the adjudication eval's
seed-7 cases, then grades each candidate on the silver labels.

| Run | Profiles | Cost | Time a profile |
|---|---|---|---|
| Pilot, Claude Sonnet 5.5 ([results](../eval/profile/results-seed7-pilot.md)) | 25 found of 40 searches | $5.15 (≈ $0.21 each) | median 34 s, slowest 49 s |
| Full, Claude Sonnet 5.5 ([results](../eval/profile/results-seed7-cached.md)) | 43 of 43 found | $8.41 (≈ $0.20 each; 3.4M input tokens, 102 searches) | median 32 s, slowest 52 s |
| Full, Tavily + DeepSeek ([results](../eval/profile/results-seed7-tavily.md)) | 40 of 43 found | $0.42 (≈ $0.01 each) | median 3 s, slowest 8 s |

The default model moved from Opus 5.5 to Sonnet 5.5 in the commit that added the eval. At the eval's list prices
Sonnet costs half as much a token as Opus, and a profile is mostly the pages it reads (~80k input tokens).

### 7.3 Three ways to use a profile

61 uncertain cases (24 same company, 37 different). Counts of candidate records:

| Claude profiles | DeepSeek, no profile | DeepSeek + profile as evidence | Jev, no profile | Jev + profile as evidence | Question to the GC |
|---|---|---|---|---|---|
| Same company matched | 0 | 3 | 0 | 3 | 0 |
| Same company, GC asked ("unsure" suggested) | | | | | 3 |
| Same company wrongly excluded | 5 | **1** | 0 | 0 | 0 |
| Different company wrongly matched | 1 | **3** | 0 | 0 | 0 |
| Different company, GC asked with a misleading "same" | | | | | 4 |
| Different company, GC asked ("unsure") | | | | | 7 |
| Different company excluded | 20 | 18 | 27 | 24 | 20 |

- **As extra evidence for DeepSeek:** wrong exclusions 5 → 1, but **wrong merges 1 → 3**, the worse error.
- **As extra evidence for Jev:** 3 same-company records matched that it had left possible, no wrong merge, 3 fewer
  lookalikes cleared.
- **As a question to the GC** (what the app does): the GC decides, so no automatic error, but 4 of the questions
  suggest "same" for a different company.

The app routes records at a profile's listed locations to the GC, with "same" suggested for a listed address and
"unsure" for a listed city only. Nothing is matched from the web without the GC's answer. The write-up of how this
eval bears on that choice is still to be added to [company-profile.md](company-profile.md).

### 7.4 Claude vs Tavily backends

On the same 43 companies:

| | Claude (Sonnet 5.5, web search + fetch) | Tavily search + DeepSeek |
|---|---|---|
| Found the company | 43 of 43 | 40 of 43 |
| Locations per found profile (share from the company's own site) | 1.8 (100%) | 4.4 (69%) |
| Cost a profile / median time | $0.20 / 32 s | $0.01 / 3 s |
| Jev with the profile: same matched, wrong exclusions, wrong merges, lookalikes excluded | 3, 0, 0, 24 | 2, 1, 1, 25 |
| Question approach: same-company records asked about, misleading "same" suggestions | 3, 4 | 6, 3 |

Close on a small sample. Tavily's extra wrong exclusion is NPL Construction (its profile gave the parent's site and
only two cities, and Jev read the short list as evidence against Las Vegas). Its wrong merge is Big-D Construction,
whose own pages list both offices, so the silver label is likely the error. Claude stays the default; Tavily is the
cheap option (`SSI_PROFILE_BACKEND=tavily`, 30 lookups a day by default to fit its free tier of 1,000 a month).

### 7.5 What the cost decided

- **The web lookup is a checkbox, off by default**, shown only when the server has a Claude key: each lookup spends
  credits, so it's the GC's choice per batch. Other subs can be looked up later from their page.
- Profiles are cached 90 days per company, and `SSI_DAILY_PROFILE_LIMIT` (100 a day) caps spending.
- Person-name subs are never looked up.

---

## 8. Other public data

Measured while linking outside sources ([README §6](../README.md#6-other-public-data)):

| Source | Measured | Decision |
|---|---|---|
| OSHA ITA 300A (3.2M filings) | Links by exact name + zip/address are ~95% precise and cover ~20% of recent inspections. One firm files under 23 EINs; some EINs are junk | Injury rates (TRIR, DART) shown against the pooled industry rate (most small filers report zero, so medians are meaningless). The EIN is adjudicator evidence and the eval's label source, **never an automatic merge** |
| WA, OR, CA licences | Grouping by cleaned name within a state already merges more than any outside ID | Used for verified identity and licence status (rule L1), not merging |
| California CSLB file | The download is cut at ~15 MB: about 45,800 of 179,000 licences; California links 13% of OSHA establishments to a licence against Washington's 57% | Partial; a full re-download is the research report's #2 recommendation |

The [data-sources research report](../reports/OSHA%20subcontractor%20matching%20data%20sources.md) measured coverage of
new sources on 30–60 sampled employers each (±15–25 points): New York's corporation registry found 87%, Texas
Comptroller files ~55%, Washington prevailing-wage filings ~37%, FMCSA ~20%. No source found sole proprietors (1 of 14).
Of 65 different-name true pairs in the adjudication eval, 29 never became candidates. Its ranked recommendations
(relabel the eval first, then fix owned data, then free registries) haven't been adopted yet.

---

## 9. Speed

| What | Before | After | Change |
|---|---|---|---|
| Scorecard for 13 subs | 4.7 s | 1.9 s | Parallel card computation, literal key lists |
| `describe_query` (cleaning a sub's name) | 306 ms (1.9 s after a CASE-based fix multiplied the macro) | 10 ms | Macros take repeated input through a lambda; one cleaning pass in a subquery |
| Matching eval | 469 s | 114 s | Same fix |
| Adjudicator, median a group | DeepSeek 0.8 s | Jev 0.23 s | Jev for groups without red flags |
| Foreman, median answer | 2.9 s | 1.6–2.2 s | Low reasoning effort |
| Company profile | Claude 32 s | Tavily 3 s | Optional backend |

---

## 10. Cost

| Component | Model | Measured usage | Cost |
|---|---|---|---|
| Adjudicator, groups without red flags | Jev 1.13 | ~1,250 input tokens a group | $0.042 per million input, output free: **≈ $0.05 per 1,000 groups** (≈ $0.013 for the 246-group held-out run) |
| Adjudicator, red-flagged groups | DeepSeek V4.1 Flash | ~690 in / 100 out a group | ≈ $0.33 per 1,000 groups |
| Adjudicator candidates (eval only) | GLM 5.3 | ~710 in / 1,530 out a group | Self-hosted on Modal; not priced |
| | Kimi K3 | ~780 in / 390 out a group | ≈ $8 per 1,000 groups |
| Foreman | GLM 5.3, low effort | 3,643 output tokens for the 20 eval questions (17,185 at max effort) | Self-hosted on Modal |
| Company profile | Claude Sonnet 5.5 + web search | ~80k input tokens, 2–3 searches | **≈ $0.20 a profile** ($8.41 for 43) |
| | Tavily + DeepSeek V4.1 Flash | ~3.7k input tokens, 1 search | ≈ $0.01 a profile ($0.42 for 43) |
| Evals run so far | | | Profile pilot $5.15, full Claude run $8.41, Tavily run $0.42; adjudication eval answers cached |

Prices are the list prices in the eval scripts ([eval/profile/run.py](../eval/profile/run.py), `PRICES`;
[ssi/llm/jev.py](../ssi/llm/jev.py), `USD_PER_M_INPUT`), October 2026: Sonnet $2 / $10 per million tokens in / out,
Opus $4 / $20, DeepSeek V4.1 Flash $0.30 / $1.20, Claude web search $10 per 1,000, a basic Tavily search $0.008.

Cost also set limits: daily token budgets for the AI, the profile lookup off by default, 100 profiles a day, and
LangSmith tracing that can be switched off (`LANGSMITH_TRACING=false`) once the monthly trace allowance ran out.

---

## 11. Not evaluated yet, or still open

| Open item | Status |
|---|---|
| **Per-rule review** | The per-rule eval's apparent errors in [review.jsonl](../eval/rules/review.jsonl) wait for a verdict; until then M1b, M2 and M3 read as worse than they are ([§3.6](#36-each-rule-on-its-own)) |
| **Rules silver labels can't grade** | S2, P1 and J1 (2 or fewer labelled records each); P2 and X2 never fired. They need hand-labelled sets |
| **Per-rule findings not acted on** | S1 holds back unrelated `… OF <PLACE>` names (1% the sub's); N1 holds back records that are the sub's 85% of the time |
| **Rule M3 on web evidence** | [eval/m3_audit/run.py](../eval/m3_audit/run.py) checks each M3 match against company profiles (same if A's profile lists B's state or both share a website). Written, no results yet. The silver labels can't grade M3: a national firm filing per state looks like two companies |
| **Jev in-state + GLM 5.3 out-of-state** | Best on both samples, but found after the held-out run: needs a fresh seed |
| **A human-labelled gold set** | The silver labels count corporate families as errors (17 of 18). The research report ranks relabelling first; the README plans a LangSmith annotation queue |
| **Profile eval write-up** | Results above; the reasoning for the question approach still to be written into [company-profile.md](company-profile.md) |
| **Model choice for the foreman** and the first adjudicator LLM | No comparative eval recorded |
| **Jev calibration** | Brier 0.20: thresholds are cut-offs, not probabilities |
| **Known matching gaps** | `typo_equal` treats different surnames as slips (HERNANDEZ/FERNANDEZ); companies named after a person are rated "person"; nicknames are different people; `SEVENTH AVENUE` ≠ `7TH AVE`; a slip in a name's first letter is never searched ([audit](name-matching-audit.md#what-is-left-known-not-fixed)) |

---

## Re-running the evals

| Eval | Command | Spends credit? |
|---|---|---|
| Matching (silver pairs, typos, licences) | `uv run python -m eval.matching.run` | No |
| Each matching rule on its own | `make eval-rules` (about 5½ minutes) | No |
| Foreman | `uv run python -m eval.foreman.run` | Yes, one conversation per question |
| Matching, per-rule and foreman together | `make eval` | Yes (the foreman) |
| Adjudicator, both seeds | `make eval-adjudication` | Only for uncached answers; each model runs when its key or URL is set |
| Company profiles | `uv run python -m eval.profile.run --seed 7 --limit 40` | Yes; profiles cached in `profiles.jsonl` |
| M3 audit | `uv run python -m eval.m3_audit.run` | Tavily credits; `--max-searches` caps them |
