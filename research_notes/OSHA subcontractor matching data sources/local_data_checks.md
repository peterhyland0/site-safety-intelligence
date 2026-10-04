# Local data checks: hidden identifiers in the project's OSHA data, and bias in the matching eval's silver labels

Scope and method (applies to every section). All numbers were computed on 2026-10-04 with DuckDB via `uv run python`, strictly read-only on the repo:
- **Raw inspections:** the 105 CSV chunks in [data/raw/inspection/][raw-insp]. These are the contents of [OSHA_inspection.zip][raw-zip], which is stored essentially uncompressed (1,445,543,317 bytes; the header is identical in the zip and the extracted files). They were loaded `all_varchar` with the same `read_csv` options as [10_raw.sql][sql10] into a temporary DuckDB in the session scratchpad (deleted afterwards).
- **Warehouse:** [warehouse-20261003T212330Z.duckdb][wh] (the file named in `data/build/CURRENT`), always attached `READ_ONLY`. Its window is open_date 2016-09-23 to 2026-09-23.
- **Cleaning:** names and keys were rebuilt with the project's own macros ([macros.sql][macros]). The `establishment_key` recomputed from raw equals the warehouse key on all 338,239 warehouse inspections.
- **"Construction"** means NAICS 23\* or SIC 15–17, the pipeline's rule from [20_scope.sql][sql20].
- **Changed file:** `ssi/pipeline/sql/20_scope.sql` changed on disk during this session. All numbers describe the built warehouse file above, not the current code.
- **Labels:** "Verified" means measured directly; anything under *Inferences* is interpretation.
- **EINs** are masked (first two and last three digits).

## 1. HOST_EST_KEY: does it exist, how full is it, and can it identify companies?

### Takeaway
`HOST_EST_KEY` does exist in the raw file, but it carries real values only for inspections opened before 2016-07-28. Since then it holds the literal placeholder `HOST_EST_KEY_VALUE`.

- **Warehouse coverage:** 0 of 338,239 warehouse inspections (0%) have a usable key.
- **Historical value:** where real values exist (1984 to mid-2016), the key is an IMIS establishment-record ID local to one state's host, and it is **finer** than the project's own `establishment_key`. 98.7% of construction inspection pairs sharing a key already share an `establishment_key`, while the key captures only 3.0% of same-`establishment_key` pairs.
- **Bottom line:** it is useless as an identifier or candidate generator for the app's data, and only marginally useful even if pre-2016 history were added.

### Cited Findings
**Existence and format**
- The raw header has 36 columns, and `HOST_EST_KEY` is column 30 (between `MAIL_ZIP` and `NR_IN_ESTAB`). The header is identical when streamed from the zip (`unzip -p … | head -1`) and in the extracted chunks. — [raw inspection CSVs][raw-insp]; [zip][raw-zip]
- The raw file has 5,202,096 rows, with 5,202,096 distinct `ACTIVITY_NR`. `HOST_EST_KEY` is non-blank on 3,050,183 rows (58.63%), with 1,546,481 distinct values. — [raw inspection CSVs][raw-insp] (query 1a)
- The non-blank values fall into four classes (query 1b):
  - `N###····#########`: the letter N, a 3-digit code, 4 spaces and 9 digits (17 chars). 2,016,552 rows, opened 1973-04-16 to 2016-07-28. This is the only "real" form. The letter is always `N`; there are 164 distinct codes and 1,546,478 distinct keys. Example: `N009    000010639`.
  - The literal string `HOST_EST_KEY_VALUE`: 1,005,292 rows, opened 2010-01-27 to 2026-09-23.
  - `000000000`: 28,338 rows, opened 1984-04-11 to 2010-10-19. This is a null sentinel: a single value shared by 17,604 different cleaned names across 54 site states.
  - One stray 4-character value (1978).
  - Blank: 2,151,913 rows, almost all opened before 1999.

  — [raw inspection CSVs][raw-insp]
**Fill rates**

| Slice | Rows | Real N-format key | % |
|---|---|---|---|
| All rows | 5,202,096 | 2,016,552 | 38.76% |
| Construction, all years | 2,346,040 | 939,270 | 40.04% |
| Construction, opened 1999–2010 | 630,656 | 630,453 | 99.97% |
| Construction, opened 2011–2015 | 217,013 | 110,722 | 51.0% |
| All rows, opened 2016+ | 781,242 | 27 (26 distinct) | 0.0035% |
| Construction, opened 2016+ | 339,852 | 6 (all opened 2016-02-25 to 2016-06-22) | 0.0018% |
| All rows, opened ≥ 2016-09-23 (warehouse window) | 719,443 | 0 | 0% |
| Rows in warehouse `osha.inspection` | 338,239 | 0 (all are `HOST_EST_KEY_VALUE`) | 0% |

— [raw inspection CSVs][raw-insp]; [warehouse][wh] (query 1a)

**Changeover to the placeholder, by year opened**

| Year | Placeholder rows | Real-key rows |
|---|---|---|
| 2011 | 7,808 | 95,937 |
| 2012 | 39,815 | 62,240 |
| 2013 | 43,350 | 54,721 |
| 2014 | 52,899 | 39,445 |
| 2015 | 80,200 | 6,227 |
| 2016 | 81,769 | 27 |
| 2017–2026 | every row | 0 |

- For 2011–2015, federal offices had real keys on only 48,589 of 222,053 rows (21.9%), while state-plan offices had them on 209,981 of 260,589 (80.6%). — [raw inspection CSVs][raw-insp] (query 1c)
- Before 1999 the key is sparse. The share of rows with any value is 1.5% in 1984, 25.8% in 1988, 37.1% in 1995 and 70.1% in 1998; it is 100% from 1999. — [raw inspection CSVs][raw-insp]

**Structure of the code**
- Each `N###` code maps to effectively one state. 84 of the 164 codes have exactly one site state, and each of the 25 largest codes has at least 99.95% of its rows in one state.
- A code spans 1 to 30 reporting offices (mean 2.77). Examples:

| Code | State | Rows | Reporting offices |
|---|---|---|---|
| N096 | WA | 119,422 | 9 |
| N180 | MI | 84,907 | 2 |
| N125 | TN | 66,032 | 30 |
| N017 | VA | 60,506 | 24 |
| N073 | MN | 48,438 | 2 |

  — [raw inspection CSVs][raw-insp] (query 1d)

**What one key groups together**

The table covers all industries. 1,308,602 keys (84.6%) hold a single inspection, which is 64.9% of real-key rows; 237,876 keys hold two or more inspections. The construction column covers the 844,608 keys that touch a construction inspection, of which 68,217 hold two or more inspections. The rest of the table counts only keys with two or more inspections.

| Among keys with ≥2 inspections | All industries | Construction-touching |
|---|---|---|
| More than one raw name | 3,558 | 549 |
| More than one cleaned name | 1,823 (0.77%) | 333 (0.49%) |
| More than one name core | 1,622 | 275 |
| More than one `establishment_key` | 9,820 (4.1%) | 1,501 (2.2%) |
| More than one mailing address key | 1,376 | 744 |
| More than one mailing zip | 972 | 557 |
| More than one mailing state | 136 | 66 |
| More than one site state | 8 | 7 |
| More than one site city | 2,420 | 1,988 (2.9%) |
| More than one reporting office | 18,300 | 2,475 |

- Only 162,879 of the 939,270 real-key construction inspections (17.3%) sit in a key that has another inspection. — [raw inspection CSVs][raw-insp] (query 1e)

**Agreement with the project's `establishment_key`** (same macros, same rows, real keys only)

| Rows | Pairs sharing a key | Pairs sharing an `establishment_key` | Pairs sharing both | P(same estab. key ∣ same key) | P(same key ∣ same estab. key) |
|---|---|---|---|---|---|
| Construction | 229,888 | 7,667,489 | 226,840 | 0.987 | 0.030 |
| All industries | 1,464,235 | 19,702,116 | 1,431,133 | 0.977 | 0.073 |

