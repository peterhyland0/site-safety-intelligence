# US federal and national public datasets for matching subcontractors to OSHA inspection records

Scope note: researched on 2026-10-04. Items marked "verified live" were checked this session against the live endpoint (HTTP HEAD, a range read of the zip's first CSV chunk, or an API call). The CSV headers quoted below come from range reads of each file's first 256 KB; no full files were downloaded. Anything taken only from secondary or older sources is flagged.

---

## 1. Other DOL datasets (WHD, MSHA, OFCCP, EBSA, VETS, OSHA SIR, ITA 300/301, SVEP, establishment search): what they carry, and does any share an employer ID with OSHA?

### Takeaway
No DOL enforcement dataset shares an employer identifier with OSHA inspections. Two are still valuable. The **WHD Enforcement** file carries a *trade name* and a *legal name* side by side for each case, so it can serve as a DBA-to-legal-name dictionary with addresses and NAICS. The **OSHA ITA case-detail (300/301) data** carries `ein`, `company_name` and `establishment_name`. Both download in bulk without a key from the same DOL data catalog the project already uses. The SVEP public log is currently offline.

### Cited Findings

**DOL Open Data Portal: catalog and access (verified live)**
- The catalog API `https://apiprod.dol.gov/v4/datasets` (5 pages, 45 datasets) lists the following. OSHA: Inspection, Violation, Accident, Accident Injury, Accident Abstract, Related Activity, Emphasis Codes, Violation Event, Optional Code Info, Violation Gen Duty Std, all "Daily". WHD: "Enforcement" (Quarterly). MSHA: Contractor Name ID Lookup, Contractor History at Mines, Controller History, Operator History at Mines, Address of Records – Mines, Mines, Inspection, Violation, Assessed Violations and others, all "Weekly". VETS: "VETS 4212 Federal Contractor Reporting" (Weekly). EBSA: "OCATS" (Quarterly). ETA: Apprenticeship, UI claims, OTAA Petition. **No OFCCP dataset, no OSHA Severe Injury Report and no OSHA ITA dataset appear in the current catalog.** — [DOL API v4 dataset catalog](https://apiprod.dol.gov/v4/datasets)
- The row-level API (`https://apiprod.dol.gov/v4/get/{AGENCY}/{dataset}/json`) returns HTTP 401 without a key: "The API key is either incorrect or missing from your query." — [DOL API v4 endpoint (live test)](https://apiprod.dol.gov/v4/get/WHD/enforcement/json)
- The API key is free and is issued immediately on registration at dataportal.dol.gov/registration. `/v4/get/` needs the key as a query parameter, not a header. This is a secondary source. — [pipeworx-io/mcp-dol-whd README](https://github.com/pipeworx-io/mcp-dol-whd)
- **Bulk "complete dataset" zips need no key.** They follow the same URL pattern the project already uses for OSHA, `https://data.dol.gov/data-catalog/{AGENCY}/{api_url}/{AGENCY}_{api_url}.zip`. HTTP HEAD results on 2026-10-04:
  - `WHD/enforcement/WHD_enforcement.zip`: 199,815,438 bytes, last-modified 2026-09-28
  - `VETS/4212/VETS_4212.zip`: 1,387,713,150 bytes, 2026-10-03
  - `MSHA/contractor_name_id_lookup/...zip`: 4,922,599 bytes
  - `MSHA/controller_history/...zip`: 9,092,251 bytes
  - `MSHA/address_of_records_mines/...zip`: 19,279,418 bytes
  - `EBSA/ocats/EBSA_ocats.zip`: 2,143,785 bytes
  - For comparison, `OSHA/inspection/OSHA_inspection.zip`: 1,445,543,317 bytes, 2026-10-04

  Each zip holds chunked CSVs (`LOAD00000001-<timestamp>_chunk_N.csv`). — [data.dol.gov WHD zip](https://data.dol.gov/data-catalog/WHD/enforcement/WHD_enforcement.zip); [VETS zip](https://data.dol.gov/data-catalog/VETS/4212/VETS_4212.zip)

**WHD Enforcement ("WHISARD" compliance actions) (verified live)**
- Description: "all concluded WHD compliance actions since FY 2005 … whether any violations were found and the back wage amount, number of employees due back wages, and civil money penalties assessed". Case open and close dates are not included. Refresh is quarterly (catalog id 10362). — [DOL API v4 dataset catalog](https://apiprod.dol.gov/v4/datasets)
- Exact CSV header:
  - Identity and location: `CASE_ID, TRADE_NM, LEGAL_NAME, STREET_ADDR_1_TXT, CTY_NM, ST_CD, ZIP_CD, NAIC_CD, NAICS_CODE_DESCRIPTION`
  - Case totals: `CASE_VIOLTN_CNT, CMP_ASSD, EE_VIOLTD_CNT, BW_ATP_AMT, EE_ATP_CNT, FINDINGS_START_DATE, FINDINGS_END_DATE, FLSA_REPEAT_VIOLATOR`
  - Per-statute blocks, including Davis-Bacon `DBRA_VIOLTN_CNT, DBRA_BW_ATP_AMT, DBRA_EE_ATP_CNT`, `CWHSSA_*`, `H2B_VIOLTN_CNT, H2B_BW_ATP_AMT, H2B_EE_ATP_CNT`, `OSHA_VIOLTN_CNT, OSHA_CMP_ASSD_AMT`, `SCA_*` and `FLSA_*`
  - `LOAD_DT`

  The file has no EIN and no OSHA identifier. — [WHD_enforcement.zip (header read via range request)](https://data.dol.gov/data-catalog/WHD/enforcement/WHD_enforcement.zip)
- Sample rows show the trade-name/legal-name pairing, which is the useful part:
  - TRADE_NM "Healthcare Services Group at Westwood Center" with LEGAL_NAME "Healthcare Services Group, Inc."
  - TRADE_NM "Reliant Energy" with LEGAL_NAME "Reliant Energy Retail Services, LLC"
  - TRADE_NM "Central Avenue Bakery" with LEGAL_NAME "Central Avenue Bakery, Inc."

  The first uncompressed chunk is 27,257,778 bytes. — [WHD_enforcement.zip](https://data.dol.gov/data-catalog/WHD/enforcement/WHD_enforcement.zip)
- A third-party mirror describes each row as identifying "the employer by trade and legal name, address, NAICS industry …". — [labordata.bunkum.us whisard](https://labordata.bunkum.us/whisard)

**VETS-4212 Federal Contractor Reporting (verified live)**
- Annual veteran-employment reports from federal contractors and subcontractors under 38 U.S.C. 4212. Refreshed weekly (catalog id 10324). — [DOL API v4 dataset catalog](https://apiprod.dol.gov/v4/datasets)
- Header:
  - Report: `ReportID, ReportType, FilingCycle, EndingPeriod, FormType` (values include "Single Establishment" and "Multiple Establishment - Headquarters") and `OrgType` ("Prime Contractor" / "Subcontractor")
  - Company: `CoName, CoAddress, CoCity, CoCounty, CoState, CoZip`
  - Second location: `HlName, HlAddress, HlCity, HlCounty, HlState, HlZip`
  - Other: `NAICS, MSC, MaxNumber, MinNumber, CreatedOn`, plus employee counts by job category, including "CRAFT WORKERS" and "LABORERS/HELPERS"

  There is no EIN or UEI. The zip is 1.39 GB. — [VETS_4212.zip](https://data.dol.gov/data-catalog/VETS/4212/VETS_4212.zip)

**MSHA (verified live)**
- Contractor Name ID Lookup has columns `CNTCTR_ID, CNTCTR_NM, LOAD_DT` (e.g. "A5198, matts tire service inc"). Controller History has `OPER_ID, CTRLR_ID, CTRLR_START_DT, CTRLR_NM, CTRLR_END_DT, OPER_NM`, a dated operator-to-controller (parent) history. — [MSHA contractor zip](https://data.dol.gov/data-catalog/MSHA/contractor_name_id_lookup/MSHA_contractor_name_id_lookup.zip); [MSHA controller zip](https://data.dol.gov/data-catalog/MSHA/controller_history/MSHA_controller_history.zip)

**OSHA ITA Form 300A summaries and Form 300/301 case detail (2023+)**
- 300A summary data covers 2016–2025. The 2025 file is `/sites/default/files/ITA_300A_Summary_Data_2025_through_03-15-2026_v2.csv`.
- Case detail (Forms 300/301) started with 2023:
  - 2025: `/sites/default/largefiles/ITA_Case_Detail_Data_2025_through_3-15-2026.csv`
  - 2024: `/sites/default/files/ITA_Case_Detail_Data_2024_through_12-31-2025.zip`
  - 2023: `/sites/default/largefiles/ITA_Case_Detail_Data_2023_through_12-31-2023OIICS.zip`

  Summary and case files link on `establishment_id`. No login is mentioned. — [OSHA Establishment-Specific Injury and Illness Data](https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data)
- The 2026 case-detail data dictionary defines `establishment_id`, `establishment_name`, **`ein`** ("Employer Identification Number (EIN), also known as …"), **`company_name`** ("The name of the company that owns the …"), `street_address`, `zip_code`, `naics_code`, `case_number` and `job_description`. — [case_detail_data_dictionary_2026.pdf](https://www.osha.gov/sites/default/files/case_detail_data_dictionary_2026.pdf)
- osha.gov returns HTTP 403 to non-browser clients such as curl. That fits the project's current practice of downloading ITA files by hand in a browser. — [OSHA SIR zip (403 to curl)](https://www.osha.gov/sites/default/files/January2015toNovember2025.zip)

**OSHA Severe Injury Reports (SIR)**
- Coverage is 2015-01-01 through 2025-11-30, for incidents under federal OSHA jurisdiction only; state-plan states are excluded. Download: `https://www.osha.gov/sites/default/files/January2015toNovember2025.zip`. Fields include establishment name and address, event date, NAICS, city and state, narrative, and amputation and hospitalization flags. The page says only "updated periodically". — [OSHA Severe Injury Reports](https://www.osha.gov/severe-injury-reports)

**OSHA SVEP log**
- osha.gov/enforcement/svep currently says: "The public logs have been temporarily removed while this program is being updated." — [OSHA SVEP page](https://www.osha.gov/enforcement/svep)
- When the log was public it listed more than 900 employers, most of them in construction (as of 2024-09-01). This is a secondary source. — [HCH Lawyers blog](https://www.hchlawyers.com/blog/2024/october/osha-severe-violator-enforcement-program-5-thing/)

**EBSA**
- OCATS (2.1 MB zip) is the only EBSA dataset on the DOL portal. EBSA's high-value dataset for this project is Form 5500, covered in section 10. — [DOL API v4 dataset catalog](https://apiprod.dol.gov/v4/datasets)

### Inferences
- **The answer on a shared ID is no.**
  - OSHA_inspection has no EIN.
  - WHD uses its own `CASE_ID`; MSHA its own contractor and controller IDs; VETS its own `ReportID`.
  - ITA's `establishment_id` is an ITA-system ID, not an OSHA inspection or establishment key.
  - Every DOL-to-OSHA link has to go through name plus address. The only EIN bridges are ITA, the OFLC H-2B/LCA files (section 10) and Form 5500 (section 10).
- **WHD is the best DOL source for DBA-vs-legal-name pairs.**
  - Construction is a heavily investigated WHD sector (Davis-Bacon and FLSA).
  - `TRADE_NM` and `LEGAL_NAME` plus street, city and ZIP let one alias pair be indexed per case. Example: "XYZ Drywall" with legal name "XYZ Interiors LLC".
  - It joins to OSHA on normalised name plus ZIP or address, the same way the project links ITA today.
  - Ingest is cheap: a 200 MB zip, the same URL pattern, no key.
- **ITA case detail (2023+) adds `company_name` (the owning company) next to `establishment_name` and `ein`.** That supports corporate-family linking: establishments of one company sharing an EIN or company name. It is likely the same EIN coverage the project already gets from 300A, but at case level.
- **VETS-4212 offers prime/sub labels and an address list for federal-contract construction firms only.** Low incremental value; no ID.
- **MSHA Controller History is a real parent-company history**, but it covers mine operators. Its relevance to building and heavy-civil subcontractors is marginal.
- **WHD's `OSHA_VIOLTN_CNT` columns are not linked to OSHA inspections.** They most likely reflect OSHA field-sanitation and temporary-labor-camp standards that WHD enforces in agriculture; this was not verified.
- **OSHA's establishment search** (osha.gov/ords/imis/establishment.html) is a UI over the same inspection data. It was not separately verified this session and should add no identifiers.

### Gaps
- Row count of WHD Enforcement and its NAICS 23 share. The full file was not downloaded; the API needs a key.
- Whether the SIR CSV carries an OSHA inspection or activity number column linking to OSHA_inspection. The osha.gov zip blocks scripted access; check by hand in a browser.
- The current applicability threshold for ITA 300/301 submission (100+ employees in designated industries under the 2023 rule) and whether NAICS 23 is included. Not verified this session.
- OFCCP: no compliance-evaluation dataset appears in the 2026 DOL catalog, and its current status was not verified.
- Whether the DOL portal states a formal licence or terms of use was not found. US federal works are generally public domain, but this was not confirmed on the portal.

---

## 2. SAM.gov (entity extract V2, entity API, exclusions): is a free account enough, and which fields and identifiers are public?

### Takeaway
A free SAM.gov individual account (Login.gov) plus its personal API key is enough to download the full **public monthly entity extract**: 142 columns covering UEI, CAGE, legal name, DBA, division name, physical and mailing address, NAICS and SBA certifications. The earlier assumption that SAM.gov needs a paid key is wrong. The extract has no parent/owner columns. Parent hierarchy (`immediateParentEntity` / `ultimateParentEntity`) is FOUO and federal-only. The Entity API's `integrityInformation.corporateRelationships` (`highestOwner`, `immediateOwner`, `predecessorsList`) is documented as Public. TIN/EIN is never available to non-federal users. The cost is coverage: SAM.gov only holds firms that registered for federal awards.

### Cited Findings
- **Monthly public extract**
  - Files: `SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP` (ASCII) and `SAM_PUBLIC_UTF-8_MONTHLY_V2_YYYYMMDD.ZIP`, produced on the first Sunday of each month and available after 7 AM ET. They contain "active entities plus those expired within the last 6 months".
  - Endpoint: `https://api.sam.gov/data-services/v1/extracts?api_key={API_KEY}&fileName=SAM_PUBLIC_MONTHLY_V2_20220403.ZIP`.
  - Allowed account types: "Non-Federal or Federal individual accounts with API key" or system accounts with "Read Public".

  — [open.gsa.gov SAM Entity/Exclusions Extracts API](https://open.gsa.gov/api/sam-entity-extracts-api/)
- **Rate limits per API key**

  | Account type | Daily limit |
  |---|---|
  | Non-federal user, no SAM.gov role | 10 requests/day |
  | Non-federal user, with a role | 1,000 requests/day |
  | Federal user | 1,000 requests/day |
  | Non-federal system account | 1,000 requests/day |
  | Federal system account | 10,000 requests/day |

  — [open.gsa.gov Entity Management API](https://open.gsa.gov/api/entity-api/)
- **Public extract V2 layout: 142 columns (verified from GSA's "SAM Master Extract Mapping v6.0 Public File V2 Layout.xlsx")**
  - 1 UNIQUE ENTITY ID
  - 4 CAGE CODE
  - 7 PURPOSE OF REGISTRATION
  - 8 INITIAL REGISTRATION DATE
  - 9 REGISTRATION EXPIRATION DATE
  - 10 LAST UPDATE DATE
  - 11 ACTIVATION DATE
  - 12 LEGAL BUSINESS NAME
  - 13 DBA NAME
  - 14 **ENTITY DIVISION NAME**
  - 15 ENTITY DIVISION NUMBER
  - 16–23 PHYSICAL ADDRESS (line 1/2, city, state, ZIP, ZIP+4, country, congressional district)
  - 24 D&B OPEN DATA FLAG
  - 25 ENTITY START DATE
  - 27 ENTITY URL
  - 28 ENTITY STRUCTURE (e.g. 2J Sole Proprietorship, 2K Partnership/LLP, 2L Corporate Entity)
  - 29 STATE OF INCORPORATION
  - 32 BUS TYPE STRING
  - 33 PRIMARY NAICS
  - 35 NAICS CODE STRING
  - 40–46 MAILING ADDRESS
  - 47–112 government-business, past-performance and electronic-business POC names and addresses
  - 116 EXCLUSION STATUS FLAG
  - 118 SBA BUSINESS TYPES STRING (8(a), HUBZone with expiry dates)
  - 119 NO PUBLIC DISPLAY FLAG
  - 122 ENTITY EVS SOURCE

  **There are no immediate-owner, highest-owner, parent or predecessor columns, and no TIN.** — [SAM Public V2 layout xlsx](https://open.gsa.gov/api/sam-entity-extracts-api/v1/SAM%20Master%20Extract%20Mapping%20v6.0%20Public%20File%20V2%20Layout.xlsx)
- **Entity API sensitivity tiers**
  - **Public**: "name, UEI, registration details, physical and mailing addresses, business types, PSC, NAICS". Fields include `ueiSAM, cageCode, legalBusinessName, dbaName, physicalAddress, mailingAddress, entityStructureCode, stateOfIncorporationCode`.
  - **FOUO** (requires a Federal System Account with "Read FOUO"): "Hierarchy …", i.e. `immediateParentEntity`, `ultimateParentEntity`, `intermediateParentEntities` (`domesticParent`, `hqParent`), plus POC emails and phones.
  - **Sensitive**: "Banking information and SSN/TIN/EIN" (`tinInformation.taxpayerIdentificationNumber`), federal "Read Sensitive" only.

  — [open.gsa.gov Entity Management API](https://open.gsa.gov/api/entity-api/)
- **`integrityInformation` subsections are documented as "Sensitivity Level: Public"**, including `corporateRelationships` → `highestOwner`, `immediateOwner` and `predecessorsList` (legalBusinessName, CAGE and related fields), `proceedingsData`, and FAPIIS `responsibilityInformationList`. They are retrieved with `includeSections=integrityInformation`. — [open.gsa.gov Entity Management API](https://open.gsa.gov/api/entity-api/)
- **API extract mode**: `format=csv|json` returns an asynchronous download link, up to **1,000,000 records**; synchronous paging stops at 10,000 records. `samRegistered=No` returns "ID Assigned" (UEI-only, unregistered) entities; NPDY unregistered entities need a federal role. — [open.gsa.gov Entity Management API](https://open.gsa.gov/api/entity-api/)
- **Exclusions**
  - API: `https://api.sam.gov/entity-information/v4/exclusions?api_key=…` returns name, UEI, CAGE, excluding agency, classification (Individual/Firm/…), exclusion type and program, dates, addresses, cross-references and additional locations. Same rate limits as above; CSV/JSON extract up to 1M records. — [open.gsa.gov Exclusions API](https://open.gsa.gov/api/exclusions-api/)
  - Daily file: `SAM_Exclusions_Public_Extract_V2_YYDDD.ZIP`. The extracts-API docs say a personal account API key is needed. — [open.gsa.gov SAM Extracts API](https://open.gsa.gov/api/sam-entity-extracts-api/)
  - **Conflict on access**: the data.gov catalog entry and third-party guides say public exclusions files can be downloaded from SAM.gov Data Services without login. — [data.gov SAM Public Extract – Exclusions](https://catalog.data.gov/dataset/system-for-award-management-sam-public-extract-exclusions); [GSA Open IAE guide](http://briangilmangsa.github.io/openIAE/developer_resources/Using_SAM_data_extracts/)
- The public extract endpoint returned no data without a key in a live test (`/entity-information/v4/entities` without `api_key`). — [api.sam.gov (live test)](https://api.sam.gov/entity-information/v4/entities)

### Inferences
- **Corrects the earlier assumption**: SAM.gov needs a *free* account and API key, not a paid one. Ten requests a day is ample for one monthly bulk-file download.
- **Value for matching**
  - The UEI is a stable ID.
  - LEGAL BUSINESS NAME + DBA NAME + **ENTITY DIVISION NAME** directly address the DBA problem and the "city name used as division name" problem, for example a builder registering "D.R. Horton – Dallas division".
  - The extract has both physical and mailing addresses, which mirrors OSHA's site and mailing fields.
- **Owner and predecessor data** may be reachable through the public Entity API (`integrityInformation`) under a 1,000-requests-a-day key, i.e. a non-federal user with a role. These are self-reported FAR 52.204-17 ownership answers.
  - `highestOwner` / `immediateOwner` would help with corporate families.
  - `predecessorsList` would help detect renames and acquisitions.

  Fetch per-UEI only for candidate matches, or use the 1M-record extract mode with `includeSections`. Test this before relying on it.
- **Coverage bias**: SAM.gov holds only firms that sought federal contracts or grants. Many small residential subcontractors will be absent, while mid-size commercial and heavy-civil subs often register.
- **How to obtain a SAM.gov role** was not documented in the sources checked. It is usually obtained by being associated with a registered entity.

### Gaps
- The share of NAICS 23 entities in the monthly extract and the file size were not obtained, because downloading requires a key.
- Whether `integrityInformation.corporateRelationships` is actually returned to a non-federal public key was not tested; there is a documentation-vs-practice risk.
- SAM.gov terms of use (e.g. any marketing-use restriction) were not reviewed.
- Whether DOL Davis-Bacon debarments appear as SAM exclusions was not confirmed from a primary source (see section 9).

---

## 3. USAspending.gov / FPDS / subaward (former FSRS) data: recipient UEI, parent and DBA names for federal construction primes and subs; bulk without an account?

### Takeaway
USAspending needs **no account or key** for its API or bulk files (verified live).
- Prime-award files carry `recipient_uei`, `recipient_name`, `recipient_doing_business_as_name`, `recipient_parent_uei` / `recipient_parent_name` and an address.
- Subaward files carry `subawardee_uei`, `subawardee_name`, `subawardee_dba_name`, `subawardee_parent_uei` and an address. These are the only free federal records that name construction **subcontractors** with a UEI and a parent.
- The recipient-profile API returns an `alternate_names` list per UEI, which is a free name-variant dictionary.

### Cited Findings
- **Live API test (no key)**:
  - `POST https://api.usaspending.gov/api/v2/search/spending_by_award/` with keyword "Brasfield" returned "BRASFIELD & GORRIE LLC", UEI `TWVGJRMK6Z78`.
  - It also returned a joint venture: "CBY DESIGN BUILDERS A JOINT VENTURE OF CDM, BRASFIELD & GORRIE, AND YATES CONSTRUCTION", UEI `UYMZTL4B2MF7`.

  — [USAspending API (live)](https://api.usaspending.gov/api/v2/search/spending_by_award/)
- **Recipient profile** `GET https://api.usaspending.gov/api/v2/recipient/a4499a6f-2139-8774-afa2-247720ff681c-C/` returned:
  - name "BRASFIELD & GORRIE LLC"
  - `alternate_names`: "BRASFIELD & GORRIE  L.L.C.", "BRASFIELD & GORRIE, L.L.C.", "BRASFIELD AND GORRIE LIMITED LIABILITY COMPANY"
  - uei TWVGJRMK6Z78 and legacy DUNS 005074302
  - parent_uei TWVGJRMK6Z78
  - location 3021 7TH AVE S, Birmingham AL 35233-3502
  - business_types including "limited_liability_corporation"

  — [USAspending recipient API (live)](https://api.usaspending.gov/api/v2/recipient/a4499a6f-2139-8774-afa2-247720ff681c-C/)
- **Data dictionary column names (verified from the API)**
  - Prime awards: `recipient_uei, recipient_name, recipient_name_raw, recipient_doing_business_as_name, recipient_parent_uei, recipient_parent_name, recipient_parent_name_raw, recipient_address_line_1, recipient_city_name, recipient_zip_code, naics_code, naics_description`
  - Subawards: `subawardee_uei, subawardee_name, subawardee_dba_name, subawardee_parent_uei, subawardee_address_line_1, subawardee_city_name, subawardee_state_code, subawardee_zip_code, subawardee_country_code, subaward_description, prime_awardee_uei, prime_awardee_name, prime_awardee_dba_name, prime_awardee_parent_uei, prime_awardee_parent_name, prime_award_naics_code`
  - Subawards also carry "SubAwardeeHighCompOfficer1..5FullName".

  — [USAspending data dictionary API](https://api.usaspending.gov/api/v2/references/data_dictionary/)
- **Bulk "Award Data Archive"**: a public S3 bucket listing at `https://files.usaspending.gov/award_data_archive/`. Files are per fiscal year and agency, e.g. `FY2025_012_Contracts_Full_20260906.zip` (21 MB) and `FY2025_015_Contracts_Full_20260906.zip` (33 MB), plus `FY(All)_..._Contracts_Delta_20260906.zip`. They are refreshed monthly (2026-09-06 stamp). — [files.usaspending.gov award_data_archive](https://files.usaspending.gov/award_data_archive/)
- **FSRS.gov was retired on 2025-03-06.** Subaward reporting moved into SAM.gov, data entered in FSRS was moved to SAM.gov from 2025-03-08, and SAM.gov subcontract reporting feeds USAspending. — [SAM.gov announcement](https://sam.gov/announcements/announcing-fsrsgov-decommission-subaward-functionality-be-added-samgov-early-2025); [DAU blog](https://www.dau.edu/blogs/fsrsgov-retired-and-functionality-moved-samgov)

### Inferences
- **Matching uses**
  - (a) Identity confirmation by UEI.
  - (b) Name variants from `alternate_names` and `*_raw` vs. cleaned names.
  - (c) Corporate families from `recipient_parent_uei` / `subawardee_parent_uei`.
  - (d) Name changes, by seeing the same UEI under different names over time.
- **Coverage is federal work only.** Subawards are only first-tier subcontracts above the FFATA reporting threshold (believed to be $30k; not verified), reported by the prime, so many small residential subs are absent. Strong for federal and federally assisted heavy-civil, military and VA work.
- **Joint-venture names** (e.g. "CBY Design Builders …") appear as their own UEIs. OSHA also sees JVs as employers, so JV names should be split or linked to member firms rather than auto-matched.
- USAspending recipient IDs end in `-C` (child), `-P` (parent) or `-R` (no parent). The `-P` ID can enumerate children via the same API, which needs testing.

### Gaps
- Exact subaward reporting threshold and the coverage of construction subawards (row counts) were not obtained.
- Whether `subawardee_parent_name` exists alongside `subawardee_parent_uei` was not confirmed; the dictionary only showed `subawardee_parent_uei`.
- The 2025 SAM.gov subaward-system migration may have caused reporting gaps; not checked.

---

## 4. SBA data: PPP and EIDL loan-level FOIA, DSBS/SBS, 8(a)/HUBZone

### Takeaway
**PPP FOIA data** is the broadest free national list of *small* construction firms, sole proprietors included, with name, street address and NAICS. It is a 2020–2021 static snapshot, has no EIN, and is published as 13 CSVs under "U.S. Government Works". SBA's DSBS was replaced by **SBS** (search.certifications.sba.gov) in July 2025. 8(a) and HUBZone status is also carried in the SAM.gov extract.

### Cited Findings
- **Files**: dataset `ppp-foia` holds 13 CSVs plus a data dictionary, last updated 2024-09-30, licence "U.S. Government Works", publicly downloadable. — [data.sba.gov PPP FOIA](https://data.sba.gov/dataset/ppp-foia)
  - `public_150k_plus_240930.csv`
  - `public_up_to_150k_1_240930.csv` … `_12_240930.csv`
  - `ppp-data-dictionary.xlsx`
  - Base URL: `https://data.sba.gov/sites/default/files/distribution/SBA-OCA-2022-07-001/`
  - Sizes (HTTP HEAD): `public_150k_plus` 452,077,279 bytes; `up_to_150k_1` 413,938,705 bytes; `up_to_150k_12` 271,182,004 bytes. — [PPP CSV (live)](https://data.sba.gov/sites/default/files/distribution/SBA-OCA-2022-07-001/public_up_to_150k_1_240930.csv)
- **Exact header (verified live)**:
  - Loan: `LoanNumber, DateApproved, SBAOfficeCode, ProcessingMethod`
  - Borrower: **`BorrowerName, BorrowerAddress, BorrowerCity, BorrowerState, BorrowerZip`**
  - Status and amounts: `LoanStatusDate, LoanStatus, Term, …, InitialApprovalAmount, CurrentApprovalAmount, …`
  - Franchise and lender: **`FranchiseName`**, `ServicingLenderName…`
  - Business and project: `BusinessAgeDescription, ProjectCity, ProjectCountyName, ProjectState, ProjectZip, CD`
  - Size and industry: **`JobsReported, NAICSCode`**
  - Demographics, proceeds and type: `Race, Ethnicity, …, BusinessType, …, Gender, Veteran, NonProfit, ForgivenessAmount, ForgivenessDate`

  Some rows show `BorrowerName` = "Exemption 6" (FOIA privacy redaction) or "NOT AVAILABLE". — [PPP CSV (live)](https://data.sba.gov/sites/default/files/distribution/SBA-OCA-2022-07-001/public_up_to_150k_1_240930.csv)
- **Sample slice (8,711 rows from `up_to_150k_5`, read via a byte range)**
  - 727 rows (8.3%) had NAICS 23xxxx.
  - Construction BusinessType mix: Corporation 269, Subchapter S 211, LLC 133, Sole Proprietorship 89, Partnership 12, Independent Contractors 3.
  - No redacted names among the construction rows in that slice.
  - Examples: "QUINCY ELECTRIC AND SIGN COMPANY, INC | 1324 SPRING LAKE RD | QUINCY IL 62305-8704 | 238990"; "JOSH RANDALL BUILDER, INC. | … CHICAGO IL 60625 | 236118".

  — [PPP CSV range sample](https://data.sba.gov/sites/default/files/distribution/SBA-OCA-2022-07-001/public_up_to_150k_5_240930.csv)
- **SBS**: SBA replaced the Dynamic Small Business Search (DSBS) with Small Business Search (SBS) on 2025-07-09 at https://search.certifications.sba.gov; the old DSBS link redirects. It offers "downloadable customized vendor lists". These are secondary sources. — [iQuasar](https://iquasar.com/blog/sbs-replaces-dsbs-a-look-at-sbas-new-small-business-search-tool/); [Idaho APEX](https://www.idahoapexaccelerator.com/blog-posts/sbas-new-small-business-search-sbs-tool-goes-live)
- The SAM.gov public extract carries "SBA BUSINESS TYPES STRING", which holds 8(a), HUBZone and 8(a) JV participation with expiration dates. — [SAM Public V2 layout xlsx](https://open.gsa.gov/api/sam-entity-extracts-api/v1/SAM%20Master%20Extract%20Mapping%20v6.0%20Public%20File%20V2%20Layout.xlsx)

### Inferences
- **PPP is the best free source for (a) confirming small subs exist at a given address and (b) recording legal-form suffixes** (Inc/LLC/S-corp), which helps with "HAGERMAN vs HAGERMAN CONSTRUCTION". `JobsReported` can be compared with OSHA `nr_in_estab`. It does not give DBAs (only `FranchiseName`), EINs or parents.
- **Sole proprietors** are present as a BusinessType. Some individual names are redacted ("Exemption 6"), which limits value for the common-name sole-proprietor problem.
- PPP is static (2020–21 approvals), so later renames are not reflected. It is still useful as a historical anchor for 2016–2021 OSHA inspections.
- SBS duplicates SAM.gov-registered small businesses. A SAM.gov extract plus its SBA string probably makes SBS ingestion unnecessary.

### Gaps
- Total PPP loan count and total NAICS 23 count were not computed; the files were not fully downloaded.
- **EIDL loan-level data**: no EIDL dataset was found on the data.sba.gov PPP page. Whether SBA publishes loan-level COVID EIDL data was not verified.
- SBS bulk export limits and terms were not verified from SBA primary documentation.

---

## 5. FMCSA company census (USDOT number, legal name, DBA name, addresses): construction firms with trucks

### Takeaway
The FMCSA **Company Census File** is free and needs no key. It has 4.5 million rows, is updated daily, and is queryable through the Socrata API.
- Every row has `dot_number` (a stable ID), `legal_name` and `dba_name`, plus physical and mailing addresses, phone, email and up to two company officers.
- Over 1.1 million rows are flagged as hauling construction cargo.

It handles sole proprietors well: legal name is the owner's personal name, DBA is the trade name. That is the best free national **DBA-to-legal-name** source for small subs that run trucks.

### Cited Findings
- **Dataset `az4n-8mr2`, "Company Census File" (verified live)**
  - "records for active, inactive, and pending entities registered with FMCSA … FMCSA assigns a unique number to each entity record … the USDOT number."
  - Row count 4,512,353; rows last updated 2026-10-03; `Last-Modified: Sat, 03 Oct 2026 10:17:58 GMT`.
  - CSV: `https://data.transportation.gov/api/views/az4n-8mr2/rows.csv?accessType=DOWNLOAD`
  - API: `https://data.transportation.gov/resource/az4n-8mr2.json`, which worked without a key or app token.

  — [data.transportation.gov Company Census File metadata](https://data.transportation.gov/api/views/az4n-8mr2.json)
- **Columns (verified)**:
  - Identity: `dot_number, legal_name, dba_name, status_code, add_date, mcs150_date`
  - Physical address: `phy_street, phy_city, phy_state, phy_zip, phy_cnty`
  - Mailing address: `carrier_mailing_street, carrier_mailing_city, carrier_mailing_state, carrier_mailing_zip`
  - Contact and people: `phone, fax, cell_phone, email_address, company_officer_1, company_officer_2`
  - Organisation: `business_org_id, business_org_desc, dun_bradstreet_no`
  - Linkage: `prior_revoke_flag, prior_revoke_dot_number, docket1prefix, docket1`
  - Fleet: `power_units, truck_units, total_drivers, carrier_operation`
  - Cargo flags: `crgo_construct, crgo_bldgmat, crgo_machlrg`
  - Safety: `safety_rating`

  — [Company Census File metadata](https://data.transportation.gov/api/views/az4n-8mr2.json)
- **Live counts**:
  - `status_code='A'` (active): 2,246,580 rows.
  - `crgo_construct='X'`: 1,122,511 rows.
  - `dun_bradstreet_no` is non-null on 4,229,290 rows, but the sampled values were "0", i.e. effectively empty.

  — [Socrata API (live query)](https://data.transportation.gov/resource/az4n-8mr2.json)
- **Live examples**:
  - USDOT 360242 "BRASFIELD & GORRIE INC", Birmingham AL, inactive.
  - USDOT 878332 "HAGERMAN PLUMBING & HEATING CORPORATION", Owensboro KY, active, `crgo_construct=X`.
  - USDOT 1385226 legal_name "ELWOOD ROGER HAGERMAN JR", dba_name "PRAIRIE WINDS CONSTRUCTION", North Platte NE.
  - USDOT 1329248 "RANDALL LEE BRASFIELD" dba "BRASFIELD'S TRUCKING".

  — [Socrata API (live query)](https://data.transportation.gov/resource/az4n-8mr2.json)
- The older dataset `4a2k-zf79`, "Motor Carrier Registrations - Census Files", is a non-tabular attachment last updated in 2018 (`rowsUpdatedAt` 1545090816). Avoid it. — [4a2k-zf79 metadata](https://data.transportation.gov/api/views/4a2k-zf79.json)

### Inferences
- **(b) Name variants and DBAs**: `legal_name` ↔ `dba_name` pairs, especially sole-proprietor person-name → trade-name pairs, address exactly the "sole proprietor with common name" and "DBA vs legal name" failures. Officer names are a further tie-breaker.
- **(a) Identity**: the physical address plus phone gives strong confirmation. A USDOT number entered by the GC could be an optional input.
- **(d) Renames**: `prior_revoke_dot_number` and MC docket numbers give limited rename and re-registration signals.
- **Coverage**: firms operating commercial vehicles in interstate commerce, plus intrastate hazmat and some state-required intrastate carriers. Many excavation, concrete, paving, roofing and landscaping subs register; finish trades with only pickups may not.
- **Privacy**: the file contains personal names, emails and phones. Ingest only the fields needed.

### Gaps
- No licence or terms field in the Socrata metadata (`license: None`).
- Overlap of `crgo_construct` firms with OSHA construction employers was not measured.

---

## 6. EPA FRS / ECHO: do they integrate OSHA records or employer names?

### Takeaway
They are low value for construction subcontractors. FRS does ingest an **OSHA-OIS** program feed, but EPA says it includes only facilities inspected in the last 7 years in *mining, oil and gas, utilities and manufacturing*, not construction. ECHO's FAQ lists no OSHA data among its integrated systems.

### Cited Findings
- FRS program-system entry **OSHA-OIS**: "inspection case detail for approximately 100,000 OSHA inspections conducted annually. The FRS dataset includes facilities that had inspections within the last 7 years within the mining, oil and gas, utilities, and manufacturing sectors." FRS covers 130+ program systems. — [EPA FRS Data Sources](https://www.epa.gov/frs/frs-data-sources)
- An older EPA description refers to "OSHA-IMIS", the predecessor system. — [EPA FRS Description](https://www.epa.gov/frs/frs-description)
- ECHO integrates ICIS-Air, ICIS-NPDES, RCRAInfo, SDWIS, ICIS, FRS, TRI and Census data. The ECHO FAQ does not mention OSHA. — [ECHO FAQ](https://echo.epa.gov/resources/general-info/echo-faq)
- ECHO bulk downloads (ECHO Exporter, FRS download) are at echo.epa.gov/tools/data-downloads. — [ECHO Data Downloads](https://echo.epa.gov/tools/data-downloads)

### Inferences
- FRS's OSHA-OIS links (FRS registry ID ↔ OSHA program ID) cover fixed industrial sites, not mobile construction employers at transient job sites. They will not help with subcontractor identity.
- ECHO facility names belong to permitted *facilities* (site owners), not to contractors.

### Gaps
- Which OSHA ID FRS stores for OSHA-OIS records (activity number vs establishment) and its refresh date were not checked.
- Whether ECHO ever displayed OSHA data historically could not be confirmed.

---

## 7. IRS: any public EIN-to-name files or legal EIN lookups?

### Takeaway
No public IRS file maps EINs to business names except for tax-exempt organisations. IRS TIN Matching is restricted to information-return payers and only confirms a name/TIN pair you already have. Legal public EIN sources are other agencies' filings: OSHA ITA, Form 5500, OFLC H-2B/LCA/PERM and SEC EDGAR (sections 1 and 10).

### Cited Findings
- TIN Matching "is only for payers and their authorized agents that submit information returns". Payers must appear in the IRS Payer Account File, which requires having filed Forms 1099 within the last two years. — [IRS TIN Matching](https://www.irs.gov/tax-professionals/taxpayer-identification-number-tin-matching); [IRS Pub 2108A mirror](https://doa.virginia.gov/reference/1099/irs-e-services-on-line-tin-matching-program.pdf)
- SAM.gov holds TINs but classes them as "Sensitive", available only to federal accounts with "Read Sensitive". — [open.gsa.gov Entity Management API](https://open.gsa.gov/api/entity-api/)

### Inferences
- The IRS Exempt Organizations Business Master File covers only tax-exempt organisations. It is irrelevant for for-profit subcontractors; this was not re-verified this session.
- Free EIN-bearing alternatives, in rough order of construction coverage:
  1. OSHA ITA (300A and 300/301, `ein`), already ingested.
  2. Form 5500 / 5500-SF (`SF_SPONS_EIN`), for any firm with a retirement or welfare plan.
  3. OFLC H-2B / LCA / PERM (`EMPLOYER_FEIN`).
  4. SEC EDGAR (`ein`), public companies only.

### Gaps
- No official IRS statement found prohibiting EIN lookup in general, only the eligibility limits on TIN Matching.

---

## 8. Census Bureau and BLS: any public business lists?

### Takeaway
None. Census Business Register microdata is confidential under Titles 13 and 26, and published products are aggregates with no names or addresses.

### Cited Findings
- "Business Register information is confidential under Title 13 and Title 26 … access is restricted to persons specially sworn." Data for individual establishments "are not available for public use because Federal law prohibits disclosure of individual business information". — [Federal Register 2012-01-27 SORN notice](https://www.govinfo.gov/content/pkg/FR-2012-01-27/pdf/2012-1804.pdf); [Census: Federal Law](https://www.census.gov/about/policies/privacy/data_stewardship/federal_law.html)
- The Business Register feeds aggregate products such as County Business Patterns and Nonemployer Statistics. — [Census CES working paper on the Business Register](https://www2.census.gov/ces/wp/2016/CES-WP-16-17.pdf)

### Inferences
- BLS QCEW establishment microdata is likewise confidential under CIPSEA, so there is no public employer list. This was not separately verified this session.
- Use County Business Patterns only for priors, e.g. how common a firm size is in a county, not for matching.

### Gaps
- No primary BLS confidentiality page was fetched.

---

## 9. Federal debarment (incl. Davis-Bacon), NLRB case data, EEOC

### Takeaway
- **Debarment**: Davis-Bacon debarments are checked through SAM.gov Exclusions (name, UEI, CAGE, address, excluding agency). Exclusions are tiny but high-signal.
- **NLRB**: case participants (employers with mailing addresses) can be downloaded from NLRB's Advanced Data Search, up to 100k records per export. A daily-refreshed third-party mirror also exists.
- **EEOC**: no public employer-level dataset was found.

### Cited Findings
- **SAM.gov Exclusions** returns entity name, UEI, CAGE, excluding agency code, classification (Firm/Individual), exclusion type and program, activation and termination dates, primary and secondary addresses, cross-references and additional locations. It requires an API key. — [open.gsa.gov Exclusions API](https://open.gsa.gov/api/exclusions-api/)
- **DOL guidance**: DBRA debarment declares a contractor ineligible for 3 years for disregarding obligations to workers or subcontractors. Grantees are told to look bidders up at SAM.gov exclusions. — [DOL WHD debarment seminar PDF](https://www.dol.gov/sites/dolgov/files/WHD/prevailing-wage-presentations/dbra-seminars/What-is-Debarment-and-Why-Does-It-Happen.pdf); [Michigan grants guidance](https://www.michigan.gov/msp/-/media/Project/Websites/msp/EMHSD/grants2/instructions_for_checking_for_excluded__debarred_contractors_revised_72020.pdf?rev=0a928fb6b4b54253b2a627f1eb70dcd8&hash=31DC61AC1AB1E38D5A84952C43D27F82)
- **NLRB official access**: Advanced Data Search builds customised downloadable data sets (up to 100,000 records at a time) from the case management system, as CSV. Case pages can be downloaded as CSV and XML. These details come from search results; nlrb.gov refused the connection when fetched this session. — [NLRB Advanced Data Search](https://www.nlrb.gov/advanced-search); [NLRB case search](https://www.nlrb.gov/case/search)
- **NLRB third-party mirror**: `labordata/nlrb-data`, "daily refreshed data on representation certification and unfair labor cases from nlrb.gov". Its participant table has 1,957,369 rows, covering petitioners, charged parties, employers, unions and intervenors, with mailing addresses. — [labordata/nlrb-data GitHub](https://github.com/labordata/nlrb-data); [labordata NLRB participant table](https://labordata.bunkum.us/nlrb/participant)

### Inferences
- **Exclusions** are a "red-flag" signal rather than an identity resolver. The cross-references and AKA-style "additional names" fields can still link related firms, e.g. a debarred owner and their new company.
- **NLRB participants** give employer names and addresses mainly for unionised or organising-target firms, which covers many union construction subs. There is no EIN. Useful only as an extra alias source.
- **EEOC**: EEO-1 reports are confidential and EEOC publishes no employer-level enforcement dataset. Not verified this session; treat as low priority.

### Gaps
- Whether DOL WHD Davis-Bacon debarments are entered as SAM exclusions, and under which agency code, was not confirmed from a primary GSA or DOL page.
- The SAM exclusions public file's download-without-login status is contradictory across sources (see section 2).
- The NLRB primary page could not be fetched (connection refused), so ADS limits and fields are from search-result summaries.

---

## 10. Other national datasets worth considering (OFLC H-2B/LCA/PERM with FEIN, Form 5500, SEC EDGAR, GLEIF, OpenCorporates, EPA RRP), plus cross-dataset prioritisation

### Takeaway
Two free, no-account, EIN-bearing sources stand out.
- **DOL Form 5500 / 5500-SF**: sponsor legal name, DBA, EIN, NAICS, a location address, and **last-reported sponsor name/EIN**, which is a direct name-change signal. Monthly, 2009–2025.
- **DOL OFLC H-2B disclosure files**: `EMPLOYER_NAME` (legal), `TRADE_NAME_DBA`, `EMPLOYER_FEIN` and NAICS, covering construction and landscaping firms that use H-2B.

SEC EDGAR (EIN plus former names) and GLEIF (parent relationships) are free but cover only large firms. OpenCorporates still needs an API key. Its free tier only allows open-data, share-alike use, and commercial use costs £2,250+/yr.

### Cited Findings

**OFLC H-2B / LCA / PERM disclosure data**
- The H-2B FY2025 record layout covers 2024-10-01 to 2025-09-30. It lists:
  - `EMPLOYER_NAME` ("Legal business name of the employer")
  - `TRADE_NAME_DBA` ("Trade name or 'Doing Business As' (DBA) name")
  - `EMPLOYER_ADDRESS1/2, EMPLOYER_CITY, EMPLOYER_STATE, EMPLOYER_POSTAL_CODE, EMPLOYER_PHONE`
  - **`EMPLOYER_FEIN`** ("Federal Employer Identification Number (FEIN from IRS). Form ETA-9142B Section C, Item 12")
  - `NAICS_CODE`, `EMPLOYER_POC_*`, `WORKSITE_CITY` and related fields

  Excluded as PII: only "Attorney's FEIN, Attorney's State Bar Number and Preparer Law Firm/Business FEIN". — [H-2B Record Layout FY2025 Q4](https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/H-2B_Record_Layout_FY2025_Q4.pdf)
- The LCA (H-1B/H-1B1/E-3) FY2024 Q4 layout also includes `EMPLOYER_FEIN`. Its PII exclusions are only "Attorney's FEIN and Attorney's State Bar Number". — [LCA Record Layout FY2024 Q4](https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Record_Layout_FY2024_Q4.pdf)
- **Conflict**: a search-engine summary says that in FY2024 Q1 the H-2B public file *excluded* employer FEIN as PII, so FEIN availability varies by year and should be checked per file. — [H-2B Record Layout FY2024 Q1](https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/H-2B_Record_Layout_FY2024_Q1.pdf)
- The latest release is FY2026 Q3 (2025-10-01 to 2026-06-30), as `.xlsx` files: `H-2B_Disclosure_Data_FY2026_Q3.xlsx` (plus Appendices A, C, D), `H-2A_…`, `PERM_Disclosure_Data_FY2026_Q3.xlsx` and `LCA_Dislclosure_Data_FY2026_Q3.xlsx` (sic). — [OFLC Performance Data](https://www.dol.gov/agencies/eta/foreign-labor/performance)

**DOL EBSA Form 5500 datasets**
- Years 2009–2025. Files: Form 5500, 5500-SF, and Schedules A/C/D/G/H/I/R/MB/MEP/SB. URL pattern `https://askebsa.dol.gov/FOIA%20Files/[YEAR]/[Latest|All]/`, e.g. `F_5500_2025_Latest.zip`. "Typically updated around the first of each month." No account. Data dictionaries are provided. — [EBSA Form 5500 Datasets](https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/public-disclosure/foia/form-5500-datasets)
- **5500-SF 2024 header (verified via range read; CSV `f_5500_sf_2024_latest.csv`, 600,132,167 bytes uncompressed)**:
  - Sponsor: `SF_SPONSOR_NAME, SF_SPONSOR_DFE_DBA_NAME, SF_SPONS_US_ADDRESS1/2, SF_SPONS_US_CITY, SF_SPONS_US_STATE, SF_SPONS_US_ZIP`, **`SF_SPONS_EIN`**, `SF_BUSINESS_CODE` (NAICS)
  - Administrator: `SF_ADMIN_NAME, SF_ADMIN_EIN`
  - Prior sponsor: **`SF_LAST_RPT_SPONS_NAME, SF_LAST_RPT_SPONS_EIN`**, `SF_LAST_RPT_PLAN_NUM`
  - Participants: `SF_TOT_PARTCP_BOY_CNT`
  - Physical location: **`SF_SPONS_LOC_US_ADDRESS1/2, SF_SPONS_LOC_US_CITY, SF_SPONS_LOC_US_STATE, SF_SPONS_LOC_US_ZIP`**
  - Preparer: `SF_PREPARER_FIRM_NAME`

  — [F_5500_SF_2024_Latest.zip](https://askebsa.dol.gov/FOIA%20Files/2024/Latest/F_5500_SF_2024_Latest.zip)

**SEC EDGAR**
- `https://data.sec.gov/submissions/CIK##########.json` needs no authentication or API key. Bulk `submissions.zip` is "recompiled nightly". — [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- Live test for D.R. Horton (CIK 0000882184): name "HORTON D R INC /DE/", **ein "752386963"**, SIC 1531 "Operative Builders", stateOfIncorporation DE, `formerNames` [] (the field exists, empty here), business and mailing address 1341 Horton Circle, Arlington TX 76011. — [data.sec.gov submissions (live)](https://data.sec.gov/submissions/CIK0000882184.json)
- `submissions.zip` is 1,567,247,172 bytes, last-modified 2026-10-03. — [submissions.zip (HEAD)](https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip)
- Rate limit is 10 requests per second, and a declared User-Agent with contact details is required. — [SEC Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

**GLEIF (LEI)**
- Golden Copy files come three times a day: Level 1 LEI-CDF, Level 2 Relationship Records (direct and ultimate parents), and Reporting Exceptions, plus delta files. — [GLEIF Golden Copy](https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy)
- Licence CC0, free, no registration; the API needs no key. — [GLEIF Open Data](https://www.gleif.org/en/about/open-data); [GLEIF Access and Use](https://www.gleif.org/en/lei-data/access-and-use-lei-data)
- Live test: "D.R.Horton, Inc." has LEI 529900ZIUEYVSB8QDD25, status **LAPSED**, and **only 1 direct child** (DHI MORTGAGE COMPANY, LTD.). "Brasfield" returned no LEI. — [GLEIF API (live)](https://api.gleif.org/api/v1/lei-records/529900ZIUEYVSB8QDD25/direct-children)

**OpenCorporates (re-check of the "paid key" assumption)**
- "An API key is required in order to use the OpenCorporates API." Accounts "are free if you are going to be using the data in an open data project … also released under an open licence (specifically share-alike attribution …)". The default limit is "200 requests per month, and 50 requests per day". Paid accounts "remove the OpenCorporates share-alike restrictions". Company records include `previous_names` and officers, and US state registries are covered (e.g. `us_mi`). — [OpenCorporates API Reference](https://api.opencorporates.com/documentation/API-Reference)
- Secondary pricing (2026): Essentials £2,250/yr (500 calls/month), Starter £6,600/yr, Basic £12,000/yr. Public-benefit access is "by application" at OpenCorporates' discretion. — [savvyiq.ai comparison](https://savvyiq.ai/compare/opencorporates); [findmymoat review](https://www.findmymoat.com/tools/opencorporates)

**EPA Lead-Safe (RRP) certified firms**
- EPA's Lead-based Paint Professional Locator returns firm name, phone, address, discipline, certification number and expiry. No bulk download was found. Coverage is limited to EPA-administered states. — [EPA firm search](https://cdxocsppapps.epa.gov/ocspp-oppt-lead/firm-search); [LeadSafeFiling guide](https://www.leadsafefiling.com/guides/how-to-look-up-a-lead-safe-certified-firm)

### Inferences

**Form 5500 is the strongest new free source for (a), (b) and (d)**
- EIN plus legal name plus DBA plus physical location.
- `LAST_RPT_SPONS_NAME/EIN` flags renames and sponsor changes, e.g. after an acquisition.
- Many small and mid construction firms sponsor 401(k) or welfare plans and file 5500-SF.
- It also links to OSHA ITA through the EIN the project already holds, so ITA EIN ↔ 5500 EIN gives a second name/DBA for the same EIN.
- The main 5500 form has analogous `SPONS_DFE_*` / `LAST_RPT_SPONS_*` fields; inferred, not re-verified this session.

**OFLC H-2B for EIN plus a DBA pair**
- Construction and landscaping firms file H-2B.
- Several fiscal years (FY2020+, where FEIN is present) can be concatenated into an EIN ↔ legal name ↔ DBA table.
- WHD's `H2B_*` violation columns and OFLC data can share employers, but only by name and address.

**Corporate families (c)**
- None of the free sources gives a complete parent tree for private construction firms. The best partial sources:
  - USAspending `*_parent_uei`
  - SAM.gov `integrityInformation` `highestOwner` / `immediateOwner`
  - EIN sharing across ITA, 5500 and H-2B, with multiple names under one EIN
  - SEC EDGAR for public builders (D.R. Horton, Lennar and similar), via Exhibit 21 subsidiary lists (not verified this session)
- GLEIF is poor for US construction: the D.R. Horton LEI is lapsed and has one child.
- D.R. Horton's regional divisions under multiple EINs are best handled by Form 5500 / ITA EIN clusters plus SAM.gov's "ENTITY DIVISION NAME" plus a curated parent alias list.

**Prioritised ingest shortlist** (free, bulk, no paid key)

| Priority | Dataset | ID carried | Best for | Access |
|---|---|---|---|---|
| 1 | DOL WHD Enforcement | none (CASE_ID) | (b) trade↔legal name pairs + address + NAICS | data.dol.gov zip, no key, quarterly, ~200 MB |
| 1 | DOL Form 5500 / 5500-SF | EIN | (a) (b) DBA, (d) last-reported sponsor name/EIN | askebsa.dol.gov zips, no account, monthly |
| 1 | FMCSA Company Census | USDOT number | (a) (b) legal↔DBA (sole proprietors), officers | Socrata CSV/API, no key, daily, 4.5M rows |
| 2 | OSHA ITA 300/301 case detail | EIN, establishment_id | (a) (c) company_name vs establishment_name | osha.gov CSV/zip (browser download) |
| 2 | OFLC H-2B (plus LCA/PERM) | EMPLOYER_FEIN | (a) (b) legal↔DBA with EIN | dol.gov xlsx, no account, quarterly |
| 2 | USAspending prime + subaward, recipient API | UEI, parent UEI | (a) (b) alternate_names, (c) parent UEI | API and S3 archive, no key, monthly |
| 2 | SAM.gov public monthly extract | UEI, CAGE | (a) (b) legal/DBA/division name | free account + API key, monthly |
| 3 | SBA PPP FOIA | none | (a) small-firm existence + address + NAICS + legal form | data.sba.gov CSVs, static 2020–21 |
| 3 | SEC EDGAR submissions | CIK, EIN | (c) (d) public builders, formerNames | no key, 10 req/s, nightly |
| 3 | SAM Exclusions, NLRB participants, VETS-4212 | UEI/CAGE; none; none | red flags / extra aliases | key / ADS export / zip |
| skip | EPA FRS/ECHO, GLEIF, Census/BLS, IRS | – | – | not useful for construction subs |

### Gaps
- FEIN presence in each OFLC fiscal-year file (FY2016–FY2026) needs checking per file. The FY2026 Q3 H-2B layout URL returned 404, so the current layout is unverified.
- The construction (NAICS 23) row counts in Form 5500-SF, H-2B and WHD were not computed; no full downloads were made this session.
- The OpenCorporates free-tier eligibility for this project, a commercial tool for GCs, is likely "no", since the share-alike condition would apply to the product's data. A licensing decision is needed.
- Whether SEC `formerNames` is populated for private construction firms that file Form D was not tested.
