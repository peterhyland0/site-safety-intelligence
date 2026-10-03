-- osha.violation: citations with parsed standard and hazard category (never NULL: unmapped -> 'other',
-- so per-hazard totals always reconcile with the citation total).
CREATE OR REPLACE TABLE wh.osha.violation AS
SELECT v.activity_nr, v.citation_id, v.is_deleted, v.viol_type,
       v.standard_raw, h.std_family, h.standard_cite, h.section_key,
       coalesce(h.hazard_code, 'other') AS hazard_code,
       v.issued_on, v.abate_on, v.contest_on, v.final_order_on,
       v.contest_on IS NOT NULL AS contested,
       v.penalty_initial, v.penalty_current, v.is_fta,
       v.viol_type IN ('S', 'W', 'R', 'U') AS is_serious_plus,
       v.nr_instances, v.nr_exposed, v.gravity, v.dq_flags
FROM stg_violation v
LEFT JOIN violation_hazard h ON h.activity_nr = v.activity_nr AND h.citation_id = v.citation_id;
