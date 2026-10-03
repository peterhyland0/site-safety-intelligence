# OSHA enforcement data: profile

What the raw data looks like, where it's broken, and what that means for the design.

## Method

- **Source:** the "Download Complete Dataset" files on the DOL Open Data Portal (data.dol.gov), downloaded 2026-10-02. The files were refreshed that morning.
- **Loading:** every column loaded as text into DuckDB 1.4.5, so the raw values could be inspected before any type conversion.
- **Coverage:** full scans of every row, no sampling.
- **CSV parsing:** some violation rows contain quoted commas, so the quote and escape settings had to be set explicitly. No rows were rejected after that.

| Table | Rows | Notes |
|---|---|---|
| inspection | 5,202,096 | One row per inspection. Opened 1970-06-20 to 2026-09-23. |
| violation | 13,275,884 | One row per citation item. |
| accident | 165,801 | One row per investigated incident. Events 1972-09-21 to **2025-03-28**. |
| accident_injury | 231,809 | One row per injured person per related inspection. |
| accident_abstract | 1,151,160 | Narrative text lines for 165,794 accidents (up to 110 lines each). |
| accident_lookup2 | 861 | Code decodes for the accident tables (14 code families). |

**Working scope for the deep checks:** construction inspections opened on or after 2015-01-01. Construction means NAICS starting `23` or SIC starting `15`, `16` or `17`. That gives **377,497 inspections** and **685,781 citations**. The 2015 cut-off is a working choice, not a final decision.

## Summary

The data is structurally clean but semantically messy:

- **Clean:** keys, dates and zip codes.
- **Messy:** which company a record belongs to, how coverage changes over time and between states, and values that keep changing after they're recorded.

| # | Problem | Impact on "which subs should worry me" |
|---|---|---|
| 1 | No company identifier; names are inconsistent | Can't find a sub's full history without entity resolution |
| 2 | Accident detail is stale and incomplete for recent years | Fatality flags can't rely on the accident tables |
| 3 | Recent citations are provisional | Counts and penalties for the last ~2 years will change |
| 4 | State plans use their own standard codes | Hazard-type questions ("fall protection?") miss ~23% of citations unless state codes are mapped |
| 5 | Industry codes and employee counts are unreliable | Peer comparison and size normalisation need care |
| 6 | Minor integrity issues | Small counts; filter or flag |

## What's clean

- **Inspection key:** `activity_nr` is unique across 5,202,096 rows, with no duplicate or conflicting versions.
- **Violation key:** `(activity_nr, citation_id)` is unique across 13,275,884 rows.
- **Dates:** every `open_date` parses and none are in the future.
- **Site zip codes (construction 2015+):** 99.9% are 5-digit; the rest are null.
- **Company mailing address:** `mail_street` is blank in only 0.04% of construction inspections.

## 1. Company identity

OSHA records the employer name as typed on each inspection. There is no company ID, no EIN and no link between inspections of the same employer.

**Name variation (construction 2015+)**

| Step | Distinct names | Change |
|---|---|---|
| Raw `estab_name` | 265,936 | |
| Uppercased | 265,936 | Already uppercase |
| Punctuation stripped | 252,396 | −5.1% |
| Legal suffixes stripped (INC, LLC, CO, CORP…) | 237,321 | −10.8% total |

Simple normalisation merges only about 11% of variants. What's left:

- **ID prefixes in names.** 66,295 inspections (**17.6%**) have names like `WA317965935 - BARNHART CRANE & RIGGING CO` or `105314 - BARTON MALOW`. They're concentrated in state-plan states: WA 23,409, NC 14,050, OR 13,115, MN 6,632, IN 3,244, KY 3,135. One mailing address alone carries 77 distinct names because of this.
- **Typos:** `BRASFIELD & GORIE GP, L.L.C.` vs `BRASFIELD & GORRIE GP, L.L.C.`
- **Corporate families:** `BARTON MALOW BUILDERS LLC`, `BARTON MALOW COMPANY` and `BARTON MALOW CONSTRUCTION SERVICES` share one address. `CLARK CONSTRUCTION GROUP LLC` and `CLARK CONCRETE CONTRACTORS, LLC` also share one.
- **Joint ventures and DBAs:** 641 names contain JV or JOINT VENTURE, and 3,543 contain a DBA ("doing business as") marker.
- **Placeholders:** 2,989 names match UNKNOWN, N/A or NONE patterns. Examples: `UNKNOWN` (783), `UNKNOWN CONTRACTOR` (686), `UNKNOWN/INVALID ESTABLISHMENT` (145), `UNKNOWN ROOFER` (116). One placeholder spans 19 different NAICS codes.
- **Whitespace junk:** 1,291 names have leading, trailing or doubled spaces.

