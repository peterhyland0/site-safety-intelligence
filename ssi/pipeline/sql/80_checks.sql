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
     ((SELECT count(*) FROM insp_key WHERE is_naics23 OR is_sic_construction)
      - (SELECT count(*) FROM wh.osha.inspection WHERE scope_reason IN ('naics23', 'sic15_17')))::DOUBLE),
  ('hazard_other_share_pct', 'warn', 5,
     (SELECT 100.0 * count(*) FILTER (WHERE hazard_code = 'other') / count(*) FROM wh.osha.violation WHERE NOT is_deleted)::DOUBLE),
  ('orphan_violations_quarantined', 'warn', 374,
     (SELECT count(*) FROM quarantine WHERE source_table = 'violation')::DOUBLE)
) t(name, severity, expected, actual);

ALTER TABLE wh.mart.dq_check ADD COLUMN pass BOOLEAN;
UPDATE wh.mart.dq_check SET pass = CASE
  WHEN name = 'hazard_other_share_pct' THEN actual <= expected
  WHEN name = 'orphan_violations_quarantined' THEN abs(actual - expected) <= 50
  ELSE actual = expected END;

CREATE OR REPLACE TABLE wh.osha.quarantine AS SELECT * FROM quarantine;
