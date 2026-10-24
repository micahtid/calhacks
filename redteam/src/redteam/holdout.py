"""Holdout custody (plan B6). Built once by us, never by the coordinator, and never written to MongoDB.

Contents, all mutated from the real listings in MongoDB:
  (a) the held-out families (families.json: urgency_pressure, lookalike_domain), with honest listings mixed in;
  (b) a slice of every other scam family.
LLM text is written by the holdout model (Nemotron), which is never used for training. The listings, their answer
keys, cases and the simulated references they need (wallet first-seen dates) are stored together, encrypted,
outside the repo. Only the MCP server process gets the key (HOLDOUT_KEY env). Scoring overlays the simulated
references on a MongoDB reference snapshot in memory and returns totals only.

Usage:
  uv run --project redteam python -m redteam.holdout build [--force] [--per-family 60] [--slice 20]
  uv run --project redteam python -m redteam.holdout totals --model <model_id|promoted>
  uv run --project redteam python -m redteam.holdout status
"""
import argparse
import json
import os
import sys
from collections import Counter

from calhacks_contracts import Case, HoldoutTotals, Rate, SyntheticListing
from cryptography.fernet import Fernet

from redteam import gate_client, store
from redteam.config import HOLDOUT, HOLDOUT_FILE, HOLDOUT_KEY_FILE, HOLDOUT_MODEL, REPO, holdout_families, scam_families
from redteam.generate import run_spec

META_FILE = HOLDOUT / "holdout.v3.meta.json"


def _key(create: bool = False) -> bytes:
    env = os.environ.get("HOLDOUT_KEY")
    if env:
        return env.encode()
    if HOLDOUT_KEY_FILE.exists():
        return HOLDOUT_KEY_FILE.read_bytes().strip()
    if not create:
        raise RuntimeError("no holdout key: set HOLDOUT_KEY or build the holdout first")
    key = Fernet.generate_key()
    HOLDOUT.mkdir(parents=True, exist_ok=True)
    HOLDOUT_KEY_FILE.write_bytes(key)
    return key


def key_for_mcp_env() -> str:
    """The key string handed to the MCP server process (and nothing else)."""
    return _key().decode()


def available() -> bool:
    return HOLDOUT_FILE.exists() and bool(os.environ.get("HOLDOUT_KEY") or HOLDOUT_KEY_FILE.exists())


def _assert_outside_repo():
    try:
        HOLDOUT.resolve().relative_to(REPO.resolve())
    except ValueError:
        return
    raise RuntimeError(f"holdout dir {HOLDOUT} must be outside the repo {REPO}")


def build(*, force: bool = False, per_family: int = 60, slice_n: int = 20, seed: int = 7, client=None,
          r=None) -> dict:
    _assert_outside_repo()
    if HOLDOUT_FILE.exists() and not force:
        raise RuntimeError(f"{HOLDOUT_FILE} already exists; the holdout is built once (use --force to rebuild)")
    r = r or store.repo()
    specs = [{"spec_id": f"H-{f}", "family": f, "n": per_family, "legit_ratio": 0.3, "mode": "mutate_real"}
             for f in sorted(holdout_families())]
    specs += [{"spec_id": f"H-slice-{f}", "family": f, "n": slice_n, "legit_ratio": 0.0, "mode": "mutate_real"}
              for f in scam_families()]
    items, wallets, dropped, tokens = [], {}, Counter(), []
    for spec in specs:
        out = run_spec(spec, round_=0, r=r, client=client, write=False, allow_holdout=True, seed=seed,
                       models=[HOLDOUT_MODEL], id_prefix="H")
        items += out["_items"]
        wallets.update(out["_refs"].wallets)
        dropped.update(out["drops_by_family"])
        tokens.append(out["tokens"])
    payload = {"version": 3, "items": [{"synthetic": s.model_dump(mode="json"), "case": c.model_dump(mode="json")}
                                       for s, c in items],
               "refs": {"wallets": wallets}}
    HOLDOUT.mkdir(parents=True, exist_ok=True)
    HOLDOUT_FILE.write_bytes(Fernet(_key(create=True)).encrypt(json.dumps(payload).encode()))
    meta = {"n": len(items), "by_family": dict(Counter(s.answer_key.family for s, _ in items)),
            "models": sorted({s.gen.model for s, _ in items if s.gen.model}), "dropped": dict(dropped),
            "tokens": {"prompt": sum(t["prompt_tokens"] for t in tokens),
                       "completion": sum(t["completion_tokens"] for t in tokens)}}
    META_FILE.write_text(json.dumps(meta, indent=1))
    return meta


def _load():
    payload = json.loads(Fernet(_key()).decrypt(HOLDOUT_FILE.read_bytes()))
    items = []
    for row in payload["items"]:
        s = SyntheticListing.model_validate(row["synthetic"])
        items.append((s.listing, Case.model_validate(row["case"]), s.answer_key))
    return items, payload["refs"]["wallets"]


def totals(model_id: str, r=None) -> HoldoutTotals | None:
    """Aggregate holdout recall and false-block rate for one model. Never returns rows."""
    if not available():
        return None
    items, wallets = _load()
    refs = (r or store.repo()).reference_snapshot().overlay(wallets=wallets)
    m = gate_client.evaluate_items(model_id, items, refs, rows=False)
    if m.get("error"):
        raise RuntimeError(m["error"])
    return HoldoutTotals(model_id=m["model_id"], recall=Rate.model_validate(m["metrics"]["recall"]),
                         fpr=Rate.model_validate(m["metrics"]["fpr"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--force", action="store_true")
    b.add_argument("--per-family", type=int, default=60)
    b.add_argument("--slice", type=int, default=20)
    t = sub.add_parser("totals")
    t.add_argument("--model", required=True)
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        out = build(force=a.force, per_family=a.per_family, slice_n=a.slice)
    elif a.cmd == "totals":
        res = totals(a.model)
        out = res.model_dump(mode="json") if res else {"error": "no holdout built"}
    else:
        out = json.loads(META_FILE.read_text()) if META_FILE.exists() else {"error": "no holdout built"}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
