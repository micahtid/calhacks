"""Run the TypeScript Layer 1 rules (the single source of truth) over a batch of GateInputs via gate-l1."""
import json
import os
import shutil
import subprocess

from calhacks_contracts import Check, GateInput

from gatepy import CONTRACTS, LAYER1_CLI


def run_layer1(inputs: list[GateInput]) -> list[list[Check]]:
    """The Layer 1 checks for each input, same order."""
    if not inputs:
        return []
    node = os.environ.get("NODE") or shutil.which("node")
    if not node:
        raise RuntimeError("node not found; Layer 1 needs Node 22+ (set NODE to override)")
    proc = subprocess.run(
        [node, str(LAYER1_CLI), "--contracts", str(CONTRACTS)],
        input="".join(x.model_dump_json() + "\n" for x in inputs),
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gate-l1 failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    results = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    if [r["listing_id"] for r in results] != [x.listing.listing_id for x in inputs]:
        raise RuntimeError("gate-l1 output does not line up with its input")
    return [[Check.model_validate(c) for c in r["checks"]] for r in results]


def passed(checks: list[Check]) -> bool:
    return all(c.passed for c in checks)


def failed_rule(checks: list[Check]) -> str | None:
    return next((c.rule for c in checks if not c.passed), None)