- Project establishments with two or more real-key construction inspections (134,529 of them, 535,981 inspections) carry 442,537 distinct keys, or 0.826 keys per inspection. Only 21.2% of them have a single key. — [raw inspection CSVs][raw-insp] (query 1f)

**When a construction key spans several `establishment_key`s** (1,244 establishment pairs), what differs:

| Difference | Establishment pairs | Keys |
|---|---|---|
| Same name, different address | 576 | 571 |
| Same name, other or missing mailing state | 315 | 307 |
| Different name | 207 | 190 |
| Same name and address, zip differs | 54 | 54 |
| Same name core, different descriptor | 49 | 48 |
| One address unparsed | 43 | 43 |

— [raw inspection CSVs][raw-insp] (query 1g)

**Name pairs inside construction keys with more than one cleaned name** (340 pairs, 333 keys)

| Relationship | Pairs |
|---|---|
| Same core (legal or descriptor word differs) | 58 |
| One name a prefix of the other | 32 |
| Share a core token | 115 |
| Spelling variant (Jaro-Winkler ≥ 0.85) | 18 |
| **No overlap at all** (in 112 keys) | **117** |

- Genuine variants on one key include BJ K / BJK CONSTRUCTION, COAST LAND / COASTLAND CONSTRUCTION, WHITE RIVER / WHITERIVER CONSTRUCTION, RGB / RJB DRYWALL, ZBI / ZVI CONSTRUCTION, EXCEL / XCEL ENERGY, and a person's name "DBA CG CONSTRUCTION" / CG CONSTRUCTION.
- Unrelated names on one key include CUSTOM DRYWALL / RJ MECHANICAL, 84 LUMBER COMPANY STORE 2381 / QUALITY STUCCO, TRUE BLUE POOLS / YUMA REGIONAL MEDICAL CENTER, 161 WEST 16TH ST OWNERS / MTA RESTORATION, and CARRABBAS ITALIAN GRILL / CORE CONSTRUCTION. Of the 112 unrelated-name keys, 48 include a non-construction inspection, 46 have a single site address and 12 have all inspections on one day.
- Some large keys are non-company records: `N040 000110426` "LOCATING JOB SITE 8" has 103 construction inspections (2004–07), and several keys belong to OSHA's own offices, e.g. "USDOL OSHA MILWAUKEE" with 180 rows.

— [raw inspection CSVs][raw-insp] (query 1h)

**Family spot-checks** (real-key rows only)

| Family | Rows (all years) | Rows with real key | Distinct keys | Inspections per key | Distinct `establishment_key` (same rows) | Cleaned names | Mailing states | Distinct N-codes |
|---|---|---|---|---|---|---|---|---|
| Brasfield & Gorrie | 644 | 326 | 255 | 1.28 | 79 | 4 | 7 | 26 |
| D.R. Horton | 815 | 313 | 287 | 1.09 | 158 | 39 | 20 | 51 |
| Hensel Phelps | 517 | 213 | 173 | 1.23 | 81 | 11 | 14 | 44 |
| Barnhart Crane | 112 | 20 | 17 | 1.18 | 10 | 1 | 5 | 13 |

- No key of these four families contains another company's name.
- No key bridges two of a family's own cleaned names. For example, BRASFIELD GORRIE and BRASFIELD GORRIE GENERAL CONTRACTOR sit on separate keys.
- The largest family keys are site-spanning but single-name. Brasfield `N119 000010026` covers 15 inspections from 1989 to 2003, at site cities Birmingham, Decatur and Trussville, with a Birmingham mailing address.
- Family filters used: `clean_name LIKE 'BRASFIELD%GORRIE%'`, `regexp '^(DR|D R) ?HORTON'`, `LIKE 'HENSEL PHELPS%'`, `LIKE 'BARNHART CRANE%' OR 'BARNHART %RIGGING%'`.

— [raw inspection CSVs][raw-insp] (query 1i)

**Bridging to warehouse establishments and agreement with ITA EINs**
- 25,111 of 215,856 non-placeholder warehouse establishments (11.6%) also appear, under the same `establishment_key`, on pre-2016 rows that carry real keys.
- Only **23** keys bridge two *different* warehouse establishments.
- Using the eval's own definition (one EIN per establishment via an ITA M1 link), just 4 of those bridged pairs have an EIN on both sides:
  - 3 share an EIN: CARVER ELECTRIC COMPANY INC ×2; BRASFIELD & GORRIE GP LLC / BRASFIELD & GORRIE LLC; SOUTH STATE INC ×2.
  - 1 does not: OBERSTAR INC (Marquette) / BRENNER EXCAVATING INC (Hopkins), on key `N180 000073718`.

  — [warehouse][wh]; [eval EIN definition][eval] (query 1j)

#### Queries (abbreviated)
```sql
-- 1a load (same options as 10_raw.sql) and derive
CREATE TABLE raw_inspection AS SELECT * FROM read_csv('data/raw/inspection/*.csv', all_varchar=true, header=true,
  quote='"', escape='"', union_by_name=true);
CREATE TABLE hk AS SELECT try_cast(activity_nr AS BIGINT) activity_nr, try_cast(left(open_date,10) AS DATE) open_date,
  coalesce(naics_code LIKE '23%',false) OR coalesce(left(lpad(trim(sic_code),4,'0'),2) IN ('15','16','17'),false) is_constr,
  host_est_key AS hek_raw,
  CASE WHEN regexp_full_match(host_est_key,'N[0-9]{3} {4}[0-9]{9}') THEN host_est_key END AS hek_real,
  clean_name(estab_name) clean_name, name_core(clean_name(estab_name)) core, addr_key(mail_street) addr_key,
  establishment_key(clean_name(estab_name), addr_key(mail_street), zip5(mail_zip), nullif(upper(trim(mail_state)),'')) ekey, ...
FROM raw_inspection;
-- 1b value classes
SELECT regexp_replace(regexp_replace(hek_raw,'[0-9]','9','g'),'[A-Z]','A','g') pattern, count(*), min(open_date), max(open_date)
FROM hk WHERE coalesce(hek_raw,'')<>'' GROUP BY 1;
-- 1e per-key profile
CREATE TABLE hkey AS SELECT hek_real k, count(*) n, count(*) FILTER (WHERE is_constr) n_constr,
  count(DISTINCT clean_name) d_clean, count(DISTINCT core) d_core, count(DISTINCT ekey) d_ekey,
  count(DISTINCT addr_key) d_addr, count(DISTINCT mail_state) d_mstate, count(DISTINCT site_state) d_sstate, ...
FROM hk WHERE hek_real IS NOT NULL GROUP BY 1;
-- 1f pair agreement: sum(c*(c-1)/2) over GROUP BY hek_real, GROUP BY ekey, GROUP BY hek_real, ekey
-- 1j bridge to warehouse + EIN (one_ein exactly as in eval/matching/run.py)
WITH m AS (SELECT DISTINCT hek_real, ekey FROM hk WHERE hek_real IS NOT NULL
           AND ekey IN (SELECT establishment_key FROM wh.entity.establishment WHERE NOT is_placeholder))
SELECT ... FROM m a JOIN m b ON a.hek_real=b.hek_real AND a.ekey<b.ekey JOIN one_ein ea ... JOIN one_ein eb ...;
```

