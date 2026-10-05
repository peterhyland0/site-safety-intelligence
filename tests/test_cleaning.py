import re
import unicodedata

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
    # a GC types accents; OSHA's records don't have them ("Muñoz" was cut to MU OZ)
    ["Muñoz Construction", "MUNOZ CONSTRUCTION LLC"],
    ["José Hernández Roofing", "JOSE HERNANDEZ ROOFING"],
    ["Peña Roofing", "PENA ROOFING INC"],
    ["Søren Ølsen Builders", "SOREN OLSEN BUILDERS"],
    # OSHA's lost accents come as ? or U+FFFD for one company; folding accents mustn't split them
    ["BERM?DEZ, LONGO, D?AZ-MASS?, LLC", "BERM�DEZ, LONGO, D�AZ-MASS�, LLC"],
    # legal forms that were left on: each was a second establishment of one company (55 such pairs in the data),
    # and the rules excluded "ADELPHI CONSTRUCTION LC" as a different name (LC) from ADELPHI CONSTRUCTION
    ["ADELPHI CONSTRUCTION, L.C.", "ADELPHI CONSTRUCTION LLC", "Adelphi Construction"],
    ["65594 - CRAFTMASTERS LIMITED LIABILITY COMPANY", "CRAFTMASTERS LLC", "CRAFTMASTERS LIMITED LIABILITY CO"],
    ["THE DRYWALL COMPANY LLLP", "DRYWALL COMPANY, LLC"],
    ["GOODSELL CONCRETE LCC", "GOODSELL CONCRETE LLC"],  # a slip for LLC
    ["CRH PLC", "CRH"],
    ["DECKER BUILDING CO.INC", "DECKER BUILDING CO., INC."],
    ["PENCZ BROTHERS, INCORPORATION", "PENCZ BROTHERS INC"],
    # cut off at a field's length limit (WA's records)
    ["WA317981341 - PIONEER DEVELOPMENT CORPORATIO", "PIONEER DEVELOPMENT CORPORATION"],
    ["WA317982128 - PROVIDENT ELECTRIC INCORPORATE", "PROVIDENT ELECTRIC INC"],
    ["COMMERCIAL DRYWALL & CONSTRUCTION COMPANY INCORPOR", "COMMERCIAL DRYWALL AND CONSTRUCTION CO"],
    # a THE between the name and its legal form, and a DBA with nothing after it
    ["WA317955263 - ANDREWS GROUP THE LLC", "THE ANDREWS GROUP, LLC", "ANDREWS GROUP LLC THE"],
    ["CRAIG HANES, INC, DBA", "CRAIG HANES INC"],
    ["CHARLES DETWILER, DBA", "CHARLES DETWILER"],
    # initials of any length, however they are written (H V A C was HV AC; V I S E was VI SE)
    ["V I S E COMPANY", "V.I.S.E. CO", "VISE CO."],
    ["TOTAL ENERGY MANAGEMENT/H V A C SVCS INC", "TOTAL ENERGY MANAGEMENT HVAC SVCS"],
    ["R D M S INC", "R.D.M.S., INC.", "RDMS"],
    # a letter and a number: A-1 ROOFING and A1 ROOFING were two names (30 such pairs in the data)
    ["A-1 ROOFING, INC.", "A1 ROOFING", "A 1 Roofing LLC"],
    ["D-7 ROOFING", "D7 ROOFING"],
    # the initials L P / G P are not a legal form after other initials
    ["J L P CONSTRUCTION", "J.L.P. CONSTRUCTION", "JLP CONSTRUCTION LLC"],
    ["R G P INC", "R.G.P., INC.", "RGP"],
    # every kind of apostrophe a keyboard or word processor makes
    ["O'BRIEN ELECTRIC", "O’BRIEN ELECTRIC", "O‘BRIEN ELECTRIC", "O´BRIEN ELECTRIC", "OʼBRIEN ELECTRIC", "O`BRIEN ELECTRIC"],
    # a name pasted from a PDF (ligatures) or typed in full-width letters
    ["ﬂoor ﬁnishers", "FLOOR FINISHERS"],
    ["ＢＲＡＳＦＩＥＬＤ ＆ ＧＯＲＲＩＥ", "BRASFIELD & GORRIE"],
    ["Ðór Construction", "DOR CONSTRUCTION"],
    ["Þórsson Builders", "THORSSON BUILDERS"],
]

