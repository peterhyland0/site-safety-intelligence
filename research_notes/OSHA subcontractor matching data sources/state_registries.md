# US state-level public registries for matching subcontractors to OSHA inspection records

Research date: 2026-10-04. Method: live probes of state open-data (Socrata) APIs for column lists and row counts, direct HTTP checks of official download endpoints, and web searches. Many Southeast state sites (tnbear.tn.gov, llr.sc.gov, licensesearch.alabama.gov, sos.ga.gov, myfloridalicense.com, ohiosos.gov, roc.az.gov) refused connections or sent a Cloudflare challenge to the research machine, which has a non-US IP. Facts about those sites come from search-index snippets of the official pages and are marked **(snippet)**. Row counts marked **(API)** were read live on 2026-10-04 with `$select=count(*)`.

---

## 1. Secretary of State / business-entity registries: free bulk or API access, DBAs, name history, cost

### Takeaway
Seven states give free, complete, machine-readable entity registries that matter for this project: **NY, CO, CT, OR, PA, IA, AK**. Two more give free bulk files without an API: **FL** (Sunbiz SFTP, with FEIN and up to six officers) and **OH** (monthly reports). NY, CO and CT also publish **name-change history** and **assumed/trade-name** tables, which target the DBA and renamed-company failures directly. The Southeast is mostly paid: TN about $1,000, GA $1,000 or $500/month, NC $750 plus $2,000/yr, TX $1,350–1,750. AL and SC have no bulk product. Florida is the exception and is the best free Southeast source.

### Cited Findings

