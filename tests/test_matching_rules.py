"""Matching rules on synthetic candidates: every trap from the profile and the evaluation."""
import pytest

from ssi.matching import rules
from ssi.matching.rules import EXCLUDED, MATCHED, UNCERTAIN, Candidate, Query, decide

GENERIC = frozenset({"CONSTRUCTION", "CONTRACTING", "CONTRACTORS", "CONTRACTOR", "GENERAL", "ROOFING", "GROUP",
                     "CONCRETE", "ELECTRIC", "HOMES", "TILE", "MASONRY", "OF", "AT", "COMPANY"})
DESCRIPTORS = frozenset({"CONSTRUCTION", "CONTRACTING", "CONTRACTORS", "CONTRACTOR", "GENERAL", "GROUP", "OF", "AT", "COMPANY"})


def q(clean, core, state="AL", tier="distinctive", city=None, trade=None, initials=False, sibling=None):
    return Query(clean=clean, core=core, state=state, city=city, trade=trade, tier=tier,
                 initials_only=initials, sibling=sibling)


def c(clean, core, state="AL", city=None, naics4=None, sibling=None, initials=False, at_addr=False):
    return Candidate(establishment_key="k", clean_name=clean, name_core=core, legal_name=clean, dba_name=None,
                     state=state, city=city, zip5=None, addr_key=None, primary_naics4=naics4,
                     sibling_suffix=sibling, initials_only=initials, at_matched_address=at_addr)


BG = q("BRASFIELD GORRIE", "BRASFIELD GORRIE")


def test_same_distinctive_name_same_state_matches():
    assert decide(BG, c("BRASFIELD GORRIE", "BRASFIELD GORRIE"), GENERIC).bucket == MATCHED


def test_generic_word_difference_matches_for_distinctive_core():
    rules.DESCRIPTORS = DESCRIPTORS
    d = decide(BG, c("BRASFIELD GORRIE GENERAL CONTRACTOR", "BRASFIELD GORRIE"), GENERIC)
    assert (d.bucket, d.rule_id) == (MATCHED, "M1b")


def test_other_state_distinctive_matches_as_multistate():
    d = decide(BG, c("BRASFIELD GORRIE", "BRASFIELD GORRIE", state="GA"), GENERIC)
    assert (d.bucket, d.rule_id) == (MATCHED, "M3")


def test_lookalike_excluded():
    d = decide(BG, c("BRASFIELD CONSTRUCTION", "BRASFIELD", state="TN"), GENERIC)
    assert d.bucket == EXCLUDED


def test_typo_at_matched_address_matches():
    d = decide(BG, c("BRASFIELD GORIE", "BRASFIELD GORIE", at_addr=True), GENERIC)
    assert (d.bucket, d.rule_id) == (MATCHED, "M2")


def test_typo_elsewhere_is_uncertain_not_excluded():
    d = decide(BG, c("BRASFIEL GORRIE", "BRASFIEL GORRIE", state="GA"), GENERIC)
    assert d.bucket == UNCERTAIN


def test_generic_name_same_state_needs_city():
    abc = q("ABC ROOFING", "ABC", state="TX", tier="generic", city="DALLAS")
    assert decide(abc, c("ABC ROOFING", "ABC", state="TX", city="DALLAS"), GENERIC).bucket == MATCHED
    assert decide(abc, c("ABC ROOFING", "ABC", state="TX", city="HOUSTON"), GENERIC).bucket == UNCERTAIN
    assert decide(abc, c("ABC ROOFING", "ABC", state="OK", city="TULSA"), GENERIC).bucket == UNCERTAIN


