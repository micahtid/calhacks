"""The Gate as its own service (Railway; see gates/README.md). The wallet pays only when /decide says buy.

  POST /decide    GateRequest -> GateDecision. Layer 1's rules run first and any failure skips; otherwise Layer 2
                  scores the listing the Gate fetched itself against the model's stored threshold. Any error is a
                  503 with decision "skip" (fail closed).
  GET  /health    liveness plus the loaded model id
  GET  /version   model id, feature-code hash, threshold, contracts version

Env: GATE_MODEL_ID (default gates/CURRENT), GATE_MODELS (default gate/models), MONGODB_URI and MONGODB_DB_REDTEAM
(listings and references, read only). Startup fails if gate/features doesn't match the model's feature-code hash.
POST /gate/risk is kept as an alias of /decide for older callers.

  uv run --project gate --extra serve uvicorn --factory gatepy.app:create_app --port 8080
"""
import os
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from gatepy import MODELS
from gatepy.layer1_bridge import Layer1Process
from gatepy.release import current, verify
from gatepy.serve import Gate


class ServedGate(Gate):
    """serve.Gate with one long-lived Layer 1 process instead of a Node start per request."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.layer1 = Layer1Process()

    def score(self, request):
        from calhacks_contracts import GateRequest
        from gatepy.evaluate import decide
        req = request if isinstance(request, GateRequest) else GateRequest.model_validate(request)
        gi = self.resolve(req)
        return decide(self.model, [gi], l1=self.layer1.run([gi]))[0]


def _contracts_version() -> str:
    try:
        return version("calhacks-contracts")
    except PackageNotFoundError:
        return "unknown"


def create_app(gate: Gate | None = None) -> FastAPI:
    if gate is None:
        model_id = os.environ.get("GATE_MODEL_ID") or current()
        verify(model_id, MODELS)  # refuse to start on a feature-code mismatch
        gate = ServedGate(model_id, MODELS)
    app = FastAPI(title="Gate", version=gate.model.model_id)
    meta = gate.model.meta

    def decide(request: dict):
        try:
            return gate.score(request).model_dump(mode="json")
        except Exception as e:  # noqa: BLE001 - fail closed on anything
            return JSONResponse(status_code=503, content={
                "decision": "skip", "decided_by": None, "error": f"{type(e).__name__}: {e}"})

    app.post("/decide")(decide)
    app.post("/gate/risk")(decide)

    @app.get("/health")
    def health():
        return {"ok": True, "model_id": gate.model.model_id}

    @app.get("/version")
    def version_():
        return {"model_id": gate.model.model_id, "feature_code_hash": meta.get("feature_code_hash"),
                "threshold": gate.model.threshold, "threshold_rule": meta.get("threshold_rule"),
                "trained_round": meta.get("round"), "created_at": meta.get("created_at"),
                "contracts_version": _contracts_version()}

    return app

