-- mart.establishment_year: additive counts per establishment per year (inspection open year).
-- A "company" only exists at query time (the establishments matched to a GC's sub), so marts must be
-- additive: a sub's figures for any window are sums over its matched keys and years.
-- Rated inspections exclude follow-ups (F), monitoring (D) and variance (E) visits, which inflate counts.
CREATE OR REPLACE TABLE wh.mart.establishment_year AS
WITH insp AS (
  SELECT establishment_key, year(open_date) AS year,
         count(*) AS insp_n,
         count(*) FILTER (WHERE coalesce(insp_type, '') NOT IN ('F', 'D', 'E')) AS insp_rated_n,
         count(*) FILTER (WHERE citation_n > 0) AS insp_with_cit_n,
         count(*) FILTER (WHERE insp_type IN ('H', 'I', 'K')) AS insp_programmed_n,
         count(*) FILTER (WHERE insp_type = 'B') AS insp_complaint_n,
         count(*) FILTER (WHERE insp_type = 'C') AS insp_referral_n,
         count(*) FILTER (WHERE insp_type IN ('A', 'M')) AS insp_accident_n,
         count(*) FILTER (WHERE insp_type = 'F') AS insp_followup_n,
         count(*) FILTER (WHERE is_open) AS open_insp_n,
         count(*) FILTER (WHERE jurisdiction = 'state_plan') AS state_plan_insp_n,
         count(*) FILTER (WHERE fatality_status = 'fatality_cited') AS fatality_cited_n
  FROM wh.osha.inspection
  WHERE open_date IS NOT NULL
  GROUP BY 1, 2
),
viol AS (
  SELECT i.establishment_key, year(i.open_date) AS year,
         count(*) AS viol_n,
         count(*) FILTER (WHERE v.viol_type = 'S') AS viol_s_n,
         count(*) FILTER (WHERE v.viol_type = 'W') AS viol_w_n,
         count(*) FILTER (WHERE v.viol_type = 'R') AS viol_r_n,
         count(*) FILTER (WHERE v.viol_type = 'O') AS viol_o_n,
         count(*) FILTER (WHERE v.viol_type = 'U') AS viol_u_n,
         count(*) FILTER (WHERE v.is_serious_plus) AS viol_serious_plus_n,
         count(*) FILTER (WHERE v.is_fta) AS viol_fta_n,
         count(*) FILTER (WHERE i.is_open) AS viol_open_n,
         sum(v.penalty_initial) AS penalty_initial_sum,
         sum(v.penalty_current) AS penalty_current_sum,
         count(v.penalty_current) AS penalty_known_n
  FROM wh.osha.violation v JOIN wh.osha.inspection i USING (activity_nr)
  WHERE NOT v.is_deleted AND i.open_date IS NOT NULL
  GROUP BY 1, 2
)
SELECT insp.*,
       coalesce(viol.viol_n, 0) AS viol_n, coalesce(viol.viol_s_n, 0) AS viol_s_n,
       coalesce(viol.viol_w_n, 0) AS viol_w_n, coalesce(viol.viol_r_n, 0) AS viol_r_n,
       coalesce(viol.viol_o_n, 0) AS viol_o_n, coalesce(viol.viol_u_n, 0) AS viol_u_n,
       coalesce(viol.viol_serious_plus_n, 0) AS viol_serious_plus_n, coalesce(viol.viol_fta_n, 0) AS viol_fta_n,
       coalesce(viol.viol_open_n, 0) AS viol_open_n,
       viol.penalty_initial_sum, viol.penalty_current_sum, coalesce(viol.penalty_known_n, 0) AS penalty_known_n
FROM insp LEFT JOIN viol USING (establishment_key, year);
