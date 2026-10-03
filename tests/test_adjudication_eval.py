import json

import httpx

from eval.adjudication import jev
from eval.adjudication.run import auc, metrics
from ssi.matching.adjudicate import ai_bucket, build_packet

PACKET = {"sub": "ABC Roofing", "lines": [
    {"id": "E1", "text": "GC's sub: name 'ABC Roofing', city 'Dallas', state 'TX', trade 'not given'"},
    {"id": "E2", "text": "Candidate OSHA record: 'ABC ROOFING' at 12 MAIN ST, PLANO TX 75023"},
]}


def test_app_thresholds():
    assert ai_bucket({"decision": "same", "confidence": 0.85}) == "matched"
    assert ai_bucket({"decision": "same", "confidence": 0.84}) == "possible"
    assert ai_bucket({"decision": "different", "confidence": 0.80}) == "excluded"
    assert ai_bucket({"decision": "different", "confidence": 0.79}) == "possible"
    assert ai_bucket({"decision": "unsure", "confidence": 0.99}) == "possible"


def test_build_packet_caps_candidates_and_keeps_keys():
    ev = {"name": "ABC ROOFING", "address": "12 MAIN ST", "city": "PLANO", "state": "TX", "zip": "75023",
          "years": ["2016-01-02", "2019-05-01"], "inspections": 3, "naics4": "2381", "similarity": 1.0, "reason": "r"}
    p = build_packet({"entered_name": "ABC Roofing", "entered_city": "Dallas", "entered_state": "TX"},
                     [ev], [ev] * 7, [f"k{i}" for i in range(7)])
    assert [line["id"] for line in p["lines"]] == [f"E{i}" for i in range(1, 8)]  # sub + 1 matched + 5 candidates
    assert p["lines"][0]["text"] == "GC's sub: name 'ABC Roofing', city 'Dallas', state 'TX', trade 'not given'"
    assert p["lines"][1]["text"].startswith("Already matched OSHA record: 'ABC ROOFING' at 12 MAIN ST, PLANO TX 75023")
    assert "3 inspection(s); trade code 2381; name similarity 1.0" in p["lines"][2]["text"]
    assert p["keys"] == [f"k{i}" for i in range(7)] and p["sub"] == "ABC Roofing"


def test_jev_request_and_answers(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return httpx.Response(200, json={"model": "jev-1.13.0", "usage": {"input_tokens": 600, "output_tokens": 4},
                                         "answers": {
                                             "decision": {"type": "choice", "choice": "same", "confidence": 0.9,
                                                          "probabilities": {"same": 0.9, "different": 0.04, "unsure": 0.06}},
                                             "same": {"type": "noul", "noul": 0.12}}})

    http = httpx.Client(base_url="https://api.typesafe.ai", transport=httpx.MockTransport(handler),
                        headers={"Authorization": "Bearer test-key"})
    resp = jev.ask(PACKET, http)
    assert seen["url"] == "https://api.typesafe.ai/v1/systemone" and seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "jev-latest"
    assert seen["body"]["state"] == {"sub": "ABC Roofing", "evidence": {"E1": PACKET["lines"][0]["text"],
                                                                         "E2": PACKET["lines"][1]["text"]}}
    assert {k: q["type"] for k, q in seen["body"]["questions"].items()} == {"decision": "choice", "same": "noul"}
    assert resp["model"] == "jev-1.13.0" and resp["usage"]["input_tokens"] == 600
    d = jev.decisions(resp)
    assert ai_bucket(d["jev-choice"]) == "matched" and abs(d["jev-choice"]["p_same"] - 0.93) < 1e-9
    assert d["jev-noul"]["decision"] == "different" and ai_bucket(d["jev-noul"]) == "excluded"  # P(yes) 0.12 <= 0.20


def test_jev_retries_server_errors_then_raises(monkeypatch):
    from ssi.llm import jev as app_jev
    monkeypatch.setattr(app_jev.time, "sleep", lambda s: None)
    calls = []
    http = httpx.Client(base_url="https://x", transport=httpx.MockTransport(
        lambda r: calls.append(1) or httpx.Response(503, text="busy")))
    try:
        jev.ask(PACKET, http, retries=2)
        raise AssertionError("expected an error")
    except RuntimeError as e:
        assert "503" in str(e)
    assert len(calls) == 3


def test_metrics_count_errors_by_label():
    rows = [{"label": 1, "bucket": "matched", "p_same": 0.9}, {"label": 1, "bucket": "excluded", "p_same": 0.1},
            {"label": 0, "bucket": "matched", "p_same": 0.95}, {"label": 0, "bucket": "possible", "p_same": 0.5},
            {"label": 0, "bucket": "excluded", "p_same": 0.05}]
    m = metrics(rows)
    assert (m["wrong_merges"], m["wrong_exclusions"], m["same_matched"], m["different_excluded"]) == (1, 1, 1, 1)
    assert m["resolved"] == 0.8 and m["match_precision"] == 0.5 and m["exclude_precision"] == 0.5
    assert auc([(0.9, 1), (0.1, 0)]) == 1.0 and auc([(0.5, 1), (0.5, 0)]) == 0.5 and auc([(0.9, 1)]) is None


def test_jev_env_names_and_url_forms(monkeypatch):
    for n in ("JEV_API_KEY", "TYPESAFE_API_KEY", "JEV_API_URL", "TYPESAFE_BASE_URL"):
        monkeypatch.delenv(n, raising=False)
    assert not jev.available() and jev.base_url() == "https://api.typesafe.ai"
    monkeypatch.setenv("JEV_API_KEY", "k")
    assert jev.available()
    for url in ("https://api.typesafe.ai/", "https://api.typesafe.ai/v1", "https://api.typesafe.ai/v1/systemone"):
        monkeypatch.setenv("JEV_API_URL", url)
        assert jev.base_url() == "https://api.typesafe.ai"
