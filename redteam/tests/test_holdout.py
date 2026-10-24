import json

import pytest

from redteam import gate_stub, holdout
from redteam.config import HOLDOUT, HOLDOUT_FILE
from redteam.generate import run_spec


def test_build_never_writes_to_mongo_and_is_encrypted(repo, fake_client):
    before = {c: repo.db[c].count_documents({}) for c in ("listings", "answer_keys", "gen", "cases", "crs_results")}
    meta = holdout.build(per_family=8, slice_n=3, client=fake_client(), r=repo)
    after = {c: repo.db[c].count_documents({}) for c in before}
    assert before == after
    assert set(meta["by_family"]) >= {"urgency_pressure", "lookalike_domain"}
    raw = HOLDOUT_FILE.read_bytes()
    assert b"listing_id" not in raw and b"urgency" not in raw
    with pytest.raises(RuntimeError, match="built once"):
        holdout.build(per_family=2, slice_n=1, client=fake_client(), r=repo)


def test_totals_only(repo, fake_client):
    for fam in ("too_cheap", "payment_mismatch"):
        run_spec({"spec_id": f"S-{fam}", "family": fam, "n": 30, "legit_ratio": 0.4, "mode": "mutate_real"},
                 round_=1, r=repo, client=fake_client())
    model = gate_stub.train(1)
    holdout.build(per_family=8, slice_n=3, client=fake_client(), r=repo)
    t = holdout.totals(model["model_id"], r=repo)
    assert set(t.model_dump()) == {"model_id", "recall", "fpr"}
    assert t.recall.n > 0


def test_holdout_dir_must_be_outside_repo(monkeypatch, repo):
    from redteam import config
    monkeypatch.setattr(holdout, "HOLDOUT", config.REPO / "x")
    with pytest.raises(RuntimeError, match="outside the repo"):
        holdout.build(r=repo)


def test_unavailable_without_build():
    assert not holdout.available() and holdout.totals("anything") is None
    assert not HOLDOUT_FILE.exists() and json.dumps(str(HOLDOUT))
