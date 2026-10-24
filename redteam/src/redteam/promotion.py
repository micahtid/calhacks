"""Model promotion (plan C6), decided in code. The coordinator can ask; it can't override.

Promote only if, on the current validation set, compared with the incumbent:
  - full-Gate recall improves,
  - full-Gate false-block rate stays <= MAX_FPR,
  - no scam family's recall drops by more than MAX_FAMILY_DROP.
With no incumbent, only the false-block bound applies. On promotion the holdout totals are recorded in
gate/models/promoted.json (same shape gatepy.model_io.set_promoted writes). On refusal the promoted model's feature
code is restored, since the coordinator edits gate/features/ in place.
"""
import json
from collections.abc import Callable
from datetime import datetime, timezone

from calhacks_contracts import HoldoutTotals, PromotionDecision
from calhacks_contracts.families import families

from redteam import gate_client
from redteam.config import MAX_FAMILY_DROP, MAX_FPR, MODELS_DIR


def promoted_file():
    return MODELS_DIR / "promoted.json"


def current() -> dict:
    p = promoted_file()
    return json.loads(p.read_text()) if p.exists() else {"model_id": None, "history": []}


def decide(candidate: dict, incumbent: dict | None) -> tuple[bool, list[str]]:
    """Both are RoundMetrics dicts on the same val set. Returns (promote, reasons for refusal)."""
    reasons = []
    fpr, recall = candidate["fpr"]["value"], candidate["recall"]["value"]
    if fpr > MAX_FPR:
        reasons.append(f"val false-block rate {fpr:.3f} > {MAX_FPR}")
    if incumbent:
        old = incumbent["recall"]["value"]
        if recall <= old:
            reasons.append(f"val recall {recall:.3f} does not beat incumbent {old:.3f}")
        fams = families()
        for fam, o in incumbent["per_family"].items():
            if fams.get(fam, {}).get("label") != "scam":
                continue
            n = candidate["per_family"].get(fam)
            if n and o["value"] - n["value"] > MAX_FAMILY_DROP:
                reasons.append(f"{fam} recall drops {o['value']:.2f} -> {n['value']:.2f}")
    return not reasons, reasons


def promote(model_id: str, holdout_totals: Callable[[str], HoldoutTotals | None] | None = None) -> dict:
    """Evaluate candidate and incumbent on the current val set, apply decide(), record the outcome."""
    state = current()
    cand = gate_client.evaluate(model_id, split="val")
    if cand.get("error"):
        return {"model_id": model_id, "promoted": False, "reasons": [cand["error"]], "incumbent": state["model_id"],
                "decision": PromotionDecision(action="revert", reason=cand["error"]).model_dump()}
    inc = gate_client.evaluate(state["model_id"], split="val") if state["model_id"] else None
    ok, reasons = decide(cand["metrics"], inc and not inc.get("error") and inc["metrics"])
    decision = PromotionDecision(action="promote" if ok else "revert",
                                 reason="beats incumbent on validation within the false-block bound" if ok else
                                 "; ".join(reasons))
    result = {"model_id": model_id, "promoted": ok, "reasons": reasons, "incumbent": state["model_id"],
              "candidate_val": cand["metrics"], "incumbent_val": inc and inc.get("metrics"),
              "decision": decision.model_dump()}
    if ok:
        holdout = holdout_totals(model_id) if holdout_totals else None
        entry = {"model_id": model_id, "round": _round_of(model_id),
                 "promoted_at": datetime.now(timezone.utc).isoformat(), "val": cand["metrics"],
                 "holdout": holdout.model_dump(mode="json") if holdout else None}
        state = {"model_id": model_id, "history": state["history"] + [entry]}
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        promoted_file().write_text(json.dumps(state, indent=1))
        result["holdout_recorded"] = holdout is not None
    elif state["model_id"]:
        gate_client.restore_features(state["model_id"])
    return result


def holdout_for_current() -> dict | None:
    """Holdout totals recorded for the current promoted model (RoundInput.holdout_totals), or None."""
    state = current()
    for h in reversed(state["history"]):
        if h["model_id"] == state["model_id"]:
            return h.get("holdout")
    return None


def _round_of(model_id: str) -> int | None:
    try:
        return json.loads((MODELS_DIR / f"{model_id}.json").read_text()).get("round")
    except (FileNotFoundError, json.JSONDecodeError):
        return None
