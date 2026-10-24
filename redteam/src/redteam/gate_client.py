"""The red team's only door into the Gate: gate-train and gate-eval (contracts/interfaces.md).

JOIN: once feat/gate is merged, change GATE_BACKEND to "real". REDTEAM_GATE=stub|real overrides it.
"""
import json
import os
import subprocess
from pathlib import Path

from redteam import gate_stub
from redteam.config import GATE_DIR, REPO

GATE_BACKEND = os.environ.get("REDTEAM_GATE", "stub")


def _run(args: list[str], timeout: int = 1800) -> dict:
    proc = subprocess.run(["uv", "run", "--project", str(GATE_DIR), *args], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout)
    out = proc.stdout.strip()
    try:
        return json.loads(out[out.index("{"):])  # the CLIs print exactly one JSON object
    except ValueError:
        return {"error": f"{args[0]} exited {proc.returncode} without JSON: {proc.stderr[-800:]}"}


def train(paths: list[Path], round_: int) -> dict:
    if GATE_BACKEND == "stub":
        return gate_stub.train(paths, round_)
    return _run(["gate-train", "--data", *map(str, paths), "--round", str(round_)])


def evaluate(model_id: str, paths: list[Path], split: str = "all", rows: bool = False) -> dict:
    if GATE_BACKEND == "stub":
        return gate_stub.evaluate(model_id, paths, split, rows)
    args = ["gate-eval", "--model", model_id, "--data", *map(str, paths), "--split", split]
    return _run(args + (["--rows"] if rows else []))