### Inferences
- **What the key is.** The `N###` prefix looks like a code for an IMIS host system (database node) and the 9-digit tail like a sequential establishment-record number within that host. So the key is a host-local establishment record, which fits the column name. The evidence: each code maps to one state, codes span several offices, and the tail is zero-padded and sequential.
- **Why it stopped.** The placeholder phases in over 2010–2016, federal offices before state plans. That timing matches OSHA's move from IMIS to OIS. This is an inference from timing only; I did not verify it against a source.
- **Why it adds so little.** OSHA created a new establishment record for most construction inspections (0.83 keys per inspection within one establishment). So the key cannot connect a firm's inspections over time. The project's name, address, zip and state key already merges about 33 times more construction pairs (7.67M vs 0.23M).
- **Value for the app.** For current data it is nil: 0% coverage in the window, and no key in OIS-era data.
  - If the history window were extended before 2016, the key would mostly restate `establishment_key`.
  - Its roughly 1.3% of cross-establishment links are a mix of genuine variants and co-located unrelated employers. About a third of cross-name construction pairs share no tokens, plus the `000000000` sentinel.
  - Every such link would need adjudication.
  - At best it is a small pool of hard examples (spelling variants, DBAs) for evaluating name-variant matching on historical data.
- **Why unrelated companies share a key.** Inspectors sometimes appear to reuse the site owner's or host's establishment record for a contractor working there, e.g. pool contractor and hospital, restoration contractor and building owners. The evidence is partial: 48 of 112 unrelated-name keys include a non-construction inspection.

### Gaps
- One web search found no public documentation of `host_est_key` semantics, so the host and record interpretation is unconfirmed.
- I could not test whether OIS keeps an internal establishment key that is simply not published. The public file shows only the placeholder.
- The key's agreement with ITA EINs can be measured on only 4 pairs. Real keys end in 2016 and EINs start in 2019, so the two overlap only through establishments inspected in both eras.

## 2. Other raw inspection columns the warehouse drops, and other identity fields in the local OSHA files

### Takeaway
The warehouse drops 12 of the 36 raw inspection columns. In the warehouse window every one of them is empty, constant, a placeholder, or non-identifying. The raw inspection file has **no** phone, EIN, DUNS, website, contact or related-activity column.

The only cross-inspection link in the local OSHA files is the violation file's `FTA_INSP_NR` (failure to abate). It links follow-up inspections up to 2015, but in OIS-era data it holds internal IDs that do not resolve to published activity numbers, so it adds nothing for 2016+.

### Cited Findings
- **The 36 raw columns:** ACTIVITY_NR, REPORTING_ID, STATE_FLAG, ESTAB_NAME, SITE_ADDRESS, SITE_CITY, SITE_STATE, SITE_ZIP, OWNER_TYPE, OWNER_CODE, ADV_NOTICE, SAFETY_HLTH, SIC_CODE, NAICS_CODE, INSP_TYPE, INSP_SCOPE, WHY_NO_INSP, UNION_STATUS, SAFETY_MANUF, SAFETY_CONST, SAFETY_MARIT, HEALTH_MANUF, HEALTH_CONST, HEALTH_MARIT, MIGRANT, MAIL_STREET, MAIL_CITY, MAIL_STATE, MAIL_ZIP, HOST_EST_KEY, NR_IN_ESTAB, OPEN_DATE, CASE_MOD_DATE, CLOSE_CONF_DATE, CLOSE_CASE_DATE, LOAD_DT. — [raw inspection CSVs][raw-insp]
- **The 24 kept in `osha.inspection`**, some renamed or typed: ACTIVITY_NR, REPORTING_ID, ESTAB_NAME (as `estab_name_raw`), SITE_ADDRESS, SITE_CITY, SITE_STATE, SITE_ZIP, OWNER_TYPE, SAFETY_HLTH, SIC_CODE, NAICS_CODE, INSP_TYPE, INSP_SCOPE, WHY_NO_INSP, UNION_STATUS, MAIL_STREET, MAIL_CITY, MAIL_STATE, MAIL_ZIP, NR_IN_ESTAB, OPEN_DATE, CASE_MOD_DATE, CLOSE_CONF_DATE, CLOSE_CASE_DATE. — [21_inspection.sql][sql21]; [warehouse][wh]
- **The 12 dropped, and how full they are on the 338,239 warehouse rows:**

| Dropped column | Filled rows | Values |
|---|---|---|
| STATE_FLAG | 0 | — |
| OWNER_CODE | 276 | government owner codes, e.g. 3100 ×85, 3017 ×48, 1102 ×26 |
| ADV_NOTICE | 338,239 | N 337,022, Y 1,217 |
| SAFETY_MANUF, SAFETY_CONST, SAFETY_MARIT, HEALTH_MANUF, HEALTH_CONST, HEALTH_MARIT | 0 each | — |
| MIGRANT | 38 | `X` |
| HOST_EST_KEY | 338,239 | all `HOST_EST_KEY_VALUE` |
| LOAD_DT | 338,239 | load timestamp; 2026-10-02 for 337,375 rows |

  — [raw inspection CSVs][raw-insp] joined to [warehouse][wh] (query 2a)
- **Other local OSHA files and their identity-related columns:**
  - Violation (29 columns): `FTA_INSP_NR`, `FTA_ISSUANCE_DATE`, `FTA_PENALTY`, `FTA_CONTEST_DATE`, `FTA_FINAL_ORDER_DATE`, plus HAZSUB1-5, REC, EMPHASIS, HAZCAT. The warehouse keeps only a boolean `is_fta` (237 violations in 96 warehouse inspections). — [raw violation CSVs][raw-viol]; [22_stg_violation.sql][sql22]; [warehouse][wh]
  - accident_injury: `REL_INSP_NR`, already used to link accidents to inspections.
  - accident, accident_abstract and accident_lookup2: no employer identifiers. — [raw files][raw-dir]
- **FTA links, all years:**
  - 22,235 distinct (activity, FTA number) rows, giving 22,129 links to a different inspection.
  - The target exists for 20,934 of them: 17,486 share the source's `establishment_key`, 1,245 share the name at a different address, and 2,203 differ in name.
  - **0 links have both ends in the warehouse window.**
  - Links by year the citing inspection opened: before 2000, 17,411; 2000–2010, 3,093; 2011–2015, 880; 2016+, 851.
  - Of the 851 links from 2016+, 775 point at numbers that are not in the inspection file. Their format is like `1689282.0`.
  - The other 76 coincide with unrelated 1982–1987 activity numbers (0 same names), i.e. accidental collisions.

  — [raw violation CSVs][raw-viol] (query 2b)
- **OIS internal IDs.** The WA L&I citation document for inspection 317962473 (opened 2021-01-21) prints "OSHA #: 1511296". That is the same 7-digit scale as the OIS-era `FTA_INSP_NR` values. — [L&I citation document][lni-doc]
- **Reference-side columns the warehouse drops** (not OSHA inspection data):
  - The WA L&I licence file carries `PhoneNumber`, `PrimaryPrincipalName` and `BusinessTypeCode`. `ref_ext.licence` keeps UBI (as `entity_id`), names, address and status but drops those three, and the separate `wa_lni_principal_*.csv` file is not loaded.
  - The ITA raw files carry `establishment_type`, `size` and `change_reason`, which the warehouse does not keep.

  — [61_licence.sql][sql61]; [60_ita.sql][sql60]; [raw ITA][raw-ita]
- **DOL tables not in the local raw set.** DOL's OSHA enforcement catalogue also publishes `related_activity`, `optional_info`, `strategic_codes`, `violation_event` and `violation_gen_duty_std`. None of these is in `data/raw/`. — [DOL developer portal (search snippet)][dol-dev]; [raw dir listing][raw-dir]

#### Queries (abbreviated)
```sql
-- 2a fill of dropped columns in the window
WITH w AS (SELECT h.* FROM hk h JOIN wh.osha.inspection USING (activity_nr))
SELECT count(nullif(trim(state_flag),'')), ... , list of top values per column FROM w;
-- 2b FTA links
CREATE TABLE fta AS SELECT DISTINCT try_cast(activity_nr AS BIGINT) activity_nr, try_cast(trim(fta_insp_nr) AS BIGINT) fta_insp_nr
FROM read_csv('data/raw/violation/*.csv', all_varchar=true, header=true, quote='"', escape='"', union_by_name=true)
WHERE coalesce(trim(fta_insp_nr),'')<>'';
-- then join both ends to hk (raw) and wh.osha.inspection; compare ekey / clean_name / open_date
```

