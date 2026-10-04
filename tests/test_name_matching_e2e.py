"""Matching end to end on a tiny warehouse built from hand-written OSHA records by the pipeline's own SQL (see
mini_warehouse.py): the GC types a name, run.match cleans it, searches, corrects spelling, rates people's names,
expands by address and applies the rules. Each scenario is a trap from the real data, with the answer a GC needs:
someone else's records never counted, the company's own records never thrown away."""
import pytest

from ssi.matching import run
from ssi.store import warehouse
from tests.mini_warehouse import Rec, build

BG = "3021 7th Ave South"
RECS = [
    # Brasfield & Gorrie: one company under many spellings; Brasfield Construction is another company
    Rec("BRASFIELD & GORRIE, LLC", BG, "Birmingham", "AL", "35233", n=10),
    Rec("136200 - BRASFIELD - GORRIE, L.L.C.", BG, "Birmingham", "AL", "35233-1234"),
    Rec("Brasfield & Gorrie, L.L.C. (Delaware)", "1201 Demonbreun St Ste 200", "Nashville", "TN", "37203", n=2),
    Rec("BRASFIELD & GORIE GP", BG, "Birmingham", "AL", "35233"),
    Rec("BRASFIELD CONSTRUCTION, INC.", "400 Main St", "Nashville", "TN", "37201"),
    Rec("BG BUILDERS", "77 Oak St", "Birmingham", "AL", "35203"),
    # legal forms that used to stay on the name
    Rec("ADELPHI CONSTRUCTION, L.C.", "1 Grand Ave", "Des Moines", "IA", "50309"),
    Rec("ADELPHI CONSTRUCTION LLC", "9 Locust St", "Des Moines", "IA", "50309"),
    Rec("CRAFTMASTERS LIMITED LIABILITY COMPANY", "5 Elm St", "Hartford", "CT", "06103"),
    Rec("WA317981341 - CRAFTMASTERS INCORPORA", "8 Pearl St", "Hartford", "CT", "06103"),
    # A-1 / A1, a common name (27 names share the core A1)
    Rec("A-1 ROOFING, INC.", "10 Pine St", "Tulsa", "OK", "74103"),
    Rec("A1 ROOFING", "88 Birch Ave", "Tulsa", "OK", "74104"),
    Rec("A1 ROOFING", "4 Lake Rd", "Akron", "OH", "44308"),
    *[Rec(f"A1 {w}", f"{i} Main St", "Dallas", "TX", "75201") for i, w in enumerate((
        "PLUMBING", "ELECTRIC", "CONCRETE", "MASONRY", "PAINTING", "FRAMING", "DRYWALL", "SIDING", "HEATING", "EXCAVATING",
        "STEEL", "GLASS", "STUCCO", "PAVING", "INSULATION", "TILE", "FLOORING", "FENCE", "GUTTERS", "SPRINKLER",
        "DEMOLITION", "WELDING", "SOLAR", "LANDSCAPING", "CABINETS", "WINDOWS"))],
    # initials
    Rec("V I S E COMPANY", "12 Ash St", "Columbus", "OH", "43215"),
    Rec("V.I.S.E. CO.", "40 High St", "Columbus", "OH", "43215"),
    Rec("R G P INC", "3 Bay St", "Tampa", "FL", "33602"),
    Rec("R, INC.", "900 Gulf Blvd", "Tampa", "FL", "33606"),
    # a joint venture at a member's address
    Rec("SAVANNAH MOBILITY CONTRACTORS", "15 River St", "Savannah", "GA", "31401", n=2),
    Rec("SAVANNAH MOBILITY CONTRACTORS (J.V.)", "15 River St", "Savannah", "GA", "31401"),
    # regional companies filed under the sub's name plus a place word: at a division office, and at the head office,
    # which houses so many of the group's names that it counts as a shared office
    Rec("D.R. HORTON, INC.", "8001 Arrowridge Blvd", "Charlotte", "NC", "28273", n=2),
    Rec("D. R. HORTON, INC", "4008 Mendenhall Oaks Pkwy", "High Point", "NC", "27265", n=2),
    Rec("D.R. HORTON, INC. - GREENSBORO", "4008 Mendenhall Oaks Pkwy", "High Point", "NC", "27265"),
    Rec("D R HORTON INC PORTLAND", "4380 SW Macadam Ave", "Portland", "OR", "97239"),
    Rec("D.R. HORTON, INC.", "1341 Horton Cir", "Arlington", "TX", "76011", n=3),
    Rec("317729173 - D R HORTON INC PORTLAND", "1341 Horton Cir", "Arlington", "TX", "76011"),
    *[Rec(n, "1341 Horton Cir", "Arlington", "TX", "76011") for n in
      ("SSHI LLC", "PACIFIC RIDGE - DRH, LLC", "DHI COMMUNITIES", "LEXINGTON - DRH, LLC", "DHIC NONA WEST, LLC")],
    # a common name (CLARK) whose head office counts as shared, housing seven names, five of them its own companies:
    # its name without GROUP there is still its record. Its regional companies add a place to its name, and one of its
    # offices is written both WESTPARK and WEST PARK
    Rec("CLARK CONSTRUCTION GROUP, LLC", "7500 Old Georgetown Rd", "Bethesda", "MD", "20814", n=5),
    Rec("CLARK CONSTRUCTION", "7500 Old Georgetown Rd", "Bethesda", "MD", "20814"),
    *[Rec(n, "7500 Old Georgetown Rd", "Bethesda", "MD", "20814") for n in
      ("GUY F ATKINSON CONSTRUCTION", "CLARK FOUNDATIONS", "CLARK LEWIS A JV", "C3M POWER SYSTEMS", "S2N TECHNOLOGY",
       "CLARK SMOOT CONSIGLI JOINT VENTURE")],
    Rec("CLARK CONSTRUCTION SERVICES", "7500 Old Georgetown Rd", "Bethesda", "MD", "20814"),
    Rec("CLARK CONSTRUCTION GROUP - CALIFORNIA, LP", "180 Howard St Ste 1200", "San Francisco", "CA", "94105"),
    Rec("CLARK CONSTRUCTION GROUP - CHICAGO LLC", "216 S Jefferson St Ste 502", "Chicago", "IL", "60661"),
    Rec("CLARK CONSTRUCTION GROUP, LLC", "7900 Westpark Dr", "McLean", "VA", "22102"),
    Rec("CLARK CONSTRUCTION GROUP, LLC", "7900 West Park Dr", "McLean", "VA", "22102"),
    *[Rec(f"CLARK {w}", f"{i} Elm St", "Omaha", "NE", "68102") for i, w in enumerate((
        "PLUMBING", "ELECTRIC", "CONCRETE", "MASONRY", "PAINTING", "FRAMING", "DRYWALL", "SIDING", "HEATING", "EXCAVATING",
        "STEEL", "GLASS", "STUCCO", "PAVING", "INSULATION", "TILE", "FLOORING", "FENCE", "GUTTERS", "SPRINKLER",
        "DEMOLITION", "WELDING", "SOLAR", "LANDSCAPING", "CABINETS", "WINDOWS"))],
    # sister companies at one address: another trade word; and one name with a trade word added
    Rec("EENIGENBURG FRAMING", "2 Calumet Ave", "Dyer", "IN", "46311", n=2),
    Rec("EENIGENBURG ROOFING", "2 Calumet Ave", "Dyer", "IN", "46311"),
    Rec("KOVALENKO ROOFING", "6 Mill Rd", "Spokane", "WA", "99201"),
    Rec("KOVALENKO ROOFING & SIDING", "6 Mill Rd", "Spokane", "WA", "99201"),
    # people: the same name is usually many people
    Rec("ALEX PEREZ", "100 Bell St", "Houston", "TX", "77002", n=2),
    Rec("ALEX PEREZ", "5 Oak Dr", "Dallas", "TX", "75204"),
    Rec("ALEX PEREZ", "77 Camelback Rd", "Phoenix", "AZ", "85016"),
    Rec("ALEX PEREZ CONSTRUCTION", "8 Flagler St", "Miami", "FL", "33130"),
    Rec("J. LOPEZ", "4 Congress Ave", "Austin", "TX", "78701"),
    Rec("J LOPEZ", "50 Colfax Ave", "Denver", "CO", "80202"),
    Rec("MORALES, JAVIER M", "3 Mesa St", "El Paso", "TX", "79901"),
    Rec("MORALES JAVIER M", "60 Federal Blvd", "Denver", "CO", "80204"),
    Rec("JOSE HERNANDEZ", "200 Main St", "Houston", "TX", "77002", n=2),
    Rec("JOSE HERNANDEZ", "12 Elm St", "Dallas", "TX", "75201"),
    Rec("JOSE HERNANDEZ", "1 Peachtree St", "Atlanta", "GA", "30303", red_flag=True),
    Rec("JOSE FERNANDEZ", "9 Westheimer Rd", "Houston", "TX", "77006"),
    Rec("MARIO CONTRERAS", "44 Palafox St", "Pensacola", "FL", "32502", n=2),
    Rec("MAURICIO CONTRERAS", "44 Palafox St", "Pensacola", "FL", "32502"),
    Rec("SERGIO CAZARES", "71 Telephone Rd", "Houston", "TX", "77023", n=2),
    Rec("SERGIO CAZARES SR", "71 Telephone Rd", "Houston", "TX", "77023"),
    Rec("ISMAEL FLORES", "8 Granby St", "Norfolk", "VA", "23510", n=2),
    Rec("ISHMAEL FLORES", "8 Granby St", "Norfolk", "VA", "23510"),
    # a company named after a person: its other office isn't another person, but a bare name still is
    Rec("THE FRED CHRISTEN & SONS COMPANY", "714 George St", "Toledo", "OH", "43604", n=2),
    Rec("FRED CHRISTEN & SONS CO", "15847 Glendale St", "Detroit", "MI", "48227"),
    Rec("FRED CHRISTEN", "3 Capitol Ave", "Lansing", "MI", "48933"),
    # ... or with only a legal form to say so, which cleaning drops
    Rec("ROBERT J. DEVEREAUX CORP.", "17 Pleasant St", "Malden", "MA", "02148", n=2),
    Rec("ROBERT J DEVEREAUX CORP", "10 Emerson Pl", "Boston", "MA", "02114"),
    Rec("ROBERT J DEVEREAUX", "5 Main St", "Worcester", "MA", "01608"),
    # place names that end in a given name are companies, not people
    Rec("SAN ANTONIO ROOFING", "300 Alamo Plz", "San Antonio", "TX", "78205"),
    Rec("SAN ANTONIO ROOFING", "14 River Rd", "Boerne", "TX", "78006"),
    # a sub entered with its DBA, a generic trade name
    Rec("QORVANEX HOLDINGS LLC DBA QUALITY ROOFING", "500 Church St", "Nashville", "TN", "37219"),
    Rec("QUALITY ROOFING", "500 Church St", "Nashville", "TN", "37219"),
    Rec("QUALITY ROOFING", "7 Main St", "Greeley", "CO", "80631"),
    # the red-flag safety net: other names at the company's own address
    Rec("BARNHART CRANE & RIGGING CO", "2163 Airways Blvd", "Memphis", "TN", "38114", n=3),
    Rec("MIDSOUTH LIFTING SERVICES", "2163 Airways Blvd", "Memphis", "TN", "38114", red_flag=True),
    Rec("DELTA HAULING", "2163 Airways Blvd", "Memphis", "TN", "38114"),
    # a registered agent's office (7 companies) never pulls records together
    *[Rec(f"{w} HOLDINGS LLC", "1209 Orange St", "Wilmington", "DE", "19801") for w in
      ("ZEPHYR", "ACORN", "BIRCHWOOD", "CEDARLINE", "DUNMORE", "ELKHORN", "FALCONER")],
    Rec("ZEPHYR BUILDERS", "1209 Orange St", "Wilmington", "DE", "19801"),
    Rec("ZEPHIR BUILDERS", "1209 Orange St", "Wilmington", "DE", "19801"),
    # the same name in another state (M3): a collision under another trade, and a real branch under the same one
    Rec("QUINN CONSTRUCTION INC", "1 Industrial Hwy", "Essington", "PA", "19029", n=2, naics="236220"),
    Rec("QUINN CONSTRUCTION", "300 Main St", "Parsons", "TN", "38363", naics="238910"),
    Rec("HELIX ELECTRIC INC", "6 Harbor Way", "Oakland", "CA", "94607", n=2, naics="238210"),
    Rec("HELIX ELECTRIC", "9 Wellington Rd", "Manassas", "VA", "20109", naics="238210"),
]


