# Prior work linking OSHA enforcement records to firms and other datasets

Scope: who has matched US OSHA inspection, violation or injury (ODI/ITA/SOII) records to companies or to other datasets, how they did it, what match rates and precision they reported, what they learned about OSHA name quirks, and which artefacts can be reused (status as of Oct 2026). Research date: 2026-10-04. Most of the sources are primary: papers, appendices, GAO/OIG reports, OSHA directives and GitHub code. Where a fact comes only from a search-engine summary, it is marked "(search summary)".

---

## 1. Academic studies: matching procedures and reported match rates

### Takeaway
Every serious academic linkage of OSHA inspection records ran into the same problem: the inspection file has no firm or establishment identifier. Researchers fell back on name, address and industry matching (Fellegi-Sunter probabilistic matching, Stata `matchit`/`reclink`, SAS DQMatch), followed by manual clerical review, and reported only moderate coverage. About 60% of records matched before clerical review in the Census linkage (Lee & Taylor), and 82% of SST target establishments linked to at least one IMIS inspection (Johnson, Levine & Toffel). Studies that needed firm-level links used EINs only where the injury data carried them (BLS SOII, 2002–2012), and even then they found that one firm has many EINs. They then added manual name matching under a "near-certainty" rule, which favours precision.

### Cited Findings

