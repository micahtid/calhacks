"""Bulk attack generation (plan C9a): spec -> parallel Bitdeer calls -> code mutations -> validated JSONL batch.

Usage:
  uv run --project redteam python -m redteam.generate --round 0 --family mixed --n 300 --legit-ratio 0.4 --offline
  uv run --project redteam python -m redteam.generate --spec spec.json            # live, needs BITDEER_API_KEY
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from redteam import bitdeer, offline, prompts
from redteam.config import (BATCH_SIZE, BULK_MODELS, CONCURRENCY, MAX_N_PER_SPEC, families, holdout_families,
                            legit_families, round_dir, scam_families)
from redteam.mutate import Slot, build_snapshot, medians
from redteam.validate import problems

OFFLINE_MODEL = "offline-templates"


def spec_errors(spec: dict, allow_holdout: bool = False) -> list[str]:
    errs = []
    fam = spec.get("family")
    if fam != "mixed" and fam not in families():
        errs.append(f"unknown family {fam!r}; use one of {sorted(scam_families())} or 'mixed'")
    elif fam in holdout_families() and not allow_holdout:
        errs.append(f"family {fam!r} is reserved for the holdout")
    elif fam in legit_families():
        errs.append("family must be an attack family; legit listings come from legit_ratio")
    n = spec.get("n")
    if not isinstance(n, int) or not 1 <= n <= MAX_N_PER_SPEC:
        errs.append(f"n must be an integer in 1..{MAX_N_PER_SPEC}")
    lr = spec.get("legit_ratio", 0.4)
    if not isinstance(lr, (int, float)) or not 0 <= lr <= 0.9:
        errs.append("legit_ratio must be in 0..0.9")
    bad_items = [i for i in spec.get("base_items") or [] if i not in medians()]
    if bad_items:
        errs.append(f"unknown base_items {bad_items}; known: {sorted(medians())}")
    if not isinstance(spec.get("round"), int) or spec["round"] < 0:
        errs.append("round must be a non-negative integer")
    return errs


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def plan_slots(spec: dict, batch_id: str, seed: int, allow_holdout: bool = False) -> list[Slot]:
    rng = random.Random(_seed(seed, batch_id))
    n = spec["n"]
    n_legit = round(n * spec.get("legit_ratio", 0.4))
    scam_pool = scam_families(include_holdout=allow_holdout) if spec["family"] == "mixed" else [spec["family"]]
    if spec["family"] == "mixed" and allow_holdout:
        scam_pool = [f for f in scam_pool if f in holdout_families()] or scam_pool
    legit_pool = legit_families()
    items = spec.get("base_items") or [k for k in medians() if k != "star-fox-snes"]
    fams = [scam_pool[i % len(scam_pool)] for i in range(n - n_legit)] + [legit_pool[i % len(legit_pool)]
                                                                          for i in range(n_legit)]
    rng.shuffle(fams)
    return [Slot(f"s{i + 1}", f, rng.choice(items), _seed(seed, batch_id, i)) for i, f in enumerate(fams)]


def next_batch_id(out_dir: Path, family: str) -> str:
    return f"b{len(list(out_dir.glob('b*.jsonl'))) + 1:02d}-{family}"


def _texts_online(client, model, temperature, slots, target, tally):
    payload = bitdeer.complete_json(client, model, prompts.build_messages(slots, target), temperature, tally)
    return prompts.parse_slots(payload) if payload is not None else {}


def _run_chunk(i, chunk, ctx):
    """Generate one chunk; retry the failed slots once, then drop them (plan B2)."""
    kept, dropped = [], []
    model, temp = ctx["model_for"](i), ctx["temp_for"](i)
    pending = list(chunk)
    for attempt in range(2):
        if not pending:
            break
        if ctx["offline"]:
            texts = {s.slot_id: offline.text_for(s) for s in pending}
        elif ctx["tally"].total >= ctx["token_budget"]:
            texts = {}
        else:
            texts = _texts_online(ctx["client"], model, temp, pending, ctx["target"], ctx["tally"])
        failed = []
        for s in pending:
            text = texts.get(s.slot_id)
            if text is None:
                failed.append((s, "no text returned"))
                continue
            gen = {"model": model, "temperature": temp, "batch_id": ctx["batch_id"], "round": ctx["round"]}
            snap = build_snapshot(s, text, gen, f"R{ctx['round']}-{ctx['batch_id']}-{int(s.slot_id[1:]):04d}")
            errs = problems(snap)
            if errs:
                failed.append((s, errs[0]))
            else:
                kept.append(snap)
        pending = [s for s, _ in failed]
        if attempt == 1 or ctx["offline"]:
            dropped += [{"slot": s.slot_id, "family": s.family, "why": why} for s, why in failed]
    return kept, dropped


def generate(spec: dict, *, offline_mode: bool = False, client=None, out_dir: Path | None = None,
             batch_id: str | None = None, seed: int = 0, allow_holdout: bool = False,
             models: list[str] | None = None, token_budget: int = 10**12, write: bool = True) -> dict:
    errs = spec_errors(spec, allow_holdout)
    if errs:
        raise ValueError("; ".join(errs))
    out_dir = out_dir or round_dir(spec["round"])
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_id = batch_id or next_batch_id(out_dir, spec["family"])
    slots = plan_slots(spec, batch_id, seed, allow_holdout)
    chunks = [slots[i:i + BATCH_SIZE] for i in range(0, len(slots), BATCH_SIZE)]
    models = models or spec.get("models") or BULK_MODELS
    tally = bitdeer.Tally()
    if not offline_mode and client is None:
        client = bitdeer.make_client()
    ctx = {
        "offline": offline_mode, "client": client, "tally": tally, "target": spec.get("target_weakness"),
        "round": spec["round"], "batch_id": batch_id, "token_budget": token_budget,
        "model_for": (lambda i: OFFLINE_MODEL) if offline_mode else (lambda i: models[i % len(models)]),
        "temp_for": (lambda i: 0.0) if offline_mode else (
            lambda i: round(random.Random(_seed(batch_id, i)).uniform(0.8, 1.0), 2)),
    }
    with ThreadPoolExecutor(1 if offline_mode else CONCURRENCY) as ex:
        results = list(ex.map(lambda ic: _run_chunk(*ic, ctx), enumerate(chunks)))
    kept = [s for k, _ in results for s in k]
    dropped = [d for _, d in results for d in d]
    kept.sort(key=lambda s: s["id"])
    summary = {
        "batch_id": batch_id, "round": spec["round"], "requested": spec["n"], "kept": len(kept),
        "dropped": len(dropped), "drop_reasons": Counter(d["why"][:60] for d in dropped).most_common(5),
        "by_family": dict(Counter(s["family"] for s in kept)),
        "models": sorted({s["gen"]["model"] for s in kept}), "tokens": tally.as_dict(), "spec": spec,
    }
    if write:
        path = out_dir / f"{batch_id}.jsonl"
        path.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in kept), encoding="utf-8")
        (out_dir / f"{batch_id}.meta.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
        summary["path"] = str(path)
    summary["_snapshots"] = kept
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", type=Path, help="JSON attack spec (contracts/interfaces.md)")
    ap.add_argument("--round", type=int, default=0)
    ap.add_argument("--family", default="mixed")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--legit-ratio", type=float, default=0.4)
    ap.add_argument("--target-weakness")
    ap.add_argument("--base-items", nargs="*")
    ap.add_argument("--offline", action="store_true", help="templated text, no Bitdeer calls")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch-id")
    a = ap.parse_args(argv)
    spec = json.loads(a.spec.read_text()) if a.spec else {
        "round": a.round, "family": a.family, "n": a.n, "legit_ratio": a.legit_ratio,
        "target_weakness": a.target_weakness, "base_items": a.base_items, "constraints": {}}
    try:
        summary = generate(spec, offline_mode=a.offline, seed=a.seed, batch_id=a.batch_id)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        return 2
    summary.pop("_snapshots")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
