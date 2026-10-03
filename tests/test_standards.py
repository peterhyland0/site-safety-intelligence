"""Standard-code parsing (02_standard_macros.sql) and the hazard map (31_hazard_map.sql + ref CSVs)."""
import csv
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "ssi" / "pipeline" / "sql"
REF = ROOT / "ssi" / "pipeline" / "ref"
MACROS = (SQL / "02_standard_macros.sql").read_text()
HAZARD_SQL = (SQL / "31_hazard_map.sql").read_text()

FAMILIES = {"federal_1926", "federal_1910", "federal_other", "general_duty", "state_WA", "state_OR",
            "state_MI", "state_CA", "state_other", "unknown"}


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    c.execute(MACROS)
    return c


def parse(con, raw, state=None):
    return con.execute("SELECT std_parse_with_state(?, ?)", [raw, state]).fetchone()[0]


# raw code, site_state, family, section_key, citation (examples taken from the real data)
PARSE_CASES = [
    ("19260501 B13", None, "federal_1926", "1926.501", "1926.501(b)(13)"),
    ("19260500 E01   IV", None, "federal_1926", "1926.500", "1926.500(e)(1)(iv)"),
    ("5A0001", None, "general_duty", "5(a)(1)", "5(a)(1)"),
    ("19101200 E01", None, "federal_1910", "1910.1200", "1910.1200(e)(1)"),
    ("19261408 B04 II A", None, "federal_1926", "1926.1408", "1926.1408(b)(4)(ii)(A)"),
    ("19260404 F07   IVC", None, "federal_1926", "1926.404", "1926.404(f)(7)(iv)(C)"),
    ("19260405 A02   IIE1", None, "federal_1926", "1926.405", "1926.405(a)(2)(ii)(E)(1)"),
    ("19260059 H", None, "federal_1926", "1926.59", "1926.59(h)"),
    ("19260096", None, "federal_1926", "1926.96", "1926.96"),
    ("19040039 A01", None, "federal_other", "1904.39", "1904.39(a)(1)"),
    ("19030019 A", None, "federal_other", "1903.19", "1903.19(a)"),
    # Washington: current WAC form and the pre-2015 packed form
    ("296-155-24609(7)(A)", "WA", "state_WA", "WAC 296-155-24609", "WAC 296-155-24609(7)(a)"),
    ("296-62-07721(2)(E)", "WA", "state_WA", "WAC 296-62-07721", "WAC 296-62-07721(2)(e)"),
    ("1550065701 A", "WA", "state_WA", "WAC 296-155-657", "WAC 296-155-657(1)(a)"),
    # Oregon
    ("OAR 437-003-1501(1)", "OR", "state_OR", "OAR 437-003-1501", "OAR 437-003-1501(1)"),
    ("OAR 437-001-0760(1)(A)-2", "OR", "state_OR", "OAR 437-001-0760", "OAR 437-001-0760(1)(a)-2"),
    ("703150202", "OR", "state_OR", "OAR 437-003-1502", "OAR 437-003-1502(2)"),
    ("701076506 A    B", "OR", "state_OR", "OAR 437-001-0765", "OAR 437-001-0765(6)(a)(B)"),
    # Michigan: rule, packed rule, MIOSH Act section
    ("408.40132(5)", "MI", "state_MI", "R 408.40132", "R 408.40132(5)"),
    ("4084011401", "MI", "state_MI", "R 408.40114", "R 408.40114(1)"),
    ("408.1011(A)", "MI", "state_MI", "MCL 408.1011", "MCL 408.1011(a)"),
    # California Title 8: current, old spaced and old packed forms
    ("3395(H)", "CA", "state_CA", "T8 CCR 3395", "T8 CCR 3395(h)"),
    ("1509 B", "CA", "state_CA", "T8 CCR 1509", "T8 CCR 1509(b)"),
    ("15410001 A01", "CA", "state_CA", "T8 CCR 1541.1", "T8 CCR 1541.1(a)(1)"),
    ("43000029 A", "CA", "state_CA", "T8 CCR 14300.29", "T8 CCR 14300.29(a)"),
    ("341.1(H)(2)(B)", "CA", "state_CA", "T8 CCR 341.1", "T8 CCR 341.1(h)(2)(B)"),
    # other state plans: state-qualified raw code
    ("182.653(08)", "MN", "state_other", "MN 182.653", "MN 182.653(08)"),
    ("12 NYCRR PART 801.4", "NY", "state_other", "NY 12 NYCRR PART 801.4", "NY 12 NYCRR PART 801.4"),
]


@pytest.mark.parametrize("raw,state,family,key,cite", PARSE_CASES)
def test_parse(con, raw, state, family, key, cite):
    p = parse(con, raw, state)
    assert (p["std_family"], p["section_key"], p["standard_cite"]) == (family, key, cite)


@pytest.mark.parametrize("raw", ["19260501 B13", "19260500 E01   IV", "5A0001", "19101200 E01"])
def test_single_argument_macros_match_parse(con, raw):
    fam, key, cite = con.execute("SELECT std_family(?), section_key(?), standard_cite(?)", [raw] * 3).fetchone()
    p = parse(con, raw)
    assert (fam, key, cite) == (p["std_family"], p["section_key"], p["standard_cite"])


