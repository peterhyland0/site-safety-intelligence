-- osha.inspection (final): adds the shared-site count and the fatality status.
-- OSHA opens an inspection for EVERY employer on a fatality site and copies the injury rows to each,
-- so "this inspection is linked to a fatality" does not mean "this employer caused it". Status:
--   fatality_cited               fatal accident linked AND this employer got serious+ citations in it
--   fatality_inspected_not_cited fatal accident linked, no serious+ citations for this employer
--   fatality_pending             the case is still open and no serious+ citation has been issued yet:
--                                a fatal accident with no citations yet, or a fatality/catastrophe
--                                inspection (insp_type M) whose accident detail isn't published. Only while
--                                citations can still come: OSHA must cite within 6 months (OSH Act 9(c)), so
--                                after 7 months (a month for load lag) it is "not cited", however long the
--                                case stays open
--   fatcat_no_inspection         a fatal accident or fatality/catastrophe file where OSHA conducted no inspection
--                                of this employer (insp_scope D) and issued no serious+ citations
--   fatcat_cited                 fatality/catastrophe-type inspection (insp_type M) without published
--                                accident detail, with serious+ citations
--   fatcat_not_cited             the same, case closed, no serious+ citations for this employer
--   fatcat_site_cited            another employer's inspection on the same site and day as an undetailed
--                                fatality/catastrophe inspection, with serious+ citations for this employer
--                                (before accident detail lagged, the accident link carried this)
--   catastrophe_cited            fatality/catastrophe inspection whose published detail shows no death
--                                (serious injuries), with serious+ citations for this employer
--   accident_outcome_unknown     accident-type inspection (A) without published accident detail
--   none
-- OSHA's accident detail lags (it ends 2025-03-28 in the 2026-10 load), so recent investigations land
-- in fatality_pending / fatcat_* rather than going unflagged.
-- A death reported only in the narrative (the employee died later in hospital) counts as a fatal accident.
CREATE OR REPLACE TABLE insp_accident AS
SELECT l.activity_nr,
       count(*) AS accident_n,
       bool_or(a.fatality_flag OR a.fatal_n > 0 OR a.death_in_narrative) AS has_fatal_accident,
       max(a.employers_on_site) AS employers_on_site
FROM accident_link l JOIN stg_accident a USING (summary_nr)
GROUP BY 1;

CREATE OR REPLACE TABLE insp_citations AS
SELECT activity_nr,
       count(*) FILTER (WHERE NOT is_deleted) AS citation_n,
       count(*) FILTER (WHERE NOT is_deleted AND is_serious_plus) AS serious_plus_n,
       count(*) FILTER (WHERE NOT is_deleted AND NOT is_final) AS not_final_n,
       sum(penalty_initial) FILTER (WHERE NOT is_deleted) AS penalty_initial,
       sum(penalty_current) FILTER (WHERE NOT is_deleted) AS penalty_current
FROM wh.osha.violation GROUP BY 1;

-- citations can still be issued for inspections opened within the last 7 months (6-month limit + load lag)
CREATE OR REPLACE TABLE citation_deadline AS
SELECT (max(open_date) - INTERVAL 7 MONTH)::DATE AS can_still_cite_since FROM stg_inspection;

-- sites (same address and day) with a fatality/catastrophe inspection whose accident detail isn't published
CREATE OR REPLACE TABLE site_fatcat AS
SELECT DISTINCT i.site_group_id
FROM stg_inspection i LEFT JOIN insp_accident a USING (activity_nr)
WHERE i.insp_type = 'M' AND a.activity_nr IS NULL AND i.site_group_id IS NOT NULL;

-- is_provisional: OSHA's case is open AND something can still change: a citation without a final order
-- (contested, or inside the contest period), or no citations yet while they can still be issued. An open case
-- whose citations are all final orders is only waiting on penalties (26,266 of 29,936 open serious cases).
-- visit_id: one visit to one site on one day. OSHA often opens a safety and a health inspection for the same
-- visit, so "separate inspections" are counted as visits.
CREATE OR REPLACE TABLE wh.osha.inspection AS
SELECT i.*,
       coalesce(g.site_group_n, 1) AS site_group_n,
       coalesce(i.site_group_id, i.activity_nr::VARCHAR) AS visit_id,
       coalesce(c.citation_n, 0) AS citation_n,
       coalesce(c.serious_plus_n, 0) AS serious_plus_n,
       c.penalty_initial, c.penalty_current,
       i.is_open AND (coalesce(c.not_final_n, 0) > 0
                      OR (coalesce(c.citation_n, 0) = 0 AND i.open_date >= d.can_still_cite_since)) AS is_provisional,
       coalesce(a.accident_n, 0) AS accident_n,
       CASE
         WHEN coalesce(a.has_fatal_accident, false) AND coalesce(c.serious_plus_n, 0) > 0 THEN 'fatality_cited'
         WHEN (coalesce(a.has_fatal_accident, false) OR i.insp_type = 'M') AND i.no_inspection
              AND coalesce(c.serious_plus_n, 0) = 0 THEN 'fatcat_no_inspection'
         WHEN coalesce(a.has_fatal_accident, false) AND i.is_open AND coalesce(c.citation_n, 0) = 0
              AND i.open_date >= d.can_still_cite_since THEN 'fatality_pending'
         WHEN coalesce(a.has_fatal_accident, false) THEN 'fatality_inspected_not_cited'
         WHEN i.insp_type = 'M' AND a.activity_nr IS NULL AND coalesce(c.serious_plus_n, 0) > 0 THEN 'fatcat_cited'
         WHEN i.insp_type = 'M' AND a.activity_nr IS NOT NULL AND coalesce(c.serious_plus_n, 0) > 0 THEN 'catastrophe_cited'
         WHEN i.insp_type = 'M' AND a.activity_nr IS NULL AND i.is_open
              AND i.open_date >= d.can_still_cite_since THEN 'fatality_pending'
         WHEN i.insp_type = 'M' AND a.activity_nr IS NULL THEN 'fatcat_not_cited'
         WHEN coalesce(i.insp_type, '') <> 'M' AND a.activity_nr IS NULL AND coalesce(c.serious_plus_n, 0) > 0
              AND i.site_group_id IN (SELECT site_group_id FROM site_fatcat) THEN 'fatcat_site_cited'
         WHEN i.insp_type = 'A' AND a.activity_nr IS NULL THEN 'accident_outcome_unknown'
         ELSE 'none'
       END AS fatality_status
FROM stg_inspection i
CROSS JOIN citation_deadline d
LEFT JOIN site_groups g USING (site_group_id)
LEFT JOIN insp_citations c USING (activity_nr)
LEFT JOIN insp_accident a USING (activity_nr);
