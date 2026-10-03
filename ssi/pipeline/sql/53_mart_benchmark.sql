-- mart.trade_benchmark: how a sub compares with peers in the same trade. Peers are establishments with
-- at least {{MIN_RATED}} rated inspections in the window; published as median/p75/p90 (not the mean,
-- so one mega-contractor can't skew it). Levels: NAICS4 -> NAICS3 -> all construction; the query
-- layer picks the most specific level with enough peers.
CREATE OR REPLACE TABLE as_of AS SELECT max(open_date) AS data_as_of FROM wh.osha.inspection;

-- Windows are dates: the last N years before the data date (calendar years would drop late 2016 from
-- a 10-year window that starts 2016-09-23). Same definitions as mart.establishment_year.
CREATE OR REPLACE TABLE est_window AS
SELECT i.establishment_key, w.window_years,
       count(*) FILTER (WHERE coalesce(i.insp_type, '') NOT IN ('F', 'D', 'E') AND NOT i.no_inspection) AS rated_n,
       count(*) FILTER (WHERE i.citation_n > 0) AS with_cit_n,
       sum(i.serious_plus_n) AS serious_plus_n, sum(i.citation_n) AS viol_n
FROM wh.osha.inspection i,
     (SELECT unnest([3, 5, 10]) AS window_years) w,
     as_of
WHERE i.open_date >= as_of.data_as_of - to_years(w.window_years)
GROUP BY 1, 2;

CREATE OR REPLACE TABLE wh.mart.trade_benchmark AS
WITH peers AS (
  SELECT ew.*, coalesce(e.primary_naics4, t.naics4) AS naics4
  FROM est_window ew
  JOIN wh.entity.establishment e USING (establishment_key)
  LEFT JOIN ref_trade t ON t.code_type = 'sic4' AND t.code = e.primary_sic4
  WHERE ew.rated_n >= {{MIN_RATED}} AND NOT e.is_placeholder
    AND e.construction_insp_n > 0  -- peers are construction-coded firms (not farms or hospitals in scope via history)
),
levels AS (
  SELECT 'naics4' AS level, naics4 AS trade_code, * FROM peers WHERE naics4 IS NOT NULL
  UNION ALL SELECT 'naics3', left(naics4, 3), * FROM peers WHERE naics4 IS NOT NULL
  UNION ALL SELECT 'all', '23', * FROM peers
)
SELECT level, trade_code, window_years, count(*) AS peer_n,
       quantile_cont(serious_plus_n / rated_n, 0.5)  AS serious_plus_rate_p50,
       quantile_cont(serious_plus_n / rated_n, 0.75) AS serious_plus_rate_p75,
       quantile_cont(serious_plus_n / rated_n, 0.9)  AS serious_plus_rate_p90,
       quantile_cont(viol_n / rated_n, 0.5)          AS citation_rate_p50,
       quantile_cont(viol_n / rated_n, 0.75)         AS citation_rate_p75,
       quantile_cont(with_cit_n / rated_n, 0.5)      AS pct_with_citations_p50
FROM levels
GROUP BY 1, 2, 3;