DIFFERENT = [
    ("C AND A CONSTRUCTION", "C AND S CONSTRUCTION"),
    ("BRASFIELD CONSTRUCTION, INC.", "BRASFIELD & GORRIE, LLC"),
    ("HOFFMAN CONSTRUCTION COMPANY OF AMERICA", "HOFFMAN CONSTRUCTION COMPANY OF OREGON"),
    ("CONNER HOMES AT ELAN", "CONNER HOMES AT MERIDIAN"),
    ("SMITH ROOFING", "SMITH ELECTRIC"),
    ("CLARK CONCRETE CONTRACTORS", "CLARK CONSTRUCTION GROUP"),
    ("561-ROOFING, INC", "ROOFING INC"),  # 561 is part of the company name, not an inspection ID
    # a joint venture is its own company: "(JV)" is not a state of incorporation
    ("ABC CONSTRUCTION (JV)", "ABC CONSTRUCTION"),
    ("ABC CONSTRUCTION (J.V.)", "ABC CONSTRUCTION, INC."),
    # initials that look like a legal form
    ("R G P INC", "R INC"),
    ("J L P CONSTRUCTION", "J CONSTRUCTION"),
    ("A G P GLASS", "GLASS"),
    # a company called AKA is not a DBA marker with no name before it
    ("AKA ELECTRIC, LLC", "D/B/A ELECTRIC"),
    ("AKA ELECTRIC, LLC", "ELECTRIC"),
    # one digit in a company name is not an Arizona case number
    ("START2FINISHNJ - ROOFING LLC", "ROOFING LLC"),
    # a number joins only the single letter before it
    ("A-1 ROOFING", "A ROOFING"),
    ("AB 1 ROOFING", "AB1 ROOFING"),
    ("A 2020 CONSTRUCTION", "A2020 CONSTRUCTION"),  # a year is not part of A-1 style names
    # a first name, a middle initial, a family name: the initial is not part of a run of initials
    ("JOSE A HERNANDEZ", "JOSE HERNANDEZ"),
    ("JOHN SMITH JR", "JOHN SMITH SR"),
    ("JOHN SMITH JR", "JOHN SMITH"),
    # a state that is the company's name, not a note
    ("ARSENAL SCAFFOLD OF PA INC.", "ARSENAL SCAFFOLD INC."),
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
    "Łukasz Straße Bau": "LUKASZ STRASSE BAU",
    "R G P INC": "RGP",  # was "R": n8 joined G P into a legal form and n9 stripped it
    "J L P CONSTRUCTION": "JLP CONSTRUCTION",
    "M K G L L C": "MKG",  # a spaced LLC after initials is still a legal form
    "TRIPLE B SERVICES L L P": "TRIPLE B SERVICES",
    "SMITH ROOFING L P": "SMITH ROOFING",
    "A B C D E F G ROOFING": "ABCDEFG ROOFING",
    "ABC CONSTRUCTION (JV)": "ABC CONSTRUCTION JV",
    "AKA ELECTRIC, LLC": "AKA ELECTRIC",
    "A.K.A. CONSTRUCTION INC": "AKA CONSTRUCTION",
    "SMITH HOLDINGS AKA SMITH ROOFING": "SMITH HOLDINGS DBA SMITH ROOFING",
    "SMITH HOLDINGS, LLC D/B/A JONES ROOFING, INC.": "SMITH HOLDINGS DBA JONES ROOFING",
    "SMITH HOLDINGS LLC Doing Business As JONES ROOFING": "SMITH HOLDINGS DBA JONES ROOFING",
    "SMITH HOLDINGS T/A JONES ROOFING": "SMITH HOLDINGS DBA JONES ROOFING",
    "START2FINISHNJ - ROOFING LLC": "START2FINISHNJ ROOFING",
    "1121 - 1125 CLEMENT STREET, LLC": "1125 CLEMENT STREET",  # an address-named LLC; the only 3-4 digit "ID" seen
    "I-5 EXTERIORS": "I5 EXTERIORS",
    "SMITH ROOFING LIMITED LIABILITY COMPANY": "SMITH ROOFING",
    "NELSON CONSTRUCTION LIMITED LIABILITY COMPANY DBA": "NELSON CONSTRUCTION",
    "SMITH ROOFING INC OF DELAWARE": "SMITH ROOFING INC OF DELAWARE",  # OF ... is a sibling note, kept (sibling_suffix)
    "BAKER WEST INC (FN)": "BAKER WEST",
    "THE": "THE", "INC": "INC", "LLC": "LLC", "DBA": "DBA",  # never stripped down to nothing
    "": "", "   ": "", "&": "",
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
    # a direction written onto the street word: both spellings are in OSHA's data for one company's office
    ("7900 Westpark Drive Suite T300", "7900 WEST PARK DR"),
    ("3715 NORTHSIDE PKWY NW STE 175", "3715 N SIDE PKWY NW BLDG 400"),
    ("1102 SOUTHPARK RD", "1102 S PARK RD"),
    ("500 EASTMOREHEAD STE 300", "500 E MOREHEAD ST STE 300"),
    ("31000 NORTHWESTERN HWY", "31000 N WESTERN HWY"),
    ("3310 WESTEND AVE", "3310 WEST END AVE"),
    # NORTHWEST is one direction, not NORTH + WEST: Hoffman's Portland office, written both ways
    ("805 SOUTHWEST BROADWAY", "805 SW BROADWAY STE 2100"),
    ("6616 Northwest 32nd Street", "6616 NW 32ND ST"),
    # and once it's read as one, FREEWAY must be FWY: DPR's Houston office (both were 3200 WEST)
    ("3200 SOUTHWEST FREEWAY STE 1550", "3200 SOUTHWEST FWY STE 1550"),
    ("13939 NW FRWY", "13939 NW FREEWAY"),
    ("2515 NE EXPRESSWAY", "2515 NE EXPY"),
    # so is N or S then E or W, as OSHA's N.W. cleans to N W (all were <n> W or <n> WEST): offices written both ways
    ("6616 N.W. 32nd Street", "6616 NW 32ND ST"),
    ("805 S W BROADWAY", "805 SW BROADWAY STE 2100"),
    ("23000 NORTH WEST LAKE DR", "23000 NW LAKE DR"),
    ("700 N W 107TH AVE STE 400", "700 NW 107TH AVE"),                    # Lennar, Miami
    ("1978 S WEST TEMPLE", "1978 S W TEMPLE"), ("1978 S W TEMPLE", "1978 SW TEMPLE"),  # Okland, Salt Lake City
    # a street called East or West keys as its type, with the half of the street or without, as 525 WEST ST does
    ("833 South East Ave", "833 SE AVE"),                                 # Crossland, Columbus KS
    ("210 S E ST", "210 E ST"),                                           # Catalyst, Bloomington IL
    ("100 S WEST ST", "100 WEST ST"),
])
def test_addr_key_variants(con, a, b):
    assert q(con, "addr_key(?)", a) == q(con, "addr_key(?)", b)


