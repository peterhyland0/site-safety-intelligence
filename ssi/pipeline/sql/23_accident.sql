-- Accidents, injuries and the many-to-many link to inspections.
-- * Injury rows are copied once per employer inspected at the site; the true injury is (summary_nr, line_nr).
-- * The 2026 load batch puts the construction-operation code in const_op_cause instead of const_op
--   (matched in 394 of 394 accidents present in both batches); it is moved back here.
-- * Codes are stored as floats ('12.0'); age 0 means unknown.
CREATE OR REPLACE TABLE stg_injury_rows AS
SELECT
  try_cast(summary_nr AS BIGINT)                             AS summary_nr,
  try_cast(rel_insp_nr AS BIGINT)                            AS rel_insp_nr,
  try_cast(injury_line_nr AS INTEGER)                        AS line_nr,
  left(load_dt, 4) >= '2026'                                 AS shifted_batch,
  nullif(try_cast(try_cast(age AS DOUBLE) AS INTEGER), 0)    AS age,
  nullif(trim(sex), '')                                      AS sex,
  try_cast(try_cast(nature_of_inj AS DOUBLE) AS INTEGER)     AS nature_code,
  try_cast(try_cast(part_of_body AS DOUBLE) AS INTEGER)      AS body_code,
  try_cast(try_cast(degree_of_inj AS DOUBLE) AS INTEGER)     AS degree_code,
  try_cast(try_cast(fat_cause AS DOUBLE) AS INTEGER)         AS fat_cause_code,
  CASE WHEN left(load_dt, 4) >= '2026' AND const_op IS NULL
       THEN try_cast(try_cast(const_op_cause AS DOUBLE) AS INTEGER)
       ELSE try_cast(try_cast(const_op AS DOUBLE) AS INTEGER) END AS const_op_code,
  try_cast(try_cast(task_assigned AS DOUBLE) AS INTEGER)     AS task_code,
  try_cast(fall_distance AS DOUBLE)                          AS fall_distance_ft,
  occ_code
FROM raw_accident_injury;

CREATE OR REPLACE TABLE lookup AS
SELECT accident_code AS code_family,
       try_cast(try_cast(accident_number AS DOUBLE) AS INTEGER) AS code_number,
       accident_letter AS code_letter, accident_value AS label
FROM raw_accident_lookup;

-- one row per injured person (merge the per-employer copies; fatal wins on degree)
CREATE OR REPLACE TABLE stg_injury AS
SELECT summary_nr, line_nr,
       max(age) AS age, any_value(sex) FILTER (WHERE sex IS NOT NULL) AS sex,
       min(nullif(degree_code, 0)) AS degree_code,
       any_value(nature_code) FILTER (WHERE nature_code > 0) AS nature_code,
       any_value(body_code) FILTER (WHERE body_code > 0) AS body_code,
       any_value(fat_cause_code) FILTER (WHERE fat_cause_code > 0) AS fat_cause_code,
       any_value(const_op_code) FILTER (WHERE const_op_code > 0) AS const_op_code,
       any_value(task_code) FILTER (WHERE task_code > 0) AS task_code,
       max(fall_distance_ft) AS fall_distance_ft
FROM stg_injury_rows
GROUP BY ALL;

CREATE OR REPLACE TABLE accident_link AS
SELECT DISTINCT r.summary_nr, r.rel_insp_nr AS activity_nr
FROM stg_injury_rows r
WHERE r.rel_insp_nr IN (SELECT activity_nr FROM stg_inspection);

CREATE OR REPLACE TABLE accident_employers AS
SELECT summary_nr, count(DISTINCT rel_insp_nr) AS employers_on_site FROM stg_injury_rows GROUP BY 1;

CREATE OR REPLACE TABLE accident_narrative AS
SELECT try_cast(summary_nr AS BIGINT) AS summary_nr,
       string_agg(trim(abstract_text), ' ' ORDER BY try_cast(line_nr AS INTEGER)) AS narrative
FROM raw_accident_abstract GROUP BY 1;

-- injuries whose accident record is missing (about 15%) keep a stub accident row, flagged, so the
-- link to the inspection (and any fatality) is not lost
CREATE OR REPLACE TABLE stg_accident AS
WITH linked AS (SELECT DISTINCT summary_nr FROM accident_link),
inj AS (SELECT summary_nr, count(*) AS injured_n, count(*) FILTER (WHERE degree_code = 1) AS fatal_n
        FROM stg_injury GROUP BY 1)
SELECT l.summary_nr,
       try_cast(left(a.event_date, 10) AS DATE) AS event_date,
       a.event_desc AS description,
       a.event_keyword AS keywords,
       pt.label AS project_type,
       eu.label AS end_use,
       try_cast(a.build_stories AS DOUBLE) AS building_stories,
       coalesce(a.fatality = 'X', false) AS fatality_flag,
       n.narrative,
       coalesce(inj.injured_n, 0) AS injured_n,
       coalesce(inj.fatal_n, 0) AS fatal_n,
       coalesce(e.employers_on_site, 1) AS employers_on_site,
       (a.summary_nr IS NULL) AS record_missing,
       list_filter([CASE WHEN a.summary_nr IS NULL THEN 'accident_record_missing' END,
                    CASE WHEN n.narrative IS NULL THEN 'no_narrative' END], lambda f: f IS NOT NULL) AS dq_flags
FROM linked l
LEFT JOIN raw_accident a ON try_cast(a.summary_nr AS BIGINT) = l.summary_nr
LEFT JOIN accident_narrative n ON n.summary_nr = l.summary_nr
LEFT JOIN inj ON inj.summary_nr = l.summary_nr
LEFT JOIN accident_employers e ON e.summary_nr = l.summary_nr
LEFT JOIN lookup pt ON pt.code_family = 'PTYP' AND pt.code_letter = a.project_type
LEFT JOIN lookup eu ON eu.code_family = 'ENDU' AND eu.code_letter = a.const_end_use;

INSERT INTO quarantine
SELECT 'accident_injury', summary_nr || '/' || line_nr, 'injury references an accident record that does not exist (kept with a stub accident row)'
FROM stg_injury WHERE summary_nr NOT IN (SELECT try_cast(summary_nr AS BIGINT) FROM raw_accident);

CREATE OR REPLACE TABLE wh.osha.accident AS SELECT * FROM stg_accident;
CREATE OR REPLACE TABLE wh.osha.accident_inspection AS SELECT * FROM accident_link;
CREATE OR REPLACE TABLE wh.osha.injury AS
SELECT j.summary_nr, j.line_nr, j.age, j.sex,
       CASE j.degree_code WHEN 1 THEN 'fatality' WHEN 2 THEN 'hospitalized' WHEN 3 THEN 'not hospitalized' END AS degree,
       nat.label AS nature, bd.label AS body_part, fc.label AS fatality_cause, op.label AS construction_operation,
       j.fall_distance_ft
FROM stg_injury j
LEFT JOIN lookup nat ON nat.code_family = 'IN' AND nat.code_number = j.nature_code
LEFT JOIN lookup bd ON bd.code_family = 'BD' AND bd.code_number = j.body_code
LEFT JOIN lookup fc ON fc.code_family = 'CAUS' AND fc.code_number = j.fat_cause_code
LEFT JOIN lookup op ON op.code_family = 'OPER' AND op.code_number = j.const_op_code
WHERE j.summary_nr IN (SELECT summary_nr FROM stg_accident);
