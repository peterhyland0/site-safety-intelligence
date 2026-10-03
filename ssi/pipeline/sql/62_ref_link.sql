-- Link reference records to OSHA establishments (same state). M1 = cleaned name + zip, M2 = cleaned name
-- + address key (both ~95%+ precise in the evaluation); M3 = same address key + zip with a near-identical
-- name (about 85% precise): shown as "possible", never counted.
CREATE OR REPLACE TABLE ref_candidates AS
SELECT 'ita' AS source, establishment_id AS ref_id, company_clean AS clean, state, zip5, addr_key FROM ita_est_year
UNION
SELECT 'ita', establishment_id, establishment_clean, state, zip5, addr_key FROM ita_est_year
UNION
SELECT 'licence:' || source, number, clean_name, state, zip5, addr_key FROM wh.ref_ext.licence
UNION
SELECT 'licence:' || source, number, dba_clean, state, zip5, addr_key FROM wh.ref_ext.licence WHERE dba_clean IS NOT NULL;

CREATE OR REPLACE TABLE wh.entity.ref_link AS
WITH est AS (SELECT establishment_key, clean_name, state, zip5, addr_key FROM wh.entity.establishment WHERE NOT is_placeholder),
m1 AS (SELECT e.establishment_key, r.source, r.ref_id, 'M1' AS method FROM est e
       JOIN ref_candidates r ON r.clean = e.clean_name AND r.state = e.state AND r.zip5 = e.zip5),
m2 AS (SELECT e.establishment_key, r.source, r.ref_id, 'M2' FROM est e
       JOIN ref_candidates r ON r.clean = e.clean_name AND r.state = e.state AND r.addr_key = e.addr_key),
m3 AS (SELECT e.establishment_key, r.source, r.ref_id, 'M3' FROM est e
       JOIN ref_candidates r ON r.addr_key = e.addr_key AND r.zip5 = e.zip5 AND r.state = e.state
       WHERE r.clean <> e.clean_name AND length(r.clean) >= 5 AND length(e.clean_name) >= 5
         AND jaro_winkler_similarity(r.clean, e.clean_name) >= 0.93)
SELECT establishment_key, source, ref_id, min(method) AS method
FROM (SELECT * FROM m1 UNION ALL SELECT * FROM m2 UNION ALL SELECT * FROM m3)
GROUP BY 1, 2, 3;

-- keep ITA rows that link to an OSHA establishment, plus all construction rows (for benchmarks)
CREATE OR REPLACE TABLE wh.ref_ext.ita_establishment_year AS
SELECT * FROM ita_est_year
WHERE naics LIKE '23%' OR establishment_id IN (SELECT ref_id FROM wh.entity.ref_link WHERE source = 'ita');

-- injury-rate benchmarks per trade and year, over plausible filings only
CREATE OR REPLACE TABLE wh.mart.ita_benchmark AS
-- trir_pooled = all peers' cases / all peers' hours (how BLS reports industry rates); medians are often 0
-- because most small filers report no cases, so the pooled rate is the comparison shown to the GC.
SELECT left(naics, 4) AS naics4, year, count(*) AS peer_n,
       sum(dafw + djtr + other_cases) * 200000.0 / sum(hours) AS trir_pooled,
       sum(dafw + djtr) * 200000.0 / sum(hours) AS dart_pooled,
       quantile_cont(trir, 0.5) AS trir_p50, quantile_cont(trir, 0.75) AS trir_p75,
       quantile_cont(dart, 0.5) AS dart_p50, quantile_cont(dart, 0.75) AS dart_p75
FROM ita_est_year
WHERE naics LIKE '23%' AND len(dq_flags) = 0 AND hours >= 20000
GROUP BY 1, 2;
