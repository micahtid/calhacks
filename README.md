# The Shopping Agent That Can't Be Scammed

Cal Hacks 13.0 project. Plan and outline: https://calhacks.micahtid.com

An AI shopping agent you can actually trust with your money. The LLM finds deals, but it never holds the wallet. Deterministic code checks every purchase against rules you set once, and only then signs an x402 payment in USDC.

## The problem

- AI can already find good prices, but only about 1 in 10 people will let an agent complete a purchase. Trust collapses between discovery and checkout, especially for larger amounts.
- That fear is justified. Studies (Guardio, Microsoft + ASU, F-Secure, Unit 42) show agents buying from fake stores, paying scammers after reading fake reviews, leaking user data, and getting hijacked by hidden text in listings.
- Projections put AI-driven US sales at $300-500B by 2030 (10-20% of US e-commerce). Payment rails (Visa, Mastercard, Coinbase x402) already exist. Trust is the missing piece.

## The answer

1. **You set rules once:** the item, a maximum price, and a spending cap.
2. **The agent shops** within those rules with no further approval.
3. **Code, not the AI, controls the money.** Before any payment, the Gate checks domain, price, wallet, and cap. The LLM has no wallet access.

### Scam types we defend against

| Scam | Gate check |
|---|---|
| Lookalike domain | Domain matches a known/verified store |
| Too cheap | Price is not suspiciously below market |
| Lookalike wallet | `payTo` matches the wallet published in `/.well-known/store.json` |
| Prompt injection | Hidden instructions in listing text cannot change the decision |
| Fake reviews | Review signals are not trusted on their own |
| Unverified seller | Seller identity/verification is required |

## Architecture

```
LLM side (no wallet)            Code side (holds wallet)         Payment rails
---------------------           ------------------------         -------------
You (goal + rules)              Gate (buy / skip)                Facilitator (x402.org)
Scout (Claude)          ---->   Wallet (viem signer)     ---->   Base Sepolia (USDC)
Listings (Apify crawler)
                                Storefronts (real + scam)
Training loop: Factory (Fix Droid), Bitdeer (scam writer)
```

### How the Gate learns

1. **Spec:** Factory writes a spec: products, real vs fake listing counts, scam tricks.
2. **Generate:** Bitdeer workers write fake listings next to real Apify listings, each keeping its label.
3. **Judge:** The Gate decides buy or skip on each raw listing (nothing reaches a storefront).
4. **Score:** Decisions are compared to labels: scams caught vs real deals wrongly skipped.
5. **Fix:** The Gate is improved, then the loop repeats.

**Open decision for the Gate:**

- **A. Two layers (Factory):** TypeScript rules check domain, wallet, price, cap. A risk score can only reject, never approve. A Factory Droid patches the rules and opens a PR on each miss.
- **B. ML model (Bitdeer):** A classifier trained on labeled listings in Bitdeer AI Studio scores each listing and retrains on misses each round.

### Proof methodology

- Rebuild real stores from Apify-scraped Amazon, eBay, and Craigslist listings, then plant ~200 scams (lookalike sites, scam sellers) among them.
- Keep 20% of scams held out as a final exam the Gate never trains on.
- Metric: **catch rate** (share of scams stopped), plus real deals wrongly skipped. Target story: e.g. 38% on the first agent rising to 97% after three rounds of fixes (illustrative, not yet measured).
- Demo call to action: judges try to scam the agent themselves.

## Store API (x402)

Each storefront is agent-facing: no accounts, payment is the authorization. Reference store: "Pixel Cart Retro" (used retro games, $2.50-$9.00) at https://calhacks.micahtid.com/store, docs at `/store/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/.well-known/store.json` | Store metadata: name, seller ID, `payTo` wallet, network, price range, rating, endpoint paths |
| GET | `/api/catalog` | All listings with price and stock |
| GET | `/api/items/{id}` | One listing with description, rating, reviews |
| POST | `/api/checkout/{id}` | Buy one item, paid via x402 |

### Checkout flow

1. Agent `POST /api/checkout/{id}` with body `{ "shipTo": { "name": "...", "address": "..." } }`.
2. Store replies `402 Payment Required` with a base64 `PAYMENT-REQUIRED` header and body:
   ```json
   {
     "x402Version": 2,
     "accepts": [{
       "scheme": "exact",
       "network": "eip155:84532",
       "amount": "2500000",
       "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
       "payTo": "<store wallet>"
     }]
   }
   ```
   `amount` is in USDC base units (6 decimals, so `2500000` = 2.50 USDC). `asset` is USDC on Base Sepolia.
