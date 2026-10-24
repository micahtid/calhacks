"""Factory Droid coordinator: one SDK session per red-team round (plan C1-C8).

Usage:
  uv run --project redteam python -m redteam.coordinator --round 1
  uv run --project redteam python -m redteam.coordinator --round 1 --resume <session_id>
  uv run --project redteam python -m redteam.coordinator --round 1 --offline-gen --max-listings 120   # cheap dry run

The coordinator sees the world only through the redteam MCP server (stdio), works in gate/, may edit only
gate/features/* and gate/train_config.yaml, and has no path to the holdout (see guard_hook.py and mcp_server.py).
"""
import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any

from pydantic import BaseModel, Field

from redteam import gate_client, holdout
from redteam.config import (COORDINATOR_MODEL, DATA, FACTORY_SETTINGS, GATE_DIR, ROUND_WALL_SECONDS, STRATEGIST_DROID,
                            contract, round_dir)

COORD_TOKEN_BUDGET = 2_000_000
ALLOWED_EDIT = ("features/", "train_config.yaml")
DISABLED_TOOLS = ["Execute", "FetchUrl", "WebSearch", "ReadAutomation", "ListAutomations", "ListAutomationTemplates",
                  "ConnectApp"]


# ---------- C4 round report ----------
class FailureCluster(BaseModel):
    kind: str = Field(description="missed_scam or false_block")
    family: str
    count: int
    cause: str = Field(description="One sentence: why the Gate got these wrong")


class AttackSpecOut(BaseModel):
    family: str
    n: int
    target_weakness: str


class FeatureChange(BaseModel):
    file: str
    feature: str
    change: str


class Metrics(BaseModel):
    recall: float
    fpr: float
    per_family: dict[str, float] = Field(description="Validation recall for attack families, FPR for legit ones")


class RoundReport(BaseModel):
    round: int
    failures_by_cluster: list[FailureCluster]
    new_attack_specs: list[AttackSpecOut]
    feature_changes: list[FeatureChange]
    train_params: dict[str, Any]
    candidate_model_id: str | None
    promoted: bool
    metrics: Metrics


# ---------- policy ----------
def _rel(p) -> str:
    from pathlib import Path
    try:
        return Path(p).resolve().relative_to(GATE_DIR.resolve()).as_posix()
    except Exception:
        return f"<outside>/{p}"


def make_permission_handler(allow_edits: bool, log: list):
    from droid_sdk import ToolConfirmationOutcome as O
    from droid_sdk.permissions import ApplyPatchAction, CreateFile, EditAction, ExecuteAction, McpToolAction

    def edit_ok(path):
        r = _rel(path)
        return allow_edits and "holdout" not in r and any(r == a or r.startswith(a) for a in ALLOWED_EDIT)

    def on_permission(req):
        offered = {o.value for o in req.options}
        ok = True
        for a in req.actions:
            if isinstance(a, (EditAction, CreateFile)):
                good = edit_ok(a.file_path)
                log.append(("edit", _rel(a.file_path), good))
            elif isinstance(a, ApplyPatchAction):
                paths = [f.file_path for f in getattr(a, "files", [])] or [getattr(a, "file_path", "?")]
                good = all(edit_ok(p) for p in paths)
                log.append(("patch", [_rel(p) for p in paths], good))
            elif isinstance(a, McpToolAction):
                good = (a.server_name or "") == "redteam" or a.tool_name.startswith("redteam___")
                log.append(("mcp", a.tool_name, good))
            elif isinstance(a, ExecuteAction):
                good = False
                log.append(("exec", a.command[:80], False))
            else:
                good = False
                log.append((type(a).__name__, "", False))
            ok = ok and good
        choice = O.PROCEED_ONCE if ok and O.PROCEED_ONCE in offered else O.CANCEL
        return req.respond(choice, comment=None if ok else "Blocked by red-team policy.")
    return on_permission