def test_related_entities_with_generic_core():
    clark = q("CLARK CONSTRUCTION GROUP", "CLARK", state="MD", tier="generic", city="BETHESDA")
    # same city: possibly a sister company -> uncertain
    assert decide(clark, c("CLARK CONCRETE CONTRACTORS", "CLARK", state="MD", city="BETHESDA"), GENERIC).bucket == UNCERTAIN
    # a different Clark elsewhere is just another company with a common name
    assert decide(clark, c("CLARK ROOFING", "CLARK", state="OH", city="AKRON"), GENERIC).bucket == EXCLUDED
    # same full name in another state stays uncertain (national firms)
    assert decide(clark, c("CLARK CONSTRUCTION GROUP", "CLARK", state="VA", city="ARLINGTON"), GENERIC).bucket == UNCERTAIN


def test_initials_names():
    ca = q("CA CONSTRUCTION", "CA", state="TX", tier="generic", initials=True)
    assert decide(ca, c("CS CONSTRUCTION", "CS", state="TX", initials=True), GENERIC).bucket == EXCLUDED
    assert decide(ca, c("CA CONSTRUCTION", "CA", state="TX", city="WACO", initials=True), GENERIC).bucket == UNCERTAIN


def test_sibling_suffix_uncertain():
    h = q("HOFFMAN CONSTRUCTION COMPANY OF AMERICA", "HOFFMAN AMERICA", state="OR", sibling=" OF AMERICA")
    d = decide(h, c("HOFFMAN CONSTRUCTION COMPANY OF OREGON", "HOFFMAN OREGON", state="OR", sibling=" OF OREGON"), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "S1")


def test_sibling_suffix_against_the_plain_name_is_uncertain_not_excluded():
    # the place word stays in the core (HOFFMAN OREGON), so the cores are compared without it; this was X1
    hoffman = q("HOFFMAN CONSTRUCTION", "HOFFMAN", state="OR", tier="medium", city="PORTLAND")
    d = decide(hoffman, c("HOFFMAN CONSTRUCTION CO OF OREGON", "HOFFMAN OREGON", state="OR", city="PORTLAND",
                          sibling=" OF OREGON"), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "S1")
    pulte = q("PULTE HOMES", "PULTE", state="GA", tier="medium", city="ATLANTA")
    d = decide(pulte, c("PULTE HOMES OF MINNESOTA", "PULTE MINNESOTA", state="MN", sibling=" OF MINNESOTA"), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "S1")
    # another name with the same suffix is still another company
    d = decide(hoffman, c("SMITH CONSTRUCTION OF OREGON", "SMITH OREGON", state="OR", sibling=" OF OREGON"), GENERIC)
    assert (d.bucket, d.rule_id) == (EXCLUDED, "X1")
    # a common name with a place suffix in another state is another company, as the plain name would be
    abc = q("ABC ROOFING", "ABC", state="TX", tier="generic", city="DALLAS")
    d = decide(abc, c("ABC ROOFING OF OKLAHOMA", "ABC OKLAHOMA", state="OK", sibling=" OF OKLAHOMA"), GENERIC)
    assert d.bucket == EXCLUDED
    d = decide(abc, c("ABC ROOFING OF TEXAS", "ABC TEXAS", state="TX", city="HOUSTON", sibling=" OF TEXAS"), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "S1")


def test_a_generic_dba_is_judged_as_its_own_name():
    # "Qorvanex Holdings LLC dba Quality Roofing": the legal name is distinctive, the DBA isn't. A record named only
    # QUALITY ROOFING used to borrow the legal name's rarity and auto-match in 11 states
    full = q("QORVANEX HOLDINGS DBA QUALITY ROOFING", "QORVANEX", state="TN", city="NASHVILLE")
    full.aliases = {full.clean, "QORVANEX HOLDINGS", "QUALITY ROOFING"}
    full.alias_queries = {"QORVANEX HOLDINGS": q("QORVANEX HOLDINGS", "QORVANEX", state="TN", city="NASHVILLE"),
                          "QUALITY ROOFING": q("QUALITY ROOFING", "", state="TN", tier="generic", city="NASHVILLE")}
    d = decide(full, c("QUALITY ROOFING", "", state="CO", city="GREELEY"), GENERIC)
    assert (d.bucket, d.rule_id) == (EXCLUDED, "X4")
    d = decide(full, c("QUALITY ROOFING", "", state="TN", city="NASHVILLE"), GENERIC)
    assert (d.bucket, d.rule_id) == (MATCHED, "M1")
    assert decide(full, c("QUALITY ROOFING", "", state="TN", city="KNOXVILLE"), GENERIC).bucket == UNCERTAIN
    # the legal name is still distinctive, in any state
    d = decide(full, c("QORVANEX HOLDINGS", "QORVANEX", state="GA"), GENERIC)
    assert (d.bucket, d.rule_id) == (MATCHED, "M3")


