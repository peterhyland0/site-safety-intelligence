"""A tiny warehouse built from hand-written OSHA records by the pipeline's own SQL (40_establishment, 42_name_stats)
and cleaning macros, so the matcher (ssi.matching.run.match) runs end to end on names whose answers are known:
candidate search, spelling correction, people's names, address expansion and the rules, without the real data."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from ssi import config
from ssi.cleaning import install_macros
from ssi.pipeline.build import render


@dataclass
class Rec:
    """One OSHA inspection: the employer as typed, and its mailing address."""
    name: str
    street: str
    city: str
    state: str
    zip: str
    n: int = 1  # inspections
    naics: str = "238160"
    red_flag: bool = False
    scope: str = "naics23"


def build(path: Path, recs: list[Rec]) -> None:
    con = duckdb.connect()
    install_macros(con)
    con.execute(f"ATTACH '{path}' AS wh")
    for schema in ("osha", "entity", "mart", "ref_ext", "ref"):
        con.execute(f"CREATE SCHEMA wh.{schema}")
    for ref in ("given_name", "surname"):
        con.execute(f"CREATE TABLE ref_{ref} AS SELECT * FROM read_csv('{config.REF_DIR / (ref + '.csv')}', "
                    "header = true, all_varchar = true)")
    con.execute("""CREATE TABLE raw (activity_nr BIGINT, estab_name VARCHAR, street VARCHAR, city VARCHAR, state VARCHAR,
                                     zip VARCHAR, naics VARCHAR, red_flag BOOLEAN, scope VARCHAR)""")
    rows, nr = [], 100000
    for r in recs:
        for _ in range(r.n):
            nr += 1
            rows.append((nr, r.name, r.street, r.city, r.state, r.zip, r.naics, r.red_flag, r.scope))
    con.executemany("INSERT INTO raw VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    # keyed the way 21_inspection.sql keys OSHA's records
    con.execute("""
      CREATE TABLE wh.osha.inspection AS
      SELECT activity_nr, estab_name AS estab_name_raw, clean_name(estab_name) AS clean_name,
             upper(city) AS mail_city, upper(state) AS mail_state, zip5(zip) AS mail_zip,
             addr_key(street) AS addr_key, clean_addr(street) AS addr_clean, naics AS naics_code,
             NULL::VARCHAR AS sic_code, DATE '2024-01-01' + (activity_nr % 300)::INTEGER AS open_date,
             false AS no_inspection, scope AS scope_reason, upper(state) AS site_state,
             establishment_key(clean_name(estab_name), addr_key(street), zip5(zip), upper(state)) AS establishment_key
      FROM raw""")
    for step in ("40_establishment.sql", "42_name_stats.sql"):
        con.execute(render((config.SQL_DIR / step).read_text(), Path(".")))
    con.execute("""CREATE TABLE wh.mart.red_flag AS
                   SELECT i.establishment_key, 'fatality_cited' AS kind FROM raw r JOIN wh.osha.inspection i USING (activity_nr)
                   WHERE r.red_flag""")
    con.execute("""CREATE TABLE wh.mart.build_info AS SELECT 'mini' AS build_id, DATE '2024-12-31' AS data_as_of,
                   DATE '2024-12-31' AS accident_detail_through, DATE '2015-01-01' AS history_since""")
    con.execute("CREATE TABLE wh.ref_ext.licence (source VARCHAR, number VARCHAR, entity_id VARCHAR, clean_name VARCHAR, "
                "dba_clean VARCHAR)")
    con.execute("CREATE TABLE wh.entity.ref_link (establishment_key VARCHAR, source VARCHAR, ref_id VARCHAR, method VARCHAR)")
    con.close()
    wh = duckdb.connect(str(path))
    install_macros(wh)  # persisted, as the real build does, so GC input is cleaned by the build's rules
    wh.close()
