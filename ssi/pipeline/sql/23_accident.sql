-- Accidents, injuries and the many-to-many link to inspections.
-- * Injury rows are copied once per employer inspected at the site; a person is (summary_nr, line_nr, person_n).
-- * Some rows put the construction-operation code in const_op_cause instead of const_op (the whole 2026
--   load batch: 394 of 394 accidents present in both batches; and 142 rows loaded 2022-2025, recognised by
--   the same pattern: const_op empty, nature and body empty); it is moved back here.
-- * Codes are stored as floats ('12.0'); ages 0, 1 and 99 mean unknown (36 rows say 1, 23 say 99).
CREATE OR REPLACE TABLE stg_injury_rows AS
SELECT
  try_cast(summary_nr AS BIGINT)                             AS summary_nr,
  try_cast(rel_insp_nr AS BIGINT)                            AS rel_insp_nr,
  try_cast(injury_line_nr AS INTEGER)                        AS line_nr,
  left(load_dt, 4) >= '2026'                                 AS shifted_batch,
  CASE WHEN try_cast(try_cast(age AS DOUBLE) AS INTEGER) NOT IN (0, 1, 99)
       THEN try_cast(try_cast(age AS DOUBLE) AS INTEGER) END AS age,
  nullif(trim(sex), '')                                      AS sex,
  try_cast(try_cast(nature_of_inj AS DOUBLE) AS INTEGER)     AS nature_code,
  try_cast(try_cast(part_of_body AS DOUBLE) AS INTEGER)      AS body_code,
  try_cast(try_cast(degree_of_inj AS DOUBLE) AS INTEGER)     AS degree_code,
  try_cast(try_cast(fat_cause AS DOUBLE) AS INTEGER)         AS fat_cause_code,
  CASE WHEN const_op IS NULL AND (left(load_dt, 4) >= '2026' OR (nature_of_inj IS NULL AND part_of_body IS NULL))
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

-- Which person is each row? OSHA copies each injury row once per employer inspected at the site, so
-- (summary_nr, line_nr) is normally one person. But the 2026 load restarts line numbers for each
-- employer, so the same (summary_nr, line_nr) can be two people (accident 221610942: a 43-year-old woman
-- and a 47-year-old man, both killed). A new person starts when sex differs or age jumps by more than
-- 2 years (1-2 years is a typo in one copy); rows without age/sex join the first person.
CREATE OR REPLACE TABLE injury_person AS
WITH fp AS (
  SELECT DISTINCT summary_nr, line_nr, age, sex FROM stg_injury_rows WHERE age IS NOT NULL AND sex IS NOT NULL
), steps AS (
  SELECT *, CASE WHEN lag(sex) OVER w IS NULL OR lag(sex) OVER w <> sex OR age - lag(age) OVER w > 2
                 THEN 1 ELSE 0 END AS new_person
  FROM fp WINDOW w AS (PARTITION BY summary_nr, line_nr ORDER BY sex, age)
)
SELECT summary_nr, line_nr, age, sex,
       sum(new_person) OVER (PARTITION BY summary_nr, line_nr ORDER BY sex, age ROWS UNBOUNDED PRECEDING) AS person_n
FROM steps;

-- one row per injured person (merge the per-employer copies; fatal wins on degree; ties pick the lowest code)
CREATE OR REPLACE TABLE stg_injury AS
SELECT r.summary_nr, r.line_nr, coalesce(p.person_n, 1) AS person_n,
       max(r.age) AS age, min(r.sex) AS sex,
       min(nullif(r.degree_code, 0)) AS degree_code,
       min(r.nature_code) FILTER (WHERE r.nature_code > 0) AS nature_code,
       min(r.body_code) FILTER (WHERE r.body_code > 0) AS body_code,
       min(r.fat_cause_code) FILTER (WHERE r.fat_cause_code > 0) AS fat_cause_code,
       min(r.const_op_code) FILTER (WHERE r.const_op_code > 0) AS const_op_code,
       min(r.task_code) FILTER (WHERE r.task_code > 0) AS task_code,
       max(r.fall_distance_ft) AS fall_distance_ft,
       count(DISTINCT r.sex) > 1 OR max(r.age) - min(r.age) > 2 AS person_conflict  -- build check: never true
FROM stg_injury_rows r
LEFT JOIN injury_person p ON p.summary_nr = r.summary_nr AND p.line_nr = r.line_nr AND p.age = r.age AND p.sex = r.sex
GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE accident_link AS
SELECT DISTINCT r.summary_nr, r.rel_insp_nr AS activity_nr
FROM stg_injury_rows r
WHERE r.rel_insp_nr IN (SELECT activity_nr FROM stg_inspection);

CREATE OR REPLACE TABLE accident_employers AS
SELECT summary_nr, count(DISTINCT rel_insp_nr) AS employers_on_site FROM stg_injury_rows GROUP BY 1;

