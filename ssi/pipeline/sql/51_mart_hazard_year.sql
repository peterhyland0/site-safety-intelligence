-- mart.establishment_hazard_year: citations by hazard category per establishment per year (additive).
CREATE OR REPLACE TABLE wh.mart.establishment_hazard_year AS
SELECT i.establishment_key, year(i.open_date) AS year, v.hazard_code,
       count(*) AS viol_n,
       count(*) FILTER (WHERE v.is_serious_plus) AS viol_serious_plus_n,
       count(DISTINCT v.activity_nr) AS insp_n
FROM wh.osha.violation v JOIN wh.osha.inspection i USING (activity_nr)
WHERE NOT v.is_deleted AND i.open_date IS NOT NULL
GROUP BY 1, 2, 3;
