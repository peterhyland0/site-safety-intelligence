# Thought process and decision log

How I approached Site Safety Intelligence: what I looked at, what I found, what I decided, and why. Open questions are listed at the end.

**The problem.** A general contractor (GC) is bidding a job and will bring 10–15 subcontractors on site.
- The GC wants to know which subs have a safety history that should worry them.
- The foreman wants to ask plain-English questions about it from the site.
- Scope: a database schema explained in the README, and a quick way for the GC to see information on the subs.

---

## 1. Understanding the domain first

The construction vocabulary needed to be clear before touching the data. A glossary is in [domain-cheat-sheet.md](domain-cheat-sheet.md). The points that shaped the design:

- **Why GCs vet subs ("prequalification").** Under OSHA's multi-employer policy, a GC can be cited as the *controlling employer* for hazards a sub creates. An accident also stops work, raises insurance costs and creates legal exposure.
- **What GCs already use.** Injury rates (TRIR, DART), the workers' comp experience modifier (EMR, which isn't public), and OSHA history. The OSHA data covers the last of these. OSHA's published injury-rate data (Form 300A, which includes hours worked) is the most useful other public data.
- **No record is not a clean record.** OSHA inspects only a small share of workplaces, so a sub with no inspections is *unknown*, not *safe*. The product has to show the two differently.

## 2. Getting the data

**Source.** `enforcedata.dol.gov` now redirects to the DOL Open Data Portal (`data.dol.gov`). I read through the portal's user guide, getting-started page, FAQ, API examples, metadata and about pages, and the OSHA dataset pages.

**Bulk zips vs the API.**

| Option | Facts | Decision |
|---|---|---|
| Bulk "Download Complete Dataset" zips | Official links on each dataset page, refreshed daily. Inspection about 1.4 GB, violation about 2.0 GB. | ✅ Use for the initial load |
| DOL API | Needs an API key (login.gov registration). 10 requests per 10 minutes. At most 10,000 records or 5 MB per request. The violation table can't be filtered by industry. | ❌ Too slow for a full pull (500+ requests for inspections alone). ✅ Good later for daily changes, using `load_dt` / `case_mod_date`. |

**Which tables.** I listed every OSHA table and its fields before choosing.

| Table | Decision | Reason |
|---|---|---|
| inspection | Core | The only table with the employer name, address and industry code. Everything joins to it on `activity_nr`. |
| violation | Core | Citations: type, standard, penalties before and after settlement, deletions, failure-to-abate. |
| accident_injury | Core | The only link from an accident to an inspection (`rel_insp_nr`). |
| accident | Core | Incident summary and fatality flag. |
| accident_abstract | Core (changed my mind) | I first thought it was redundant. Profiling showed `accident.abstract_text` is empty on every row, so this is the only narrative source. |
| accident_lookup2 | Core | Decodes the accident tables' numeric codes. 55 KB. |
| related_activity | Optional | Links inspections to the complaints, referrals and accidents that triggered them. |
| violation_event, violation_gen_duty_std, emphasis_codes, optional_code_info | Skipped for now | Penalty history (current/initial penalty is enough), General Duty narratives (large, narrow), emphasis programs (marginal), internal codes. |

Other DOL datasets (MSHA mines, unemployment claims) are out of scope. Wage and Hour enforcement is noted as a possible future "other behaviour" signal.

## 3. How messy is it? (full scan)

I loaded every row of every core table into DuckDB as raw text and profiled it. Full results with numbers are in [data-profile.md](data-profile.md).

**Clean:**
- the keys (no duplicate inspections or citations)
- dates
- zip codes
- the company mailing address, filled 99.96% of the time

**Messy, ranked by impact:**

1. **No company ID.** 266k distinct raw names across 377k construction inspections since 2015. The messiness includes ID prefixes baked into names (17.6% of inspections, mostly in state-plan states), typos, corporate families, joint ventures, DBAs, and placeholders like "UNKNOWN ROOFER".
2. **Accident detail is stale.** Coverage of accident-type inspections falls from about 85% (2017–19) to 36% (2023–24), 5% (2025) and 0% (2026). One accident is copied onto every employer inspected at a shared site. A 2026 load batch shifted a field into the wrong column.
3. **Recent data is provisional.** 65% of 2026 and 49% of 2025 citations come from still-open cases. Settlements cut penalties 18–36% depending on citation type.
4. **State plans use their own standard codes.** 23% of construction citations since 2015 use them (e.g. Washington `296-155`, Oregon `OAR 437`).
5. **Comparison fields are unreliable.** Industry codes drift within a company (44%), SIC was replaced by NAICS during the 2000s, and employee counts are implausible (max 1,000,000).