@pytest.fixture(scope="module", autouse=True)
def mini(tmp_path_factory):
    path = tmp_path_factory.mktemp("mini") / "warehouse.duckdb"
    build(path, RECS)
    saved = warehouse._con, warehouse._path, warehouse._meta
    warehouse._con = None
    warehouse.open_warehouse(path)
    yield
    warehouse._con.close()
    warehouse._con, warehouse._path, warehouse._meta = saved


def decisions(name, city, state, trade=None):
    """[(clean name, city, state, bucket, rule)] for every record the matcher kept, and the query and note."""
    res = run.match(name, city, state, trade)
    rows = sorted((x["row"]["clean_name"], x["row"]["city"], x["row"]["state"], x["decision"].bucket, x["decision"].rule_id)
                  for x in res["decisions"])
    return rows, res["query"], res["note"]


def outcome(name, city, state, trade=None):
    """{(clean name, city, state): (bucket, rule)}, for scenarios with one record per name and city."""
    rows, q, note = decisions(name, city, state, trade)
    got = {(n, c, st): (b, r) for n, c, st, b, r in rows}
    assert len(got) == len(rows), "two records share a name and city: use decisions()"
    return got, q, note


def buckets(got, bucket):
    return {k for k, (b, _) in got.items() if b == bucket}


