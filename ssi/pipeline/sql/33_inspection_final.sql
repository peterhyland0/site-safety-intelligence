-- osha.inspection (final): adds the shared-site count and the fatality status.
-- OSHA opens an inspection for EVERY employer on a fatality site and copies the injury rows to each,
-- so "this inspection is linked to a fatality" does not mean "this employer caused it". Status:
--   fatality_cited               fatal accident linked AND this employer got serious+ citations in it
--   fatality_inspected_not_cited fatal accident linked, no serious+ citations for this employer
--   fatcat_cited                 fatality/catastrophe-type inspection (insp_type M) without published
--                                accident detail, with serious+ citations
--   accident_outcome_unknown     accident-type inspection (A/M) without published accident detail
--   none
CREATE OR REPLACE TABLE insp_accident AS
SELECT l.activity_nr,
       count(*) AS accident_n,
       bool_or(a.fatality_flag OR a.fatal_n > 0) AS has_fatal_accident,
       max(a.employers_on_site) AS employers_on_site
FROM accident_link l JOIN stg_accident a USING (summary_nr)
GROUP BY 1;

CREATE OR REPLACE TABLE insp_citations AS
SELECT activity_nr,
       count(*) FILTER (WHERE NOT is_deleted) AS citation_n,
       count(*) FILTER (WHERE NOT is_deleted AND is_serious_plus) AS serious_plus_n,
       sum(penalty_initial) FILTER (WHERE NOT is_deleted) AS penalty_initial,
       sum(penalty_current) FILTER (WHERE NOT is_deleted) AS penalty_current
FROM wh.osha.violation GROUP BY 1;

CREATE OR REPLACE TABLE wh.osha.inspection AS
SELECT i.*,
       coalesce(g.site_group_n, 1) AS site_group_n,
       coalesce(c.citation_n, 0) AS citation_n,
       coalesce(c.serious_plus_n, 0) AS serious_plus_n,
       c.penalty_initial, c.penalty_current,
       coalesce(a.accident_n, 0) AS accident_n,
       CASE
         WHEN coalesce(a.has_fatal_accident, false) AND coalesce(c.serious_plus_n, 0) > 0 THEN 'fatality_cited'
         WHEN coalesce(a.has_fatal_accident, false) THEN 'fatality_inspected_not_cited'
         WHEN i.insp_type = 'M' AND a.activity_nr IS NULL AND coalesce(c.serious_plus_n, 0) > 0 THEN 'fatcat_cited'
         WHEN i.insp_type IN ('A', 'M') AND a.activity_nr IS NULL THEN 'accident_outcome_unknown'
         ELSE 'none'
       END AS fatality_status
FROM stg_inspection i
LEFT JOIN site_groups g USING (site_group_id)
LEFT JOIN insp_citations c USING (activity_nr)
LEFT JOIN insp_accident a USING (activity_nr);
