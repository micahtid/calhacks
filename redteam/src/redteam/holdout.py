"""Holdout custody (plan B6). Built once by us, never by the coordinator.

Contents: (a) the holdout families (urgency_pressure, spoofed_store_name) plus legit rows, and (b) a slice of every
other family. Online, everything is written by the holdout generator model (Nemotron), which is never used for
training. Stored encrypted outside the repo; only the MCP server process gets the key (HOLDOUT_KEY env).

Usage:
  uv run --project redteam python -m redteam.holdout build [--offline] [--force]
  uv run --project redteam python -m redteam.holdout totals --model <model_id|promoted>
  uv run --project redteam python -m redteam.holdout status
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from cryptography.fernet import Fernet

from redteam import gate_client
from redteam.config import HOLDOUT, HOLDOUT_FILE, HOLDOUT_KEY_FILE, HOLDOUT_MODEL, REPO
from redteam.generate import generate

META_FILE = HOLDOUT / "holdout.meta.json"


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


def _assert_outside_repo():
    try:
        HOLDOUT.resolve().relative_to(REPO.resolve())
    except ValueError:
        return
    raise RuntimeError(f"holdout dir {HOLDOUT} must be outside the repo {REPO}")


def build(offline: bool = False, force: bool = False, n_families: int = 300, n_slice: int = 300, seed: int = 7,
          client=None) -> dict:
    _assert_outside_repo()
    if HOLDOUT_FILE.exists() and not force:
        raise RuntimeError(f"{HOLDOUT_FILE} already exists; the holdout is built once (use --force to rebuild)")
    models = None if offline else [HOLDOUT_MODEL]
    kw = dict(offline_mode=offline, client=client, models=models, seed=seed, write=False, out_dir=Path(tempfile.gettempdir()))
    a = generate({"round": 0, "family": "mixed", "n": n_families, "legit_ratio": 0.3}, allow_holdout=True,
                 batch_id="hA-families", **kw)
    b = generate({"round": 0, "family": "mixed", "n": n_slice, "legit_ratio": 0.3}, batch_id="hB-slice", **kw)
    rows = a["_snapshots"] + b["_snapshots"]
    blob = "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in rows).encode()
    HOLDOUT.mkdir(parents=True, exist_ok=True)
    HOLDOUT_FILE.write_bytes(Fernet(_key(create=True)).encrypt(blob))
    meta = {"n": len(rows), "by_family": dict(Counter(s["family"] for s in rows)),
            "models": sorted({s["gen"]["model"] for s in rows}), "offline": offline,
            "dropped": a["dropped"] + b["dropped"], "tokens": [a["tokens"], b["tokens"]]}
    META_FILE.write_text(json.dumps(meta, indent=1))
    return meta


def _rows_blob() -> bytes:
    return Fernet(_key()).decrypt(HOLDOUT_FILE.read_bytes())


def totals(model_id: str) -> dict:
    """Aggregate holdout metrics for one model. Never returns rows."""
    tmp = Path(tempfile.mkdtemp(prefix="rt-h-"))
    try:
        path = tmp / "h.jsonl"
        path.write_bytes(_rows_blob())
        m = gate_client.evaluate(model_id, [path], split="all", rows=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    m.pop("rows", None)
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--offline", action="store_true")
    b.add_argument("--force", action="store_true")
    t = sub.add_parser("totals")
    t.add_argument("--model", required=True)
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        out = build(offline=a.offline, force=a.force)
    elif a.cmd == "totals":
        out = totals(a.model)
    else:
        out = json.loads(META_FILE.read_text()) if META_FILE.exists() else {"error": "no holdout built"}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
