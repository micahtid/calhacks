import json

import numpy as np
import pytest

from gatepy import GATE_DIR
from gatepy.dataset import GateInputError, load_snapshots
from gatepy.evaluate import evaluate
from gatepy.evaluate import main as eval_main
from gatepy.fixtures import build
from gatepy.model_io import load
from gatepy.registry import feature, select
from gatepy.train import main as train_main
from gatepy.train import pick_threshold, train

METRIC_KEYS = {"n", "n_scam", "n_legit", "recall", "fpr", "recall_l2", "fpr_l2", "l1_catches", "per_family"}


def test_lightgbm_trains_and_meets_fpr_rule(trained):
    assert trained["model_id"].startswith("r1-")
    assert trained["kind"] == "lightgbm"
    val = trained["val"]
    assert METRIC_KEYS <= set(val)
    assert val["fpr_l2"] <= 0.02
    assert val["recall"] >= 0.8
    assert 0 < trained["threshold"] <= 1


def test_r0_baseline_trains(baseline):
    assert baseline["model_id"].startswith("r0-")
    assert baseline["kind"] == "logreg"
    assert baseline["features"] == ["price_ratio", "seller_age_years", "injection_hits"]
    assert baseline["val"]["fpr_l2"] <= 0.02


def test_model_id_is_deterministic(trained, fixture_file, tmp_path):
    again = train([str(fixture_file)], 1, GATE_DIR / "train_config.yaml", tmp_path)
    assert again["model_id"] == trained["model_id"]


def test_model_file_matches_contract(trained, models_dir):
    meta = load(trained["model_id"], models_dir).meta
    for key in ("model_id", "round", "kind", "features", "monotone", "threshold", "booster", "coef",
                "train_data_hash", "feature_code_hash", "created_at", "val_metrics"):
        assert key in meta
    assert len(meta["monotone"]) == len(meta["features"])
    assert "price.py" in meta["feature_sources"]


def test_eval_rows_have_top3(trained, models_dir, fixture_file, ctx):
    model = load(trained["model_id"], models_dir)
    result = evaluate(model, load_snapshots([fixture_file]), ctx, with_rows=True)
    assert result["n"] == 300
    row = next(r for r in result["rows"] if r["layer"] == "L2")
    assert len(row["top3"]) == 3 and all(len(t) == 3 for t in row["top3"])
    l1 = [r for r in result["rows"] if r["layer"] == "L1"]
    assert l1 and all(r["label"] == "scam" for r in l1)


def test_risk_never_falls_as_price_falls(trained, models_dir, ex, ctx):
    """G3: monotone constraint on price_ratio, checked by sweeping the price of one listing."""
    model = load(trained["model_id"], models_dir)
    feats = select(model.features)
    from gatepy.dataset import featurize
    risks = []
    for factor in np.linspace(0.1, 1.5, 15):
        s = ex["ex-legit-plain"].model_copy(deep=True)
        s.item.priceUsd = round(2.5 * factor, 2)
        risks.append(float(model.predict_risk(featurize([s], ctx, feats))[0]))
    assert all(a >= b - 1e-12 for a, b in zip(risks, risks[1:])), risks


def test_pick_threshold():
    legit = np.array([0.01, 0.02, 0.05, 0.1, 0.9] + [0.0] * 95)
    t = pick_threshold(legit, 0.02)
    assert (legit >= t).sum() <= 2
    assert t <= 0.1 + 1e-6
    assert pick_threshold(np.array([]), 0.02) == 0.5


def test_train_rejects_holdout_families(tmp_path):
    rows = build(n=40, seed=2)
    rows[0]["family"] = "urgency_pressure"
    p = tmp_path / "bad.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(GateInputError, match="holdout"):
        train([str(p)], 1, GATE_DIR / "train_config.yaml", tmp_path)


def test_train_fails_on_broken_feature(fixture_file, tmp_path, monkeypatch):
    import gatepy.train as train_mod
    from gatepy.registry import discover

    def discover_with_broken():
        discover()

        @feature("t_broken")
        def t_broken(s, c):
            return float("inf")

    monkeypatch.setattr(train_mod, "discover", discover_with_broken)
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("kind: logreg\nfeatures: [price_ratio, t_broken]\n", encoding="utf-8")
    with pytest.raises(GateInputError, match="self-test failed: t_broken"):
        train([str(fixture_file)], 1, cfg, tmp_path)
    cfg.write_text("kind: logreg\nfeatures: [price_ratio, no_such_feature]\n", encoding="utf-8")
    with pytest.raises(GateInputError, match="unknown features"):
        train([str(fixture_file)], 1, cfg, tmp_path)


def test_clis_print_json_and_exit_codes(trained, models_dir, fixture_file, capsys, monkeypatch):
    assert train_main(["--data", str(fixture_file), "--round", "1", "--out", str(models_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["model_id"] == trained["model_id"]
    monkeypatch.setattr("gatepy.evaluate.load", lambda mid: load(mid, models_dir))
    assert eval_main(["--model", trained["model_id"], "--data", str(fixture_file), "--split", "val"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert METRIC_KEYS <= set(out) and "rows" not in out
    assert eval_main(["--model", "no-such-model", "--data", str(fixture_file)]) == 2
    assert "error" in json.loads(capsys.readouterr().out)
    assert train_main(["--data", "no/such/path", "--round", "1", "--out", str(models_dir)]) == 2
    assert "error" in json.loads(capsys.readouterr().out)