3. **The Gate runs here.** Only if domain, price, wallet, and cap pass does the agent sign the exact amount (signing moves no funds; the key never leaves the agent).
4. Agent retries the POST with a `PAYMENT-SIGNATURE` header.
5. Store forwards to the facilitator, which verifies signature, balance, amount, and receiver.
6. Store validates the order (missing `shipTo` returns 400, nothing settles).
7. Facilitator settles the USDC transfer on Base Sepolia and pays gas.
8. Store returns `200` with a base64 `PAYMENT-RESPONSE` header (includes tx hash) and:
   ```json
   { "orderId": "ord_...", "status": "confirmed", "item": { "id": "tetris-gb", "title": "Tetris" }, "amount": 2.5, "currency": "USDC" }
   ```

Errors: `400` missing `shipTo` (no money moves), `402` no or rejected payment, `404` unknown item, `409` sold out (returned before any payment request). Payments are irreversible; refunds are out of scope. Testnet only, nothing ships, orders are not persisted.

### Configuration

| Variable | Purpose |
|---|---|
| `STORE_PAY_TO` | Store wallet address where payments land |
| `BUYER_PRIVATE_KEY` | Agent wallet key that signs payments. Fund with free test USDC from https://faucet.circle.com |

| `MONGODB_URI` | MongoDB Atlas connection string, read from `.env.local` / `.env` at the repo root |
| `MONGODB_DB_REDTEAM` | Database for listings, answer keys and Gate references (default `redteam`) |

Secrets go in `.env` files (gitignored). Commit only `.env.example`.

## Shared contracts (red team + Gate)

`contracts/` holds the schemas from issue #1 as the `calhacks-contracts` uv package (pydantic models, a TypeScript mirror in
`contracts/ts/`, generated JSON Schemas in `contracts/schemas/`) plus the MongoDB access layer. Details:
`contracts/interfaces.md`; plan: `docs/plans/redteam-gate.md`.

- **One `Listing` shape** for real listings, synthetic listings and the Gate's input. A synthetic listing's answer key
  (label, family, attack diff) and generator info are stored in separate collections the Gate never reads.
- **All data lives in MongoDB** (`redteam` database): listings, cases (mandates), answer keys, and the references the Gate
  looks up itself: known sellers, market medians, wallet first-seen dates.
- **Getting real data in:**

  ```sh
  cd contracts
  uv run contracts-ingest listings FILE.jsonl --source apify:ebay   # Listing per line
  uv run contracts-ingest known-sellers FILE.json
  uv run contracts-ingest medians FILE.json --source apify:ebay-sold
  uv run contracts-ingest stats
  uv run pytest                                                     # tests use mongomock, not Atlas
  ```

- **Attack families** (`contracts/families.json`): Layer 1 catches payment mismatch, bait-and-switch and product
  switch by rule. Layer 2 handles lookalike wallets and unknown sellers within the cap, too-cheap, prompt injection, hidden
  text and fake reviews.
  `urgency_pressure` and `lookalike_domain` are held out of training entirely, for the final exam.
- **Seller trust:** a **known wallet** (on the known-seller list) is trusted. An **unknown wallet** is paid only up to `unknown_seller_cap_usd` ($100, `contracts/allowlist.json`), and Layer 2 then decides; $100 covers about 92% of the scraped listings. CRS is not used.

On this network uv may need `UV_SYSTEM_CERTS=1` (TLS interception).

## Gate

Two layers decide whether the wallet may pay; both must say yes. Details: `gate/README.md`.

- **Layer 1** (`gate/layer1`, TypeScript, fixed rules that are never learned): checkout wallet matches `store.json`; a known
  wallet, or an unknown wallet priced within `unknown_seller_cap_usd` ($100); 402 amount equals
  the price; price within max price and spend remaining; network and asset allowlisted; checkout item and product match the
  listing and the mandate; 402 timeout at most 120s. `node gate/layer1/src/cli.ts < gate_inputs.jsonl`. It is an npm
  workspace: `npm run test:gate-l1`; root `npm run build` / `npm run lint` typecheck it.
  `L1_SELLER_UNTRUSTED` stays a valid (deprecated) `RuleId` only for the agent API's mock Gate; Layer 1 no longer runs it.