**Shared sites.** 32% of construction inspections share a site and date with another employer's inspection. This is the GC and its subs being inspected together. It complicates attributing accidents, but it also links subs to the jobs they worked on.

## 4. How far back to look

**What the data covers:**
- Inspections effectively start in **1972**: 17,164 that year, and 2 in 1971.
- The earliest inspection is dated June 1970, before OSHA existed. It's a single data error.
- Violations start in 1972.
- Accident records only become meaningful in **1984**.

**My lookback rule.** A GC realistically wants two things:
- **5–10 years of history for context:** rates, trends, penalties, hazard types.
- **Unlimited lookback for catastrophic or repeated offences:** fatalities, willful, repeat, failure-to-abate.

**Can the data support it?** Mostly.
- Willful and repeat citations are recorded in every decade, so the all-time tier works.
- Penalty amounts are blank 37–71% of the time before 2010. Old history has to be judged by citation *type*, not dollars.
- Inspection type `M` only appears from the 2010s, and before that accident inspections are all `A`. So no single code means "fatality" across all years. Fatality detection combines inspection type with injury detail where it exists.
- The older the record, the less certain it belongs to today's company: firms are sold and renamed, and names get reused. Old records need lower match confidence and should show the address they were filed under.
- "Repeated" for a GC means more than OSHA's repeat label, which only looks back a limited period. The app can find patterns itself, e.g. fall protection cited in 6 separate inspections over 20 years.

**Consequences:**
- yearly rollups per establishment, so the window is a setting (5 or 10 years) rather than a fixed design
- an all-time red-flag table that always applies
- construction volume across all years: about 2.35M inspections and 4.25M citations, about 6× the 2015+ slice

## 5. Entity resolution: finding the sub in OSHA's records

### How many companies are there?

There's no answer key, so I estimated with a cleanup funnel (construction inspections):

| Step | Since 2015 | All years |
|---|---|---|
| Raw distinct names | 265,936 | 1,204,474 |
| Strip ID prefixes, punctuation, legal suffixes | 198,377 (−25%) | 822,826 (−32%) |
| …split by mailing state | 217,744 | 1,008,943 |
| Distinct mailing addresses | 237,360 | 1,074,173 |
| Names seen only once | 135,653 | 539,259 |

**Estimate:** roughly 190k–220k companies since 2015, and 0.8–1.0M across all years.
- Splitting by state *raises* the count, because the same name in two states may be two companies.
- Addresses aren't a clean key either: companies move, and addresses are typed inconsistently.

**Fuzzy matching test.** I used Jaro-Winkler similarity of 0.95 or more, within the same state.
- It found only 5,406 additional near-duplicates, about 2.7% more merging.
- In a 20-pair spot check, about 14 were right, 3 were clearly wrong and 3 were unclear. The wrong ones were initials-style names: `C AND A CONSTRUCTION` vs `C AND S CONSTRUCTION`.
- **Conclusion:** fuzzy matching should *suggest* candidates, never merge automatically.

### Influence: the ContextOne entity-matching pipeline

AI One's public paper *ContextOne: A Context and Control Architecture for Enterprise AI* (March 2026) describes a five-stage entity-matching pipeline. I adapted it rather than adopting it wholesale:

| Their stage | My adaptation | Why |
|---|---|---|
| LLM-based standardization | **Rules first**; LLM only for leftovers (DBAs, joint ventures, placeholders) | The quirks are predictable. Rules are free, testable and give the same answer every time. Rules alone cut names 25–32%. |
| Deterministic matching on hard identifiers | Kept, but weak | OSHA has no hard identifiers (no EIN, no company ID). The closest is exact cleaned name + address. |
| Fuzzy matching | Kept for **candidate generation only** | About 1 in 6 fuzzy merges was wrong in the spot check. |
| Semantic embeddings | **Skipped** | Company-name embeddings mostly capture trade words ("Smith Roofing" ≈ "Jones Roofing"). |
| LLM adjudicator with confidence + rationale | Kept, **run only on the GC's 10–15 subs** | The rationale is exactly what a GC needs to defend a decision. Running it on 1.2M names would be slow and costly. |

### Establishments: the safe grouping step

The pipeline groups inspections only when the cleaned name, cleaned mailing address and zip are **identical**. That group is an *establishment*, keyed by a hash of those three values so the key is stable across rebuilds.

