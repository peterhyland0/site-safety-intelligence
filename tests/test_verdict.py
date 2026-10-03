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


def test_cited_catastrophe_without_a_death_is_review():
    from datetime import date
    f = RedFlagFact("catastrophe_cited", 2024, 6, False, when=date(2024, 5, 1))
    v, r = evaluate(facts(as_of=date(2026, 9, 23), red_flags=[f]))
    assert v == "review" and r[0].code == "R_catastrophe_cited"


def test_one_visit_is_one_inspection_for_repeats():
    # OSHA opened a safety and a health inspection for the same visit (same site and day): one visit, Review
    same_visit = [RedFlagFact("repeat", 2024, 1, False, visit="site-a"), RedFlagFact("repeat", 2024, 2, False, visit="site-a")]
    v, r = evaluate(facts(red_flags=same_visit))
    assert v == "review" and r[0].code == "R_repeat"
    two_visits = [RedFlagFact("repeat", 2024, 1, False, visit="site-a"), RedFlagFact("repeat", 2023, 2, False, visit="site-b")]
    assert evaluate(facts(red_flags=two_visits))[0] == "high"


def test_files_without_an_inspection_are_no_record():
    # matched records exist, but OSHA never inspected (insp_scope D): unknown, not clean
    v, r = evaluate(facts(inspections_all=0, inspections_window=0, rated_window=0, serious_plus_window=0,
                          visits_without_inspection=12))
    assert v == "no_record" and r[0].code == "I_no_inspection" and r[0].severity == "info"


def test_fatcat_file_without_inspection_is_review_while_recent():
    from datetime import date
    f = RedFlagFact("fatcat_no_inspection", 2025, 7, False, when=date(2025, 3, 1))
    v, r = evaluate(facts(as_of=date(2026, 9, 23), red_flags=[f]))
    assert v == "review" and r[0].code == "R_fatcat_no_inspection"


def test_self_reported_deaths_are_review():
    from datetime import date
    v, r = evaluate(facts(as_of=date(2026, 9, 23), ita_deaths=[(2023, 6)]))
    assert v == "review" and r[0].code == "R_ita_deaths" and "6 work-related death" in r[0].label
    # older than the 10-year recency window: no reason
    assert evaluate(facts(as_of=date(2026, 9, 23), ita_deaths=[(2014, 1)]))[0] == "no_flags"


def test_a_fatality_is_one_event_per_visit():
    # OSHA's fatality inspection (346032436) had no citations; a second inspection of the same visit (346062102)
    # carried the serious ones. The build marks the fatality cited for the visit, and when both inspections link
    # to the accident the death counts once
    from datetime import date

    from ssi.scoring.verdict import one_event_per_visit
    day = date(2022, 6, 21)
    m = RedFlagFact("fatality_cited", 2022, 346032436, False, when=day)
    g = RedFlagFact("fatality_cited", 2022, 346062102, False, when=day)
    rep = RedFlagFact("repeat", 2022, 346062102, False, when=day)
    other = RedFlagFact("fatality_inspected_not_cited", 2023, 111, False, when=date(2023, 1, 5))
    kept = one_event_per_visit([m, g, rep, other], {346032436: "v1", 346062102: "v1", 111: "v2"})
    assert kept == [m, rep, other]
    v, r = evaluate(facts(as_of=date(2026, 9, 23), red_flags=kept))
    high = next(x for x in r if x.code == "H_fatality_cited")
    assert v == "high" and high.figures["count"] == 1 and high.evidence == [346032436]
    # the most serious outcome stands for the visit, wherever it is listed
    site = RedFlagFact("fatcat_site_cited", 2024, 5, False, when=date(2024, 2, 1))
    own = RedFlagFact("fatcat_cited", 2024, 6, False, when=date(2024, 2, 1))
    assert one_event_per_visit([site, own], {5: "v3", 6: "v3"}) == [own]
    # without a known visit, each inspection is its own
    assert one_event_per_visit([site, own], {}) == [site, own]