- **Layer 2** (`gate/gatepy` + `gate/features`, Python): a LightGBM risk score that runs only when Layer 1 passes and can
  only turn a buy into a skip. Features from issue #1: price vs median, known wallet and wallet age,
  domain and wallet lookalikes, injection and hidden-text scores, review similarity. Each decision carries its top 3 reasons.
  Feature files are checked statically before import (`gatepy.sandbox`): no file, env, network or object-graph access.
- **Data:** training and evaluation read listings, mandates and references from MongoDB (`MONGODB_DB_REDTEAM`); answer keys
  are used only for scoring. `uv run --project gate gate-train --round N`, `uv run --project gate gate-eval --model promoted`.
- **Purchase time:** `gatepy.serve` scores a `GateRequest` (`POST /gate/risk`), fetching the listing and references itself
  and failing closed.

## Red-team loop

`redteam/` (uv project) makes attack listings, keeps the sealed holdout, and runs the Factory coordinator. All
listings live in MongoDB through `calhacks-contracts`; nothing is read from local data files. Full command list:
`redteam/README.md`.

- **Scraped-listing snapshot** (`redteam.scrape_map`): reads `calhacks.listings` (read-only) and writes a frozen local
  issue #1 snapshot (e.g. `scrape-v1`). It holds:
  - placeholder wallets per seller
  - brand + type product keys
  - the top 10 reputable sellers as known wallets
  - no wallet first-seen dates by default (no real history yet; `--wallet-history` restores the old heuristic for comparisons)
  - medians from the training side (with a type-level fallback)
  - a $500 budget per case
  - a seller-level split: ~80% training bases, ~20% locked-test bases reserved for the holdout
  `uv run --project redteam python -m redteam.scrape_map --out <dir> --as-of YYYY-MM-DD`
- **Artifact audit** (`redteam.audit`): checks whether generated listings can be told apart from real ones by
  anything other than the attack. Per family, a classifier on untouched traits (seller-name shape, wallet age,
  review count and length, text length) reports a grouped-CV AUC and a permutation p-value; a family fails when
  AUC > 0.6 and p < 0.05 (a tell the Gate could learn instead of the scam). Each family is compared with the real
  listings it draws bases from. `uv run --project redteam python -m redteam.audit --store <local store dir>`
- **Local dry runs** (`redteam.dryrun`): the full loop against a snapshot with no MongoDB. A file-backed store
  (`REDTEAM_LOCAL_STORE`) is shared between the coordinator and the MCP server and saved after every tool call. The
  holdout is built from the snapshot's locked-test listings (including those real listings, unmodified).
  `REDTEAM_ATTACKER_KNOWLEDGE` and `REDTEAM_SEED` fix the attacker type and seed. Run each dry run from its own git
  worktree, so the coordinator's feature edits are saved per round as diffs and never touch committed code:
  ```sh
  uv run --project redteam python -m redteam.dryrun init    --run DIR --snapshot SNAP [--seed N] [--knowledge white_box] [--all-known]
  uv run --project redteam python -m redteam.dryrun holdout --run DIR [--per-family 60 --slice 20]
  uv run --project redteam python -m redteam.dryrun round   --run DIR --round N [--max-listings 300]
  uv run --project redteam python -m redteam.dryrun summary --run DIR   # summary.json + summary.md
  ```
- **Attack factory** (`redteam.generate`): an `AttackSpec` in, `SyntheticListing`s out to MongoDB. The main mode,
  `mutate_real`, copies a real listing and changes one thing in code (wallet, price, checkout id, product, seller,
  domain, hidden text), recorded in the answer key's `attack_diff`. `mutate.ALLOWED_DIFF` lists the only fields each
  family may change and anything else is rejected, so a scam keeps its real seller; only seller-themed families
  (unknown seller, new honest seller, lookalikes) get a new one, named in the style of real sellers on the same
  marketplace (`mutate.styled_name`), never from a fixed pattern. Hidden-text instructions and honest discount reasons are worded by the LLM (code
  still hides the instruction); without a Bitdeer client they come from large combinatorial pools, never a few fixed
  sentences. Every LLM rewrite must keep the base listing's shape (text length within 0.7-1.4x, the same number of
  reviews), and a `legit_rewrite` control family runs honest listings through the same prompt, so LLM-written style
  shows up on both sides. Families that need wording (prompt injection,
  fake reviews, urgency, mixed reviews) get their text or reviews rewritten by Bitdeer (GLM-5.3-Flash and
  DeepSeek-V4.1-Flash in rotation). Bad LLM output is retried once, then dropped, and drops are counted per family.
