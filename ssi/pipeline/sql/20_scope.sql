-- Scope. Industry codes drift within a company (44% of firms with 5+ inspections carry several NAICS codes),
-- so filtering each inspection on its own code would drop part of a sub's history. Two passes instead:
--   1. compute the establishment key (cleaned name + address key + zip + state) for EVERY inspection;
--   2. keep every inspection of any establishment that has at least one construction-coded inspection.
-- scope_reason records why each inspection is in.
--
-- History window: only inspections opened in the last {{HISTORY_YEARS}} years before the newest inspection
-- in the data are kept (0 = every year back to 1972). Set with SSI_HISTORY_YEARS. Whether an establishment
-- is a construction company is decided from ALL years first: codes drift, and a contractor coded as
-- construction in 2012 but differently since must keep its recent inspections.
CREATE OR REPLACE TABLE history_window AS
SELECT CASE WHEN {{HISTORY_YEARS}} > 0 THEN (max_open - INTERVAL ({{HISTORY_YEARS}}) YEAR)::DATE
            ELSE DATE '1900-01-01' END AS since
FROM (SELECT max(try_cast(left(open_date, 10) AS DATE)) AS max_open FROM raw_inspection);

CREATE OR REPLACE TABLE raw_inspection_window AS
SELECT * FROM raw_inspection
WHERE try_cast(left(open_date, 10) AS DATE) >= (SELECT since FROM history_window);
CREATE OR REPLACE TABLE name_clean AS
SELECT estab_name, clean_name(estab_name) AS clean_name, name_core(clean_name(estab_name)) AS core
FROM (SELECT DISTINCT estab_name FROM raw_inspection);

CREATE OR REPLACE TABLE addr_clean AS
SELECT mail_street, addr_key(mail_street) AS addr_key, clean_addr(mail_street) AS addr_clean, addr_unit(mail_street) AS addr_unit
FROM (SELECT DISTINCT mail_street FROM raw_inspection);

CREATE OR REPLACE TABLE insp_key AS
SELECT i.activity_nr,
       n.clean_name, n.core,
       a.addr_key, a.addr_clean, a.addr_unit,
       zip5(i.mail_zip) AS zip5,
       nullif(upper(trim(i.mail_state)), '') AS mail_state,
       establishment_key(n.clean_name, a.addr_key, zip5(i.mail_zip), nullif(upper(trim(i.mail_state)), '')) AS establishment_key,
       coalesce(i.naics_code LIKE '23%', false) AS is_naics23,
       -- SIC codes are 4 digits; some loads drop the leading zero ('175' is 0175 orchards, not 17xx construction)
       coalesce(left(lpad(trim(i.sic_code), 4, '0'), 2) IN ('15', '16', '17'), false) AS is_sic_construction,
       is_placeholder(n.clean_name) AS is_placeholder,
       coalesce(try_cast(left(i.open_date, 10) AS DATE) >= (SELECT since FROM history_window), false) AS in_window
FROM raw_inspection i
LEFT JOIN name_clean n ON n.estab_name IS NOT DISTINCT FROM i.estab_name
LEFT JOIN addr_clean a ON a.mail_street IS NOT DISTINCT FROM i.mail_street;

-- Placeholder employers ("UNKNOWN") never pull in other inspections: their key isn't a real company.
CREATE OR REPLACE TABLE construction_keys AS
SELECT establishment_key, bool_or(in_window) AS coded_in_window
FROM insp_key
WHERE (is_naics23 OR is_sic_construction) AND NOT is_placeholder
GROUP BY 1;

-- Related facilities: a construction company's plant, yard or shop is often coded under another industry
-- (Tindall's Conley GA precast plant is concrete manufacturing), so scope by establishment misses it. Bring in
-- records whose company name matches a construction establishment's, but only for names that are distinctive
-- across ALL industries (5 or fewer full-name variants in any year), long enough (one word of 6+ letters, or
-- several words), and not a person's name. They are 'related_name': the matcher never counts them on the
-- name alone (only once confirmed, or at an address the company uses).
CREATE OR REPLACE TABLE core_variety AS
SELECT core, count(DISTINCT clean_name) AS variety
FROM insp_key WHERE NOT is_placeholder AND core <> '' GROUP BY 1;

CREATE OR REPLACE TABLE related_cores AS
WITH g AS (SELECT list(upper(trim(name))) AS names FROM ref_given_name),
c AS (SELECT DISTINCT k.core, string_split(k.core, ' ') AS tok
      FROM insp_key k JOIN construction_keys USING (establishment_key)
      WHERE NOT k.is_placeholder AND k.core <> '')
SELECT c.core
FROM c JOIN core_variety v USING (core), g
WHERE v.variety <= {{DISTINCTIVE_MAX_VARIETY}}
  AND CASE WHEN len(c.tok) = 1 THEN length(c.core) >= 6 ELSE length(c.core) >= 5 END
  AND NOT (len(c.tok) BETWEEN 2 AND 4 AND regexp_full_match(c.core, '[A-Z]+( [A-Z]+)*')
           AND (list_contains(g.names, c.tok[1]) OR (len(c.tok) = 2 AND list_contains(g.names, c.tok[2]))));

-- same_establishment: coded as construction on another in-window inspection;
-- construction_history: coded as construction only before the window;
-- related_name: another facility of a construction company (see above)
CREATE OR REPLACE TABLE scope AS
SELECT k.activity_nr, k.establishment_key,
       CASE WHEN k.is_naics23 THEN 'naics23'
            WHEN k.is_sic_construction THEN 'sic15_17'
            WHEN c.coded_in_window THEN 'same_establishment'
            WHEN c.establishment_key IS NOT NULL THEN 'construction_history'
            ELSE 'related_name' END AS scope_reason
FROM insp_key k
LEFT JOIN construction_keys c USING (establishment_key)
WHERE k.in_window AND (k.is_naics23 OR k.is_sic_construction OR c.establishment_key IS NOT NULL
                       OR (NOT k.is_placeholder AND k.core IN (SELECT core FROM related_cores)));
