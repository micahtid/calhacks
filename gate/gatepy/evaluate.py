"""gate-eval: run the full Gate (Layer 1 then Layer 2) over labeled Snapshots and report metrics."""
import argparse
import json
import sys

from gatepy.context import Ctx, load_ctx
from gatepy.contracts import Snapshot
from gatepy.dataset import GateInputError, featurize, load_snapshots
from gatepy.layer1_bridge import run_layer1
from gatepy.model_io import Model, load
from gatepy.registry import discover, select
from gatepy.splits import split_of


def decide(model: Model, snaps: list[Snapshot], ctx: Ctx, l1: list[dict] | None = None) -> list[dict]:
    """One decision row per snapshot (decision JSON from interfaces.md, plus id/family/label)."""
    l1 = l1 if l1 is not None else run_layer1(snaps)
    X = featurize(snaps, ctx, select(model.features))
    risk = model.predict_risk(X)
    contrib = model.contributions(X)
    rows = []
    for i, s in enumerate(snaps):
        r = float(risk[i])
        if not l1[i]["pass"]:
            decision, layer = "skip", "L1"
        elif r >= model.threshold:
            decision, layer = "skip", "L2"
        else:
            decision, layer = "buy", None
        rows.append({
            "id": s.id, "family": s.family, "label": s.label, "decision": decision, "layer": layer,
            "l1_failures": l1[i]["failures"], "risk": round(r, 6), "threshold": model.threshold,
            "model_id": model.model_id, "top3": model.top3(X[i], contrib[i]),
        })
    return rows


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def metrics(rows: list[dict], with_rows: bool = False) -> dict:
    rows = [r for r in rows if r["label"] in ("scam", "legit")]
    scam = [r for r in rows if r["label"] == "scam"]
    legit = [r for r in rows if r["label"] == "legit"]
    skipped = lambda rs: sum(r["decision"] == "skip" for r in rs)  # noqa: E731
    scam_l2 = [r for r in scam if r["layer"] != "L1"]
    legit_l2 = [r for r in legit if r["layer"] != "L1"]
    per_family = {}
    for fam in sorted({r["family"] for r in rows}):
        rs = [r for r in rows if r["family"] == fam]
        key = "recall" if rs[0]["label"] == "scam" else "fpr"
        per_family[fam] = {"n": len(rs), key: _rate(skipped(rs), len(rs))}
    out = {
        "n": len(rows), "n_scam": len(scam), "n_legit": len(legit),
        "recall": _rate(skipped(scam), len(scam)), "fpr": _rate(skipped(legit), len(legit)),
        "recall_l2": _rate(skipped(scam_l2), len(scam_l2)), "fpr_l2": _rate(skipped(legit_l2), len(legit_l2)),
        "l1_catches": len(scam) - len(scam_l2), "l1_false_blocks": len(legit) - len(legit_l2),
        "per_family": per_family,
    }
    if with_rows:
        out["rows"] = [{k: r[k] for k in ("id", "family", "label", "decision", "layer", "risk", "top3")} for r in rows]
    return out


def evaluate(model: Model, snaps: list[Snapshot], ctx: Ctx, l1: list[dict] | None = None,
             with_rows: bool = False) -> dict:
    return {"model_id": model.model_id, **metrics(decide(model, snaps, ctx, l1), with_rows)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate-eval", description=__doc__)
    ap.add_argument("--model", default="promoted")
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--split", choices=["train", "val", "all"], default="all")
    ap.add_argument("--rows", action="store_true")
    a = ap.parse_args(argv)
    try:
        discover()
        model = load(a.model)
        snaps = load_snapshots(a.data)
        if a.split != "all":
            snaps = [s for s in snaps if split_of(s.id) == a.split]
        result = evaluate(model, snaps, load_ctx(), with_rows=a.rows)
    except (GateInputError, FileNotFoundError, KeyError) as e:
        print(json.dumps({"error": str(e)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
