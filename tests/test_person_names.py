"""People's names. Sole proprietors appear in OSHA's data under the owner's name, and the same name is usually many
different people (JOSE HERNANDEZ: 49 records in 17 states), so a person's name is only matched by place. A real
person's name the rule misses is rated by its rarity instead, and a rare one auto-matched across states (ALEX PEREZ:
7 records in 5 states); a company's name the rule takes for a person loses its records in other cities.

The rule has two copies: the is_person_name macro (core_stats.is_person, related-facility scope) and
candidates.is_person_core (the GC's own entry, at query time). Both read ref/given_name.csv and ref/surname.csv."""
import csv
import itertools

import duckdb
import pytest

from ssi import config
from ssi.cleaning import install_macros
from ssi.matching import candidates
from ssi.matching.candidates import PLACE_PREFIXES, given_names, is_person_core, surnames

PEOPLE = [
    "JUAN GARCIA", "JOSE HERNANDEZ", "JOSE LUIS GARCIA", "MARIA LOS ANGELES GARCIA", "JOHN SMITH JR",
    "HERNANDEZ JOSE",  # surname first
    "MORALES JAVIER M", "RAMIREZ JOSE L",  # surname first, then a middle initial (31 of these were rated distinctive)
    "J LOPEZ", "R GARCIA", "M CAMPBELL",  # an initial and a common surname (J LOPEZ: 7 states)
    # given names the list was missing, each first in real records rated distinctive in several states
    "ALEX PEREZ", "EDGAR LOPEZ", "JOSUE HERNANDEZ", "IVAN TORRES", "ELMER GARCIA", "RENE MARTINEZ", "JOEL LOPEZ",
    "CHRISTIAN SANCHEZ", "ERICK HERNANDEZ", "RAMIRO PEREZ", "EDWIN LOPEZ", "CHARLIE JONES",
    # places and titles inside a person's name don't stop it being one
    "GARY ST CLAIR", "RAYMOND SAN DIEGO", "JOSE DEL RIO", "RICARDO LA ROSA",
]
NOT_PEOPLE = [
    "BRASFIELD GORRIE", "JOSE", "JR 84", "AUSTIN BRIDGE ROAD", "",
    # place names that end in a given name: companies named after a city (they were rated as people)
    "SAN ANTONIO", "SAN JOSE", "SAN JUAN", "SAN DIEGO", "SAN JOAQUIN", "SANTA MARIA", "SANTA ROSA", "ST GEORGE",
    "ST JOHN", "SAINT JOSEPH", "FORT WAYNE", "FT WAYNE", "PORT ARTHUR", "MT VERNON", "LAKE TRAVIS", "LOS SANTOS",
    "CAPE ANN",
    # companies named with surnames, and well-known firms whose first word is also a name
    "JOHNSON CONTROLS", "BARTON MALOW", "TAYLOR MORRISON", "ROBINS MORTON", "MARTIN MARIETTA", "ALLAN MYERS",
    "WILLIAMS SCOTSMAN", "HENKELS MCCOY", "BEN HUR",
    # an initial and a word that isn't a common surname
    "J CREW", "A1 SMITH", "J 84",
    # too many words, digits
    "JOSE LUIS LA CRUZ MARTINEZ", "JUAN 2 GARCIA",
]


@pytest.mark.parametrize("core", PEOPLE)
def test_recognises_peoples_names(core):
    assert is_person_core(core)


@pytest.mark.parametrize("core", NOT_PEOPLE)
def test_leaves_company_and_place_names_alone(core):
    assert not is_person_core(core)


@pytest.fixture(scope="module")
def sql():
    """A DuckDB connection with the macros and both name lists, as the build has them."""
    c = duckdb.connect()
    install_macros(c)
    for ref in ("given_name", "surname"):
        c.execute(f"CREATE TABLE ref_{ref} AS SELECT * FROM read_csv('{config.REF_DIR / (ref + '.csv')}', "
                  "header = true, all_varchar = true)")
    return c


def sql_is_person(sql, cores: list[str]) -> list[bool]:
    return sql.execute("""
        WITH g AS (SELECT list(upper(trim(name))) AS names FROM ref_given_name),
             s AS (SELECT list(upper(trim(name))) AS names FROM ref_surname)
        SELECT list(is_person_name(c, g.names, s.names) ORDER BY i)
        FROM unnest(?::VARCHAR[]) WITH ORDINALITY t(c, i), g, s""", [cores]).fetchone()[0]