def test_trade_conflict_demotes():
    bg = q("ACME", "ACME", state="AL", trade="electrical")
    d = decide(bg, c("ACME", "ACME", naics4="2381"), GENERIC)
    assert d.bucket == UNCERTAIN and d.rule_id.endswith("_trade")


def test_trade_word_difference_is_a_sister_company():
    rules.DESCRIPTORS = DESCRIPTORS
    w = q("WAUSAU HOMES", "WAUSAU", state="WI")
    assert decide(w, c("WAUSAU TILE", "WAUSAU", state="WI"), GENERIC).bucket == UNCERTAIN
    t = q("TURNKEY CONSTRUCTION", "TURNKEY", state="PA")
    assert decide(t, c("TURNKEY ELECTRIC", "TURNKEY", state="PA", at_addr=True), GENERIC).bucket == UNCERTAIN


def test_all_generic_name_in_another_state_is_excluded():
    qr = q("QUALITY ROOFING", "", state="TN", tier="generic", city="NASHVILLE")
    assert decide(qr, c("QUALITY ROOFING", "", state="OH", city="AKRON"), GENERIC).bucket == EXCLUDED
    assert decide(qr, c("QUALITY ROOFING", "", state="TN", city="KNOXVILLE"), GENERIC).bucket == UNCERTAIN
    assert decide(qr, c("QUALITY ROOFING", "", state="TN", city="NASHVILLE"), GENERIC).bucket == MATCHED


def test_city_spelling_variants_match():
    from ssi.matching.rules import norm_city
    assert norm_city("LaFollette") == norm_city("LA FOLLETTE")
    assert norm_city("St. Louis") == norm_city("SAINT LOUIS")
    assert norm_city("Fort Worth") == norm_city("FT WORTH")
    assert norm_city("San José") == norm_city("SAN JOSE")
    assert norm_city("Peñasco") == norm_city("PENASCO")
    d = q("DIXIE ROOFING", "DIXIE", state="TN", tier="medium", city="LaFollette")
    assert decide(d, c("DIXIE ROOFING", "DIXIE", state="TN", city="LA FOLLETTE"), GENERIC).bucket == MATCHED


# --- people's names (sole proprietors): the same name is usually many different people ---------------
JUAN = q("JUAN GARCIA", "JUAN GARCIA", state="TX", tier="person")


def test_person_name_in_another_state_is_excluded():
    d = decide(JUAN, c("JUAN GARCIA", "JUAN GARCIA", state="MA"), GENERIC)
    assert (d.bucket, d.rule_id) == (EXCLUDED, "X5")


def test_person_name_needs_a_place_to_match():
    # no city given: same name in the same state is unsure, never an automatic match
    assert decide(JUAN, c("JUAN GARCIA", "JUAN GARCIA", state="TX", city="HOUSTON"), GENERIC).rule_id == "P1"
    houston = q("JUAN GARCIA", "JUAN GARCIA", state="TX", tier="person", city="Houston")
    assert decide(houston, c("JUAN GARCIA", "JUAN GARCIA", state="TX", city="HOUSTON"), GENERIC).bucket == MATCHED
    assert decide(houston, c("JUAN GARCIA ROOFING", "JUAN GARCIA", state="TX", city="DALLAS"), GENERIC).rule_id == "X5"