**Addresses**

- **The site address is the job site, not the company.** `site_address` differs from `mail_street` on **95.7%** of construction inspections.
- **The site is often in another state.** In 13.1% of inspections the site state differs from the mailing state, so matching on the site's state would miss cross-state work.
- **The mailing address is the best stable key.** But it over-merges. For example, `221 JONESTOWN ROAD, 27104` carries 66 distinct names across different companies sharing an office (`SHUGART MANAGEMENT`, `CLAYTON PROPERTIES GROUP`, …).
- **National contractors file from regional offices:** `WHITING TURNER CONTRACTING` appears with mailing addresses in 24 states, `TURNER CONSTRUCTION` in 23, and `GILBANE BUILDING` in 19.

## 2. Accident and fatality data

**The accident tables stop in early 2025 and thin out well before that.** The table below counts construction inspections of the accident-related types (`A` and `M`, see note below), and how many have any accident detail.

| Year opened | Accident-type inspections | With accident detail | Coverage |
|---|---|---|---|
| 2015 | 1,554 | 604 | 39% |
| 2017 | 1,447 | 1,206 | 83% |
| 2019 | 1,518 | 1,296 | 85% |
| 2021 | 1,366 | 709 | 52% |
| 2023 | 1,465 | 534 | 36% |
| 2024 | 1,404 | 531 | 38% |
| 2025 | 1,458 | 80 | 5% |
| 2026 | 1,083 | 0 | 0% |

**Accident volume swings with reporting changes, not real-world changes.** All-industry accident records were about 1,700 a year in 2015–16, 7,500–9,200 a year in 2017–21, and 1,800–3,000 a year in 2022–24.

**Other accident-table problems**

- **Empty narrative column.** `accident.abstract_text` is empty on every row. Narratives only exist in `accident_abstract`, split across up to 110 lines that must be reassembled in `line_nr` order. Coverage there is about 100%.
- **Multi-employer duplication.** One accident is copied to every related inspection. At least 4,072 accidents link to 2 or more inspections, and some link to 10 or more. The injury rows are identical copies, so **the data can't say which employer's worker was hurt.** The true key of `accident_injury` is `(summary_nr, rel_insp_nr, injury_line_nr)`.
- **Orphans.** 34,178 injury rows (14.7%) reference a `summary_nr` that isn't in the accident table. 5 accidents have no injury rows.
- **Schema drift between load batches.**
  - The 59,363 injury rows loaded in 2026 cover events from 2014 to 2025.
  - In those rows, `nature_of_inj` and `part_of_body` are empty on every row.
  - The construction-operation code lands in `const_op_cause` instead of `const_op`. It matched the older load's `const_op` in 394 of 394 accidents present in both.
- **Placeholders.** Older loads use `age = 0` for "unknown" (39,237 rows). Codes are stored as floats (`12.0`), including in the lookup table.
- **Small inconsistencies in the fatality flag.** 157 accidents have no fatality flag but a fatal injury row; 149 are flagged fatal with no fatal injury row.

**Inspection type codes.** The portal publishes no lookup table for inspection codes; `accident_lookup2` covers only the accident tables. Construction inspections linked to accidents are mostly types `M` (5,415), `C` (4,312) and `A` (3,155). `M` and `A` appear to be the fatality/catastrophe and accident types, and `C` (referral) likely captures employer-reported severe injuries. **These decodes are unconfirmed.**

## 3. Provisional and changing values

**Open cases**

| Year opened | Construction inspections | Still open | Citations from open cases |
|---|---|---|---|
| 2022 | 30,108 | 2,103 (7%) | 15.1% |
| 2023 | 33,255 | 3,745 (11%) | 22.6% |
| 2024 | 32,135 | 6,627 (21%) | 37.5% |
| 2025 | 29,041 | 8,382 (29%) | 48.9% |
| 2026 | 20,530 | 11,739 (57%) | 64.6% |

**Settlements reduce penalties (construction 2015+, deleted citations excluded)**

| Type | Citations | Initial ($M) | Current ($M) | Reduction |
|---|---|---|---|---|
| Serious (S) | 439,291 | 1,132.8 | 848.4 | 25.1% |
| Other-than-serious (O) | 173,530 | 161.4 | 102.5 | 36.5% |
| Repeat (R) | 36,543 | 354.0 | 282.1 | 20.3% |
| Willful (W) | 4,305 | 200.1 | 163.6 | 18.2% |
| Unclassified (U) | 178 | 1.5 | 1.0 | 28.8% |

**Other changes after issuance**

