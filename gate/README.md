# Gate

Two layers decide whether the wallet may pay. Both must say yes.

| Layer | Where | What |
|---|---|---|
| 1 | `layer1/` (TypeScript) | Fixed rules, never learned: wallet match and lookalikes, amount, max price, budget, network/asset/scheme allowlist, timeout, checkout item |
| 2 | `gatepy/` + `features/` (Python) | LightGBM risk model on structured features, monotone in price and seller age, fixed threshold |

Interfaces are in `../contracts/interfaces.md`.

## Commands

```sh
# from the repo root; add --system-certs to uv on this machine (TLS interception)
npm test -w @calhacks/gate-layer1                     # Layer 1 tests
node gate/layer1/src/cli.ts < snapshots.jsonl          # gate-l1

uv run --project gate gate-fixtures --n 400            # dev-only synthetic data -> data/rounds/R0/fixture.jsonl
uv run --project gate gate-train --data data/rounds/R0 --round 0 --config gate/configs/r0_baseline.yaml
uv run --project gate gate-train --data data/rounds --round 1
uv run --project gate gate-eval --model r1-xxxxxx --data data/rounds --split val --rows
uv run --project gate pytest                            # run inside gate/
```

## Notes for the red-team loop

- The coordinator may edit only `features/*.py` and `train_config.yaml`. New features use `@feature(name, monotone=...)`
  and must be pure; `gate-train` self-tests them and exits 2 on failure.
- `gate-train` refuses data containing holdout families (exit 2).
- Layer 2 trains only on rows that pass Layer 1, which is what it sees at purchase time.
- On revert, call `gatepy.model_io.restore_features("promoted")`. Features are edited in place, so a rejected
  candidate's code would otherwise be scored with the promoted model. Each model file carries its feature sources.
- `gatepy.model_io.set_promoted(model_id, val=..., holdout=...)` moves the pointer. The promotion rule (C6) belongs to redteam.
- `gatepy.serve.score(snapshot)` / `make_router()` (`POST /gate/risk`) are for the wallet. Treat any error as "skip".
