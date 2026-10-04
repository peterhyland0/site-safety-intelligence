# Thought process and decision log

How I approached Site Safety Intelligence: what I looked at, what I found, what I decided, and why. Where a decision changed once I'd built and measured something, both the first plan and what I ended up with are kept, with the reason. Open questions are at the end, with how each was settled.

**The problem.** A general contractor (GC) is bidding a job and will bring 10–15 subcontractors on site.
- The GC wants to know which subs have a safety history that should worry them.
- The foreman wants to ask plain-English questions about it from the site.
- The data is OSHA enforcement data: at least the inspection and violation tables, which are messy. Other public data might help.
- Scope: a database schema explained in the README, a quick way for the GC to see information on the subs, and a README with the decisions and trade-offs.

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
| Bulk "Download Complete Dataset" zips | Official links on each dataset page, refreshed daily. Inspection about 1.4 GB, violation about 2.0 GB. | ✅ Use for every build |
| DOL API | Needs an API key (login.gov registration). 10 requests per 10 minutes. At most 10,000 records or 5 MB per request. The violation table can't be filtered by industry. | ❌ Too slow for a full pull (500+ requests for inspections alone). Still the plan for daily changes, using `load_dt` / `case_mod_date`. |

**Which tables.** I listed every OSHA table and its fields before choosing.

| Table | Decision | Reason |
|---|---|---|
| inspection | Core | The only table with the employer name, address and industry code. Everything joins to it on `activity_nr`. |
| violation | Core | Citations: type, standard, penalties before and after settlement, deletions, failure-to-abate. |
| accident_injury | Core | The only link from an accident to an inspection (`rel_insp_nr`). |
| accident | Core | Incident summary and fatality flag. |
| accident_abstract | Core (changed my mind) | I first thought it was redundant. Profiling showed `accident.abstract_text` is empty on every row, so this is the only narrative source. |
| accident_lookup2 | Core | Decodes the accident tables' numeric codes. 55 KB. |
| related_activity | Optional, not loaded | Links inspections to the complaints, referrals and accidents that triggered them. |
| violation_event, violation_gen_duty_std, emphasis_codes, optional_code_info | Skipped | Penalty history (current/initial penalty is enough), General Duty narratives (large, narrow), emphasis programs (marginal), internal codes. |

Other DOL datasets (MSHA mines, unemployment claims) are out of scope. Wage and Hour enforcement is noted as a possible future "other behaviour" signal.