def test_person_name_at_a_matched_address_still_matches():
    d = decide(JUAN, c("JUAN GARCIA", "JUAN GARCIA", state="TX", at_addr=True), GENERIC)
    assert d.bucket == MATCHED and d.rule_id == "M2"
    # a trade word added at the same address is unsure (as for companies), so the reviewer decides
    assert decide(JUAN, c("JUAN GARCIA ROOFING", "JUAN GARCIA", state="TX", at_addr=True), GENERIC).bucket == UNCERTAIN


def test_branch_or_division_is_never_a_different_company():
    barnhart = q("BARNHART CRANE RIGGING", "BARNHART CRANE RIGGING", state="TN")
    d = decide(barnhart, c("BARNHART CRANE RIGGING OKLAHOMA CITY BRANCH", "BARNHART CRANE RIGGING OKLAHOMA CITY BRANCH",
                           state="TN"), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "S2")


# --- spelling correction: only a clearly dominant spelling, never a different small company ---------
def _row(core, insp, clean=None, city=None, state=None):
    return {"name_core": core, "clean_name": clean or core, "insp_n": insp, "sim": 0.95, "initials_only": False,
            "sibling_suffix": None, "city": city, "state": state}


def test_spelling_correction_needs_a_clearly_dominant_spelling(monkeypatch):
    from ssi.matching import candidates, run
    monkeypatch.setattr(candidates, "core_tier", lambda core, initials: "distinctive")
    colmex = q("COLMEX CONTRACTING", "COLMEX", state="FL")
    q2, note = run.correct_spelling(colmex, [_row("COLMEX", 1, "COLMEX CONTRACTING"), _row("COMEX", 5, "COMEX CONSTRUCTION")])
    assert note is None and q2.core == "COLMEX"  # Comex (5 inspections) is another company, not a typo fix
    slip = q("BRASFEILD GORRIE", "BRASFEILD GORRIE")
    q3, note = run.correct_spelling(slip, [_row("BRASFEILD GORRIE", 1), _row("BRASFIELD GORRIE", 300)])
    assert q3.core == "BRASFIELD GORRIE" and note


def test_spelling_correction_keeps_the_gcs_other_words(monkeypatch):
    # "Aboe Board Contracting" must not become the most-inspected ABOVE BOARD record (a California roofer)
    from ssi.matching import candidates, run
    monkeypatch.setattr(candidates, "core_tier", lambda core, initials: "distinctive")
    aboe = q("ABOE BOARD CONTRACTING", "ABOE BOARD", state="RI", city="Portsmouth")
    q2, note = run.correct_spelling(aboe, [
        _row("ABOVE BOARD", 14, "ABOVE BOARD CONSTRUCTION ROOFING", city="REDDING", state="CA"),
        _row("ABOVE BOARD", 3, "ABOVE BOARD CONTRACTING", city="PORTSMOUTH", state="RI")])
    assert note and q2.core == "ABOVE BOARD" and q2.clean == "ABOVE BOARD CONTRACTING"
    assert "ABOE BOARD CONTRACTING" in q2.aliases


def test_one_slip_is_a_dropped_added_or_swapped_letter():
    assert rules.one_slip("MCKENNYS", "MCKENNEYS") and rules.one_slip("BRASFEILD", "BRASFIELD")
    assert not rules.one_slip("MCKENNYS", "MCKENNA")  # two letters apart
    assert not rules.one_slip("PARMANCO", "HARMANCO") and not rules.one_slip("SANDOBAL", "SANDOVAL")  # replaced letter
    assert not rules.one_slip("BORA", "KORA") and not rules.one_slip("AECON", "AECOM")  # short names
    assert not rules.one_slip("STRATTONS", "SRATTONS")  # the first letters are rarely the slip
    assert not rules.one_slip("NORTH CREEK", "NORTHCREEK") and not rules.one_slip("BUILDERS G6", "BUILDERS G26")


