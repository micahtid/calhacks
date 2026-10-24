"""The red team's only door into the Gate (contracts/interfaces.md).

Backends: "stub" (redteam.gate_stub) until feat/gate is merged, then "real" (gate-train / gate-eval CLIs, and gatepy
in-process for the holdout). JOIN: set GATE_BACKEND's default to "real". REDTEAM_GATE=stub|real overrides it.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from calhacks_contracts import AnswerKey, Case, Listing
from calhacks_contracts.db import ReferenceSet

from redteam import gate_stub
from redteam.config import GATE_DIR, MODELS_DIR, REPO

GATE_BACKEND = os.environ.get("REDTEAM_GATE", "stub")
# Gate subprocesses run coordinator-written feature code; they never need the holdout.
SUBPROCESS_DROP = ("HOLDOUT_KEY", "CALHACKS_HOLDOUT")


def subprocess_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in SUBPROCESS_DROP}
    env["UV_SYSTEM_CERTS"] = "1"
    return env


def _run(args: list[str], timeout: int = 1800) -> dict:
    proc = subprocess.run(["uv", "run", "--project", str(GATE_DIR), *args], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout, env=subprocess_env())
    out = proc.stdout.strip()
    try:
        return json.loads(out[out.index("{"):])  # the CLIs print exactly one JSON object
    except ValueError:
        return {"error": f"{args[0]} exited {proc.returncode} without JSON: {proc.stderr[-800:]}"}


def train(round_: int) -> dict:
    if GATE_BACKEND == "stub":
        return gate_stub.train(round_)
    return _run(["gate-train", "--round", str(round_)])


def evaluate(model_id: str, split: str = "all", ids: list[str] | None = None, rows: bool = False) -> dict:
    """{"model_id", "metrics": RoundMetrics, "rows"?}. ids restricts to those listings (e.g. one round's attacks)."""
    if GATE_BACKEND == "stub":
        return gate_stub.evaluate(model_id, split, ids, rows)
    args = ["gate-eval", "--model", model_id, "--split", split]
    tmp = None
    if ids is not None:
        tmp = Path(tempfile.mkstemp(prefix="rt-ids-", suffix=".txt")[1])
        tmp.write_text("\n".join(ids), encoding="utf-8")
        args += ["--ids", str(tmp)]
    try:
        return _run(args + (["--rows"] if rows else []))
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def evaluate_items(model_id: str, items: list[tuple[Listing, Case, AnswerKey]], refs: ReferenceSet,
                   rows: bool = False) -> dict:
    """In-process scoring of listings that are not in MongoDB (the holdout)."""
    if GATE_BACKEND == "stub":
        return gate_stub.evaluate_items(model_id, items, refs, rows)
    from gatepy.evaluate import evaluate as gate_evaluate  # JOIN: available once feat/gate is merged
    from gatepy.model_io import load
    return gate_evaluate(load(model_id), items, refs, rows=rows)


def model_features(model_id: str | None) -> list[str]:
    if not model_id:
        return []
    try:
        return list(json.loads((MODELS_DIR / f"{model_id}.json").read_text())["features"])
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return []


def restore_features(model_id: str) -> None:
    """After a refused promotion, put the promoted model's feature code back (the coordinator edits in place)."""
    if GATE_BACKEND == "stub":
        return
    from gatepy.model_io import restore_features as gate_restore  # JOIN
    gate_restore(model_id)