**Other public data.** I evaluated four sources; details are in [README §6](../README.md#6-other-public-data).

| Source | Decision |
|---|---|
| OSHA ITA 300A injury filings (2016–2025) | ✅ Injury rates (TRIR, DART) against the trade's pooled rate. The EIN is evidence for the adjudicator, never an automatic merge: big firms file under many EINs. |
| WA L&I and Oregon CCB licences | ✅ Verified legal names; a GC can enter a licence number to pin a sub |
| California CSLB licences | Partial: the server cuts the download at about 15 MB |
| SAM.gov, OpenCorporates | ❌ Need an account or a paid key |

The surprise: none of these merges OSHA records much. Grouping by cleaned name within a state already merges more than any outside ID. Their value is verified identity and injury rates.

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

**What I first wanted.** A GC realistically wants two things:
- **5–10 years of history for context:** rates, trends, penalties, hazard types.
- **No time limit for catastrophic or repeated offences:** fatalities, willful, repeat, failure-to-abate.

**Can the data support it?** Mostly.
- Willful and repeat citations are recorded in every decade, so a no-limit tier works.
- Penalty amounts are blank 37–71% of the time before 2010. Old history has to be judged by citation *type*, not dollars.
- Inspection type `M` only appears from the 2010s, and before that accident inspections are all `A`. So no single code means "fatality" across all years. Fatality detection combines inspection type with injury detail where it exists.
- The older the record, the less certain it belongs to today's company: firms are sold and renamed, and names get reused.
- "Repeated" for a GC means more than OSHA's repeat label, which only looks back a limited period. The app can find patterns itself, e.g. fall protection cited in 6 separate inspections over 20 years.

**What I built first: every year.** The first warehouse held everything back to 1972: about 2.5M inspections, 5M citations and 217k red-flag events, in 1.38 GB. Two windows sit on top of it, and both are still there:
- **The project window** (3, 5 or 10 years), chosen per project, for rates, trends and penalties. Yearly rollups per establishment make it a setting rather than a schema decision.
- **The red-flag table**, which covers the whole history kept. A cited fatality, willful violation or failure-to-abate inside the last 10 years makes a sub **High concern**; an older one makes it **Review**, never High.

**Then I weighed cutting it to 10 years.** It was a real trade-off, so I measured both sides on the all-years build. That build predates some later rule fixes, so the counts are approximate.

*What keeping every year buys:*
- About 210,000 establishments were inspected in the last 10 years. About 1,700 of them also have a cited fatality, willful violation or failure-to-abate from before that.
- For about 1,400 of them it's their only red flag. With 10 years kept, those subs show nothing of it and can read "No flags".
- About 760 of those 1,400 have the event 10–20 years back; for the rest it's more than 20 years old.
- Slightly more precise matching. More history means more spelling variants per name, so fewer names look "distinctive" and auto-match across offices. Auto-match precision was 0.90 on all years and 0.85 on 10 years (different samples). The extra 10-year auto-matches are mostly corporate families filing under several tax IDs ([README §8](../README.md#8-evaluation)).

*What keeping 10 years buys:*
- A 210 MB warehouse instead of 1.38 GB, about 6.5× smaller. The server copies it to local disk on every cold start, so this means faster starts and cheaper hosting.
- Records a GC can defend. Old records are the least certain to belong to today's company, and a new owner trading under the same name at the same address can't be told apart. For nearly half of the 1,400 subs above, the old event is more than 20 years back.
- Prequalification forms usually ask about the last 3–5 years, so 10 years already goes further back than the GC's own paperwork.
- Little lost on money: penalties are mostly blank before 2010, so old records only ever counted by citation type.

**What actually matters.** The verdict is driven almost entirely by the last 10 years. Older events could only ever raise a sub to Review, and they're the only red flag for about 0.7% of companies inspected in the last decade. That's rare. But it's also the case a GC would most want to hear about: a sub with a fatality in its past and a clean recent record. So the old history stays one setting away instead of being removed.

**Decision (3 October): 10 years by default, every year one setting away.**
- `SSI_HISTORY_YEARS=10` is the default. `0` builds everything back to 1972, and the pipeline and tests run on both.
- Which establishments count as construction companies is decided from every year, and the cut comes after that. The first version cut first, and that dropped 5,817 recent inspections of firms coded as construction only in earlier years. A build check now recounts scope independently.
- Windows compare dates, not calendar years, so an event from October 2016 still counts in data dated September 2026.
- With the default, the "older than 10 years → Review" rule never fires; it comes back with `SSI_HISTORY_YEARS=0`.

**What I'd build next.** A middle ground: full detail for the last 10 years, plus every year's red flags and the names and addresses needed to match them. The red-flag table is only 217k rows, but attaching an old flag to a sub means matching the old records too, which needs about 1.3M establishments of names and addresses.

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
| LLM-based standardization | **Rules only** | The quirks are predictable. Rules are free, testable and give the same answer every time. Rules alone cut names 25–32%. I'd planned an LLM for leftover DBAs and joint ventures, but rules covered them. |
| Deterministic matching on hard identifiers | Kept, but weak | OSHA has no hard identifiers (no EIN, no company ID). The closest is exact cleaned name + address. A licence number the GC enters is the one hard link (rule L1). |
| Fuzzy matching | Kept for **candidate generation only** | About 1 in 6 fuzzy merges was wrong in the spot check. |
| Semantic embeddings | **Skipped** | Company-name embeddings mostly capture trade words ("Smith Roofing" ≈ "Jones Roofing"). |
| LLM adjudicator with confidence + rationale | Kept, **run only on the GC's 10–15 subs** | The rationale is exactly what a GC needs to defend a decision. Running it on 1.2M names would be slow and costly. |

### Establishments: the safe grouping step

The pipeline groups inspections only when the cleaned name, address key, zip and state are **identical**. That group is an *establishment*, keyed by a hash of those values so the key is stable across rebuilds.

Real example: in the first build, Brasfield & Gorrie since 2015 came out as **58 establishments plus 1 lookalike**:
- **Regional offices.** Genuinely different places: Birmingham AL, Georgia, Atlanta, Nashville and more.
- **Address and suffix variants** that better rules will collapse: `7TH AVE SOUTH` vs `7TH AVE S`, `GP`, `L P`.
- **Typos** that rules can't fix: `GORIE`, zip `35223`, `VAUGN`.
- **Brasfield Construction** in Tennessee: a *different company*.

**Why stop at exact matches:** the two kinds of mistake cost different amounts.
- Splitting too much costs a little review effort.
- Merging too much silently attaches someone else's history, possibly a fatality, to the sub.

Keys are stable only while the cleaning rules are. When a rule changes, some records get new keys, so every match decision also stores its record's inspection IDs, which never change, and `scripts/rematch.py` moves each decision to the keys that now hold them.

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
- **The GC can move any record** between buckets. That's stored as a GC decision and always wins.
- **Assumption, stated in the README:** matching is automatic, and the GC is only asked to confirm uncertain matches that carry red flags.

These three rules grew to about fifteen as evaluation and two reviews found cases they got wrong: people's names (sole proprietors), branches, joint ventures, sibling companies, names that differ by a trade word, and a safety net that never lets a rule exclude a red-flagged record at an address the company uses. The full table is in [README §3](../README.md#3-matching-subs-to-osha-records), and the audit behind it is in [name-matching-audit.md](name-matching-audit.md).

### Where the adjudicator runs

The adjudicator runs in one place only: **when the GC adds a sub, and only on the candidates the rules can't sort confidently.** It never touches the pipeline, the scorecard numbers or the red flags.

```
GC enters sub (name, city, state)
   │
   ▼
1. Find candidates ─────── exact alias · same name core · rarest name words (typo-tolerant)    (DuckDB, no AI)
   │                       · records at already-matched addresses
   ▼
2. Rules sort them ─────── ordered rules → MATCHED / UNCERTAIN / EXCLUDED, each with a rule ID   (no AI)
   │
   ▼
3. AI adjudicator ──────── runs ONLY on the UNCERTAIN ones, grouped by name and state
   │                       no red flag → Jev; red flag → DeepSeek V4.1 Flash
   ▼
4. Red-flag check ──────── uncertain record with a fatality/willful/repeat/failure-to-abate?
                           → a yes/no question to the GC, with the AI's lean and reason
```

**What counts as uncertain:**

| Case | Why the rules can't decide | What the adjudicator weighs |
|---|---|---|
| Generic name in another state | "ABC Roofing" in two states could be one company or two | Same trade? Overlapping years? Any shared address? |
| Similar name, different address | Typo or a different company? | e.g. `BRASFIELD AND GORRIE GENERAL CONTRACTOR` at a Birmingham address that isn't the HQ |
| Related legal entities | Same family, different company | e.g. `CLARK CONCRETE CONTRACTORS` vs `CLARK CONSTRUCTION GROUP` at the same HQ |
| DBA vs legal name | Two names for the same thing | e.g. `XYZ LLC DBA ABC ROOFING` vs `ABC ROOFING` |

**What it sees and returns:**
- **Identity evidence only:** what the GC entered, the candidate's name spellings, addresses, trade code and years active, and the establishments already matched. **It is not shown the safety history**, so a fatality can't bias whether a record is judged "the same company".
- **Structured output checked in code:** `{ "bucket": "possible", "confidence": 0.55, "rationale": "Same trade (roofing) and active 2016–2023 like the matched records, but a different city and no shared address." }`. Code rejects any rationale that cites evidence not in its input.
- **Saved and auditable:** each decision is cached by a hash of the model and the evidence (`app.adjudication_cache`), so the same evidence is never decided twice, across projects and rebuilds. The result lands in `app.sub_match` with the method, confidence and rationale.

**Which model.** I started with an LLM for every uncertain group. In October, Jev, a decision model that returns a label with a probability instead of text, beat it on a held-out sample: 130 lookalikes excluded against 110, 9 wrong exclusions against 13, and no wrong merges against 2, in a quarter of the time. Red-flagged groups stay with the LLM because the GC reads its reason. The comparison is in [adjudicator.md](adjudicator.md).

**The limits on what it decides:**
- **Confident "same"** → matched, labelled as decided by AI rather than hidden.
- **Unsure** → possible: shown as "+N if these are yours" and not counted.
- **Confident "different"** → excluded.
- **Anything carrying a red flag** → the AI never decides alone. It gives its lean and reason; the GC answers.

**Added later: company profiles.** The rules and the adjudicator only see OSHA's data, so a sub's plants and branches in other states mostly stayed "possible". When the GC ticks a box (off by default, because each lookup costs credits), Claude looks the sub up on the web and lists the locations the company publishes, each with a quote from the page. OSHA records at those locations become one question to the GC. Nothing is matched from the web on its own. Details: [company-profile.md](company-profile.md).

**Without an AI key, the app still works** in a rules-only mode: uncertain candidates stay "possible".

## 6. Answering the foreman's questions

**Named queries, not free-form SQL.** This is also from the ContextOne paper ("Named Queries").
- **Free-form text-to-SQL** writes a new query every time. It can silently use the wrong company, miss state codes, count deleted citations, or give different answers to the same question.
- **Named queries** are written and tested once; the model only picks one and fills in parameters. There are about 12, e.g. `sub_summary`, `citations_by_hazard`, `fatality_history`, `compare_subs`. The same functions power the GC's view, so a term means the same thing in both.
- **Trade-off:** named queries can only answer what was planned for. For a safety tool, I'd rather be consistent and limited than flexible and sometimes wrong. Unanswerable questions are logged to decide which query to add next.

**Other ideas adapted from the paper, implemented as plain code:**
- **One meaning per business term.** A hazard-category map gives "fall protection" one meaning across federal and state codes.
- **Precondition check.** No answer about a sub's history until its match is settled.
- **Grounding check.** Every number in an answer must come from a query result, and every inspection ID must be one a query returned.
- **Lineage.** Every flag traces back to its source inspections and citations, and each opens its record in the app. osha.gov numbers inspections differently from the published data, so its link is a search by employer, state and opening day.

Skipped from the paper: the large-scale agent runtime, memory engine, Z3 constraint solver, cryptographic audit ledger and access-control stack. They solve problems a 15-sub lookup tool doesn't have.

## 7. Cleaning, completeness and outliers

**Clean once, in layers.** Raw files → clean tables → establishments → scorecards → named queries. Queries never touch raw data, so every query inherits the same fixes. A sub the GC types in is cleaned by the same rules that built the data.

**Flag, don't delete.** Data-quality problems are recorded as flags on the row, and the original values stay traceable.

**How the named queries are kept complete:**
- Design from the GC's decisions backwards, and check every decision has a query.
- Every citation lands in exactly one hazard category, including an explicit "other / unmapped" bucket, so totals always add up.
- A full-record query always returns every inspection and citation for a sub.
- Every answer states its coverage, e.g. "14 inspections, 2016–2026; 3 cases open; accident detail through March 2025".
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

**First plan: DuckDB to build, Postgres to serve. Built: DuckDB builds and serves the facts; Postgres holds only the decisions.**

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

**Why I planned Postgres for serving:**
- **Integrity:** relational data with foreign keys and checks.
- **Fuzzy search built in:** `pg_trgm`.
- **Safe writes:** transactions for match decisions while several people use the app.
- **Reporting features:** materialized views, arrays and JSON.
- **Familiar:** easy to host and widely known.

**Why I changed it.** The OSHA facts never change between builds, and the app only reads them. So the warehouse file the build produces *is* the serving copy: DuckDB opens it read-only, in-process, with no import step. Each build writes a new file and swaps a `CURRENT` pointer only if every error-level check passed, so a failed build never replaces live data. Postgres keeps the job it's best at: small, concurrent writes of the GC's decisions, accounts and chats.
- **Cost:** two stores, joined in API code. That's cheap, because a sub's scope is tens of keys.
- **Cost:** DuckDB has no trigram index, so candidate search uses a token-blocking table plus Jaro-Winkler.
- **Cost:** decisions can't have foreign keys into the warehouse. Stable hash keys, plus the stored inspection IDs (§5), stand in for them.

| Serving alternative | Verdict |
|---|---|
| DuckDB, read-only, in-process | ✅ Chosen for the facts |
| Postgres | ✅ Chosen for decisions only |
| SQLite | Simplest, but no typo-tolerant search built in, and saving decisions is awkward on read-only hosts |
| MySQL | Works, but no materialized views or trigram equivalent |
| MongoDB | The data is all relationships; documents would duplicate shared-site accidents |
| Neo4j | Good for relationship hops; the core queries are counts over time. Future work: which subs keep turning up on the same sites |
| Elasticsearch | Best fuzzy search, but a second system to keep in sync |
| BigQuery / Snowflake | Overkill and too slow and costly behind an interactive app |

**Front end.** A Vite + React + Tailwind single-page app, talking to a FastAPI backend. Mobile-first: the foreman's view is designed for a 375 px phone screen.

**Where it runs.**
- The pipeline needs about 10 GB of disk, a few GB of memory and 2–4 cores. Serverless hosting (e.g. Vercel functions) can't run it, because of small disk, memory and time limits.
- So the deploy is split: the static site on Vercel; the API, the nightly rebuild and the AI models on Modal. It's prepared ([deploy.md](deploy.md)) but not deployed; the app currently runs locally.

## 9. Schema

The draft had five Postgres schemas. What was built is six layers in two stores, split by trust and by whether they can be rebuilt:

| Layer | Store | Contents | Rebuildable? |
|---|---|---|---|
| `ref` | DuckDB | Lookups: violation types, inspection types, hazard categories, standard-code → hazard map (federal and state) | From the repo's CSVs |
| `osha` | DuckDB | Cleaned OSHA facts: `inspection`, `violation`, `accident`, `accident_inspection` (many-to-many), `injury`, `quarantine` | Yes |
| `entity` | DuckDB | `establishment`: exact-match groups with name variants, distinctiveness and shared-office stats, links to reference data | Yes |
| `ref_ext` | DuckDB | ITA injury rates, state licences | Yes |
| `mart` | DuckDB | Yearly rollups per establishment, hazard-by-year, red flags over the whole history kept, trade benchmarks (median and percentiles) | Yes |
| `app` | Postgres | Projects (each with its lookback window), subs, match decisions (bucket, method, confidence, rationale, who decided), match questions, the AI decision cache, question logs, users and chats | **No: human and AI decisions** |

**Key principles:**
- **No global "company" table.** A company exists only as the set of establishments matched to a GC's sub.
- **Stable hash keys,** so rebuilds don't break saved match decisions; decisions follow their inspections when a rule change moves a key.
- **Yearly rollups** make the lookback window a setting.
- **Shared-site accidents are many-to-many,** so they're never pinned on every employer.
- **Data-quality flags, nullable penalties (blank ≠ $0), and an "other" hazard bucket** keep every quirk visible.
- **Rows that fail integrity checks are quarantined with a reason,** not dropped.

The full rationale, with what each choice costs, is in [README §1](../README.md#1-the-database-schema-and-why-its-structured-this-way).

## 10. Open questions and how they were settled

- [x] **Front end:** Next.js vs something simpler. Settled: a Vite + React single-page app, with the API in Python (§8).
- [x] **AI models.** Settled: GLM 5.3 answers the foreman, Jev and DeepSeek V4.1 Flash adjudicate (§5), all through a provider switch. Claude is used only for the optional company profiles.
- [x] **Federal OSHA only, or state plans too?** Settled: both, labelled by who inspected (`jurisdiction`), with the hazard map covering state codes.
- [x] **Hosting and size.** Settled: 10 years by default, a 210 MB warehouse; every year is one setting away (§4).
- [x] **Confirm code meanings.** Settled: the inspection-type codes are confirmed against DOL's own dataset metadata. `reporting_id`'s third digit `5` marking state-plan offices is evidence-based, not documented: it holds for 99.98% of inspections citing state-specific codes.
- [x] **Tighten cleaning rules** (`S`/`SOUTH`, `&`/`-`/`AND`, suite numbers). Settled, and audited against every name in the warehouse ([name-matching-audit.md](name-matching-audit.md)).
- [x] **Build a labelled evaluation set.** Settled: 300 silver-labelled pairs from shared tax IDs in the injury filings ([eval/matching/](../eval/matching/)), plus an adjudicator eval ([eval/adjudication/](../eval/adjudication/)).
- [x] **Write the README:** schema rationale, trade-offs and the stated assumptions above.

**Still open:**
- [ ] Every year's red flags on top of 10 years of detail (§4).
- [ ] Daily incremental updates through the DOL API instead of full rebuilds.
- [ ] A human-labelled gold set for matching, to replace the silver labels.
- [ ] Deploying the prepared Vercel + Modal setup.