**Johnson, Levine & Toffel, "Improving Regulatory Effectiveness through Better Targeting: Evidence from OSHA" (AEJ: Applied 2023, 15(4): 30–67)**
- Data: SST target lists 2001–2010 and ODI injury surveys 1996–2011, obtained from OSHA "after signing a memorandum of understanding"; IMIS inspections downloaded Dec 2014 from enforcedata.dol.gov; NETS (Dun & Bradstreet) 1990–2013 — [HBS PDF](https://www.hbs.edu/ris/Publication%20Files/improving%20regulatory%20effectiveness--final%20working%20paper_dbebc460-588b-4eb4-bf97-0f683bac5f70.pdf)
- ODI carries a DUNS number, "a unique establishment-level identifier". Linking by DUNS found "100 percent of the SST target list establishments in ODI and 97 percent in NETS" — [same](https://www.hbs.edu/ris/Publication%20Files/improving%20regulatory%20effectiveness--final%20working%20paper_dbebc460-588b-4eb4-bf97-0f683bac5f70.pdf)
- "Because the IMIS database does not include DUNS numbers, we linked the establishments on the SST target list to IMIS records by fuzzy-matching names, addresses, and industries using MatchIt software, the Stata reclink command, and a manual process. We linked 82 percent of the establishments on the SST target lists to at least one inspection record in IMIS." — [same](https://www.hbs.edu/ris/Publication%20Files/improving%20regulatory%20effectiveness--final%20working%20paper_dbebc460-588b-4eb4-bf97-0f683bac5f70.pdf)
- They kept the 18% that did not link. They acknowledge that "our matching algorithm might have failed to identify some of their corresponding IMIS records" and that apparently uninspected establishments may be link failures (fn. 14, 23). Scale: 101,463 establishment-directive records, which are 40,946 unique establishments. The pre-analysis plan was revised in Jan 2016 partly because they "made some improvements to our fuzzy linking" (OSF: osf.io/2snka) — [same](https://www.hbs.edu/ris/Publication%20Files/improving%20regulatory%20effectiveness--final%20working%20paper_dbebc460-588b-4eb4-bf97-0f683bac5f70.pdf)

**Johnson, Levine & Toffel, "Spillover Effects of Regulatory Inspections: Evidence from OSHA" (HBS Working Paper 27-014, © 2026)**
- Reuses the same pipeline. ODI, SST and NETS are merged on DUNS; "We fuzzy linked (via Stata's matchIt and reclink commands, and manually) 82 percent of the SST list members to IMIS records." It uses NETS "corporate networks" to study spillovers. Main result: inspections cut injuries at uninspected same-ZIP establishments by about 11% — [HBS WP 27-014](https://www.hbs.edu/ris/Publication%20Files/27-014_a4367aa5-143f-4c91-8f7f-d5ef1b53494a.pdf)

**Levine, Toffel & Johnson, "Randomized Government Safety Inspections Reduce Worker Injuries with No Detectable Job Loss" (Science 2012, 336: 907)**
- Compares 409 randomly inspected California establishments with 409 matched controls, 1996–2006 (5,593 firm-years). Cal/OSHA built its random-selection frame from Dun & Bradstreet and other sources. Controls had to be in the same industry and region, be single-establishment firms with 10 or more employees, and have no inspection in the prior two years. Injury rates fell 9.4% — [DOL CLEAR summary](https://clear.dol.gov/study/randomized-government-safety-inspections-reduce-worker-injuries-no-detectable-job-loss-levine); [HBS PDF](https://www.hbs.edu/ris/Publication%20Files/LevineToffelJohnson_2012_Science_1e9730f0-4224-4b6a-b1b6-ff0c44d11514.pdf) (search summary)

**Lee & Taylor, "Randomized Safety Inspections and Risk Exposure on the Job: Quasi-experimental Estimates of the Value of a Statistical Life", online appendix (AEA replication materials; journal and year believed to be AEJ: Economic Policy 2019, not verified here). This is the most detailed published OSHA-to-Census linkage method.**
- "OSHA inspection data are matched to the plants in the Business Register using an iterative probability matching process that is based on an algorithm developed by Fellegi and Sunter (1969). The matching is conducted within two-digit SIC industry classification." Matching was repeated against each year's Business Register, 1987–1997, "to improve match rates in situations where plants report multiple addresses across years." — [AEA materials 11737](https://topcat.aeaweb.org/articles/materials/11737)
- Procedure:
  - standardise case and street suffixes;
  - parse into full name and address plus subsets (city, state, zip, street number);
  - weight each field by m/u, i.e. P(agree | true match) / P(agree | non-match), calibrated on "a carefully reviewed subset of the data" of hand-checked certain matches and non-matches;
  - add SAS DQMatch, a phonetic organisation-name and address matcher, as a comparison feature;
  - set the upper threshold "such that less than 1% of untrue matches are mistakenly treated as a match", and the lower bound at the lowest score of any true match in the reference set;
  - review records between the two thresholds manually.
  
  "The initial algorithm match rates were approximately 60%." — [same](https://topcat.aeaweb.org/articles/materials/11737)
- Lineage: "We thank Wayne Gray for sharing code upon which our matching is based. See Scholz and Gray (1993, 1990) and Gray and Mendeloff (2004) for examples of the code implementation using Census and BLS data." — [same](https://topcat.aeaweb.org/articles/materials/11737)
- Quirks the authors list: "ownership changes, misreported or miscoded addresses, and large plants with multiple addresses". Unmatched plants were far more likely to have a "failed inspection", where the inspector found a wrong address, a closed plant or a wrong industry code: 24% unmatched vs 9% matched. Union rate was 30% among matched vs 19% among unmatched — [same](https://topcat.aeaweb.org/articles/materials/11737)

**Cohn & Wardlaw, "Financing Constraints and Workplace Safety" (Journal of Finance 2016, 71: 2017–2058)**
- Uses confidential BLS SOII establishment data, which has its own establishment ID. "The BLS data also include, for the period 2002 to 2009, the employer identification number (EIN) of the establishment's parent company. We use the EIN to match the establishment-level data to firm-level data in Compustat." — [author PDF](https://faculty.mccombs.utexas.edu/jonathan.cohn/papers/injuries_2016mar_public.pdf)

**Cohn, Nestoriak & Wardlaw, "Private Equity Buyouts and Workplace Safety" (Dec 2020 version; later published in RFS)**
- "The only firm-level identifier in the SOII data is the parent firm's employer identification number (EIN)." — [author PDF](https://faculty.mccombs.utexas.edu/jonathan.cohn/papers/PE_buyouts_and_workplace_safety_2020dec.pdf)
- On EINs: "Compustat provides only a single EIN, while firms often have multiple EINs, and different establishments belonging to the same firm often report different EINs." EINs exist only for 2002–2012, so 1996–2001 years were back-filled from later EIN matches of the same establishment — [same](https://faculty.mccombs.utexas.edu/jonathan.cohn/papers/PE_buyouts_and_workplace_safety_2020dec.pdf)
- Second pass: "manually comparing each buyout firm's name to establishment names", using "corporate websites, Bloomberg Business, and news articles to identify other names under which a firm operates. If we cannot determine with near-certainty that an establishment belongs to a given buyout firm, we do not create the match." Private targets were matched by name only. Franchisers were removed — [same](https://faculty.mccombs.utexas.edu/jonathan.cohn/papers/PE_buyouts_and_workplace_safety_2020dec.pdf)
- Yield:
  - public targets: 13,452 establishments to 244 targets, about 55 per target;
  - private targets: 2,051 establishments to 316 targets, about 6.5 per target;
  - comparison: Census-based work (Davis et al. 2019) finds about 112 and 16 establishments per target.
  
  "We match establishments in the OSHA inspection data to buyout firms based on establishment name." The link files "are stored at the BLS and can be made available to researchers on-site." — [same](https://faculty.mccombs.utexas.edu/jonathan.cohn/papers/PE_buyouts_and_workplace_safety_2020dec.pdf)

**Caskey & Ozel, "Earnings Expectations and Employee Safety" (Journal of Accounting and Economics 2017)**
- Merged OSHA ODI injury data for 2002–2011 with Compustat parents — [ResearchGate](https://www.researchgate.net/publication/311551998_Earnings_Expectations_and_Employee_Safety)
- Ozel posts a public linking file, Compustat GVKEY ↔ OSHA establishment names. Names are "as reported by the OSHA, without any modifications". The matching used OSHA unique identifiers that are not public, so those IDs were left out of the file. No match rate is given. Hosted on Google Drive — [Bugra Ozel data page](https://sites.google.com/view/bugraozel/data)

**Haviland, Burns, Gray, Ruder & Mendeloff (RAND), "A new estimate of the impact of OSHA inspections on manufacturing injury rates, 1998–2005" (Am. J. Ind. Med. 2012)**
- Linked Pennsylvania workers' compensation injury data with unemployment-insurance employment records and with OSHA IMIS inspections, for single-establishment manufacturers with more than 10 employees. Penalty inspections cut injuries by 19–24% a year over two years — [Wiley](https://onlinelibrary.wiley.com/doi/10.1002/ajim.22062); [RAND](https://www.rand.org/pubs/external_publications/EP50461.html); [CLEAR](https://clear.dol.gov/study/new-estimate-impact-osha-inspections-manufacturing-injury-rates-1998-2005-haviland-et-al-2012) (search summary; match rate not retrieved)

**Mendeloff, Nelson, Ko & Haviland, "Small Businesses and Workplace Fatality Risk" (RAND TR-371, 2006)**
- Fatality rates by establishment size and by firm size, 1992–2001. Holding establishment size fixed, firm size has little effect on risk — [RAND](https://www.rand.org/pubs/technical_reports/TR371.html) (search summary; linkage method not retrieved because the page returned 403)

**Johnson, "Regulation by Shaming" (AER 2020)**
- Design: OSHA issued press releases for penalties of $40,000 or more, which the paper uses as a regression discontinuity. After a press release, nearby facilities (about 3 miles) had 73% fewer violations — [AEA research summary](https://www.aeaweb.org/research/regulation-shaming-osha-enforcement); [Corporate Crime Reporter](https://www.corporatecrimereporter.com/news/200/matthew-johnson-on-regulation-by-shaming/)
- Replication package on openICPSR project 114988 — [openICPSR](https://www.openicpsr.org/openicpsr/project/114988/version/V1/view)

**Finance and accounting papers that use Violation Tracker as the crosswalk**
- Raghunandan (Review of Accounting Studies 2021) merged Compustat with WHD WHISARD wage-theft cases "by using parent-subsidiary matching provided by Violation Tracker of Good Jobs First", which covers roughly the 3,000 largest firms. Later papers follow this approach and are careful not to treat unmatched firms as non-violators — [LSE PDF](https://researchonline.lse.ac.uk/id/eprint/109863/2/Raghunandan_financial_misconduct_employee_mistreatment_published.pdf); [Chircop et al.](https://eprints.lancs.ac.uk/id/eprint/236063/1/Manuscript.pdf) (search summary)

### Inferences
- Published OSHA→external linkage coverage sits at about 60% automated (Lee & Taylor), rising with clerical review, and 82% "at least one inspection" for SST targets (JLT). The JLT denominator includes truly uninspected sites, so its true recall is unknown. No academic source reports precision measured on a held-out labelled set. Lee & Taylor only *design* for under 1% false matches using a hand-reviewed calibration subset. The project's labelled eval with a held-out check is more rigorous than what this literature publishes.
- The project's ITA EIN path has a known weakness, documented by Cohn et al.: a firm has many EINs, and establishments of one firm report different EINs. EIN equality is strong evidence of a match. EIN *inequality* is weak evidence against one, which matters for corporate families such as D.R. Horton divisions.
- The precision-first conventions in this literature map directly onto the project's adjudicator: the "near-certainty" rule, manual review of the middle band, and dropping franchisers.
- Unmatched OSHA records skew toward failed or no-inspection records and wrong addresses (Lee & Taylor). The project should expect `why_no_insp`-type records to be the hardest to match, and may treat them separately.
- Matching within an industry block (2-digit SIC in Lee & Taylor; industry in JLT) is standard. For construction subcontractors, trade (NAICS 238x) could act as a soft block, but NAICS on OSHA records is entered per inspection.

### Gaps
- I could not retrieve the matching details for Scholz & Gray (1990, 1993) or Gray & Mendeloff (2004/2005), the original Wayne Gray OSHA↔LRD/BLS code lineage, beyond Lee & Taylor's description.
- I found no study that links OSHA to Census LEHD, or that reports OSHA↔LBD firm-level match rates in an FSRDC disclosure.
- I found no reference for "Li & Singleton". A search summary said one paper manually matched OSHA establishments to Compustat by name and then searched Hoover's and company websites, but I could not tell which paper (possibly "Institutional Investors and Workplace Safety" or "Less is More: Lender Distraction"), so that claim is unverified.
- Weil's construction work (e.g., on unions and OSHA enforcement, or the fissured workplace) and Mendeloff's construction-contractor analyses: I did not retrieve their linkage methods. Searches returned only legal commentary on the multi-employer citation policy.
- The BLS Monthly Labor Review article on linking OSHA inspections to the BLS respirator survey (2013) failed to fetch (connection reset). It reportedly used probabilistic matching to the BLS Longitudinal Database, but I could not confirm the details.
- Johnson (2020): I did not establish how the paper defines a "facility" across inspections.

---

## 2. OSHA's own identifiers, ITA fields and SST linkage

### Takeaway
OSHA publishes only an inspection-level key, `activity_nr`, plus free-text names. ITA has its own `establishment_id`, `company_name` and `ein`. OSHA links ITA establishments to inspections *manually inside its internal SST application*, and that link is not published. EINs collected during inspections (encouraged since a May 2019 memo) are not in the public inspection file. A field called `host_est_key` exists in the public inspection table but I found no documentation for it.

### Cited Findings
- OSHA's establishment-search help says establishment names "are not unique" and may be spelled in several ways; it advises searching on "as few words as necessary". Each inspection gets a unique "Activity" number. IMIS holds 3M+ inspections since 1972, updated daily from 120+ offices, and is "always subject to change" — [OSHA Establishment Search Help](https://www.osha.gov/help/establishment-search)
- ITA fields: `establishment_id` is "a unique number for each establishment that can be used to link establishment 300A data to 300/301 data", assigned when a user creates the establishment in ITA. `company_name` is the owning company's name. `ein` is the 9-digit IRS EIN — [OSHA ITA 300A Data Dictionary](https://www.osha.gov/sites/default/files/ITA_Data_Dictionary.pdf); [ITA Case Detail Data Dictionary 2026](https://www.osha.gov/sites/default/files/case_detail_data_dictionary_2026.pdf) (search summary)
- EIN collection: "On May 31, 2019, OSHA issued a memorandum to Regional Administrators encouraging Compliance Safety and Health Officers (CSHOs) to make efforts to obtain an Employer Identification Number (EIN) during an inspection". CSHOs are also to make "reasonable efforts to obtain the establishment's EIN prior to opening an inspection". A follow-up memo is dated 2020-12-22 — [OSHA memo](https://www.osha.gov/memos/2020-12-22/employer-identification-number) (search summary; page returned 403)
- In 2015, under the Fair Pay and Safe Workplaces executive order, CSHOs were told to request employer DUNS numbers, CAGE codes and parent-company identification, described as "a unified means of identifying companies on a government-wide database" — [OSHA Law Blog, June 2015](https://www.oshalawblog.com/2015/06/articles/osha-compliance-officers-instructed-to-collect-employer-data-for-fair-pay-and-safe-workplaces-executive-order/) (search summary)
- The public inspection table has these columns:
  - activity_nr, reporting_id, state_flag, estab_name;
  - site_address/city/state/zip;
  - owner_type, owner_code, adv_notice, safety_hlth, sic_code, naics_code;
  - insp_type, insp_scope, why_no_insp, union_status;
  - safety/health manuf/const/marit flags, migrant;
  - mail_street/city/state/zip;
  - **host_est_key**, nr_in_estab;
  - open_date, case_mod_date, close_conf_date, close_case_date, ld_dt.
  
  There is no EIN column. `host_est_key` is filled for some rows (e.g. activity_nr 18: `"N102    000024233"`) and blank for others — [labordata Datasette mirror of DOL OSHA enforcement data](https://labordata.bunkum.us/osha_enforcement/inspection)
- A separate `related_activity` table links inspections to related activities: activity_nr, rel_type (values seen include `C` and `R`), rel_act_nr, rel_safety, rel_health — [labordata Datasette](https://labordata.bunkum.us/osha_enforcement/related_activity); its FK wiring is in the [labordata/osha-enforcement Makefile](https://github.com/labordata/osha-enforcement)
- SST directive CPL 02-01-067 (April 2025) targets from CY2021–2023 ITA Form 300A data. The Area Office (AO) deletes an establishment that "has received a comprehensive safety or health inspection within 36 months", keyed to the opening-conference date, which "The SST interface tracks". Crucially: "After initiation of an inspection, the AO shall update the application to connect the inspection number with the particular establishment." Data discrepancies go to DTSEM's Office of Statistical Analysis. SST inspections are coded in OIS (e.g. `SSTARG23` in the National Emphasis Program field) — [OSHA CPL 02-01-067](https://www.osha.gov/sites/default/files/enforcement/directives/CPL-02-01-067.pdf); [Ogletree summary](https://ogletree.com/insights-resources/blog-posts/osha-issues-updated-guidance-for-site-specific-targeting-inspection-program/)
- Pre-ITA research access: JLT obtained the SST lists and ODI with DUNS through an MOU with OSHA. Caskey & Ozel's ODI data contained OSHA "unique identifiers not publicly available" — [JLT](https://www.hbs.edu/ris/Publication%20Files/improving%20regulatory%20effectiveness--final%20working%20paper_dbebc460-588b-4eb4-bf97-0f683bac5f70.pdf); [Ozel data page](https://sites.google.com/view/bugraozel/data)

### Inferences
- OSHA's own ITA→inspection link exists inside the SST application, but only for SST-targeted establishments, and it is entered by hand. It is not in any public file. A FOIA request for "SST establishment list with connected inspection numbers" or "ITA establishment_id to activity_nr" is a plausible ask, but I found no evidence anyone has obtained one.
- The JLT and Caskey-Ozel precedents show OSHA will share non-public identifiers (DUNS-bearing ODI, SST lists) with researchers under an MOU. That route may also work for EINs collected during inspections since 2019.
- `host_est_key` looks like an internal establishment key: an office code plus a zero-padded number. If it is consistent across inspections, it could be an OSHA-assigned establishment identifier. This is worth checking empirically on the project's 2016–2026 construction slice: how often it is populated, and whether one key spans several activity_nrs with different name spellings.
- `related_activity` may tie inspections from the same multi-employer construction site or the same complaint or referral together. That could link GC and sub inspections, but its rel_type codes need verifying.

### Gaps
- No public documentation of `host_est_key` was found. The DOL data dictionary URL now redirects to data.dol.gov and was not retrieved.
- I found no source explaining why `activity_nr` in the bulk file differs from inspection numbers shown on osha.gov, as the project observed.
- I found no FOIA'd crosswalk of OIS establishment IDs or ITA establishment_id to activity_nr.
- The full text of the 2019 and 2020 EIN memos, including whether EINs are stored in OIS and for what share of inspections, was not retrieved (403).

---

## 3. GAO and DOL OIG findings on data quality and employer identifiers

### Takeaway
GAO identified the missing corporate identifier as the core problem in 1996. In matching OSHA violators to federal contractors, it had to verify matches by telephone, could rebuild prior inspection histories for only about half of worksites, and said construction was the hardest sector. It recommended a corporate identification code, and OSHA said it was trying D&B and tax-ID cross-referencing. The DOL OIG later (2009) found OSHA routinely failed to find "related worksites" of high-risk employers under the Enhanced Enforcement Program.

### Cited Findings
- **GAO/HEHS-96-157 (1996), "Violations of Safety and Health Regulations by Federal Contractors"**
  - GAO matched OSHA's inspection database to GSA's federal contractor database. It then "verified by telephone that the company listed in the OSHA database of inspections was the same company (or owned by the same parent company)". The violator "might be a division, subsidiary, or have some other legal relationship with the federal contractor."
  - Result: 261 contractors with penalties of $15,000 or more across 345 FY1994 inspections, about 16% of significant-penalty inspections.
  - For construction, "this is likely an underestimate because of the difficulties we experienced verifying that worksites inspected in that industry were part of the same company".
  - "Because of omitted corporate identification numbers, we were only able to retrieve prior inspection information for about one-half of the worksites."
  - "A corporate identification code would make it easier for OSHA or a contracting agency to determine whether a company has a history of OSHA violations." OSHA was "automatically sending information regarding the worksite inspected to Dun & Bradstreet" and "experimenting with the use of tax identification numbers".
  - Sources: [govinfo HTML](https://www.govinfo.gov/content/pkg/GAOREPORTS-HEHS-96-157/html/GAOREPORTS-HEHS-96-157.htm); [GAO product page](https://www.gao.gov/products/hehs-96-157)
- **GAO/HEHS-97-43R (Dec 30, 1996), "OSHA's Inspection Database"**
  - IMIS did not "appropriately characterize or fully capture information on corporatewide or individual facility settlement agreements", which produced "distorted or inaccurate" violation counts and penalties.
  - By Dec 1997 OSHA had reviewed more than 1,000 cases and added a web disclaimer.
  - Source: [GAO](https://www.gao.gov/products/hehs-97-43r)
- **A later GAO report on DOD contractor safety (cited in a June 2019 letter from Sen. Warren to OSHA)**
  - According to the search summary, GAO said OSHA "does not require its staff to obtain and enter a corporate identification number in its inspection data, which is needed to match contracting data to inspection data", and recommended OSHA study the feasibility of requiring one and making the website searchable by it.
  - Source: [Warren letter PDF](https://www.warren.senate.gov/imo/media/doc/2019.06.17%20Letter%20to%20OSHA%20on%20GAO%20DOD%20Contractor%20Safety%20Report1.pdf) (search summary; GAO report number not verified)
- **DOL OIG Report 02-09-203-10-105 (March 2009), Enhanced Enforcement Program audit**
  - For 97% of sampled EEP-qualifying cases, OSHA failed at least one requirement: EEP designation, inspections of related worksites, enhanced follow-ups, or settlement provisions.
  - 29 cases were designated EEP with no enhanced action, and 16 of those employers later had 20 fatalities.
  - Source: [OIG highlights PDF](https://www.oig.dol.gov/public/reports/oa/2009/02-09-203-10-105b.pdf)
- **EEP definition of related establishments**
  - Establishments are related through common ownership, including a parent and subsidiaries in which the parent owns more than 50%.
  - Source: [OSHA CPL 02-00-145](https://www.osha.gov/enforcement/directives/cpl-02-00-145) (search summary)

### Inferences
- The project's failure modes (corporate families, divisions, construction worksites) are the same ones GAO hit in 1996 with telephone verification. Thirty years later, no public fix exists.
- OSHA itself struggles to find related worksites, which is the same problem as SVEP/EEP corporate-family identification. The project should not expect OSHA-side identifiers to solve corporate-family grouping.

### Gaps
- I found no recent GAO or OIG report (2015–2026) specifically on SVEP related-establishment identification or on a unique employer identifier in OIS.
- GAO-24-106413 (warehouse ergonomics, 2024) was checked and contains nothing on employer identifiers.
- I found no evidence that DOL's Chief Data Officer has created a cross-agency "employer" entity in the data.dol.gov enforcement API.

---

## 4. Journalism and NGO projects

### Takeaway
Good Jobs First's Violation Tracker is the only large, maintained, publicly described OSHA→parent-company linkage. It is manually checked, limited to large parents, and covers only cases with penalties of at least $5,000. Newsroom projects found in this search (Center for Public Integrity, The Oregonian, NELP, the Strategic Organizing Center, student projects) either avoided entity resolution or merged a handful of big brands by hand. I found no detailed published methodology ("nerd box") from ProPublica, Reveal, BuzzFeed, Bloomberg Law or The Markup on OSHA entity matching.

### Cited Findings
- **Violation Tracker, launch (Oct 2015)**
  - Covered environmental, health and safety cases with penalties of $5,000 or more since 2010 from 13 agencies, linked to more than 1,600 parents.
  - It reused "the same parent-subsidiary matching system" built for Subsidy Tracker.
  - Sources: [Dirt Diggers Digest, Oct 27 2015](https://dirtdiggersdigest.org/archives/4965)
- **Violation Tracker, OSHA inclusion rule**
  - Only "serious, willful or repeated violations of $5,000 or more after any negotiated reductions in OSHA's initial proposed fines".
  - Source: [Dirt Diggers Digest, Nov 5 2015](https://dirtdiggersdigest.org/archives/4986)
- **Violation Tracker, parent matching**
  - "Agency enforcement records usually do not indicate whether the company involved is part of a larger corporate entity." About 25,000 companies in agency records were matched to parents.
  - Parent universe: Fortune 1000, Fortune Global 500, S&P 500, Russell 3000, Forbes largest private companies, the Uniworld list of large foreign firms in the US, and the PEI top-100 private equity firms. "The system that generates parent-subsidiary matches is checked manually."
  - More than 3,000 parents are now aggregated, either large corporations or smaller firms with large penalties.
  - Sources: [Good Jobs First user guide](https://www.goodjobsfirst.org/violation-tracker-user-guide); [Violation Tracker OSHA page](https://violationtracker.goodjobsfirst.org/agency/OSHA) (search summary; both pages returned 403 to direct fetch)
- **Center for Public Integrity with Vox (Aug 2020)**
  - "Fewer inspectors, more deaths", an analysis of OSHA fatality inspections. The code is published as an R notebook (Joe Yerardi). It is an inspection-level analysis with no firm linkage described.
  - Source: [GitHub PublicI/osha-fatality-inspections](https://github.com/PublicI/osha-fatality-inspections)
- **The Oregonian**
  - Pipeline that downloads all OSHA enforcement files, normalises citation standard codes, geocodes site addresses, and uses `activity_nr` as an incremental bookmark. No employer deduplication.
  - Source: [GitHub TheOregonian/osha](https://github.com/TheOregonian/osha)
- **NELP "Warehousing Pain" (May 2022)**
  - Computed Amazon facility injury rates in New York from ITA data, filtering by NAICS 492110/4931xx. The methodological note says nothing about how Amazon establishments were identified.
  - Source: [NELP PDF](https://www.nelp.org/app/uploads/2022/05/Warehousing-Pain-Data-Brief-2022.pdf)
- **Strategic Organizing Center Amazon reports**
  - Limited the analysis to the largest employers with the largest warehouses so that employment and facility counts "could be more easily cross-verified with company publications and media reports".
  - Source: [SOC, "Failure to Deliver"](https://thesoc.org/resources/failure-to-deliver-amazon-falls-short-on-safety/) (search summary)
- **Lede student project on high-penalty OSHA cases**
  - Found "the same employers were sometimes listed under different names" and merged them by hand with substring rules, e.g. "Dollar Tree" + "Family Dollar", and "Dolgencorp" → Dollar General.
  - Source: [GitHub davidmhorowitz/Lede_Project-3](https://github.com/davidmhorowitz/Lede_Project-3_OSHA-high-fine-violations)

### Inferences
- Violation Tracker's parent→subsidiary name lists could seed the project's corporate-family rules for large GCs and homebuilders (e.g. D.R. Horton divisions). They will not help with small subcontractors: they fall below the parent universe and often below the $5,000 threshold.
- The "Dolgencorp → Dollar General" case is the same legal-entity-vs-brand problem as the project's DBA and renamed-company failures.

### Gaps
- I could not find, in the time available, published methodologies from ProPublica (e.g. temp-worker investigations), Reveal/CIR (Amazon), BuzzFeed, Bloomberg Law or The Markup describing OSHA entity matching.
- Violation Tracker's current OSHA record counts, threshold changes since 2015, and bulk-download or licensing terms were not confirmed (403).

---

## 5. Open-source code and reusable artefacts (status Oct 2026)

### Takeaway
A few public repositories do OSHA entity resolution. Two use the `dedupe` active-learning library (dchud/osha-dedupe; labordata/employer-links, which also does OSHA↔WHD). One recent rule-based pipeline (HockerAI, Sept 2026) is close to the project's design: ZIP blocking, normalised name or address, union-find. None publishes labelled training pairs. The only public firm crosswalk found is Caskey & Ozel's GVKEY↔ODI names file. Academic link files from BLS and Census are on-site only.

### Cited Findings
- **dchud/osha-dedupe** (created ~2016, last updated 2023)
  - An "experimental/learning project" running Python `dedupe` with PostgreSQL on more than 4M `osha_inspection` records, adapted from DataMade's pgsql_big_dedupe example. It includes a fixture sample.
  - The training file (`training.json`) is created interactively and is not committed. The repo contains config.json, create-table.sql, fixtures and pgdedupe.py.
  - Source: [GitHub](https://github.com/dchud/osha-dedupe)
- **labordata/employer-links** (created Oct 2022, last push Feb 2023)
  - (1) `whd_dedupe.py` deduplicates WHD WHISARD cases on trade_nm, legal_name, street, city, state (exact + string) and naics. It clusters at threshold 0.5 and assigns `lbd-establishment/<uuid>` entity IDs.
  - (2) `osha_link.py` trains a `dedupe.Gazetteer` linking a random 10,000 unique OSHA inspection name/address/NAICS rows to the WHD canonical entities. OSHA `estab_name` is fed as *both* trade and legal name because OSHA has a single name field.
  - Committed artefacts: `establishment/learned_settings` and `establishment/gazetteer.db`, plus an `EstablishmentGazetteer` class with SQLite blocking. Training JSON is not committed. No match-rate reporting.
  - Sources: [GitHub labordata/employer-links](https://github.com/labordata/employer-links); [Makefile](https://github.com/labordata/employer-links/blob/main/Makefile)
- **labordata/osha-enforcement**
  - Builds a SQLite or Datasette copy of all DOL OSHA enforcement tables with foreign keys: inspection, violation, accident, accident_injury.rel_insp_nr, related_activity, optional_info, strategic_codes, violation_event, and others. Served at labordata.bunkum.us.
  - The same organisation hosts WHD compliance, NLRB, FMCS F-7 and USAspending mirrors.
  - Sources: [GitHub](https://github.com/labordata/osha-enforcement); [labordata org](https://github.com/labordata)
- **Dipzinski/HockerAI** (Sept–Oct 2026)
  - Processes 5.2M inspections. `facilities.py` merges records into facilities when they share a ZIP and either have the same normalised name, or the same normalised street address and a "similar" name (same first word, or token Jaccard ≥ 0.5), grouped with union-find.
  - Name normalisation: uppercase; `&`→AND; strip punctuation; drop legal suffixes (INC, LLC, CO, CORP, LTD, LP, LLP, PLLC, PC, THE); cut everything after "DBA" / "D/B/A"; strip state-record prefixes such as `"110584 - ACME INC"`.
  - Address normalisation: USPS-style abbreviations; drop STE/UNIT/BLDG/#; only addresses containing digits are used.
  - Result: 14,445 inspections → 8,914 facilities, of which 845 had 2+ name spellings. It also has an LLM (Claude) step with code-level grounding checks.
  - Source: [GitHub README](https://github.com/Dipzinski/HockerAI); [facilities.py](https://github.com/Dipzinski/HockerAI/blob/main/hocker/facilities.py)
- **dmil/osha-establishment-search** (2022)
  - Notebook scraper for osha.gov's Establishment Search.
  - Source: [GitHub](https://github.com/dmil/osha-establishment-search)
- **Caskey & Ozel linking file**
  - Compustat GVKEY ↔ OSHA ODI establishment names, 2002–2011, publicly downloadable from Google Drive.
  - Source: [Ozel data page](https://sites.google.com/view/bugraozel/data)
- **Cohn, Nestoriak & Wardlaw link files**
  - Buyout firm ↔ SOII establishments, held at BLS for on-site access only.
  - Source: [PDF](https://faculty.mccombs.utexas.edu/jonathan.cohn/papers/PE_buyouts_and_workplace_safety_2020dec.pdf)
- **Archives**
  - DataLumos holds OSHA IMIS and enforcement data snapshots (projects 248068 and 100441).
  - The Data Liberation Project exists, but I found no OSHA employer-matching product from it.
  - Sources: [DataLumos OSHA IMIS](https://www.datalumos.org/datalumos/project/248068/version/V1/view); [DataLumos OSHA Enforcement](https://www.datalumos.org/datalumos/project/100441/version/V1/view); [Data Liberation Project](https://www.data-liberation-project.org/)
- **Commercial or hobby wrappers**
  - Several Apify actors scrape OSHA and DOL data. One combines OSHA inspections with WHD cases; its matching method is not described. A third-party write-up recommends EIN as the primary key with fuzzy-name fallback, and warns that contractor names can differ from both the establishment name and the DBA.
  - Sources: [Apify retrainmap/dol-enforcement](https://apify.com/retrainmap/dol-enforcement); [morvs.ai](https://morvs.ai/writing/osha-inspection-enforcement/)

### Inferences
- The project's establishment grouping uses exact cleaned name + address + zip + state. That is stricter than HockerAI's rule, which merges the same name within a ZIP regardless of address, and merges similar names at the same address. HockerAI's 845/8,914 (~9.5%) multi-spelling rate is a rough external benchmark for how much variant-merging a looser rule adds, though in manufacturing rather than construction. Construction is site-based, so address keys behave differently: site addresses are jobsites, and mail addresses are the better firm key.
- `dedupe` Gazetteer (labordata) is the closest open-source analogue to "match a user-entered entity against a canonical OSHA set". It is a reusable template, but there are no labelled pairs to borrow. The project's own labelled eval set appears to be more than anything public.
- I found no public OSHA↔WHD, OSHA↔ITA or OSHA↔licence crosswalk with labels.

### Gaps
- GitHub code search, as opposed to repo search, was not run. Smaller scripts inside other projects (e.g. ITA+inspection joins) may exist.
- Enigma's historical OSHA datasets and any entity IDs they carried were not checked.
- `gazetteer.db` in labordata/employer-links was not inspected for size or contents.

---

## 6. Linking OSHA to DOL WHD data

### Takeaway
The only public OSHA↔WHD employer-linking code found is labordata/employer-links: a 2022–23 `dedupe` Gazetteer with no published evaluation or labels. In practice, cross-agency employer aggregation is done through Violation Tracker's manually checked parent matching, which covers large firms only.

### Cited Findings
- labordata/employer-links deduplicates WHD WHISARD cases into canonical entities, then trains a Gazetteer to attach OSHA inspections, using fields trade_nm, legal_name, street_addr_1_txt, cty_nm, st_cd and naic_cd — [GitHub](https://github.com/labordata/employer-links)
- WHD data is richer for matching than OSHA: WHISARD has separate `trade_nm` and `legal_name` fields, whereas OSHA has only `estab_name` — [employer-links Makefile SQL](https://github.com/labordata/employer-links/blob/main/Makefile)
- Violation Tracker covers both OSHA and WHD cases under the same parent matching. Researchers such as Raghunandan use it to link WHD data to Compustat — [Raghunandan 2021](https://researchonline.lse.ac.uk/id/eprint/109863/2/Raghunandan_financial_misconduct_employee_mistreatment_published.pdf); [Good Jobs First](https://www.goodjobsfirst.org/violation-tracker-user-guide) (search summary)

### Inferences
- WHD's separate legal and trade name fields could serve as a DBA dictionary for the project. A WHD case whose `trade_nm` matches an OSHA estab_name and whose `legal_name` matches the sub's legal name, in the same city or ZIP, would be evidence for DBA links. This is an untested idea, not something prior work reports.

### Gaps
- I found no DOL-published OSHA↔WHD employer crosswalk and no evaluation of the labordata linker.
