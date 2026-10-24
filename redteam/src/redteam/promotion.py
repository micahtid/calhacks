"""Model promotion (plan C6), decided in code. The coordinator can ask; it can't override.

Promote only if, on the same current validation set as the incumbent:
  - recall improves,
  - FPR stays <= MAX_FPR,
  - no attack family's recall drops by more than MAX_FAMILY_DROP.
With no incumbent, only the FPR bound applies. On promotion, holdout totals are recorded (never returned as rows).
"""
import json
from datetime import datetime, timezone

from redteam import gate_client
from redteam.config import MAX_FAMILY_DROP, MAX_FPR, MODELS_DIR

PROMOTED = MODELS_DIR / "promoted.json"


def current() -> dict:
    return json.loads(PROMOTED.read_text()) if PROMOTED.exists() else {"model_id": None, "history": []}


def decide(candidate: dict, incumbent: dict | None) -> tuple[bool, list[str]]:
    """Both arguments are <metrics> dicts on the same val set. Returns (promote, reasons)."""
    reasons = []
    if candidate.get("error"):
        return False, [f"candidate eval failed: {candidate['error']}"]
    if candidate["fpr"] > MAX_FPR:
        reasons.append(f"val FPR {candidate['fpr']:.3f} > {MAX_FPR}")
    if incumbent:
        if candidate["recall"] <= incumbent["recall"]:
            reasons.append(f"val recall {candidate['recall']:.3f} does not beat incumbent {incumbent['recall']:.3f}")
        for fam, old in incumbent["per_family"].items():
            new = candidate["per_family"].get(fam)
            if "recall" in old and new and old["recall"] - new.get("recall", 0) > MAX_FAMILY_DROP:
                reasons.append(f"{fam} recall drops {old['recall']:.2f} -> {new['recall']:.2f}")
    return not reasons, reasons


def promote(model_id: str, val_paths, holdout_totals=None) -> dict:
    """Evaluate candidate and incumbent on the current val set, apply decide(), record the outcome."""
    state = current()
    cand = gate_client.evaluate(model_id, val_paths, split="val")
    inc = gate_client.evaluate(state["model_id"], val_paths, split="val") if state["model_id"] else None
    ok, reasons = decide(cand, inc)
    result = {"model_id": model_id, "promoted": ok, "reasons": reasons, "incumbent": state["model_id"],
              "candidate_val": {k: cand.get(k) for k in ("recall", "fpr", "recall_l2", "fpr_l2")},
              "incumbent_val": inc and {k: inc.get(k) for k in ("recall", "fpr", "recall_l2", "fpr_l2")}}
    if ok:
        model = json.loads((MODELS_DIR / f"{model_id}.json").read_text())
        entry = {"model_id": model_id, "round": model.get("round"),
                 "promoted_at": datetime.now(timezone.utc).isoformat(), "val": cand,
                 "holdout": holdout_totals(model_id) if holdout_totals else None}
        state = {"model_id": model_id, "history": state["history"] + [entry]}
        PROMOTED.write_text(json.dumps(state, indent=1))
        result["holdout"] = entry["holdout"]
    return result