@pytest.mark.parametrize("raw,state,family", [
    # self-identifying formats ignore the site state
    ("19260501 B13", "CA", "federal_1926"),
    ("296-155-110(2)", None, "state_WA"),
    ("296-155-110(2)", "OR", "state_WA"),
    ("OAR 437-003-0134(8)(A)", None, "state_OR"),
    ("408.40114(1)", None, "state_MI"),
    ("GENERAL DUTY CLAUSE", None, "general_duty"),
    # ambiguous formats need the state; without it the dominant state's family is assumed
    ("3395(H)", None, "state_CA"),
    ("1509 B", "CA", "state_CA"),
    ("1509 B", "NV", "state_other"),
    ("4084011401", None, "state_MI"),
    ("4084011401", "MN", "state_other"),
    ("1550065701 A", "WA", "state_WA"),
    ("408.11442(2)", "IL", "state_other"),
    ("RULE 4(1)", "MI", "state_MI"),
    ("RULE 800-01-09-.06(2)", "TN", "state_other"),
    # junk
    ("", None, "unknown"),
    (None, None, "unknown"),
    ("E", None, "unknown"),
    ("�59.1-408.1", "VA", "unknown"),
])
def test_family(con, raw, state, family):
    assert con.execute("SELECT std_family_with_state(?, ?)", [raw, state]).fetchone()[0] == family


def test_unknown_has_no_section_key(con):
    assert parse(con, "", None)["section_key"] is None


def test_natural_key_orders_sections_numerically(con):
    keys = ["1926.1053", "1926.95", "1926.501", "1926.1000", "1926.5"]
    got = [r[0] for r in con.execute(
        "SELECT k FROM unnest(?::VARCHAR[]) t(k) ORDER BY std_natural_key(k)", [keys]).fetchall()]
    assert got == ["1926.5", "1926.95", "1926.501", "1926.1000", "1926.1053"]


# ------------------------------------------------------------------ hazard map: rule precedence on a tiny map

def build(con, standards, rules):
    con.execute("CREATE OR REPLACE TEMP TABLE stg_violation (activity_nr VARCHAR, citation_id VARCHAR, "
                "standard_raw VARCHAR, site_state VARCHAR)")
    con.executemany("INSERT INTO stg_violation VALUES (?, ?, ?, ?)",
                    [(str(i), "01001", raw, st) for i, (raw, st) in enumerate(standards)])
    con.execute("CREATE OR REPLACE TEMP TABLE ref_standard_hazard_map (family VARCHAR, match_type VARCHAR, "
                "pattern VARCHAR, range_to VARCHAR, hazard_code VARCHAR, note VARCHAR)")
    con.executemany("INSERT INTO ref_standard_hazard_map VALUES (?, ?, ?, ?, ?, '')", rules)
    con.execute(HAZARD_SQL)
    return {r[0]: r[1] for r in con.execute(
        "SELECT s.standard_raw, h.hazard_code FROM violation_hazard h "
        "JOIN stg_violation s USING (activity_nr, citation_id)").fetchall()}


TINY_RULES = [
    ("federal_1926", "range", "1926.750", "1926.761", "steel_concrete_masonry"),
    ("federal_1926", "exact", "1926.760", None, "fall_protection"),          # exact beats the range around it
    ("federal_1926", "range", "1926.450", "1926.454", "scaffolds"),
    ("federal_1926", "range", "1926.1", "1926.1500", "outer_range"),       # innermost range wins
    ("state_WA", "prefix", "WAC 296-", None, "short_prefix"),
    ("state_WA", "prefix", "WAC 296-880-", None, "fall_protection"),        # longest prefix wins
    ("state_CA", "range", "T8 CCR 1539", "T8 CCR 1547", "excavation_trenching"),  # range covers 1541.1
]


def test_hazard_map_precedence(con):
    got = build(con, [
        ("19260760 A01", None),          # exact
        ("19260451 G01", None),          # range
        ("296-880-20005(6)", "WA"),      # prefix
        ("15410001 A01", "CA"),          # range covering a decimal subsection
        ("182.653(08)", "MN"),           # unmatched -> other
        ("19260761 B", None),            # range (not the exact)
        ("19269999 A", None),            # outside every federal range -> other
        ("", None),                      # unknown -> other
    ], TINY_RULES)
    assert got == {
        "19260760 A01": "fall_protection",
        "19260451 G01": "scaffolds",
        "296-880-20005(6)": "fall_protection",
        "15410001 A01": "excavation_trenching",
        "182.653(08)": "other",
        "19260761 B": "steel_concrete_masonry",
        "19269999 A": "other",
        "": "other",
    }


