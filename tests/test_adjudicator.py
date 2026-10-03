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
    assert "ATLANTA, GA; MACON, GA" in qs[0][0] and "mark those individually under Matches" in qs[0][0]
    assert qs[1][2] is None  # the AI leaned both ways across the group: no single suggestion
