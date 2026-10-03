-- mart.red_flag: every catastrophic or repeated-offence event, all years, one row per event,
-- with lineage back to the inspection (and citation) that produced it. case_open is OSHA's case status;
-- case_provisional says whether anything about it can still change (33_inspection_final).
CREATE OR REPLACE TABLE wh.mart.red_flag AS
SELECT md5(kind || '|' || activity_nr || '|' || coalesce(citation_id, '')) AS flag_id, *
FROM (
  SELECT i.establishment_key, i.activity_nr, NULL::VARCHAR AS citation_id, i.fatality_status AS kind,
         i.open_date AS event_date, NULL::VARCHAR AS hazard_code, NULL::VARCHAR AS standard_cite,
         i.penalty_initial, i.penalty_current, i.is_open AS case_open, i.is_provisional AS case_provisional,
         i.site_group_n AS shared_site_n, i.visit_id, i.dq_flags
  FROM wh.osha.inspection i
  WHERE i.fatality_status IN ('fatality_cited', 'fatality_inspected_not_cited', 'fatality_pending',
                             'fatcat_cited', 'fatcat_not_cited', 'fatcat_site_cited', 'catastrophe_cited',
                             'fatcat_no_inspection')
  UNION ALL
  SELECT i.establishment_key, v.activity_nr, v.citation_id,
         CASE v.viol_type WHEN 'W' THEN 'willful' ELSE 'repeat' END,
         coalesce(v.issued_on, i.open_date), v.hazard_code, v.standard_cite,
         v.penalty_initial, v.penalty_current, i.is_open, i.is_provisional, i.site_group_n, i.visit_id, v.dq_flags
  FROM wh.osha.violation v JOIN wh.osha.inspection i USING (activity_nr)
  WHERE NOT v.is_deleted AND v.viol_type IN ('W', 'R')
  UNION ALL
  SELECT i.establishment_key, v.activity_nr, v.citation_id, 'fta',
         coalesce(v.issued_on, i.open_date), v.hazard_code, v.standard_cite,
         v.penalty_initial, v.penalty_current, i.is_open, i.is_provisional, i.site_group_n, i.visit_id, v.dq_flags
  FROM wh.osha.violation v JOIN wh.osha.inspection i USING (activity_nr)
  WHERE NOT v.is_deleted AND v.is_fta
);
