"""Matching rules on synthetic candidates: every trap from the profile and the evaluation."""
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
    assert d.bucket != MATCHED


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
def _row(core, insp, clean=None):
    return {"name_core": core, "clean_name": clean or core, "insp_n": insp, "sim": 0.95, "initials_only": False,
            "sibling_suffix": None}


def test_spelling_correction_needs_a_clearly_dominant_spelling(monkeypatch):
    from ssi.matching import candidates, run
    monkeypatch.setattr(candidates, "core_tier", lambda core, initials: "distinctive")
    colmex = q("COLMEX CONTRACTING", "COLMEX", state="FL")
    q2, note = run.correct_spelling(colmex, [_row("COLMEX", 1, "COLMEX CONTRACTING"), _row("COMEX", 5, "COMEX CONSTRUCTION")])
    assert note is None and q2.core == "COLMEX"  # Comex (5 inspections) is another company, not a typo fix
    slip = q("BRASFEILD GORRIE", "BRASFEILD GORRIE")
    q3, note = run.correct_spelling(slip, [_row("BRASFEILD GORRIE", 1), _row("BRASFIELD GORRIE", 300)])
    assert q3.core == "BRASFIELD GORRIE" and note


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
