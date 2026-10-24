"""Drive the MCP server over real stdio, the way droid does, against throwaway data/models/holdout dirs."""
import asyncio
import json
import os
import subprocess
import sys

import pytest

from redteam.config import REPO

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    root = tmp_path_factory.mktemp("mcp")
    e = {**os.environ, "CALHACKS_DATA": str(root / "data"), "CALHACKS_MODELS": str(root / "models"),
         "CALHACKS_HOLDOUT": str(root / "holdout"), "REDTEAM_OFFLINE": "1", "REDTEAM_GATE": "stub"}
    run = lambda *a: subprocess.run([sys.executable, "-m", *a], env={**e, "REDTEAM_ROUND": "0"}, cwd=REPO,
                                    check=True, capture_output=True)
    run("redteam.generate", "--round", "0", "--family", "mixed", "--n", "300", "--offline", "--batch-id", "b01-seed")
    run("redteam.holdout", "build", "--offline")
    e["REDTEAM_ROUND"] = "1"
    return e, root


def drive(env, calls):
    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "redteam.mcp_server"], env=env)
        out = []
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                out.append(sorted(t.name for t in (await s.list_tools()).tools))
                for name, args in calls:
                    res = await s.call_tool(name, args)
                    out.append(json.loads(res.content[0].text))
        return out
    return asyncio.run(go())


def test_round_flow_over_stdio(env):
    e, root = env
    tools, status, held, gen, train = drive(e, [
        ("get_status", {}),
        ("generate_attacks", {"family": "spoofed_store_name", "n": 10}),
        ("generate_attacks", {"family": "too_cheap", "n": 30}),
        ("train_gate", {"round": 0}),
    ])
    assert "promote_model" in tools and "eval_gate" in tools
    assert status["round"] == 1 and "urgency_pressure" in status["reserved_families"]
    assert "reserved for the holdout" in held["error"]
    assert gen["kept"] == 30
    assert train["model_id"].startswith("r0-stub")

    promo, score, insp, holdout_eval, val = drive(e, [
        ("promote_model", {"model_id": train["model_id"]}),
        ("score_round", {}),
        ("inspect_failures", {"limit": 2}),
        ("eval_gate", {"model_id": "promoted", "split": "holdout"}),
        ("eval_gate", {"model_id": "promoted", "split": "val"}),
    ])[1:]
    assert promo["promoted"], promo
    assert promo["holdout"] == "recorded"
    recorded = json.loads((root / "models" / "promoted.json").read_text())["history"][-1]["holdout"]
    assert recorded["n"] == 600 and "rows" not in recorded
    assert 0 <= score["attack_success"] <= 1
    assert "clusters" in insp
    assert "not available to the coordinator" in holdout_eval["error"]
    assert "rows" not in val
    calls = (root / "data" / "rounds" / "R1" / "calls.jsonl").read_text().splitlines()
    assert len(calls) >= 8
