from redteam.promotion import decide


def m(recall, fpr, **fams):
    return {"recall": recall, "fpr": fpr, "per_family": {k: {"n": 10, "recall": v} for k, v in fams.items()}}


def test_first_model_only_needs_fpr():
    assert decide(m(0.5, 0.01), None) == (True, [])
    ok, why = decide(m(0.99, 0.03), None)
    assert not ok and "FPR" in why[0]


def test_must_beat_incumbent_recall():
    ok, why = decide(m(0.80, 0.01, a=0.8), m(0.80, 0.01, a=0.8))
    assert not ok and "does not beat" in why[0]
    assert decide(m(0.81, 0.01, a=0.8), m(0.80, 0.01, a=0.8))[0]


def test_family_drop_over_five_points_blocks():
    ok, why = decide(m(0.90, 0.01, a=0.94, b=0.60), m(0.85, 0.01, a=1.0, b=0.60))
    assert not ok and any("a recall drops" in w for w in why)
    assert decide(m(0.90, 0.01, a=0.96, b=0.70), m(0.85, 0.01, a=1.0, b=0.60))[0]


def test_legit_families_and_errors():
    inc = {"recall": 0.5, "fpr": 0.0, "per_family": {"legit_plain": {"n": 5, "fpr": 0.0}}}
    assert decide({"recall": 0.6, "fpr": 0.0, "per_family": {}}, inc)[0]
    assert decide({"error": "boom"}, None) == (False, ["candidate eval failed: boom"])