# --- companies --------------------------------------------------------------------------------------------
def test_one_company_under_many_spellings():
    got, q, note = outcome("Brasfield & Gorrie", "Birmingham", "AL")
    assert q.clean == "BRASFIELD GORRIE" and note is None
    assert buckets(got, "matched") == {("BRASFIELD GORRIE", "BIRMINGHAM", "AL"), ("BRASFIELD GORRIE", "NASHVILLE", "TN"),
                                       ("BRASFIELD GORIE", "BIRMINGHAM", "AL")}  # the slip, at the company's address
    assert got[("BRASFIELD GORIE", "BIRMINGHAM", "AL")][1] == "M2"
    assert got[("BRASFIELD CONSTRUCTION", "NASHVILLE", "TN")] == ("excluded", "X1")  # Brasfield Construction is another company


def test_a_gcs_slip_is_searched_by_oshas_spelling_and_keeps_the_dba():
    # the DBA used to be dropped from the sub's names once its spelling was corrected, so the record under the
    # DBA (BG BUILDERS) was judged against BRASFIELD GORRIE and excluded
    got, q, note = outcome("Brasfeild & Gorrie LLC dba BG Builders", "Birmingham", "AL")
    assert "BRASFIELD GORRIE" in note and q.core == "BRASFIELD GORRIE"
    assert q.clean == "BRASFIELD GORRIE DBA BG BUILDERS"
    assert {"BG BUILDERS", "BRASFIELD GORRIE", "BRASFEILD GORRIE DBA BG BUILDERS"} <= q.aliases
    assert got[("BG BUILDERS", "BIRMINGHAM", "AL")] == ("matched", "M1")
    assert got[("BRASFIELD GORRIE", "BIRMINGHAM", "AL")][0] == "matched"