def test_slip_with_a_record_in_the_gcs_city_is_searched_by_osha_spelling(monkeypatch):
    # McKenney's has 9 inspections, below the volume test, but one in Atlanta: "McKennys, Atlanta" is a slip
    from ssi.matching import candidates, run
    monkeypatch.setattr(candidates, "core_tier", lambda core, initials: "distinctive")
    rows = [_row("MCKENNEYS", 7, city="ATLANTA", state="GA"), _row("MCKENNEYS", 1, city="CHARLOTTE", state="NC"),
            _row("MCKENNA", 3, "MCKENNA CONSTRUCTION", city="PAYSON", state="AZ")]
    q2, note = run.correct_spelling(q("MCKENNYS", "MCKENNYS", state="GA", city="Atlanta"), rows)
    assert q2.core == q2.clean == "MCKENNEYS" and "Atlanta" in note
    # no record in the GC's city: nothing ties the slip to that company
    q3, note = run.correct_spelling(q("MCKENNYS", "MCKENNYS", state="GA", city="Savannah"), rows)
    assert note is None and q3.core == "MCKENNYS"
    # the GC's spelling has records of its own
    q4, note = run.correct_spelling(q("MCKENNYS", "MCKENNYS", state="GA", city="Atlanta"),
                                    [*rows, _row("MCKENNYS", 1, city="MACON", state="GA")])
    assert note is None
    # two names a slip away in the city: no way to tell which one the GC meant
    q5, note = run.correct_spelling(q("MCKENNYS", "MCKENNYS", state="GA", city="Atlanta"),
                                    [*rows, _row("MCKENNYSS", 1, city="ATLANTA", state="GA")])
    assert note is None
    # a replaced letter is usually another company, even in the same city
    q6, note = run.correct_spelling(q("SANDOBAL ROOFING", "SANDOBAL", state="MT", city="Billings"),
                                    [_row("SANDOVAL", 2, "SANDOVAL ROOFING", city="BILLINGS", state="MT")])
    assert note is None


def test_a_slip_in_the_gcs_city_beats_a_bigger_company_elsewhere(monkeypatch):
    # "Brinkmman Construction, Wheat Ridge": one letter from BRINKMAN (a record in Wheat Ridge) and near BRINKMANN
    # (25 inspections, St. Louis and Denver). Volume alone searched BRINKMANN and matched another company's records
    from ssi.matching import candidates, run
    monkeypatch.setattr(candidates, "core_tier", lambda core, initials: "distinctive")
    rows = [_row("BRINKMANN", 25, "BRINKMANN CONSTRUCTORS", city="AURORA", state="CO"),
            _row("BRINKMAN", 2, "BRINKMAN CONSTRUCTION", city="WHEAT RIDGE", state="CO")]
    q2, note = run.correct_spelling(q("BRINKMMAN CONSTRUCTION", "BRINKMMAN", state="CO", city="Wheat Ridge"), rows)
    assert q2.core == "BRINKMAN" and "Wheat Ridge" in note
    # with no record in the GC's city, OSHA's dominant spelling is still searched
    q3, note = run.correct_spelling(q("BRINKMMAN CONSTRUCTION", "BRINKMMAN", state="CO", city="Pueblo"), rows)
    assert q3.core == "BRINKMANN" and "25 inspections" in note


def test_typo_means_about_one_letter():
    assert rules.typo_equal("GORIE", "GORRIE") and rules.typo_equal("BRASFEILD", "BRASFIELD")
    assert not rules.typo_equal("COLMEX", "COLE")  # two letters short: another name


def test_person_name_with_a_misspelt_city_is_unsure_not_excluded():
    heuston = q("JOSE HERNANDEZ", "JOSE HERNANDEZ", state="TX", tier="person", city="heuston")
    d = decide(heuston, c("JOSE HERNANDEZ", "JOSE HERNANDEZ", state="TX", city="HOUSTON"), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "P1")
    assert decide(heuston, c("JOSE HERNANDEZ", "JOSE HERNANDEZ", state="TX", city="DALLAS"), GENERIC).rule_id == "X5"


