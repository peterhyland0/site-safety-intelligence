-- OSHA Injury Tracking Application (Form 300A summaries, 2016-2025): self-reported hours worked and
-- injury counts per establishment and year -> TRIR/DART. Used for enrichment only: an EIN is evidence
-- for the adjudicator, never an automatic merge (big firms file under many EINs; some EINs are junk).
CREATE OR REPLACE TABLE ita_raw AS
SELECT * FROM read_csv('{{REFERENCE_RAW}}/osha_ita/utf8/*.csv', all_varchar = true, header = true,
                       quote = '"', escape = '"', union_by_name = true, filename = true, ignore_errors = true);

CREATE OR REPLACE TABLE ita_rows AS
SELECT try_cast(id AS BIGINT) AS ita_id,
       try_cast(try_cast(year_filing_for AS DOUBLE) AS INTEGER) AS year,
       establishment_id,
       company_name, establishment_name,
       regexp_replace(coalesce(ein, ''), '[^0-9]', '', 'g') AS ein_digits,
       street_address, city, nullif(upper(trim(state)), '') AS state, zip5(zip_code) AS zip5,
       addr_key(street_address) AS addr_key,
       left(regexp_replace(coalesce(naics_code, ''), '[^0-9]', '', 'g'), 6) AS naics,
       try_cast(annual_average_employees AS DOUBLE) AS employees,
       try_cast(total_hours_worked AS DOUBLE) AS hours,
       try_cast(try_cast(total_deaths AS DOUBLE) AS INTEGER) AS deaths,
       coalesce(try_cast(try_cast(total_dafw_cases AS DOUBLE) AS INTEGER), 0) AS dafw,
       coalesce(try_cast(try_cast(total_djtr_cases AS DOUBLE) AS INTEGER), 0) AS djtr,
       coalesce(try_cast(try_cast(total_other_cases AS DOUBLE) AS INTEGER), 0) AS other_cases,
       created_timestamp
FROM ita_raw
QUALIFY row_number() OVER (PARTITION BY establishment_id, try_cast(try_cast(year_filing_for AS DOUBLE) AS INTEGER)
                           ORDER BY try_cast(id AS BIGINT) DESC) = 1;

-- EINs shared by many unrelated company names are placeholders, not identities
CREATE OR REPLACE TABLE ita_junk_ein AS
SELECT ein_digits FROM ita_rows WHERE length(ein_digits) = 9
GROUP BY 1 HAVING count(DISTINCT split_part(upper(trim(company_name)), ' ', 1)) > 25;

CREATE OR REPLACE TABLE ita_est_year AS
SELECT r.* EXCLUDE (ein_digits),
       CASE WHEN length(r.ein_digits) = 9 AND r.ein_digits NOT IN ('000000000', '111111111', '999999999', '123456789', '987654321')
             AND r.ein_digits NOT IN (SELECT ein_digits FROM ita_junk_ein) THEN r.ein_digits END AS ein,
       clean_name(r.company_name) AS company_clean,
       clean_name(r.establishment_name) AS establishment_clean,
       CASE WHEN r.hours > 0 THEN (r.dafw + r.djtr + r.other_cases) * 200000.0 / r.hours END AS trir,
       CASE WHEN r.hours > 0 THEN (r.dafw + r.djtr) * 200000.0 / r.hours END AS dart,
       list_filter([
         CASE WHEN coalesce(r.hours, 0) <= 0 THEN 'hours_missing' END,
         CASE WHEN r.employees > 0 AND r.hours > 0 AND (r.hours / r.employees < 500 OR r.hours / r.employees > 4000)
              THEN 'hours_per_employee_implausible' END,
         CASE WHEN r.hours > 0 AND r.hours < 20000 THEN 'too_small_to_rate' END,
         CASE WHEN r.hours > 0 AND (r.dafw + r.djtr + r.other_cases) * 200000.0 / r.hours > 50 THEN 'rate_implausible' END
       ], lambda f: f IS NOT NULL) AS dq_flags
FROM ita_rows r;