@pytest.mark.parametrize("a,b", [
    ("100 WESTERN AVE", "100 EASTERN AVE"),     # ER: a street's own name, not a direction
    ("100 WESTON RD", "100 ON RD"),             # too short to split
    ("200 NORTHERN BLVD", "200 SOUTHERN BLVD"),
    ("805 SOUTHWEST BROADWAY", "805 NORTHWEST GLISAN ST"),       # both were 805 WEST
    ("11718 SOUTHEAST FEDERAL HWY", "11718 NORTHEAST 2ND AVE"),  # both were 11718 EAST
    # W or E then N or S isn't one direction: West South Temple and West North Temple are two streets
    ("15 W SOUTH TEMPLE", "15 W NORTH TEMPLE"), ("1902 E N 10TH ST", "1902 E S 10TH ST"),
])
def test_addr_key_keeps_street_names_apart(con, a, b):
    assert q(con, "addr_key(?)", a) != q(con, "addr_key(?)", b)


@pytest.mark.parametrize("address,key,side", [
    ("805 SOUTHWEST BROADWAY", "805 BROADWAY", {"S", "W"}), ("11718 SOUTHEAST FEDERAL HWY", "11718 FEDERAL", {"S", "E"}),
    ("7900 WESTPARK DR", "7900 PARK", {"W"}), ("31000 NORTHWESTERN HWY", "31000 WESTERN", {"N"}),
    ("525 WEST ST", "525 ST", {"W"}), ("100 WESTERN AVE", "100 WESTERN", set()),
    ("6616 N W 32ND ST", "6616 32ND", {"N", "W"}), ("23000 NORTH WEST LAKE DR", "23000 LAKE", {"N", "W"}),
    ("100 S WEST ST", "100 ST", {"S", "W"}), ("15 W SOUTH TEMPLE", "15 S", {"W"}), ("833 S E", "833 E", {"S"})])
