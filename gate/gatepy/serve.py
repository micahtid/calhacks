"""Purchase-time scoring: score(snapshot) -> Decision, and an optional FastAPI router (POST /gate/risk).

The wallet must treat any error or non-200 response as "skip" (fail closed).
"""
import sys
from functools import cache
from pathlib import Path

from gatepy import MODELS
from gatepy.context import load_ctx
from gatepy.contracts import Snapshot
from gatepy.evaluate import decide
from gatepy.model_io import Model, load
from gatepy.registry import discover, feature_code_hash

DECISION_KEYS = ("decision", "layer", "l1_failures", "risk", "threshold", "model_id", "top3")


class Gate:
    def __init__(self, model_id: str = "promoted", models_dir: Path = MODELS):
        discover()
        self.model: Model = load(model_id, models_dir)
        self.ctx = load_ctx()
        if self.model.meta.get("feature_code_hash") != feature_code_hash():
            print(f"warning: gate/features changed since {self.model.model_id} was trained; "
                  f"run model_io.restore_features() to match", file=sys.stderr)

    def score(self, snapshot: Snapshot | dict) -> dict:
        s = snapshot if isinstance(snapshot, Snapshot) else Snapshot.model_validate(snapshot)
        row = decide(self.model, [s], self.ctx)[0]
        return {k: row[k] for k in DECISION_KEYS}


@cache
def _gate(model_id: str) -> Gate:
    return Gate(model_id)


def score(snapshot: Snapshot | dict, model_id: str = "promoted") -> dict:
    return _gate(model_id).score(snapshot)


def make_router(gate: Gate | None = None):
    """FastAPI router for the wallet. Needs the `serve` extra (fastapi)."""
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    router = APIRouter()

    @router.post("/gate/risk")
    def risk(snapshot: dict):
        try:
            return (gate or _gate("promoted")).score(snapshot)
        except Exception as e:  # noqa: BLE001 - fail closed on anything
            return JSONResponse(status_code=503, content={"decision": "skip", "error": f"{type(e).__name__}: {e}"})

    return router
