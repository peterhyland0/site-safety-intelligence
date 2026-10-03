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


def test_inspection_ids_are_checked_whole():
    outs = [{"events": [{"inspection_id": 348557646, "date": "2025-11-03"}], "hours": 1250000}]
    assert check("A fatality in 2025 (#348557646).", outs) == []
    # an invented ID used to pass: digits after # were never checked
    assert check("A fatality in 2025 (#9999999).", outs) == ["#9999999"]
    # a truncated ID used to become a chip for an inspection that doesn't exist (substring match)
    assert check("See (#3485576).", outs) == ["#3485576"]
    assert cited_ids("See (#3485576) and (#348557646).", outs) == [348557646]
    # any 6+ digit figure in the results isn't an inspection
    assert cited_ids("Hours worked: 1250000.", outs) == []
    # an ID the foreman asked about can be named back; a short "#1" is an ordinary number
    assert check("I found no inspection #7777777 on this project.", outs, "What happened in #7777777?") == []
    assert check("Fall protection is the #1 hazard.", [{"cases": [{"inspection_id": 348557646}]}]) == []
    assert check("Fall protection is the #4 hazard.", outs) == ["#4"]


def test_keys_and_sub_ids_do_not_ground_figures():
    outs = [{"sub_id": "3f2a8c41-7b95-4e26-a813-90d2c5e67b14", "naics4": "2361", "trade_p75": 1.2, "verdict": "Review"}]
    assert check("They had 7 fatalities, 41 repeat citations and 4 open cases.", outs) == ["7", "41", "4"]
    # a percentile field's name is quoted as a figure ("Is Allison-Smith clean?" in the foreman eval)
    assert check("A rate of 1.2, at the trade's 75th percentile.", outs) == []


def test_date_parts_and_written_dates_pass():
    outs = [{"events": [{"date": "2025-11-03", "inspection_id": 1234567}]}]
    assert check("Inspected November 3, 2025 (#1234567), opened 2025-11-03.", outs) == []
    assert check("Opened 2025-11-04.", outs) == ["04"]


def test_list_lengths_and_instruction_constants_pass():
    outs = [{"cases": [{"inspection_id": 1}, {"inspection_id": 2}, {"inspection_id": 3}]}]
    assert check("3 open cases. Ask for the OSHA 300 logs.", outs) == []
    assert check("4 open cases.", outs) == ["4"]