- **Deletions.** 453,550 citations (3.4%) carry `delete_flag = 'X'`; in construction 2015+ it's 4.66%.
- **Penalties also go up.** 18,368 citations have a current penalty higher than the initial one (some from $0). 130,649 were cut to $0.
- **"Missing" changed meaning over time.** Penalties were recorded as blank in older data and as $0 in newer data. In construction 2015+ blanks are about 0%.

| Issuance decade | Initial penalty blank | Initial penalty $0 |
|---|---|---|
| 1970s | 69.2% | 0.0% |
| 1980s | 74.7% | 0.1% |
| 1990s | 53.8% | 0.0% |
| 2000s | 46.2% | 0.2% |
| 2010s | 18.8% | 24.3% |
| 2020s | 0.0% | 35.5% |

## 4. Standard codes

**Federal codes are packed:** `19260501 B13` means 29 CFR 1926.501(b)(13), and some codes carry roman-numeral suffixes (`19260500 E01   IV`).

**State plans cite their own codes.** 22.9% of construction citations since 2015 use non-federal codes:

| Prefix | Citations | Jurisdiction |
|---|---|---|
| `296-155` | 27,408 | Washington construction (WAC) |
| `OAR 437` | 11,681 | Oregon |
| `408.401` | 10,838 | Michigan |
| `296-880` | 7,106 | Washington |
| `3395(I)` | 5,700 | California Title 8 |
| `1509(A)` | 5,098 | California Title 8 |

**Most-cited standards, construction 2015+ (deleted citations excluded)**

| Standard | Citations | Topic |
|---|---|---|
| 1926.501 | 101,908 | Fall protection: duty to have |
| 1926.451 | 44,671 | Scaffolds |
| 1926.1053 | 41,884 | Ladders |
| 1926.503 | 36,252 | Fall protection training |
| WA 296-155 | 26,628 | Washington construction |
| 1926.102 | 24,714 | Eye and face protection |
| 1910.1200 | 22,676 | Hazard communication |

## 5. Comparison fields

- **NAICS drifts within a company.** Of 6,880 companies (normalised name plus mailing zip) with 5 or more inspections, **3,058 (44.4%)** carry more than one NAICS code. `WOLVERINE BUILDING GROUP` appears as roofing (238160) and as four building codes.
- **SIC was replaced by NAICS during the 2000s.** Before 2000 only SIC is populated; by 2015–19, 182,363 construction inspections carry NAICS 23 and 21,836 carry SIC 15–17. The two codes disagree on 15,328 inspections. Filtering on NAICS alone drops older construction records.
- **Employee count (`nr_in_estab`) is unusable for normalisation.** For construction 2015+ the median is 5, p90 is 40, p99 is 500 and the max is 1,000,000. 185 inspections report 10,000 or more employees, apparently company-wide rather than on-site. 2.6% are blank or zero.
- **Inspection type mix (construction 2015+):** H 189,373 · C 51,685 · B 48,020 · I 31,190 · G 25,414 · A 9,897 · M 7,200 · F 6,318 · K 3,354 · N 2,161 · J 1,808 · D 875 · L 197 · E 4.
- **Citation-free inspections:** 37.6% of construction inspections since 2015 have no citations.

## 6. Minor integrity issues

| Issue | Count |
|---|---|
| Inspections closed before they opened | 464 |
| Citations issued before the inspection opened | 449 |
| Citations referencing a missing inspection | 374 |
| Inspections never closed (all years, all industries) | 79,476 |
| Names with encoding damage (`�`) | 131 |
| Standard codes with encoding damage | 16 |
| Undocumented violation type `P` | 11 |
| Null violation type | 16 |

## Multi-employer sites

**120,262 construction inspections (31.9%) share a site address, zip and open date with another employer's inspection.** The busiest single site-day has 27 employers. This is OSHA inspecting a GC and its subs together.

- **The downside:** a fatality on a shared site appears on several employers' records.
- **The upside:** you can see which subs were cited on the same jobs.

## Implications for the design

1. **Keep the raw data as delivered** and clean it in a separate layer. Field meanings changed between load batches and over time, so the original values must stay traceable.
2. **Model the company separately from the inspection.** Store a name-alias table and record the evidence for each match. Strip ID prefixes before matching, and have a human confirm matches, since normalisation alone resolves little and address-based merging over-reaches.
3. **Derive fatality and accident flags from the inspection type.** Use accident detail and narratives only where they exist, and say so when they don't.
4. **Treat open-case citations as provisional.** Exclude deleted citations, and show both the initial and current penalty.
5. **Parse standard codes and map them to hazard categories**, including the main state-plan codes.
6. **Compare subs to peers using each company's most frequent NAICS code.** Don't normalise by `nr_in_estab`.
7. **Caveat shared-site accidents** rather than attributing them to every employer on the site.