- **Holdout** (`redteam.holdout`): built once from the real listings, holding the two held-out families plus a slice
  of every other family, with text written by Nemotron. It's stored encrypted outside the repo with its simulated
  references, never in MongoDB, and scored in memory to totals only.
- **Coordinator** (`redteam.coordinator`): one Factory Droid SDK session per round on Bitdeer DeepSeek-V4.1-Flash, with
  a GLM-5.3 attack-strategist droid. It sees the world only through the stdio MCP tools (`get_round_input`,
  `generate_attacks`, `score_round`, `inspect_failures`, `train_gate`, `eval_gate`, `promote_model`). A guard hook
  limits edits to `gate/features/<name>.py` and `gate/train_config.yaml`, and Gate subprocesses never receive the holdout key. Promotion (validation recall up, Layer 2 false blocks ≤ 2% — Layer 1 policy blocks such as unknown wallets over the cap are reported separately, no
  family down more than 5 points) and the `RoundReport` numbers are computed in code.
- **Gate backend:** the real Gate in `gate/` (path dependency). `REDTEAM_GATE=stub` selects a fast stand-in used by unit tests.

  ```sh
  uv run --project redteam python -m redteam.generate --round 1 --family too_cheap --n 40 --legit-ratio 0.4
  uv run --project redteam python -m redteam.coordinator --round 1 --max-listings 60
  uv run --project redteam python -m redteam.report
  uv run --project redteam pytest          # mongomock + fake Bitdeer client, no network
  ```

## Prize tracks

Visa, Hyphenate, Coinbase x402 (payment protocol), Apify (real listings), Factory (spec + Fix Droid), CRS, Armadin, Bitdeer (scam generation / classifier), Cal Hacks Overall.

## Repository layout

```
apps/
  agent/     Python FastAPI shopping agent backend (uv, Python 3.13), port 8000
  store-a/   Next.js 16 storefront, port 3001
  store-b/   Next.js 16 storefront
  store-c/   Next.js 16 storefront
contracts/   Shared schemas (issue #1), MongoDB access and ingestion CLI (uv package calhacks-contracts)
docs/plans/  Red-team loop + Gate implementation plan
package.json npm workspaces for the stores + root dev scripts
```

## Running locally

Requires Node.js and [uv](https://docs.astral.sh/uv/).

```sh
npm install
npm run dev          # agent + all three stores via concurrently
npm run dev:agent    # agent only (http://localhost:8000, GET /health)
npm run dev:store-a  # one store
npm run build        # build all stores
npm run lint         # lint all stores
```

## Implementation status

Keep this section current (see `AGENTS.md`).

- [x] Monorepo scaffold: FastAPI agent with `/health`, three default Next.js store apps
- [x] Shared schemas from issue #1 (`Listing`, `SyntheticListing`, `AttackSpec`, `RoundInput`, `RoundReport`, `GateRequest`, `GateDecision`) as pydantic + TypeScript, with MongoDB repository and ingestion CLI
- [ ] Real listings, known sellers and market medians ingested into MongoDB
- [ ] Storefront API (`store.json`, catalog, items, x402 checkout) in each store
- [ ] Scam storefront variants (lookalike domain/wallet, too cheap, prompt injection, fake reviews, unverified seller)
- [ ] Apify listing ingestion
- [ ] Scout (Claude) agent loop
- [x] Gate Layer 1: fixed TypeScript rules over the issue #1 `GateInput`
- [x] Gate Layer 2: LightGBM risk model trained and evaluated on MongoDB data, `POST /gate/risk`
- [ ] Wallet signer + x402 payment against Base Sepolia
- [x] Bitdeer attack generation from real MongoDB listings (`mutate_real` / `generate`), labels and attack diffs set by code
- [ ] Labeled dataset generated from real listings (blocked on real listings in MongoDB)
- [x] Scoring harness: issue #1 RoundMetrics (Wilson intervals, `fpr_real`, `adaptive_recall`), encrypted holdout scored to totals only, rounds table from MongoDB
- [x] Factory coordinator loop: per-round Droid SDK session, MCP tools, guard hook, strategist droid, code-enforced promotion, connected to the real Gate (train, evaluate, promote with holdout totals, restore on revert)
- [ ] Demo UI (rules input, payment view)
