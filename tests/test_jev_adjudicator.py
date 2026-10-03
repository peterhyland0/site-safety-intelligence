import pytest

from ssi.llm import adjudicator, jev
from ssi.matching.adjudicate import ai_bucket, packet_facts


def _resp(same, different, unsure, model="jev-1.13.0"):
    return {"model": model, "usage": {"input_tokens": 900, "output_tokens": 3},
            "answers": {"decision": {"type": "choice", "choice": "same", "confidence": 0.5,
                                     "probabilities": {"same": same, "different": different, "unsure": unsure}}}}


@pytest.mark.parametrize("p, same_state, bucket", [
    (0.20, True, "excluded"), (0.21, True, "possible"),     # in the sub's state
    (0.06, False, "excluded"), (0.07, False, "possible"),   # another state: a national firm's branches live here
    (0.10, None, "possible"),                               # unknown state counts as another state
    (0.85, False, "matched"), (0.84, True, "possible"),
])
def test_thresholds_reach_the_apps_buckets(p, same_state, bucket):
    assert ai_bucket(jev.decision(p, same_state)) == bucket


def test_p_same_counts_unsure_as_half():
    assert jev.p_same(_resp(0.1, 0.7, 0.2)) == pytest.approx(0.2)


ANCHORS = [{"name": "NPL CONSTRUCTION", "address": "1 MAIN ST", "city": "TULSA", "state": "OK", "naics4": "2371"}]


def test_facts_compare_the_candidate_with_the_search_and_matched_records():
    far = packet_facts(ANCHORS, [{"address": "9 DESERT RD", "city": "LAS VEGAS", "state": "NV", "naics4": "2382"}], "ok")
    assert far == {"place": "Las Vegas, NV", "sub_state": "OK", "same_state": False, "anchor_addresses": True,
                   "shared_address": False, "trade": "2382", "anchor_trades": ["2371"]}
    near = packet_facts(ANCHORS, [{"address": "1 Main St", "city": "TULSA", "state": "OK", "naics4": "2371"}], None)
    assert near["same_state"] is None and near["shared_address"] is True  # no search state given: unknown


def test_facts_describe_the_whole_cluster():
    two = [{"address": "1 A ST", "city": "EASTVALE", "state": "CA", "naics4": "2371"},
           {"address": "1 MAIN ST", "city": "CERRITOS", "state": "CA", "naics4": "2212"}]
    f = packet_facts(ANCHORS, two, "OK")
    assert f["place"] == "Eastvale and Cerritos, CA" and f["shared_address"] and f["trade"] == "2212, 2371"
    three = two + [{"city": "IRVINE", "state": "CA"}]
    assert packet_facts(ANCHORS, three, "OK")["place"] == "3 places in CA"
    assert "trade code 2212, 2371, the matched records' 2371" in jev.rationale(0.04, "different", f)


def test_reason_is_written_from_the_evidence():
    facts = packet_facts(ANCHORS, [{"address": "9 DESERT RD", "city": "LAS VEGAS", "state": "NV", "naics4": "2382"}], "OK")
    text = jev.rationale(0.04, "different", facts)
    assert text == ("Likely a different company: Jev puts the chance it's the same company at 4%. Las Vegas, NV, "
                    "outside the sub's state (OK); no address in common with the sub's matched records; "
                    "trade code 2382, the matched records' 2371.")
    assert jev.rationale(0.5, "unsure", {}) == "Unclear: Jev puts the chance it's the same company at 50%."


def test_jev_answer_has_the_adjudicator_shape():
    packet = {"lines": [], "facts": {"same_state": True, "place": "Tulsa, OK"}}
    a = adjudicator.jev_answer(_resp(0.05, 0.85, 0.10), packet)
    assert a["decision"] == "different" and a["confidence"] == pytest.approx(0.9) and ai_bucket(a) == "excluded"
    assert a["decided_by"] == "ai:jev:jev-1.13.0" and a["evidence_ids"] == [] and a["rationale"].startswith("Likely a different")


@pytest.fixture
def routes(monkeypatch):
    """Both adjudicators available, each replaced by a stub that records which one answered."""
    calls = []
    monkeypatch.setenv("JEV_API_KEY", "k")
    monkeypatch.delenv("SSI_ADJUDICATOR", raising=False)
    monkeypatch.setattr(adjudicator.llm, "available", lambda role="foreman": True)
    monkeypatch.setattr(adjudicator, "decide_llm", lambda p: calls.append("llm") or {"decision": "unsure"})
    monkeypatch.setattr(adjudicator, "decide_jev", lambda p: calls.append("jev") or {"decision": "unsure"})
    return calls


def test_ordinary_clusters_go_to_jev_and_red_flagged_ones_to_the_llm(routes):
    adjudicator.decide({"lines": [], "red_flagged": False})
    adjudicator.decide({"lines": [], "red_flagged": True})
    assert routes == ["jev", "llm"]


def test_llm_setting_and_missing_key_send_everything_to_the_llm(routes, monkeypatch):
    monkeypatch.setenv("SSI_ADJUDICATOR", "llm")
    adjudicator.decide({"lines": []})
    monkeypatch.delenv("SSI_ADJUDICATOR")
    monkeypatch.delenv("JEV_API_KEY")
    adjudicator.decide({"lines": []})
    assert routes == ["llm", "llm"]


def test_red_flags_use_jev_when_there_is_no_llm(routes, monkeypatch):
    monkeypatch.setattr(adjudicator.llm, "available", lambda role="foreman": False)
    adjudicator.decide({"lines": [], "red_flagged": True})
    assert routes == ["jev"] and adjudicator.available()


def test_a_failed_jev_call_falls_back_to_the_llm(routes, monkeypatch):
    def boom(p):
        raise RuntimeError("Jev HTTP 503")
    monkeypatch.setattr(adjudicator, "decide_jev", boom)
    assert adjudicator.decide({"lines": []}) == {"decision": "unsure"} and routes == ["llm"]
    monkeypatch.setattr(adjudicator.llm, "available", lambda role="foreman": False)
    assert adjudicator.decide({"lines": []}) is None  # nothing else to ask: the cluster stays possible


def test_a_new_jev_version_is_logged_once(caplog):
    packet = {"lines": [], "facts": {}}
    adjudicator._warned.clear()
    adjudicator.jev_answer(_resp(0.5, 0.3, 0.2, model="jev-1.13.0"), packet)
    assert not caplog.records
    for _ in range(2):
        a = adjudicator.jev_answer(_resp(0.5, 0.3, 0.2, model="jev-1.14.0"), packet)
    assert [r.message for r in caplog.records] == [
        "Jev answered as jev-1.14.0; its thresholds were tuned on jev-1.13.0: re-run eval/adjudication"]
    assert a["decided_by"] == "ai:jev:jev-1.14.0"
