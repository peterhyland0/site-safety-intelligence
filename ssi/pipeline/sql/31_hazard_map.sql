-- Hazard category for every citation.
-- Needs: 02_standard_macros.sql installed; stg_violation(activity_nr, citation_id, standard_raw, site_state, ...);
--        ref_standard_hazard_map loaded from ssi/pipeline/ref/standard_hazard_map.csv.
-- Produces: violation_hazard(activity_nr, citation_id, std_family, standard_cite, section_key, hazard_code),
--           one row per stg_violation row, hazard_code never NULL ('other' when nothing matches).
--
-- Matching (per std_family, on section_key):
--   1. exact   section_key = pattern
--   2. range   std_natural_key(pattern) <= std_natural_key(section_key) <= std_natural_key(range_to) || '~'
--              (inclusive; the '~' makes range_to cover its own subsections, e.g. T8 CCR 1541 covers 1541.1)
--   3. prefix  starts_with(section_key, pattern)
--   Exact beats range beats prefix. Ties inside a type go to the most specific rule: the innermost range
--   (highest lower bound, then lowest upper bound) or the longest prefix. No match -> 'other'.
-- Rules are matched against the distinct (family, section_key) pairs (tens of thousands), then joined back,
-- so the cost does not grow with the number of rules times citations.

CREATE OR REPLACE TABLE violation_hazard AS
WITH parsed AS (
    SELECT activity_nr, citation_id, std_parse_with_state(standard_raw, site_state) AS p
    FROM stg_violation
),
keys AS (
    SELECT DISTINCT p.std_family AS std_family, p.section_key AS section_key,
           std_natural_key(p.section_key) AS nk
    FROM parsed
    WHERE p.section_key IS NOT NULL
),
rules AS (
    SELECT family, match_type, pattern, hazard_code,
           CASE match_type WHEN 'exact' THEN 1 WHEN 'range' THEN 2 WHEN 'prefix' THEN 3 END AS type_rank,
           std_natural_key(pattern) AS lo,
           std_natural_key(coalesce(nullif(trim(range_to), ''), pattern)) || '~' AS hi,
           length(pattern) AS plen
    FROM ref_standard_hazard_map
),
matched AS (
    SELECT k.std_family, k.section_key, r.hazard_code, r.type_rank, r.lo, r.hi, r.plen
    FROM keys k
    JOIN rules r ON r.family = k.std_family
    WHERE (r.match_type = 'exact' AND k.section_key = r.pattern)
       OR (r.match_type = 'range' AND k.nk >= r.lo AND k.nk <= r.hi)
       OR (r.match_type = 'prefix' AND starts_with(k.section_key, r.pattern))
),
best AS (
    SELECT std_family, section_key, hazard_code
    FROM matched
    QUALIFY row_number() OVER (
        PARTITION BY std_family, section_key
        ORDER BY type_rank, lo DESC, hi ASC, plen DESC, hazard_code) = 1
)
SELECT pa.activity_nr,
       pa.citation_id,
       pa.p.std_family AS std_family,
       pa.p.standard_cite AS standard_cite,
       pa.p.section_key AS section_key,
       coalesce(b.hazard_code, 'other') AS hazard_code
FROM parsed pa
LEFT JOIN best b
  ON b.std_family = pa.p.std_family AND b.section_key = pa.p.section_key;
