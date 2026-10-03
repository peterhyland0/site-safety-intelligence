"""Deaths reported only in the accident narrative (03_narrative_macros.sql). Snippets are from OSHA's data."""
from pathlib import Path

import duckdb
import pytest

SQL = Path(__file__).resolve().parents[1] / "ssi" / "pipeline" / "sql" / "03_narrative_macros.sql"


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    c.execute(SQL.read_text())
    return c


def reports_death(con, txt):
    return con.execute("SELECT narrative_reports_death(?)", [txt]).fetchone()[0]


@pytest.mark.parametrize("txt", [
    "Employee #1 remained hospitalized until October 24, 2018, when he died.",
    "Employee #1 was transported to the hospital and admitted for treatment. He died as a result of his injuries.",
    "The employee was killed as the result of his head injuries.",
    "The employee died during hospitalization.",
    "The Coworker #1 was later transferred to another hospital, where he died on December 4, 2019.",
    "hot tar splashed on him resulting in severe burns to multiple parts of hisbody from which he died.",
    "from being struck by the metal roof structure. Theemployee later died.",
    "The employee was hospitalized in a coma, but later died of the injuries.",
])
def test_delayed_deaths(con, txt):
    assert reports_death(con, txt) is True


@pytest.mark.parametrize("txt", [
    "while a coworker operating the Diedrich D-50 Turbo Drilling Rig closed the breakout",
    "He was hospitalized and later died of a non-work related medical condition.",
    "an acute sudden intracerebral hemorrhage unrelated to work and later died.",
    "The employee suffered a heart attack and was killed.",
    "Employee #1 was trying to start a yard truck whose battery had died.",
    "The employee was hospitalized for a fractured femur and released.",
    None,
])
def test_not_a_reported_death(con, txt):
    assert reports_death(con, txt) is False