def test_legal_forms_left_on_a_name_dont_split_or_exclude_it():
    # "ADELPHI CONSTRUCTION, L.C." was excluded as a different name (LC); CRAFTMASTERS had two names
    rows, _, _ = decisions("Adelphi Construction", "Des Moines", "IA")
    assert rows == [("ADELPHI CONSTRUCTION", "DES MOINES", "IA", "matched", "M1")] * 2
    rows, q, _ = decisions("Craftmasters LLC", "Hartford", "CT")
    assert q.clean == "CRAFTMASTERS" and rows == [("CRAFTMASTERS", "HARTFORD", "CT", "matched", "M1")] * 2


def test_a_common_name_written_two_ways_is_one_name_but_still_needs_the_city():
    # A-1 ROOFING was "A 1 ROOFING": the GC's "A-1 Roofing" never found A1 ROOFING at all
    rows, q, _ = decisions("A-1 Roofing", "Tulsa", "OK")
    assert q.clean == "A1 ROOFING" and q.tier == "generic"
    assert [r for r in rows if r[3] == "matched"] == [("A1 ROOFING", "TULSA", "OK", "matched", "M1")] * 2
    assert [r[3] for r in rows if r[:3] == ("A1 ROOFING", "AKRON", "OH")] == ["uncertain"]  # a common name, another state
    assert {r[3] for r in rows if r[0] != "A1 ROOFING"} == {"excluded"}  # A1 PLUMBING, A1 ELECTRIC...


def test_initials_written_with_dots_or_spaces_are_one_company():
    rows, q, _ = decisions("Vise Company", "Columbus", "OH")
    assert q.clean == "VISE" and rows == [("VISE", "COLUMBUS", "OH", "matched", "M1")] * 2