**Free, open-data or API (verified live)**
- **New York DOS, data.ny.gov (free Socrata API/CSV).** The NY set is the most complete of any state:
  - "Active Corporations: Beginning 1800" (`n9v6-gdp6`): **4,291,968 rows (API)**. Columns: dos_id, current_entity_name, initial_dos_filing_date, county, jurisdiction, entity_type, DOS process name/address, chairman name/address, registered agent name/address, location name/address. Updated 2026-10-03. — [data.ny.gov n9v6-gdp6](https://data.ny.gov/d/n9v6-gdp6)
  - "Corporations and Other Entities: All Filings" (`63wc-4exh`): **20,976,639 filings (API)**. Columns include corp_name, **fict_name** (155,096 non-null), and amendment flags such as amd_corp_name_flag and amd_fict_name_flag. Assumed-name document types (API): ASSUMED NAME CORP INITIAL FILING 444,010; CERTIFICATE OF ASSUMED NAME 247,117; ASSUMED NAME LLC INITIAL FILING 132,996; plus amendment and discontinuance filings. — [data.ny.gov 63wc-4exh](https://data.ny.gov/d/63wc-4exh)
  - "All Filings – Name Status History" (`ekwr-p59j`): **7,504,217 rows (API)**. Columns: corpid_num, film_num, date_filed, name_type, name_status (A = active 4.32M, I = inactive 3.18M), corp_name. Each row is a current or previous name of an entity, so this table is the prior-name history. — [data.ny.gov ekwr-p59j](https://data.ny.gov/d/ekwr-p59j)
  - "All Filings – Address" (`2tms-hftb`): 18,448,465 rows (API). Also available: Entity Status History (`3gg2-jgnp`), Constituent/merger (`dnbf-xifz`), and a "Daily Corporation and Other Entity Filing Data" 30-day feed (`k4vb-judh`, 81,474 rows) with corp_name, fictitious_name, **pre_corp_name** (the prior name) and merger constituent names. — [data.ny.gov 2tms-hftb](https://data.ny.gov/d/2tms-hftb); [k4vb-judh](https://data.ny.gov/d/k4vb-judh)
- **Colorado SOS, data.colorado.gov (free).**
  - "Business Entities in Colorado" (`4ykn-tg5h`): **3,118,181 rows (API)**, updated daily. Columns: entityid, entityname, principal and mailing address, entitystatus, jurisdiction, entitytype, registered-agent name and address, entityformdate. — [data.colorado.gov 4ykn-tg5h](https://data.colorado.gov/d/4ykn-tg5h)
  - "Trade Names for Businesses in Colorado" (`u7sb-g482`): **286,877 rows (API)**. Columns: tradenamedescription, registrant first/last name or registrantorganization, address, entitystatus, entityid. — [data.colorado.gov u7sb-g482](https://data.colorado.gov/d/u7sb-g482)
  - "Business Entity Transaction History" (`casm-dbbj`): **21,705,937 rows (API)**. Includes **58,151 "Entity Name Change"** events, 26,567 entity-name corrections and about 1.9M trade-name statements and renewals. — [data.colorado.gov casm-dbbj](https://data.colorado.gov/d/casm-dbbj)
- **Connecticut SOTS, data.ct.gov (free, nightly).**
  - Business Master (`n7gp-d28j`): **1,300,995 rows (API)**. Fields include name, status, accountnumber, date_registration, **dissolution_date**, billing, mailing and office addresses, and **naics_code**.
  - **Name Change History** (`enwv-52we`): **96,682 rows (API)**. Columns: business_name_old, business_name_new, name_change_date.
  - **Principals** (`ka36-64k6`): **1,793,777 rows (API)**. Officer/member names with business and residence addresses.
  - Agents (`qh2m-n44y`) and Business Filing History (`ah3s-bes7`).
  — [data.ct.gov n7gp-d28j](https://data.ct.gov/d/n7gp-d28j); [enwv-52we](https://data.ct.gov/d/enwv-52we); [ka36-64k6](https://data.ct.gov/d/ka36-64k6)
- **Oregon SOS, data.oregon.gov (free).** "Active Businesses – ALL" (`tckn-sxa6`) has **1,580,777 rows (API)**, one row per associated name or address. Row types: principal place of business 561,846; registered agent 451,486; mailing 449,814; authorized representative 117,631. **Assumed Business Names are included as an entity type (234,232 rows)**, and the fields `entity_of_record_reg_number` and `entity_of_record_name` link each ABN to its registrant. The dataset is active entities only. A monthly "New Businesses Registered Last Month" dataset (`esjy-u4fc`) is also published. — [data.oregon.gov tckn-sxa6](https://data.oregon.gov/d/tckn-sxa6)
- **Pennsylvania DOS, data.pa.gov (free).** "Registered Businesses in PA Current by County" (`xvd7-5r2c`) has **4,110,251 rows (API)**. Columns: business_name, filing_number, address, typeofbusinessregistration, creationdate, party_type plus party last/first name (officers, members, owners), and county. The distinct-business view (`3urc-uaba`) has 2,360,829 rows. Entity types listed (API) are corporations, LLCs, LPs and similar. **No fictitious-name registrations appear** among the types in this dataset. — [data.pa.gov xvd7-5r2c](https://data.pa.gov/d/xvd7-5r2c); [3urc-uaba](https://data.pa.gov/d/3urc-uaba)
- **Iowa SOS, Iowa Data Hub dataset 554 (free, monthly).** Download: `https://idh-be.iowa.gov/api/v1/datasets/554/rows.csv`, a zipped CSV. Columns verified: corp_number, legal_name, corporation_type, effective_date, registered_agent with address, and home_office address. Active entities only. — [Iowa Data Hub 554](https://data.iowa.gov/catalog/dataset/554); [data.gov listing](https://catalog.data.gov/dataset/active-iowa-business-entities)
- **Alaska CBPL (free, no account).** `CorporationsDownload` returns CSV directly. Header verified: CORPTYPE, ENTITYNUMBER, LEGALNAME, **ASSUMEDNAME**, STATUS, AKFORMEDDATE, registered agent, entity mailing and physical addresses. — [commerce.alaska.gov CorporationsDownload](https://www.commerce.alaska.gov/cbp/main/DbDownload/CorporationsDownload)
- **Delaware**: there is no free corporate bulk file (pay per entity: $10 status, $20 with history). — [OpenCorporates blog, 2025-09-15](https://blog.opencorporates.com/2025/09/15/sourcing-data-directly-from-us-state-registries/). Separately, data.delaware.gov "Delaware Business Licenses" (`5zy2-grhr`) has **69,121 rows (API)** with business_name, **trade_name**, category, license number and address. — [data.delaware.gov 5zy2-grhr](https://data.delaware.gov/d/5zy2-grhr)

**Free bulk files without an API**
- **Florida Sunbiz (free SFTP).** Files are served from host `sftp.floridados.gov` using public credentials that the Division of Corporations posts on its page. They are not reproduced here; the researcher did not log in.
  - Quarterly files (January, April, July, October): Corporate Filings `doc/quarterly/cor/cordata.zip`, Corporate Events `corevent.zip`, Fictitious Names `doc/quarterly/fic/ficdata.zip` with events in `ficevt.zip`.
  - Daily files are also published.
  - All files are fixed-length ASCII. — [Sunbiz Quarterly Data](https://dos.fl.gov/sunbiz/other-services/data-downloads/quarterly-data/) (snippet; the page returned 403 to the fetcher); [Fictitious Name file definitions](https://dos.myflorida.com/sunbiz/other-services/data-downloads/fictitious-name-data-file/); [Daily Data](https://dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/)
  - Corporate record layout (1,440 characters), fetched directly: corporation number and name, status (A/I), filing type, principal and mailing addresses, file date, **FEI Number (field 18, position 481, length 14)**, last transaction date, report years, registered agent name and address, and **up to 6 officers** (title, type, name, address) with a "more than six officers" flag. There is no prior-name field in the master record; name changes are carried in the events file. — [Sunbiz corporate file definitions](https://dos.sunbiz.org/data-definitions/cor.html)
- **Ohio SOS**: free monthly reports, generated on the second Saturday of each month, covering new business filings, subsequent filings, trademarks and dissolved entities. Fields include charter number, name, statutory agent, incorporator and address. — [ohiosos.gov business reports](https://www.ohiosos.gov/business/business-reports) (snippet; Cloudflare blocked a direct fetch). These look like monthly *activity* files rather than a full master snapshot; this was not verified.

**Paid bulk**
- **Texas SOS (SOSDirect bulk order).** Master Unload $1,350 (previous format) or **$1,750 (new format)**; Daily Filing Update subscription $60/month; Weekly Filing Update $20/month; List by Entity Description $200. Individual searches cost $1 each. — [SOSDirect bulk orders help](https://direct.sos.state.tx.us/help/help-corp.asp?pg=bulk) (snippet; a direct fetch returned only the index); [SOSDirect fee schedule](https://direct.sos.state.tx.us/help/help-corp.asp?pg=fee-revised)
- **Texas Comptroller (free, data.texas.gov).** This is a usable substitute for the paid SOS master.
  - "Active Franchise Taxpayers" (`9cir-efmm`): **3,484,555 rows (API)**. Columns: taxpayer_number, taxpayer_name and address, organizational type, **secretary_of_state_sos_or_coa_file_number** (which links to SOS), sos_charter_date, sos_status_code, right_to_transact_business_code.
  - "Active Sales Tax Permit Holders" (`jrea-zgmq`): **888,901 outlet rows (API)**. Columns: taxpayer_name plus **outlet_name** (often the trade name or DBA), outlet address, **outlet_naics_code** and permit issue date. **45,676 outlets have a construction NAICS (23xxxx) (API)**.
  — [data.texas.gov 9cir-efmm](https://data.texas.gov/d/9cir-efmm); [jrea-zgmq](https://data.texas.gov/d/jrea-zgmq)
- **Georgia SOS (through the Georgia Technology Authority).** One-time purchase **$1,000**, or an FTP subscription at **$100** to set up plus **$500/month**. Tab-delimited text, paid by check or money order, with a signed Bulk Corporations Data Agreement required. — [georgia.gov Bulk Corporations Data](https://georgia.gov/bulk-corporations-data) (fetched directly)
- **Tennessee SOS (tnbear DB Download Wizard).** Full database **$1,000**; prior-month or prior-week activity **$50** each, plus a service fee. Contents: mailing address, **assumed names the entities have registered**, registered agent, and annual-report history. — [tnbear DBDownloadWizard](https://tnbear.tn.gov/Ecommerce/DBDownloadWizard.aspx) (snippet; host refused connection)
- **North Carolina SOS.** One-time set-up fee **$750**, then the Business Registration Division Master Files subscription at **$2,000 per state fiscal year**. Updated weekly, CSV. — [NC SOS data-subscription fees](https://b2b.sosnc.gov/fees/by_title/_data_subscriptions) (fetched directly); [NC data subscriptions](https://www.sosnc.gov/online_services/data_subscriptions); 2026 weekly CSV per [secondary search summary](https://sosnc.gov/online_services/data_subscriptions/business_registration_data_subscriptions)
- **California SOS**: bizfile "Master Unload" business-entity data **$100**, images $800, data plus images $900, ordered through "BE & UCC Bulk Orders" in bizfile Online. — [Kyckr 2025](https://www.kyckr.com/blog/california-business-register-2025-update); [Quintel](https://quintel.ai/blog/ucc-filing-search-by-state). Secondary sources only; not confirmed on sos.ca.gov. The official page lists the free online search fields: name, number, status, agent, officers, addresses. — [CA SOS information requests](https://www.sos.ca.gov/business-programs/business-entities/information-requests)
- **Illinois**: bulk data is available only by paid contract with the Department of Business Services (217-782-6961). Bulk copying from the web search is prohibited. — [secondary summary of ilsos.gov terms](https://www.ilsos.gov/departments/business-services/business-searches.html) (snippet; no price found)
- **Other states, from secondary sources:**
  - KY **$2,000/month**, including officers and daily or weekly deltas.
  - IN **$8,000** one-time or **$9,500** with monthly updates.
  - MN **$30** for name and address only, no officers.
  - WV **$25 minimum + $0.05/record**.
  — [OpenCorporates blog, 2025-09-15](https://blog.opencorporates.com/2025/09/15/sourcing-data-directly-from-us-state-registries/)
- A secondary matrix last updated 2026-05-18 lists these as paid or by request: AR, AZ (records request), HI, ID, ME, MI, MT, ND, NJ (paid API), NV (paid), OK, SD, UT, WI. It lists these as having no bulk product: **AL, KS, LA, MD, MO, MS, NE, NH, NM, RI, SC, VA, VT, DC**. — [privatepierce.com matrix](https://privatepierce.com/business-formation/business-registry-bulk-data-availability-by-state/). **This matrix is demonstrably wrong for several states**:
  - It marks OR and PA as "No", but both have free datasets (above).
  - It marks NY and WA as "unresolved".
  - It marks FL as "records request", but Sunbiz runs a free SFTP.
  - Treat it as a starting point only.
- **Alabama SOS**: the "Business Downloads" page offers only forms and a registered-agent PDF list; no data downloads. — [sos.alabama.gov business-downloads](https://www.sos.alabama.gov/business-entities/business-downloads) (fetched directly)
- **Washington SOS**: "The Corporations Data Extract feature is no longer available." Users can only export Advanced Search results to Excel. — [data.wa.gov f9jk-mm39](https://data.wa.gov/Consumer-Protection/Corporations-Search-Washington-state-/f9jk-mm39)
- **Vermont**: Business Registration database downloads exist but require logging in to the Online Business Service Center; no price found. — [VT SOS searches & databases](https://www.sec.state.vt.us/corporationsbusiness-services/searches-databases.aspx) (snippet)
- **Aggregators.** OpenCorporates covers all 50 states in one schema, with officers, alternative names and identifiers delivered by API or bulk SFTP. Its entry API plan is about $3,040/yr for 500 calls/month; free bulk access is limited to public-benefit users. — [savvyiq comparison](https://savvyiq.ai/compare/opencorporates); [FEBIS 2022](https://www.febis.org/2022/12/15/opencorporates-unifies-official-company-data-from-all-50-us-states/)

### Inferences
- **NY, CO and CT are the only states found that publish an explicit old-name to new-name table for free.** NY has 7.5M name records, CT 96.7k changes and CO 58k name-change events. These address the renamed-company case directly. NY also has about 867k assumed-name filings by corporations, LLCs and LPs.
- **Florida Sunbiz is the best Southeast source.** It is free, includes FEI/EIN, officers (useful for sole proprietors and corporate families) and a separate statewide fictitious-name file. FL is also a top-5 OSHA construction state, so it should be the first SOS ingest after NY.
- **Texas, the highest-volume OSHA state, can be covered for free** without buying the $1,750 SOS master:
  - The Comptroller franchise-tax file gives legal names with the SOS file number.
  - The sales-tax outlet file gives trade names with NAICS: 45.7k construction outlets, the closest free proxy for Texas DBAs.
  - The franchise file has no officers.
- **Georgia, Tennessee and North Carolina** each cost $1,000–2,750 one-off or yearly. Tennessee's $1,000 file explicitly includes assumed names, which matters for the Nashville demo.
- **Alabama and South Carolina have no SOS bulk product.** For those states the contractor boards are the only structured source.
- From general knowledge, not verified here: in many states, including GA and county-filed sole-proprietor DBAs in TX and TN, assumed names for **unincorporated sole proprietors are filed with county clerks**, not the SOS. That would leave statewide SOS files with gaps for exactly the "sole proprietor with a common name" failure.

### Gaps
- NJ, IL, MI, MA, SC and LA bulk prices or terms were not confirmed from primary pages.
- The OH monthly report schema and whether a full master exists were not confirmed (Cloudflare).
- MA "CorpDataExport" (free per the secondary matrix) was not verified.
- The Texas SOS bulk page could not be rendered, so prices rest on a search snippet of the official help page.
- California's $100 Master Unload rests on secondary sources only, and the claimed free "weekly unloads" are unverified.
- Florida SFTP file sizes and row counts were not measured: logging in with the posted public credentials was deliberately avoided.
- No NASS directory or report on bulk-data availability was found.

---

## 2. State contractor licensing boards: bulk licensee lists, fields, and how to get the full California CSLB file

### Takeaway
Free bulk licence files exist for: **CA CSLB** (full master about 57 MB), **FL DBPR** (CILB and electrical CSV extracts), **TX** (TDLR all-licences dataset and TSBPE plumbing CSVs), **VA DPOR** (tab-delimited regulant lists), **MN DLI** (nightly CSVs), **OR CCB**, **WA L&I**, **NYC DOB**, **NYS DOL Contractor Registry**, and **AZ ROC** (posting list). In the Southeast, TN's board publishes a downloadable Tableau dashboard and AL's general-contractor board offers a CSV verification list. GA sells rosters (on CD) and SC rosters cost $10 per request. **The CSLB truncation is a timeout problem.** The full License Master is 57,079,888 bytes with about 179k licences, served slowly through an ASP.NET postback, and needs a long-running streamed download.

### Cited Findings

**California CSLB (free)**
- The Public Data Portal "Master List of California Licensed Contractors" has three files: **License Master, Workers' Compensation, Personnel**, in Excel (.xls) or CSV, at no charge. The License Master covers licences that are "currently renewed, or expired but renewable"; "cancelled, revoked, or expired non-renewable" licences are excluded. A licence stays renewable for 5 years after expiry. Personnel excludes disassociated personnel. The page showed "Updated as of 10/3/2026". — [CSLB ContractorList](https://www.cslb.ca.gov/onlineservices/dataportal/ContractorList)
- **How the download works (verified 2026-10-04):**
  1. GET the page.
  2. POST back `ctl00$MainContent$ddlStatus=M` (M = License Master, W = Workers' Comp, P = Personnel) with `__VIEWSTATE` and `__EVENTVALIDATION`.
  3. POST `__EVENTTARGET=ctl00$MainContent$lbMasterCSV`.
  4. The server returns a 302 to `/OnlineServices/DataPortal/DownLoadFile.ashx?fName=MasterLicenseData&type=C`, served as `text/csv` with **no Content-Length** (chunked).
  - A full stream (session cookie kept, 300 s timeout) returned **57,079,888 bytes and 179,087 CSV rows including the header** and took about 2+ minutes.
  - Requesting `fName=WorkersCompData` without first selecting "W" in the same session returned 0 bytes. Each file therefore needs its own dropdown postback.
  - `fName=PersonnelData&type=C` streamed correctly.
  — [CSLB ContractorList](https://www.cslb.ca.gov/onlineservices/dataportal/ContractorList) (live probe)
- **License Master CSV columns (verified):** LicenseNo, LastUpdate, BusinessName, BUS-NAME-2, FullBusinessName, MailingAddress, City, State, County, ZIPCode, BusinessPhone, **BusinessType** (e.g. Sole Owner), IssueDate, ReissueDate, ExpirationDate, InactivationDate, ReactivationDate, PrimaryStatus, SecondaryStatus, **Classifications(s)**, AsbestosReg, WorkersCompCoverageType, **WCInsuranceCompany, WCPolicyNumber**, WC effective/expiry/cancel/suspend dates, contractor bond (CB), worker bond (WB) and disciplinary bond (DB) surety, number, dates and amount, plus NAME-TP-2. — live file header
- **Personnel CSV columns (verified):** LIC-NO, LastUpdated, REC-TP, SEQ-NO, Name-TP, Name, EMP-Titl-CDE (Officer / Responsible Managing Officer / RME), CL-CDE, association and disassociation dates, qualifier bond, JointVenture licence type and number. Names are fixed-width "LAST FIRST MIDDLE". — live file header

**Florida DBPR (free CSV extracts, behind Cloudflare)**
- The Construction Industry "Public Records" page publishes licensee files covering active, inactive and voluntarily inactive licensees. Fields: Board Number, Occupation Code, Licensee Name, **Doing Business As Name**, Class Code, address, County Code, License Number, primary and secondary status, original licensure date, effective and expiry dates. — [DBPR Construction Industry public records](https://www2.myfloridalicense.com/construction-industry/public-records/) (snippet)
- Extract URLs from the search index: `https://www2.myfloridalicense.com/sto/file_download/extracts/CONSTRUCTIONLICENSE_1.csv` and `.../cilb_registered.csv`. From the research machine both returned HTTP 403 with a Cloudflare challenge; they may need a US IP or a browser session. — [cilb_registered.csv](https://www2.myfloridalicense.com/sto/file_download/extracts/cilb_registered.csv)

**Texas (free)**
- "TDLR – All Licenses" (`7358-krk7`): **1,007,729 rows (API)**, updated 2026-09-19. Columns: license_type, license_number, business_name, business address and county, owner_name, mailing address, license_subtype, expiry. Construction-relevant counts (API): **Electrical Contractor 14,019; A/C Contractor 20,436**; Master Electrician 19,927; Electrical Sign Contractor 655; Appliance Installation Contractor 830. — [data.texas.gov 7358-krk7](https://data.texas.gov/d/7358-krk7)
- **TSBPE "Free Licensee List"**: one CSV per credential type, no account needed (`/download-csv/RMP/`, `/MP/`, `/TP/`, `/PI/`, plus JP and PA zips). The **Responsible Master Plumber** file has **PLUMB_COMPANY** and INSURANCE_COMPANY plus the licensee's name and address. RMP.csv was about 1.99 MB on 2026-10-04. — [TSBPE Free Licensee List](https://tsbpe.texas.gov/free-licensee-list/)

**Virginia DPOR (free)**
- "Regulant lists are provided free of charge in electronic format." Contractor files:
  - `2705a__crnt.txt`, `2705b__crnt.txt`, `2705c__crnt.txt` for Class A, B and C contractors.
  - `2701` (Class A), `2703` (temporary), and tradesman files `2710`, `2717`, `2718`.
  - URL pattern: `https://www.dpor.virginia.gov/sites/default/files/Records%20and%20Documents/Regulant%20List/<code>__crnt.txt`.
  — [DPOR Records & Documents](https://www.dpor.virginia.gov/RecordsandDocuments); [DPOR Regulant Lists](https://www.dpor.virginia.gov/RegulantLists)
- Tab-delimited header (verified): BOARD, OCCUPATION, CERTIFICATE #, INDIVIDUAL NAME, BUSINESS NAME, address fields, EXPIRATION DATE, CERTIFICATION DATE, LICENSE RANK (A/B/C), **LICENSE SPECIALTY** (e.g. CBC, RBC, ELE, HVA codes), EMAILADDRESS. `2701__crnt.txt` was 504 KB. A secondary source says the lists refresh about every 5 business days. — live file; [Apify description](https://apify.com/scrapebench/virginia-contractor-license-lookup)

**Minnesota DLI (free, nightly)**
- "Download registration data – This export file includes all registrations… updated nightly." Files:
  - `MNDLILicRegCertExport_Contractor_Registrations.csv` (4.45 MB, last-modified 2026-10-04)
  - `…_Residential_Contractors.csv`, `…_Electrical.csv`, `…_Plumbing.csv`, `…_Mechanical_Contractor_Bond.csv`, `…_High_Pressure_Piping.csv`
  - a combined `MNDLILicRegCertExport.zip`
- Columns (verified): Bus_Pers, License_Type, License_Subtype, Name, **DBA_Name**, address, phone, email, Lic_Number, Status, Orig_Date, Exp_Date, Enforcement_Action.
— [DLI contractor registration](https://www.dli.mn.gov/business/construction-contractor-registration); [DLI lookup page](https://www.dli.mn.gov/license-and-registration-lookup)

**Oregon (free)**
- "CCB Active Licenses" (`g77e-6bhs`): **56,494 rows (API)**. Columns: license_number, license_type, full_name, address, county, original registration date, licence expiry, bond company, amount and expiry, insurance company, amount and expiry, **rmi_name** (responsible managing individual), endorsement_text. Active licences only.
- "Building Codes Division – Active Contractor/Individual Licenses" (`vhbr-cuaq`) covers trade licences.
— [data.oregon.gov g77e-6bhs](https://data.oregon.gov/d/g77e-6bhs); [vhbr-cuaq](https://data.oregon.gov/d/vhbr-cuaq)

**Washington L&I (free; already ingested by the project)**
- "Contractor License Data – General" (`m8qx-ubtq`): **161,164 rows (API)**, including UBI, specialties and primary principal.
- "Principal Data" (`4xk5-x9j6`): **250,718 rows (API)**, giving principal names with start and end dates per UBI, which is useful for ownership history.
- "Authorized Signer" (`s7ge-wicw`), "Insurance" (`ciwg-agsx`: insurer, policy number, dates) and "Bond" (`bzff-4fmt`). The data updates three times a day.
— [data.wa.gov m8qx-ubtq](https://data.wa.gov/d/m8qx-ubtq); [4xk5-x9j6](https://data.wa.gov/d/4xk5-x9j6); [L&I public records](https://www.lni.wa.gov/agency/public-disclosure/)

**New York**
- NYC "DOB License Info" (`t8hj-ruu2`): **103,251 rows (API)**. Columns: license_type, license_number, last and first name, **business_name**, business address, license_status. **GENERAL CONTRACTOR 34,661**; Electrical Firm 5,546; Electrical Contractor 5,105; Master Plumber 3,007; Site Safety 3,206; Superintendent of Construction 11,082; Fire Suppression Contractor 1,134. — [NYC Open Data t8hj-ruu2](https://data.cityofnewyork.us/d/t8hj-ruu2)
- NYS DOL "Contractor Registry Certificate" (`i4jv-zkey`), the public-works contractor registry: **14,899 rows (API)**. Columns: business_name, **dba_name**, **business_officers**, address, issued and expiry dates, status, debarment fields, whether a NYS DOL employer registration number or WCB employer number exists, workers'-comp insurance and exemption flags, and **"business_has_final_determination_safety_standard_violations"**. — [data.ny.gov i4jv-zkey](https://data.ny.gov/d/i4jv-zkey)

**Arizona ROC (free)**
- "Posting List" downloads:
  - All Current Contractors: 58,512 records, 12.46 MB
  - Commercial: 47,319 records
  - Residential: 47,707 records
  - Dual: 36,617 records
- Updated 2026-09-29. — [roc.az.gov/posting-list](https://roc.az.gov/posting-list) (snippet; Cloudflare blocked a direct fetch; fields not verified)

**Southeast boards**
- **Tennessee Board for Licensing Contractors**: a public Tableau dashboard of "Tennessee contractor and qualifying agent data", including the qualifying agents tied to each licensed contractor. "You can sort, search, or download this data" through View Data. — [TN verify-qa dashboard page](https://www.tn.gov/commerce/regboards/contractors/consumer/verify-qa.html) (fetched directly). No static bulk file was found; licence search runs on verify.tn.gov. — [TN BLC](https://www.tn.gov/commerce/regboards/contractors.html)
- **Alabama Licensing Board for General Contractors**: a "Download License Verification List (CSV)" at licensesearch.alabama.gov/genconbd, with name, licence number, city, state, specialty and phone. About 10,594 licensees. — [licensesearch.alabama.gov/genconbd](https://licensesearch.alabama.gov/genconbd); [roster](https://genconbd.alabama.gov/DATABASE-SQL/roster.aspx) (snippet; host refused connection)
- **Georgia (SOS Professional Licensing Boards)**: rosters are purchased by mailed form. All boards cost $3,000; the Residential & General Contractors **company** roster costs $100 and the individual roster $25. **Delivered on CD only.** Free single-record lookup is at verify.sos.ga.gov. — [GA Licensing Division Rosters](https://sos.ga.gov/licensing-division-rosters); [roster request form 07/31/25](https://sos.ga.gov/sites/default/files/forms/Paper_Roster_Form_07.31.25.pdf) (snippet)
- **South Carolina LLR Contractor's Licensing Board**: roster by request with a **$10 fee**, sent by email or mail. Lookup at verify.llronline.com. — [llr.sc.gov/clb](https://llr.sc.gov/clb/) (snippet)
- **North Carolina Licensing Board for General Contractors**: public search at portal.nclbgc.org; county rosters on written request to info@nclbgc.org (snippet). No bulk download was found. — [NCLBGC public search](https://portal.nclbgc.org/Public/Search); [NCLBGC FAQ](https://nclbgc.org/faq-contractors/). No bulk file was found for the **NC electrical board (NCBEEC)** either. — [ncbeec.org](https://www.ncbeec.org/board-information/)

**Other states**
- **Nevada NSCB**: listings of active contractors are free online. Specialty lists cost **$100 (≤500 records) or $200 (>500)** in Excel or PDF, with business name, licence number, status, expiry, classification, monetary limit, address and phone. — [NSCB Contractor List Request (2023 PDF)](https://www.nvcontractorsboard.com/wp-content/uploads/2023/06/Contractor-List-Request.pdf) (older source)
- **Louisiana LSLBC**: search only, by name, licence, parish, type or qualifying party. No downloadable list was found. — [lslbc.gov contractor search](https://lslbc.gov/contractor-search/)
- **Michigan LARA**: residential builder licensing runs on Accela with a verify-a-licence page. No bulk download was found. — [LARA Residential Builders](https://www.michigan.gov/lara/bureau-list/bcc/sections/licensing-section/residential-builders)

### Inferences
- **CSLB fix:**
  - Replicate the two-step postback with a persistent cookie jar.
  - Stream to disk with no client timeout (allow at least 10 minutes).
  - Check that the row count is about 179k and that the last LicenseNo parses.
  - Fetch Personnel and Workers' Comp in separate postbacks.
  - Personnel is the key file for matching sole proprietors and qualifiers (RMO/RME) to OSHA employer names.
  - Licences cancelled, or expired for more than 5 years, are absent, so renamed or sold companies from early in the 2016–2026 OSHA window may be missing.
- **Ingest priority for licence data:**
  1. FL DBPR (DBA field, high OSHA volume)
  2. TX TDLR and TSBPE (no state GC licence exists in TX, so electrical, A/C and plumbing are the only licensed trades)
  3. VA DPOR
  4. NYC DOB and NYS DOL Contractor Registry
  5. MN DLI (DBA field)
  6. AZ ROC
  7. AL CSV
  8. TN Tableau export
  9. GA and SC rosters by purchase or request.
- Licence files carrying **qualifier or responsible-person names** help with corporate families and sole proprietors, because one person can link several entities: CSLB Personnel, OR CCB rmi_name, WA principals, TN qualifying agents, LA qualifying-party search.
- From general knowledge, not verified here: Texas has no statewide general-contractor licence.

### Gaps
- The FL DBPR file layout, row counts and exact file list were not verified (Cloudflare 403).
- No verified bulk source was found for: NC electrical and plumbing boards, GA field layout, UT DOPL, NM CID, HI PVL, NJ home-improvement contractors, PA home-improvement contractors (Attorney General registry), and the Ohio OCILB commercial trades.
- The TN Tableau download may be capped per view; not tested.

---

## 3. Workers' compensation coverage and proof-of-coverage databases: FEIN, policyholder names, bulk data

### Takeaway
NCCI proof-of-coverage data is restricted to regulators. Four states publish **bulk** WC employer lists: **TX DWC** (2.07M subscriber rows plus 106.7k non-subscribers), **OR** (131k active employers with legal name, DBA, NAICS and insurer), **FL DFS** (downloadable POC and construction exemption lists, searchable by FEIN), and **CA CSLB** (WC insurer and policy number per licence). **No bulk file found exposes FEIN.** NY WCB, CA WCIRB and FL DFS accept FEIN as a search key, but only for single lookups.

### Cited Findings
- **NCCI POC.** NCCI provides proof-of-coverage services in 38 states as daily IAIABC EDI or NCCI files to state boards. The POC Inquiry (search by name, policy, **FEIN** or address) is available to "regulators, industrial commissions, and accident boards". States listed: AK, AL, AR, AZ, CO, CT, DC, FL, GA, IA, ID, IL, IN, KS, KY, LA, MD, ME, MO, MS, MT, NE, NH, NM, NV, NY, OK, OR, RI, SC, SD, TN, TX, UT, VA, VT, WV. — [NCCI POC Inquiry](https://www.ncci.com/ServicesTools/Pages/POC.aspx); [NCCI POC service](https://www.ncci.com/ServicesTools/Pages/PROOFOFCOVERAGE.aspx) (snippet)
- **Texas DWC (free, data.texas.gov).**
  - "Workers' compensation insurance coverage subscriber information" (`c4xz-httr`): **2,068,377 rows (API)**, published quarterly. Columns: insured_employer_name and address, business_market, PEO flag, ncci_coverage_provider_id, policy effective, expiry and cancellation dates, **governing_class_code, sic_code_naics_code**, state_standard_premium, coverage_provider_name. **No FEIN.**
  - "Non-subscriber employer information" (`azae-8krr`): **106,724 rows (API)**, monthly. Columns: company_name, address, start and end dates.
  — [data.texas.gov c4xz-httr](https://data.texas.gov/d/c4xz-httr); [azae-8krr](https://data.texas.gov/d/azae-8krr)
- **Oregon (free).** "Oregon Active Workers' Compensation Employer Database" (`q9zj-c8r2`): **131,357 rows (API)**, updated monthly. Columns: employer_num, **legal_business_name, dba_name**, ownership, **naics**, employees_range, principal-place-of-business and mailing addresses, insurer, liability begin and end dates, ncci_code. No FEIN. — [data.oregon.gov q9zj-c8r2](https://data.oregon.gov/d/q9zj-c8r2)
- **Florida DFS Division of Workers' Compensation.**
  - **Proof of Coverage Database**: "will produce a downloadable list of employers… whose WC insurance policies have been reported… within the past 5 years". It can be narrowed by employer name, **FEIN**, policy number, dates or county.
  - **Exemption Search**: searches by name, employer name, **FEIN** or SSN and returns a downloadable file of corporate officers and LLC members exempt from WC, with a **Construction / Non-Construction** filter. It includes historical exemptions.
  - "Digital Download (Policy Data)": export by employer-name initial, policy-date range (2016–2027) and county, as Text or Excel.
  - The portal also hosts a **Stop-Work Order Database** and a Construction Policy Tracking database.
  — [FL DFS Exemption Search](https://dwcdataportal.fldfs.com/Exemption.aspx); [FL DFS POC Data](https://dwcdataportal.fldfs.com/POCData.aspx); [Digital Download](https://dwcdataportal.fldfs.com/DigitalDownload.aspx) (all fetched directly)
- **Tennessee**: the Workers' Compensation Exemption Registry, run with the SOS, lets construction services providers register an exemption: sole proprietors, corporate officers, or LLC members and partners with at least 20% ownership. Searchable at tnbear.tn.gov/WC/WCFillingSearch.aspx. — [TN WC exemptions](https://www.tn.gov/workforce/injuries-at-work/employers/employers/who-must-carry-insurance/exemptions.html); [Registry FAQs](https://www.tn.gov/workforce/injuries-at-work/employers/employers/wc-exemption-registry/exemption-registry-forms-and-faqs.html) (snippet). No bulk export was found.
- **New York WCB**: "NY Employer Coverage Search" by employer name, **FEIN (9 digits)**, policy number or WCB employer number. It shows WC, disability and paid-family-leave coverage history. Free, single lookup only. "A firm's FEIN is the Board's primary identification for that business." — [wcb.ny.gov/icpocinq](https://www.wcb.ny.gov/icpocinq/) (snippet). The NY WCB claims dataset on data.ny.gov (`jshw-gkgu`) has **no employer name or ID**: its columns are carrier, industry code, injury codes and zip. — [data.ny.gov jshw-gkgu](https://data.ny.gov/d/jshw-gkgu)
- **California WCIRB**: Coverage Inquiry (caworkcompcoverage.com) by FEIN or employer name for any date in the last 5 years, single lookup only. "The WCIRB's FEIN records are not complete." — [CA WC Coverage Inquiry](https://www.caworkcompcoverage.com/); [WCIRB coverage research](https://www.wcirb.com/products-and-services/products-and-services/coverage-research) (snippet)
- **CSLB License Master** carries WorkersCompCoverageType, WCInsuranceCompany, **WCPolicyNumber** and dates for every licence. — live CSLB file header (Section 2)
- **WA L&I**: the contractor insurance dataset (`ciwg-agsx`) gives insurer, policy number and dates keyed by UBI. — [data.wa.gov ciwg-agsx](https://data.wa.gov/d/ciwg-agsx)

### Inferences
- **Florida is the strongest WC source for matching.** The FEIN-searchable POC and exemption exports can confirm an entity's EIN and its officer names, which helps with sole proprietors who hold construction exemptions. Combined with the Sunbiz FEI field, this gives a FEIN link in Florida.
- Texas DWC and Oregon WC lists add **NAICS and class code** to employer names, which helps separate same-name companies in different industries.
- The Oregon WC list adds legal-name-to-DBA pairs.
- For the Nashville demo, TN WC exemption-registry lookups could confirm sole proprietors and officers, but only one at a time.

### Gaps
- Whether the FL DFS downloadable POC and exemption files *display* FEIN (as opposed to accepting it as a search filter) was not confirmed.
- No bulk WC data was found for GA, NC, AL, SC, OH, PA, IL or NJ.
- NCCI POC is unavailable to non-regulators; no public licensing path was found.

---

## 4. State unemployment-insurance employer lists and tax-registration lists

### Takeaway
UI employer identities are **confidential by federal regulation**, so no state UI employer list is public. Tax-registration lists are public only where a state chooses to publish them. Texas does, through the Comptroller franchise-tax and sales-tax permit files on data.texas.gov.

### Cited Findings
- 20 CFR Part 603 requires state law to keep confidential any UC information that "reveals the name or any identifying particular about any… past or present employing unit". Employer information includes "name, address, State, and the Federal employer identification number". Disclosure is limited to defined exceptions such as subpoena or court order. — [eCFR 20 CFR 603](https://www.ecfr.gov/current/title-20/chapter-V/part-603); [Federal Register 2023 rule](https://www.federalregister.gov/documents/2023/07/25/2023-15631/federal-state-unemployment-compensation-uc-program-confidentiality-and-disclosure-of-state-uc)
- **Texas Comptroller**:
  - Active Franchise Taxpayers: 3,484,555 rows, with SOS file number.
  - Active Sales Tax Permit Holders: 888,901 outlets, with outlet name and NAICS; 45,676 construction outlets.
  - Both free on data.texas.gov. — [9cir-efmm](https://data.texas.gov/d/9cir-efmm); [jrea-zgmq](https://data.texas.gov/d/jrea-zgmq)
- The NYS DOL Contractor Registry publishes only a **flag** for whether a business has a NYS DOL employer registration number, not the number itself. — [data.ny.gov i4jv-zkey](https://data.ny.gov/d/i4jv-zkey)
- Washington's DOR/BLS merged licence list on data.wa.gov dates from 2015 and is stale. — [data.wa.gov hw7n-fcif](https://data.wa.gov/d/hw7n-fcif) (catalog listing, data updated 2015-03-14)

### Inferences
- Do not plan on UI employer files.
- Texas tax files are the only large free tax-registration source found. They are high value because TX is the top OSHA construction state.
- Delaware business licences (69k, with trade names) are a smaller analogue.

### Gaps
- Public sales-tax or business-licence registrant lists were not surveyed for FL, GA, TN, NC, OH, PA or IL. For example, FL DOR and TN DOR have no sales-tax permit list confirmed as published.

---

## 5. State-plan OSHA programs: own employer data with identifiers

### Takeaway
**Washington DOSH inspections in the federal OSHA bulk data carry the WA L&I inspection number inside `estab_name`** (e.g. `WA317981395 - TEAM CAR CARE LLC`). L&I's public Verify system indexes those inspection numbers by **UBI**. This gives an identifier bridge to the WA L&I contractor data (UBI) that the project already ingests. No other state plan embeds an identifier this way in the federal file. Oregon OSHA publishes only annual aggregates.

### Cited Findings
- In the project's OSHA inspection bulk file (`data/raw/inspection/*.csv`, DOL load 2026-10-02):
  - **57,508 inspection rows** have `ESTAB_NAME` matching `WA<9-digit number> - <name>`.
  - **21,471 of them are construction (NAICS 23) opened in 2016 or later.**
  - No other two-letter state prefix appears in this pattern.
  - Examples: activity 347699167, "WA317981395 - TEAM CAR CARE LLC", Bellingham; activity 346601073, "WA317973267 - AXABRA LLC", Spokane.
  — local analysis of `/Users/peterhyland/Desktop/GitHub/site-safety-intelligence/data/raw/inspection/`
- WA L&I Verify serves DOSH citation documents keyed by inspection number **and UBI**: `secure.lni.wa.gov/verify/Details/CitationDocument.aspx?InspectionNo=317973267&...&UBI=603349128`. The inspection number matches the OSHA estab_name prefix above. — [L&I Verify citation document (317973267)](https://secure.lni.wa.gov/verify/Details/CitationDocument.aspx?InspectionNo=317973267&LIC=&SAW=&UBI=603349128+&VIO=); [another (317981395, UBI 604285029)](https://secure.lni.wa.gov/verify/Details/CitationDocument.aspx?LIC=&UBI=604285029&SAW=&VIO=&InspectionNo=317981395)
- "DOSH inspection results are public information and will be posted online" at secure.lni.wa.gov/verify. A bulk DOSH inspection dataset was not found on data.wa.gov; bulk records go through L&I public-records requests, which can be filed by UBI. — [L&I public records](https://www.lni.wa.gov/agency/public-disclosure/) (snippet)
- Oregon OSHA's only dataset on data.oregon.gov (`xc4e-hg3n`) has **36 rows of annual aggregates**: year, inspections, citations, violations, penalties. It has no employer-level data. — [data.oregon.gov xc4e-hg3n](https://data.oregon.gov/d/xc4e-hg3n)
- No state-plan employer datasets with identifiers were found on the Socrata catalog for Cal/OSHA, MIOSHA or other state plans; searches for "OSHA" and "occupational safety inspections" returned none. — [Socrata catalog API](https://api.us.socrata.com/api/catalog/v1?q=OSHA&only=dataset)

### Inferences
- **High-value, low-cost win for WA.** Parse the `WA\d+ - ` prefix:
  1. Strip it to clean the employer name (it currently pollutes name matching).
  2. Keep the L&I inspection number.
  3. Resolve the UBI either by looking up each candidate contractor's UBI in L&I Verify, which lists that business's DOSH inspections, or by a one-off public-records request for the DOSH inspection-number-to-UBI table.
- With the UBI resolved, the 21k WA construction inspections join deterministically to the L&I licence, principal and signer tables already in the warehouse. **(Inference: whether the Verify contractor page lists every DOSH inspection by UBI was not tested here.)**
- State-plan inspections from CA, OR, MI, KY, SC, TN, NC, etc. appear in the same federal OIS data. TN, KY, SC and NC are all state-plan states in the Southeast. None of them showed an identifier prefix, so they need the same name/address matching as federal-state records.

### Gaps
- No Cal/OSHA, TOSHA (TN), NC OSH, SC OSHA, KY OSH or MIOSHA employer-level bulk data with state identifiers was found.
- The coverage of L&I Verify's inspection-by-UBI listing, and whether L&I would supply a bulk inspection-to-UBI extract, are unconfirmed.
