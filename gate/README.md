# Gate

Two layers decide whether the wallet may pay; both must say yes. The input is the issue #1 `GateInput` (mandate +
the listing the Gate fetched itself + references it looked up itself); the output is a `GateDecision`. Contracts:
`../contracts/interfaces.md`.

| Layer | Where | What |
|---|---|---|
| 1 | `layer1/` (TypeScript) | Fixed rules, never learned: 402 wallet matches `store.json`; wallet known **or** seller CRS-verified (CRS-only capped at `unknown_seller_cap_usd`); amount equals price; max price; spend remaining; network and asset allowlist; checkout item; product matches the mandate; 402 timeout |
| 2 | `gatepy/` + `features/` (Python) | LightGBM risk score, run only when Layer 1 passes and only able to turn buy into skip. Monotone in price and trust signals, fixed threshold, top-3 reasons |

## Data

Everything is read from MongoDB through `calhacks_contracts.db.Repo` (`MONGODB_URI` from `.env.local`, database
`MONGODB_DB_REDTEAM`, default `redteam`): `listings`, `cases` (mandates) and the reference collections. Answer keys are
read only to label and score; they never reach a feature. Holdout families in the database are refused. The Gate
never writes to MongoDB.

## Layer 2 features (`features/`, the coordinator may edit these and `train_config.yaml`)

| Module | Features |
|---|---|
| `price.py` | `price_ratio` (price / median, neutral 1.0 without a median), `price_too_low`, `has_median` |
| `trust.py` | `known_wallet`, `crs_verified`, `crs_days_verified`, `payto_age_days` |
| `domain.py` | `domain_known`, `domain_similarity_to_known` (exact match excluded) |
| `payment.py` | `payto_lookalike` (same first/last 4 hex as a known wallet), `payto_affix_match` |
| `injection.py` | `injection_hits_text`, `injection_hits_reviews`, `imperative_to_agent` (after removing invisible characters and NFKC folding) |
| `hidden.py` | `hidden_chars` (zero-width/format characters), `mixed_script_words` (homoglyphs) |
| `reviews.py` | `review_count`, `review_similarity_max` (cached embeddings via `features/_text.EMBEDDINGS` when present, else word overlap), `review_len_mean` |

Each is `@feature(name, monotone=-1|0|1)` on a pure `GateInput -> float`. `gate-train` self-tests every feature on
`contracts/tests/fixtures` plus a sample of training rows and exits 2 on failure. Ages are measured against
`GATE_AS_OF` (default: the process start date), recorded in each model file.

Before any feature module is imported, `gatepy.sandbox` checks every file in `features/` statically: imports only from
an allowlist (math, re, unicodedata, itertools, the contract models, `gatepy.registry`/`gatepy.clock`, `features._text`),
no `open`/`exec`/`eval`/`getattr`/`__import__`, no private or dunder attributes, no frame walking, no `'__'` strings. A
violation raises `FeaturePolicyError` (the CLIs exit 2) and nothing in `features/` runs. This matters because the
coordinator writes these files and the red-team MCP server scores the holdout in-process.

## Commands

```sh
# from the repo root; on this machine uv needs UV_SYSTEM_CERTS=1 (TLS interception)
npm test -w @calhacks/gate-layer1                      # Layer 1 tests
node gate/layer1/src/cli.ts < gate_inputs.jsonl         # gate-l1: {"listing_id", "checks"} per line

uv run --project gate gate-train --round 0 --config gate/configs/r0_baseline.yaml
uv run --project gate gate-train --round 1 [--query '{"family": {"$ne": "legit_plain"}}']
uv run --project gate gate-eval --model promoted --split val [--ids ids.txt] [--rows]
cd gate && uv run pytest                                # mongomock, never Atlas
```

## Notes for the red-team loop

- In-process scoring (used for the holdout, which never enters MongoDB):
  `gatepy.evaluate.evaluate(model, [(Listing, Case | None, AnswerKey), ...], refs)` where `refs` is a
  `calhacks_contracts.db.ReferenceSet` (e.g. `repo.reference_snapshot().overlay(crs=..., wallets=...)`).
- `gatepy.model_io.load(model_id)`, `set_promoted(model_id, val=..., holdout=...)`; the promotion rule (C6) belongs to redteam.
- On revert, call `gatepy.model_io.restore_features("promoted")`: features are edited in place, so a rejected
  candidate's code would otherwise stay live. Each model file carries its feature sources.
- Layer 2 trains only on rows that pass Layer 1. The threshold is the lowest risk cut with validation false blocks
  (legit rows reaching Layer 2) at most `threshold.max_fpr`.
- `gatepy.serve.Gate(...).score(GateRequest)` / `make_router()` (`POST /gate/risk`) are for the wallet. The Gate fetches
  the listing by `proposal.listing_id` and looks up references itself; any error is a 503 "skip".
