# Interfaces between `gate/` and `redteam/`

This file and the JSON files next to it are the only things both sides depend on. Change them only on
`feat/contracts` (or in a commit both branches pick up).

## Paths

| What | Where |
|---|---|
| Data root | `$CALHACKS_DATA`, default `<repo>/data` (gitignored) |
| Round batches | `<data>/rounds/R{n}/{batch_id}.jsonl`, one Snapshot per line |
| Holdout | `$CALHACKS_HOLDOUT`, default `<repo>/../calhacks-holdout/` (outside the repo; encrypted) |
| Models | `gate/models/{model_id}.json`; pointer `gate/models/promoted.json` |

**Split rule** (implemented once in `gatepy.splits.split_of`; `redteam` imports it):
`"val"` if `int(sha256(id).hexdigest(), 16) % 5 == 0` else `"train"`. Holdout rows never live under `<data>`.

## Layer 1 CLI (TypeScript, `gate/layer1`)

```
node gate/layer1/src/cli.ts [--contracts contracts/] < snapshots.jsonl > results.jsonl
```
Node 22 strips types natively, so the source must use erasable TypeScript only (no `enum`, no `namespace`,
no parameter properties) and import with `.ts` extensions. One output line per input line, same order:

```json
{"id": "ex-payment-mismatch", "pass": false, "failures": ["L1_PAYTO_MISMATCH"]}
```

Rule ids: `L1_PAYTO_MISMATCH`, `L1_PAYTO_LOOKALIKE`, `L1_AMOUNT_MISMATCH`, `L1_OVER_MAX`, `L1_OVER_BUDGET`,
`L1_NETWORK`, `L1_ASSET`, `L1_SCHEME`, `L1_TIMEOUT`, `L1_ITEM_MISMATCH`.

Lookalike: case-insensitive, `a != b`, and `a[2:6] == b[2:6]` and `a[-4:] == b[-4:]` (first and last 4 hex chars).

## Python CLIs (`gate/`, uv project, entry points)

All print **one JSON object on stdout**. Logs go to stderr. Exit 0 = ok, exit 2 = rejected input or failed self-test
(stdout still holds `{"error": "..."}`).

```
uv run --project gate gate-train --data <jsonl|dir>... --round N [--config gate/train_config.yaml]
  -> {"model_id", "round", "kind", "features": [...], "n_train", "n_val", "threshold", "val": <metrics>}

uv run --project gate gate-eval --model <model_id|promoted> --data <jsonl|dir>... [--split train|val|all] [--rows]
  -> <metrics>
```

`<metrics>`:

```json
{
  "n": 600, "n_scam": 420, "n_legit": 180,
  "recall": 0.93, "fpr": 0.017,
  "recall_l2": 0.88, "fpr_l2": 0.017,
  "l1_catches": 140,
  "per_family": {"too_cheap": {"n": 60, "recall": 0.9}, "legit_plain": {"n": 50, "fpr": 0.0}},
  "rows": [{"id": "...", "family": "...", "label": "scam", "decision": "skip", "layer": "L2",
            "risk": 0.81, "top3": [["price_ratio", 0.22, 1.9], ["seller_age_years", 0.0, 0.7], ["review_dup_max", 0.9, 0.4]]}]
}
```

- `recall` = scams skipped / scams. `fpr` = legit skipped / legit. Both for the full Gate (L1 then L2).
- `recall_l2`, `fpr_l2` = the same, computed only on rows that pass Layer 1.
- `rows` only with `--rows`.

## Decision (`gatepy.serve.score(snapshot)`, optional `POST /gate/risk`)

```json
{"decision": "skip", "layer": "L2", "l1_failures": [], "risk": 0.81, "threshold": 0.42,
 "model_id": "r2-3f9c1a", "top3": [["price_ratio", 0.22, 1.9], ["...", 0, 0], ["...", 0, 0]]}
```
`layer` is `"L1"` if any Layer 1 rule failed, `"L2"` if the risk is ≥ threshold, else `null` with `decision: "buy"`.

## Model file (`gate/models/{model_id}.json`)

```json
{"model_id": "r2-3f9c1a", "round": 2, "kind": "lightgbm",
 "features": ["price_ratio", "..."], "monotone": [-1, 0],
 "threshold": 0.42, "booster": "<lightgbm model_to_string>", "coef": null,
 "train_data_hash": "...", "feature_code_hash": "...", "created_at": "...", "val_metrics": {}}
```
`promoted.json`: `{"model_id": "...", "history": [{"model_id", "round", "promoted_at", "val", "holdout"}]}`.

## Feature plugin API (`gate/features/*.py`; the coordinator may edit these)

```python
from gatepy.registry import feature

@feature("price_ratio", monotone=-1)      # -1: risk must not rise as this value rises
def price_ratio(s: Snapshot, ctx: Ctx) -> float:
    return s.item.priceUsd / ctx.median(s.item.id)
```
Pure, deterministic, finite float, no I/O or network. `gate-train` self-tests every feature on `contracts/examples`
before training; a failure exits 2.

## Attack spec (input to `generate_attacks`, plan B1)

```json
{"round": 1, "family": "too_cheap", "n": 60, "legit_ratio": 0.4,
 "target_weakness": "price between 40-45% of median with a believable reason",
 "base_items": ["tetris-gb", "mario-kart-64-n64"], "constraints": {"max_price_usd": 10}}
```
`family` must not be in `families.json.holdout_families`. `legit_ratio` of the `n` slots become `legit_*` listings
in the same Bitdeer calls.
