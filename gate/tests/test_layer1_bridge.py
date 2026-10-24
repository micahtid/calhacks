from gatepy.contracts import examples
from gatepy.layer1_bridge import run_layer1


def test_bridge_runs_typescript_rules_on_examples():
    snaps = examples()
    results = {r["id"]: r for r in run_layer1(snaps)}
    assert [r for r in results] == [s.id for s in snaps]
    assert results["ex-legit-plain"] == {"id": "ex-legit-plain", "pass": True, "failures": []}
    assert results["ex-payment-mismatch"]["failures"] == ["L1_PAYTO_MISMATCH"]
    assert results["ex-lookalike-payto"]["failures"] == ["L1_PAYTO_LOOKALIKE"]
    assert results["ex-bait-and-switch"]["failures"] == ["L1_ITEM_MISMATCH"]
    for text_scam in ("ex-too-cheap", "ex-prompt-injection", "ex-fake-reviews"):
        assert results[text_scam]["pass"], "text tactics are Layer 2's job"


def test_bridge_handles_empty_batch():
    assert run_layer1([]) == []
