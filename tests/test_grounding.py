from ssi.agent.grounding import check, cited_ids

OUT = [{"sub": "ACME", "verdict": "Review", "serious_per_inspection": 1.83, "trade_median": 0.4,
        "reasons": [{"label": "Fall protection cited in 4 separate inspections (2012–2024)", "inspection_ids": [1234567]}],
        "penalty_current": 12500.0, "share": 0.25, "date": "2021-06-03"}]


def test_grounded_answer_passes():
    a = "ACME: Review. Serious citations 1.83 per inspection vs a median of 0.4; fall protection in 4 inspections " \
        "(2012–2024), e.g. (#1234567). Penalty $12,500, about 25% of cases, in 2021."
    assert check(a, OUT) == []


def test_invented_figures_fail():
    assert check("ACME had 7 willful violations and $40,000 in fines.", OUT) == ["7", "$40,000"]
    assert check("Rate 2.5 per inspection.", OUT) == ["2.5"]


def test_ids_cited_only_if_in_results():
    assert cited_ids("See (#1234567) and (#7654321).", OUT) == [1234567]
