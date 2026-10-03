-- Data-quality checks. severity 'error' fails the build; 'warn' is reported.
CREATE OR REPLACE TABLE wh.mart.dq_check AS
SELECT * FROM (VALUES
  ('inspection_pk_unique', 'error', 0::DOUBLE,
     (SELECT count(*) - count(DISTINCT activity_nr) FROM wh.osha.inspection)::DOUBLE),
  ('violation_pk_unique', 'error', 0,
     (SELECT count(*) - count(DISTINCT (activity_nr, citation_id)) FROM wh.osha.violation)::DOUBLE),
  ('violation_has_inspection', 'error', 0,
     (SELECT count(*) FROM wh.osha.violation v WHERE NOT EXISTS (SELECT 1 FROM wh.osha.inspection i WHERE i.activity_nr = v.activity_nr))::DOUBLE),
  ('every_inspection_has_establishment', 'error', 0,
     (SELECT count(*) FROM wh.osha.inspection i WHERE NOT EXISTS (SELECT 1 FROM wh.entity.establishment e WHERE e.establishment_key = i.establishment_key))::DOUBLE),
  ('hazard_totals_reconcile', 'error', 0,
     ((SELECT sum(viol_n) FROM wh.mart.establishment_year) - (SELECT sum(viol_n) FROM wh.mart.establishment_hazard_year))::DOUBLE),
  ('red_flags_have_inspections', 'error', 0,
     (SELECT count(*) FROM wh.mart.red_flag r WHERE NOT EXISTS (SELECT 1 FROM wh.osha.inspection i WHERE i.activity_nr = r.activity_nr))::DOUBLE),
  ('construction_coded_inspections_all_in_scope', 'error', 0,
     ((SELECT count(*) FROM insp_key WHERE in_window AND (is_naics23 OR is_sic_construction))
      - (SELECT count(*) FROM wh.osha.inspection WHERE scope_reason IN ('naics23', 'sic15_17')))::DOUBLE),
  -- a 3-digit SIC code is a 4-digit code missing its leading zero (0175 orchards), never construction
  ('short_sic_codes_in_scope', 'error', 0,
     (SELECT count(*) FROM wh.osha.inspection WHERE scope_reason = 'sic15_17' AND length(sic_code) < 4)::DOUBLE),
  -- every fatality/catastrophe investigation without published accident detail carries a red flag
  ('undetailed_fatcat_without_flag', 'error', 0,
     (SELECT count(*) FROM wh.osha.inspection i WHERE i.insp_type = 'M' AND i.accident_n = 0
        AND NOT EXISTS (SELECT 1 FROM wh.mart.red_flag r WHERE r.activity_nr = i.activity_nr))::DOUBLE),
  -- a person's name must never count as a distinctive company name
  ('person_names_rated_distinctive', 'error', 0,
     (SELECT count(*) FROM wh.entity.core_stats WHERE is_person AND tier = 'distinctive')::DOUBLE),
  -- no merged injury row may mix two people (different sex, or ages more than 2 years apart)
  ('injury_rows_mixing_two_people', 'error', 0,
     (SELECT count(*) FROM stg_injury WHERE person_conflict)::DOUBLE),
  -- scope recounted directly from the keys: every in-window inspection that is construction-coded or belongs
  -- to an establishment ever coded as construction (any year) is in osha.inspection, and nothing else is
  ('scope_recount_matches', 'error', 0,
     ((SELECT count(*) FROM insp_key k WHERE k.in_window AND (k.is_naics23 OR k.is_sic_construction
          OR k.establishment_key IN (SELECT establishment_key FROM insp_key
                                     WHERE (is_naics23 OR is_sic_construction) AND NOT is_placeholder)))
      - (SELECT count(*) FROM wh.osha.inspection))::DOUBLE),
  -- citations recounted from the raw file: every raw citation of an in-scope inspection is in osha.violation
  ('citations_recount_from_raw', 'error', 0,
     ((SELECT count(DISTINCT (try_cast(v.activity_nr AS BIGINT), v.citation_id)) FROM raw_violation v
         WHERE try_cast(v.activity_nr AS BIGINT) IN (SELECT activity_nr FROM wh.osha.inspection))
      - (SELECT count(*) FROM wh.osha.violation))::DOUBLE),
  -- red flags recounted from live citations: one per willful, repeat and failure-to-abate citation
  ('red_flags_recount_from_citations', 'error', 0,
     ((SELECT count(*) FILTER (WHERE viol_type IN ('W', 'R')) + count(*) FILTER (WHERE is_fta)
         FROM wh.osha.violation WHERE NOT is_deleted)
      - (SELECT count(*) FROM wh.mart.red_flag WHERE kind IN ('willful', 'repeat', 'fta')))::DOUBLE),
  -- OSHA's accident detail lags; warn when it is more than 18 months behind the inspection data
  ('accident_detail_days_behind', 'warn', 548,
     (SELECT date_diff('day', (SELECT max(event_date) FROM wh.osha.accident), (SELECT max(open_date) FROM wh.osha.inspection)))::DOUBLE),
  ('hazard_other_share_pct', 'warn', 5,
     (SELECT 100.0 * count(*) FILTER (WHERE hazard_code = 'other') / count(*) FROM wh.osha.violation WHERE NOT is_deleted)::DOUBLE),
  ('orphan_violations_quarantined', 'warn', 374,
     (SELECT count(*) FROM quarantine WHERE source_table = 'violation')::DOUBLE)
) t(name, severity, expected, actual);

ALTER TABLE wh.mart.dq_check ADD COLUMN pass BOOLEAN;
UPDATE wh.mart.dq_check SET pass = CASE
  WHEN name IN ('hazard_other_share_pct', 'accident_detail_days_behind') THEN actual <= expected
  WHEN name = 'orphan_violations_quarantined' THEN abs(actual - expected) <= 50
  ELSE actual = expected END;

CREATE OR REPLACE TABLE wh.osha.quarantine AS SELECT * FROM quarantine;