def test_the_direction_addr_key_drops_is_the_side_street_side_reads(con, address, key, side):
    """ssi.matching.rules.street_side mirrors addr_key: what the key drops before the street word is the side."""
    from ssi.matching.rules import street_side
    assert (q(con, "addr_key(?)", address), street_side(address)) == (key, side)


def test_address_rules(con):
    assert q(con, "addr_key(?)", "3021 7th Ave South") == "3021 7TH"
    assert q(con, "addr_key(?)", "P.O. Box 1385") == "POBOX 1385"
    assert q(con, "addr_key(?)", "1201 Demonbreun St Ste 200") == "1201 DEMONBREUN"
    assert q(con, "addr_key(?)", "7900 Westpark Drive") == "7900 PARK"
    assert q(con, "addr_key(?)", "7900 WESTPARK DR") == "7900 PARK"
    assert q(con, "addr_key(?)", "805 SOUTHWEST BROADWAY") == "805 BROADWAY"
    assert q(con, "addr_key(?)", "6616 N.W. 32nd Street") == "6616 32ND"
    assert q(con, "addr_key(?)", "3810 West Broad Street Suite 103") == "3810 BROAD"
    # a profile's quote is checked for the key's words the same way (ssi/llm/profile.py)
    assert q(con, "addr_split_dir(clean_addr(?))", "McLean 7900 Westpark Drive Suite T300") == "MCLEAN 7900 WEST PARK DR STE T300"
    assert q(con, "addr_split_dir(clean_addr(?))", "805 Southwest Broadway") == "805 SW BROADWAY"
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


# --- properties over many spellings of one name ------------------------------------------------------------
# Names a GC might type, with no legal form of their own (one ends in initials, one is a person's name)
BASES = ["BRASFIELD & GORRIE", "Whiting-Turner Contracting", "Juan García Roofing", "J R Johnson", "84 Lumber",
         "Hoffman Construction Company of Oregon", "A-1 Roofing", "Muñoz & Sons Framing", "Smith-Jones Builders",
         "O'Brien Electric", "XYZ Holdings dba ABC Roofing", "Barnhart Crane & Rigging", "J & J Drywall"]
LEGAL_FORMS = [", Inc.", " Inc", " INCORPORATED", ", LLC", " L.L.C.", " L L C", " LLC.", " Co.", " Company", " Corp.",
               " Corporation", ", Ltd.", " Limited", " LP", " L.P.", " LLP", " LLLP", " PLLC", " P.L.L.C.", " PC",
               " L.C.", " LC", " PLC", " Limited Liability Company", " Co., Inc.", " Company, LLC", ", Inc., The",
               " Incorpora", " Corporatio", " LCC", " (Delaware)", " (TX)", ", LLC (Georgia)"]


@pytest.mark.parametrize("base", BASES)
def test_legal_forms_never_split_a_company(con, base):
    want = clean(con, base)
    got = {form: clean(con, base + form) for form in LEGAL_FORMS}
    assert {f: g for f, g in got.items() if g != want} == {}, want


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("prefix", ["WA317965935 - ", "317725037 - ", "136200 - ", "105314-", "NC105314 - ",
                                    "FCX2024XEG419X0079 - ", "A09CS000013UQXVAA4 - ", "The ", "THE "])
def test_inspection_ids_and_the_never_split_a_company(con, base, prefix):
    assert clean(con, prefix + base) == clean(con, base)


@pytest.mark.parametrize("base", BASES)
def test_case_accents_and_spacing_dont_matter(con, base):
    want = clean(con, base)
    folded = "".join(ch for ch in unicodedata.normalize("NFKD", base) if not unicodedata.combining(ch))
    for variant in (base.upper(), base.lower(), folded, "  " + base.replace(" ", "   ") + "\t", base.replace(" ", " ")):
        assert clean(con, variant) == want, variant


@pytest.mark.parametrize("letters", ["JR", "ABC", "HVAC", "VISEX", "ABCDEF", "ABCDEFGH"])
def test_initials_join_however_they_are_written(con, letters):
    # "A.B.C.D." always joined in n3; the spaced and ampersand forms must reach the same name at any length
    forms = [".".join(letters) + ". CONSTRUCTION", " ".join(letters) + " CONSTRUCTION",
             " & ".join(letters) + " CONSTRUCTION", "-".join(letters) + " CONSTRUCTION", letters + " CONSTRUCTION"]
    assert {clean(con, f) for f in forms} == {letters + " CONSTRUCTION"}


