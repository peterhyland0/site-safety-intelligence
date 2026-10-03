-- Build settings. Intermediate tables live in the scratch database (the connection's main catalog);
-- final, served tables are written to the attached warehouse `wh`.
SET preserve_insertion_order = false;
CREATE SCHEMA IF NOT EXISTS wh.ref;
CREATE SCHEMA IF NOT EXISTS wh.osha;
CREATE SCHEMA IF NOT EXISTS wh.entity;
CREATE SCHEMA IF NOT EXISTS wh.ref_ext;
CREATE SCHEMA IF NOT EXISTS wh.mart;
