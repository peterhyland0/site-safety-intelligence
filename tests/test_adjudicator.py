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