def test_initials_stay_apart_from_words(con):
    assert clean(con, "J SMITH CONSTRUCTION") == "J SMITH CONSTRUCTION"
    assert clean(con, "JOHN A B SMITH") == "JOHN AB SMITH"
    assert clean(con, "A PLUS ROOFING") == "A PLUS ROOFING"


@pytest.mark.parametrize("raw", [
    "", "&&&", "Ｆｕｌｌ ｗｉｄｔｈ", "ﬁﬂ", "Søren's Ø-Bygg", "BERM?DEZ", "BERM�DEZ", "A\u200bB", "　SMITH　",
    "émoji 🚧 builders", "Ελληνική Κατασκευή", "Строитель LLC", "中文建筑", "x" * 300, "A" + " B" * 40,
    "(((JV)))", "D/B/A", "- - -", "  THE  ", "LLC LLC LLC", "SMITH DBA DBA JONES", "12345-", "WA317965935 - ",
])
def test_output_is_upper_letters_digits_and_single_spaces(con, raw):
    out = clean(con, raw)
    assert out == "" or re.fullmatch(r"[A-Z0-9]+( [A-Z0-9]+)*", out), out


@pytest.mark.parametrize("raw", BASES + [b + f for b in BASES[:3] for f in LEGAL_FORMS[:8]] + [
    "136200 - The Brasfield & Gorrie, L.L.C. (Delaware)", "WA317955263 - ANDREWS GROUP THE LLC", "R G P INC",
    "AKA ELECTRIC, LLC", "CRAIG HANES, INC, DBA", "TOTAL ENERGY MANAGEMENT/H V A C SVCS INC", "ﬂoor ﬁnishers",
])
def test_steps_compose_to_clean_name_for_every_kind_of_name(con, raw):
    # the build's per-rule merge counts apply the steps one by one; they must add up to clean_name
    expr = "?"
    for step in NAME_STEPS:
        expr = f"{step}({expr})"
    assert q(con, f"trim(regexp_replace({expr}, '\\s+', ' ', 'g'))", raw) == clean(con, raw)


@pytest.mark.parametrize("raw", BASES + ["WA317955263 - ANDREWS GROUP THE LLC", "CRAIG HANES, INC, DBA",
                                         "65594 - CRAFTMASTERS LIMITED LIABILITY COMPANY", "R G P INC", "V I S E COMPANY"])
def test_cleaning_a_clean_name_changes_nothing(con, raw):
    once = clean(con, raw)
    assert clean(con, once) == once


def test_joint_ventures_stay_flagged(con):
    for raw in ("ABC CONSTRUCTION (JV)", "ABC CONSTRUCTION (J.V.)", "ABC CONSTRUCTION (J V)", "ABC-XYZ JV",
                "CLARK, SMOOT, CONSIGLI, A JOINT VENTURE", "TUTOR PERINI ZACHRY PARSONS JOINT VENTURE"):
        assert q(con, "is_jv(clean_name(?))", raw) is True, raw
    for raw in ("ABC CONSTRUCTION", "JV ELECTRIC"[3:], "JOVI CONSTRUCTION"):
        assert q(con, "is_jv(clean_name(?))", raw) is False, raw


def test_dba_markers(con):
    for marker in ("D/B/A", "d/b/a", "D.B.A.", "DBA", "D B A", "Doing Business As", "T/A", "Trading As", "A/K/A", "AKA",
                   "a.k.a."):
        c = clean(con, f"Smith Holdings, LLC {marker} Jones Roofing, Inc.")
        assert c == "SMITH HOLDINGS DBA JONES ROOFING", marker
        assert (q(con, "legal_part(?)", c), q(con, "dba_part(?)", c)) == ("SMITH HOLDINGS", "JONES ROOFING")
    # words that only contain the letters aren't markers
    assert clean(con, "DBAKER ROOFING") == "DBAKER ROOFING"
    assert clean(con, "TACO ROOFING") == "TACO ROOFING"
    assert clean(con, "ALASKA ROOFING") == "ALASKA ROOFING"


def test_name_core_never_keeps_a_generic_word(con):
    generic = set(q(con, "ssi_generic_tokens()"))
    for raw in BASES + list(EXACT) + [s for group in SAME for s in group]:
        core = q(con, "name_core(clean_name(?))", raw)
        assert not set(core.split()) & generic, (raw, core)