def test_sql_and_python_rules_agree(sql):
    # every shape the rule looks at: given names and surnames in each position, initials, places, 1-5 words
    g = sorted(given_names())[::7]
    s = sorted(surnames())[::7]
    words = g[:40] + s[:40] + sorted(PLACE_PREFIXES) + ["J", "M", "X", "ROOFING", "ACME", "BRASFIELD", "84"]
    cores = PEOPLE + NOT_PEOPLE + [" ".join(p) for n in (1, 2, 3) for p in itertools.product(words[::3], repeat=n)]
    cores += [f"{a} {b} {c} {d}" for a, b, c, d in zip(g, s, g[1:], "ABCDEFGHIJKLMNOPQRSTUVWXYZ")]
    cores += [f"{a} {b} {c} {d} {e}" for a, b, c, d, e in zip(g, g[1:], s, s[1:], g[2:])]
    python = [is_person_core(c) for c in cores]
    assert {c: p for c, p, q in zip(cores, python, sql_is_person(sql, cores)) if p != q} == {}
    assert 0.1 < sum(python) / len(python) < 0.9  # the corpus has both kinds


def test_place_prefixes_are_the_macros(sql):
    assert PLACE_PREFIXES == frozenset(sql.execute("SELECT ssi_place_prefixes()").fetchone()[0])


def test_null_and_empty_cores_are_not_people(sql):
    assert sql.execute("SELECT is_person_name(NULL, ['JOSE'], ['LOPEZ']), is_person_name('', ['JOSE'], ['LOPEZ'])"
                       ).fetchone() == (False, False)


def test_a_gcs_entry_is_cleaned_before_it_is_rated(sql):
    # what the GC types reaches the rule as a cleaned core: accents, commas, middle initials, trade words, legal forms
    typed = {"Juan A. García Roofing, LLC": True, "José Hernández": True, "Morales, Javier M.": True,
             "J. Lopez Drywall": True, "Alex Pérez Construction Inc": True, "San Antonio Roofing": False,
             "St. George Builders": False, "Brasfield & Gorrie": False, "Hernández, José": True}
    cores = sql.execute("SELECT list(name_core(clean_name(s)) ORDER BY i) FROM unnest(?::VARCHAR[]) WITH ORDINALITY t(s, i)",
                        [list(typed)]).fetchone()[0]
    assert {t: c for t, c, want in zip(typed, cores, typed.values()) if is_person_core(c) != want} == {}


def test_a_persons_tier_needs_no_warehouse(monkeypatch):
    # the GC's own entry is rated at query time; a person's name is "person" whatever core_stats says
    monkeypatch.setattr(candidates.warehouse, "one", lambda *a, **k: pytest.fail("looked up core_stats"))
    assert candidates.core_tier("ALEX PEREZ", False) == "person"
    assert candidates.core_tier("", False) == "generic"
    assert candidates.core_tier("CA", True) == "generic"


@pytest.mark.parametrize("file", ["given_name.csv", "surname.csv"])
def test_name_lists_are_clean(file):
    with (config.REF_DIR / file).open() as f:
        names = [r["name"] for r in csv.DictReader(f)]
    assert names == sorted(set(names)), "sorted, no repeats"
    assert all(n.isalpha() and n.isupper() and n == n.strip() for n in names)
    c = duckdb.connect()
    install_macros(c)
    generic = set(c.execute("SELECT ssi_generic_tokens()").fetchone()[0])
    # a trade or descriptor word in a name list would turn companies into people (or people into companies)
    assert set(names) & generic == set()
    assert set(names) & PLACE_PREFIXES == set()


def test_given_names_leave_out_words_that_name_companies():
    # each of these starts real companies' names (MARTIN MARIETTA, ALLAN MYERS, BEN HUR, ORLANDO HEALTH, MILTON CAT)
    assert not {"MARTIN", "ALLAN", "BEN", "ORLANDO", "MILTON", "GERMAN", "JAY", "RICH", "TOWN", "CITY"} & given_names()
    # surnames that are everyday words would make "J STONE" or "A DAY" a person
    assert not {"STONE", "LONG", "DAY", "MAY", "PARK", "WOODS", "BELL", "PRICE", "CROSS", "LANE"} & surnames()
