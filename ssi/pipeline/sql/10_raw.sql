-- Raw OSHA tables exactly as delivered: every column as text, so nothing is lost or silently coerced.
-- Quote/escape are explicit because some state standard codes contain quoted commas.
CREATE OR REPLACE TABLE raw_inspection AS
SELECT * FROM read_csv('{{RAW}}/inspection/*.csv', all_varchar = true, header = true, quote = '"', escape = '"', union_by_name = true);
CREATE OR REPLACE TABLE raw_violation AS
SELECT * FROM read_csv('{{RAW}}/violation/*.csv', all_varchar = true, header = true, quote = '"', escape = '"', union_by_name = true);
CREATE OR REPLACE TABLE raw_accident AS
SELECT * FROM read_csv('{{RAW}}/accident/*.csv', all_varchar = true, header = true, quote = '"', escape = '"', union_by_name = true);
CREATE OR REPLACE TABLE raw_accident_injury AS
SELECT * FROM read_csv('{{RAW}}/accident_injury/*.csv', all_varchar = true, header = true, quote = '"', escape = '"', union_by_name = true);
CREATE OR REPLACE TABLE raw_accident_abstract AS
SELECT * FROM read_csv('{{RAW}}/accident_abstract/*.csv', all_varchar = true, header = true, quote = '"', escape = '"', union_by_name = true);
CREATE OR REPLACE TABLE raw_accident_lookup AS
SELECT * FROM read_csv('{{RAW}}/accident_lookup2/*.csv', all_varchar = true, header = true, quote = '"', escape = '"', union_by_name = true);