Real example: Brasfield & Gorrie since 2015 comes out as **58 establishments plus 1 lookalike**:
- **Regional offices.** Genuinely different places: Birmingham AL, Georgia, Atlanta, Nashville and more.
- **Address and suffix variants** that better rules will collapse: `7TH AVE SOUTH` vs `7TH AVE S`, `GP`, `L P`.
- **Typos** that rules can't fix: `GORIE`, zip `35223`, `VAUGN`.
- **Brasfield Construction** in Tennessee: a *different company*.

**Why stop at exact matches:** the two kinds of mistake cost different amounts.
- Splitting too much costs a little review effort.
- Merging too much silently attaches someone else's history, possibly a fatality, to the sub.

### Don't hand the work to the GC

Given the goal (a *quick* way for the GC to see info on the subs), asking the GC to confirm dozens of establishments per sub is wrong. Revised rule: **the system matches; the GC only reviews exceptions that would change the verdict.**

The GC enters the sub's name plus city and state, which they already have from bid paperwork. Results come back in three buckets, and nothing is hidden:

| Bucket | Contents | Counted in the scorecard? |
|---|---|---|
| **Matched** | Same cleaned name in the GC's state · same name at the same address (even with typos) · same **distinctive** name in other states (noted as "also operates in …") | ✅ |
| **Possibly the same company** | Same **generic** name in another state (e.g. "ABC Roofing", initials-style names) · similar name at a different address | ❌ Shown as "+N inspections if these are yours" |
| **Excluded lookalikes** (collapsed) | Different name core (e.g. Brasfield **Construction**) | ❌ |

- **Distinctive vs generic** is measured from the data. A name whose words appear in few establishments is distinctive. A name found at many unrelated addresses and trades is generic.
- **Red-flag override:** any "possible" record carrying a fatality, willful, repeat or failure-to-abate citation becomes a direct yes/no question to the GC. A dangerous record is never silently dropped and never silently attributed.
- **Assumption, stated in the README:** matching is automatic, and the GC is only asked to confirm uncertain matches that carry red flags.

## 6. Answering the foreman's questions

**Named queries, not free-form SQL.** This is also from the ContextOne paper ("Named Queries").
- **Free-form text-to-SQL** writes a new query every time. It can silently use the wrong company, miss state codes, count deleted citations, or give different answers to the same question.
- **Named queries** are written and tested once; the LLM only picks one and fills in parameters. Examples: `sub_summary`, `citations_by_hazard`, `fatality_history`, `compare_subs`.
- **Trade-off:** named queries can only answer what was planned for. For a safety tool, I'd rather be consistent and limited than flexible and sometimes wrong. Unanswerable questions are logged to decide which query to add next.

**Other ideas adapted from the paper, implemented as plain code:**
- **One meaning per business term.** A hazard-category map gives "fall protection" one meaning across federal and state codes.
- **Precondition check.** No answer about a sub's history until its match is settled.
- **Grounding check.** Every number in an answer must come from a query result and link to an inspection ID.
- **Lineage.** Every flag traces back to its source inspections and citations, with links to osha.gov.

Skipped from the paper: the large-scale agent runtime, memory engine, Z3 constraint solver, cryptographic audit ledger and access-control stack. They solve problems a 15-sub lookup tool doesn't have.

## 7. Cleaning, completeness and outliers

**Clean once, in layers.** Raw files → clean tables → establishments → scorecards → named queries. Queries never touch raw data, so every query inherits the same fixes.

**Flag, don't delete.** Data-quality problems are recorded as flags on the row, and the original values stay traceable.

**How the named queries are kept complete:**
- Design from the GC's decisions backwards, and check every decision has a query.
- Every citation lands in exactly one hazard category, including an explicit "other / unmapped" bucket, so totals always add up.
- A full-record query always returns every inspection and citation for a sub.
- Every answer states its coverage, e.g. "14 inspections, 2016–2026; 3 cases open; accident detail unavailable after 2024".
- Test the queries against hand-checked companies on OSHA's own website.

**Outliers: is it an error or real?**

| Kind | Example | Handling |
|---|---|---|
| Data error | 1,000,000 employees; closed before opened | Flag; exclude from calculations; show in detail |
| Placeholder employer | `UNKNOWN INVALID ESTABLISHMENT` | Exclude from search and benchmarks |
| Real extreme | $3.6M penalty; a fatality; 200 inspections | **Never remove**: this is the signal |
| Too little data | 1 inspection, 1 serious citation ("100% serious") | Show counts next to rates; minimum sample size for comparisons |
| Skews comparisons | One mega-contractor in a trade | Compare against median and percentiles, not the average |

