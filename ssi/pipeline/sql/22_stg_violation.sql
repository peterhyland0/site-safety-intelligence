-- Citations of in-scope inspections, typed. Penalties: blank stays NULL ("not recorded"), '0.00' is $0.
-- Failure-to-abate comes from fta_insp_nr / fta_issuance_date: fta_penalty is '0.00' on millions of rows and can't be used.
CREATE OR REPLACE TABLE stg_violation AS
SELECT
  try_cast(v.activity_nr AS BIGINT)                              AS activity_nr,
  v.citation_id,
  coalesce(v.delete_flag, '') = 'X'                              AS is_deleted,
  v.standard                                                     AS standard_raw,
  i.site_state,
  nullif(trim(v.viol_type), '')                                  AS viol_type,
  try_cast(left(v.issuance_date, 10) AS DATE)                    AS issued_on,
  try_cast(left(v.abate_date, 10) AS DATE)                       AS abate_on,
  try_cast(left(v.contest_date, 10) AS DATE)                     AS contest_on,
  try_cast(left(v.final_order_date, 10) AS DATE)                 AS final_order_on,
  try_cast(v.initial_penalty AS DECIMAL(14, 2))                  AS penalty_initial,
  try_cast(v.current_penalty AS DECIMAL(14, 2))                  AS penalty_current,
  (coalesce(v.fta_insp_nr, '') <> '' OR coalesce(v.fta_issuance_date, '') <> '') AS is_fta,
  try_cast(try_cast(v.nr_instances AS DOUBLE) AS INTEGER)        AS nr_instances,
  try_cast(try_cast(v.nr_exposed AS DOUBLE) AS INTEGER)          AS nr_exposed,
  v.gravity,
  list_filter([
    CASE WHEN try_cast(left(v.issuance_date, 10) AS DATE) < i.open_date THEN 'issued_before_open' END,
    CASE WHEN try_cast(v.current_penalty AS DECIMAL(14, 2)) > try_cast(v.initial_penalty AS DECIMAL(14, 2)) THEN 'penalty_increased' END,
    CASE WHEN v.initial_penalty IS NULL OR v.initial_penalty = '' THEN 'penalty_not_recorded' END,
    CASE WHEN nullif(trim(v.viol_type), '') IS NULL OR v.viol_type = 'P' THEN 'viol_type_undocumented' END,
    CASE WHEN strpos(v.standard, '�') > 0 THEN 'standard_encoding_damage' END
  ], lambda f: f IS NOT NULL)                                    AS dq_flags
FROM raw_violation v
JOIN stg_inspection i ON i.activity_nr = try_cast(v.activity_nr AS BIGINT);

-- Integrity failures are quarantined with a reason, never silently dropped.
CREATE OR REPLACE TABLE quarantine AS
SELECT 'violation' AS source_table, v.activity_nr || '/' || v.citation_id AS source_key,
       'citation references an inspection that does not exist' AS reason
FROM raw_violation v
WHERE NOT EXISTS (SELECT 1 FROM raw_inspection i WHERE i.activity_nr = v.activity_nr);