# --- related facilities (plants, yards, shops not coded as construction) are never counted on name alone
def test_related_facility_by_name_is_unsure_not_matched():
    tindall = q("TINDALL CORPORATION", "TINDALL", state="SC")
    plant = c("TINDALL CORPORATION", "TINDALL", state="GA")
    plant.related_only = True
    d = decide(tindall, plant, GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "N1") and "isn't coded as construction" in d.reason
    plant.at_matched_address = True  # at an address the company uses: counted like any other record
    assert decide(tindall, plant, GENERIC).bucket == MATCHED


# --- the address is evidence, but a similar name at it isn't always the same company or person ------------
def test_a_joint_venture_at_the_address_is_never_merged():
    smc = q("SAVANNAH MOBILITY CONTRACTORS", "SAVANNAH MOBILITY", state="GA")
    jv = c("SAVANNAH MOBILITY CONTRACTORS JV", "SAVANNAH MOBILITY JV", state="GA", at_addr=True)
    jv.is_jv = True
    assert (decide(smc, jv, GENERIC).bucket, decide(smc, jv, GENERIC).rule_id) == (UNCERTAIN, "J1")
    # a JV the GC entered, and a member's record at its address: also not merged
    entered_jv = q("SAVANNAH MOBILITY CONTRACTORS JV", "SAVANNAH MOBILITY JV", state="GA")
    d = decide(entered_jv, c("SAVANNAH MOBILITY CONTRACTORS", "SAVANNAH MOBILITY", state="GA", at_addr=True), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "J1")


def test_is_jv_name_is_the_macro():
    import duckdb

    from ssi.cleaning import install_macros
    con = duckdb.connect()
    install_macros(con)
    names = ["ABC JV", "ABC JOINT VENTURE", "JV", "ABC", "JVC ELECTRIC", "ABC JOINT", "ADJV", "ABC JV DBA XYZ"]
    sql = con.execute("SELECT list(is_jv(n) ORDER BY i) FROM unnest(?::VARCHAR[]) WITH ORDINALITY t(n, i)", [names]).fetchone()[0]
    assert [rules.is_jv_name(n) for n in names] == sql


def test_trade_swaps_are_sister_companies_but_added_words_and_word_forms_are_not():
    g, d = GENERIC | {"FRAMING", "PAINTING", "PAINTERS", "ROOF", "SIDING"}, DESCRIPTORS
    assert rules.trade_swap("EENIGENBURG FRAMING", "EENIGENBURG ROOFING", g, d) == ["FRAMING", "ROOFING"]
    assert rules.trade_swap("SMITH ROOFING", "SMITH ROOFING SIDING", g, d) == []  # a trade word added
    assert rules.trade_swap("SMITH PAINTING", "SMITH PAINTERS", g, d) == []  # one word, two forms
    assert rules.trade_swap("SMITH ROOF", "SMITH ROOFING", g, d) == []
    assert rules.trade_swap("SMITH CONSTRUCTION", "SMITH CONTRACTING", g, d) == []  # descriptors, not trades
    at = {"at_addr": True, "state": "IN"}
    rules.DESCRIPTORS = DESCRIPTORS
    e = q("EENIGENBURG FRAMING", "EENIGENBURG", state="IN")
    d1 = decide(e, c("EENIGENBURG ROOFING", "EENIGENBURG", **at), g, d)
    assert (d1.bucket, d1.rule_id) == (UNCERTAIN, "U3")
    k = q("KOVALENKO ROOFING", "KOVALENKO", state="WA")
    assert decide(k, c("KOVALENKO ROOFING SIDING", "KOVALENKO", at_addr=True, state="WA"), g, d).rule_id == "M2"