### Inferences
- Beyond name, the two addresses, NAICS/SIC and headcount, the inspection file has no company identity, and the warehouse already keeps all the useful columns. Dropping the 12 columns costs nothing for matching.
- OIS-era `FTA_INSP_NR` appears to hold OIS internal inspection IDs (the "OSHA #"), which the public inspection file does not publish. So follow-up-to-original links cannot be rebuilt for 2016+ from the local data.
- DOL's `related_activity` table (not downloaded) is the one public OSHA table that might carry inspection-to-inspection or inspection-to-complaint links in the OIS era. It is the only untested lead inside OSHA's own data.

### Gaps
- The contents and fill of `related_activity` and `optional_info` are untested: they are not local, and downloads were out of scope.

## 3. WA L&I inspection numbers in employer names: counts, warehouse retention, and whether the public site maps them to a UBI

### Takeaway
**Counts and storage**
- **Counts confirmed:** 57,508 raw rows carry a `WA#########` prefix (WA plus 9 digits), and 21,471 of them are construction inspections opened 2016 or later.
- **One number per inspection.** The number is unique per inspection (57,506 distinct values), so on its own it never groups an employer's inspections.
- **Warehouse storage:** it survives only inside `estab_name_raw` (21,690 warehouse rows), and inside the display names and name variants of about 11,000 establishments. There is no dedicated column.

**What the public L&I site returns** (my five lookups)
- The inspection number **alone does not retrieve a UBI**.
- L&I's `CitationDocument.aspx` returns the citation PDF only for the **correct (UBI, inspection number) pair**. That PDF shows Legal Name, DBA, UBI, mailing and site addresses and the inspection number.
- The per-UBI contractor page has a Workplace Safety & Health inspection grid that is filled in by JavaScript; I did not retrieve its data.
- Three search-engine-indexed citation URLs pair WA inspection numbers with UBIs, and all three UBIs match the project's own WA licence records.

### Cited Findings
**Counts in the raw file**

| Slice | Rows | Distinct numbers |
|---|---|---|
| All rows with prefix `^WA[0-9]{3,}` | 57,508 | 57,506 |
| Construction, all years | 23,414 | 23,414 |
| Opened 2016+ | 53,258 | 53,256 |
| Construction, opened 2016+ | 21,471 | 21,471 |
| In warehouse `osha.inspection` | 21,690 | 21,690 |
| In warehouse, scope `naics23`/`sic15_17` | 20,066 | 20,066 |

- Every match has exactly the form `WA` followed by 9 digits (11 characters).
- The only repeated numbers are 2, each used on two inspections of the same employer on the same day (both health inspections).

— [raw inspection CSVs][raw-insp]; [warehouse][wh] (query 3a)

**When the prefix appears.** It first appears in 2013 (1 row) and 2014 (10 rows). From 2015 it is on almost every WA-site inspection: 93.5% in 2015, 96.4–98.3% in 2016–2024, and 98.7% in 2025 and 2026. — [raw inspection CSVs][raw-insp] (query 3b)

**What the number is**
- Values run from 317934694 to 317993016 and rise with open date (correlation 0.9987). The number never equals the OSHA `ACTIVITY_NR` (0 of 57,508).
- All come from 7 WA state-plan reporting offices (IDs starting 1055).
- An employer gets a new number for every inspection. For example, MAYFIELDS HOISTING SERVICE has 81 inspections and 81 numbers, and BARNHART CRANE RIGGING has 69 and 69.

— [raw inspection CSVs][raw-insp] (query 3c)

**Warehouse retention**
- All 21,690 WA-numbered rows keep the full raw name in `osha.inspection.estab_name_raw`, are flagged `id_prefix_stripped`, and have the number removed from `clean_name` (rule n2 in [macros.sql][macros]).
- In `entity.establishment`, 10,302 `display_name`s and the `name_variants` of 11,123 establishments still contain a `WA#########` prefix.
- No column holds the bare number. — [warehouse][wh] (query 3d)
**Existing licence linkage**
- The WA-numbered warehouse inspections belong to 11,124 establishments. 6,075 of those (54.6%) already link to a WA L&I licence by any method, and 5,353 (48.1%) by M1/M2.
- 5,049 establishments (45.4%) have no WA licence link. They account for 8,995 inspections, 5,513 of them with citations. — [warehouse][wh] (query 3e)

**Other state-plan numbers stripped from names** (warehouse, 2016-09-23 onward)

| Prefix form | State | Rows | Example form |
|---|---|---|---|
| Digits and dash (38,401 rows in total) | NC | 13,152 | |
| | OR | 11,030 | 9-digit, e.g. `317730040 - …` |
| | MN | 6,316 | |
| | KY | 2,872 | |
| | IN | 2,867 | |
| | SC | 2,134 | |
| Letters-and-digits case numbers (1,184 rows in total) | AZ | 1,109 | |
| | IA | 75 | |

— [warehouse][wh] (query 3f)

**L&I lookups.** I made five lookups on L&I's site, all GETs, with no login and no form submission.

1. **Correct pair returns the document.** [CitationDocument.aspx with UBI=603106218 and InspectionNo=317962473][lni-doc] returns a PDF citation document. It shows:
   - Legal Name and DBA Name (ALLWAYS ROOFING INC)
   - UBI 603106218
   - mailing address and inspection site address
   - Inspection Number 317962473 and "OSHA #" 1511296
   - opening and closing conference dates, issue date, inspector ID, region and reference
   - violations and penalty totals

   The body shows no contractor licence number.
