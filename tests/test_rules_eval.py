from eval.rules.run import apparent_error, capped, merge_review, reviewed_label, summarise, wilson
from ssi.matching.run import EXCLUDED, MATCHED, UNCERTAIN


def rec(a, b, rule, bucket, label, ein="E1", local=False):
    return {"pool": "general", "a_key": a, "a_ein": ein, "b_key": b, "rule": rule, "bucket": bucket, "label": label,
            "local": local, "a": f"A{a}", "b": f"B{b}"}


def test_wilson_interval():
    assert wilson(0, 0) is None
    assert wilson(10, 10) == (0.72, 1.0)
    lo, hi = wilson(50, 100)
    assert lo < 0.5 < hi and round(lo + hi, 2) == 1.0


def test_cap_keeps_k_labelled_per_search_rule_and_bucket():
    rows = [rec("a", f"b{i}", "X1", EXCLUDED, 0) for i in range(10)]
    rows += [rec("a", "u", "X1", EXCLUDED, None), rec("a", "m", "M1", MATCHED, 1), rec("z", "b", "X1", EXCLUDED, 0)]
    out = capped(rows, k=3)
    assert sum(r["a_key"] == "a" and r["rule"] == "X1" for r in out) == 3  # one national firm can't fill a rule's set
    assert all(r["label"] is not None for r in out)  # unlabelled records aren't graded
    assert {(r["a_key"], r["rule"]) for r in out} == {("a", "X1"), ("a", "M1"), ("z", "X1")}
    assert capped(rows, k=3) == out  # deterministic


def test_apparent_errors_are_wrong_merges_and_wrong_exclusions():
    assert apparent_error(rec("a", "b", "M3", MATCHED, 0))
    assert apparent_error(rec("a", "b", "X5", EXCLUDED, 1))
    assert not apparent_error(rec("a", "b", "M3", MATCHED, 1))
    assert not apparent_error(rec("a", "b", "S1", UNCERTAIN, 0))  # holding a record back is never an error here


def test_review_keeps_verdicts_drops_stale_unjudged_and_caps_new():
    errors = [rec("a", f"b{i}", "M3", MATCHED, 0) for i in range(5)]
    existing = {("a", "old", "M3"): {"rule": "M3", "bucket": MATCHED, "a_key": "a", "b_key": "old", "verdict": "family"},
                ("a", "gone", "M3"): {"rule": "M3", "bucket": MATCHED, "a_key": "a", "b_key": "gone", "verdict": None}}
    out = merge_review(existing, errors, per_rule=3)
    assert out[("a", "old", "M3")]["verdict"] == "family"  # a person's verdict is never thrown away
    assert ("a", "gone", "M3") not in out  # an unjudged entry that's no longer an error goes
    assert sum(e["rule"] == "M3" for e in out.values()) == 3  # the judged one counts toward the cap
    assert all(e["verdict"] is None and e["silver"] == "different" for k, e in out.items() if k[1] != "old")


def test_verdicts_replace_the_silver_label_and_a_family_counts_as_same():
    r = rec("a", "b", "M3", MATCHED, 0)
    assert reviewed_label(r, {}) == 0
    assert reviewed_label(r, {("a", "b", "M3"): {"verdict": "family"}}) == 1
    assert reviewed_label(r, {("a", "b", "M3"): {"verdict": "unsure"}}) == 0
    assert reviewed_label(rec("a", "b", "X5", EXCLUDED, 1), {("a", "b", "X5"): {"verdict": "different"}}) == 0


def test_summary_by_rule_and_bucket():
    fired = [rec("a", "b1", "M3", MATCHED, 1), rec("a", "b2", "M3", MATCHED, 0, local=True),
             rec("c", "b3", "M3", MATCHED, None, ein="E2"), rec("a", "b4", "X1", EXCLUDED, 0)]
    graded = capped(fired)
    review = {("a", "b2", "M3"): {"verdict": "same"}}
    s = {(x["rule"], x["bucket"]): x for x in summarise(fired, graded, review)}
    m3 = s[("M3", MATCHED)]
    assert (m3["searches"], m3["records"], m3["labelled"], m3["firms"]) == (2, 3, 2, 1)
    assert (m3["same"], m3["different"], m3["different_local"], m3["share_same"]) == (1, 1, 1, 0.5)
    assert (m3["apparent_errors"], m3["reviewed"], m3["share_same_after_review"]) == (1, 1, 1.0)
    assert s[("X1", EXCLUDED)]["share_same"] == 0.0 and s[("X1", EXCLUDED)]["share_same_after_review"] is None
    assert [x["bucket"] for x in summarise(fired, graded, review)] == [MATCHED, EXCLUDED]  # matched rules first
