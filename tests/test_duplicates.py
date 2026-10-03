import duckdb
import pytest

from ssi.api.duplicates import find
from ssi.cleaning import install_macros


@pytest.fixture(scope="module")
def key():
    c = duckdb.connect()
    install_macros(c)
    return lambda s: c.execute("SELECT clean_name(?)", [s]).fetchone()[0]


def rows(key, names, state):
    return [{"name": n, "key": key(n), "state": state} for n in names]


def test_same_company_spelled_differently_is_already_on_the_project(key):
    existing = [{"sub_id": "s1", "name": "COLMEX CONTRACTING", "key": key("COLMEX CONTRACTING"), "state": "FL"}]
    out = find(rows(key, ["Colmex Contracting, L.L.C.", "COLMEX CONTRACTING"], "FL"), existing)
    assert [o["row"] for o in out] == [0, 1]
    assert out[0]["message"] == 'Already on this project as "COLMEX CONTRACTING".'
    assert out[1]["message"] == "Already on this project."
    assert out[0]["sub_id"] == "s1"


def test_trade_words_and_state_keep_subs_apart(key):
    existing = [{"sub_id": "s1", "name": "ABC Roofing", "key": key("ABC Roofing"), "state": "TX"}]
    new = rows(key, ["ABC Electric"], "TX") + rows(key, ["ABC Roofing"], "OK")
    assert find(new, existing) == []


def test_repeat_within_one_batch(key):
    out = find(rows(key, ["J & J Drywall", "J and J Drywall LLC"], "TN"), [])
    assert out == [{"row": 1, "name": "J and J Drywall LLC", "message": 'Same company as "J & J Drywall" above.'}]


def test_city_typed_into_the_name_is_not_caught_here(key):
    # the form warns about this one and offers to move the place into the city and state fields
    existing = [{"sub_id": "s1", "name": "COLMEX CONTRACTING", "key": key("COLMEX CONTRACTING"), "state": "FL"}]
    assert find(rows(key, ["COLMEX CONTRACTING LLC. BUNNELL FL"], "FL"), existing) == []
