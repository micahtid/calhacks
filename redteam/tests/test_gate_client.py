"""Gate subprocesses run coordinator-written feature code, so they must never receive the holdout key or location."""
import subprocess

from redteam import gate_client


def test_subprocess_env_drops_holdout(monkeypatch):
    monkeypatch.setenv("HOLDOUT_KEY", "secret-key")
    monkeypatch.setenv("CALHACKS_HOLDOUT", "C:/somewhere/calhacks-holdout")
    monkeypatch.setenv("MONGODB_DB_REDTEAM", "redteam_test")
    seen = {}

    def fake_run(args, **kw):
        seen.update(kw["env"])
        return subprocess.CompletedProcess(args, 0, stdout='{"model_id": "r1-x"}', stderr="")

    monkeypatch.setattr(gate_client.subprocess, "run", fake_run)
    assert gate_client._run(["gate-train", "--round", "1"]) == {"model_id": "r1-x"}
    assert "HOLDOUT_KEY" not in seen and "CALHACKS_HOLDOUT" not in seen
    assert seen["MONGODB_DB_REDTEAM"] == "redteam_test" and seen["UV_SYSTEM_CERTS"] == "1"
