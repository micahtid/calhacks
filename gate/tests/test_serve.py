import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gatepy import GATE_DIR
from gatepy.model_io import read_promoted, restore_features, set_promoted
from gatepy.serve import DECISION_KEYS, Gate, make_router


def test_score_returns_decision_contract(trained, models_dir, ex):
    gate = Gate(trained["model_id"], models_dir)
    d = gate.score(ex["ex-legit-plain"])
    assert tuple(d) == DECISION_KEYS
    assert d["decision"] == "buy" and d["layer"] is None
    d = gate.score(ex["ex-payment-mismatch"].model_dump())
    assert d == {**d, "decision": "skip", "layer": "L1", "l1_failures": ["L1_PAYTO_MISMATCH"]}


def test_score_handles_item_without_median(trained, models_dir, ex):
    s = ex["ex-legit-plain"].model_copy(deep=True)
    s.item.id = s.checkout_item_id = "item-from-another-source"
    d = Gate(trained["model_id"], models_dir).score(s)
    assert d["l1_failures"] == [] and 0.0 <= d["risk"] <= 1.0


def test_router_fails_closed(trained, models_dir, ex):
    app = FastAPI()
    app.include_router(make_router(Gate(trained["model_id"], models_dir)))
    client = TestClient(app)
    ok = client.post("/gate/risk", json=ex["ex-legit-plain"].model_dump())
    assert ok.status_code == 200 and ok.json()["model_id"] == trained["model_id"]
    bad = client.post("/gate/risk", json={"id": "broken"})
    assert bad.status_code == 503 and bad.json()["decision"] == "skip"


def test_promote_and_restore_features(trained, baseline, models_dir, tmp_path):
    set_promoted(baseline["model_id"], models_dir=models_dir)
    pointer = set_promoted(trained["model_id"], holdout={"recall": 0.9}, models_dir=models_dir)
    assert read_promoted(models_dir)["model_id"] == trained["model_id"]
    assert [h["model_id"] for h in pointer["history"]][-2:] == [baseline["model_id"], trained["model_id"]]

    gate_copy = tmp_path / "gate"
    shutil.copytree(GATE_DIR / "features", gate_copy / "features", ignore=shutil.ignore_patterns("__pycache__"))
    (gate_copy / "train_config.yaml").write_text("kind: logreg\n", encoding="utf-8")
    (gate_copy / "features" / "price.py").write_text("# edited by a rejected candidate\n", encoding="utf-8")
    (gate_copy / "features" / "new_feature.py").write_text("# added by a rejected candidate\n", encoding="utf-8")
    written = restore_features(trained["model_id"], models_dir, gate_copy)
    assert "features/new_feature.py (removed)" in written
    assert not (gate_copy / "features" / "new_feature.py").exists()
    assert (gate_copy / "features" / "price.py").read_text(encoding="utf-8") == \
        (GATE_DIR / "features" / "price.py").read_text(encoding="utf-8")
    assert (gate_copy / "train_config.yaml").read_text(encoding="utf-8").startswith("# Layer 2 training config")