def test_initials_that_look_like_a_legal_form_stay_a_name():
    # "R G P INC" was cleaned to "R", the name of every "R, INC." in the country
    got, q, _ = outcome("RGP Inc", "Tampa", "FL")
    assert q.clean == "RGP"
    assert got == {("RGP", "TAMPA", "FL"): ("matched", "M1")}


def test_a_joint_venture_is_never_merged_into_its_member():
    got, _, _ = outcome("Savannah Mobility Contractors", "Savannah", "GA")
    assert got[("SAVANNAH MOBILITY CONTRACTORS", "SAVANNAH", "GA")] == ("matched", "M1")
    assert got[("SAVANNAH MOBILITY CONTRACTORS JV", "SAVANNAH", "GA")] == ("uncertain", "J1")


def test_a_sister_company_at_the_same_address_is_a_question_not_a_match():
    got, _, _ = outcome("Eenigenburg Framing", "Dyer", "IN")
    assert got[("EENIGENBURG ROOFING", "DYER", "IN")] == ("uncertain", "U3")
    # a trade word added to the same name, at the same address, is the same company
    got, _, _ = outcome("Kovalenko Roofing", "Spokane", "WA")
    assert got[("KOVALENKO ROOFING SIDING", "SPOKANE", "WA")] == ("matched", "M2")


def test_the_subs_name_plus_a_place_at_its_own_address_is_a_question():
    got, _, _ = outcome("D.R. Horton", "Charlotte", "NC")
    assert got[("DR HORTON", "HIGH POINT", "NC")] == ("matched", "M1")
    assert got[("DR HORTON INC GREENSBORO", "HIGH POINT", "NC")] == ("uncertain", "S3")
    # the head office is a shared office: it pulls in the sub's name plus a word, as a question, and nothing else
    assert got[("DR HORTON", "ARLINGTON", "TX")] == ("matched", "M3")
    assert got[("DR HORTON INC PORTLAND", "ARLINGTON", "TX")] == ("uncertain", "S3")
    assert not {n for n, c, _ in got if c == "ARLINGTON"} - {"DR HORTON", "DR HORTON INC PORTLAND"}
    # the same name away from any address the sub uses: nothing ties it to the sub
    assert got[("DR HORTON INC PORTLAND", "PORTLAND", "OR")] == ("excluded", "X1")


def test_a_common_names_own_records_at_its_shared_head_office_and_its_regional_companies():
    rows, q, _ = decisions("Clark Construction Group", "Bethesda", "MD")
    assert q.tier == "generic"
    got = {(n, c): (b, r) for n, c, _, b, r in rows}
    # the head office is shared (seven names), but the sub's name without GROUP there is its record (M2)...
    assert warehouse.one("SELECT is_shared_office FROM entity.address_stats WHERE addr_key = '7500 OLD'")["is_shared_office"]
    assert got[("CLARK CONSTRUCTION GROUP", "BETHESDA")] == ("matched", "M1")
    assert got[("CLARK CONSTRUCTION", "BETHESDA")] == ("matched", "M2")
    # ...not one with a word swapped (SERVICES for GROUP), nor the other companies there
    assert got.get(("CLARK CONSTRUCTION SERVICES", "BETHESDA"), ("",))[0] != "matched"
    assert not {n for n, c in got if c == "BETHESDA"} & {"GUY F ATKINSON CONSTRUCTION", "C3M POWER SYSTEMS", "S2N TECHNOLOGY"}
    # its regional companies (the name plus a state or the record's own city) are questions, not other companies
    assert got[("CLARK CONSTRUCTION GROUP CALIFORNIA", "SAN FRANCISCO")] == ("uncertain", "S4")
    assert got[("CLARK CONSTRUCTION GROUP CHICAGO", "CHICAGO")] == ("uncertain", "S4")
    # 7900 WESTPARK DR and 7900 WEST PARK DR are one record
    mclean = [r for r in rows if r[1] == "MCLEAN"]
    assert len(mclean) == 1 and mclean[0][3] == "uncertain"
    assert warehouse.one("SELECT insp_n FROM entity.establishment WHERE clean_name = 'CLARK CONSTRUCTION GROUP' "
                         "AND city = 'MCLEAN'")["insp_n"] == 2