2. **Inspection number alone fails.** The [same endpoint with only InspectionNo][lni-noubi] returns the generic Verify search page, with no document.
3. **A mismatched UBI fails.** The [same endpoint with a different firm's UBI (601050656) and InspectionNo 317962473][lni-wrongubi] also returns the generic search page.
4. **The detail page is a template.** The [Verify detail page for UBI 603106218][lni-detail] renders an empty template: the UBI field is blank, and the "Workplace Safety & Health" section has List/Grid toggles but no rows.
5. **The detail HTML shows the inspection grid is filled client-side.** The raw HTML of [Detail.aspx?UBI=603106218&LIC=ALLWARI891KO&SAW=][lni-detail-raw] (45,528 bytes):
   - sets `var UBI='603106218'; var LIC='ALLWARI891KO'; var SAW='';`
   - contains empty containers `#safetyList` ("list of safety inspections") and `#safetyGrid` ("grid-view of safety inspections")
   - loads `JavaScript/Service/service.js`, `DetailContractor.js`, `detail.js` and `toggleListGridDisplay.js`

   The page text says the section lets you "check for any past safety and health violations found on jobsites this business was responsible for". — [L&I Verify][lni-verify]

**Indexed citation URLs found by web search.** These were search hits, not lookups on L&I's site. Each pairs a WA inspection number with a UBI in the URL:
- UBI 603106218 and inspection 317962473 ([link][lni-doc])
- UBI 604520313 (licence FLATIWI813OT) and inspection 317991019 ([link][lni-doc2])
- UBI 601050656 (licence FORDCCI962OG) and inspection 317987919 ([link][lni-doc3])

**Local cross-check of those three**
- All three inspection numbers exist in the raw OSHA data, with matching employers:
  - WA317962473: ALLWAYS ROOFING INC, Snohomish, opened 2021-01-21
  - WA317991019: FLATIRON WEST INC THE LANE CONSTRUCTION COR, Renton, opened 2026-04-29
  - WA317987919: FORD CRANE INC, Snohomish, opened 2025-09-18
- All three UBIs equal the UBI on the project's WA licence rows for the same firms:
  - ALLWARI891KO: "Allways Roofing Inc", EXPIRED
  - FLATIWI813OT: "FLATIRON W, INC LANE CONST JV", ACTIVE
  - FORDCCI962OG: "FORD CRANE INC", ACTIVE
- The warehouse already links Allways and Ford Crane (M1), but **not** the Flatiron/Lane JV establishment.

— [raw inspection CSVs][raw-insp]; [warehouse `ref_ext.licence`][wh] (query 3g)

**Search engines as a reverse index.** A web search for "InspectionNo=317962473" finds the citation URL and therefore the UBI. A search for a typical cited inspection with no licence link (317978428, TAC BUILD LLC, 2024, 6 citations) finds nothing. — [search hit][lni-doc]

#### Queries (abbreviated)
```sql
-- 3a/3c
CREATE TABLE wa AS SELECT h.*, regexp_extract(upper(estab_name), '^\s*(WA[0-9]+)', 1) wa_nr
FROM hk h WHERE regexp_matches(upper(estab_name), '^\s*WA[0-9]{3,}');
SELECT count(*), count(DISTINCT wa_nr) FROM wa WHERE is_constr AND open_date >= DATE '2016-01-01';
SELECT corr(substr(wa_nr,3)::BIGINT, epoch(open_date)), count(*) FILTER (WHERE substr(wa_nr,3)::BIGINT = activity_nr) FROM wa;
-- 3d retention
SELECT count(*), count(*) FILTER (WHERE list_contains(dq_flags,'id_prefix_stripped')) FROM wh.osha.inspection
WHERE regexp_matches(upper(estab_name_raw), '^\s*WA[0-9]{9}');
-- 3e licence linkage of WA-numbered establishments
... establishment_key IN (SELECT establishment_key FROM wh.entity.ref_link WHERE source='licence:WA L&I' [AND method IN ('M1','M2')])
```

### Inferences
- **No forward lookup.** An inspection number alone cannot be turned into a UBI through any public L&I page I tested.
- **The endpoint is a confirmation test.** `CitationDocument.aspx?UBI=<ubi>&InspectionNo=<9 digits>` returns a document only for the correct pair (one positive and one negative test). So it can confirm a candidate UBI, for example one proposed by name and address matching against the WA licence table the project already ingests. One GET per candidate either returns the document, whose Legal Name and UBI also appear in it, or falls back to the search page. This probably works only for inspections that produced citations.
- **The reverse direction looks feasible.** The Verify detail page appears to list each UBI's inspections client-side, and the indexed citation URLs carry UBI and LIC, which suggests they are generated from that grid. If so, the inspection list could be retrieved for each WA licence UBI, and an inspection-to-UBI map assembled for the 21,690 WA-numbered warehouse inspections. That would give an exact identifier join for WA, including the 5,049 establishments with no licence link today and JV names that defeat name matching, such as Flatiron/Lane. I have not verified the data endpoint, its fields, or the terms of use and rate limits.
- **Display names carry the number.** Because the number is unique per inspection, the 10,302 display names that still carry it show the GC an arbitrary "WA3179… - NAME" string.
- **Oregon may allow the same approach.** Oregon OSHA's 9-digit numbers (11,030 warehouse rows) might be open to a similar lookup. This is untested.

### Gaps
- I did not see the per-UBI inspection grid's data source or contents. The JavaScript and its API calls were not fetched within the five-lookup limit.
- I did not test whether inspections without citations have any document or grid entry.
- L&I's terms of use and rate limits for automated lookups were not reviewed.
- The confirmation-test behaviour rests on one correct and one mismatched pair.
- The WebFetch tool cached the 363.6 KB citation PDF from lookup 1 automatically, under the Claude project `tool-results` folder (outside the repo). Nothing was saved to the repo.

## 4. Silver-label bias in eval/matching

### Takeaway
The ITA-EIN silver labels come from a narrow, unrepresentative slice of the population.

- **Larger firms.** Label-eligible establishments have a median OSHA-recorded headcount of 14 versus 5 in the population, and a median ITA headcount of 60 (only 8.6% under 20).
- **More active.** 14–18% have five or more inspections, versus 3.6%.
- **Concentrated.** The top 10 EINs supply 42% of all positive pairs, and five firms supply a third of the sampled positives.
- **Small firms are nearly absent.** Establishments with a median headcount under 20 are 85.4% of the population but only 6.2% of them are label-eligible, against 28.7% for larger ones. Person-name (sole-proprietor-like) establishments are 9.6% of the population and only 1.3% are eligible.
- **Positives are mostly easy.** 90–92% are identical-name pairs.
- **Negatives include many family pairs.** 17% of the sampled negatives (26 of 150) are clearly same-family by strong heuristics, and up to 33% are flagged by any heuristic.
- **The precision miss is mostly families.** 17 of the 18 negatives the matcher "wrongly" matched are such family pairs. Without them, matched precision would be 0.99 instead of 0.845.

### Cited Findings
- **How pairs are built.** A positive is two establishments linked by ITA M1 to the same single EIN. A negative is the same `name_core` and state with different EINs. Eligible establishments are non-placeholder, have a city, and are not `related_only`. The sample is ordered by `md5(keys || '7')`, 150 per class. — [eval/matching/run.py][eval]
- **My reproduction matches the eval.** Re-running that exact SQL read-only gives the same kind counts as [results.md][eval-res]: same_name_other_address 135, different_name 15, same_core_different_ein 144, same_name_different_ein 6.
- **The universes behind the sample:**
  - 19,756 eligible establishments covering 16,079 EINs.
  - Positive universe: 9,492 pairs, of which 8,731 (92.0%) have identical cleaned names and 761 (8.0%) have different names.
  - Negative universe: 813 pairs (52 with identical names).

  — [eval][eval]; [warehouse][wh] (query 4a)
- **Positive pairs are concentrated.** The 9,492 come from 2,525 EINs.

| Firm | Pairs | Share of positive universe |
|---|---|---|
| DR HORTON | 990 | 10.4% |
| TURNER CONSTRUCTION | 595 | 6.3% |
| NVR | 496 | 5.2% |
| GILBANE BUILDING | 465 | 4.9% |
| OTIS ELEVATOR | 378 | 4.0% |
| THYSSENKRUPP ELEVATOR | 276 | 2.9% |
| JE DUNN | 253 | 2.7% |
| CENTIMARK | 210 | 2.2% |
| PERFORMANCE CONTRACTING | 210 | 2.2% |
| KONE | 120 | 1.3% |
| **Top 10 total** | | **42.1%** |

  In the 150 sampled positives, DR HORTON has 17 pairs, TURNER 15, NVR 7, GILBANE 6 and OTIS 5: together 50 of 150 (33%). — [warehouse][wh] (query 4b)
- **Headcount reported on inspections.** On the 313,412 construction-coded inspections in the window, `nr_in_estab` is:

| Headcount | Inspections | Share |
|---|---|---|
| 0 | 7,524 | 2.4% |
| 1 | 28,100 | 9.0% |
| 2–19 | 223,609 | 71.3% |
| 20 or more | 54,179 | 17.3% |

  Quantiles (p10, p25, p50, p75, p90) are 1, 3, 5, 11, 40, and 157 rows report 10,000 or more. — [warehouse][wh] (query 4c)

**Establishment-level comparison.** Size is each establishment's median `nr_in_estab`; activity is `insp_n`. Columns: n = establishments; size quantiles p10 / p25 / p50 / p75 / p90; share with median under 20, at most 1, and at most 5; share with max ≥ 20; mean inspections; inspections p50 / p90; share with a single inspection; share with 5 or more.

| Group | n | size p10/25/50/75/90 | <20 | ≤1 | ≤5 | max≥20 | mean insp | insp p50/p90 | 1 insp | 5+ insp |
|---|---|---|---|---|---|---|---|---|---|---|
| Population (non-placeholder, not related-only) | 207,394 | 1.5/3/5/10/30 | 85.4% | 9.6% | 54.7% | 18.4% | 1.57 | 1/3 | 74.7% | 3.6% |
| Any ITA link (M1/M2/M3) | 28,110 | 2/5/14.5/46/118 | 55.7% | 5.0% | 28.5% | 57.4% | 2.63 | 1/5 | 51.1% | 13.2% |
| Label-eligible (one EIN via M1) | 19,756 | 2/5/14/45/110 | 56.0% | 4.7% | 28.4% | 57.7% | 2.69 | 2/6 | 49.0% | 14.1% |
| In positive universe | 6,202 | 2/5/15/54/169 | 54.9% | 5.2% | 28.2% | 59.1% | 2.89 | 2/6 | 47.5% | 15.5% |
| In negative universe | 1,050 | 2.5/5/15.5/48/111 | 53.0% | 4.5% | 27.0% | 60.1% | 3.22 | 2/6 | 47.7% | 17.0% |
| In sampled positives | 271 | 2/4/16/62/250 | 54.2% | 7.0% | 28.0% | 63.1% | 3.52 | 2/8 | 42.1% | 17.3% |
| In sampled negatives | 266 | 3/5/15/47/96 | 55.6% | 2.3% | 30.1% | 59.4% | 3.23 | 2/7 | 48.1% | 19.2% |
| In any sampled pair | 533 | 2/5/15/50/173 | 54.8% | 4.5% | 28.7% | 61.4% | 3.37 | 2/7.8 | 45.0% | 18.2% |

— [warehouse][wh] (query 4d)

**Coverage by size band** (population by median headcount)

| Size band | Establishments | Share of population | Label-eligible | % eligible | In pair universe | % in universe |
|---|---|---|---|---|---|---|
| 0–1 | 19,963 | 9.6% | 934 | 4.68% | 348 | 1.74% |
| 2–5 | 93,442 | 45.1% | 4,686 | 5.01% | 1,587 | 1.70% |
| 6–19 | 63,723 | 30.7% | 5,438 | 8.53% | 1,829 | 2.87% |
| 20–99 | 22,926 | 11.1% | 6,293 | 27.45% | 2,018 | 8.80% |
| 100–249 | 4,603 | 2.2% | 1,602 | 34.80% | 653 | 14.19% |
| 250+ | 2,737 | 1.3% | 803 | 29.34% | 468 | 17.10% |
| **Under 20 combined** | 177,128 | 85.4% | 11,058 | 6.24% | 3,764 | 2.13% |
| **20 or more combined** | 30,266 | 14.6% | 8,698 | 28.74% | 3,139 | 10.37% |

— [warehouse][wh] (query 4e)

**Coverage by number of inspections**

| Inspections | Share of population | % eligible |
|---|---|---|
| 1 | 74.7% | 6.26% |
| 2 | 14.6% | 13.48% |
| 3–4 | 7.1% | 21.67% |
| 5–9 | 2.8% | 34.64% |
| 10 or more | 0.7% | 48.97% |

- Weighted by inspections, only 48,242 of 313,412 construction inspections (15.4%) belong to label-eligible establishments. — [warehouse][wh] (query 4f)
- **Two measures of size disagree.** On the ITA side, the eligible establishments' latest filings report a median of 60 employees (p10 20, p90 281), and only 8.6% report under 20. All 121,437 construction ITA establishments have a median of 38, with 21.8% under 20. — [warehouse `ref_ext.ita_establishment_year`][wh] (query 4g)
- **Sole-proprietor proxy.** I flagged cleaned names that are entirely a person's name, using the project's 374-entry given-name list, with no generic or trade words. That flags 19,884 establishments (9.6% of the population); 254 of them (1.28%) are label-eligible, against 10.4% of all other establishments. — [warehouse `ref.given_name`][wh] (query 4h)

**Same-family heuristics on the negatives** (a and b are the two establishments in a pair)
- Same name: `a.clean_name = b.clean_name`
- Same city: `upper(a.city) = upper(b.city)`
- Prefix: one cleaned name plus a space starts the other
- Same address: equal `addr_key`
- "Strong" means same name, or same address, or prefix in the same city

| Flag | Sampled negatives (150) | Negative universe (813) |
|---|---|---|
| Same name | 6 | 52 |
| Same city | 36 | 143 |
| Prefix | 15 | 74 |
| Same address key | 16 | 65 |
| Same zip | 28 | 114 |
| Any of name, city, prefix | 49 (32.7%) | 236 (29.0%) |
| Strong | 26 (17.4%) | 127 (15.8%) |
| Weak only | 22 | 108 |

— [warehouse][wh] (query 4i)

**Examples from the sampled negatives** (the two names in each pair carry different EINs):
- **Same name:** DR HORTON (Charlotte, Morrisville ×2, High Point) vs DR HORTON (Raleigh); BOPAT ELECTRIC (Frederick vs Columbia, MD); CRITCHFIELD MECHANICAL (San Jose vs Huntington Beach).
- **Same address:** DORAN COMPANIES / DORAN CONSTRUCTION; MCCLURE SONS / MCCLURE BROTHERS; SUNRUN / SUNRUN INSTALLATION SERVICES; GUY M TURNER / GUY M TURNER CRANE RIGGING; JH BERRA PAVING / JH BERRA CONSTRUCTION; NOR SON / NOR SON CONSTRUCTION; HAGERMAN / HAGERMAN CONSTRUCTION (Fishers); DESERT PLASTERING, ROOFING and FRAMING (one North Las Vegas address); FOCUS PLUMBING, CONCRETE and FIRE PROTECTION (one Las Vegas address); FLY FORM; AMX; KMU; TURNKEY; WESTERN NATIONAL.
- **Prefix in the same city:** CHRISTMAN / CHRISTMAN CONSTRUCTORS; JAKE MARSHALL / JAKE MARSHALL SERVICE; LOBAR / LOBAR ASSOCIATES (×2).
- **Same city only:** BAKER CONCRETE CONSTRUCTION / BAKER CONCRETE CONSTRUCTORS; GRAYCOR; HENKEL; WRIGHT BROTHERS; A TEICHERT SON / TEICHERT ENERGY UTILITIES.
- **Weak flags that are probably unrelated:** LOUISVILLE WATER / LOUISVILLE PAVING; CONSTRUCTORS HAWAII / HAWAII PLUMBING GROUP.
- **Unflagged pairs** are mostly generic-word collisions: ACTION ROOFING / ACTION GLASS; ALLIANCE ROOFING / ALLIANCE CONSTRUCTION SOLUTIONS; ALLEGHENY ×3.

— [warehouse][wh] (query 4j)

**Concentration in the negative universe.** By name core, the largest are PACIFIC (32 pairs, 3.9%), DR HORTON (29, 3.6%), GREAT LAKES (22, 2.7%), PERFORMANCE (15), SOUTHERN (13) and NORTHWEST (13). In the 150 sampled negatives: PACIFIC 9, GREAT LAKES 5, DR HORTON 4, TURNER 4. — [warehouse][wh]

**Precision arithmetic from results.md**
- [results.md][eval-res] reports matched_precision 0.845, which is 98 matched positives against 18 matched negatives, and it lists all 18 matched negatives.
- 17 of the 18 are in the flagged groups above:
  - 14 strong: DR HORTON ×4, CRITCHFIELD, BOPAT, NOR SON, HAGERMAN (Fishers), DORAN, MCCLURE, JAKE MARSHALL, LOBAR ×2, CHRISTMAN.
  - 3 weak: BAKER CONCRETE, HAGERMAN (Fort Wayne vs Fishers), HENKEL.
- The only unflagged one is CONCRETE PLACEMENT (Santa Ana) / AMERICAN CONCRETE PLACEMENT (Anderson).
- Without the 17 flagged pairs, precision is 98/99 = 0.990. — [results.md][eval-res]

**Labels conflict for D.R. Horton.** The same results file lists DR HORTON INC GREENSBORO (High Point, NC) vs DR HORTON (Kingsport, TN) as a *positive* (same EIN). Meanwhile DR HORTON (Raleigh, NC) vs DR HORTON (Charlotte, NC) is a *negative*. — [results.md][eval-res]

**Different-name positives are few.** There are only 15 in the sample: 0 matched, 5 uncertain, 2 excluded, 8 not found. — [results.md][eval-res]

#### Queries (abbreviated)
```sql
-- 4a: base/positive/negative SQL copied verbatim from eval/matching/run.py lines 42-62 (seed '7'), with and without LIMIT 150
-- 4d/4e size and activity per establishment
WITH sz AS (SELECT establishment_key, median(nr_in_estab) med_emp, max(nr_in_estab) max_emp FROM osha.inspection GROUP BY 1)
SELECT grp, count(*), quantile_cont(med_emp,[.1,.25,.5,.75,.9]), avg((med_emp<20)::INT), avg((med_emp<=1)::INT),
       avg(insp_n), avg((insp_n=1)::INT), avg((insp_n>=5)::INT)
FROM entity.establishment JOIN sz USING (establishment_key)
WHERE NOT is_placeholder AND NOT coalesce(related_only,false) GROUP BY grp;  -- grp = population / eligible / universe / sample membership
-- 4h person-name proxy
clean_name = name_core AND len(tok) BETWEEN 2 AND 4 AND regexp_full_match(clean_name,'[A-Z]+( [A-Z]+)*')
  AND (list_contains(given_names, tok[1]) OR list_contains(given_names, tok[-1]))
-- 4i negatives
same_name: a.clean_name=b.clean_name; same_city: upper(a.city)=upper(b.city);
prefix: starts_with(an, bn||' ') OR starts_with(bn, an||' '); same_addr: a.addr_key=b.addr_key
```

### Inferences
- **The metrics describe big-firm matching.** The silver labels measure the matcher on large, multi-establishment, frequently inspected firms (national homebuilders, big GCs, elevator companies). The typical subcontractor a GC vets is a small firm with one or two OSHA records, and it is nearly absent. So `matched_precision`, `matched_recall` and `candidate_recall` should not be read as estimates for small subs.
- **OSHA headcount is not firm size.** For construction, `nr_in_estab` looks like a site-level count. Eligible establishments have an OSHA median of 14 but an ITA median of 60. So "85.4% under 20" overstates how many *firms* are under 20, but the gradient is clear: eligibility is about 4.6 times higher for 20+ establishments, and pair membership about 4.9 times higher.
- **The ITA threshold explains the gap.** ITA 300A filing is required only at 20+ employees in construction, and the eligible set's ITA headcounts confirm this (91.4% are 20 or more). Firms below the threshold, including sole proprietors, can enter the labels only by filing voluntarily.
- **Positives under-test name variation.** They are dominated by identical-name pairs of large firms at other addresses, which is the easiest case. Name-variant recall, the GC's real problem, rests on 15 sampled pairs (761 in the whole universe).
- **The negative label is "different legal entity".** That differs from "different company" in the sense a GC cares about. About 16–17% of negatives are strong same-family pairs, and roughly another 10–15% weakly so; by my manual reading of the 22 weak-only sampled pairs, about half are families. That gives roughly 25% (about 37 of 150) plausibly same-family pairs.
- **The headline precision is mostly label design.** The 0.845 figure is driven almost entirely by these family pairs, not by unrelated-company confusions.
- **Suggested fixes for the eval** (inference):
  - Stratify by size and inspection count.
  - Down-weight or cap pairs per EIN.
  - Mark family negatives as "related" rather than "different".
  - Add small-firm labels from another identifier source, such as WA UBI via L&I (section 3) or licence numbers.

### Gaps
- True firm size is unknown for the 90% of establishments without an ITA link; OSHA's `nr_in_estab` is a site-level proxy.
- The person-name proxy undercounts sole proprietors, since the given-name list has only 374 entries.
- Family judgments beyond the strong heuristics are my manual reading, not verified against corporate records.
- I did not re-run the matcher (no pipeline or eval runs), so the precision recalculation relies on the 18 matched negatives listed in results.md.

## 5. How many names and establishments one EIN covers in construction ITA filings

### Takeaway
In construction ITA filings, the EIN behaves like a **legal-entity (filer) identifier**: it is stable for a given establishment across years (only 1.7% change), and 91% of EINs carry a single cleaned name.

It is not a company-family identifier. Families routinely file under many EINs: TURNPOINT SERVICES under 48, D.R. Horton under 31, and Walsh Group under 23 in one state. 17.6% of company names with two or more establishments carry more than one EIN.

It is also noisy at the edges:
- 36.5% of multi-name EINs include names with nothing in common (roll-ups, project names typed as company names, errors).
- One placeholder-like EIN covers 723 "FACILITY n" establishments and escapes the junk filter.
- EIN is missing entirely for 2016–2018 and for about 16% of 2019+ rows.

### Cited Findings
**EIN availability by year** (warehouse `ref_ext.ita_establishment_year`, NAICS 23, after the pipeline's cleaning)

| Year | Construction rows | Share with EIN |
|---|---|---|
| 2016 | 19,551 | 0% |
| 2017 | 24,005 | 0% |
| 2018 | 27,140 | 0.6% |
| 2019 | 28,637 | 74.3% |
| 2020 | 29,009 | 85.1% |
| 2021 | 31,002 | 84.7% |
| 2022 | 33,803 | 84.2% |
| 2023 | 39,905 | 83.4% |
| 2024 | 39,137 | 84.3% |
| 2025 | 37,281 | 87.4% |

— [warehouse][wh]; [60_ita.sql][sql60] (query 5a)

**Raw EIN quality** (construction rows in the raw ITA files, before de-duplication)

| | 2016–2018 | 2019+ |
|---|---|---|
| Rows | 70,697 | 238,992 |
| Blank EIN | 70,534 | 32,540 (13.6%) |
| Not 9 digits | — | 6,248 (2.6%) |
| Placeholder value | — | 9 |
| Junk shared EIN | — | 512 |
| Usable | 163 | 199,683 (83.6%) |

- The pipeline's junk rule (a 9-digit EIN whose company names have more than 25 distinct first words) finds 27 junk EINs across all industries. The largest has 18,512 rows with 7,067 distinct first words, with names like "WASHINGTON_1386514". — [raw ITA CSVs][raw-ita]; [60_ita.sql][sql60] (query 5b)

**One EIN to many names or establishments.** There are 41,537 distinct construction EINs.

| An EIN covering more than one… | EINs | Share |
|---|---|---|
| Cleaned company name (counting empty names) | 4,830 | 11.6% |
| Non-empty cleaned company name | 3,733 | 9.0% |
| Name core | 3,975 | 9.6% |
| ITA establishment | 13,195 | 31.8% |
| State | 1,997 | 4.8% |

- Establishments per EIN: median 1, p90 3, p99 16, max 723. — [warehouse][wh] (query 5c)

**Kinds of multi-name EIN** (3,733 EINs with two or more non-empty names)

| Kind | EINs | Share |
|---|---|---|
| All names share a first word or a core token (division or location variants) | 2,366 | 63.4% |
| Some names share nothing | 1,363 | 36.5% |
| "FACILITY n" placeholder names | 4 | 0.1% |

Examples of names with nothing in common under one EIN:
- **Roll-up brands:** DH PACE vs OVERHEAD DOOR COMPANY OF WICHITA / OF ST LOUIS; WAYNE DALTON TEMPE vs WDSS OF SPOKANE VALLEY.
- **Parent and subsidiary:** BISCO REFRACTORIES vs OMI DBA BISCO; 3G COMPANIES vs GRAHAM CONSTRUCTION.
- **Project or site names typed as company names:** BAKERS PLACE APARTMENTS vs LACROSSE ISLE LA PLUME WWTP; DMA PLAZA vs EATON HIGH SCHOOL.
- **Typos:** ABERCROMBIE vs ANBERCROMBIE PIPELINE SERVICES.
- **Apparent errors:** ADM COLUMBUS NE vs LINDE CATOOSA.

— [warehouse][wh] (query 5d)

**EINs with the most names**

| EIN (masked) | Establishments | Names | States | What the names are |
|---|---|---|---|---|
| 94-…347 | 723 | 720 | 1 | "FACILITY 1", "FACILITY 10", … (passes the junk rule because every name starts with FACILITY) |
| 36-…790 | 78 | 90 | 1 | GEORGE SOLLITT plus a project name in each |
| 43-…574 | 98 | 69 | 24 | DH PACE and acquired door companies |
| 95-…490 | 62 | 65 | 26 | LENNAR plus a region in each |
| 71-…684 | 57 | 35 | 14 | SYSTEMS CONTRACTING / SYSTEMS PLANT SERVICES |
| 81-…712 | 58 | 27 | 13 | BARNARD |
| 39-…311 | 53 | 18 | 19 | MICHELS divisions |
| 75-…963 | 71 | 18 | 22 | DR HORTON plus divisions |

— [warehouse][wh] (query 5e)

**One name to many EINs**
- 2,167 of 42,585 distinct non-empty cleaned names (5.1%) carry more than one EIN; 916 of those stay within one state.
- 131 names have five or more EINs.
- Among names with two or more ITA establishments, 2,068 of 11,777 (17.6%) have more than one EIN.

Names with the most EINs:

| Name | EINs | Establishments | States |
|---|---|---|---|
| TURNPOINT SERVICES | 48 | 48 | 26 |
| ESSENTIAL SERVICES INTERMEDIATE HOLDING | 46 (+21 under a "…COR" spelling) | 47 | 28 |
| DR HORTON | 31 | 97 | 32 |
| KATERRA | 30 | 31 | 8 |
| FIDELITY ENGINEERING | 29 | 29 | 12 |
| NEARU SERVICES | 28 | 49 | 7 |
| WALSH GROUP | 23 | 31 | 1 |
| NORTHWINDS SERVICES GROUP | 20 | | |
| TECTA AMERICA | 20 | | |
| EMPLOYCO USA (a professional employer organization) | 16 | | 1 |

— [warehouse][wh] (query 5f)

**Stability over time**
- 86,985 ITA establishments have an EIN, and 46,204 of them filed in two or more years. Only 804 of those (1.7%) changed EIN across years.
- On the OSHA side, 22,379 establishments link (M1) to EIN-bearing ITA rows; 1,012 of them (4.5%) map to more than one EIN, which excludes them from the eval's eligible set. — [warehouse][wh] (query 5g)

#### Queries (abbreviated)
```sql
WITH c AS (SELECT * FROM ref_ext.ita_establishment_year WHERE naics LIKE '23%' AND ein IS NOT NULL)
SELECT ein, count(DISTINCT company_clean), count(DISTINCT name_core(company_clean)), count(DISTINCT establishment_id),
       count(DISTINCT state) FROM c GROUP BY 1;                       -- 5c/5e
SELECT company_clean, count(DISTINCT ein), count(DISTINCT establishment_id), count(DISTINCT state)
FROM c WHERE company_clean<>'' GROUP BY 1;                          -- 5f
-- 5d: per EIN, all name pairs; same_first = split_part(a,' ',1)=split_part(b,' ',1);
--     share_core = len(list_intersect(string_split(core_a,' '), string_split(core_b,' ')))>0
-- 5b raw: read_csv('data/raw/reference/osha_ita/utf8/*.csv', all_varchar=true, ...), digits-only EIN,
--     junk = 9-digit EIN with count(DISTINCT split_part(upper(trim(company_name)),' ',1)) > 25  (as 60_ita.sql)
-- 5g: SELECT establishment_id, count(DISTINCT ein), count(DISTINCT year) FROM c GROUP BY 1
```

### Inferences
- **Matching EINs is strong evidence.** Two establishments with the same EIN are almost always the same legal entity or division. The exceptions are a few roll-up brands, project-named filings, and placeholder filers such as "FACILITY n". `ita_junk_ein` should also catch EINs with hundreds of names that share a first word; that is a fix suggestion, not a verified need beyond the one case.
- **Different EINs are weak evidence.** Different EINs often mean sibling legal entities of one family: subsidiaries (D.R. Horton), acquired companies in a roll-up (Turnpoint, Essential Services, Tecta), or separate state entities (Walsh Group's 23 EINs in one state). This supports treating EIN mismatch as "related or unknown" rather than "different" in the eval's negatives (section 4), and keeping EIN as adjudicator evidence rather than an automatic merge, as [60_ita.sql][sql60] already says.
- **EIN cannot label older history.** EIN is absent for 2016–2018 filings, so EIN-based labels apply only to establishments with 2019+ ITA filings. That compounds the size bias in section 4.

### Gaps
- Corporate-family structure (which EINs belong to one parent) cannot be verified from the local data; it would need an external ownership source.
- The identity of the "FACILITY n" filer (94-…347) is unknown.
- I did not quantify EIN multiplicity outside construction NAICS.

[raw-insp]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/data/raw/inspection/
[raw-zip]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/data/raw/OSHA_inspection.zip
[raw-viol]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/data/raw/violation/
[raw-dir]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/data/raw/
[raw-ita]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/data/raw/reference/osha_ita/utf8/
[wh]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/data/build/warehouse-20261003T212330Z.duckdb
[eval]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/eval/matching/run.py
[eval-res]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/eval/matching/results.md
[sql10]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/ssi/pipeline/sql/10_raw.sql
[sql20]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/ssi/pipeline/sql/20_scope.sql
[sql21]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/ssi/pipeline/sql/21_inspection.sql
[sql22]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/ssi/pipeline/sql/22_stg_violation.sql
[sql60]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/ssi/pipeline/sql/60_ita.sql
[sql61]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/ssi/pipeline/sql/61_licence.sql
[macros]: file:///Users/peterhyland/Desktop/GitHub/site-safety-intelligence/ssi/cleaning/macros.sql
[lni-doc]: https://secure.lni.wa.gov/verify/Details/CitationDocument.aspx?LIC=&UBI=603106218&SAW=&VIO=&InspectionNo=317962473
[lni-doc2]: https://secure.lni.wa.gov/verify/Details/CitationDocument.aspx?UBI=604520313&LIC=FLATIWI813OT&SAW=false&VIO=&InspectionNo=317991019
[lni-doc3]: https://secure.lni.wa.gov/verify/Details/CitationDocument.aspx?UBI=601050656&LIC=FORDCCI962OG&VIO=&InspectionNo=317987919
[lni-noubi]: https://secure.lni.wa.gov/verify/Details/CitationDocument.aspx?InspectionNo=317962473
[lni-wrongubi]: https://secure.lni.wa.gov/verify/Details/CitationDocument.aspx?LIC=&UBI=601050656&SAW=&VIO=&InspectionNo=317962473
[lni-detail]: https://secure.lni.wa.gov/verify/Detail.aspx?UBI=603106218
[lni-detail-raw]: https://secure.lni.wa.gov/verify/Detail.aspx?UBI=603106218&LIC=ALLWARI891KO&SAW=
[lni-verify]: https://secure.lni.wa.gov/verify/
[dol-dev]: https://developer.dol.gov/health-and-safety/dol-osha-enforcement/
