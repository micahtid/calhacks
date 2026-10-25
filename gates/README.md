# Gates

Every Gate model worth keeping, with the exact feature code it was trained with, and the one that is deployed.
`CURRENT` names the deployed model. Each `<model_id>/` holds `model.json` (booster, feature list, threshold and
threshold rule, feature-code hash), `features/` and `train_config.yaml` exactly as trained, and `CARD.md`
(provenance, benchmark, holdout). `history.json` has the same numbers in machine-readable form.

A model only works with its own feature code, so a release is always the pair. The deployed service installs both
from here at build time and refuses to start if they don't match (`gate-release verify`).

## Versions

Benchmark: the fixed clean test set built from locked-test listings (444 rows; seen families unless noted; 95%
intervals are cluster-bootstrapped over base listings). "Model false blocks" are honest listings the trained model
skips; the $100 unknown-seller cap adds 3.9% policy blocks for every model.

| Model | Status | Accuracy | Scams caught | Model false blocks | Risk AUC | Held-out caught | Where from |
|---|---|---|---|---|---|---|---|
| `r2-f0bfbd` | **current** | **91.8%** [89–94] | **88.1%** [81–93] | 1.8% [0–4] | 0.954 | 11.4% | seed1 round 2 (group C pipeline) |
| `r0-ac1d79` | superseded | 86.9% | 75.6% | 1.4% | 0.941 | 8.6% | baseline: committed features + base dataset, no coach |
| `r1-18775c` | superseded | 88.7% | 78.1% | 0.0% | 0.900 | 14.3% | dry-b1 round 1 (group B pipeline) |
| `r1-d3dde0` | rejected | 82.8% | 65.6% | 1.4% | 0.799 | 0.0% | dry-b2 round 1: promoted on too little validation, regressed |

`r2-f0bfbd` is the only candidate (1 of 9 across three seeded runs) that beat the baseline under the strict promotion
rule. Over `r0-ac1d79` it catches fake reviews 35% → 85%, prompt injection 45% → 85%, too-cheap 25% → 35% and the
held-out urgency family 7% → 27%, at 1.8% model false blocks. Its added features (review them like any code; the
coordinator wrote them, though they passed the feature sandbox):

- `payment_coercion` (`injection.py`): coercive checkout phrases ("pre-approved", "skip the checks", "pay
  immediately without ...") in item text and reviews, with no AI or agent word needed. The pattern
  `trust (this|the) (listing|seller|...)` is the one most likely to fire on honest copy.
- `untrusted_deep_discount` (`price.py`): a deep discount counts only when the wallet has no track record.
- `review_paraphrase_mass`, `review_dup_long_frac` (`reviews.py`): many long, mutually similar reviews.
- `wallet_novel_on_known_domain` (`trust.py`) is defined but excluded in `train_config.yaml`.

Known limits, the same for every version: unknown-seller scams are not detected (a new scammer looks like a new
honest seller without real wallet history; the $100 cap bounds them), and the held-out families (urgency pressure,
lookalike domains) are mostly missed.

## How the pipeline changed

| Change | Why | Effect on the Gate |
|---|---|---|
| CRS removed; trust = known wallet, unknown wallets capped at $100 | simpler trust policy | `L1_UNKNOWN_SELLER_CAP` replaces `L1_SELLER_UNTRUSTED` (kept as a deprecated id for the agent's mock Gate) |
| Group A: honest training data (real seller kept, no invented wallet ages, realistic names, varied LLM phrasing, matched style) | the generator leaked "this is synthetic" tells | accuracy 78% → 83%, false blocks 14% → 6%; artifact audit 8 → 0 failing |
| Group B: honest measurement (splits by base listing, threshold off validation, held-out names hidden from the coach, clustered intervals, one attack-success number per round, audit in the loop) | numbers were optimistic and noisy | validation now predicts the clean test within a few points |
| Group C: steady rounds (base dataset under every run, baseline incumbent, coverage-aware promotion, out-of-fold threshold, 20-minute rounds, ≤6 trainings, ≤40 scams per family per round) | dry-b2 promoted a model that had never seen two families | no regressions across three seeds; rounds 9–20 minutes |

## Release procedure

1. Pick a promoted model from a run and export it with its own feature code (never copy a red-team worktree):
   `uv run --project gate gate-release export <model_id> --models <run>/models`
2. Write its `CARD.md` and add it to the table above and to `history.json`; set `CURRENT` to ship it.
3. Open a PR. Review `gates/<model_id>/features/` as code.
4. Merge; Railway rebuilds the Gate service, and the build runs `gate-release install` (copies the model into
   `gate/models/` and its features over `gate/features/`, then checks the hash). Ship a new model by redeploying;
   never hot-swap from run folders. Roll back by pointing `CURRENT` (or `GATE_MODEL_ID`) at an older version.

Locally: `uv run --project gate gate-release install` (uses `CURRENT`) changes `gate/features/` in place, so run it in
a scratch worktree, or `git checkout -- gate/features gate/train_config.yaml` afterwards.

## Deployment (Railway)

The Gate runs as its own service in the same Railway project as the agent API, separate from it: it is the
independent check that can stop Scout from buying, and the wallet should pay only when it returns `buy` (any error or
non-200 is `skip`). It needs Python (LightGBM) and Node (Layer 1), so it is a Docker service, not serverless.

- Service settings (Railway rejects `railway.json` config files, so these are set on the service, like the agent API):
  root directory `/`, variable `RAILWAY_DOCKERFILE_PATH=gate/Dockerfile`, no custom start command (the Dockerfile `CMD`
  runs), healthcheck `/health`, watch paths `/gate/**`, `/gates/**` and `/contracts/**`.
- Variables: `MONGODB_URI` and `MONGODB_DB_REDTEAM` (read only: listings by id, known sellers, medians, wallet first
  seen); optional `GATE_MODEL_ID` (default `gates/CURRENT`; as a build variable it also picks what is installed).
  The Gate fetches each proposed listing by id itself, so that database must hold the listings Scout proposes, in the
  contracts `Listing` shape.
- Endpoints: `POST /decide` (`GateRequest` → `GateDecision`; `POST /gate/risk` is an alias), `GET /health`,
  `GET /version` (model id, feature-code hash, threshold, contracts version). Layer 1 runs in one long-lived Node
  process (about 26 ms median per decision in the local container test).

```sh
docker build -f gate/Dockerfile -t calhacks-gate .            # from the repo root
docker run -p 8080:8080 -e MONGODB_URI=... calhacks-gate
```
