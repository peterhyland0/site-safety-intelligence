"""Names in the built warehouse: invariants over every establishment and name core OSHA's data produced, where a
synthetic test can't reach. Skipped without a warehouse, and when the warehouse was built from other cleaning rules
or name lists than the repo's (run `make build`): its figures then describe the old rules."""
import csv

import duckdb
import pytest

from ssi import config
from ssi.cleaning import install_macros
from ssi.matching.candidates import PLACE_PREFIXES, is_person_core
from ssi.store import warehouse

pytestmark = pytest.mark.skipif(config.current_warehouse() is None, reason="needs a built warehouse")

# legal forms n9 strips from the end of a name (a name that is only a legal form keeps it)
LEGAL_END = (r" (INC|INCORPORATED|INCORPORATION|LLC|LCC|LC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|LLLP|GP|PLLC|PLC"
             r"|LIMITED LIABILITY)$")


@pytest.fixture(scope="module")
def wh(tmp_path_factory):
    # a cursor on the app's connection: DuckDB opens a file once per process, with one configuration, and an earlier
    # test may have opened the warehouse already (test_foreman_fake does). A cursor doesn't see that connection's
    # temp macros, so an older warehouse without stored ones still reads as stale below.
    con = warehouse.open_warehouse(config.current_warehouse()).cursor()
    # the repo's macros as a stored database prints them (stored lambdas read back in another form than they're written)
    path = tmp_path_factory.mktemp("macros") / "repo.duckdb"
    with duckdb.connect(str(path)) as repo:
        install_macros(repo)
    defs = "SELECT function_name, macro_definition FROM duckdb_functions() WHERE function_type = 'macro' AND schema_name = 'main'"
    with duckdb.connect(str(path), read_only=True) as repo:
        current = dict(repo.execute(defs).fetchall())
    built = dict(con.execute(defs).fetchall())
    stale = sorted(n for n in current if built.get(n) != current[n])
    for ref in ("given_name", "surname"):
        with (config.REF_DIR / f"{ref}.csv").open() as f:
            want = sorted(r["name"].strip().upper() for r in csv.DictReader(f))
        try:
            have = sorted(r[0] for r in con.execute(f"SELECT upper(trim(name)) FROM ref.{ref}").fetchall())
        except duckdb.CatalogException:
            have = None
        if have != want:
            stale.append(f"ref/{ref}.csv")
    if stale:
        pytest.skip(f"warehouse built from older name rules ({', '.join(stale[:4])}); run `make build`")
    yield con
    con.close()


def test_every_clean_name_is_upper_letters_digits_and_single_spaces(wh):
    bad = wh.execute("""SELECT clean_name FROM entity.establishment
                        WHERE clean_name <> '' AND NOT regexp_full_match(clean_name, '[A-Z0-9]+( [A-Z0-9]+)*') LIMIT 5""").fetchall()
    assert bad == []


def test_no_legal_form_is_left_on_a_name(wh):
    # what's left: a name that is only a legal form, or initials that became one when joined (P C -> PC)
    left = wh.execute(f"""
        SELECT clean_name, display_name FROM entity.establishment
        WHERE regexp_matches(clean_name, '{LEGAL_END}')
          AND NOT regexp_matches(upper(display_name), '(^|[^A-Z])[A-Z][ .&]+[A-Z][ .,]*$|(^|[^A-Z])[A-Z][ .&]+[A-Z][ .&]+[A-Z][ .,]*$')
        LIMIT 10""").fetchall()
    assert left == []


def test_no_dangling_dba_or_the_before_a_legal_form(wh):
    assert wh.execute("SELECT count(*) FROM entity.establishment WHERE regexp_matches(clean_name, ' DBA$| THE$')").fetchone()[0] == 0


def test_initials_are_never_left_in_pairs(wh):
    # "H V A C" was cleaned to "HV AC" (pairwise joining); every spaced run of single letters is now one word
    n = wh.execute("""SELECT count(*) FROM entity.establishment e, unnest(e.name_variants) v(raw)
                      WHERE regexp_matches(clean_name(raw), '(^| )[A-Z]( [A-Z])+( |$)')""").fetchone()[0]
    assert n == 0


def test_every_joint_venture_is_flagged(wh):
    # "JOINT VENTURE", "(JV)" or a JV after the name; not initials that end in V (J.J.V. ENTERPRISE, A J V CONSTRUCTION)
    missed = wh.execute(r"""SELECT DISTINCT e.clean_name FROM entity.establishment e, unnest(e.name_variants) v(raw)
                            WHERE regexp_matches(upper(raw), 'JOINT VENTURE|\(J\.?V\.?\)|[A-Z]{2,}[ ,-]+J\.?V\.?,?( (LLC|INC|LP|LLP)\.?)?\s*$')
                              AND NOT e.is_jv LIMIT 10""").fetchall()
    assert missed == []


def test_python_and_the_build_agree_on_every_persons_name(wh):
    rows = wh.execute("SELECT name_core, is_person FROM entity.core_stats").fetchall()
    assert len(rows) > 50_000
    assert [core for core, built in rows if is_person_core(core) != built] == []


def test_no_persons_name_is_rated_distinctive(wh):
    # a person's name is "person", or "generic" when every word is short (DAN RAY): both need a city to match
    assert wh.execute("SELECT count(*) FROM entity.core_stats WHERE is_person AND tier NOT IN ('person', 'generic')"
                      ).fetchone()[0] == 0


def test_place_names_are_not_people(wh):
    people = wh.execute("""SELECT name_core FROM entity.core_stats
                           WHERE is_person AND len(string_split(name_core, ' ')) = 2
                             AND list_contains(?::VARCHAR[], split_part(name_core, ' ', 1))""",
                        [sorted(PLACE_PREFIXES)]).fetchall()
    assert people == []


def test_known_people_and_companies(wh):
    tiers = dict(wh.execute("""SELECT name_core, tier FROM entity.core_stats WHERE name_core IN
        ('JOSE HERNANDEZ', 'ALEX PEREZ', 'J LOPEZ', 'EDGAR LOPEZ', 'JUAN GARCIA', 'SAN JOAQUIN', 'ST GEORGE', 'SAN ANTONIO',
         'BRASFIELD GORRIE', 'BARTON MALOW', 'JOHNSON CONTROLS', 'ALLAN MYERS')""").fetchall())
    for person in ("JOSE HERNANDEZ", "ALEX PEREZ", "J LOPEZ", "EDGAR LOPEZ", "JUAN GARCIA"):
        assert tiers.get(person, "person") == "person", person
    for company in ("SAN JOAQUIN", "ST GEORGE", "SAN ANTONIO", "BRASFIELD GORRIE", "BARTON MALOW", "JOHNSON CONTROLS",
                    "ALLAN MYERS"):
        assert tiers.get(company, "distinctive") != "person", company


def test_one_company_under_many_spellings(wh):
    # every Brasfield & Gorrie record cleans to one name (plus a slip in OSHA's own data), whatever the spelling
    names = {r[0] for r in wh.execute("""SELECT DISTINCT clean_name FROM entity.establishment
                                         WHERE clean_name LIKE 'BRASFIELD%GOR%' AND NOT is_jv""").fetchall()}
    assert names and names <= {"BRASFIELD GORRIE", "BRASFIELD GORIE", "BRASFIELD GORRIE GENERAL CONTRACTOR",
                               "BRASFIELD GORRIE GENERAL CONTRACTORS"}, names