@pytest.mark.parametrize("a,b,different", [
    ("MARIO CONTRERAS", "MAURICIO CONTRERAS", True),  # two given names
    ("RAMON GARCIA", "RAYMOND GARCIA", True),
    ("SERGIO CAZARES", "SERGIO CAZARES SR", True),  # father and son
    ("JOSE LUIS GARCIA", "JOSE LUIS GARCIA JR", True),
    ("CLARENCE BRIGNER", "CLARENCE M BRIGNER III", True),
    ("STEVE SELING", "STEVEN SELING", False),  # shortened
    ("MARCOS SOUZA", "MARCUS SOUZA", False),  # spelt another way
    ("ISMAEL FLORES", "ISHMAEL FLORES", False),  # ISHMAEL isn't a listed given name: a slip
    ("DANIEL KEATING", "DANIEL J KEATING", False),  # a middle initial added
    ("FRANCISCO CORTEZ", "FRANCISCO CORTEZ BUSTOS", False),  # a second family name added
    ("JOSE LUIS GARCIA", "JOSE GARCIA", False),
    ("ACME ROOFING", "ACME ROOFING SUPPLY", False),  # not people
])
def test_different_people(a, b, different):
    from ssi.matching.candidates import given_names
    assert rules.different_people(a, b, given_names()) is different
    assert rules.different_people(b, a, given_names()) is different


def test_another_person_at_the_address_is_a_question():
    mario = q("MARIO CONTRERAS", "MARIO CONTRERAS", state="FL", tier="person", city="Pensacola")
    d = decide(mario, c("MAURICIO CONTRERAS", "MAURICIO CONTRERAS", state="FL", city="PENSACOLA", at_addr=True), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "P2")
    # the query needn't be the person: a company's address with a person's record on it
    d = decide(q("SERGIO CAZARES", "SERGIO CAZARES", state="TX", tier="distinctive"),
               c("SERGIO CAZARES SR", "SERGIO CAZARES SR", state="TX", at_addr=True), GENERIC)
    assert (d.bucket, d.rule_id) == (UNCERTAIN, "P2")
    ismael = q("ISMAEL FLORES", "ISMAEL FLORES", state="VA", tier="person", city="Norfolk")
    assert decide(ismael, c("ISHMAEL FLORES", "ISHMAEL FLORES", state="VA", city="NORFOLK", at_addr=True), GENERIC).rule_id == "M2"


# --- spelling correction changes only the misspelt words, and keeps the sub's other names ------------------
def test_respell_replaces_words_not_letters():
    from ssi.matching.run import respell
    assert respell("ABOE BOARD CONTRACTING", "ABOE BOARD", "ABOVE BOARD") == "ABOVE BOARD CONTRACTING"
    # str.replace("ICE", "ACE") changed the first ICE it found, inside SERVICES
    assert respell("SERVICES ICE", "ICE", "ACE") == "SERVICES ACE"
    assert respell("ABOE CONSTRUCTION BOARD", "ABOE BOARD", "ABOVE BOARD") == "ABOVE CONSTRUCTION BOARD"
    assert respell("NORTH CREEK BUILDERS", "NORTH CREEK", "NORTHCREEK") == "NORTHCREEK BUILDERS"
    assert respell("XYZ HOLDINGS", "NORTH CREEK", "NORTHCREEK") is None  # a name without the slip
    assert respell("BRASFEILD GORRIE DBA BG BUILDERS", "BRASFEILD GORRIE", "BRASFIELD GORRIE") == \
        "BRASFIELD GORRIE DBA BG BUILDERS"