def write_hooks() -> None:
    """gate/.factory/hooks.json (gitignored): the guard hook runs before every tool call, subagents included if droid applies it."""
    log = DATA / "guard.log"
    DATA.mkdir(parents=True, exist_ok=True)
    cmd = f'"{sys.executable}" -m redteam.guard_hook --root "{GATE_DIR}" --log "{log}"'
    hooks = {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": cmd, "timeout": 30}]}]}
    (GATE_DIR / ".factory").mkdir(parents=True, exist_ok=True)
    (GATE_DIR / ".factory" / "hooks.json").write_text(json.dumps(hooks, indent=1))


def mcp_server(round_: int, offline_gen: bool, max_listings: int):
    from droid_sdk import StdioMcpServerConfig
    env = {"REDTEAM_ROUND": str(round_), "CALHACKS_DATA": str(DATA), "REDTEAM_GATE": gate_client.GATE_BACKEND,
           "REDTEAM_MAX_LISTINGS": str(max_listings), "PYTHONIOENCODING": "utf-8"}
    for k in ("BITDEER_API_KEY", "CALHACKS_HOLDOUT", "CALHACKS_MODELS"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    if offline_gen:
        env["REDTEAM_OFFLINE"] = "1"
    try:
        env["HOLDOUT_KEY"] = holdout.key_for_mcp_env()  # only the MCP server process gets the key
    except RuntimeError:
        pass
    return StdioMcpServerConfig(name="redteam", command=sys.executable, args=["-m", "redteam.mcp_server"], env=env)


def build_session(round_: int, *, model: str, offline_gen: bool = False, max_listings: int = 300,
                  allow_edits: bool = True, perm_log: list | None = None, resume: str | None = None):
    from droid_sdk import Autonomy, InteractionHandlers, Runtime, Session, SessionConfig
    os.environ.pop("HOLDOUT_KEY", None)  # never inherited by droid itself
    write_hooks()
    perm_log = perm_log if perm_log is not None else []
    handlers = InteractionHandlers(on_permission=make_permission_handler(allow_edits, perm_log))
    runtime = Runtime(args=["--settings", str(FACTORY_SETTINGS)],
                      env={k: v for k, v in os.environ.items() if k.startswith("BITDEER")})
    servers = [mcp_server(round_, offline_gen, max_listings)]
    if resume:
        return Session.resume(resume, interactions=handlers, mcp_servers=servers, runtime=runtime,
                              disabled_tools=DISABLED_TOOLS, disable_builtin_skills=True)
    cfg = SessionConfig(autonomy=Autonomy.HIGH, mcp_servers=servers, disabled_tools=DISABLED_TOOLS,
                        disable_builtin_skills=True)
    return Session(cwd=GATE_DIR, model=model, config=cfg, interactions=handlers, runtime=runtime)


def round_prompt(round_: int, allow_edits: bool, max_listings: int) -> str:
    fams = contract("families.json")
    editing = (
        "Then fix the Gate by editing feature files under features/ (relative to your working directory) or "
        "train_config.yaml. A feature is a pure function registered with the decorator below; it must be "
        "deterministic, return a finite float, and do no file or network I/O:\n"
        "    from gatepy.registry import feature\n"
        "    @feature(\"name\", monotone=-1|0|1)   # -1: risk must not rise as the value rises\n"
        "    def name(s, ctx) -> float: ...\n"
        "Read the existing files in features/ first and follow their style."
        if allow_edits else
        "Feature editing is disabled in this run (the stub gate ignores features). Put the feature changes you "
        "would make into feature_changes in the report instead.")
    return f"""You are the red-team lead for a payment Gate that protects an AI shopping agent from scam listings.
This is round {round_}. Your goal: find where the Gate is weak, attack it there, and make it stronger without
blocking honest sellers.

You act only through the redteam tools (get_status, generate_attacks, score_round, inspect_failures, train_gate,
eval_gate, promote_model) and the {STRATEGIST_DROID} subagent (Task tool, subagent_type "{STRATEGIST_DROID}").
There is no shell. Families {fams['holdout_families']} are reserved for a sealed test and cannot be requested;
do not try to find or read any holdout data.

Procedure:
1. get_status. If there is no promoted model, run train_gate(round=0) and promote_model on it as the baseline.
2. Give the {STRATEGIST_DROID} the per-family numbers from get_status and ask for new attack specs.
3. generate_attacks for 2-4 specs: the weakest attack families, families with fewer than 30 rows, and the
   strategist's best ideas. Stay within {max_listings} listings this round in total.
4. score_round (how well last round's model holds up against the fresh attacks), then inspect_failures.
5. {editing}
6. train_gate, then promote_model on the new model id. Promotion is decided by code (validation recall must go up,
   FPR <= 2%, no family drops more than 5 points). If it is refused, you may make one more fix and retry once.
7. Finish with the round report: clusters of failures with their causes, the attack specs you ran, the feature
   changes, train params, the candidate model id, whether it was promoted, and its validation metrics.
"""


def _guard_denials(session_id: str) -> list[dict]:
    """Denials the guard hook logged for this session (SDK hook events don't reliably carry the exit code)."""
    log = DATA / "guard.log"
    if not log.exists():
        return []
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [{"tool": r["tool"], "why": r["why"]} for r in rows if r["decision"] == "deny" and r.get("session") == session_id]


async def run_round(round_: int, *, model: str, offline_gen: bool, max_listings: int, resume: str | None,
                    timeout: float) -> dict:
    allow_edits = gate_client.GATE_BACKEND != "stub"
    out_dir = round_dir(round_)
    perm_log, events, tokens = [], [], {"in": 0, "out": 0}
    session = build_session(round_, model=model, offline_gen=offline_gen, max_listings=max_listings,
                            allow_edits=allow_edits, perm_log=perm_log, resume=resume)
    prompt = round_prompt(round_, allow_edits, max_listings) if not resume else \
        "Continue this round from where you stopped, then produce the round report."
    started = time.time()
    async with session as s:
        (out_dir / "session.json").write_text(json.dumps({"session_id": s.id, "model": model, "started": started,
                                                          "resumed_from": resume}))
        async with s.stream(prompt, output=RoundReport, timeout=timeout) as st:
            async for ev in st:
                kind = type(ev).__name__
                if kind == "ToolCall":
                    events.append({"t": round(time.time() - started, 1), "tool": ev.name})
                elif kind == "HookExecution" and ev.status == "completed" and ev.exit_code == 2:
                    events.append({"t": round(time.time() - started, 1), "hook_denied": (ev.stderr or "")[:200]})
                elif kind == "TokenUsageUpdate":
                    tokens = {"in": ev.input_tokens, "out": ev.output_tokens}
                    if ev.input_tokens + ev.output_tokens > COORD_TOKEN_BUDGET:
                        events.append({"budget": "coordinator token budget exceeded; interrupting"})
                        await s.interrupt()
            result = st.result
    u = result.usage
    usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
             "cache_read_tokens": u.cache_read_tokens, "thinking_tokens": u.thinking_tokens} if u else tokens
    budget = out_dir / "budget.json"
    summary = {"round": round_, "session_id": result.session_id, "subtype": result.subtype,
               "seconds": round(time.time() - started), "turns": result.turn_count, "usage": usage,
               "generation_budget": json.loads(budget.read_text()) if budget.exists() else None,
               "tool_calls": len([e for e in events if "tool" in e]),
               "hook_denials": _guard_denials(result.session_id), "permission_log": perm_log}
    (out_dir / "usage.json").write_text(json.dumps(summary, indent=1, default=str))
    (out_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    report = result.output.model_dump() if result.output else {"error": "no structured report",
                                                               "text": (result.text or "")[-2000:]}
    (out_dir / "report.json").write_text(json.dumps(report, indent=1))
    return {"summary": summary, "report": report}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--resume")
    ap.add_argument("--model", default=COORDINATOR_MODEL)
    ap.add_argument("--offline-gen", action="store_true", help="MCP generate_attacks uses templates (no Bitdeer spend)")
    ap.add_argument("--max-listings", type=int, default=300)
    ap.add_argument("--timeout", type=float, default=ROUND_WALL_SECONDS)
    a = ap.parse_args(argv)
    out = asyncio.run(run_round(a.round, model=a.model, offline_gen=a.offline_gen, max_listings=a.max_listings,
                                resume=a.resume, timeout=a.timeout))
    print(json.dumps(out, indent=1, default=str))
    return 0 if out["summary"]["subtype"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
