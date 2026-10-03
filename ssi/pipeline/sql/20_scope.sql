-- Scope. Industry codes drift within a company (44% of firms with 5+ inspections carry several NAICS codes),
-- so filtering each inspection on its own code would drop part of a sub's history. Two passes instead:
--   1. compute the establishment key (cleaned name + address key + zip + state) for EVERY inspection;
--   2. keep every inspection of any establishment that has at least one construction-coded inspection.
-- scope_reason records why each inspection is in.
CREATE OR REPLACE TABLE name_clean AS
SELECT estab_name, clean_name(estab_name) AS clean_name
FROM (SELECT DISTINCT estab_name FROM raw_inspection);

CREATE OR REPLACE TABLE addr_clean AS
SELECT mail_street, addr_key(mail_street) AS addr_key, clean_addr(mail_street) AS addr_clean, addr_unit(mail_street) AS addr_unit
FROM (SELECT DISTINCT mail_street FROM raw_inspection);

CREATE OR REPLACE TABLE insp_key AS
SELECT i.activity_nr,
       n.clean_name,
       a.addr_key, a.addr_clean, a.addr_unit,
       zip5(i.mail_zip) AS zip5,
       nullif(upper(trim(i.mail_state)), '') AS mail_state,
       establishment_key(n.clean_name, a.addr_key, zip5(i.mail_zip), nullif(upper(trim(i.mail_state)), '')) AS establishment_key,
       coalesce(i.naics_code LIKE '23%', false) AS is_naics23,
       coalesce(left(i.sic_code, 2) IN ('15', '16', '17'), false) AS is_sic_construction,
       is_placeholder(n.clean_name) AS is_placeholder
FROM raw_inspection i
LEFT JOIN name_clean n ON n.estab_name IS NOT DISTINCT FROM i.estab_name
LEFT JOIN addr_clean a ON a.mail_street IS NOT DISTINCT FROM i.mail_street;

-- Placeholder employers ("UNKNOWN") never pull in other inspections: their key isn't a real company.
CREATE OR REPLACE TABLE construction_keys AS
SELECT DISTINCT establishment_key FROM insp_key
WHERE (is_naics23 OR is_sic_construction) AND NOT is_placeholder;

CREATE OR REPLACE TABLE scope AS
SELECT k.activity_nr, k.establishment_key,
       CASE WHEN k.is_naics23 THEN 'naics23'
            WHEN k.is_sic_construction THEN 'sic15_17'
            ELSE 'same_establishment' END AS scope_reason
FROM insp_key k
WHERE (k.is_naics23 OR k.is_sic_construction)
   OR k.establishment_key IN (SELECT establishment_key FROM construction_keys);
