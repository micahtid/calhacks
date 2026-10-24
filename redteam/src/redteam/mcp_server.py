"""stdio MCP server: the coordinator's only window on the red-team loop (plan C2, adjusted for B6).

There is deliberately no tool that scores the holdout. Holdout totals are computed only inside promote_model, after
the code-enforced promotion decision, and are recorded for the dashboard, not returned.

Env: REDTEAM_ROUND (current round), REDTEAM_OFFLINE=1 (templated generation), HOLDOUT_KEY (only this process),
BITDEER_API_KEY, CALHACKS_DATA.

Run: uv run --project redteam python -m redteam.mcp_server
"""
import functools
import inspect
import json
import os
import time
from collections import Counter, defaultdict

from redteam import gate_client, holdout, promotion
from redteam.config import (BULK_MODELS, ROUND_TOKEN_BUDGET, ROUNDS, holdout_families, legit_families, round_dir,
                            scam_families)
from redteam.generate import generate
from redteam.mutate import medians
from redteam.splits import iter_rows, round_files, split_of

NOT_BUILT = "not available: the storefront scam-store route (plan A4/B6) isn't built yet; judge offline instead"


def current_round() -> int:
    if os.environ.get("REDTEAM_ROUND"):
        return int(os.environ["REDTEAM_ROUND"])
    rounds = [int(d.name[1:]) for d in ROUNDS.glob("R*") if d.name[1:].isdigit()] if ROUNDS.exists() else []
    return max(rounds, default=0)


def _paths_upto(r: int):
    return round_files(range(0, r + 1))


def _budget_file(r):
    return round_dir(r) / "budget.json"


def _budget(r) -> dict:
    f = _budget_file(r)
    return json.loads(f.read_text()) if f.exists() else {"gen_tokens": 0, "gen_calls": 0, "limit": ROUND_TOKEN_BUDGET}


def _log(tool: str, args: dict, result: dict):
    with (round_dir(current_round()) / "calls.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "tool": tool, "args": args,
                            "ok": not (isinstance(result, dict) and result.get("error"))}) + "\n")
    return result


def _strip(m: dict) -> dict:
    return {k: v for k, v in m.items() if k != "rows"}


# ---------- tools ----------
def get_status() -> dict:
    r = current_round()
    state = promotion.current()
    cov = defaultdict(Counter)
    for row in iter_rows(_paths_upto(r)):
        cov[row["family"]][split_of(row["id"])] += 1
    last = state["history"][-1] if state["history"] else None
    return _log("get_status", {}, {
        "round": r,
        "promoted_model": state["model_id"],
        "promoted_val": last and _strip(last["val"]),
        "coverage": {f: dict(c) for f, c in sorted(cov.items())},
        "attack_families": scam_families(), "legit_families": legit_families(),
        "reserved_families": holdout_families(),
        "base_items": sorted(medians()),
        "budget": _budget(r),
        "generator_models": BULK_MODELS,
    })


def generate_attacks(family: str, n: int, legit_ratio: float = 0.4, target_weakness: str | None = None,
                     base_items: list[str] | None = None) -> dict:
    r = current_round()
    args = {"family": family, "n": n, "legit_ratio": legit_ratio, "target_weakness": target_weakness,
            "base_items": base_items}
    budget = _budget(r)
    left = budget["limit"] - budget["gen_tokens"]
    if left <= 0:
        return _log("generate_attacks", args, {"error": f"round {r} generation budget exhausted"})
    cap = int(os.environ.get("REDTEAM_MAX_LISTINGS", "100000"))
    have = sum(1 for _ in iter_rows(round_files([r])))
    if isinstance(n, int) and have + n > cap:
        return _log("generate_attacks", args, {"error": f"round {r} listing cap {cap} reached ({have} generated); "
                                                        f"request at most {max(0, cap - have)}"})
    spec = {"round": r, "family": family, "n": n, "legit_ratio": legit_ratio, "target_weakness": target_weakness,
            "base_items": base_items, "constraints": {}}
    try:
        out = generate(spec, offline_mode=os.environ.get("REDTEAM_OFFLINE") == "1", token_budget=left)
    except ValueError as e:
        return _log("generate_attacks", args, {"error": str(e)})
    out.pop("_snapshots")
    budget["gen_tokens"] += out["tokens"]["prompt_tokens"] + out["tokens"]["completion_tokens"]
    budget["gen_calls"] += out["tokens"]["calls"]
    _budget_file(r).write_text(json.dumps(budget))
    return _log("generate_attacks", args, {k: out[k] for k in ("batch_id", "kept", "dropped", "drop_reasons",
                                                              "by_family", "models", "tokens")})