def test_a_dba_trade_name_is_judged_as_the_common_name_it_is():
    got, _, _ = outcome("Qorvanex Holdings LLC dba Quality Roofing", "Nashville", "TN")
    assert got[("QORVANEX HOLDINGS DBA QUALITY ROOFING", "NASHVILLE", "TN")][0] == "matched"
    assert got[("QUALITY ROOFING", "NASHVILLE", "TN")][0] == "matched"
    assert got[("QUALITY ROOFING", "GREELEY", "CO")] == ("uncertain", "U4")


def test_red_flags_at_the_companys_address_reach_the_gc():
    got, _, _ = outcome("Barnhart Crane & Rigging", "Memphis", "TN")
    assert got[("MIDSOUTH LIFTING SERVICES", "MEMPHIS", "TN")] == ("uncertain", "R1")
    assert ("DELTA HAULING", "MEMPHIS", "TN") not in got  # another name, no red flag: not this company's record


def test_a_registered_agents_office_pulls_nothing_in():
    got, _, _ = outcome("Zephyr Builders", "Wilmington", "DE")
    assert buckets(got, "matched") == {("ZEPHYR BUILDERS", "WILMINGTON", "DE")}
    assert all(n.startswith("ZEPH") for n, _, _ in got)  # ACORN HOLDINGS etc. at the same office: never candidates


def test_a_placeholder_matches_nothing():
    got, _, note = outcome("Unknown", "Houston", "TX")
    assert got == {} and note == "Name is empty or a placeholder"


# --- people -----------------------------------------------------------------------------------------------
def test_a_person_is_matched_by_city_never_by_name_alone():
    # ALEX was missing from the given names: ALEX PEREZ was rated a distinctive company and matched in 4 cities
    got, q, _ = outcome("Alex Perez", "Houston", "TX")
    assert q.tier == "person"
    assert buckets(got, "matched") == {("ALEX PEREZ", "HOUSTON", "TX")}
    assert {k: r for k, (b, r) in got.items() if b != "matched"} == {
        ("ALEX PEREZ", "DALLAS", "TX"): "X5", ("ALEX PEREZ", "PHOENIX", "AZ"): "X5",
        ("ALEX PEREZ CONSTRUCTION", "MIAMI", "FL"): "X5"}


@pytest.mark.parametrize("typed,city,state,home", [
    ("J. Lopez", "Austin", "TX", ("J LOPEZ", "AUSTIN", "TX")),  # an initial and a surname
    ("Morales, Javier M.", "El Paso", "TX", ("MORALES JAVIER M", "EL PASO", "TX")),  # surname first, middle initial
])
def test_other_ways_of_writing_a_persons_name(typed, city, state, home):
    got, q, _ = outcome(typed, city, state)
    assert q.tier == "person"
    assert buckets(got, "matched") == {home}
    assert all(r == "X5" for k, (b, r) in got.items() if k != home)


def test_a_company_named_after_a_person_keeps_its_other_offices():
    # the rules eval: X5 excluded such a company's own records in another city all 24 times it was checked
    got, q, _ = outcome("The Fred Christen & Sons Company", "Toledo", "OH")
    assert q.tier == "person" and q.clean == "FRED CHRISTEN SONS"
    assert got[("FRED CHRISTEN SONS", "TOLEDO", "OH")] == ("matched", "M1")
    assert got[("FRED CHRISTEN SONS", "DETROIT", "MI")] == ("uncertain", "P3")
    assert got[("FRED CHRISTEN", "LANSING", "MI")] == ("excluded", "X5")


def test_a_legal_form_typed_and_on_the_record_makes_a_persons_name_a_company():
    got, q, _ = outcome("Robert J. Devereaux Corp.", "Malden", "MA")
    assert q.tier == "person" and q.incorporated
    assert got[("ROBERT J DEVEREAUX", "MALDEN", "MA")] == ("matched", "M1")
    assert got[("ROBERT J DEVEREAUX", "BOSTON", "MA")] == ("uncertain", "P3")
    assert got[("ROBERT J DEVEREAUX", "WORCESTER", "MA")] == ("excluded", "X5")  # no legal form on that record
    # typed without one, nothing says it's a company: as before
    got, q, _ = outcome("Robert J Devereaux", "Malden", "MA")
    assert not q.incorporated and got[("ROBERT J DEVEREAUX", "BOSTON", "MA")] == ("excluded", "X5")


