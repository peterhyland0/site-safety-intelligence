-- osha.inspection: one row per in-scope inspection, typed, decoded and flagged (never deleted).
CREATE OR REPLACE TABLE stg_inspection AS
SELECT
  try_cast(i.activity_nr AS BIGINT)                         AS activity_nr,
  s.establishment_key,
  s.scope_reason,
  i.estab_name                                              AS estab_name_raw,
  k.clean_name,
  i.site_address, i.site_city,
  nullif(upper(trim(i.site_state)), '')                     AS site_state,
  zip5(i.site_zip)                                          AS site_zip,
  i.mail_street, i.mail_city,
  k.mail_state, k.zip5 AS mail_zip, k.addr_key, k.addr_clean,
  i.reporting_id,
  -- 3rd digit of the reporting office ID is '5' for state-plan offices (evidence-based; see docs)
  CASE WHEN substr(i.reporting_id, 3, 1) = '5' THEN 'state_plan' ELSE 'federal' END AS jurisdiction,
  i.owner_type, i.insp_type, i.insp_scope,
  i.why_no_insp,  -- kept raw: populated on ~100% of recent rows, so it can't be used as a filter
  i.union_status, i.safety_hlth,
  nullif(nullif(i.naics_code, '000000'), '0')               AS naics_code,
  nullif(nullif(i.sic_code, '0000'), '0')                   AS sic_code,
  try_cast(i.nr_in_estab AS INTEGER)                        AS nr_in_estab,  -- never used to normalise
  try_cast(left(i.open_date, 10) AS DATE)                   AS open_date,
  try_cast(left(i.close_case_date, 10) AS DATE)             AS close_date,
  try_cast(left(i.close_conf_date, 10) AS DATE)             AS close_conf_date,
  try_cast(left(i.case_mod_date, 10) AS DATE)               AS case_mod_date,
  (i.close_case_date IS NULL OR i.close_case_date = '')     AS is_open,
  CASE WHEN addr_key(i.site_address) IS NOT NULL AND zip5(i.site_zip) IS NOT NULL
       THEN md5(addr_key(i.site_address) || '|' || zip5(i.site_zip) || '|' || left(i.open_date, 10)) END AS site_group_id,
  list_filter([
    CASE WHEN try_cast(left(i.close_case_date, 10) AS DATE) < try_cast(left(i.open_date, 10) AS DATE) THEN 'closed_before_opened' END,
    CASE WHEN try_cast(i.nr_in_estab AS INTEGER) >= 10000 THEN 'employees_implausible' END,
    CASE WHEN regexp_matches(upper(i.estab_name), '^[A-Z]{0,3}[0-9]{3,}\s*-\s*') THEN 'id_prefix_stripped' END,
    CASE WHEN strpos(i.estab_name, '�') > 0 THEN 'name_encoding_damage' END,
    CASE WHEN k.is_placeholder THEN 'placeholder_name' END,
    CASE WHEN try_cast(left(i.open_date, 10) AS DATE) < DATE '1971-04-28' THEN 'opened_before_osha_existed' END
  ], lambda f: f IS NOT NULL)                               AS dq_flags
FROM scope s
JOIN raw_inspection_window i ON i.activity_nr = s.activity_nr
JOIN insp_key k ON k.activity_nr = s.activity_nr;

-- employers inspected at the same site on the same day (GC + subs inspected together)
CREATE OR REPLACE TABLE site_groups AS
SELECT site_group_id, count(DISTINCT establishment_key) AS site_group_n
FROM stg_inspection WHERE site_group_id IS NOT NULL GROUP BY 1;
