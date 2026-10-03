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
    h = [HazardFact("fall_protection", "Fall protection (edges, holes)", 3, 1, 2012, 2024, [1, 2, 3])]
    v, r = evaluate(facts(hazards=h))
    assert v == "review" and r[0].label.startswith("Fall protection cited in 3")
    old = [HazardFact("electrical", "Electrical", 9, 0, 1975, 1999, [4])]
    v, r = evaluate(facts(hazards=old))
    assert v == "no_flags" and r[0].severity == "info"
    assert evaluate(facts(open_serious_cases=[9]))[0] == "review"


def test_recency_compares_dates_not_calendar_years():
    from datetime import date
    as_of = date(2026, 9, 23)
    inside = RedFlagFact("fatality_cited", 2016, 1, False, when=date(2016, 10, 1))   # 9 years 11 months ago
    outside = RedFlagFact("fatality_cited", 2016, 2, False, when=date(2016, 9, 1))   # just over 10 years ago
    assert evaluate(facts(as_of=as_of, red_flags=[inside]))[0] == "high"
    v, r = evaluate(facts(as_of=as_of, red_flags=[outside]))
    assert v == "review" and r[0].code == "R_old_fatality_cited"


def test_open_fatality_investigation_is_never_silent():
    from datetime import date
    pending = RedFlagFact("fatality_pending", 2025, 3, True, when=date(2025, 10, 16))
    v, r = evaluate(facts(as_of=date(2026, 9, 23), red_flags=[pending]))
    assert v == "review" and r[0].code == "R_fatality_pending"


def test_closed_fatcat_investigation_without_serious_citations_is_review_while_recent():
    from datetime import date
    f = RedFlagFact("fatcat_not_cited", 2025, 4, False, when=date(2025, 6, 1))
    assert evaluate(facts(as_of=date(2026, 9, 23), red_flags=[f]))[0] == "review"


def test_cited_at_a_site_under_fatality_investigation_is_review():
    from datetime import date
    f = RedFlagFact("fatcat_site_cited", 2026, 5, True, when=date(2026, 2, 3))
    v, r = evaluate(facts(as_of=date(2026, 9, 23), red_flags=[f]))
    assert v == "review" and r[0].code == "R_fatcat_site_cited"