def test_hazard_map_one_row_per_citation(con):
    build(con, [("19260501 B13", None), ("19260501 B13", None), ("3395(H)", "CA")], TINY_RULES)
    n_stg, n_out, n_null = con.execute(
        "SELECT (SELECT count(*) FROM stg_violation), count(*), count(*) FILTER (WHERE hazard_code IS NULL) "
        "FROM violation_hazard").fetchone()
    assert n_out == n_stg and n_null == 0


# ------------------------------------------------------------------ the shipped reference CSVs

def read_csv(name):
    with open(REF / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_hazard_map_csv_is_consistent(con):
    rules = read_csv("standard_hazard_map.csv")
    codes = {r["hazard_code"] for r in read_csv("hazard_category.csv")}
    assert "other" in codes
    seen = set()
    for r in rules:
        assert r["family"] in FAMILIES, r
        assert r["match_type"] in {"exact", "range", "prefix"}, r
        assert r["hazard_code"] in codes, r
        assert bool(r["range_to"]) == (r["match_type"] == "range"), r
        k = (r["family"], r["match_type"], r["pattern"])
        assert k not in seen, f"duplicate rule {k}"
        seen.add(k)


def test_hazard_map_ranges_are_nested_or_disjoint(con):
    """Overlapping ranges must nest, so 'innermost range wins' is well defined."""
    con.execute(f"CREATE OR REPLACE TEMP TABLE m AS SELECT * FROM read_csv('{REF / 'standard_hazard_map.csv'}', "
                "header=true, all_varchar=true) WHERE match_type = 'range'")
    bad = con.execute("""
        WITH r AS (SELECT family, pattern, range_to, std_natural_key(pattern) lo, std_natural_key(range_to) || '~' hi FROM m)
        SELECT a.family, a.pattern, a.range_to, b.pattern, b.range_to
        FROM r a JOIN r b ON a.family = b.family AND a.pattern < b.pattern
        WHERE a.lo <= b.hi AND b.lo <= a.hi                       -- overlap
          AND NOT ((a.lo <= b.lo AND b.hi <= a.hi) OR (b.lo <= a.lo AND a.hi <= b.hi))  -- but neither contains the other
    """).fetchall()
    assert bad == []


@pytest.mark.parametrize("raw,state,hazard", [
    ("19260501 B13", None, "fall_protection"),
    ("19260760 A01", None, "fall_protection"),
    ("19260451 G01", None, "scaffolds"),
    ("19261053 B01", None, "ladders"),
    ("19260652 A01", None, "excavation_trenching"),
    ("19100178 L01", None, "motor_vehicles_equipment"),
    ("19101200 E01", None, "hazcom"),
    ("19260062 D02", None, "health_silica_lead_asbestos_noise"),
    ("19030019 A", None, "recordkeeping"),
    ("5A0001", None, "general_duty"),
    ("296-155-110(2)", "WA", "safety_program_training"),
    ("296-62-09530(1)", "WA", "heat"),
    ("296-880-20005(6)", "WA", "fall_protection"),
    ("OAR 437-003-1501(1)", "OR", "fall_protection"),
    ("OAR 437-002-0156(5)", "OR", "heat"),
    ("408.40114(1)", "MI", "safety_program_training"),
    ("408.41243(13)", "MI", "scaffolds"),
    ("3395(H)", "CA", "heat"),
    ("1509 B", "CA", "safety_program_training"),
    ("15410001 A01", "CA", "excavation_trenching"),
    ("1716.2(E)", "CA", "fall_protection"),
])
def test_shipped_map_known_codes(con, raw, state, hazard):
    con.execute(f"CREATE OR REPLACE TEMP TABLE ref_standard_hazard_map AS SELECT * FROM "
                f"read_csv('{REF / 'standard_hazard_map.csv'}', header=true, all_varchar=true)")
    con.execute("CREATE OR REPLACE TEMP TABLE stg_violation AS SELECT '1' activity_nr, '01001' citation_id, "
                "?::VARCHAR standard_raw, ?::VARCHAR site_state", [raw, state])
    con.execute(HAZARD_SQL)
    assert con.execute("SELECT hazard_code FROM violation_hazard").fetchone()[0] == hazard


def test_reference_csvs_shape():
    vt = {r["code"]: r for r in read_csv("violation_type.csv")}
    assert set(vt) == {"S", "O", "R", "W", "U", "P"}
    assert {c for c, r in vt.items() if r["serious_plus"] == "true"} == {"S", "W", "R", "U"}
    it = read_csv("inspection_type.csv")
    assert [r["code"] for r in it] == list("ABCDEFGHIJKLMN")
    assert {r["code"] for r in it if r["is_accident"] == "true"} == {"A", "M"}
    sp = read_csv("state_plan.csv")
    assert len(sp) == 29 and sum(r["plan_scope"] == "public_only" for r in sp) == 7
    trade = read_csv("trade.csv")
    assert {r["code"] for r in trade if r["code_type"] == "naics4"} == {
        "2361", "2362", "2371", "2372", "2373", "2379", "2381", "2382", "2383", "2389"}
    naics4 = {r["code"] for r in trade if r["code_type"] == "naics4"}
    assert all(r["naics4"] in naics4 or r["naics4"] == "" for r in trade)
