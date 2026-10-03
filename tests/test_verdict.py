from ssi.scoring.verdict import Facts, HazardFact, RedFlagFact, evaluate


def facts(**kw):
    base = dict(as_of_year=2026, window_years=5, matched_establishments=2, inspections_all=10, inspections_window=4,
                rated_window=4, serious_plus_window=2, red_flags=[], hazards=[], open_serious_cases=[], pending_questions=0,
                benchmark_p75=1.5, benchmark_p90=2.5, benchmark_peers=100, benchmark_label="roofing contractors")
    base.update(kw)
    return Facts(**base)


def test_no_record_is_not_clean():
    v, _ = evaluate(facts(matched_establishments=0, inspections_all=0, inspections_window=0, rated_window=0, serious_plus_window=0))
    assert v == "no_record"


def test_no_flags_and_no_recent():
    assert evaluate(facts())[0] == "no_flags"
    assert evaluate(facts(inspections_window=0, rated_window=0, serious_plus_window=0))[0] == "no_recent"


def test_recent_cited_fatality_is_high_old_one_is_review():
    v, r = evaluate(facts(red_flags=[RedFlagFact("fatality_cited", 2021, 111, False)]))
    assert v == "high" and r[0].evidence == [111]
    v, _ = evaluate(facts(red_flags=[RedFlagFact("fatality_cited", 2005, 111, False)]))
    assert v == "review"


def test_fatality_site_not_cited_is_only_review_and_only_when_recent():
    assert evaluate(facts(red_flags=[RedFlagFact("fatality_inspected_not_cited", 2024, 5, False)]))[0] == "review"
    assert evaluate(facts(red_flags=[RedFlagFact("fatality_inspected_not_cited", 1985, 5, False)]))[0] == "no_flags"


def test_repeat_thresholds():
    one = [RedFlagFact("repeat", 2024, 1, False)]
    two = one + [RedFlagFact("repeat", 2023, 2, False)]
    assert evaluate(facts(red_flags=one))[0] == "review"
    assert evaluate(facts(red_flags=two))[0] == "high"


def test_rate_needs_enough_inspections_and_peers():
    assert evaluate(facts(rated_window=6, serious_plus_window=18))[0] == "high"           # 3.0 >= p90
    assert evaluate(facts(rated_window=2, serious_plus_window=6))[0] == "no_flags"        # too few inspections
    assert evaluate(facts(rated_window=6, serious_plus_window=18, benchmark_peers=10))[0] == "no_flags"


def test_recurring_hazard_and_open_cases():
    h = [HazardFact("fall_protection", "Fall protection", 3, 1, 2012, 2024, [1, 2, 3])]
    v, r = evaluate(facts(hazards=h))
    assert v == "review" and "Fall protection cited in 3" in r[0].label
    assert evaluate(facts(open_serious_cases=[9]))[0] == "review"
