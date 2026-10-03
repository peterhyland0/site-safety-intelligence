import duckdb
import pytest

from ssi.cleaning import NAME_STEPS, install_macros


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    install_macros(c)
    return c


def q(con, expr, *args):
    return con.execute(f"SELECT {expr}", list(args)).fetchone()[0]


def clean(con, s):
    return q(con, "clean_name(?)", s)


SAME = [
    # Brasfield & Gorrie spellings seen in OSHA's data must all clean to one name
    ["BRASFIELD & GORRIE, LLC", "136200 - BRASFIELD - GORRIE, L.L.C.", "BRASFIELD & GORRIE GP, L.L.C.",
     "Brasfield & Gorrie, L.L.C. (Delaware)", "BRASFIELD AND GORRIE LLC", "BRASFIELD & GORRIE, L.P.",
     "BRASFIELD & GORRIE, INC."],
    ["O'BRIEN ELECTRIC", "OBRIEN ELECTRIC INC"],
    ["J.R. JOHNSON LLC", "J R JOHNSON INC", "JR JOHNSON"],
    ["THE WHITING-TURNER CONTRACTING COMPANY", "WHITING TURNER CONTRACTING CO"],
    ["WA317965935 - BARNHART CRANE & RIGGING CO", "BARNHART CRANE AND RIGGING CO."],
    # "The Clark Construction Group, LLC" as some offices write it
    ["CLARK CONSTRUCTION GROUP, LLC", "WA317962258 - CLARK CONSTRUCTION GROUP LLC THE", "THE CLARK CONSTRUCTION GROUP INC"],
]

DIFFERENT = [
    ("C AND A CONSTRUCTION", "C AND S CONSTRUCTION"),
    ("BRASFIELD CONSTRUCTION, INC.", "BRASFIELD & GORRIE, LLC"),
    ("HOFFMAN CONSTRUCTION COMPANY OF AMERICA", "HOFFMAN CONSTRUCTION COMPANY OF OREGON"),
    ("CONNER HOMES AT ELAN", "CONNER HOMES AT MERIDIAN"),
    ("SMITH ROOFING", "SMITH ELECTRIC"),
    ("CLARK CONCRETE CONTRACTORS", "CLARK CONSTRUCTION GROUP"),
    ("561-ROOFING, INC", "ROOFING INC"),  # 561 is part of the company name, not an inspection ID
]

EXACT = {
    "BRASFIELD & GORRIE, LLC": "BRASFIELD GORRIE",
    "84 LUMBER": "84 LUMBER",
    "1ST CHOICE ROOFING": "1ST CHOICE ROOFING",
    "NEXT 150 CONSTRUCTION": "NEXT 150 CONSTRUCTION",
    "WA317965935 - BARNHART CRANE & RIGGING CO": "BARNHART CRANE RIGGING",
    "C AND A CONSTRUCTION": "CA CONSTRUCTION",
    "M & M MASONRY, INC. D/B/A MASONRY, INC.": "MM MASONRY DBA MASONRY",
    "XYZ HOLDINGS LLC DBA ABC ROOFING": "XYZ HOLDINGS DBA ABC ROOFING",
    "HOFFMAN CONSTRUCTION COMPANY OF AMERICA": "HOFFMAN CONSTRUCTION COMPANY OF AMERICA",
    "CO": "CO",  # never strip a name down to nothing
    "561-ROOFING, INC": "561 ROOFING",
    "1234 - ACME DRYWALL": "ACME DRYWALL",  # short ID with a spaced dash
    # Arizona's and Iowa's case numbers in front of the name
    "FCX2024XEG419X0079 - VALLEYCARE LANDSCAPING, LLC": "VALLEYCARE LANDSCAPING",
    "URX2022XRS251X0001 - WILLMENG CONSTRUCTION, INC.": "WILLMENG CONSTRUCTION",
    "A09CS000013UQXVAA4 - PHILLIP'S FLOORS INC.": "PHILLIPS FLOORS",
    "3M COMPANY": "3M",
    "A1 ROOFING - DIVISION 2": "A1 ROOFING DIVISION 2",
    "B2B CONTRACTING - NORTH": "B2B CONTRACTING NORTH",
}


@pytest.mark.parametrize("group", SAME)
def test_variants_merge(con, group):
    cleaned = {clean(con, s) for s in group}
    assert len(cleaned) == 1, cleaned


@pytest.mark.parametrize("a,b", DIFFERENT)
def test_different_companies_stay_apart(con, a, b):
    assert clean(con, a) != clean(con, b)


@pytest.mark.parametrize("raw,expected", EXACT.items())
def test_exact_output(con, raw, expected):
    assert clean(con, raw) == expected


