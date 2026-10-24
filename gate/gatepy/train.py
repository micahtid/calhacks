"""gate-train: train Layer 2 on rows that pass Layer 1, pick the threshold on validation, write a model file."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import yaml
from sklearn.linear_model import LogisticRegression

from gatepy import GATE_DIR, MODELS
from gatepy.context import load_ctx
from gatepy.contracts import examples, holdout_families
from gatepy.dataset import GateInputError, data_hash, featurize, load_snapshots
from gatepy.evaluate import evaluate
from gatepy.layer1_bridge import run_layer1
from gatepy.model_io import from_meta, save
from gatepy.registry import Feature, discover, feature_code_hash, select, self_test
from gatepy.splits import split_of

DEFAULT_CONFIG = GATE_DIR / "train_config.yaml"


def fit_lightgbm(X, y, feats: list[Feature], cfg: dict) -> dict:
    p = dict(cfg.get("params", {}))
    rounds = int(p.pop("n_estimators", 200))
    params = {
        "objective": "binary", "verbose": -1, "deterministic": True, "force_row_wise": True,
        "num_threads": 1, "seed": int(cfg.get("seed", 7)),
        "monotone_constraints": [f.monotone for f in feats], "monotone_constraints_method": "advanced",
        **p,
    }
    ds = lgb.Dataset(X, label=y, feature_name=[f.name for f in feats], free_raw_data=False)
    booster = lgb.train(params, ds, num_boost_round=rounds)
    return {"booster": booster.model_to_string(), "coef": None}


def fit_logreg(X, y, feats: list[Feature], cfg: dict) -> dict:
    """Standardized logistic regression. A feature whose weight breaks its monotone direction is dropped (weight 0)."""
    mean = X.mean(axis=0)
    scale = X.std(axis=0)
    scale[scale == 0] = 1.0
    Z = (X - mean) / scale
    active = list(range(len(feats)))
    weights = np.zeros(len(feats))
    intercept = 0.0
    while active:
        clf = LogisticRegression(C=float(cfg.get("params", {}).get("C", 1.0)), max_iter=2000)
        clf.fit(Z[:, active], y)
        w = clf.coef_[0]
        bad = [j for j, i in enumerate(active) if feats[i].monotone and np.sign(w[j]) == -feats[i].monotone]
        if not bad:
            weights[active] = w
            intercept = float(clf.intercept_[0])
            break
        active = [i for j, i in enumerate(active) if j not in bad]
    return {"booster": None, "coef": {"weights": weights.tolist(), "intercept": intercept,
                                      "mean": mean.tolist(), "scale": scale.tolist()}}


FITTERS = {"lightgbm": fit_lightgbm, "logreg": fit_logreg}


def pick_threshold(risk_legit: np.ndarray, max_fpr: float) -> float:
    """Lowest cut (skip if risk >= cut) that blocks at most max_fpr of legit rows."""
    if len(risk_legit) == 0:
        return 0.5
    desc = np.sort(risk_legit)[::-1]
    allowed = int(np.floor(max_fpr * len(desc) + 1e-9))
    if allowed >= len(desc):
        return 0.0
    return float(min(1.0, desc[allowed] + 1e-9))


def train(data: list[str], round_: int, config: Path = DEFAULT_CONFIG, out: Path = MODELS) -> dict:
    config = Path(config)
    cfg_src = config.read_text(encoding="utf-8")
    cfg = yaml.safe_load(cfg_src) or {}
    kind = cfg.get("kind", "lightgbm")
    if kind not in FITTERS:
        raise GateInputError(f"unknown model kind {kind!r}")

    discover()
    try:
        feats = select(cfg.get("features", "all"), cfg.get("exclude_features", []))
    except KeyError as e:
        raise GateInputError(str(e)) from e
    if not feats:
        raise GateInputError("no features selected")
    ctx = load_ctx()
    errors = self_test(feats, examples(), ctx)
    if errors:
        raise GateInputError("feature self-test failed: " + "; ".join(errors[:5]))

    snaps = [s for s in load_snapshots(data) if s.label in ("scam", "legit")]
    leaked = sorted({s.family for s in snaps} & holdout_families())
    if leaked:
        raise GateInputError(f"training data contains holdout families {leaked}")

    l1 = run_layer1(snaps)
    split = [split_of(s.id) for s in snaps]
    tr = [i for i, s in enumerate(snaps) if split[i] == "train" and l1[i]["pass"]]
    va = [i for i, s in enumerate(snaps) if split[i] == "val"]
    y = np.array([s.label == "scam" for s in snaps], dtype=int)
    if len(set(y[tr])) < 2:
        raise GateInputError("training rows that pass Layer 1 need both scam and legit examples")

    X = featurize(snaps, ctx, feats)
    fitted = FITTERS[kind](X[tr], y[tr], feats, cfg)

    meta = {
        "model_id": None, "round": round_, "kind": kind,
        "features": [f.name for f in feats], "monotone": [f.monotone for f in feats],
        "threshold": 0.5, **fitted,
        "train_data_hash": data_hash([snaps[i] for i in tr]), "feature_code_hash": feature_code_hash(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "val_metrics": None,
        "threshold_rule": {"max_fpr": float(cfg.get("threshold", {}).get("max_fpr", 0.02)), "on": "val fpr_l2"},
        "n_train": len(tr), "n_val": len(va),
        "config_source": cfg_src, "config_is_default": config.resolve() == DEFAULT_CONFIG.resolve(),
        "feature_sources": {p.name: p.read_text(encoding="utf-8") for p in sorted((GATE_DIR / "features").glob("*.py"))},
    }
    model = from_meta(meta)

    # Threshold on validation legit rows that reach Layer 2; fall back to training rows if val has none.
    va_l2_legit = [i for i in va if l1[i]["pass"] and y[i] == 0] or [i for i in tr if y[i] == 0]
    meta["threshold"] = pick_threshold(model.predict_risk(X[va_l2_legit]), meta["threshold_rule"]["max_fpr"])

    digest = hashlib.sha256(json.dumps([meta["booster"], meta["coef"], meta["threshold"], meta["train_data_hash"],
                                        meta["feature_code_hash"], cfg_src]).encode()).hexdigest()
    meta["model_id"] = f"r{round_}-{digest[:6]}"
    model = from_meta(meta)
    meta["val_metrics"] = evaluate(model, [snaps[i] for i in va], ctx, [l1[i] for i in va])
    save(meta, out)
    return {"model_id": meta["model_id"], "round": round_, "kind": kind, "features": meta["features"],
            "n_train": len(tr), "n_val": len(va), "threshold": round(meta["threshold"], 6), "val": meta["val_metrics"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate-train", description=__doc__)
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--out", type=Path, default=MODELS)
    a = ap.parse_args(argv)
    try:
        result = train(a.data, a.round, a.config, a.out)
    except GateInputError as e:
        print(json.dumps({"error": str(e)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