def score_round(round: int | None = None) -> dict:
    """Last promoted model vs. this round's fresh attacks: the red team's 'attack success'."""
    r = current_round() if round is None else round
    state = promotion.current()
    if not state["model_id"]:
        return _log("score_round", {"round": r}, {"error": "no promoted model yet: train_gate then promote_model"})
    m = gate_client.evaluate(state["model_id"], round_files([r]), split="all")
    if m.get("error"):
        return _log("score_round", {"round": r}, m)
    m = _strip(m)
    m["model_id"] = state["model_id"]
    m["attack_success"] = round_(1 - m["recall"])
    m["attack_success_per_family"] = {f: round_(1 - v["recall"]) for f, v in m["per_family"].items() if "recall" in v}
    (round_dir(r) / "score.json").write_text(json.dumps(m, indent=1))
    return _log("score_round", {"round": r}, m)


def round_(x):
    return round(x, 4)


def _snippet(s: dict) -> dict:
    med = medians().get(s["item"]["id"]) or s["item"]["priceUsd"]
    return {"store": s["store"]["name"], "seller_since": s["store"]["sellingSince"],
            "store_reviews": s["store"]["reviewCount"], "price_ratio": round_(s["item"]["priceUsd"] / med),
            "description": s["item"]["description"][:240],
            "reviews": [{"rating": r["rating"], "verified": r["verifiedPurchase"], "date": r["date"],
                         "body": r["body"][:140]} for r in s["reviews"][:3]]}


def inspect_failures(round: int | None = None, limit: int = 20, model_id: str | None = None) -> dict:
    """Misses (scams bought) and false blocks (legit skipped), clustered by family and top feature."""
    r = current_round() if round is None else round
    model_id = model_id or promotion.current()["model_id"]
    if not model_id:
        return _log("inspect_failures", {"round": r}, {"error": "no model to inspect"})
    paths = round_files([r])
    m = gate_client.evaluate(model_id, paths, split="all", rows=True)
    if m.get("error"):
        return _log("inspect_failures", {"round": r}, m)
    by_id = {s["id"]: s for s in iter_rows(paths)}
    bad = [row for row in m["rows"] if (row["label"] == "scam") == (row["decision"] == "buy")]
    clusters = defaultdict(list)
    for row in bad:
        kind = "missed_scam" if row["label"] == "scam" else "false_block"
        top = row["top3"][0][0] if row["top3"] else "none"
        clusters[(kind, row["family"], top)].append(row)
    out = []
    for (kind, fam, top), rows in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        out.append({"kind": kind, "family": fam, "top_feature": top, "count": len(rows),
                    "examples": [{"id": x["id"], "risk": x["risk"], "layer": x["layer"], "top3": x["top3"],
                                  **_snippet(by_id[x["id"]])} for x in rows[:3]]})
    return _log("inspect_failures", {"round": r}, {"model_id": model_id, "round": r, "n_failures": len(bad),
                                                   "clusters": out[:limit]})


def train_gate(round: int | None = None) -> dict:
    r = current_round() if round is None else round
    out = gate_client.train(_paths_upto(r), r)
    if not out.get("error"):
        (round_dir(r) / f"train-{out['model_id']}.json").write_text(json.dumps(out, indent=1))
    return _log("train_gate", {"round": r}, out)


def eval_gate(model_id: str, split: str) -> dict:
    if split not in ("train", "val"):
        return _log("eval_gate", {"model_id": model_id, "split": split},
                    {"error": "split must be 'train' or 'val'; the holdout is not available to the coordinator"})
    m = gate_client.evaluate(model_id, _paths_upto(current_round()), split=split)
    return _log("eval_gate", {"model_id": model_id, "split": split}, _strip(m))


def promote_model(model_id: str) -> dict:
    r = current_round()
    have_holdout = holdout.HOLDOUT_FILE.exists() and bool(os.environ.get("HOLDOUT_KEY") or holdout.HOLDOUT_KEY_FILE.exists())
    res = promotion.promote(model_id, _paths_upto(r), holdout.totals if have_holdout else None)
    if res.get("promoted"):
        res["holdout"] = "recorded" if res.get("holdout") else "not available"
    (round_dir(r) / "promotion.json").write_text(json.dumps(res, indent=1, default=str))
    return _log("promote_model", {"model_id": model_id}, res)


def render_store(listing_ids: list[str]) -> dict:
    return _log("render_store", {"n": len(listing_ids)}, {"error": NOT_BUILT})


def run_agent_batch(listing_ids: list[str]) -> dict:
    return _log("run_agent_batch", {"n": len(listing_ids)}, {"error": NOT_BUILT})


TOOLS = [get_status, generate_attacks, score_round, inspect_failures, train_gate, eval_gate, promote_model,
         render_store, run_agent_batch]


def build_server():
    from mcp.server.fastmcp import FastMCP
    server = FastMCP("redteam")
    for fn in TOOLS:
        server.tool()(_jsonify(fn))
    return server


def _jsonify(fn):
    """Return results as a JSON string (what the planning tests proved works with droid)."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return json.dumps(fn(*a, **kw), default=str)
        except Exception as e:  # never crash the server on one bad call
            return json.dumps({"error": f"{type(e).__name__}: {e}"})
    wrapper.__signature__ = inspect.signature(fn).replace(return_annotation=str)
    wrapper.__annotations__ = {**fn.__annotations__, "return": str}
    return wrapper


if __name__ == "__main__":
    build_server().run()
