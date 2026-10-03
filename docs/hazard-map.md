# Standard codes and the hazard map

How a raw `violation.standard` value becomes a readable citation and one hazard category, how much of the data that covers, and how the code decodes were checked.

All numbers are full scans of `data/profile.duckdb` (DOL bulk files of 2026-10-02). **Scope:** construction citations (NAICS 23 or SIC 15–17), deleted citations (`delete_flag = 'X'`) excluded: 4,254,391 citations in all years, 653,849 from inspections opened since 2015-01-01.

## Method

**1. Parse** (`ssi/pipeline/sql/02_standard_macros.sql`). The pipeline calls `std_parse_with_state(standard, site_state)`, which returns three fields.

| Family | Raw examples | `section_key` | `standard_cite` |
|---|---|---|---|
| `federal_1926` | `19260501 B13`, `19260500 E01   IV` | `1926.501` | `1926.501(b)(13)`, `1926.500(e)(1)(iv)` |
| `federal_1910` | `19101200 E01` | `1910.1200` | `1910.1200(e)(1)` |
| `federal_other` | `19040039 A01`, `19030019 A` | `1904.39` | `1904.39(a)(1)` (parts 1903, 1904, 1908, 1915–1918, 1928, 1960) |
| `general_duty` | `5A0001` | `5(a)(1)` | `5(a)(1)` (OSH Act only; a state's own general duty clause keeps its state family) |
| `state_WA` | `296-155-24609(7)(A)`; pre-2015 packed `1550065701 A` | `WAC 296-155-24609`, `WAC 296-155-657` | `WAC 296-155-24609(7)(a)`, `WAC 296-155-657(1)(a)` |
| `state_OR` | `OAR 437-003-1501(1)`; 1989–2014 packed `703150202` | `OAR 437-003-1501` | `OAR 437-003-1501(1)`, `OAR 437-003-1502(2)` |
| `state_MI` | `408.40132(5)`; packed `4084011401`; `408.1011(A)` | `R 408.40132`, `R 408.40114`, `MCL 408.1011` | `R 408.40132(5)`, `R 408.40114(1)`, `MCL 408.1011(a)` |
| `state_CA` | `3395(H)`, `1509 B`, packed `15410001 A01` | `T8 CCR 3395`, `T8 CCR 1541.1` | `T8 CCR 3395(h)`, `T8 CCR 1541.1(a)(1)` |
| `state_other` | `182.653(08)` (MN) | `MN 182.653` | `MN 182.653(08)` |
| `unknown` | blank, no digits, encoding damage (21 citations) | NULL | raw text |

- **Section key** is the section without its paragraph. Federal keys are `part.section`. State keys carry the code system's own prefix (`WAC`, `OAR`, `R`/`MCL`, `T8 CCR`), so keys never collide across families. Other states' keys are `<site_state> <code before the paragraph>`.
- **The site state matters.** Some state formats are just numbers: Cal/OSHA's `1509 B`, and the old packed codes of WA (`155…`), MI (`408…`) and OR (`70…`). For those the macro uses the citing inspection's `site_state`. The one-argument macros (`std_family(raw)`, `section_key(raw)`, `standard_cite(raw)`) pass a NULL state and fall back to the format's dominant state. Self-identifying formats (`296-…`, `OAR 437-…`, federal `19xx`) ignore the state.
- **Paragraph case** follows each code's convention by depth: CFR `(a)(1)(i)(A)`, WAC and MI `(1)(a)(i)(A)`, OAR `(1)(a)(A)(i)`, Title 8 `(a)(1)(A)(i)`. Federal tokens with spaces stripped (`F07IVC`) read as letter, number, roman, letter, number.

**2. Map** (`ssi/pipeline/ref/standard_hazard_map.csv`, applied by `ssi/pipeline/sql/31_hazard_map.sql`).
- Each rule is `family, match_type, pattern, range_to, hazard_code, note`.
- Matching is **exact**, then **range**, then **prefix**. Within a type the most specific rule wins: the innermost range, or the longest prefix.
- **Ranges compare a natural sort key**: every digit run is zero-padded, so `1926.95 < 1926.501 < 1926.1053`. The upper bound includes its own subsections (`T8 CCR 1541` covers `1541.1`). A test checks that overlapping ranges always nest.
- **Unmatched → `other`.** Every citation gets exactly one category, so totals always add up.
- **What each code system gets:**
  - Federal 1926: every subpart, by range.
  - Federal 1910: by subpart, with exact overrides (hazcom, respirators, forklifts, lockout).
  - Cal/OSHA: by Title 8 article and group.
  - Michigan: by part number (`R 408.4PPRR` is construction part PP; `R 408.1PPRR` is general industry).
  - Washington: by chapter and section-group prefix.
  - Oregon: rule by rule.
  - Other states: exact or prefix rules on the state-qualified keys cited most since 2015. These include 19 state general duty clauses plus state recordkeeping, abatement, training, crane, heat and fall rules.

**Loading.** Load the reference CSVs as text: `read_csv(path, header = true, all_varchar = true)`. Otherwise type detection turns `trade.code` into integers and can read map patterns such as `1926.1` as numbers. Install `02_standard_macros.sql` before running `31_hazard_map.sql`. Prefer `std_parse_with_state` over three separate macro calls; each macro re-runs the regexes.

**3. Categories** (`ssi/pipeline/ref/hazard_category.csv`). There are 20, including `other`. The data argued for three beyond the first 17:
- **`tools_machine_guarding`:** 15,120 citations since 2015. Sources: federal Subpart I, 1910 Subparts O and P, lockout, and the state tool parts.
- **`confined_space`:** 2,528 citations. Sources: Subpart AA, 1910.146, T8 5157 and 1950–1962, WAC 296-809.
- **`demolition`:** 1,355 citations. Sources: Subpart T, MI Part 20, T8 Art 31, WAC 296-155-775.

`fatal_four` is true where the category's main hazard is a Focus Four hazard: falls, electrocution, struck-by, or caught-in/between.

**Known approximations**
- **Mapping is per section, not per paragraph.** For example, all of 1926.501 is fall protection, including (c) falling objects. MN 182.653 is mapped to `safety_program_training` because 88% of its citations are subd. 8 (AWAIR); the remaining 12% are subd. 2, the general duty clause.
- **1910.21–.30 (walking-working surfaces) all map to `fall_protection`.** The subpart was renumbered in 2017, so a section number alone can't tell old ladder sections from new ones.
- **Repealed WA sections are inferred** from the chapter structure (for example the pre-2008 scaffold sections 296-155-48x). The notes column marks every inferred row.
- **Old packed codes:** Oregon's 1981–1993 divisions (`7831539`) and most other states' pre-2015 codes are left as `other`. Their meaning isn't documented anywhere I found.
- **Heat:** federal heat citations are filed under 5(a)(1). So `heat` only comes from state rules (T8 3395/3396, WAC 296-62-095, OAR 437-002-0156, MD COMAR 09.12.32), and federal heat cases sit in `general_duty`.

## Coverage

Mapped means the citation got a category other than `other`. Since 2015, **99.58%** of construction citations map to a real category, against a target of 99%. Across all years the figure is 95.95%.

| Family | Citations, all years | Mapped | Citations since 2015 | Mapped |
|---|---:|---:|---:|---:|
| federal_1926 | 3,088,839 | 99.7% | 426,662 | 99.9% |
| federal_1910 | 287,987 | 99.1% | 61,256 | 99.3% |
| federal_other | 94,613 | 98.3% | 12,478 | 99.2% |
| general_duty | 12,910 | 100.0% | 1,824 | 100.0% |
| state_WA | 209,599 | 98.7% | 48,808 | 99.6% |
| state_CA | 168,201 | 99.5% | 47,798 | 99.6% |
| state_MI | 192,924 | 98.1% | 33,081 | 98.8% |
| state_OR | 60,794 | 50.4% | 11,853 | 98.5% |
| state_other | 138,503 | 12.3% | 10,086 | 91.4% |
| unknown | 21 | 0.0% | 3 | 0.0% |
| **All** | **4,254,391** | **95.95%** | **653,849** | **99.58%** |

**Share in `other`: 0.42% since 2015 (2,727 citations) and 4.05% across all years (172,348).**
- **Most of the all-years gap is old state codes** that no source decodes.
  - Other states' pre-2015 formats: 120,661 citations.
  - Oregon's 1981–1993 packed divisions: 26,088.
- **Since 2015, 594 of the 2,727 are `other` by choice.** These are sections that a rule deliberately sends to `other`:
  - Materials storage and handling: MI Part 8, OR 437-002-0221, WAC 296-155-32x/335.
  - Bins and hoppers: T8 1548–1549.
  - Tree work, agriculture and marine terminals: T8 3420–3482.
- **The rest have no rule.** Mostly these are federal sections with no fitting category: storage and disposal (1926.250/.252, 1910.176), logging (1910.266) and diving (1910.410–.440).

Hazard mix since 2015:
- fall protection 27.4%
- safety program/training 11.7%
- scaffolds 11.6%
- ladders 9.7%
- PPE 7.9%
- health 5.4%
- electrical 4.5%
- hazcom 3.7%
- excavation 3.6%
- recordkeeping 3.3%
- every other category under 2.5% each

### Top 15 section keys left in `other` (construction, since 2015)

These include keys with no rule and keys a rule sends to `other` on purpose (MI Part 8, T8 1549, OAR 437-002-0221).

| # | Family | Section key | Since 2015 | All years | Why it is `other` |
|---:|---|---|---:|---:|---|
| 1 | state_other | `VA 16VAC25-60-130` | 255 | 259 | Adopts 29 CFR 1926 by reference (and manufacturer's specifications); the hazard isn't in the code |
| 2 | federal_1926 | `1926.252` | 242 | 3,150 | Disposal of waste materials (Subpart H) |
| 3 | federal_1910 | `1910.176` | 171 | 740 | Handling materials, general |
| 4 | federal_1910 | `1910.266` | 132 | 836 | Logging operations |
| 5 | federal_1926 | `1926.250` | 116 | 5,894 | General requirements for storage (Subpart H) |
| 6 | state_other | `NV NEVADA ADMINISTRATIVE CODE 618.50` | 68 | 68 | NAC 618.50x large-project rules; the raw code is cut off at 33 characters |
| 7 | state_MI | `R 408.40818` | 64 | 335 | CS Part 8 handling and storage of materials |
| 8 | state_MI | `R 408.40833` | 64 | 247 | CS Part 8 |
| 9 | state_MI | `R 408.40831` | 55 | 313 | CS Part 8 |
| 10 | state_MI | `R 408.40820` | 52 | 228 | CS Part 8 |
| 11 | state_MI | `R 408.40832` | 45 | 189 | CS Part 8 |
| 12 | state_CA | `T8 CCR 1549` | 45 | 88 | CSO Art 7 bins, bunkers, hoppers |
| 13 | state_OR | `OAR 437-002-0221` | 41 | 155 | Oregon rules for handling materials |
| 14 | state_other | `VA 16VAC25-60-120` | 39 | 39 | Adopts 29 CFR 1910 by reference |
| 15 | federal_1910 | `1910.421` | 36 | 146 | Commercial diving |

Seven of the fifteen are materials storage and handling. A `materials_handling` category would absorb about 1,000 citations since 2015, if the product ever needs one.

## Inspection type (`insp_type`) decode

**Verified against the official DOL metadata.** The source is the DOL Open Data Portal API record for the "OSHA Inspection" dataset: <https://apiprod.dol.gov/v4/datasets/10334> (table `OSHA_inspection`).
- Its `insp_type` definition lists all 14 codes: "A=Accident. B=Complaint. C=Referral. D=Monitoring. E=Variance. F=FollowUp. G=Unprog Rel. H=Planned. I=Prog Related. J=Unprog Other. K=Prog Other. L=Other-L. M=Fat/Cat. N=Unprog Emph".
- I fetched it on 2026-10-03. All 14 codes in `ref/inspection_type.csv` are marked `decode_confirmed = true` with that URL.
- OSHA's field definition page (<https://www.osha.gov/data/inspection-detail-definitions>) describes inspection type only in general terms ("the impetus for actually performing the inspection") and gives no code list.

**Corrections and notes**
- **I and J were the wrong way round** in an earlier working assumption. Officially, I = programmed related and J = unprogrammed other.
- **N** is "Unprog Emph". Expanding it to "unprogrammed emphasis" is my reading; no source spells it out.
- **M (fatality/catastrophe) first appears on 2011-04-20**, and N first appears on 2025-05-16. Before 2011, accident investigations are all type A.
- **Since 2015, federal offices record accident investigations only as M** (13,281 M, zero A). State-plan offices use both A (34,739) and M (12,533). So `is_accident` is true for both A and M.
- **The DOL dictionary is silent on when M was introduced.** An archived copy of OSHA's older IMIS manual described the single accident type as fatality/catastrophe for federal offices and as an accident for state offices. That copy was read through the Wayback Machine, because the live osha.gov PDF returned 403: <https://www.osha.gov/sites/default/files/enforcement/directives/ADM_1_03-06.pdf>. It has not been re-checked.
- **Referrals (C) are not accident inspections by definition, but they often carry accident records.** Among construction inspections since 2015, 8.3% of C have accident-injury rows, compared with 31.9% of A and 75.2% of M. That is consistent with severe-injury reports arriving as referrals.

**Violation type.** OSHA's definitions page lists "Willful, Repeat, Serious, Other, or Unclassified": <https://www.osha.gov/data/inspection-detail-definitions>. The DOL violation metadata (<https://apiprod.dol.gov/v4/datasets/10338>) only says "Violation Type".
- **Code `P` is undocumented.** It appears on 11 citations issued 2012–2015, with gravity 05–10 and initial penalties of $1,350 to $70,000 ($70,000 was the willful maximum in 2012).
- `ref/violation_type.csv` labels P as undocumented and does not count it as serious-or-worse.

## Does the 3rd digit of `reporting_id` = '5' mark a state-plan office?

**Verdict: supported by the data and by OSHA's own office list, but not documented as a rule.** Treat it as a strong inferred rule.

**Official definitions**
- The DOL metadata says only that `reporting_id` "Identifies the OSHA federal or state reporting jurisdiction": <https://apiprod.dol.gov/v4/datasets/10334>.
- The same source says `state_flag` "is not populated". This data confirms that: it is blank on all 5,202,096 inspections. So `state_flag` can't tell federal from state.
- OSHA's help page says the RID "Identifies the OSHA office or organizational unit responsible for the inspection": <https://www.osha.gov/help/establishment-search>. It doesn't describe the digit structure.

**OSHA's office list**
- OSHA's Establishment Search office drop-down pairs every office name with its RID. The live page is behind a CAPTCHA, so it was parsed from a Wayback Machine copy of 2026-10-01: <https://www.osha.gov/ords/imis/establishment.html>. That parse was done once during research and has not been re-run.
- Padded to 7 digits, all 188 offices with '5' as the 3rd digit are state-plan agencies, and they cover all 29 plans. Examples: Cal/OSHA district offices 0950xxx, Washington DOSH 1055xxx, Oregon OSHA 1054xxx, MIOSHA 0552xxx.
- No federal area, regional or national office has a '5' there. Federal area offices use 1, 2 or 3, two area offices use 7, regional offices use 0, and national units use 8.
- **Pad first:** 6,953 inspections store a 6-digit RID that has lost its leading zero, so pad to 7 digits before reading the 3rd character.

**What the data shows (construction inspections, all years)**

| Site state's plan | 3rd digit = 5 | Inspections | Citing state-specific codes |
|---|---|---:|---:|
| Federal-only state | no | 826,223 | 32 |
| Federal-only state | yes | 51 | 0 |
| Private + public state plan | no | 46,921 | 9 |
| Private + public state plan | yes | 1,068,783 | 298,665 |
| Public-sector-only state plan | no | 384,639 | 27 |
| Public-sector-only state plan | yes | 20,165 | 2,441 |

- **State codes almost always come from '5' offices.** Of the 301,174 inspections citing any state-specific code, 301,106 (99.98%) have '5' as the 3rd digit.
- **In the 22 private-plus-public states, 92–100% of construction inspections since 2015 come from '5' offices** (lowest SC 92.3%, highest MI and VT 100%). The rest are federal jurisdiction within those states.
- **In the 7 public-only states, '5' inspections are public-sector work and the others are private.**
  - '5' inspections are mostly public employers: owner type B or C (local or state government) on 18,664 of 20,165.
  - Inspections without a '5' are almost all private (owner type A) or have no owner type recorded.
  - In Maine and Massachusetts, the first '5' inspection comes after the plan's approval: Maine 2015-10 (approved 2015), Massachusetts 2022-10 (approved 2022-08-18).
- **Don't use the citation format to tell federal from state.** Many state-plan inspections cite federal-format codes, because NC, MD, VA and others adopt the federal standards. Use the reporting office instead.
- **The State Plan list is from** <https://www.osha.gov/stateplans>: 22 private-and-public plans and 7 public-only plans, including Massachusetts. It is stored in `ref/state_plan.csv`.

## Sources for the state code structures

| Code system | Source |
|---|---|
| Washington | WAC 296-155 table of contents <https://app.leg.wa.gov/wac/default.aspx?cite=296-155>; also chapters 296-800, 296-62 and 296-24 at the same site |
| Oregon | OAR 437 divisions 1, 2, 3, 4 and 7 <https://oregon.public.law/rules/oar_chapter_437_division_3> (and `_division_1`, `_2`, `_4`, `_7`); heat rule 437-002-0156 <https://www.law.cornell.edu/regulations/oregon/Or-Admin-Code-SS-437-002-0156> |
| Michigan | Part lists for construction, general industry and occupational health <https://www.law.cornell.edu/regulations/michigan/department-labor-and-economic-opportunity/miosha/general-industry-and-construction-safety-and-occupational-health-standards>; individual rules such as R 408.40114, R 408.40132, R 408.22349 and R 408.41523 at the same site |
| California | Title 8 Construction Safety Orders articles <https://www.dir.ca.gov/title8/sub4.html>; General Industry Safety Orders groups <https://www.dir.ca.gov/title8/sub7.html> |
| Other states (`state_other` rules) | Each row's note names the provision. Sources by state: Hawaii HAR 12-110 <https://labor.hawaii.gov/hiosh/files/2018/12/12-110.pdf>; Tennessee rules 0800-01-03/-04/-09 <https://publications.tnsosfiles.com/rules/0800/0800-01/>; Maryland L&E 5-503 <https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gle&section=5-503> and COMAR 09.12.26 <https://regs.maryland.gov/us/md/exec/comar/09.12.26.08>; Minnesota rules <https://www.revisor.mn.gov/rules/5207/>; Nevada NRS 618 <https://nevada.public.law/statutes/nrs_618.987>; Virginia <https://law.lis.virginia.gov/admincode/title16/agency25/>; Utah R614-1-5 <https://www.law.cornell.edu/regulations/utah/Utah-Admin-Code-R614-1-5>; New York 12 NYCRR 801 <https://www.law.cornell.edu/regulations/new-york/title-12/chapter-XI/subchapter-A/part-801>; state general duty clauses (AZ, CT, IA, IL, IN, KY, MD, ME, MN, NC, NJ, NV, NY, PR, SC, TN, UT, VA, WY) at each state's statute site. These were decoded during research and the rows were not re-checked one by one. |

**Caveats on the other-state rows**
- **Utah's R614-1-5 letters were renumbered around 2020.** B is reporting from 2020 on, and C/D carry their pre-2020 meanings. The rows follow the dates actually observed for each key.
- **Nevada values are cut off at 33 characters** (`NAC 618.54` may be 618.540, 618.542 or 618.544). Those rows are marked inferred.
- **Maryland COMAR 09.12.32** is the 2024 heat standard. Before 1994 it was lead in construction; every cited row in this data is from 2025 or later.
- **Some keys mix subjects.** For `MN 182.653` and `PR 6`, the key covers subdivisions with different subjects. Each is mapped to its majority subject, and the share is given in the note.
