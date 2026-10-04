# Source coverage probes: how many OSHA construction employers appear in candidate company-matching sources

Live probes run on 2026-10-04 against warehouse `warehouse-20261003T212330Z`. Outcome codes used throughout:

- **V (verified):** the name agrees (exact after the app's `clean_name()`, a legal-form or punctuation variant, a descriptor variant, a DBA, or a prior name) **and** the street, zip or city agrees with one of the OSHA establishment's mailing addresses.
- **P (probable):** an exact or near-exact distinctive name in the same state, but the address differs. Typical reasons are an HQ record against a branch, a registered-agent address, or a neighbouring town.
- **A (ambiguous):** several plausible same-name entities, or a name-only match in a conflicting city.
- **—:** not found.
- **addr-only:** same address but an unrelated name. These are noted and never counted.

Personal names of sole proprietors are shown as "[personal name]" on purpose.

## 1. How were the samples drawn, the sources queried, and hits judged?

### Takeaway
A reproducible stratified sample was probed with 180 small API requests, about 0.6 MB in total:

- 60 establishments across 10 states;
- 30 each from WA, NY and TX;
- sample order set by `md5(establishment_key)`.

The design gives small (<20 employees) and large (≥20) firms equal weight, but 82% of the population is small. Raw hit rates therefore overstate population coverage, so every source also gets a population-weighted rate. All intervals are wide, about ±15–25 percentage points.

### Cited Findings
- **Population.** There are 134,488 non-placeholder construction establishments (`construction_insp_n > 0`, not `related_only`) with at least one inspection opened on or after 2020-01-01. Of these, 110,499 are "small" (max `nr_in_estab` over those inspections < 20, or null) and 23,989 are "large" (≥ 20), so 82% are small. — [warehouse query](../../data/build/warehouse-20261003T212330Z.duckdb)
- **Population by state (small / large).** — [warehouse query](../../data/build/warehouse-20261003T212330Z.duckdb)

  | State | Small | Large |
  |---|---|---|
  | WA | 6,493 | 452 |
  | NY | 5,369 | 1,047 |
  | TX | 9,764 | 1,818 |
  | CA | 6,046 | 3,358 |
  | FL | 5,292 | 1,277 |
  | GA | 3,433 | 584 |
  | IL | 5,605 | 665 |
  | NC | 5,078 | 607 |
  | OH | 4,235 | 908 |
  | TN | 1,625 | 459 |

  Small shares are 93% in WA, 84% in NY and 84% in TX.
- **How the sample was drawn.** Within each state × size stratum, rows were ordered by `md5(establishment_key)`. — [warehouse query](../../data/build/warehouse-20261003T212330Z.duckdb)
  - Multi-state sample: the first 3 per stratum in TN, GA, FL, TX, NY, CA, WA, NC, IL and OH, giving 60 (30 small, 30 large).
  - WA, NY and TX samples: the first 15 per stratum (30 each). Their first 3 per stratum are the same establishments as in the multi-state sample.
  - The establishment address is the OSHA mailing address, per `40_establishment.sql`. — [40_establishment.sql](../../ssi/pipeline/sql/40_establishment.sql)
- **Sample make-up.** — [warehouse query](../../data/build/warehouse-20261003T212330Z.duckdb)
  - 14 distinct establishments are a bare personal name: 7 multi-state, 1 WA, 2 NY and 4 more in TX. Two of the multi-state ones are also in the TX sample.
  - 5 are government units: Schenectady Co DPW, Johnson City water & sewer, Lowe Township Road District, City of Bellingham, and Eastchester Town Highway Dept.
  - 1 is a joint venture (KZJV LLC).
- **Query design.** Name patterns were SoQL `upper(name) like '%TOKEN%'` on the rarest name tokens, with rarity taken from warehouse `entity.token_df`. Initials-only names used wildcards (for example `'%J%L PLUMB%'`). Each pattern carried a state filter.
  - FMCSA requests OR'ed 6 establishments per state.
  - Each FMCSA establishment added a broad core-token clause restricted to its OSHA mailing zip, plus a street-number-plus-zip clause, to catch DBA and legal-name pairs at the same address.
  - Template, shown for one establishment from the TN batch:
    `https://data.transportation.gov/resource/az4n-8mr2.json?$select=dot_number,legal_name,dba_name,status_code,phy_street,phy_city,phy_state,phy_zip,carrier_mailing_street,carrier_mailing_city,carrier_mailing_state,carrier_mailing_zip,company_officer_1,company_officer_2,add_date,mcs150_date,power_units,total_drivers,crgo_construct,business_org_desc,carrier_operation&$where=((phy_state='TN' OR carrier_mailing_state='TN') AND (upper(legal_name) like '%TRAF%MARK%' OR upper(dba_name) like '%TRAF%MARK%' OR upper(legal_name) like '%TRAFMARK%' OR upper(dba_name) like '%TRAFMARK%')) OR ((phy_street like '280 %' AND phy_zip like '38017%') OR (carrier_mailing_street like '280 %' AND carrier_mailing_zip like '38017%')) OR …&$limit=1000&$order=dot_number`

  — [FMCSA Company Census API](https://data.transportation.gov/resource/az4n-8mr2.json)
- **Name comparisons** used the app's own `clean_name()` and `name_core()` macros, which are persisted in the warehouse. — [macros.sql](../../ssi/cleaning/macros.sql)
- **Request budget.** 180 API requests were made; 177 returned HTTP 200 and 3 failed on TLS before the CA-bundle fix described in §3. — endpoints as cited in §2–§6

  | Host | Requests |
  |---|---|
  | api.usaspending.gov | 136 |
  | data.wa.gov | 17 |
  | data.transportation.gov | 11 |
  | data.ny.gov | 9 |
  | data.texas.gov | 6 |
  | api.us.socrata.com (catalog search) | 1 |

  - The USAspending 136 break down as: 61 recipient-keyword searches, 54 profile GETs, 4 state-filtered loan searches, 10 batched subaward searches, and 7 tests.
  - Median latency was 0.95 s and the maximum 9.1 s. Total transfer was about 0.62 MB.
  - About 10 extra GitHub fetches retrieved USAspending API contract docs and SQL; these returned no data.

### Inferences
- With n = 15–30 per stratum, Wilson 95% intervals are ±15–25 pp. Differences of less than about 20 pp between sources should not drive decisions.
- **Population weighting.** The weighted rates combine the small and large rates using population shares: 82/18 nationally, 93/7 for WA, and 84/16 for NY and TX. The multi-state sample weights the 10 states equally, so its weighted rates are rough.
- Name patterns found **after** the app's cleaning dominate. Most V and P hits are an exact `clean_name` match: 17 of 20 FMCSA hits, and every USAspending hit except the plural "GLOBAL STEEL ERECTORS". So these sources mostly *confirm* identities. Only a minority of hits expose a second name that would fix a hard failure (see §8).

### Gaps
- Judgements were manual and made by one reviewer, with no gold standard. "P" outcomes on common names could be wrong.
- The USAspending keyword is a contiguous substring, and only one pattern per establishment was used there, so "&" versus "AND" variants may be missed.

## 2. FMCSA Company Census File (`az4n-8mr2`, data.transportation.gov)

### Takeaway
**Multi-state hit rate (n=60):**

- V: 16/60 (27%, 95% CI 17–39%).
- V+P: 20/60 (33%, 23–46%).
- Large firms: V 40% (12/30), V+P 50%.
- Small firms: V 13% (4/30), V+P 17%.
- Population-weighted: about 18% (V) to 23% (V+P).

Hits almost always add officer names, a stable USDOT number and fleet size. Some add physical-versus-mailing addresses, and 3 of 16 add a DBA. Coverage follows truck ownership, so personal-name sole proprietors and small trades are mostly absent.

### Cited Findings
- **Per-establishment outcome, multi-state sample.** Same rows as the USAspending table in §3. — [FMCSA API](https://data.transportation.gov/resource/az4n-8mr2.json)
  - **V, large (12):**
    - LEONARD ROOFING (CA): FMCSA lists 43280 against OSHA's 42380 Business Park Dr, same zip.
    - O'STEEN BROTHERS (FL): dba "OBI".
    - CURB & GUTTER PROFESSIONALS (GA).
    - ROSSI CONTRACTORS (IL): inactive.
    - INDUSTRIAL CORK COMPANY (IL).
    - SCHENECTADY CO DPW (NY): "SCHENECTADY COUNTY DPW", inactive, same city.
    - AB CONSTRUCTION & ROOFING (NY).
    - BSB CONSTRUCTION (NY).
    - VALLEY ELECTRICAL CONSOLIDATED (OH): found **only by address**, as "VEC INC" (USDOT 655318, 95 power units).
    - TRAF-MARK INDUSTRIES (TN).
    - ALL ABOUT PROJECTS (WA): "ALL ABOUT PROJECTS LLC", dba "RAIN CITY EXTERIORS", inactive.
    - ROGNLIN'S INC (WA).
  - **V, small (4):**
    - [personal name, Los Angeles]: FMCSA "<same name> CONSTRUCTION", dba "KRB CONSTRUCTION", one door away on the same street.
    - B & B WELL DRILLING (FL).
    - O'ROURKE WRECKING (OH): plus an active sister record, "O'ROURKE WRECKING TRANSPORT COMPANY", at the same address.
    - CIVILWORKS NW (WA).
  - **P (4):**
    - MIDSOUTH STEEL (GA): FMCSA has an Atlanta street address; OSHA has a Fairburn PO box.
    - MASSANA CONSTRUCTION (GA): Newnan versus Tyrone.
    - DAN WILLIAMS COMPANY (TX): Austin/Hutto versus El Paso.
    - TURNER CONSTRUCTION COMPANY (NY): HQ USDOT 73988 in New York NY, 564 power units, against an OSHA Buffalo office.
  - **Parent org only (not counted):** JOHNSON CITY WATER & SEWER (TN) matches "CITY OF JOHNSON CITY".
  - **A:** [personal name, Whitehall OH] matched only a same-name inactive carrier in Parma OH. CIRCLE K ENTERPRISES (WA) matched only a same-name DBA of a person in Washougal; OSHA's address is in Pasco.
- **Extra identity information on the 16 V hits.** — [FMCSA API](https://data.transportation.gov/resource/az4n-8mr2.json)
  - Officer names on 14.
  - A DBA on 3.
  - Physical street differs from mailing street on 6. Examples: Rognlin's (physical address on W State St; mailing PO Box 307); Civilworks NW (physical address on NE Caples Rd; mailing PO Box 970).
  - 4 are inactive (`status_code` ≠ A).
  - `crgo_construct` = X on 14.
  - Power units range from 1 to 95.
  - `add_date` ranges from 1987 to 2023.
- **Address-only noise.** — [FMCSA API](https://data.transportation.gov/resource/az4n-8mr2.json)
  - At Global Steel Erector's street address FMCSA lists an unrelated-looking name, "WEST COAST IRON INC".
  - Shared buildings and mail drops return many unrelated carriers. AA Phoenix's Buford Hwy suite in Cumming GA returned 8; Clean Force's Tampa office tower returned 2.
- **Misses (37 of 60):** — [FMCSA API](https://data.transportation.gov/resource/az4n-8mr2.json)
  - **Named firms (29):** J & L PLUMBING, IM BUILDERS, INLINE PAINTING, CLEAN FORCE, SEACOAST AIR CONDITIONING, VAZQUEZ CONCRETE FINISH, AGUILAR'S CONSTRUCTION, L&G GREEN POWERHOUSE, CONTINENTAL ELECTRICAL CONSTRUCTION, Y&B ROOFING, ANDY'S GT ROOFING, TRI POINTE HOMES, PROSTEEL BUILDINGS, CORTES SPARTANS FRAMING, CREATIVE MASONRY, ADAMS HOMES AEC, RAMOS FRAMING, MGC DESIGN, STEELCON, STANDARD PLUMBING, PAUL RUSSELL CONSTRUCTION, EARLYBIRD PAINT, C&CH SIDING, TOPOLLO, MSF ELECTRIC, ANT FORCE, TURNKEY CONSTRUCTION, J & I GROUP, and DYNAMIC RFS (FMCSA has a different firm, "RFS CONSTRUCTION", in Ellensburg).
  - **Address-only (2):** GLOBAL STEEL ERECTOR and AA PHOENIX.
  - **Government (1):** LOWE TOWNSHIP ROAD DISTRICT.
  - **Personal-name establishments (5).**
- **Interval estimates.** — computed from the outcomes above
  - V: raw 27% [17–39%]. Large 40% [25–58%]. Small 13% [5–30%]. Population-weighted 18% [8–29%].
  - V+P: raw 33% [23–46%]. Large 50% [33–67%]. Small 17% [7–34%]. Population-weighted 23% [11–34%].
- **Performance.** 10 state-batched queries, each OR-ing 6 establishments and up to about 2.8k characters of `$where`, returned 8–62 rows in 0.8–2.7 s each. — [FMCSA API](https://data.transportation.gov/resource/az4n-8mr2.json)

### Inferences
- FMCSA is a national single-file source. Its coverage tracks fleet ownership, so it is useful for heavy civil, roofing, steel, paving, demolition and well drilling, and weak for labour-only trades and sole proprietors.
- Its distinctive value is officer names plus physical addresses that differ from OSHA PO boxes. Officer names help only where the person has a USDOT registration.
- Address clauses surface acronyms and renamed firms ("VEC INC"). They also pull in noise at shared addresses, so they need the same frequency weighting the app already applies to OSHA site addresses.

### Gaps
- FMCSA was not probed on the WA, NY and TX 30-samples.
- Officer-name search was tested only for personal-name establishments.
- `dun_bradstreet_no` was not examined.

## 3. USAspending.gov API (recipient profiles, SBA loans, subawards)

### Takeaway
**Multi-state hit rate (n=60):**

- V: 21/60 (35%, 24–48%).
- V+P: 29/60 (48%, 36–61%).
- Large firms: V 47%, V+P 60%.
- Small firms: V 23%, V+P 37%.
- Population-weighted: about 27% (V) and 41% (V+P).

**Where the hits come from.** 14 of the 21 V hits exist only as SBA COVID-era loan or assistance records: recipient level "R", no UEI, 2020–21 addresses.

- **UEI-bearing records** (SAM registrations, contracts or subawards) are verified for only 7/60 (12%, 6–22%), all of them large firms. That is about 4% population-weighted.
- **Subawardees:** only 3/60 (5%).
- **Request cost:** the API needs at least 2 requests per establishment (name search, then a profile for the address), because the name filter takes one value.

### Cited Findings
- **Endpoints used:**
  - `POST https://api.usaspending.gov/api/v2/recipient/` with `{"keyword": "ROGNLIN", "award_type": "all", "limit": 100}`. This is a nationwide name/UEI/DUNS search over recipient profiles with no state filter. It returns `id`, `name`, `uei`, `duns`, `recipient_level` and trailing-12-month `amount`. — [recipient endpoint contract](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/recipient.md)
  - `GET /api/v2/recipient/{id}/?year=all`, which returns `location`, `alternate_names`, `business_types`, parent and award or loan totals. — [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/)
  - `POST /api/v2/search/spending_by_award/`, used two ways. — [spending_by_award API](https://api.usaspending.gov/api/v2/search/spending_by_award/)
    - Loans: `award_type_codes` ["07","08"] with `recipient_search_text` [name] and `recipient_locations` [{"country":"USA","state":ST}].
    - Subawards: `spending_level: "subawards"` with `keywords` (6 names per state), `award_type_codes` A–D, a state filter, and fields "Sub-Awardee Name", "Sub-Recipient UEI", "Sub-Recipient Location" and "Prime Recipient Name".
- `recipient_search_text` "must not exceed a length of 1 item". — [search_filters.md](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/search_filters.md)
- The `keywords` filter ORs its items. A test with ["ROGNLIN","BRASFIELD"] returned subawards to both ROGNLINS, INC. and BRASFIELD & GORRIE LLC. — [spending_by_award API](https://api.usaspending.gov/api/v2/search/spending_by_award/)
- The autocomplete endpoint returns names only. UEI is populated "only … when the search text matches a UEI", so it cannot verify location. — [autocomplete contract](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/autocomplete/recipient.md)
- Recipient profiles are rebuilt from `rpt.recipient_lookup`. The lookup's build steps load SAM records ("010 Adding Recipient records from SAM") and FPDS/FABS transactions; no subaward step is listed. — [restock_recipient_profile.sql](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/recipient/management/sql/restock_recipient_profile.sql); [recipient_lookup SQL folder](https://github.com/fedspendingtransparency/usaspending-api/tree/master/usaspending_api/recipient/management/sql/recipient_lookup)
- **Per-establishment outcomes, multi-state sample (USAspending | FMCSA).** — [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/); [FMCSA API](https://data.transportation.gov/resource/az4n-8mr2.json)

  | St | Size | OSHA establishment | USAspending | FMCSA |
  |---|---|---|---|---|
  | CA | L | GLOBAL STEEL ERECTOR INC | V (plural "ERECTORS": SBA loan at same street; subaward with UEI) | — (addr-only: WEST COAST IRON INC) |
  | CA | L | J & L PLUMBING INC | — (same name in OK, GA) | — |
  | CA | L | LEONARD ROOFING INC. | — (same name in VA) | V |
  | CA | S | IM BUILDERS INC | — | — |
  | CA | S | [personal name, Los Angeles] | V (5 SBA loans, same block) | V (dba KRB CONSTRUCTION) |
  | CA | S | INLINE PAINTING INC. | — (same name in IN) | — |
  | FL | L | O'STEEN BROTHERS, INC. | P (Gainesville) | V (dba OBI) |
  | FL | L | CLEAN FORCE BUILDING SERVICES INC | V (SBA loans; zip) | — |
  | FL | L | SEACOAST AIR CONDITIONING AND SHEET METAL | V (UEI; zip) | — |
  | FL | S | B & B WELL DRILLING, INC. | V | V |
  | FL | S | VAZQUEZ CONCRETE FINISH, CORP. | P (Miami, same county) | — |
  | FL | S | AGUILAR'S CONSTRUCTION SERVICES | — | — |
  | GA | L | MIDSOUTH STEEL INC. | P (same Atlanta street as FMCSA; "LLC") | P |
  | GA | L | CURB & GUTTER PROFESSIONALS | V | V |
  | GA | L | MASSANA CONSTRUCTION INC | P (UEI; Newnan) | P |
  | GA | S | L&G GREEN POWERHOUSE BUILDERS | — | — |
  | GA | S | AA PHOENIX CONSTRUCTION GROUP | V (same suite) | — (addr-only, mail drop) |
  | GA | S | [personal name] | — | — |
  | IL | L | ROSSI CONTRACTORS | V (UEI) | V |
  | IL | L | INDUSTRIAL CORK COMPANY | V | V |
  | IL | L | CONTINENTAL ELECTRICAL CONSTRUCTION | V (UEI; 38 subaward rows) | — |
  | IL | S | Y&B ROOFING | — | — |
  | IL | S | ANDY'S GT ROOFING | — | — |
  | IL | S | LOWE TOWNSHIP ROAD DISTRICT | — | — |
  | NC | L | TRI POINTE HOMES HOLDINGS | — | — |
  | NC | L | PROSTEEL BUILDINGS | — | — |
  | NC | L | CORTES SPARTANS FRAMING | — | — |
  | NC | S | CREATIVE MASONRY | — (same name in CA, CT) | — |
  | NC | S | [personal name] | — | — |
  | NC | S | ADAMS HOMES AEC | — | — |
  | NY | L | SCHENECTADY CO DPW | parent (COUNTY OF SCHENECTADY UEI) | V |
  | NY | L | AB CONSTRUCTION & ROOFING | — | V |
  | NY | L | BSB CONSTRUCTION INC. | V (SBA loan at OSHA street) | V |
  | NY | S | RAMOS FRAMING CORP | — | — |
  | NY | S | TURNER CONSTRUCTION COMPANY (Buffalo) | P (HQ UEIs) | P |
  | NY | S | MGC DESIGN AND CONTRACTING | V | — |
  | OH | L | VALLEY ELECTRICAL CONSOLIDATED | V (UEI) | V (as VEC INC) |
  | OH | L | STEELCON, LLC | — (same name in TN, CO) | — |
  | OH | L | STANDARD PLUMBING AND HEATING | V (UEI; "THE STANDARD PLUMBING & HEATING COMPANY LLC"; zip) | — |
  | OH | S | [personal name, common] | — (0 OH loans) | A |
  | OH | S | PAUL RUSSELL CONSTRUCTION LLC | — (namesakes in AZ, MS) | — |
  | OH | S | O'ROURKE WRECKING COMPANY | V | V |
  | TN | L | TRAF-MARK INDUSTRIES | — (0 results) | V |
  | TN | L | [personal name] | — | — |
  | TN | L | JOHNSON CITY WATER & SEWER | parent (CITY OF JOHNSON CITY UEI) | parent |
  | TN | S | EARLYBIRD PAINT & CONSTRUCTION | V | — |
  | TN | S | C&CH SIDING CONSTRUCTION | — | — |
  | TN | S | TOPOLLO CONSTRUCTION | — | — |
  | TX | L | [personal name] | — | — |
  | TX | L | DAN WILLIAMS COMPANY | P (UEI; Austin) | P |
  | TX | L | MSF ELECTRIC, INC. | V (SBA loan at OSHA street) | — |
  | TX | S | ANT FORCE CONSTRUCTION GROUP | — | — (addr-only) |
  | TX | S | TURNKEY CONSTRUCTION COMPANY I, LP | V | — |
  | TX | S | [personal name] | — (namesake in IL) | — |
  | WA | L | ALL ABOUT PROJECTS INC | V | V (dba RAIN CITY EXTERIORS) |
  | WA | L | CIRCLE K ENTERPRISES LLC | V (same street) | A |
  | WA | L | ROGNLINS INC | V (UEI + subaward) | V |
  | WA | S | CIVILWORKS NW INC | P (Vancouver) | V |
  | WA | S | DYNAMIC RFS CONSTRUCTION LLC | P (Vancouver) | — |
  | WA | S | J & I GROUP INC | — | — |

- **Interval estimates.** — computed from the table
  - USAspending V: large 47% [30–64%], small 23% [12–41%], population-weighted 27% [15–40%].
  - USAspending V+P: large 60% [42–75%], small 37% [22–54%], population-weighted 41% [26–55%].
  - UEI-bearing V only: 7/60 = 12% [6–22%] (large 7/30, small 0/30).
  - Subawards: 3/60 = 5% [2–14%].
- **What the hits come from.** — [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/)
  - Of the 21 V hits, 14 rest only on R-level records with no UEI.
    - 13 of those profiles show SBA loan transactions. Examples: B & B Well Drilling (1 loan, $52,844 face value), MSF Electric ($3.43M), O'Rourke Wrecking ($1.16M), Circle K Enterprises ($93,300), and the Los Angeles sole proprietor (5 loans).
    - MGC Design's profile shows a single $2,000 transaction of unidentified type.
  - The other 7 V hits carry a UEI from SAM, contract or subaward data: Seacoast, Rossi, Continental Electrical, Valley Electrical Consolidated, The Standard Plumbing & Heating, Rognlins, and Global Steel Erectors (via subaward).
- **Loan record example.** BSB CONSTRUCTION INC, 1613 Route 9W, Milton NY: issued 2020-04-28, $154,635.80, Small Business Administration, description "TO AID SMALL BUSINESSES IN MAINTAINING W…". It was found only by the state-filtered loan search, not by the keyword list. — [spending_by_award API](https://api.usaspending.gov/api/v2/search/spending_by_award/)
- **Subaward hits.** These give the sub-to-prime (GC) link plus a sub UEI. — [spending_by_award API](https://api.usaspending.gov/api/v2/search/spending_by_award/)
  - GLOBAL STEEL ERECTORS, INC (UEI TP44NKDZ34P9): sub to RQ CONSTRUCTION, LLC, 2023-12-05, $565,528.
  - ROGNLINS, INC. (UEI VALGLNTAG6A1): sub to NORTHERN MANAGEMENT SERVICES, INC., 2019-03-19, $649,200, "SITE WORK".
  - CONTINENTAL ELECTRICAL CONSTRUCTION COMPANY LLC (UEI KAQUAJAD1X38): 38 rows, including prime NORTHROP GRUMMAN SYSTEMS CORPORATION on 2015-10-29. Identical rows repeat.
- **`alternate_names`** are formatting variants, not DBAs. ROGNLINS, INC. lists "ROGNLIN'S, INC.", "ROGNLIN'S  INC." and "MMROGNLIN'S, INC."; THE STANDARD PLUMBING & HEATING COMPANY LLC lists "STANDARD PLUMBING & HEATING COMPANY, THE". — [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/)
- **One company, several recipient IDs.** The keyword "ROGNLIN" returned 6 profiles. — [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/)
  - P and C records with UEI VALGLNTAG6A1.
  - A P record "ROGNLINS  INC." with a different UEI (YTJEMGHU35T3) and no address.
  - Two R records with no UEI, one located at 321 West State Street, Aberdeen.
  - One unrelated firm, ROGNLIN MOTORSPORTS & MARINE LLC.
- **`business_types`** carry flags such as small_business, subchapter_s_corporation, minority_owned_business, woman_owned_business and other_than_small_business. — [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/)
- **Nationwide keyword noise.** "AGUILAR" returned 2,472 recipients, "SCHENECTADY" 215, "AB CONSTRUCTION" 170, a common personal name 96, and "TURNER CONSTRUCTION" 59. — [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/)
- **TLS issue.** api.usaspending.gov's certificate chain ends at "Sectigo Public Server Authentication Root R46". That root is missing from `/private/etc/ssl/cert.pem`, which the project's Python used. Calls failed until the certifi CA bundle was passed. — [USAspending API](https://api.usaspending.gov/api/v2/recipient/)

### Inferences
- **The breadth is the PPP list.** USAspending's apparent breadth for small firms is mostly the 2020–21 SBA PPP/EIDL borrower list. It gives a legal name and a 2020-era address, but no UEI, DBA or officers, and nothing for firms formed after 2021. The same borrower data is published in bulk by SBA; that was not probed here.
- **UEI records and subawards are narrow.** UEI-bearing federal records and subawards reach mainly larger firms. Subawards are the only free source that names a construction sub's federal prime (GC), but only 5% of the sample appears there.
- **The API is not a bulk route.** Per-name API matching (≥2 calls per establishment) does not scale. Ingestion would need the bulk award/subaward archives or SBA's PPP files.

### Gaps
- At most 2 profiles were checked per establishment. For example, 2 of 5 same-name "J & L PLUMBING" records were checked, though a CA-filtered loan search returned none.
- Grants and direct payments were not separated. MGC Design's matched record (1 transaction of $2,000, no loan) has an unidentified award type.
- The CITY OF JOHNSON CITY UEI was not checked for TN versus NY location.

## 4. WA L&I prevailing-wage filings (Intents `t9je-9qwa`, Affidavits `9ncw-tqjn`), including the site-level test

### Takeaway
**WA hit rate (n=30):**

- 18/30 WA establishments have filed intents (60%, 42–75%).
- Large firms: 13/15 (87%).
- Small firms: 5/15 (33%).
- Population-weighted: about 37% (14–59%), because 93% of WA OSHA construction establishments are small.

**How the hits were found:**

- 12 hits came through the UBI the app's existing licence link already supplies.
- The other 6 were found by name. Each turned out to be an existing WA licence record the app had failed to link, because of a zip mismatch, an abbreviation, a rename, or a licence held under a trade name.

**Site-level test (10 multi-employer OSHA sites):**

- 1 site matched a public project naming all 3 inspected employers and their tier chain.
- 1 site matched a likely GC project only.
- 8 sites had no filings.

### Cited Findings
- **Queries** (one request each), all against the Intents endpoint (`t9je-9qwa`) unless noted:
  - Intents aggregated by UBI: `$select=ubi,companyname,companycity,count(*) as n,min(expected_start_dt),max(expected_start_dt)&$where=ubi in ('141005883',…16 UBIs)&$group=ubi,companyname,companycity`.
  - The same aggregation on the Affidavits endpoint (`9ncw-tqjn`).
  - Hiring companies by UBI.
  - A name search for the 14 unlinked establishments: `upper(companyname) like '%EVERGREEN CONCRETE%' OR …`.

  — [WA Intents API](https://data.wa.gov/resource/t9je-9qwa.json); [WA Affidavits API](https://data.wa.gov/resource/9ncw-tqjn.json)
- **Per-establishment outcomes.** Intent-row counts are across all years. — [WA Intents API](https://data.wa.gov/resource/t9je-9qwa.json)
  - **Large, V by UBI (9):** CIRCLE K ENTERPRISES (1, 2025); ROGNLINS (about 1,006, 2004–2026); WALKER CONSTRUCTION (114); JODY MILLER CONSTRUCTION (32); STETNER ELECTRIC (363); TOPLINE COUNTERS (292); CORNERSTONE GENERAL CONTRACTORS (127); A-1 EXTERIOR (1, 2026); PUGET PAVING & CONSTRUCTION (about 1,133).
  - **Large, V by name (4):** VALLEY ELECTRIC CO OF MT VERNON (UBI 600560647, 5 intents in 2019); EVERGREEN CONCRETE CUTTING (UBI 601605667, about 5,250 intents); STYLE CORP (UBI 603145444, 1 intent in 2018); JR G CONCRETE DESIGN (UBI 603262585, 9 intents, 2015–2025).
  - **Large, not found:** ALL ABOUT PROJECTS (no licence link and no filings); CITY OF BELLINGHAM (an awarding agency, not a filer).
  - **Small, V by UBI (3):** CIVILWORKS NW (37, last in 2020); DYNAMIC RFS (1, 2024); CLARK COUNTY PAINTING (17, last in 2022).
  - **Small, V by name (2):** ROYAL ROOFING & SIDING (UBI 602779764, about 168 intents); PENNON CONSTRUCTION (UBI 601994757, 10).
  - **Small, not found:** NORTH BAY BUILDERS, INFRAWEST, INSIGHT ROOFING and SHARK ROLL OFFS (all have a known UBI but no filings); J & I GROUP; ZEDIC; A 1 BUILDERS (worker co-op); EPIC PLUMBING; PREMIUM CONCRETE FINISHING; [personal name].
- **Why the 6 name-found firms had been missed by the app's M1/M2 licence link.** M1 requires the same cleaned name plus zip; M2 requires the same cleaned name plus address key. — [warehouse `ref_ext.licence`](../../data/build/warehouse-20261003T212330Z.duckdb); [62_ref_link.sql](../../ssi/pipeline/sql/62_ref_link.sql); [WA Intents API](https://data.wa.gov/resource/t9je-9qwa.json)
  - **Rename:** UBI 602779764 filed as "ROYAL ROOFING & SIDING INC" (57 intents, 2009–2015) and then as "ROYAL ROOFING INC" (109, 2015–2026). The licence file holds only "ROYAL ROOFING INC", at the same Pasco street address as the OSHA record "ROYAL ROOFING & SIDING INC".
  - **DBA/legal:** OSHA "STYLE CORP" (Woodinville) filed as "Style Corp" under licence SERVPS*893QM. That licence record is named "SERVPRO OF SHORELINE/WOODINVLL" and is at the same street address.
  - **Abbreviation:** the licence names are "VALLEY ELEC CO/MT VERNON INC" and "VALLEY ELEC CO OF MTVERNON INC"; the PW filings and OSHA spell out "Valley Electric Co. of Mt. Vernon". All share the Everett zip.
  - **Zip mismatches:**
    - Evergreen Concrete Cutting: licence PO Box in Sumner 98390; OSHA address in Pacific 98047. PW `companycity` PACIFIC appears on 455 intents.
    - Pennon Construction: licence in Shoreline 98133; OSHA address in Seattle 98115.
    - Jr G Concrete Design: licence in Lakewood 98499; OSHA and PW in Lake Stevens. An earlier UBI, 602965507, "JR. G CONCRETE DESIGN" in Everett, also appears.
- **Existing licence coverage.** 3,952 of 6,945 WA OSHA construction establishments with 2020+ inspections (57%) already have an M1/M2 licence link. The comparable figures are OR 2,191 of 3,490 and CA 1,210 of 9,404. — [warehouse query](../../data/build/warehouse-20261003T212330Z.duckdb)
- **GC relationship data.** Hiring-company rows by UBI for the sample's hits. — [WA Intents API](https://data.wa.gov/resource/t9je-9qwa.json)
  - Puget Paving & Construction appears as a hired sub on 770 intent rows under 234 distinct hiring companies (PAPE & SONS CONSTRUCTION 62, KBH CONSTRUCTION COMPANY 32, …).
  - Topline Counters: 270 rows, 86 hiring companies (HD Supply Facilities Maint 52, WALSH CONSTRUCTION CO/WASH 41, …).
  - Stetner Electric: 132 rows, 75 hiring companies.
  - Rognlins: 73 rows, 45 hiring companies.
  - Rows with no hiring company (prime work, or a blank field) number 363, 22, 231 and 933 respectively.
- **Name variants on filings under one UBI.** Examples: "ROGNLINS INC" (997) and "Rognlin's, Inc." (9); "PUGET PAVING & CONST INC" and "Puget Paving & Construction, Inc."; "TOPLINE COUNTERS LLC" and "Topline Counters". — [WA Intents API](https://data.wa.gov/resource/t9je-9qwa.json)
- **Affidavits** returned the same UBIs, as 16 name/city rows, and add `workstartdate` and `projectcompletiondate`. — [WA Affidavits API](https://data.wa.gov/resource/9ncw-tqjn.json)
- **Site-level test design.** — [warehouse query](../../data/build/warehouse-20261003T212330Z.duckdb)
  - Population: 331 WA OSHA site groups since 2020 with ≥3 establishments inspected at the same site and day; 209 of them have ≥2 licence-linked employers.
  - 10 of the 209 were drawn by `md5(site_group_id)`.
  - One query per group: `$where=(ubi in (<group UBIs>) OR upper(companyname) like '<unlinked names>') AND upper(city) = '<site city>' AND expected_start_dt between '<inspection−3y>' and '<inspection+90d>'`.
- **Site-level test results.** — [WA Intents API](https://data.wa.gov/resource/t9je-9qwa.json)
  - **Full match (1/10).** OSHA inspected LYDIG CONSTRUCTION, INLAND STEEL ERECTORS and FORD CRANE at 11725 1st Ave NE, Seattle, on 2022-02-03. Intents for project 963831, "Northgate Elementary School" (Seattle School District), show:
    - prime LYDIG CONSTRUCTION INC;
    - Inland Steel Erectors hired by LYDIG CONSTRUCTION INC (expected start 2021-11-15);
    - FORD CRANE INC hired by INLAND STEEL ERECTORS INC (2021-11-08).

    That is the whole three-tier chain.
  - **GC-only (1/10).** T W CLARK CONSTRUCTION LLC is prime on "SVFD New Maintenance Facility" (Spokane Valley Fire Department, expected start 2022-03-17) in the city of an OSHA site inspected 2024-06-05. The other two employers do not appear.
  - **No co-filing (8/10).** These were mostly private developments, with employers such as LENNAR, MIRRA HOMES, AVALONBAY and PARAS HOMES. One employer (FINISHING EDGE WASHINGTON) had two other Everett public projects in the window, but not at the inspected site.

### Inferences
- For WA, PW filings add less as a new identity source, since licences already link 57%. Their value is in three other places:
  - an alias and address bridge that recovered 6 of 14 unlinked sample establishments;
  - a GC↔sub relationship graph with UBIs at both ends;
  - a project key that can tie a multi-employer public-works inspection to its GC and tier chain.
- Site-level linking only works for public works. Most WA multi-employer OSHA sites are private, so expect roughly 10–20% of sites to be resolvable. That figure is a guess from 10 groups.
- **Small firms.** Only about a third of small establishments have filings, so small-firm coverage stays weak.

### Gaps
- The SVFD facility's street address was not checked against 10807 E Empire Ave.
- Only city plus a date window was used for site matching. The `contractname` and `projectlocation` text was not geocoded.
- The `qp8s-a5uf` projects table was fetched only for its schema.

## 5. New York: DOS active corporations (`n9v6-gdp6`), name history (`ekwr-p59j`), all filings (`63wc-4exh`), NYS DOL Contractor Registry (`i4jv-zkey`)

### Takeaway
**NY hit rate (n=30):**

- V: 19/30 (63%, 46–78%).
- V+P: 26/30 (87%, 70–95%), the same 87% in both size strata.
- The 4 misses are 2 town or county government departments and 2 bare personal names (sole proprietors are not DOS filers).
- DOS active corporations alone reach about 24/30 (V+P).

**Where verification is limited, and where it is recovered:**

- DOS "process" addresses are often registered agents, which limits address verification.
- DOS name history recovered 3 renames.
- The DOL registry resolved 2 DBA cases.
- No usable assumed-name (DBA) data was found on data.ny.gov.

### Cited Findings
- **Columns returned by DOS active corporations:** `dos_id`, `current_entity_name`, `initial_dos_filing_date`, `county`, `jurisdiction`, `entity_type`, `dos_process_name`, `dos_process_address_1`, `dos_process_city`, `dos_process_state`, `dos_process_zip`. Two OR-batched name queries, each carrying about half of the 31 name patterns (28 non-government establishments), took 6.0 and 9.1 s. — [NY DOS Active Corporations API](https://data.ny.gov/resource/n9v6-gdp6.json)
- **Per-establishment outcomes, NY sample.** — [NY DOS API](https://data.ny.gov/resource/n9v6-gdp6.json); [NYS DOL Contractor Registry API](https://data.ny.gov/resource/i4jv-zkey.json); [NY name history API](https://data.ny.gov/resource/ekwr-p59j.json)
  - **Large, V (11):**
    - AB CONSTRUCTION & ROOFING: DOS "A B CONSTRUCTION & ROOFING, INC.", Broome County; the DOL registry has it at the OSHA street address.
    - BSB CONSTRUCTION.
    - PYRAMID ROOFING & SHEET METAL (filed 1972).
    - WOODCOCK & ARMANI: **DOL only**. Registry business "Comfort Systems USA (Syracuse), Inc." lists dba "Woodcock & Armani Plumbing & Mechanical Contractors; Billone Mechanical Contractors; abj Fire Protection Company" at the same street address.
    - KDL CONSTRUCTION & DEVELOPMENT GROUP.
    - CON-TECH CONSTRUCTION TECHNOLOGY.
    - BONACIO CONSTRUCTION.
    - J ANTHONY ENTERPRISE: "J. ANTHONY ENTERPRISES INC." at the same street.
    - FERGUSON ELECTRIC CONSTRUCTION COMPANY: **found by name history**. dos_id 48608 was "FERGUSON ELECTRIC CONSTRUCTION CO., INC." from 1935 and became "FERGUSON ELECTRIC INC." on 2022-07-15, in Buffalo.
    - MUGHAL GENERAL CONSTRUCTION: "MUGHAL G. CONSTRUCTION INC." at the same street address.
    - CONSTRUCTION ASSOCIATES, LLC.
  - **Large, P (2):**
    - EXYTE U.S., INC.: foreign corporation, process address 28 Liberty St NYC. Its name history runs MEISSNER+WURST U.S. OPERATIONS (1997), then M+W ZANDER U.S. OPERATIONS (2000), then M+W U.S. (2010), then EXYTE U.S. (2018).
    - ARO CONSTRUCTION GROUP: process address is LegalCorp Solutions; Westchester County.
  - **Large, government (2):** SCHENECTADY CO DPW and EASTCHESTER TOWN HWY DEPT.
  - **Small, V (8):** MGC DESIGN AND CONTRACTING (renamed from "MGC CONTRACTING CORP." in 2008); CBL CONSTRUCTION; GMN CONTRACTING 1 (same city); D&H EXCAVATING; MPS PLUMBING & HEATING; VILLNAVE CONSTRUCTION SERVICES; JASONAUT; ALL CITY CONTRACTORS.
  - **Small, P (5):**
    - RAMOS FRAMING: agent address.
    - TURNER CONSTRUCTION COMPANY: dos_id 22401, filed 1902, C T Corporation address; the DOL registry shows the HQ.
    - TETRA STEEL: foreign corporation with an NJ address, Richmond County.
    - JACK G.H. CONSTRUCTION: LegalInc agent, Nassau County.
    - MISS STEEL: **DOL only**. It is a dba of "Sowinski Steel LLC" in Cohoes, about 10 miles from OSHA's Mechanicville.
  - **Small, not found (2):** two personal names.
- **Name history.** 3 of the 26 DOS IDs checked have prior names, namely the Ferguson, Exyte and MGC renames above. One request covered all 26 IDs (`corpid_num in (...)`). — [NY name history API](https://data.ny.gov/resource/ekwr-p59j.json)
- **Assumed names.** — [NY all-filings API](https://data.ny.gov/resource/63wc-4exh.json); [Socrata catalog](https://api.us.socrata.com/api/catalog/v1?domains=data.ny.gov&q=assumed%20name)
  - The `fict_name` search on `63wc-4exh` covered the same 31 name patterns plus "%MISS STEEL%" and "%WOODCOCK%". It returned 9 rows, all for one irrelevant entity: "FERGUSON ELECTRIC COMPANY, INCORPORATED", operating under the fictitious name "FERGUSON ELECTRIC OF PLAINVIEW, CONNECTICUT" (an Application of Authority, Tompkins County).
  - The `63wc-4exh` columns are `corpid_num`, `corp_name`, `fict_name`, `documenttype`, `date_filed` and `cnty_prin_ofc`, among others.
  - A data.ny.gov catalog search for "assumed name" found no assumed-name dataset. The only related result was `k4vb-judh`, "Daily Corporation and Other Entity Filing Data".
- **DOL Contractor Registry.** 10 rows matched, carrying `dba_name` and `business_officers` (officers populated on 1 row). The flag `business_has_final_determination_safety_standard_violations` is "Yes" for Bonacio Construction, D&H Excavating and Villnave Construction Services. — [NYS DOL Contractor Registry API](https://data.ny.gov/resource/i4jv-zkey.json)
- **Corporate families exposed by name search.** — [NY DOS API](https://data.ny.gov/resource/n9v6-gdp6.json)
  - Ferguson Electric: Holdings Corp., Service Co., a Foundation, and a JV with E-J Electric, around 321 Ellicott St, Buffalo.
  - Bonacio: Real Estate L.L.C. and Referrals LLC.
  - Villnave: Realty Corp. and Transportation Services.

### Inferences
- For NY-registered corporations and LLCs, DOS is the strongest per-establishment source tested. Two extras are cheap to add:
  - **name history**, whose `corpid_num` lookups are cheap and catch renames OSHA records carry for years;
  - **the DOL registry**, the only NY source here that maps a trade name to a legal entity.
- The DOS "process" address is a weak verifier, because registered agents and C T Corporation addresses are common. Matching should lean on name distinctiveness plus county.

### Gaps
- Inactive and dissolved entities are not in `n9v6-gdp6`.
- DOS active corporations carry no officer names.
- NY county-clerk assumed-name certificates, where sole-proprietor DBAs live, are not on data.ny.gov as far as this probe could find.

## 6. Texas Comptroller: Active Franchise Taxpayers (`9cir-efmm`) and Active Sales Tax Permit Holders (`jrea-zgmq`)

### Takeaway
**TX hit rate (n=30):**

- V: 11/30 (37%, 22–54%).
- V+P: 18/30 (60%, 42–75%).
- Large firms: 10/15 (V+P).
- Small firms: 8/15 (V+P).
- Population-weighted: about 34% (V) and 55% (V+P).

The sales-tax **outlet name** exposed DBA↔legal pairs, including one sole proprietor's trade name, and branch addresses. All 6 personal-name establishments in the TX sample were missed.

### Cited Findings
- **Fields.** — [TX franchise API](https://data.texas.gov/resource/9cir-efmm.json); [TX sales tax API](https://data.texas.gov/resource/jrea-zgmq.json)
  - Franchise: `taxpayer_number`, `taxpayer_name`, taxpayer address, `taxpayer_organizational_type`, `secretary_of_state_sos_or_coa_file_number`, `sos_charter_date`, `sos_status_code`, `right_to_transact_business_code`.
  - Sales tax: taxpayer fields plus `outlet_name`, outlet address, `outlet_naics_code` and `outlet_permit_issue_date`.
  - Each source took 2 OR-batched requests, at 3–6 s each. Personal names were restricted to the OSHA city in the sales-tax query.
- **Per-establishment outcomes, TX sample.** — [TX franchise API](https://data.texas.gov/resource/9cir-efmm.json); [TX sales tax API](https://data.texas.gov/resource/jrea-zgmq.json)
  - **Large, V (6):**
    - EPPX CONSTRUCTION: "EPPX CONSTRUCTION, L.L.C.", El Paso; the sales-tax outlet is "EPPX CONSTRUCTION".
    - TEXCON GENERAL CONTRACTORS: a sales-tax **outlet named "TEXCON GENERAL CONTRACTORS" belongs to taxpayer "CIVIL CONSTRUCTORS, INC."**, whose taxpayer address is the OSHA PO box in Kurten.
    - JORDAN FOSTER CONSTRUCTION: same street address. It has outlets in Houston, Pflugerville, San Antonio and Dallas, one spelled "JORDON FOSTER CONSTRUCTION, LLC", and a sibling, JORDAN FOSTER PROPERTIES, at the same address.
    - AZALI INVESTMENTS: same PO box, shared by about 10 "AZALI …" entities including itself.
    - PRUNEDA CONSTRUCTION: "PRUNEDA CONSTRUCTION, LLC" against OSHA "…, INC.", same zip.
    - ANTEX ROOFING: chartered 1975.
  - **Large, P (4):**
    - DAN WILLIAMS COMPANY: Austin HQ, as in FMCSA and USAspending.
    - MSF ELECTRIC: now in Sugar Land, next to Stafford; the 2020 SBA loan record was at the OSHA address.
    - GALINDO & BOYD ARAHED: Mesquite HQ, with 5 sibling Galindo & Boyd entities.
    - KZJV LLC: a JV with a San Antonio PO box.
  - **Large, A (2):**
    - INDUSTRIAL SERVICE SOLUTIONS: 4 same-name entities, none in Pasadena TX.
    - DLH CONSTRUCTION: a Houston LLC chartered 2025-09-10.
  - **Large, not found (3):** HARVEY-CLEARY BUILDERS (only "HARVEY CLEARY LAKE AUSTIN" entities), BEHEMOTH INDUSTRIES, and one personal name.
  - **Small, V (5):**
    - TURNKEY CONSTRUCTION COMPANY I, LP.
    - J-M AMERICAN CANOPIES: **a sales-tax outlet "J M AMERICAN CANOPIES" whose taxpayer is the owner's personal name**, at the same street.
    - VILLAGOMEZ JR. PAINTING CO: same city.
    - FISK ELECTRIC COMPANY: chartered 1931, with outlets in Austin, Carrollton and San Antonio.
    - ETECH TECHNOLOGIES.
  - **Small, P (3):** ANT FORCE CONSTRUCTION GROUP (Rosenberg), JULIE RIVERS CONSTRUCTION (Brookshire, next to Katy), and IRONTEK METAL WORKS (San Marcos).
  - **Small, not found (7):** SOUTHWEST CONSTRUCTION SERVICES, AD METAL ERECTORS, and five personal names.

### Inferences
- **Two complementary files.** The franchise file covers formal entities. The sales-tax file adds trade names (outlets) and some sole proprietors. Neither covers labour-only or personal-name subs well; 0 of 6 were found even with a city filter.
- **Shared mailing addresses** create clusters of sibling entities (AZALI, Galindo & Boyd). Matching should treat these as corporate families, not as one entity.

### Gaps
- The meaning of `sos_status_code` "R" (seen on EPPX, Villagomez and Irontek) was not checked.
- No officer data is in either file.
- Texas permit rules for construction services were not researched.

## 7. Overture Maps Places (optional probe)

### Takeaway
Not run. Reading Overture's parquet from DuckDB requires the `httpfs` extension, which is not installed in the project's DuckDB. Installing it means downloading an extension binary, which I did not do without explicit approval from the user. By that point 180 of the ~200-request budget had also been used.

### Cited Findings
- `duckdb_extensions()` in the project environment (duckdb 1.4.5) reports `httpfs` installed=False and `spatial` installed=False. — [local check of the project environment](../../pyproject.toml)

### Inferences
- With approval, the Nashville-bbox probe is still feasible. It would need `INSTALL httpfs` (a one-off binary download from DuckDB's extension repository) plus bbox-filtered parquet reads.

### Gaps
- No Overture coverage numbers were obtained.

## 8. Which known failure types do hits resolve, and what should be ingested first?

### Takeaway
Most hits in every source are exact name matches after the app's cleaning. They confirm identities but do not by themselves fix the hard cases.

**What each source resolves:**

- **DBA vs legal name:** resolved mainly by the NY DOL registry, TX sales-tax outlets, FMCSA `dba_name`, and WA PW filings tied to a licence.
- **Renames:** resolved by NY DOS name history and WA UBI continuity.
- **Descriptor variants:** resolved incidentally by every source.
- **Sole proprietors with common names:** essentially unresolved. Only 1 of 14 personal-name establishments was found anywhere.

**Coverage per establishment**, best first: NY DOS (87% V+P), TX Comptroller (60%), WA PW (60%, but mostly large firms), USAspending (48%, mostly PPP records), FMCSA (33%).

### Cited Findings
- **Hits exposing a second name (DBA, trade, legal or prior name) or bridging a missed link.** — sources as cited in §2–§6
  - **FMCSA:** 4 of 20 V+P hits ("OBI"; "KRB CONSTRUCTION" for a personal-name proprietor; "RAIN CITY EXTERIORS"; "VEC INC" found by address).
  - **USAspending:** 0 DBAs. Only formatting `alternate_names`, plus a plural variant ("GLOBAL STEEL ERECTORS").
  - **WA PW:** 4 of 18.
    - Royal Roofing & Siding to Royal Roofing Inc (same UBI).
    - Style Corp to the Servpro licence (trade name).
    - "VALLEY ELEC CO OF MTVERNON".
    - Jr G Concrete Design's predecessor UBI.

    Also 2 zip-mismatch bridges (Evergreen, Pennon).
  - **NY:** 5 of 26. Two DOL DBAs (Woodcock & Armani to Comfort Systems USA (Syracuse); Miss Steel to Sowinski Steel LLC) and three DOS renames (Ferguson Electric, Exyte/M+W, MGC).
  - **TX:** 2 of 18 (Texcon to Civil Constructors, Inc.; J-M American Canopies to the owner's personal name).
- **Descriptor and legal-form variants crossed by hits.** — sources as cited in §2–§6
  - "<personal name>" to "<personal name> CONSTRUCTION" (FMCSA).
  - "SCHENECTADY CO DPW" to "SCHENECTADY COUNTY DPW" (FMCSA).
  - "GLOBAL STEEL ERECTOR" to "…ERECTORS" (USAspending).
  - "MUGHAL GENERAL CONSTRUCTION" to "MUGHAL G. CONSTRUCTION INC." (NY DOS, same street address).
  - "J ANTHONY ENTERPRISE" to "J. ANTHONY ENTERPRISES INC." (NY).
  - "PRUNEDA CONSTRUCTION, INC." to "…, LLC" (TX).
  - "MIDSOUTH STEEL INC." to "MIDSOUTH STEEL, LLC" (USAspending).
- **Sole proprietors with personal names: 14 in the samples.** Only one, a Los Angeles contractor, was found: in FMCSA as "<name> CONSTRUCTION", dba "KRB CONSTRUCTION", and in USAspending through 5 SBA loans. Common names produced same-name false candidates in other cities:
  - a same-name inactive carrier in Parma OH for a Whitehall OH establishment (FMCSA);
  - a namesake in Chicago for a Garland TX establishment (USAspending);
  - namesakes in AZ and MS for "PAUL RUSSELL" (USAspending).

  — [FMCSA API](https://data.transportation.gov/resource/az4n-8mr2.json); [USAspending recipient API](https://api.usaspending.gov/api/v2/recipient/); [TX sales tax API](https://data.texas.gov/resource/jrea-zgmq.json)
- **FMCSA and USAspending together** on the same 60: verified in at least one source 27/60 (45%), and with probables 33/60 (55%). By size, large 19/30 and small 8/30 are verified in at least one. — computed from the §3 table
- **Summary of hit rates (V / V+P, with 95% CI on V+P).** — §2–§6

  | Source | Sample | V | V+P | Large V+P | Small V+P | Pop-weighted V+P |
  |---|---|---|---|---|---|---|
  | NY DOS + name history + DOL registry | NY 30 | 63% | 87% (70–95) | 87% | 87% | ~87% |
  | TX Comptroller franchise + sales tax | TX 30 | 37% | 60% (42–75) | 67% | 53% | ~55% |
  | WA L&I PW intents | WA 30 | 60% | 60% (42–75) | 87% | 33% | ~37% |
  | USAspending (all record types) | 10-state 60 | 35% | 48% (36–61) | 60% | 37% | ~41% |
  | USAspending (UEI-bearing only) | 10-state 60 | 12% | 17% (9–28) | 30% | 3% | ~8% |
  | USAspending subawards | 10-state 60 | 5% | 5% (2–14) | 10% | 0% | ~2% |
  | FMCSA Company Census | 10-state 60 | 27% | 33% (23–46) | 50% | 17% | ~23% |

### Inferences
- **Suggested ingestion priority.** These are inferences from small samples.
  1. **NY DOS active corporations plus name history**, keyed by DOS ID. Add the **NYS DOL Contractor Registry**, which is small (about 15k rows) and is the one NY source with DBAs, officers and a safety-violation flag. Coverage is highest, and the renames and DBAs fix real misses. NY only.
  2. **TX Comptroller franchise plus sales-tax outlets.** Good entity coverage, plus trade names and branch addresses. TX only.
  3. **WA L&I PW Intents/Affidavits.** Use them as a bridge and relationship layer on top of the licence file the app already ingests. They recovered 6 of 14 unlinked sample firms, give GC↔sub edges, and can key some public-works inspection sites. Small-firm coverage is weak.
  4. **FMCSA Company Census.** National and a single bulk file, with officers and physical addresses. Mid coverage, concentrated in large and fleet-owning firms.
  5. **USAspending.** Through the API it is mostly a PPP borrower list. If the team wants that breadth, SBA's PPP bulk files are the cheaper route (not probed here). The UEI and subaward data is valuable only for federal-work subs (about 5%).
- **None of these sources fix personal-name sole proprietors.** Those still need GC-supplied identifiers or licence numbers, as noted in earlier research.
- **Shared-address families need corporate-family handling.** In TX and NY, matching to a whole sibling cluster (AZALI, Galindo & Boyd, Ferguson Electric) is needed so that shared addresses do not trigger false merges.

### Gaps
- Sample sizes cannot separate state effects from source effects. The NY, TX and WA rates come from different states than the multi-state FMCSA and USAspending rates, so cross-source comparisons are confounded by state.
- No timing tests of bulk ingestion.
- No precision estimate for automated matching. These are human-judged coverage rates, not the precision or recall of an automated matcher.
