from collections import Counter

from jsonschema import Draft202012Validator

from gatepy.contracts import holdout_families, load_json
from gatepy.fixtures import build
from gatepy.splits import split_of


def test_examples_load_as_snapshots(ex):
    assert len(ex) == 8
    assert ex["ex-prompt-injection"].tactic_evidence


def test_fixtures_match_json_schema():
    validator = Draft202012Validator(load_json("snapshot.schema.json"))
    for row in build(n=120, seed=3):
        errors = list(validator.iter_errors(row))
        assert not errors, (row["id"], errors[0].message)


def test_fixtures_are_deterministic_and_skip_holdout_families():
    a, b = build(n=80, seed=5), build(n=80, seed=5)
    assert a == b
    assert build(n=80, seed=6) != a
    fams = Counter(r["family"] for r in a)
    assert not set(fams) & holdout_families()
    assert {r["label"] for r in a} == {"scam", "legit"}


def test_split_rule_matches_contract():
    assert split_of("ex-legit-plain") in ("train", "val")
    assert split_of("x") == split_of("x")
    share = sum(split_of(f"id-{i}") == "val" for i in range(5000)) / 5000
    assert 0.17 < share < 0.23