## 8. Architecture and tools

**DuckDB to build, Postgres to serve.**

DuckDB runs the pipeline:
- It reads the CSVs directly and processes only the columns a query needs.
- It spreads the work across all CPU cores. In profiling, 5.2M inspections loaded in about 13 s and 13.3M violations in about 10 s.

| Pipeline alternative | Verdict |
|---|---|
| Polars | Equally good; DuckDB chosen to keep one language (SQL) across pipeline and schema |
| pandas | Loads everything into memory and mostly uses one core |
| Do it all in Postgres | Viable, but slow import, 7 GB of raw text in the serving database, and rebuilds compete with the app |
| Spark / BigQuery / Snowflake | Built for far bigger data; setup and cost not justified |
| dbt | An add-on, not an alternative; possible next step for structure and data tests |

Postgres serves the app:
- **Integrity:** relational data with foreign keys and checks.
- **Fuzzy search built in:** `pg_trgm`.
- **Safe writes:** transactions for match decisions while several people use the app.
- **Reporting features:** materialized views, arrays and JSON.
- **Familiar:** easy to host and widely known.

| Serving alternative | Verdict |
|---|---|
| SQLite | Simplest, but no typo-tolerant search built in, and saving decisions is awkward on read-only hosts. A fallback if hosting cost bites. |
| MySQL | Works, but no materialized views or trigram equivalent |
| MongoDB | The data is all relationships; documents would duplicate shared-site accidents |
| Neo4j | Good for relationship hops; the core queries are counts over time. Future work. |
| Elasticsearch | Best fuzzy search, but a second system to keep in sync |
| BigQuery / Snowflake | Overkill and too slow and costly behind an interactive app |

**Where the pipeline runs.**
- It needs about 10 GB of disk, a few GB of memory and 2–4 cores.
- A normal server (VM or container) can run it as a nightly job.
- Serverless hosting (e.g. Vercel functions) can't, because of small disk, memory and time limits. If the app is serverless, the pipeline runs on a laptop, a scheduled GitHub Action or a small VM.

## 9. Schema (draft)

Five Postgres schemas, layered by trust:

| Schema | Contents | Rebuildable? |
|---|---|---|
| `ref` | Lookups: violation types, inspection types, hazard categories, standard-code → hazard map (federal and state) | Hand-maintained in the repo |
| `osha` | Cleaned OSHA facts: `inspection`, `violation`, `accident`, `accident_inspection` (many-to-many), `injury` | Yes |
| `entity` | `establishment`: exact-match groups with name variants, primary NAICS, placeholder flag | Yes |
| `app` | `project` (with lookback setting), `project_sub`, `sub_match` (bucket, method, confidence, rationale, who decided), `question_log` | **No: human decisions** |
| `mart` | Yearly rollups per establishment, hazard-by-year, all-time red flags, trade benchmarks (median and percentiles) | Yes |

**Key principles:**
- **No global "company" table.** A company exists only as the set of establishments matched to a GC's sub.
- **Stable hash keys,** so rebuilds don't break saved match decisions.
- **Yearly rollups** make the lookback window a setting.
- **Shared-site accidents are many-to-many,** so they're never pinned on every employer.
- **Data-quality flags, nullable penalties (blank ≠ $0), and an "other" hazard bucket** keep every quirk visible.
- **Rows that fail integrity checks are quarantined with a reason,** not dropped.

## 10. Open questions and next steps

- [ ] **Front end:** Next.js web app (mobile-friendly for the foreman) vs a simpler option.
- [ ] **Anthropic API key** for the LLM adjudicator and foreman Q&A.
- [ ] **Federal OSHA only, or state plans too?** Leaning towards including state plans and labelling who did the inspection.
- [ ] **Hosting and size:** full construction history is roughly 1–1.5 GB with indexes. Option: keep citation-level detail for 10 years plus all red-flag events, and rely on rollups for the rest.
- [ ] **Confirm code meanings:** inspection types `A` vs `M`, and how `reporting_id` tells federal from state inspections.
- [ ] **Tighten cleaning rules:** `S`/`SOUTH`, `&`/`-`/`AND`, suite numbers.
- [ ] **Build a labelled evaluation set** (~200 candidate pairs) and report matching precision and recall.
- [ ] **Write the README:** schema rationale, trade-offs and the stated assumptions above.
