"""Run the TypeScript Layer 1 rules (the single source of truth) over a batch of Snapshots via gate-l1."""
import json
import os
import shutil
import subprocess

from gatepy import CONTRACTS, LAYER1_CLI
from gatepy.contracts import Snapshot


def run_layer1(snaps: list[Snapshot]) -> list[dict]:
    """One {"id", "pass", "failures"} per snapshot, same order."""
    if not snaps:
        return []
    node = os.environ.get("NODE") or shutil.which("node")
    if not node:
        raise RuntimeError("node not found; Layer 1 needs Node 22+ (set NODE to override)")
    proc = subprocess.run(
        [node, str(LAYER1_CLI), "--contracts", str(CONTRACTS)],
        input="".join(s.model_dump_json() + "\n" for s in snaps),
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gate-l1 failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    results = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    if [r["id"] for r in results] != [s.id for s in snaps]:
        raise RuntimeError("gate-l1 output does not line up with its input")
    return results
