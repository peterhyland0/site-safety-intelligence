-- How distinctive is a name? Measured from the data, by the variety of distinct full names that share
-- the same core (e.g. TURNER has hundreds -> generic; BRASFIELD GORRIE has a handful -> distinctive).
-- Counting establishments instead would wrongly mark a big multi-office firm as generic.
-- A core that is a person's name (sole proprietors) gets tier 'person': the same name is usually many
-- different people (JOSE HERNANDEZ: 49 records in 17 states), so only a city or address can tie a record
-- to a sub. Mirrors ssi.matching.candidates.is_person_core (same list: ref/given_name.csv).
CREATE OR REPLACE TABLE wh.entity.core_stats AS
WITH c AS (
  SELECT name_core,
         count(DISTINCT clean_name) AS variety,
         count(*) AS establishment_n,
         count(DISTINCT state) AS state_n,
         initials_only(min(clean_name)) AS initials_only,
         string_split(name_core, ' ') AS tok
  FROM wh.entity.establishment
  WHERE NOT is_placeholder
  GROUP BY 1
), g AS (SELECT list(upper(trim(name))) AS names FROM ref_given_name),
p AS (
  SELECT c.*, (len(tok) BETWEEN 2 AND 4 AND regexp_full_match(name_core, '[A-Z]+( [A-Z]+)*')
               AND (list_contains(g.names, tok[1]) OR (len(tok) = 2 AND list_contains(g.names, tok[2])))) AS is_person
  FROM c, g
)
SELECT name_core, variety, establishment_n, state_n, initials_only, is_person,
       CASE WHEN name_core = '' OR initials_only THEN 'generic'
            WHEN is_person THEN 'person'
            WHEN variety >= {{GENERIC_MIN_VARIETY}} THEN 'generic'
            WHEN variety <= {{DISTINCTIVE_MAX_VARIETY}} THEN 'distinctive'
            ELSE 'medium' END AS tier
FROM p;

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
