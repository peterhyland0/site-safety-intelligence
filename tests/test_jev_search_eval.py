import json

import httpx

from eval.jev_search.run import QUESTIONS, grade, jev_kept, packet, pairs_for, ranked_first
from ssi.llm import jev


def _rec(key, name, city, state, ein, core=None, variants=()):
    return {"establishment_key": key, "display_name": name, "clean_name": name, "name_core": core or name,
            "name_variants": [name, *variants], "city": city, "state": state, "ein": ein, "insp_n": 1}


SEARCH = {**_rec("a", "ABC ROOFING", "DALLAS", "TX", "1", "ABC"), "name": "ABC ROOFING"}
POOL = [_rec("a", "ABC ROOFING", "DALLAS", "TX", "1", "ABC"),
        _rec("b", "ABC ROOFING", "TULSA", "OK", "1", "ABC", ["ABC ROOFING INC", "A B C ROOFING", "ABC ROOF", "ABC R"]),
        _rec("c", "ABC PLUMBING", "DALLAS", "TX", "2", "ABC"),
        _rec("d", "ZETA ELECTRIC", "PLANO", "TX", "3")]


def test_packet_is_the_search_and_one_record_as_evidence_lines():
    p = packet(SEARCH, POOL[1])
    assert p["sub"] == "ABC ROOFING" and [x["id"] for x in p["lines"]] == ["E1", "E2"]
    assert p["lines"][0]["text"] == "GC's search: name 'ABC ROOFING', city 'DALLAS', state 'TX'"
    assert p["lines"][1]["text"] == ("OSHA record: name 'ABC ROOFING' (also typed as 'ABC ROOFING INC', "
                                     "'A B C ROOFING', 'ABC ROOF'), city 'TULSA', state 'OK'")  # 3 other spellings at most


def test_pairs_skip_the_search_itself_and_are_labelled_by_tax_id():
    pairs = pairs_for([SEARCH], POOL)
    assert [(p["record"]["establishment_key"], p["label"], p["kind"]) for p in pairs] == [
        ("b", 1, "same company"), ("c", 0, "lookalike"), ("d", 0, "other")]
    assert (pairs[0]["same_name"], pairs[0]["same_state"]) == (True, False)
    typed = pairs_for([{"name": "Abc Roofing", "city": "Dallas", "state": "TX"}], POOL)
    assert len(typed) == 4 and {p["label"] for p in typed} == {None}  # a search of your own has no label


def _scored(jev_p, jw, rules):
    pairs = pairs_for([SEARCH], POOL)
    for p, j, w, r in zip(pairs, jev_p, jw, rules):
        p.update(jev=j, jw=w, rules=r, seconds=0.2, tokens=600)
    return pairs


def test_grade_counts_what_each_finder_would_show():
    g = grade(_scored([0.9, 0.3, 0.0], [1.0, 0.9, 0.5], ["matched", "excluded", "not_found"]))
    assert g["groups"]["Same company"] == {"n": 1, "Rules (the app's search)": 1, "Jaro-Winkler ≥ 0.8": 1,
                                           "Jev, the app's cut-offs": 1, "Jev P(same) > 0.2": 1, "Jev P(same) ≥ 0.85": 1}
    look = g["groups"]["Lookalike (same name core, other tax ID)"]
    assert (look["Rules (the app's search)"], look["Jaro-Winkler ≥ 0.8"], look["Jev P(same) > 0.2"]) == (0, 1, 1)
    assert g["jev"]["auc"] == 1.0 and g["jev"]["tokens"] == 1800 and g["jev"]["missing"] == 0


def test_the_apps_cut_offs_keep_more_in_another_state():
    other, here, _ = _scored([0.07, 0.15, 0.0], [1.0, 0.9, 0.5], ["matched"] * 3)  # b is in OK, c in TX
    assert jev_kept(other) and not jev_kept(here)  # 0.07 > 0.06 out of state; 0.15 <= 0.20 in the search's state
    g = grade(_scored([0.07, 0.15, 0.0], [1.0, 0.9, 0.5], ["not_found", "excluded", "not_found"]))
    assert g["groups"]["  the rules don't find"]["Jev, the app's cut-offs"] == 1


def test_a_tie_with_a_wrong_record_is_not_ranked_first():
    assert ranked_first(_scored([0.5, 0.5, 0.1], [1.0, 0.9, 0.5], ["matched"] * 3), "jev") == 0.0
    assert ranked_first(_scored([0.5, 0.5, 0.1], [1.0, 0.9, 0.5], ["matched"] * 3), "jw") == 1.0


def test_a_failed_call_is_missing_not_found():
    pairs = _scored([None, 0.3, 0.0], [1.0, 0.9, 0.5], ["matched", "excluded", "not_found"])
    g = grade(pairs)
    assert g["jev"]["missing"] == 1 and g["groups"]["Same company"]["Jev P(same) > 0.2"] == 0


def test_the_request_carries_the_search_question(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "k")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "jev-1.13.0", "usage": {"input_tokens": 630}, "answers": {
            "decision": {"type": "choice", "choice": "same", "probabilities": {"same": 0.8, "different": 0.0, "unsure": 0.2}}}})

    http = httpx.Client(base_url="https://api.typesafe.ai", transport=httpx.MockTransport(handler))
    r = jev.ask(packet(SEARCH, POOL[1]), http, QUESTIONS)
    assert seen["body"]["questions"]["decision"]["instructions"].startswith("A general contractor looks up")
    assert seen["body"]["state"]["evidence"]["E1"] == "GC's search: name 'ABC ROOFING', city 'DALLAS', state 'TX'"
    assert abs(jev.p_same(r) - 0.9) < 1e-9
