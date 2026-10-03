"""Name/address cleaning rules (DuckDB macros). One implementation for build time and query time."""
from pathlib import Path

MACROS_SQL = (Path(__file__).parent / "macros.sql").read_text()

# The name rule's steps, in order, for per-rule merge counts in the build report.
NAME_STEPS = [
    "ssi_n1_upper", "ssi_n2_strip_id", "ssi_n3_dots", "ssi_n4_dba", "ssi_n5_state_note",
    "ssi_n6_separators", "ssi_n7_the", "ssi_n8_join_legal", "ssi_n9_legal", "ssi_n10_initials",
]


def install_macros(con, temp: bool = False) -> None:
    """Create the cleaning macros on a DuckDB connection (TEMP on read-only serving connections)."""
    sql = MACROS_SQL
    if temp:
        sql = sql.replace("CREATE OR REPLACE MACRO", "CREATE OR REPLACE TEMP MACRO")
    con.execute(sql)
