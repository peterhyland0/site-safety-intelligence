# Company-identity, firmographic, place and corporate-ownership databases for matching US construction subcontractors to OSHA inspection records

Scope: non-government aggregators, ownership data, SEC and GLEIF. Research date: 2026-10-04. "Live test" means a query I ran on 2026-10-04 against a public API (GLEIF API, SEC data.sec.gov / EDGAR archives, Wikidata Query Service, OSM taginfo). Prices are as of 2026 unless flagged. Where a price comes only from a third-party comparison site or a search-result snippet, it is flagged as such.

## 1. OpenCorporates: 2026 API tiers and prices, free/public-benefit access, bulk data, US coverage, officers, previous/alternative names, network data, licence obligations

### Takeaway
OpenCorporates is not free for this project in practice. Free access is limited to public-benefit users (journalists, NGOs, academics), and "corporations" are explicitly excluded. Free use also brings ODbL share-alike. Paid self-serve plans run £2,250–£12,000/yr but allow only 500–5,000 calls/month. That is far too few for batch matching, so bulk data (Enterprise, custom price) is the only realistic paid route. The data model is a strong fit (all 50 states + DC, typed previous names and trading names, SEC-derived subsidiary relationships), but the US relationship data mostly repeats SEC Exhibit 21.

### Cited Findings
- **Self-serve plans (annual):** Essentials £2,250/yr (£225/mo), up to 500 API calls/month and 200/day. Starter £6,600/yr (£660/mo), 2,500/month and 500/day. Basic £12,000/yr (£1,200/mo), 5,000/month and 1,000/day. All three allow "Internal & external use". — [OpenCorporates pricing](https://opencorporates.com/pricing/)
- **Enterprise:** custom price. Includes "Bulk-data delivery", API access, internal and external use, the choice of "only the jurisdictions you require", and a chosen delivery frequency. — [OpenCorporates pricing](https://opencorporates.com/pricing/)
- **Effective cost per call:** about £0.375 (Essentials) to £0.20 (Basic). "A call counts whether or not the response contains a match". Typical verification takes 2–4 calls per company. (Third-party analysis dated 2 Feb 2026.) — [Zephira.ai](https://zephira.ai/opencorporates-pricing-explained-2026-plans-api-limits-licensing-and-what-it-means-in-production/)
- **Public-benefit access:** free at-scale data access for "investigative journalists, NGOs, universities and anti-crime-and-corruption research groups". Projects must "improve the use, quality and understanding of legal-entity data" or serve "the greater good". — [OpenCorporates pricing](https://opencorporates.com/pricing/)
- **Terms of use, eligibility:** Permitted Users for free access are the public (website, personal use) plus journalists, NGOs and academics doing public-benefit research. "financial institutions, corporations, government departments and regulatory authorities" are explicitly excluded. OpenCorporates reserves discretion over eligibility. — [OpenCorporates Terms of Use](https://opencorporates.com/terms-of-use-2/)
- **Terms of use, licence:** the database is under the **ODbL**. Attribution must be a "from OpenCorporates" hyperlink, at no less than 70% of the largest font or 7px. Users must "share any improvements you make to our databases under the ODbL". Combined data must be published under ODbL share-alike. Non-share-alike licences are available by paid contract. Automated scraping and "Extracting large volumes of data over a short period of time" are prohibited. — [OpenCorporates Terms of Use](https://opencorporates.com/terms-of-use-2/)
- **ODbL share-alike trigger:** "If you publicly use any adapted version of this database, or works produced from an adapted database, you must also offer that adapted database under the ODbL". Any public use must be attributed. — [ODbL summary, Open Data Commons](https://opendatacommons.org/licenses/odbl/summary/)
- **API docs on free use:** free API access requires the product or database that uses the data to be "released under an open licence (specifically share-alike attribution...)". Paid accounts remove the share-alike restriction on database rights. The default unauthenticated limit is **200 requests/month and 50/day**. — [OpenCorporates API Reference](https://api.opencorporates.com/documentation/API-Reference)
- **Website restrictions since 1 Aug 2023:** directors/officers, beneficial owners, source-registry links, filings, incorporation data and company status are shown only to registered users. This was to curb harvesting "for commercial or unlawful purposes". — [OpenCorporates Knowledge base](https://knowledge.opencorporates.com/knowledge-base/website-data-access-changes/)
- **Company object fields:** `previous_names` (name, type, dates); `alternative_names` (with a type); `branch` (F = foreign, L = local) and `home_company`; `alternate_/previous_/subsequent_registration_entities`; `registered_address`; `industry_codes`; `identifiers`; `officers`; `corporate_groupings`; `controlling_entity`; `ultimate_beneficial_owners`; `ultimate_controlling_company`; `source` provenance.
  - Company search supports `normalise_company_name`, searching `previous_names` through `fields`, `registered_address`, `inactive`, `branch` and `industry_codes` filters, and wildcards.
  - There is an OpenRefine reconciliation API.
  - [OpenCorporates API Reference](https://api.opencorporates.com/documentation/API-Reference)
- **Alternative-name types:** Trading (DBA/trading styles), Abbreviation, Legal (other language), Alias, Unknown and Transliteration. — [OpenCorporates Glossary](https://knowledge.opencorporates.com/knowledge-base/glossary-of-terms/) (via search snippet)
- **US coverage:** registers for all 50 states + DC. Examples: California about 8.62M companies and 28.4M officers; Texas about 7.02M companies and 19.7M officers; Delaware about 5.40M companies and 5.37M officers. Some states, e.g. Illinois and New Jersey, show no officer counts. — [OpenCorporates registers](https://opencorporates.com/registers)
- **Relationships:** after de-duplication, 39.7M relationship records globally: 12.8M control statements, 8.7M share parcels, 3.6M subsidiaries, 14.9M branches. About 13.7M of them are US. US subsidiaries are "Derived from the Securities and Exchange Commission Archives". Last updated 29 May 2025. — [OpenCorporates Knowledge base: Relationship File](https://knowledge.opencorporates.com/knowledge-base/count-of-relationship-records/)
- **Bulk files (six):** Companies, Officers, Non-Registered Addresses, Alternative Names, Additional Identifiers, and Relationships (branches, subsidiaries, control statements, share parcels). Uncompressed sizes range from 0.06GB to 77GB. — [OpenCorporates Bulk Files Explained](https://knowledge.opencorporates.com/knowledge-base/bulk-files-explained/)
- **"API + Relationships File" workflow (Oct 2025):** find the company via the API, then expand up and down through the Relationships File. Pricing is by contact only. — [OpenCorporates blog, 28 Oct 2025](https://blog.opencorporates.com/2025/10/28/opencorporates-api-plus-relationships-file/)
- **GLEIF mapping:** GLEIF publishes an OpenCorporates-ID-to-LEI mapping file. — [GLEIF concatenated files](https://www.gleif.org/en/lei-data/gleif-concatenated-file/download-the-concatenated-file)
- **US beneficial ownership context (June 2026 blog):** the title says the GAO is "still finding ownership when 99% of companies have gone dark", meaning US domestic BOI data is not available. — [OpenCorporates blog, 10 Jun 2026](https://blog.opencorporates.com/2026/06/10/government-accountability-office-finding-ownership/)

### Inferences
- The project's earlier belief ("needs a paid key") is broadly right. A GC-facing tool built by a company or individual for commercial use falls outside "Permitted Users", who exclude corporations. Free access would need either a genuine academic/NGO public-benefit framing or a paid licence.
- If free/public-benefit access were granted, the OSHA→OpenCorporates linkage table would probably count as an adapted database. Using it publicly (showing matches to GCs) would then oblige releasing that table under ODbL, with "from OpenCorporates" attribution on screen. OSHA data is itself public, so releasing the linkage table might be acceptable. But it would also expose any derived corporate-family groupings.
- Self-serve quotas (at most 5,000 calls/month on Basic) cannot support re-matching hundreds of thousands of OSHA construction employer names. Only Enterprise bulk delivery for selected US states (price unknown) fits a batch pipeline. Per-subcontractor lookups at GC entry time (a few per subcontractor) could fit Starter or Basic.
- The useful parts for the listed failures are:
  - `previous_names` for renamed companies;
  - `alternative_names` of type Trading for DBAs, where states supply them;
  - `branch`/`home_company` for foreign-qualified entities. For example, a Colorado Hensel Phelps registration in other states would appear as foreign branches linked to the home company.
  - US subsidiary relationships mostly duplicate SEC Exhibit 21, which is free directly from EDGAR.

### Gaps
- No 2026 price was found for Enterprise/bulk US-only data. OpenCorporates publishes none.
- I could not confirm which US states supply DBA/assumed names as `alternative_names`, or how many US companies have `previous_names`.
- I could not find the current turnaround or approval criteria for public-benefit applications.

## 2. GLEIF LEI: free golden copy, Level 2 parent data, share of US construction firms with LEIs, usefulness for corporate families

### Takeaway
GLEIF is free (CC0), current (updated three times daily) and has a good open API. It is nearly useless for small subcontractors, and weak even for big contractors' families. US construction subsidiaries and divisions rarely have their own LEIs, so Level 2 child lists for D.R. Horton, Quanta, MasTec, Comfort Systems, Kiewit and Turner are empty or near-empty. Its real value is as a bridge identifier (LEI ↔ state registry file number ↔ OpenCorporates ID ↔ Wikidata) for large firms.

### Cited Findings
- **Golden Copy:** published three times daily, with Level 1 (LEI-CDF), Level 2 Relationship Records (RR-CDF) and Level 2 Reporting Exceptions. Delta files cover the last 8h, 24h, 7 days and 31 days. RDF is available through data.world. — [GLEIF Golden Copy](https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy)
- **Concatenated files as of 2026-10-04:** LEI-CDF v3.1 has 3,451,839 records (518.79 MB). RR-CDF v2.1 has 672,251 relationship records (35.96 MB). Reporting Exceptions has 6,230,385 records. Mapping files cover BIC, ISIN, MIC, **OpenCorporates ID**, QCC and GEM IDs to LEI. — [GLEIF concatenated files](https://www.gleif.org/en/lei-data/gleif-concatenated-file/download-the-concatenated-file)
- **Licence:** CC0. — [GLEIF Open Data / LEI Data Terms of Use](https://www.gleif.org/en/meta/lei-data-terms-of-use) (via search snippet)
- **Q1 2026 population:** 3.02M active LEIs, 3.26M including retired. "Over 3.13 million LEI registrants – representing 99% of the total active LEI population – reported information on their direct and ultimate parents". That figure includes reporting exceptions such as "no parent" or "parent has no LEI". — [GLEIF blog, Q1 2026](https://www.gleif.org/en/newsroom/blog/the-lei-in-numbers-active-lei-population-surpasses-3-million-in-q1-2026)
- **US count:** 361,244 US LEI records, with 2,249 new US LEIs in a 30-day period in early Sept 2026. This came from a search-result summary of third-party LEI-statistics sites and was not verified at GLEIF. — [rapidlei stats](https://rapidlei.com/stats/); [lei-registry stats](https://lei-registry.com/lei-statistics)
- **Level 1 names:** `OtherEntityNames` lists "all types of names other than the Primary Legal Name" (e.g. trading names and previous legal names). `SuccessorEntity` (SuccessorLEI or name) records mergers and replacements. — [GLEIF LEI-CDF 3.1](https://www.gleif.org/en/lei-data/access-and-use-lei-data/level-1-data-lei-cdf-3-1-format) (via search snippet)
- **Live test, LEIs (GLEIF API `filter[fulltext]`/`filter[entity.names]`, US):**
  - "Hensel Phelps": 0 results.
  - "Lobar": 0 results.
  - "Hagerman": only a Swedish firm and two Michigan family trusts, no construction firm.
  - Turner Construction Company has an LEI.
  - Kiewit Corporation has an LEI.
  - Bechtel Corporation and several Bechtel entities have LEIs.
  - D.R. Horton, Inc. has LEI 529900ZIUEYVSB8QDD25. Its registration-authority fields are RA000602 / 2267254, the Delaware file number. MasTec's are RA000603 / P98000032690.
  - [GLEIF API](https://api.gleif.org/api/v1/lei-records)
- **Live test, Level 2 ultimate children (GLEIF API `/ultimate-children`):**
  - D.R. Horton: 1 (DHI Mortgage Company, Ltd.).
  - Lennar: 5, all financial or holding LP/LLCs.
  - Bechtel Corp: 3.
  - Quanta Services, MasTec, Comfort Systems USA, EMCOR Group, Kiewit Corp and Turner Construction: **0**.
  - [GLEIF API, D.R. Horton example](https://api.gleif.org/api/v1/lei-records/529900ZIUEYVSB8QDD25/ultimate-children)
- **Search tooling:** the API offers fuzzycompletions/autocompletions endpoints. My live fuzzy test returned nothing for "DR Horton Inc", so name search is brittle with punctuation. — [GLEIF API](https://api.gleif.org/api/v1/fuzzycompletions)

### Inferences
- US LEIs exist mainly where a regulation demands them (securities issuers, derivatives counterparties, funds and trusts). Small and mid-size construction subcontractors almost never have one. My tests found none for Hagerman, Lobar or Hensel Phelps (a large private GC). A very rough bound: about 361k US LEIs against tens of millions of US businesses.
- The share of US construction firms with LEIs cannot be computed directly, because LEI records carry no NAICS or SIC code. My spot checks suggest roughly zero for small subcontractors and partial coverage for the top public and largest private contractors.
- Level 2 adds nothing for the D.R. Horton and Hensel Phelps family problem. Divisional entities like "D.R. Horton, Inc. - Greensboro" have no LEIs.
- The best uses are:
  1. a free, clean legal name plus state file number for big firms, which can be joined to SOS data;
  2. `OtherEntityNames`/`SuccessorEntity` for renames;
  3. a crosswalk to OpenCorporates IDs and Wikidata. Wikidata's P1278 holds LEIs for most of the public contractors tested; see section 4.

### Gaps
- I could not find a GLEIF-published US-only count, or any statistic on US construction-sector LEIs.
- I did not measure how often US records populate `OtherEntityNames` with trading or previous names.

## 3. SEC EDGAR: Exhibit 21 subsidiary lists, CIK/tickers, former names, parsed datasets (CorpWatch, sec-api, academic) for public homebuilders and contractors

### Takeaway
EDGAR is the best free source for public contractors' families and renames.
- Exhibit 21 is not XBRL-structured, but it is easy to parse. For D.R. Horton it lists hundreds of subsidiaries, including the exact city-division entities ("D.R. Horton, Inc. - Greensboro") and a "Doing Business As" column of brand DBAs.
- The `formerNames` array in the submissions JSON gives dated legal-name history.
- Parsed Ex-21 datasets exist: CorpWatch (via OpenSanctions, CC BY-NC) and sec-api.io (commercial).

### Cited Findings
- **Exhibit 21 is unstructured:** it is not XBRL-tagged. XBRL US has advocated that "Subsidiary Listing reported on Exhibit 21" be digitally tagged. Current SEC Inline XBRL mandates cover financial statements, not Ex-21. — [XBRL International news](https://www.xbrl.org/news/xbrl-us-supports-expanded-digital-reporting-at-sec/); [XBRL US forum](https://xbrl.us/forums/topic/how-to-get-list-of-subsidiaries-for-a-company-in-a-filing/)
- **Live test, D.R. Horton FY2025 10-K Exhibit 21.1** (filed 2025-11-19, subsidiaries as of 30 Sept 2025):
  - The table has 617 rows. Its columns are NAME, STATE OF INCORPORATION and **DOING BUSINESS AS**, and 178 rows carry DBA text.
  - City-named divisional entities are listed as separate legal entities, e.g. "D.R. Horton, Inc. - Greensboro" (Delaware), "- Birmingham" (Alabama), "-Chicago", "- Denver", "- Jacksonville", "- Louisville", "- Portland", "- Minnesota", "- New Jersey".
  - Brand DBAs include Emerald Homes, Express Homes, Freedom Homes, Crown Communities, Westport Homes, Torrey Homes, Trimark Communities, Braselton Homes, Classic Builders and Terramor Homes.
  - [EDGAR: DHI Ex-21.1](https://www.sec.gov/Archives/edgar/data/882184/000088218425000081/a9302025ex211subsidiaries.htm)
- **Live test, EDGAR submissions JSON (`formerNames` with date ranges):**

  | Company | Former names (until) |
  |---|---|
  | EMCOR | JWP INC/DE/ (1994) |
  | Tutor Perini | PERINI CORP (2009) |
  | PulteGroup | PULTE HOMES INC (2010); PULTE CORP (2001) |
  | KB Home | KAUFMAN & BROAD HOME CORP (2001) |
  | Sterling Infrastructure | STERLING CONSTRUCTION CO INC (2022); OAKHURST CO INC (2002) |
  | IES Holdings | Integrated Electrical Services (2016) |
  | MYR Group | MYERS L E CO GROUP (1996) |
  | MasTec | BURNUP & SIMS INC (1994) |
  | Lennar | PACIFIC GREYSTONE CORP (1997) |
  | AECOM | AECOM TECHNOLOGY CORP (2015) |
  | Limbach | 1347 Capital Corp (2016, a SPAC) |
  | Primoris | Rhapsody Acquisition Corp (2008, a SPAC) |

  - D.R. Horton, Dycom, Granite, NVR and Fluor have none.
  - Some entries are case-only changes (e.g. Comfort Systems, MYR and Primoris in 2026).
  - SIC codes are present (e.g. 1531 Operative Builders; 1731 Electrical Work; 1623 Water, Sewer, Pipeline...).
  - [data.sec.gov submissions, e.g. CIK0000105634](https://data.sec.gov/submissions/CIK0000105634.json); [SEC company_tickers.json](https://www.sec.gov/files/company_tickers.json) (10,434 tickers on 2026-10-04)
- **CorpWatch API:** automated parsers pull subsidiary names, locations and hierarchy from Exhibit 21. The code is on GitHub and SQL/CSV database dumps are offered. In March 2010 it covered 2003–2010, with 625,766 filing companies processed and 1,181,039 relationships. — [GitHub michalgm/corpwatchapi](https://github.com/michalgm/corpwatchapi); [CorpWatch API FAQ](http://api.corpwatch.org/documentation/faq.html) (via search snippet; the api.corpwatch.org TLS certificate was invalid on 2026-10-04)
- **OpenSanctions "US CorpWatch EX-21 Filings":**
  - Coverage: 2003 onward, monthly updates. About 2.34M entities, of which 1.42M are companies.
  - Freshness: dataset version 20260914; last data change 31 Mar 2026.
  - Format: FollowTheMoney JSON (841 MB), with CSV via archive.org.
  - Licence: **CC BY-NC 4.0**; commercial users need a data licence.
  - [OpenSanctions us_corpwatch](https://www.opensanctions.org/datasets/us_corpwatch/)
- **sec-api.io Subsidiary API:**
  - Content: Exhibit 21 from 10-K, 10-Q, S-1 and 20-F filings, 2003 to present. Over 100,000 subsidiary lists, with about 7,000 new ones a year; includes delisted companies.
  - Fields: subsidiary name, jurisdiction, parent CIK/ticker/name, accession number and date.
  - Query by ticker, CIK or jurisdiction. Claims an error rate below 0.1%.
  - Pricing is not on the docs page.
  - [sec-api.io docs](https://sec-api.io/docs/subsidiary-api)
- **Academic use:** Dyreng and Hoopes compared Exhibit 21 foreign subsidiaries with IRS data for 2005–2013 and studied strategic non-disclosure. Ex-21 is not guaranteed complete. — [Dyreng & Hoopes, "Strategic Subsidiary Disclosure"](https://www.bauer.uh.edu/departments/accy/research/documents/Dyreng-Strategic-Subsidiary-Disclosure.pdf)

### Inferences
- **City-division names (D.R. Horton):** the OSHA pattern "DR HORTON INC GREENSBORO" is explained directly by DHI's Ex-21 entity "D.R. Horton, Inc. - Greensboro". Parsing Ex-21 for each public homebuilder or contractor gives an authoritative alias list, including city/region divisions and brand DBAs, keyed to the parent CIK. This is the strongest free fix for public-company families.
- **Which companies to cover:** for the named public contractors (DHI, LEN, PHM, NVR, TOL, KBH, EME, FIX, PWR, MTZ, DY, PRIM, TPC, GVA, STRL, LMB, IESC, MYRG, ACM, FLR), CIKs resolve from `company_tickers.json` and Ex-21 can be pulled per 10-K. Annual Ex-21 snapshots across 2016–2026 also capture acquisitions and disposals with dates.
- **Renames:** `formerNames` handles renames of the parent registrant only, not of subsidiaries. Subsidiary renames must be inferred by diffing successive Ex-21 lists, or taken from SOS/OpenCorporates `previous_names`.
- **Limits:** Ex-21 omits "insignificant" subsidiaries and covers only SEC registrants. Hensel Phelps, Kiewit, Turner (Hochtief-owned), Bechtel and most subcontractors are private and absent.

### Gaps
- No current price was found for sec-api.io's Subsidiary API. Its pricing page was not checked.
- The CorpWatch API host now has a certificate mismatch, so it is unclear whether CorpWatch itself still serves the API. OpenSanctions' copy is current to March 2026.
- I did not verify whether EDGAR full-text search or the SEC's financial-statement datasets carry any structured subsidiary data.

## 4. Wikidata (and LSEG Open PermID): company items, parents/subsidiaries, aliases, query service, usefulness for big firms

### Takeaway
Wikidata reliably covers the large public contractors, holding CIK, LEI, aliases and some former names. Its parent/subsidiary graph for US construction firms is very thin (0–5 subsidiaries per company in tests), so it is a crosswalk and alias source for the top firms, not a family-tree source. Open PermID (CC BY) has a free matching API but no free bulk download since 2021.

### Cited Findings
- **Properties:** P749 is "parent organization or unit" and P355 is "child organization or unit" (aliases "subsidiary company" etc.). Ownership share can be expressed with P127 plus the P1107 qualifier. — [Wikidata P355](https://www.wikidata.org/wiki/Property:P355); [Wikidata P749](https://www.wikidata.org/wiki/Property:P749)
- **Live test (Wikidata Query Service, items matched by CIK P5531):**
  - Found: 15 of 20 public construction or homebuilding companies.
    - D.R. Horton (Q5203782): 3 English aliases, LEI present, 0 subsidiaries.
    - Lennar: 1 alias, 0 subsidiaries.
    - PulteGroup: 2 aliases, 1 subsidiary.
    - AECOM: 5 subsidiaries.
    - Fluor: 1 subsidiary.
    - Quanta, MasTec, Comfort Systems, Granite, Tutor Perini, KB Home, Toll, Primoris and NVR: 0 subsidiaries, 0–1 aliases.
  - Not found by CIK: EMCOR, Dycom, Sterling, Limbach and MYR Group. They may exist without a CIK statement.
  - [Wikidata Query Service](https://query.wikidata.org/)
- **Licence:** Wikidata structured data is CC0. — [Wikidata:Licensing](https://www.wikidata.org/wiki/Wikidata:Licensing)
- **Open PermID:**
  - Licensed CC BY 4.0. LSEG discontinued the Entity Bulk Download and daily files on 8 Aug 2021, with "no alternative for the bulk offer on a free and open license".
  - Entity Search, Record Matching (including a Bulk Matching API) and Intelligent Tagging remain.
  - [LSEG Developer Community](https://community.developers.lseg.com/discussion/81593/permid-entity-bulk-download-support-is-ending-what-are-the-alternatives); [OpenSanctions PermID](https://www.opensanctions.org/datasets/permid/)

### Inferences
- Wikidata is useful for:
  1. joining CIK ↔ LEI ↔ ticker for big firms;
  2. a handful of English aliases and abbreviations (e.g. "DR Horton", "DHI");
  3. occasional historical names.
- For family trees of construction groups, Wikidata is weaker than Exhibit 21 by two orders of magnitude (DHI: 0 in Wikidata vs ~600 Ex-21 rows).
- Private large contractors (Kiewit, Bechtel, Hensel Phelps, Turner) may have items but rarely any subsidiaries listed. Small subcontractors are essentially absent.
- Open PermID's free Record Matching API could help with big-company name resolution. Without bulk data, though, it adds little beyond EDGAR plus GLEIF for this use case.

### Gaps
- I did not test Wikidata coverage of private top-400 contractors (ENR list) or of Hensel Phelps specifically.
- I did not check Wikidata Query Service rate and timeout limits in 2026.

## 5. Commercial firmographic, credit and ownership databases: D&B (DUNS, family tree, Direct+), NETS, Data Axle, ZoomInfo, Experian, Equifax, LexisNexis, Moody's Orbis/BvD and Cortera, BrightQuery

### Takeaway
The commercial bureaus are the only sources with site-level corporate linkage (HQ → branch → domestic and global ultimate) for private and small firms.
- **D&B** is the most mature, and the one used in OSHA research through NETS. Its unit prices are knowable (about $0.24 per identity-resolution match; about $19.70 per full family tree on the US federal schedule). Licences are per use case and restrict reuse and display.
- **NETS** (a D&B-derived annual time series with HQ links) is the academic standard for longitudinal parent links. It is costly (federal purchase orders $50k–$800k) and is research-licensed.
- **BrightQuery** is a newer option: an entity graph keyed on EIN, LEI and CIK, with an open (non-commercial) tier.
- Most other vendors (ZoomInfo, Orbis, Experian, LexisNexis) are quote-only and aimed at sales, credit or KYB.

### Cited Findings
- **D&B prices** (secondary source citing the US federal schedule effective June 2024; "verified August 18, 2026"):
  - Identity Resolution (Cleanse+Match) **$0.24/call**; Company Search $2.95; Criteria Search $0.99; Type-ahead $0.10.
  - **Full Family Tree $19.70/record**; Ultimate Beneficial Ownership $11.82; Full Family Tree monitoring $15.76; Company Profile monitoring $1.18.
  - UK G-Cloud: £0.16 per record for cleanse/match, 12-month minimum, up to 6% annual increases.
  - [SavvyIQ D&B comparison](https://savvyiq.ai/compare/dun-bradstreet); [D&B G-Cloud 13 pricing doc (2022)](https://assets.applytosupply.digitalmarketplace.service.gov.uk/g-cloud-13/documents/93073/813070293753528-pricing-document-2022-05-17-1107.pdf)
- **D&B matching:**
  - Confidence Code runs 1–10, with user-set thresholds. An 11-character Match Grade string (e.g. "AZZZAZZZFFZ") scores name, address and other components.
  - Records are "licensed per use case, not per dataset" across Compliance, Supply Chain, Finance, Sales & Marketing and Master Data. Reuse for a second purpose costs extra.
  - About 555M global business records (D&B, March 2024).
  - [SavvyIQ D&B comparison](https://savvyiq.ai/compare/dun-bradstreet); [D&B Direct 2.0 cleanseMatch docs](https://docs.dnb.com/direct/2.0/en-US/company/5.0/getcleansematch/rest-API)
- **D&B linkage model:**
  - "Linkage occurs ... when one business entity has financial or legal responsibility for another", forming HQ/Branch or Parent/Subsidiary relationships.
  - Each member carries Site, Parent/HQ, Domestic Ultimate and Global Ultimate DUNS. Parent means more than 50% ownership; Headquarters means "has branches or divisions reporting to it".
  - [D&B Master Data Hierarchies whitepaper](https://www.dnb.com.hk/resources_center/files/DNB_Master_Data_Hierarchies-Whitepaper.pdf); [D&B Direct 2.0 linkage docs](https://docs.dnb.com/direct/2.0/en-US/linkage/latest/orderproduct/linkage-rest-API)
- **DUNS demand for small firms has fallen:** on 4 Apr 2022 the federal government stopped using DUNS. The SAM-issued UEI is now "the identifier of record" for federal registrants. — [National League of Cities](https://www.nlc.org/article/2022/09/23/transitioning-from-duns-to-unique-entity-ids-uei/); [GSA UEI fact sheet](https://origin-www.gsa.gov/system/files/UEI_External_Fact_Sheet.pdf)
- **NETS (Walls & Associates):**
  - Built from annual snapshots of the D&B database. It has longitudinal establishment links and "firm identifiers to link the establishments of multi-unit firms", with annual industry, employment and sales.
  - Covers 60M+ establishments from 1990 onward.
  - [Minneapolis Fed assessment of NETS (Barnatchez, Crane & Decker)](https://www.minneapolisfed.org/institute/working-papers/wp17-29.pdf); [Fed FEDS 2017-110](https://www.federalreserve.gov/econres/feds/files/2017110pap.pdf)
- **NETS pricing and status:**
  - Federal NETS purchase orders range from $50,625 to $800,000. Licences can be national or by state/CBSA, priced by establishment count.
  - USDA ARS bought a sole-source NETS licence for calendar 2024, so NETS was still sold in 2024.
  - [GovTribe NETS opportunity](https://govtribe.com/opportunity/federal-contract-opportunity/purchase-of-nets-national-establishment-time-series-data-1232sa24p0008); [HigherGov](https://www.highergov.com/contract-opportunity/purchase-of-nets-national-establishment-time-ser-1232sa24p0008-p-32048/)
- **NETS in OSHA research:** Levine, Toffel and Johnson (Science 2012) compared 409 randomly inspected California establishments with 409 matched controls. They used OSHA IMIS, WCIRB workers' comp data, "Dun & Bradstreet's compilation of credit ratings and the National Establishment Time-Series database". They found a 9.4% drop in injury rates and no detectable job loss. — [Science 2012](https://www.science.org/doi/10.1126/science.1215191); [DOL CLEAR summary](https://clear.dol.gov/study/randomized-government-safety-inspections-reduce-worker-injuries-no-detectable-job-loss-levine)
- **NETS alternative (YTS):** YourEconomy Time Series (YTS), built in-house from multiple Data Axle business files and hosted at the Universities of Wisconsin, replaced NETS for that group's work. Its maintainers say its counts are closer to QCEW/CBP than NETS. — [youreconomy.org YTS](https://youreconomy.org/yts-database.html)
- **Data Axle (ex-Infogroup/ReferenceUSA)** (from a search snippet of Data Axle's own API page, which returned 403 on fetch):
  - Data: "19.5M+ business places", 400+ attributes, 183M+ contacts.
  - Business API pricing: Standard **$50 per 1,000 records** and Enhanced **$75 per 1,000** for 3,001–100,000 records/month, with add-ons from $30/1,000. Enhanced includes "Corporate Structure".
  - [Data Axle APIs](https://www.data-axle.com/data-solutions/apis/)
- **ZoomInfo:** no public API pricing; API access is bundled in enterprise contracts. Vendr's median negotiated contract is $33,500/yr, ranging $7,213–$155,820 across 1,573 purchases. The prospecting API is "near $50,000 per year". Contracts are annual with a three-seat minimum. A consumption-credit "GTM.AI" platform has been live since June 2026. All figures are from third parties. — [Datamagnet](https://www.datamagnet.co/post/zoominfo-api/); [UpLead](https://www.uplead.com/zoominfo-pricing/)
- **Experian Business:** a 9-character BIN for each company location. The Business Search API takes name, address, city and state and returns a BIN. The Businesses API adds commercial scores, trades, **corporate linkage**, bankruptcies, liens and judgments. Pricing depends on product, volume and end-user industry. — [Experian Businesses PHP SDK README](https://github.com/thelogicstudio/ExperianBusinessesPHP); [Experian BIN glossary](https://smallbusiness.experian.com/pdp.aspx?pg=Glossary&bm=FILENO)
- **LexisNexis InstantID Business:** combines business names, locations, FEINs and firmographics with consumer data. It claims 25% more businesses than any other provider. — [LexisNexis InstantID Business](https://risk.lexisnexis.com/products/instantid-business)
- **SBFE data:** covers 39M+ small and micro businesses, and is sold only via the exclusive bureau partners D&B, Equifax, Experian and LexisNexis. — [LexisNexis press release 2021](https://risk.lexisnexis.com/about-us/press-room/press-release/20210518-sbfe); [Nav on SBFE](https://www.nav.com/resource/small-business-financial-exchange/)
- **Equifax:** offers a "Business Verification Solution (KYB)" API on its developer portal. No pricing was found. — [Equifax developer portal](https://developer.equifax.com/products/apiproducts/business-verification-solution-kyb)
- **Moody's Orbis (BvD):** 625M+ entities with ownership, subsidiaries and ultimate owners. Pricing is not public. Buyer-reported estimates (third-party, low confidence): $5k–$15k per user per year for the web platform, API from $20k, bulk feeds $0.5M–$5M+ a year. — [WRDS BvD](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/bureau-van-dijk-bvd/); [MonetaIQ](https://monetaiq.com/top-moodys-bvd-orbis-alternatives-for-company-financial-data-2026/)
- **Cortera:** Moody's bought it for $139M in cash (completed March 2021). It brought North American SME credit data on 36M+ companies, which now feeds Orbis. — [Moody's press release](https://ir.moodys.com/press-releases/news-details/2021/Moodys-to-Acquire-Cortera-a-Leader-in-Credit-Data-and-Insights/default.aspx); [Moody's FY2022 10-K](https://www.sec.gov/Archives/edgar/data/1059556/000105955623000016/mco-20221231.htm)
- **BrightQuery:**
  - Entity graph of Organizations, Legal Entities, People, Locations and Addresses, linked by **EIN, LEI, CIK** and the proprietary bq_id. About 74M US organizations, with "corporate family structures".
  - Business Identity API: matches on name, address, website, ticker, CIK, LinkedIn or email, and returns legal entity, firmographics and corporate family tree. Claims coverage of "102M Organizations doing business in the US". Pricing is by contact.
  - OpenData.org (BQ's free graph) is CC BY-NC 4.0.
  - [BrightQuery docs](https://docs.brightquery.com/business_identity_api); [OpenSanctions BrightQuery dataset](https://www.opensanctions.org/datasets/brightquery/)

### Inferences
- **D&B for families:** for the multi-EIN family problem (D.R. Horton divisions, Hensel Phelps regional offices), D&B's Domestic Ultimate DUNS is purpose-built.
  - Estimated cost: one $0.24 match per OSHA employer name plus $19.70 per family tree, for a few thousand families. That is roughly in the tens of thousands of dollars before contract minimums, which are unknown.
  - Licence: "per use case" licensing and display limits are the bigger risk. Showing D&B-derived parent names to GCs may need a Sales & Marketing or Master Data plus redistribution licence.
- **D&B for small subcontractors:** coverage is plausibly patchy for firms that never needed a DUNS, a need that weakened after the 2022 UEI switch. This is inference, not measured.
- **NETS:** the right tool for historical parent links (renamed or sold companies, establishment HQ over time), and it has OSHA research precedent. Pricing and terms make it fit an academic study, not a production GC product.
- **BrightQuery and Data Axle:** BrightQuery's EIN-keyed graph could join directly to OSHA ITA 300A EINs, which the project already uses. It is the most promising commercial candidate to evaluate for EIN → legal entity → corporate family. Data Axle's "Corporate Structure" at $75/1k records is the cheapest published per-record linkage price.
- **ZoomInfo, Orbis, Experian, LexisNexis and Equifax:** these suit sales, credit or KYB use and carry enterprise minimums. They offer little extra for OSHA name matching relative to cost.
- **SBFE credit data:** almost certainly not licensable for a safety-screening product. This is inferred from its restricted distribution channel.

### Gaps
- No public 2026 D&B Direct+ list price or minimum contract was found. The figures above are from a 2024 federal schedule as reported by a third party.
- I found no D&B or BrightQuery figure for coverage of US construction (NAICS 23) sole proprietors.
- NETS 2025–2026 vintage, availability and price were not confirmed. The NaNDA (U. Michigan) NETS update page returned 403.
- Data Axle's figures come from a search snippet. The page could not be fetched.
- No academic paper was found that links OSHA records to NETS or D&B HQ linkage to aggregate corporate families. Levine et al. used NETS for outcomes, not for family linkage.

## 6. KYB / entity-resolution APIs: Enigma, Middesk, Baselayer, Persona (SOS + IRS TIN match), prices, small-firm coverage, matching APIs

### Takeaway
KYB APIs resolve a name and address (optionally an EIN) to a SOS-registered legal entity, and some return DBAs and alternate names. That makes them good at "is HAGERMAN the same as HAGERMAN CONSTRUCTION LLC in IN?", but costly per lookup ($1–$2.50) and not designed for bulk OSHA backfill.
- **Enigma** is the most relevant. It explicitly models brands (DBAs) vs legal entities vs operating locations, including sole proprietors as "Persons", with published self-serve pricing.
- **Middesk** and **Baselayer** add IRS TIN-name matching, which fits the project's 300A EINs.

### Cited Findings
- **Enigma data model and quality:**
  - Brands (trade names; one brand can span locations and be owned by several legal entities) vs Legal Entities (Registered Entities and Persons) vs Operating Locations vs Persons (officers, owners, registered agents).
  - "2.4 billion+ nodes".
  - Sources: SOS registrations, websites and directories, third-party data, and a card-transaction panel (750M+ cards).
  - Claimed accuracy: brand→legal-entity link precision 95%, NAICS 98%, location precision 95%.
  - Delivery: bulk CSV/Parquet, GraphQL API, agentic/MCP.
  - [Enigma documentation](https://documentation.enigma.com/getting_started/enigma_data)
- **Enigma pricing (primary pricing page):** Free ($0, console search). Pro $20/mo with 2,100 credits. Max $200/mo with 25,000 credits plus MCP access. Enterprise is custom. "One credit is one cent." Example costs: KYB Identify 150 credits ($1.50), KYB Verify 250 credits ($2.50), watch-list screening $0.50, address 2 credits, industry 5 credits, card revenue 25 credits. Charges apply only to returned fields. — [Enigma pricing](https://www.enigma.com/pricing)
  - **Conflict:** a third-party listing says Pro is 600 credits and Max 8,000, with $5 per 100 extra credits, and that Enigma's Identity Graph covers 48.9M brands and 98M legal entities. — [The GTM Directory](https://thegtmdirectory.com/tools/enigma). Prefer the primary pricing page.
- **Middesk:**
  - TIN check: verifies that an EIN is valid and matches the name given. If it does not match, Middesk "performs a series of lookups to identify alternate names that may be associated with that EIN".
  - Also offers direct SOS searches.
  - No public pricing.
  - [Middesk docs: Verify TIN](https://docs.middesk.com/verify-business/tin); [Middesk TIN Matching API](https://www.middesk.com/tin-matching-api); [Signzy (no public pricing)](https://www.signzy.com/blogs/middesk-alternatives)
- **Baselayer:**
  - Resolves a business by name and address and returns officers, state registrations, entity structure and verification status. Claims direct pipelines to all 50 SOS registries and live IRS TIN verification with about 99% coverage.
  - Pricing (third-party): Startup plan from $150/mo with 500–2,000 credits.
  - Via the Exa integration: business search $1.00 each; lookups and officers free after a search; lien search $2.00 per state.
  - [Baselayer docs](https://docs.baselayer.com/docs/business-verification-basics); [Kaaj.ai](https://kaaj.ai/resources/best-kyb-software-for-lenders); [Exa: Baselayer](https://exa.ai/docs/reference/agent-api/connect/baselayer)
- **Persona** (third-party): Essential plan from $250/mo, 12-month minimum, billed per successful verification. KYB pricing is quote-based. — [Signzy KYC pricing](https://www.signzy.com/blogs/kyc-pricing-us-cost-per-verification); [Capterra](https://www.capterra.com/p/199701/Persona/)

### Inferences
- **Fit:**
  - For GC-entered subcontractors (name, city, state, optional licence), one KYB "identify" call per subcontractor (about $1–$2.50) is affordable and returns the SOS legal name, DBAs and officers. Those can then be matched to OSHA free text.
  - For backfilling hundreds of thousands of OSHA employer strings, per-call KYB pricing is prohibitive. Enigma's bulk/Enterprise or BrightQuery would be needed.
- **Sole proprietors with common names:** Enigma's "Persons as legal entities" plus brand/location linking is the only aggregator model found that targets this case explicitly. Precision on very small trades firms is unverified.
- **EIN bridges:** Middesk's "alternate names associated with that EIN" and Baselayer's TIN match pair naturally with the ITA 300A EINs (2019+). They could confirm that two OSHA names share an EIN, and so are the same filer, without the IRS data itself being exposed.
- **Licence:** KYB terms usually tie data to verification or onboarding purposes. Displaying the results to third-party GCs needs contractual confirmation (not verified).

### Gaps
- Enigma's terms on display and storage were not reviewed. No vendor publishes coverage specific to NAICS 23 or construction sole proprietors.
- Middesk and Persona KYB per-check prices are not public. The figures above come from third-party comparison blogs.

## 7. Open and commercial place/POI datasets: Overture Places, Foursquare OS Places, OpenStreetMap, Google Places, SafeGraph/Advan

### Takeaway
POI data can confirm that a business exists at an address and supply consumer-facing names (DBAs/brands). Construction subcontractors are badly covered, though: they often operate from homes or yards, with no storefront.
- **Overture Places** (about 81M places, monthly, CDLA-Permissive/Apache/CC0, no share-alike) is the best free bulk option. It includes about 10M BrightQuery-sourced records.
- **Foursquare OS Places** (Apache 2.0, about 106M) adds closure dates.
- **OSM** is negligible for contractors.
- **Google Places** has the best coverage of tradespeople but costs $32 per 1,000 Text Search Pro calls, and only the place ID may be stored indefinitely.

### Cited Findings
- **Overture Places:**
  - Size and sources: about 81M point features globally (Sept 2026); Meta contributes about 59M. Other sources: Microsoft, Foursquare, PinMeTo, AllThePlaces, BrightQuery, DAC, Krick, RenderSEO. **No OSM data.**
  - Fields: `names` (primary + alternate), `brand`, a taxonomy of about 2,300 categories, addresses, websites, phones, emails, socials, `confidence` (0–1 likelihood of existence) and `operating_status`.
  - Release, access and IDs: monthly; free on S3 and Azure; stable GERS IDs.
  - [Overture Places guide](https://docs.overturemaps.org/guides/places/)
- **Overture licences by source:** CDLA Permissive 2.0 (Meta, Microsoft, PinMeTo, Krick, RenderSEO, DAC, BrightQuery); Apache 2.0 (Foursquare, with NOTICE); CC0 (AllThePlaces). Attribution is required except for AllThePlaces. — [Overture attribution](https://docs.overturemaps.org/attribution/)
  - BrightQuery contributes 10,255,071 features as of Sept 2026, under CDLA-Permissive-2.0. This count is from a search-result summary; the attribution page I fetched did not show counts. — [Overture attribution](https://docs.overturemaps.org/attribution/)
- **Foursquare OS Places:**
  - Licence and size: Apache 2.0. The December 2025 release had 106,205,195 POIs; an independent count found 104.5M.
  - Fields: `fsq_place_id`, name, address fields, `date_created`, `date_refreshed`, **`date_closed`**, tel/website/email/socials, category IDs and labels, and `unresolved_flags` (closed, duplicate, doesnt_exist...).
  - No brand/chain or alternate-name field is documented.
  - [Foursquare OS Places schema](https://docs.foursquare.com/data-products/docs/places-os-data-schema); [Foursquare blog](https://foursquare.com/resources/blog/data/evolving-fsq-open-source-places/); [Simon Willison](https://simonwillison.net/2024/Nov/20/foursquare-open-source-places/)
- **OSM, live taginfo counts (global, all object types, 2026-10-04):** office=construction_company 4,611; craft=builder 5,748; craft=electrician 14,830; craft=plumber 12,235; craft=roofer 6,043; office=contractor 60. OSM is ODbL (share-alike). — [OSM taginfo](https://taginfo.openstreetmap.org/tags/office=construction_company)
- **Google Places API (New) prices** (Google pricing page, updated 2026-09-28):
  - Text Search Essentials (IDs only): free and unlimited.
  - Text Search Pro: 5,000 free/month, then **$32 per 1,000**.
  - Text Search Enterprise: 1,000 free, then $35 per 1,000.
  - Place Details Essentials: 10,000 free, then $5 per 1,000. Pro: 5,000 free, then $17. Enterprise: 1,000 free, then $20.
  - Autocomplete: $2.83 per 1,000.
  - Volume tiers reduce prices.
  - [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
- **Google Places policies:** "the place ID ... is exempt from the caching restrictions ... You can therefore store place ID values indefinitely". Other content falls under the Maps Platform caching restrictions. Content shown without a Google Map needs Google Maps logo or text attribution, and must not be misattributed or blended with non-Google content. — [Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies)
- **SafeGraph/Advan via Dewey:** academic seats $3,600/yr; university-wide $50,000/yr; non-commercial only. SafeGraph Places is free to Dewey-subscribing universities. Commercial licensing is negotiated, "typically five to six figures annual" (third-party estimate). — [Jay Mount Consulting](https://jaymountconsulting.com/data-sources/safegraph-advan-dewey); [Dewey/Advan](https://www.deweydata.io/data-partners/advan)

### Inferences
- **Overture as the free baseline:** a free, commercially usable, monthly bulk layer for checking "is there an active business named X near address Y". It has alternate names and brands, and it carries no ODbL obligation unless joined with OSM. Its BrightQuery-sourced records may cover legal-entity-style business addresses better than Meta's consumer pages. Coverage of construction trades needs measuring, e.g. by counting US places in contractor categories.
- **Foursquare's closure fields:** `date_closed` and `unresolved_flags` can help flag companies that were renamed or have closed.
- **OSM:** its global contractor counts (tens of thousands across all trades worldwide) make it irrelevant for US subcontractor matching.
- **Google Places:**
  - Use: best for live, per-subcontractor confirmation at GC entry time (business name variants, address, phone, operational status). It is not bulk-cacheable.
  - Storage: store only place_id and re-query.
  - Cost: about $0.032 per Pro text search after the free 5,000/month is reasonable for interactive use.
- **SafeGraph/Advan:** foot-traffic data is irrelevant here. SafeGraph Places is mostly a commercial or academic copy of POI data already approximated by Overture.

### Gaps
- No US-only count of Overture or Foursquare places in construction-contractor categories was available. I could not run DuckDB locally (not installed).
- The current caching limits in Google's Service Specific Terms for Places content other than place_id (e.g. coordinates) could not be extracted; the page was truncated.
- Whether Places "businessStatus" closure flags are reliable for small contractors is unverified.

## 8. Good Jobs First Violation Tracker: parent matching method, downloads and licensing, use as labelled data for corporate families

### Takeaway
Violation Tracker links OSHA penalties of $5,000 or more to more than 3,000 large parents. The links come from a proprietary, manually checked parent–subsidiary system built for Subsidy Tracker, seeded from big-company lists (Fortune 1000, Russell 3000, Forbes largest private, and others). Subscribers see both the parent at the time of the penalty and the current parent, plus a summary of ownership changes. That makes it a strong labelled set for big-firm families and renames, but useless for small subcontractors. The full dataset is licensable to academics and commercial users. Downloads otherwise need a $250–$1,500/yr subscription.

### Cited Findings
- **Parent matching:** enforcement records "usually do not indicate whether the company involved is part of a larger corporate entity", so Good Jobs First identifies parents "using a variety of sources".
  - Parent universe: the Fortune 1000, Fortune Global 500, S&P 500, Russell 3000, the Forbes largest private US companies, Uniworld's 1,000 largest foreign firms in the US, and PEI's 100 largest PE firms.
  - Matches are "checked manually".
  - Linkages reflect the latest revision, which "may vary from what was the case when a violation occurred".
  - [Violation Tracker User Guide](https://violationtracker.goodjobsfirst.org/pages/user-guide) (via search snippet; the site returns 403 to fetchers)
- **Matching system and rules:** Violation Tracker uses "a proprietary system of parent-subsidiary matching developed by Good Jobs First for its Subsidy Tracker database". Records link to "more than 3,000 parent companies". A joint venture counts as a subsidiary only if one owner holds more than 50%. PE portfolio companies are treated the same way. — [Violation Tracker User Guide](https://violationtracker.goodjobsfirst.org/pages/user-guide); [Introducing Violation Tracker](https://goodjobsfirst.org/introducing-violation-tracker/)
- **Which parents are shown:** aggregated data appears for more than 3,000 parents, which are "either large corporations, regardless of penalty amount, or selected smaller companies with large penalties". — [VT OSHA agency page](https://violationtracker.goodjobsfirst.org/agency/OSHA) (via search snippet)
- **Subscriber fields:** expanded entries show "the parent at the time of the penalty and the current parent". If the two differ, a field summarises the ownership changes. — [Dirt Diggers Digest, "Violation Tracker's New Track"](https://dirtdiggersdigest.org/archives/7081) (via search snippet)
- **Scale and OSHA threshold:** more than 600,000 cases from about 500 agencies. "Only fines of $5,000 or more" are included, and OSHA accounts for more than one-third of cases. — [Good Jobs First, "Corporate Penalties Reach the Trillion-Dollar Mark"](https://goodjobsfirst.org/the-high-cost-of-misconduct-corporate-penalties-reach-the-trillion-dollar-mark/)
- **OSHA totals in VT:** 254,596 records and $3.83B in penalties since 2000. — [VT OSHA agency page](https://violationtracker.goodjobsfirst.org/agency/OSHA) (via search snippet)
- **Access tiers:**
  - Search and display are free; downloads and some fields are for subscribers only.
  - Tier 1: $25/mo or $250/yr, up to 1,000 records per search download.
  - Tier 2: $45/mo or $450/yr, up to 5,000 records.
  - Tier 3: $150/mo or $1,500/yr, up to 10,000 records.
  - The full dataset "with corporate identifiers" is offered for academic purposes (contact Philip Mattera). More than 400 faculty and grad students at 274 universities in 35 nations have licensed it, and about a dozen companies (e.g. ESG raters) license full sets.
  - [Violation Tracker plans](https://violationtracker.goodjobsfirst.org/plans) (via search snippet); [Message to Violation Tracker Users](https://goodjobsfirst.org/message-to-violation-tracker-users/)

### Inferences
- **As labelled data:** VT's OSHA ↔ parent links (time-of-penalty and current parent, with ownership-change notes) are the best ready-made labels for "these OSHA employer strings belong to family F". They are directly relevant to D.R. Horton-, Lennar-, EMCOR- and Quanta-type families and to sold companies. Hensel Phelps would be covered only if it appears on the Forbes largest-private list; unverified.
- **Bias:** the labels are skewed towards large parents and penalties of $5,000 or more, so they cannot train or evaluate small-subcontractor matching. They are good for evaluating the "family" layer.
- **Licence:** commercial use or redistribution of VT parent links in a GC product would need a commercial licence, as about a dozen firms already hold. An academic licence would only support a research evaluation.

### Gaps
- I could not read VT pages directly (HTTP 403). I could not confirm whether VT OSHA rows carry the OSHA activity/inspection number, which is needed to join exactly to DOL bulk data, nor the academic or commercial licence prices.
- The current exact parent count (the ">3,000" figure may be dated) is unverified.

## 9. Open datasets of company name aliases, DBAs and corporate families usable as training or labelled data

### Takeaway
There is no single open US DBA dataset for this use case, but several free or cheap sources can be combined:
- **Public domain or CC0:** EDGAR `formerNames` and Exhibit 21 (with DBA columns for some filers); GLEIF `OtherEntityNames`/`SuccessorEntity`; Wikidata aliases.
- **CC BY-NC:** OpenSanctions' CorpWatch Ex-21 graph.
- **Benchmarks:** the new CorpFam benchmark (SAM.gov self-reported parents validated against Ex-21), which shows family resolution is a retrieval/blocking problem; and OpenSanctions Pairs for general entity matching.
- **Licensed:** OpenCorporates `alternative_names`/`previous_names` bulk files.

### Cited Findings
- **CorpFam benchmark** (H. Gupta, arXiv 2609.04269, 2 Sept 2026):
  - Built from 6,638,350 US federal award records "in which every supplier self-reports its ultimate parent". It has 54,864 candidate pairs across 10,307 corporate families, stratified by name visibility (identical, shared tokens, or completely different names), and is validated against SEC Exhibit 21.
  - The best matcher recovered "100.0% of identical pairs and 4.2% of invisible ones". "93.2% of these links never enter the candidate set". Blocking recovered 6.8% of invisible pairs.
  - Code, data and adjudication logs are on GitHub.
  - [arXiv 2609.04269](https://arxiv.org/abs/2609.04269)
- **OpenSanctions Pairs** (arXiv 2603.11051): 755,540 expert-labelled pairs over 1M+ entities from 293 source datasets in 45 jurisdictions. LLMs reach up to 99.0% F1. The paper is CC BY 4.0; the dataset's location and licence were not stated in the abstract page. — [arXiv 2603.11051](https://arxiv.org/abs/2603.11051)
- **OpenSanctions CorpWatch EX-21:** 2.34M entities with parent links, CC BY-NC 4.0. — [OpenSanctions](https://www.opensanctions.org/datasets/us_corpwatch/)
- **EDGAR former names:** dated former names for every SEC registrant (live test examples in section 3). — [data.sec.gov submissions](https://data.sec.gov/submissions/CIK0000822416.json)
- **D.R. Horton Ex-21 DBA column:** 178 rows with "DOING BUSINESS AS" values. — [EDGAR DHI Ex-21.1](https://www.sec.gov/Archives/edgar/data/882184/000088218425000081/a9302025ex211subsidiaries.htm)
- **GLEIF:** `OtherEntityNames` and `SuccessorEntity`, CC0. — [GLEIF LEI-CDF 3.1](https://www.gleif.org/en/lei-data/access-and-use-lei-data/level-1-data-lei-cdf-3-1-format)
- **OpenCorporates:** Alternative Names and previous names bulk files, with typed names (Trading, Alias, and so on). Licence is ODbL or commercial. — [OpenCorporates Bulk Files](https://knowledge.opencorporates.com/knowledge-base/bulk-files-explained/); [Glossary](https://knowledge.opencorporates.com/knowledge-base/glossary-of-terms/)
- **BrightQuery OpenData.org:** about 74M US organizations with corporate family structures, CC BY-NC 4.0. — [OpenSanctions BrightQuery](https://www.opensanctions.org/datasets/brightquery/)

### Inferences
- **Most relevant benchmark:** CorpFam's finding that 93% of different-name family links never reach the candidate set matches this project's failures (D.R. Horton divisions, Hensel Phelps offices). It argues for adding identifier-driven candidate generation rather than better string similarity. Useful identifiers: EIN from 300A, Ex-21 alias lists, SOS registered-agent and officer overlap, shared mailing addresses.
- **Cheap open labelled set for families and renames:** EDGAR `formerNames` plus Ex-21 subsidiaries and DBAs, plus GLEIF other names, plus Wikidata aliases. Pairing it with VT parent links (licensed) gives OSHA-side labels.
- **Licensing:** the CC BY-NC sources (OpenSanctions CorpWatch, BrightQuery OpenData) are usable for research and evaluation only, unless a commercial licence is bought.

### Gaps
- I found no open, bulk, multi-state US DBA/assumed-name dataset among non-government sources. County and state DBA filings are government sources, covered by another researcher.
- I did not verify the CorpFam GitHub repo's licence or whether it includes construction firms.

## 10. Practical fit: which source addresses which matching failure, and comparison of identifiers, coverage, access, price and licence

### Takeaway
No single database fixes all the failure modes. A layered, mostly free stack covers the large-family cases:
1. EDGAR Exhibit 21 and `formerNames` for public-company families, city divisions, DBAs and renames.
2. GLEIF and Wikidata as crosswalks.
3. Violation Tracker as OSHA-side family labels.
4. Overture as a free existence check.

Small subcontractors (sole proprietors, DBAs, common names) need either a per-lookup KYB/identity API at GC entry time (Enigma about $1.50–$2.50, Google Places about $0.03, D&B about $0.24) or a bulk EIN-keyed graph (BrightQuery, D&B/NETS) under a commercial licence. OpenCorporates is a good data model, but share-alike or high prices make it marginal.

### Cited Findings
- See sections 1–9 for the sources behind each cell below. Key anchors:
  - DHI Ex-21 lists "D.R. Horton, Inc. - Greensboro". — [EDGAR](https://www.sec.gov/Archives/edgar/data/882184/000088218425000081/a9302025ex211subsidiaries.htm)
  - GLEIF Level 2 has 0–5 children for the major contractors. — [GLEIF API](https://api.gleif.org/api/v1/lei-records/529900ZIUEYVSB8QDD25/ultimate-children)
  - D&B match costs $0.24 and a family tree $19.70. — [SavvyIQ](https://savvyiq.ai/compare/dun-bradstreet)
  - OpenCorporates self-serve is £2,250–£12,000/yr, and free users fall under ODbL. — [OpenCorporates pricing](https://opencorporates.com/pricing/); [Terms](https://opencorporates.com/terms-of-use-2/)
  - Enigma credit prices. — [Enigma pricing](https://www.enigma.com/pricing)
  - Google Text Search Pro is $32 per 1,000. — [Google pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
  - VT links OSHA penalties of $5,000 or more to more than 3,000 parents. — [VT User Guide](https://violationtracker.goodjobsfirst.org/pages/user-guide)

### Inferences
Comparison (US construction subcontractor matching):

| Source | Key IDs | Small-firm coverage | Corporate hierarchy | Name history / DBA | Access | 2026 price | Licence: store / show to users | Fit |
|---|---|---|---|---|---|---|---|---|
| SEC EDGAR (Ex-21, submissions) | CIK, ticker | None (public registrants only) | Ex-21 subsidiaries (unstructured; DHI ~600 rows) | `formerNames` with dates; Ex-21 DBA column (some filers) | Free bulk/API | Free | Public domain | **High** for public homebuilders and contractors |
| GLEIF | LEI; state file no.; OC-ID map | Near zero | L2 parent/child, but children rarely have LEIs | OtherEntityNames, SuccessorEntity | Free bulk + API | Free | CC0 | Low–medium (crosswalk) |
| Wikidata | QID, CIK, LEI | None | Sparse P355/P749 | Aliases | Free SPARQL/dumps | Free | CC0 | Low (aliases for top firms) |
| OpenCorporates | jurisdiction + company no. | Good for registered entities (all 50 states + DC); no sole proprietors | Branches; SEC-derived subsidiaries | previous_names; typed alternative_names | API, bulk (Enterprise) | £2,250–£12,000/yr self-serve; bulk custom; free only for public benefit | ODbL share-alike if free; paid = proprietary | Medium (data good; access costly) |
| D&B Direct+ | DUNS (site, HQ, domestic and global ultimate) | Broad but patchy for firms with no DUNS | **Best** site-level family trees | Tradestyles (unverified) | API, batch | ~$0.24 per match; $19.70 per family tree (2024 federal schedule) | Per-use-case licence; display restricted | High for families, if licence allows display |
| NETS | DUNS-based, with HQ links | Broad (60M+ establishments) | HQ links per year | Longitudinal (renames, moves) | Bulk files | $50k–$800k purchase orders (federal) | Research licence | High for research; not for production |
| BrightQuery | bq_id, EIN, LEI, CIK | Claims 74M–102M US organizations | Corporate family tree | Unknown | API; OpenData (non-commercial) | Contact sales; OpenData free (CC BY-NC) | Commercial licence needed | **Promising** (EIN join to 300A) |
| Data Axle | Data Axle IDs | 19.5M+ business places | "Corporate Structure" (Enhanced) | Unknown | API | $50–$75 per 1,000 records | Unknown | Medium |
| Enigma | Enigma IDs; brand vs legal entity | Targets SMBs, including sole proprietors | Brand ↔ legal-entity links | Brands/DBAs | API, bulk, MCP | Pro $20/mo; Max $200/mo; KYB $1.50–$2.50 | Not reviewed | **High** for DBA and sole-proprietor cases at entry time |
| Middesk / Baselayer / Persona | SOS IDs; EIN | SOS-registered entities | Limited | Alternate names via EIN (Middesk) | API | Not public (Baselayer from ~$150/mo) | KYB-purpose terms | Medium (EIN confirmation) |
| ZoomInfo / Orbis / Experian / LexisNexis / Equifax | Proprietary (BIN etc.) | Variable | Yes (linkage) | Some | Enterprise | Quote; ~$7k–$156k/yr (ZoomInfo) | Restrictive | Low value for the cost |
| Overture Places | GERS ID | Weak for trades without storefronts | Brand only | names.alternate, brand | Free bulk, monthly | Free | CDLA-P 2.0 / Apache / CC0 | Medium (existence check) |
| Foursquare OS Places | fsq_place_id | Weak | None | None; has date_closed | Free bulk | Free | Apache 2.0 | Low–medium |
| OSM | OSM ID | Negligible | None | Some | Free | Free | ODbL share-alike | Very low |
| Google Places | place_id | Best POI coverage of trades | None | Display name | API only | $32 per 1,000 Text Search Pro after 5,000 free | Store only place_id indefinitely; attribution | Medium (interactive confirmation) |
| Violation Tracker | VT parent | None (penalties ≥$5k, large parents) | >3,000 parents; parent at penalty time vs now | Ownership-change notes | Subscription or full licence | $250–$1,500/yr; full set by licence | Licence required to redistribute | **High as labelled data** for families |

Mapping failure modes to sources:
- **Corporate families with several EINs:**
  - D.R. Horton and other public firms: Ex-21 alias lists, then VT labels; D&B Domestic Ultimate if licensed.
  - Hensel Phelps (private): D&B or BrightQuery family tree, or OpenCorporates foreign-branch records across states. Also cluster 300A EINs by shared HQ mailing address.
- **Descriptor variants** (HAGERMAN / HAGERMAN CONSTRUCTION; LOBAR / LOBAR ASSOCIATES): resolve to the SOS legal name via OpenCorporates or a KYB API, then use a descriptor-stripping normaliser (OpenCorporates `normalise_company_name` is an example). No external family data is needed.
- **City names as division names** (DR HORTON INC GREENSBORO): Ex-21 divisional entity names; D&B branch/HQ records.
- **Sole proprietors with common names:** Enigma (Persons and brands at locations); Google Places / Overture existence plus phone and address; GC-supplied licence numbers (handled elsewhere).
- **DBA vs legal name:** Ex-21 DBA column (public firms); OpenCorporates Trading alternative names; Enigma brand→legal entity; Middesk alternate names via EIN.
- **Renamed or sold companies:** EDGAR `formerNames`; OpenCorporates `previous_names`; GLEIF SuccessorEntity; VT "parent at time of penalty vs current parent"; NETS longitudinal HQ links (research).

### Gaps
- Nothing here measures the real recall of any vendor on a sample of OSHA construction employer names. A paid pilot (e.g. 200 OSHA names through D&B match, Enigma, BrightQuery and OpenCorporates) would be needed to rank them empirically.
- Licence terms for showing vendor-derived parent names to GC end users (D&B, BrightQuery, Enigma, Data Axle) were not reviewed in contract detail.
