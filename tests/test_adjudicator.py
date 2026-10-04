from ssi.llm.adjudicator import validate

PACKET = {"lines": [
    {"id": "E1", "text": "GC's sub: name 'ABC Roofing', city 'Dallas', state 'TX', trade 'roofing'"},
    {"id": "E2", "text": "Candidate OSHA record: 'ABC ROOFING' at 12 MAIN ST, PLANO TX 75023; active 2016-01-02–2019-05-01; 3 inspection(s)"},
]}


def test_valid_answer():
    ok, _ = validate({"decision": "unsure", "confidence": 0.5, "evidence_ids": ["E1", "E2"],
                      "rationale": "Same name in Plano, near Dallas, active 2016–2019, but no shared address."}, PACKET)
    assert ok


def test_rejects_invented_evidence_and_places():
    assert not validate({"decision": "same", "confidence": 0.9, "evidence_ids": ["E7"], "rationale": "x"}, PACKET)[0]
    assert not validate({"decision": "same", "confidence": 0.9, "evidence_ids": ["E2"],
                         "rationale": "Same company, also seen in Houston."}, PACKET)[0]
    assert not validate({"decision": "same", "confidence": 0.9, "evidence_ids": ["E2"],
                         "rationale": "Active since 2009."}, PACKET)[0]
    assert not validate({"decision": "same", "confidence": 1.4, "evidence_ids": ["E2"], "rationale": "ok"}, PACKET)[0]
    assert not validate(None, PACKET)[0]


def _cluster(name, city, state, key, insp=2, decision=None, flags=1):
    rows = [{"establishment_key": key, "evidence": {"name": name, "city": city, "state": state, "address": None,
                                                     "years": ["2018-03-01", "2021-06-01"], "inspections": insp}}]
    return (rows, decision, (decision or {}).get("rationale"), flags)


SUB = {"entered_name": "Quality Roofing"}


def test_red_flag_record_reaches_gc_even_when_ai_says_different():
    from ssi.matching.adjudicate import questions_for
    ai = {"decision": "different", "confidence": 0.95, "rationale": "Different city and trade."}
    qs = questions_for(SUB, [_cluster("BARNARD ROOFING", "KNOXVILLE", "TN", "k1", decision=ai)])
    assert len(qs) == 1
    text, keys, suggestion, rationale = qs[0]
    assert keys == ["k1"] and suggestion == "different" and rationale == "Different city and trade."
    assert "Is this the same company as your sub 'Quality Roofing'?" in text


def test_many_red_flag_clusters_are_grouped_by_name_not_dropped():
    from ssi.matching.adjudicate import questions_for
    red = [_cluster("QUALITY ROOFING", c, s, f"q{i}", decision={"decision": d, "confidence": 0.9}, flags=1)
           for i, (c, s, d) in enumerate([("DALLAS", "TX", "same"), ("TAMPA", "FL", "different"), ("MOBILE", "AL", "same")])]
    red += [_cluster("QUALITY ROOFING AND SIDING", "ATLANTA", "GA", "s1", flags=5),
            _cluster("QUALITY ROOFING AND SIDING", "MACON", "GA", "s2", flags=1)]
    qs = questions_for(SUB, red)
    assert len(qs) == 2  # one per OSHA name
    assert sorted(k for q in qs for k in q[1]) == ["q0", "q1", "q2", "s1", "s2"]  # nothing dropped
    assert qs[0][1] == ["s1", "s2"]  # most red flags first
    assert "ATLANTA, GA; MACON, GA" in qs[0][0] and "answer each record below" in qs[0][0]
    assert qs[1][2] is None  # the AI leaned both ways across the group: no single suggestion


def test_question_says_when_a_facility_isnt_coded_as_construction():
    from ssi.matching.adjudicate import question_text
    rows = [{"establishment_key": "k", "evidence": {"name": "TINDALL CORPORATION", "city": "CONLEY", "state": "GA", "address": "PO BOX 280",
                                                     "years": ["2026-08-09", "2026-08-09"], "inspections": 1,
                                                     "related_only": True, "naics4": "3273", "rule": "N1"}}]
    text = question_text({"entered_name": "Tindall Corporation"}, rows)
    assert "isn't coded as construction (industry code 3273)" in text and "Tindall Corporation" in text


def test_ordinary_capitalised_words_and_spelled_out_states_are_not_invented_places():
    tn = {"lines": [{"id": "E1", "text": "GC's sub: name 'Jake Marshall LLC', city 'heuston', state 'TN'"},
                    {"id": "E2", "text": "Candidate OSHA record: 'JAKE MARSHALL SERVICE' at 1 MAIN ST, NASHVILLE TN 37201"}]}
    for rationale in ["Although the names match, the cities differ.",            # sentence-initial word
                      "Thin evidence: only the name matches.",                    # sentence-initial word
                      "Both records are in Tennessee, but in different cities.",  # spelled-out state = TN
                      "The sub is in Houston per the GC, the record in Nashville."]:  # GC typed 'heuston'
        assert validate({"decision": "unsure", "confidence": 0.5, "evidence_ids": ["E1", "E2"], "rationale": rationale}, tn)[0], rationale
    # still strict about places that appear nowhere
    assert not validate({"decision": "same", "confidence": 0.9, "evidence_ids": ["E2"],
                         "rationale": "Both offices are in Memphis."}, tn)[0]


def test_peoples_names_are_never_grouped():
    from ssi.matching.adjudicate import questions_for
    red = []
    for i, city in enumerate(["KATY", "CANUTILLO", "EL PASO", "SAN ANTONIO"]):
        rows, d, r, f = _cluster("JOEL HERNANDEZ", city, "TX", f"k{i}")
        rows[0]["evidence"]["query"] = {"tier": "person"}
        red.append((rows, d, r, f))
    qs = questions_for({"entered_name": "Jose Hernandez"}, red)
    assert len(qs) == 4 and all(len(q[1]) == 1 for q in qs)  # one question per record, past the threshold too


def test_facility_wording_only_for_records_linked_by_the_subs_name():
    from ssi.matching.adjudicate import question_text
    rows = [{"establishment_key": "k", "evidence": {"name": "NEEL SCHAFFER", "city": "JACKSON", "state": "MS",
                                                     "address": "4450 OLD CANTON RD STE 100", "years": ["2021-01-01", "2024-01-01"],
                                                     "inspections": 2, "related_only": True, "naics4": "5413", "rule": "R1"}}]
    assert "plant, yard or shop" not in question_text({"entered_name": "Brasfield & Gorrie"}, rows)


def test_a_failed_llm_call_leaves_the_cluster_possible_instead_of_failing_the_sub(monkeypatch):
    # a Modal timeout on one red-flagged cluster used to escape adjudicate() and lose every decision on the sub
    from ssi.llm import adjudicator
    from ssi.llm import client as llm

    def timeout(packet):
        raise TimeoutError("adjudicator endpoint timed out")

    monkeypatch.setattr(llm, "available", lambda role="foreman": True)
    monkeypatch.setattr(adjudicator, "use_jev", lambda: False)
    monkeypatch.setattr(adjudicator, "decide_llm", timeout)
    assert adjudicator.decide({**PACKET, "red_flagged": True}) is None
