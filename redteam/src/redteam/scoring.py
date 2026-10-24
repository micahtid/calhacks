"""Decisions vs. answer keys -> issue #1 RoundMetrics (Wilson intervals on every rate).

A row is {"listing_id", "label", "family", "attacker_knowledge", "decision": GateDecision as dict}.

- recall / fpr: full Gate on scams / on every legit listing (synthetic legit_* and real).
- layer2_fpr: false blocks among legit listings that pass Layer 1 (the trained model's mistakes).
- fpr_real: false blocks on real listings only (family "real").
- layer1_catches: scams Layer 1 stopped. layer2_recall: of the scams that passed Layer 1, the share Layer 2 stopped.
- per_family: skip rate per family (recall for scam families, false-block rate for legit ones).
- adaptive_recall: recall on white_box attacks (None when there are none).
"""
from collections import defaultdict

from calhacks_contracts import RoundMetrics, rate


def _skipped(rows) -> int:
    return sum(r["decision"]["decision"] == "skip" for r in rows)


def metrics(rows: list[dict]) -> RoundMetrics:
    scam = [r for r in rows if r["label"] == "scam"]
    legit = [r for r in rows if r["label"] == "legit"]
    real = [r for r in legit if r["family"] == "real"]
    passed_l1 = [r for r in scam if r["decision"]["decided_by"] != "layer1"]
    legit_l2 = [r for r in legit if r["decision"]["decided_by"] != "layer1"]
    white = [r for r in scam if r.get("attacker_knowledge") == "white_box"]
    fam = defaultdict(list)
    for r in rows:
        fam[r["family"]].append(r)
    return RoundMetrics(
        layer1_catches=sum(r["decision"]["decided_by"] == "layer1" for r in scam),
        layer2_recall=rate(_skipped(passed_l1), len(passed_l1)),
        fpr_real=rate(_skipped(real), len(real)),
        per_family={f: rate(_skipped(rs), len(rs)) for f, rs in sorted(fam.items())},
        adaptive_recall=rate(_skipped(white), len(white)) if white else None,
        recall=rate(_skipped(scam), len(scam)),
        fpr=rate(_skipped(legit), len(legit)),
        layer2_fpr=rate(_skipped(legit_l2), len(legit_l2)),
    )


def misses(rows: list[dict]) -> list[dict]:
    """Rows the Gate got wrong: scams bought and legit listings skipped."""
    return [r for r in rows if (r["label"] == "scam") == (r["decision"]["decision"] == "buy")]
