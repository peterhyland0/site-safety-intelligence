-- How distinctive is a name? Measured from the data, by the variety of distinct full names that share
-- the same core (e.g. TURNER has hundreds -> generic; BRASFIELD GORRIE has a handful -> distinctive).
-- Counting establishments instead would wrongly mark a big multi-office firm as generic.
CREATE OR REPLACE TABLE wh.entity.core_stats AS
SELECT name_core,
       count(DISTINCT clean_name) AS variety,
       count(*) AS establishment_n,
       count(DISTINCT state) AS state_n,
       initials_only(any_value(clean_name)) AS initials_only,
       CASE WHEN name_core = '' OR initials_only(any_value(clean_name)) OR count(DISTINCT clean_name) >= {{GENERIC_MIN_VARIETY}} THEN 'generic'
            WHEN count(DISTINCT clean_name) <= {{DISTINCTIVE_MAX_VARIETY}} THEN 'distinctive'
            ELSE 'medium' END AS tier
FROM wh.entity.establishment
WHERE NOT is_placeholder
GROUP BY 1;

-- Shared offices: an address used by many different name cores (registered agents, office buildings,
-- builders' per-project LLCs) must never be used to pull records into a match.
CREATE OR REPLACE TABLE wh.entity.address_stats AS
SELECT addr_key, zip5, count(DISTINCT name_core) AS core_n,
       count(DISTINCT name_core) >= {{SHARED_OFFICE_MIN_CORES}} AS is_shared_office
FROM wh.entity.establishment
WHERE addr_key IS NOT NULL AND NOT is_placeholder
GROUP BY 1, 2;

-- Token blocking index for candidate search (DuckDB has no trigram index): each establishment is
-- findable by each non-generic token of its name; rare tokens are searched first.
CREATE OR REPLACE TABLE wh.entity.name_token AS
SELECT DISTINCT a.establishment_key, t.token
FROM wh.entity.establishment_alias a,
     LATERAL (SELECT unnest(string_split(a.alias, ' ')) AS token) t
WHERE length(t.token) >= 2 AND NOT list_contains(ssi_generic_tokens(), t.token);

CREATE OR REPLACE TABLE wh.entity.token_df AS
SELECT token, count(DISTINCT establishment_key) AS df FROM wh.entity.name_token GROUP BY 1;