def test_with_legal_form_uses_the_cleaning_steps():
    from ssi.matching.candidates import with_legal_form
    assert with_legal_form(["ROBERT J. DEVEREAUX CORP.", "Jose Hernandez LLC", "CRAIG HANES, INC, DBA",
                            "ANDREWS GROUP THE LLC", "SMITH THE", "JOSE HERNANDEZ", "J L P CONSTRUCTION", ""]) == {
        "ROBERT J. DEVEREAUX CORP.", "Jose Hernandez LLC", "CRAIG HANES, INC, DBA", "ANDREWS GROUP THE LLC"}


def test_jose_hernandez_in_three_places():
    # typed with accents; the Atlanta record has a red flag, and must not be pinned on the Houston sub
    got, q, _ = outcome("José Hernández", "Houston", "TX")
    assert q.clean == "JOSE HERNANDEZ" and q.tier == "person"
    assert got[("JOSE HERNANDEZ", "HOUSTON", "TX")] == ("matched", "M1")
    assert got[("JOSE HERNANDEZ", "DALLAS", "TX")] == ("excluded", "X5")
    assert got[("JOSE HERNANDEZ", "ATLANTA", "GA")] == ("excluded", "X5")
    # a name a letter away is another family name, not a slip: never matched without an address
    assert got[("JOSE FERNANDEZ", "HOUSTON", "TX")][0] != "matched"


def test_without_a_city_a_persons_name_is_a_question():
    got, _, _ = outcome("Jose Hernandez", None, "TX")
    assert {k: v for k, v in got.items() if k[2] == "TX" and k[0] == "JOSE HERNANDEZ"} == {
        ("JOSE HERNANDEZ", "HOUSTON", "TX"): ("uncertain", "P1"), ("JOSE HERNANDEZ", "DALLAS", "TX"): ("uncertain", "P1")}
    assert got[("JOSE HERNANDEZ", "ATLANTA", "GA")] == ("excluded", "X5")  # another state needs no city to tell
    assert got[("JOSE FERNANDEZ", "HOUSTON", "TX")][0] != "matched"


def test_another_person_at_the_same_address_is_a_question_not_a_match():
    # M2 matched any name within a Jaro-Winkler of 0.93 at the address: MARIO / MAURICIO, a father and son
    got, _, _ = outcome("Mario Contreras", "Pensacola", "FL")
    assert got[("MAURICIO CONTRERAS", "PENSACOLA", "FL")] == ("uncertain", "P2")
    got, _, _ = outcome("Sergio Cazares", "Houston", "TX")
    assert got[("SERGIO CAZARES SR", "HOUSTON", "TX")] == ("uncertain", "P2")
    # the same person spelt another way at the address is still matched
    got, _, _ = outcome("Ismael Flores", "Norfolk", "VA")
    assert got[("ISHMAEL FLORES", "NORFOLK", "VA")] == ("matched", "M2")


def test_a_company_named_after_a_city_is_not_a_person():
    # SAN ANTONIO was a person's name (ANTONIO), so the Boerne office was excluded as "a person in another city"
    got, q, _ = outcome("San Antonio Roofing", "San Antonio", "TX")
    assert q.tier != "person"
    assert buckets(got, "matched") == {("SAN ANTONIO ROOFING", "SAN ANTONIO", "TX"), ("SAN ANTONIO ROOFING", "BOERNE", "TX")}


# --- the same name in another state (M3) ------------------------------------------------------------------
def test_a_colliding_name_under_another_trade_in_another_state_is_left_for_the_adjudicator():
    # Quinn Construction of Essington PA (general building) and of Parsons TN (another trade): two companies
    got, _, _ = outcome("Quinn Construction Inc", "Essington", "PA")
    assert got[("QUINN CONSTRUCTION", "ESSINGTON", "PA")] == ("matched", "M1")
    assert got[("QUINN CONSTRUCTION", "PARSONS", "TN")] == ("uncertain", "M3u")


def test_a_branch_under_the_same_trade_in_another_state_stays_matched():
    got, _, _ = outcome("Helix Electric", "Oakland", "CA")
    assert got[("HELIX ELECTRIC", "MANASSAS", "VA")] == ("matched", "M3")


def test_without_a_record_in_the_subs_state_the_guard_has_no_trade_to_compare():
    got, _, _ = outcome("Quinn Construction", "Columbus", "OH")
    assert {k: v for k, v in got.items() if k[0] == "QUINN CONSTRUCTION"} == {
        ("QUINN CONSTRUCTION", "ESSINGTON", "PA"): ("matched", "M3"), ("QUINN CONSTRUCTION", "PARSONS", "TN"): ("matched", "M3")}