def test_spelling_correction_keeps_the_dba_and_licence_names(monkeypatch):
    from ssi.matching import candidates, run
    monkeypatch.setattr(candidates, "core_tier", lambda core, initials: "distinctive")
    slip = q("BRASFEILD GORRIE DBA BG BUILDERS", "BRASFEILD GORRIE", state="AL", city="Birmingham")
    slip.aliases = {slip.clean, "BRASFEILD GORRIE", "BG BUILDERS", "B AND G LICENSED NAME"}
    q2, note = run.correct_spelling(slip, [_row("BRASFEILD GORRIE", 1), _row("BRASFIELD GORRIE", 300)])
    assert note and q2.clean == "BRASFIELD GORRIE DBA BG BUILDERS"
    assert {"BG BUILDERS", "B AND G LICENSED NAME", "BRASFIELD GORRIE", "BRASFEILD GORRIE DBA BG BUILDERS"} <= q2.aliases
    # a slip that joins two words: the sub's other names stay as they were, never the bare corrected name
    nc = q("NORTH CREEK ROOFING DBA XYZ BUILDERS", "NORTH CREEK", state="WA")
    nc.aliases = {nc.clean, "NORTH CREEK ROOFING", "XYZ BUILDERS"}
    q3, note = run.correct_spelling(nc, [_row("NORTH CREEK", 1), _row("NORTHCREEK", 300)])
    assert note and q3.clean == "NORTHCREEK ROOFING DBA XYZ BUILDERS"
    assert "NORTHCREEK" not in q3.aliases and {"XYZ BUILDERS", "NORTHCREEK ROOFING"} <= q3.aliases


# --- properties: what the rules must never do, over many candidates ---------------------------------------
STATES = ["TX", "CA", "GA"]
CITIES = [None, "HOUSTON", "DALLAS", "AUSTIN"]


def _candidates(clean, core):
    for st in STATES:
        for city in CITIES:
            for extra in ("", " ROOFING", " JR", " SR"):
                yield c(clean + extra, core + (extra if extra in (" JR", " SR") else ""), state=st, city=city)


@pytest.mark.parametrize("name", ["JOSE HERNANDEZ", "JUAN GARCIA", "ALEX PEREZ", "J LOPEZ", "MORALES JAVIER M"])
def test_a_persons_name_is_never_matched_outside_the_gcs_city(name):
    for city in ("Houston", None):
        person = q(name, name, state="TX", tier="person", city=city)
        for cand in _candidates(name, name):
            d = decide(person, cand, GENERIC, DESCRIPTORS)
            if d.bucket == MATCHED:
                assert cand.state == "TX" and city and cand.city == "HOUSTON", (cand.clean_name, cand.state, cand.city)


@pytest.mark.parametrize("other", ["JOSE FERNANDEZ", "JOSE HERNANDES", "JOSUE HERNANDEZ", "JOSE HERNANDEZ JR",
                                   "MARIA HERNANDEZ", "JOSE HERRERA"])
def test_another_persons_name_is_never_matched_without_an_address(other):
    # typo_equal() calls HERNANDEZ / FERNANDEZ a slip (Jaro-Winkler 0.97); it must not decide on its own
    jose = q("JOSE HERNANDEZ", "JOSE HERNANDEZ", state="TX", tier="person", city="Houston")
    for st in STATES:
        for city in CITIES:
            assert decide(jose, c(other, other, state=st, city=city), GENERIC, DESCRIPTORS).bucket != MATCHED


@pytest.mark.parametrize("tier", ["distinctive", "medium", "generic", "person"])
def test_another_real_word_in_the_name_is_never_matched_without_an_address(tier):
    acme = q("ACME DRYWALL", "ACME", state="TX", tier=tier, city="Houston")
    for other, core in (("ACME ZEPHYR DRYWALL", "ACME ZEPHYR"), ("ZEPHYR DRYWALL", "ZEPHYR"), ("ACMEX DRYWALL", "ACMEX")):
        for st in STATES:
            for city in CITIES:
                assert decide(acme, c(other, core, state=st, city=city), GENERIC, DESCRIPTORS).bucket != MATCHED


def test_typo_equal_takes_different_family_names_for_slips():
    # documented: these are why typo_equal() alone never matches a record (see the two tests above)
    for a, b in (("JOSE HERNANDEZ", "JOSE FERNANDEZ"), ("JOHNSON", "JOHNSTON"), ("JUAN GARCIA", "JUAN GARZA"),
                 ("CARLOS MEJIA", "CARLOS MEDINA"), ("MARIO RAMIREZ", "MARIA RAMIREZ")):
        assert rules.typo_equal(a, b)