def test_dba_parts(con):
    c = clean(con, "XYZ HOLDINGS LLC DBA ABC ROOFING")
    assert q(con, "legal_part(?)", c) == "XYZ HOLDINGS"
    assert q(con, "dba_part(?)", c) == "ABC ROOFING"
    assert q(con, "dba_part(?)", "BRASFIELD GORRIE") is None


@pytest.mark.parametrize("raw,expected", [
    ("UNKNOWN ROOFER", True), ("Unknown/Invalid Establishment", True), ("N/A", True), ("", True),
    ("UNITED ROOFING", False), ("BRASFIELD & GORRIE", False),
    ("Home Owner", True), ("ROOFING CONTRACTOR", True), ("Self-Employed", True), ("UNK", True),
    ("ABC ROOFING CONTRACTOR", False),
    # OSHA's own offices entered as the employer on internal records
    ("USDOL OSHA - CINCINNATI AREA OFFICE", True), ("U.S. DOL OSHA AUSTIN AREA OFFICE", True),
    ("US Department of Labor - OSHA", True), ("WICHITA AREA OSHA OFFICE", True), ("OSHA", True),
    ("OSHA STEEL", False), ("OSHA TRAINING INSTITUTE", False),
])
def test_placeholders(con, raw, expected):
    assert q(con, "is_placeholder(clean_name(?))", raw) is expected


def test_joint_venture(con):
    assert q(con, "is_jv(clean_name(?))", "CLARK, SMOOT, CONSIGLI, A JOINT VENTURE") is True
    assert q(con, "is_jv(clean_name(?))", "CLARK CONSTRUCTION") is False


@pytest.mark.parametrize("raw,core", [
    ("BRASFIELD & GORRIE", "BRASFIELD GORRIE"),
    ("BRASFIELD CONSTRUCTION INC", "BRASFIELD"),
    ("CLARK CONCRETE CONTRACTORS", "CLARK"),
    ("QUALITY ROOFING", ""),
    ("XYZ HOLDINGS DBA ABC ROOFING", "XYZ"),
])
def test_name_core(con, raw, core):
    assert q(con, "name_core(clean_name(?))", raw) == core


def test_initials_and_sibling(con):
    assert q(con, "initials_only(clean_name(?))", "C AND A CONSTRUCTION") is True
    assert q(con, "initials_only(clean_name(?))", "J.R. JOHNSON") is False
    assert q(con, "sibling_suffix(clean_name(?))", "CONNER HOMES AT ELAN") == " AT ELAN"
    assert q(con, "sibling_suffix(clean_name(?))", "BRASFIELD & GORRIE") is None


@pytest.mark.parametrize("a,b", [
    ("3021 7th Ave South", "3021 7TH AVE S"),
    ("3021 Seventh-street placeholder", "3021 SEVENTH"),
    ("P. O. Box 10383", "PO BOX 10383"),
    ("P O BOX 10383", "Post Office Box 10383"),
])
def test_addr_key_variants(con, a, b):
    assert q(con, "addr_key(?)", a) == q(con, "addr_key(?)", b)


def test_address_rules(con):
    assert q(con, "addr_key(?)", "3021 7th Ave South") == "3021 7TH"
    assert q(con, "addr_key(?)", "P.O. Box 1385") == "POBOX 1385"
    assert q(con, "addr_key(?)", "1201 Demonbreun St Ste 200") == "1201 DEMONBREUN"
    assert q(con, "addr_unit(?)", "1201 Demonbreun St Ste 200") == "Ste 200".upper()
    assert q(con, "zip5(?)", "35233-1234") == "35233"
    assert q(con, "zip5(?)", "2134") == "02134"
    assert q(con, "zip5(?)", "00000") is None


def test_steps_compose_to_clean_name(con):
    # The per-rule steps applied in order must equal clean_name (the build's merge counts rely on this)
    raw = "136200 - The Brasfield & Gorrie, L.L.C. (Delaware)"
    expr = "?"
    for step in NAME_STEPS:
        expr = f"{step}({expr})"
    assert q(con, f"trim(regexp_replace({expr}, '\\s+', ' ', 'g'))", raw) == clean(con, raw)


def test_temp_macros_on_read_only(tmp_path):
    path = tmp_path / "w.duckdb"
    duckdb.connect(str(path)).close()
    ro = duckdb.connect(str(path), read_only=True)
    install_macros(ro, temp=True)
    assert ro.execute("SELECT clean_name('BRASFIELD & GORRIE, LLC')").fetchone()[0] == "BRASFIELD GORRIE"
