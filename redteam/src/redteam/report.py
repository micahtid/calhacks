"""Rounds table for the demo and dashboard: attack success, validation, holdout totals and spend per round.

Usage: uv run --project redteam python -m redteam.report [--json]
"""
import argparse
import json
import sys

from redteam.config import DATA, ROUNDS
from redteam.promotion import current


def _read(path):
    return json.loads(path.read_text()) if path.exists() else None


def rows() -> list[dict]:
    history = {h["round"]: h for h in current()["history"]}
    out = []
    for d in sorted((p for p in ROUNDS.glob("R*") if p.name[1:].isdigit()), key=lambda p: int(p.name[1:])):
        r = int(d.name[1:])
        score, promo, usage, budget = (_read(d / f) for f in ("score.json", "promotion.json", "usage.json",
                                                              "budget.json"))
        h = history.get(r)
        out.append({
            "round": r,
            "attack_success": score and score["attack_success"],
            "scored_model": score and score["model_id"],
            "candidate": promo and promo["model_id"],
            "promoted": promo and promo["promoted"],
            "refused_because": promo and promo["reasons"],
            "val_recall": promo and promo["candidate_val"]["recall"],
            "val_fpr": promo and promo["candidate_val"]["fpr"],
            "holdout_recall": h and h["holdout"] and h["holdout"]["recall"],
            "holdout_fpr": h and h["holdout"] and h["holdout"]["fpr"],
            "holdout_recall_l2": h and h["holdout"] and h["holdout"]["recall_l2"],
            "gen_tokens": budget and budget["gen_tokens"],
            "coord_tokens": usage and usage["usage"] and sum(v or 0 for k, v in usage["usage"].items()
                                                            if k in ("input_tokens", "output_tokens")),
            "hook_denials": usage and usage["hook_denials"],
        })
    return out


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.1%}" if v <= 1 else f"{v:.0f}"
    if isinstance(v, list):
        return "; ".join(v) or "-"
    return str(v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    data = rows()
    (DATA / "report.json").write_text(json.dumps(data, indent=1))
    if a.json:
        print(json.dumps(data, indent=1))
        return 0
    cols = ["round", "attack_success", "candidate", "promoted", "val_recall", "val_fpr", "holdout_recall",
            "holdout_fpr", "gen_tokens", "coord_tokens", "hook_denials"]
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in data:
        print("| " + " | ".join(fmt(r[c]) for c in cols) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