-- Narratives come in numbered lines. Before mid-2015 they were hard-wrapped at 80 characters, often
-- mid-word ("unlo" / "ading"): a full 80-character line that doesn't end in a space joins the next
-- line directly; every other line break is a space.
CREATE OR REPLACE TABLE accident_narrative AS
WITH lines AS (
  SELECT try_cast(summary_nr AS BIGINT) AS summary_nr, try_cast(line_nr AS INTEGER) AS line_nr, abstract_text AS txt,
         lag(abstract_text) OVER (PARTITION BY summary_nr ORDER BY try_cast(line_nr AS INTEGER), abstract_text) AS prev
  FROM raw_accident_abstract
)
SELECT summary_nr,
       trim(regexp_replace(string_agg(
         CASE WHEN prev IS NULL THEN trim(txt)
              WHEN length(prev) >= 80 AND right(prev, 1) <> ' ' AND left(txt, 1) <> ' ' THEN rtrim(txt)
              ELSE ' ' || trim(txt) END, '' ORDER BY line_nr, txt), '\s+', ' ', 'g')) AS narrative
FROM lines GROUP BY 1;

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
       -- the employee died later (in hospital): the narrative says so, the injury degree doesn't (03_narrative_macros)
       narrative_reports_death(n.narrative) AS death_in_narrative,
       n.narrative,
       coalesce(inj.injured_n, 0) AS injured_n,
       coalesce(inj.fatal_n, 0) AS fatal_n,
       coalesce(e.employers_on_site, 1) AS employers_on_site,
       (a.summary_nr IS NULL) AS record_missing,
       list_filter([CASE WHEN a.summary_nr IS NULL THEN 'accident_record_missing' END,
                    CASE WHEN n.narrative IS NULL THEN 'no_narrative' END,
                    CASE WHEN narrative_reports_death(n.narrative) AND NOT coalesce(a.fatality = 'X', false)
                              AND coalesce(inj.fatal_n, 0) = 0 THEN 'death_only_in_narrative' END],
                   lambda f: f IS NOT NULL) AS dq_flags
FROM linked l
LEFT JOIN raw_accident a ON try_cast(a.summary_nr AS BIGINT) = l.summary_nr
LEFT JOIN accident_narrative n ON n.summary_nr = l.summary_nr
LEFT JOIN inj ON inj.summary_nr = l.summary_nr
LEFT JOIN accident_employers e ON e.summary_nr = l.summary_nr
LEFT JOIN lookup pt ON pt.code_family = 'PTYP' AND pt.code_letter = a.project_type
LEFT JOIN lookup eu ON eu.code_family = 'ENDU' AND eu.code_letter = a.const_end_use;

-- in-scope accidents whose accident record is missing keep a stub row (record_missing) and are listed here
INSERT INTO quarantine
SELECT 'accident_injury', summary_nr || '/' || line_nr || '/' || person_n,
       'injury references an accident record that does not exist (kept with a stub accident row)'
FROM stg_injury
WHERE summary_nr NOT IN (SELECT try_cast(summary_nr AS BIGINT) FROM raw_accident)
  AND summary_nr IN (SELECT summary_nr FROM accident_link);
-- injury rows that point at an inspection that doesn't exist in OSHA's data at all
INSERT INTO quarantine
SELECT 'accident_injury', summary_nr || '/' || line_nr || '/' || rel_insp_nr,
       'injury references an inspection that does not exist'
FROM stg_injury_rows
WHERE rel_insp_nr IS NOT NULL AND rel_insp_nr NOT IN (SELECT try_cast(activity_nr AS BIGINT) FROM raw_inspection);

CREATE OR REPLACE TABLE wh.osha.accident AS SELECT * FROM stg_accident;
CREATE OR REPLACE TABLE wh.osha.accident_inspection AS SELECT * FROM accident_link;
CREATE OR REPLACE TABLE wh.osha.injury AS
SELECT j.summary_nr, j.line_nr, j.person_n, j.age, j.sex,
       CASE j.degree_code WHEN 1 THEN 'fatality' WHEN 2 THEN 'hospitalized' WHEN 3 THEN 'not hospitalized' END AS degree,
       nat.label AS nature, bd.label AS body_part, fc.label AS fatality_cause, op.label AS construction_operation,
       j.fall_distance_ft
FROM stg_injury j
LEFT JOIN lookup nat ON nat.code_family = 'IN' AND nat.code_number = j.nature_code
LEFT JOIN lookup bd ON bd.code_family = 'BD' AND bd.code_number = j.body_code
LEFT JOIN lookup fc ON fc.code_family = 'CAUS' AND fc.code_number = j.fat_cause_code
LEFT JOIN lookup op ON op.code_family = 'OPER' AND op.code_number = j.const_op_code
WHERE j.summary_nr IN (SELECT summary_nr FROM stg_accident);
