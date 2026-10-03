-- entity.establishment: inspections grouped ONLY when cleaned name, address key, zip and state are identical.
-- Deliberately conservative: a wrong split costs a little review; a wrong merge silently attaches someone
-- else's history. Companies are assembled from establishments per GC sub, at match time.
CREATE OR REPLACE TABLE est_naics AS
SELECT establishment_key, left(naics_code, 4) AS naics4, count(*) AS n
FROM wh.osha.inspection WHERE naics_code IS NOT NULL GROUP BY ALL;

CREATE OR REPLACE TABLE est_sic AS
SELECT establishment_key, sic_code AS sic4, count(*) AS n
FROM wh.osha.inspection WHERE sic_code IS NOT NULL GROUP BY ALL;

CREATE OR REPLACE TABLE wh.entity.establishment AS
WITH base AS (
  SELECT establishment_key,
         any_value(clean_name) AS clean_name,
         any_value(addr_key) AS addr_key,
         any_value(mail_zip) AS zip5,
         any_value(mail_state) AS state,
         -- most common value; ties broken alphabetically (mode() picks arbitrarily between ties)
         first(estab_name_raw ORDER BY name_n DESC, estab_name_raw) AS display_name,
         first(addr_clean ORDER BY addr_n DESC NULLS LAST, addr_clean NULLS LAST) AS address,
         first(mail_city ORDER BY city_n DESC NULLS LAST, mail_city NULLS LAST) AS city,
         list(DISTINCT estab_name_raw ORDER BY estab_name_raw)[1:25] AS name_variants,
         min(open_date) AS first_seen,
         max(open_date) AS last_seen,
         count(*) AS insp_n,
         count(*) FILTER (WHERE scope_reason IN ('naics23', 'sic15_17')) AS construction_insp_n,
         list(DISTINCT site_state ORDER BY site_state) FILTER (WHERE site_state IS NOT NULL) AS site_states
  FROM (SELECT *,
               count(*) OVER (PARTITION BY establishment_key, estab_name_raw) AS name_n,
               count(addr_clean) OVER (PARTITION BY establishment_key, addr_clean) AS addr_n,
               count(mail_city) OVER (PARTITION BY establishment_key, mail_city) AS city_n
        FROM wh.osha.inspection)
  GROUP BY 1
),
naics AS (SELECT establishment_key, first(naics4 ORDER BY n DESC, naics4) AS naics4 FROM est_naics GROUP BY 1),
sic AS (SELECT establishment_key, first(sic4 ORDER BY n DESC, sic4) AS sic4 FROM est_sic GROUP BY 1)
SELECT b.*,
       name_core(b.clean_name) AS name_core,
       legal_part(b.clean_name) AS legal_name,
       dba_part(b.clean_name) AS dba_name,
       n.naics4 AS primary_naics4,
       s.sic4 AS primary_sic4,
       is_placeholder(b.clean_name) AS is_placeholder,
       is_jv(b.clean_name) AS is_jv,
       sibling_suffix(b.clean_name) AS sibling_suffix
FROM base b LEFT JOIN naics n USING (establishment_key) LEFT JOIN sic s USING (establishment_key);

-- membership is stored so a later rule change can remap old keys to new ones by inspection overlap
CREATE OR REPLACE TABLE wh.entity.establishment_member AS
SELECT establishment_key, activity_nr FROM wh.osha.inspection;

-- searchable aliases: the cleaned name, plus legal and trade names of "X DBA Y"
CREATE OR REPLACE TABLE wh.entity.establishment_alias AS
SELECT establishment_key, clean_name AS alias, 'clean' AS kind FROM wh.entity.establishment
UNION ALL
SELECT establishment_key, legal_name, 'legal' FROM wh.entity.establishment WHERE dba_name IS NOT NULL
UNION ALL
SELECT establishment_key, dba_name, 'dba' FROM wh.entity.establishment WHERE dba_name IS NOT NULL;
