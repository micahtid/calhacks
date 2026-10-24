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
Scout (Bitdeer GLM)     ---->   Wallet (viem signer)     ---->   Base Sepolia (USDC)
Listings (Apify crawler)        CRS (optional)
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

## Live store search (Apify Standby)

The chat's "Searching Stores" step reads our hosted storefronts live through an Apify Actor in Standby mode, and the
agent API streams what it finds to the browser as it arrives.

```
Browser (Vercel)  <- SSE -  agent API (Railway, FastAPI)  <- NDJSON -  store-crawler Actor (Apify Standby)  ->  storefronts
```

- **Actor** (`apps/agent/api/actor`, Python): `GET /search?stores=&q=&max=&details=` streams one JSON event per line.
  Per store it fetches `/api/catalog` and `/.well-known/store.json` in parallel, so listings go out ~250ms in while
  `store.json` (1.5-3s, it reads the wallet per request) is still loading. Then it fetches every matching item page
  (50 at a time, retries on network errors, 429 and 5xx).
  - Events: `listing` (catalog fields + absolute `url`/`checkoutUrl`), `store` (`name`, `payTo`, `network`,
    `currency`), `page` (`title`, `h1`, `text`, `images`, `hiddenText`, `jsonLd`), `error` (one store or page; the
    search goes on), `done` (counts and `ms`).
  - `q` matches when every word appears in the title, so `jacket` also matches "Jackets"; empty matches everything.
  - Page extraction works on any store: it applies React's streamed-HTML swap (content arrives in `<div hidden id="S:n">`),
    joins text nodes with spaces in document order, and collects `hiddenText` (`hidden`, `sr-only`, inline
    `display:none` and similar). Text hidden by stylesheet rules is not detected.
  - Standby URLs collapse `//` in query strings, so store URLs are normalized (`https:/host` and bare hosts work).
- **Agent API** (`apps/agent/api/app`): `GET /search?q=&max=&max_price=` relays the Actor's events as SSE (`event:`
  is the event type). Searches cover `STORE_URLS`, by default mzn, by, dpp and the mzn Official Outlet scam store. If the
  Actor can't be reached, the stream sends one `error` event and ends.
- **Mock Gate** (`app/gate.py`, until the real Gate can judge live listings): right after each item's `page` (or
  page `error`) the stream sends a `verdict` event with the contracts' `GateDecision` fields plus `store` and `key`,
  with `model_version: "mock"`. The UI can be built against it now, and the real Gate can replace it without changing
  the stream.
  - Layer 1: the store's domain must be mzn, by or dpp (`L1_SELLER_UNTRUSTED`), and the price must be at most
    `max_price` (`L1_OVER_MAX`). It checks domains, not wallets, because the hosted stores and the outlet share one
    test wallet.
  - Layer 2 (hand-weighted, threshold 0.5): prompt-injection patterns in the page or hidden text (0.7), any hidden
    text (0.6), and a price under 10% of the search's median price so far (0.6). The patterns are the seed list in
    `contracts/injection_patterns.json`, the same one the real Gate's Layer 2 counts.
  - Known stores come from the one store list in `app/search.py`, and every decision is validated as a contracts
    `GateDecision` before it is sent.
  - A page that could not be fetched is a skip with `decided_by: null` and an `error`, like the real Gate's fail-closed 503.
  - On a live search of all 686 listings it skipped all 148 outlet listings at Layer 1 and approved every real one.
  - Self-check: `uv run python -m app.gate` (from `apps/agent/api`).
- **Measured** (agent API -> Standby, `q=fleece jacket`, 10 per store, 3 stores): first listing 0.2-0.5s, all 30 pages
  in about 2s. All 317 items take 3.0s at 4 GB and 18.5s at 1 GB: Apify gives CPU in proportion to memory, and
  parsing (~10ms a page) needs it. Standby is set to 4 GB in the Apify console. The first request after 5 minutes idle
  adds a 2.5-3.5s cold start.
- **Deploying the Actor:** `cd apps/agent/api/actor && apify push`. Version 0.2 tags each build `latest`, which is
  the build Standby serves.

| Variable | Where | Purpose |
|---|---|---|
| `APIFY_ACTOR_URL` | agent API | Standby URL (`https://lauded-crevasse--store-crawler.apify.actor`), or `http://localhost:4321` for a local Actor |
| `APIFY_TOKEN` | agent API | Apify token, sent as a Bearer header to the Standby URL |
| `STORE_URLS` | agent API | Optional comma-separated store origins (default: the four hntr.store stores) |
| `CORS_ORIGINS` | agent API | Comma-separated browser origins allowed to call the API (default `http://localhost:3000`) |
| `BITDEER_API_KEY` | agent API | Bitdeer Model Studio key for the Scout |
| `BITDEER_MODEL` | agent API | Optional model id (default `zai-org/GLM-5.3-Flash`) |
| `NEXT_PUBLIC_AGENT_API_URL` | agent web | Agent API origin, inlined at build time (default `http://localhost:8000`) |
| `BUYER_PRIVATE_KEY` | agent API | Hunter's wallet key; signs x402 payments in `app/pay.py`. Unset: runs stop before paying |
| `SHIP_TO_NAME`, `SHIP_TO_ADDRESS` | agent API | Optional ship-to sent at checkout (default a demo address; nothing ships) |
| `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`, `CDP_WALLET_SECRET` | agent API | Coinbase Developer Platform keys for the faucet behind Add Funds (`app/wallet.py`). Unset: only Add Funds fails |

Locally the agent API reads `apps/agent/api/.env` and the web app `apps/agent/web/.env.local`; both have a
`.env.example`. The API depends on `contracts/` (`calhacks-contracts`, a uv path dependency like in `gate/` and
`redteam/`), so Railway builds it from the repo root: root directory `/`, config file `apps/agent/api/railway.json`,
which builds `apps/agent/api/Dockerfile` and redeploys on changes under `apps/agent/api/` or `contracts/`.

## Wallet (Settings and Transactions)

The agent web app reads Hunter's wallet (`AGENT_WALLET` in `apps/agent/web/lib/wallet.ts`) live from Base Sepolia
through the agent API (`app/wallet.py`):

- `GET /wallet/{address}`: the USDC balance, read on chain with `eth_call` on `https://sepolia.base.org`, and every
  USDC transfer in or out (`hash`, `at`, `direction` sent|received, `amount`, `counterparty`, `explorer`), newest
  first, from the Blockscout API (`https://base-sepolia.blockscout.com`, no key needed, up to 250 transfers).
- `POST /wallet/{address}/fund`: test USDC from the CDP faucet (`request_faucet`, Base Sepolia). Measured: 1 USDC a
  request, landing within a few seconds. The faucet rate-limits each address; its refusal comes back as the `detail`.
- **Settings** shows the balance and an Add Funds button, then reads the balance again until the funds land.
- **Transactions** lists the real transfers (sent or received, counterparty, time, amount, Basescan link), with
  totals spent and left. The sample transactions are gone; the sample chats remain.
- Self-check: `uv run python -m app.wallet` (from `apps/agent/api`).

## Hunter chat run (Scout + live search)

A new chat in the agent web app is one live run: the browser opens `GET /chat?prompt=` on the agent API as an
`EventSource`, and the stages fill in as events arrive. The Scout is the LLM (Bitdeer, `zai-org/GLM-5.3-Flash`,
OpenAI-compatible at `https://api-inference.bitdeer.ai/v1`); it never touches money.

1. **Understand** (`app/scout.py`): the model reads the request and returns JSON with `item`, `query` (1-3 title
   words), `max_price` and 2-4 `thoughts`, all validated in code. Sent as `thought` and `instruction` events.
2. **Search and check:** the live search above with that query and limit, 25 listings per store, and a mock Gate
   `verdict` per listing. If a query finds nothing, it is retried with its first word dropped ("warm fleece jacket",
   then "fleece jacket", then "jacket"), with a `search` event per query. Page text stays on the server for the Scout.
3. **Pick:** the model ranks up to 30 of the cheapest Gate-approved listings and returns up to 3 picks with a
   one-line note. Listing text is passed as untrusted data, and a pick that doesn't name an offered listing is dropped.
   If the model fails or names nothing usable, the 3 cheapest approved listings are picked in code.
4. **Pay** (`app/pay.py`): the best pick is bought over x402 in the six steps the UI lists, each sent as a
   `checkout {step, state, detail}` event: start checkout (POST with a ship-to, the store answers 402), read the price
   and wallet from `PAYMENT-REQUIRED`, double-check in code (network and asset as in
   `contracts/allowlist.json`, amount equals the listed price, `payTo` equals the store.json wallet, within the
   limit), sign an EIP-3009 `TransferWithAuthorization` for exactly
   that amount with `BUYER_PRIVATE_KEY`, POST again with `PAYMENT-SIGNATURE`, and read the order and the transaction
   hash (`PAYMENT-RESPONSE`). A `receipt` event follows a real payment. The facilitator pays gas, so the wallet needs
   USDC but no ETH. Without `BUYER_PRIVATE_KEY` the run stops at "Approve the Exact Amount" (`state: blocked`) and
   nothing is signed. A failed check stops before signing.
   - Verified without paying: all four stores answer a correct v2 402, and a payload signed by `app/pay.py` with an
     unfunded key was rejected by the x402.org facilitator's `/verify` only for insufficient USDC balance.
5. **End:** `end` with `status: bought`, `ready` (everything checked, no wallet key) or `stopped`.

- **Reasoning:** GLM-5.3-Flash streams its thinking as `reasoning_content`. The agent API forwards it as
  `reasoning {stage: understand|pick, text}` events, and the UI shows it under a "Show Reasoning" toggle in the
  Understanding and Picking stages, collapsed by default. Reasoning counts against `max_tokens`, so calls allow 6000
  (at 600 the answer came back empty).
- **UI** (`apps/agent/web`): the same stages, summaries and receipt as the scripted demo it replaced
  ("192 Safe · 59 Scams Blocked", "mzn · 8.50 USDC", "Paid 8.50 USDC"), filled from the stream. Found listings
  join the feed one every 55ms and are checked one every 70ms (checking starts once every found listing is on screen),
  and each checkout step appears once its event arrives. Blocked rows show "Fake Store Website", "Hidden
  Instructions", "Too Cheap to Be Real" and similar. Listings over the user's limit are left out of the stream, as a
  price filter; the Gate and the checkout double-check still enforce the limit. The receipt shows the real payer,
  store wallet, order id, time and Basescan link; the store gives no delivery date, so there is no "Arrives" row.
- A run lives in its chat view: leaving a chat mid-run ends the stream and coming back starts it over. Finished runs
  are kept with the chat and shown without streaming again.
- **Measured** (local agent API, warm Standby Actor): first reasoning at 0.7s, request understood at 1.7-1.9s, first
  listing about 0.3-2.6s later, search and checks done by 5-12s, picks at 9.7-18.9s. The pick call takes 4-7s.
- Self-check: `uv run python -m app.scout` (from `apps/agent/api`).

## Shared contracts (red team + Gate)

`contracts/` holds the schemas from issue #1 as the `calhacks-contracts` uv package (pydantic models, a TypeScript mirror in
`contracts/ts/`, generated JSON Schemas in `contracts/schemas/`) plus the MongoDB access layer. Details:
`contracts/interfaces.md`; plan: `docs/plans/redteam-gate.md`.

- **One `Listing` shape** for real listings, synthetic listings and the Gate's input. A synthetic listing's answer key
  (label, family, attack diff) and generator info are stored in separate collections the Gate never reads.
- **All data lives in MongoDB** (`redteam` database): listings, cases (mandates), answer keys, and the references the Gate
  looks up itself: known sellers, CRS results, market medians, wallet first-seen dates.
- **Getting real data in:**

  ```sh
  cd contracts
  uv run contracts-ingest listings FILE.jsonl --source apify:ebay   # Listing per line
  uv run contracts-ingest known-sellers FILE.json
  uv run contracts-ingest medians FILE.json --source apify:ebay-sold
  uv run contracts-ingest crs FILE.json                             # CRS stand-in
  uv run contracts-ingest stats
  uv run pytest                                                     # tests use mongomock, not Atlas
  ```

- **Attack families** (`contracts/families.json`): Layer 1 catches payment mismatch, lookalike wallet, bait-and-switch,
  product switch and unverified seller by rule. Layer 2 handles too-cheap, prompt injection, hidden text and fake reviews.
  `urgency_pressure` and `lookalike_domain` are held out of training entirely, for the final exam.
- **Unknown sellers:** paid only if CRS-verified, and only up to `unknown_seller_cap_usd` ($100) in `contracts/allowlist.json`. $100 covers about 92% of the scraped listings.

On this network uv may need `UV_SYSTEM_CERTS=1` (TLS interception).

## Gate

Two layers decide whether the wallet may pay; both must say yes. Details: `gate/README.md`.

- **Layer 1** (`gate/layer1`, TypeScript, fixed rules that are never learned): checkout wallet matches `store.json`; wallet is
  a known seller's **or** the seller is CRS-verified (CRS-only sellers capped at `unknown_seller_cap_usd`); 402 amount equals
  the price; price within max price and spend remaining; network and asset allowlisted; checkout item and product match the
  listing and the mandate; 402 timeout at most 120s. `node gate/layer1/src/cli.ts < gate_inputs.jsonl`. It is an npm
  workspace: `npm run test:gate-l1`; root `npm run build` / `npm run lint` typecheck it.
- **Layer 2** (`gate/gatepy` + `gate/features`, Python): a LightGBM risk score that runs only when Layer 1 passes and can
  only turn a buy into a skip. Features from issue #1: price vs median, CRS verification and age, known wallet and wallet age,
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

- **Attack factory** (`redteam.generate`): an `AttackSpec` in, `SyntheticListing`s out to MongoDB. The main mode,
  `mutate_real`, copies a real listing and changes one thing in code (wallet, price, checkout id, product, seller,
  domain, hidden text), recorded in the answer key's `attack_diff`. Families that need wording (prompt injection,
  fake reviews, urgency, mixed reviews) get their text or reviews rewritten by Bitdeer (GLM-5.3-Flash and
  DeepSeek-V4.1-Flash in rotation). Bad LLM output is retried once, then dropped, and drops are counted per family.
- **Holdout** (`redteam.holdout`): built once from the real listings, holding the two held-out families plus a slice
  of every other family, with text written by Nemotron. It's stored encrypted outside the repo with its simulated
  references, never in MongoDB, and scored in memory to totals only.
- **Coordinator** (`redteam.coordinator`): one Factory Droid SDK session per round on Bitdeer DeepSeek-V4.1-Flash, with
  a GLM-5.3 attack-strategist droid. It sees the world only through the stdio MCP tools (`get_round_input`,
  `generate_attacks`, `score_round`, `inspect_failures`, `train_gate`, `eval_gate`, `promote_model`). A guard hook
  limits edits to `gate/features/<name>.py` and `gate/train_config.yaml`, and Gate subprocesses never receive the holdout key. Promotion (validation recall up, false blocks ≤ 2%, no
  family down more than 5 points) and the `RoundReport` numbers are computed in code.
- **Gate backend:** a stub with the same interface stands in until the Gate branch is merged (`REDTEAM_GATE=real` after).

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
  agent/api/ Python FastAPI shopping agent backend (uv, Python 3.13), port 8000
    actor/   store-crawler Apify Standby Actor (Python), port 4321 locally
  agent/web/ Next.js agent dashboard, port 3000
  store-a/   mzn, a general store (Next.js 16), port 3001
  store-b/   by, an auction marketplace, port 3002
  store-c/   dpp, a resale app, port 3003
  store-d/   mzn Official Outlet, a scam lookalike of mzn, port 3004
packages/
  common/    Shared store code: MongoDB listings, x402 checkout, highlights, page shell
  amazon/    Shared storefront used by mzn and its scam lookalike
contracts/   Shared schemas (issue #1), MongoDB access and ingestion CLI (uv package calhacks-contracts)
docs/plans/  Red-team loop + Gate implementation plan
package.json npm workspaces for the stores + root dev scripts
```

## Running locally

Requires Node.js and [uv](https://docs.astral.sh/uv/).

```sh
npm install
npm run dev            # agent API, agent dashboard, and all four stores via concurrently
npm run dev:agent-api  # agent API only (http://localhost:8000, GET /health)
npm run dev:store-a    # one store

# store-crawler Actor locally (from apps/agent/api/actor), then set APIFY_ACTOR_URL=http://localhost:4321
uv run --no-project --python 3.13 --with-requirements requirements.txt python -m src
uv run --no-project --python 3.13 --with-requirements requirements.txt python -m src.test_extract  # self-check
npm run build          # build every workspace
npm run lint           # lint every workspace
```

## Implementation status

Keep this section current (see `AGENTS.md`).

- [x] Monorepo scaffold: FastAPI agent with `/health`, three default Next.js store apps
- [x] Shared schemas from issue #1 (`Listing`, `SyntheticListing`, `AttackSpec`, `RoundInput`, `RoundReport`, `GateRequest`, `GateDecision`) as pydantic + TypeScript, with MongoDB repository and ingestion CLI
- [ ] Real listings, known sellers and market medians ingested into MongoDB
- [x] Storefront API (`store.json`, catalog, x402 checkout) in each store, with listings and highlights loaded from MongoDB
- [x] Store names and logos use the real names with the vowels removed (mzn, by, dpp)
- [x] Scam storefront (mzn Official Outlet: lookalike brand, too cheap, prompt injection, fake reviews)
- [ ] Apify listing ingestion
- [x] Live store search: store-crawler Apify Standby Actor streaming listings and item pages, relayed as SSE by the agent API (`GET /search`)
- [x] Mock Gate verdicts in the search stream (`GateDecision` shape, `model_version: "mock"`), standing in for the real Gate
- [x] Wallet in the agent web app: live USDC balance and Add Funds (CDP faucet) in Settings, real Base Sepolia transfers in Transactions
- [x] Agent web chat runs live from `GET /chat` in the demo's design (editable prompt, live feed and checks, picks, collapsed reasoning, checkout steps, receipt)
- [x] x402 checkout in the agent API (`app/pay.py`): real 402, double-check, EIP-3009 signing, settlement; `BUYER_PRIVATE_KEY` is the demo wallet (`0x7D06…Cea8`, also in `apps/agent/web/lib/wallet.ts`), which needs more faucet USDC before it can pay
- [x] Scout on Bitdeer GLM-5.3-Flash: reads the request, ranks Gate-approved listings, streams its reasoning (`GET /chat`)
- [x] Gate Layer 1: fixed TypeScript rules over the issue #1 `GateInput`
- [x] Gate Layer 2: LightGBM risk model trained and evaluated on MongoDB data, `POST /gate/risk`
- [ ] Wallet signer + x402 payment against Base Sepolia
- [x] Bitdeer attack generation from real MongoDB listings (`mutate_real` / `generate`), labels and attack diffs set by code
- [ ] Labeled dataset generated from real listings (blocked on real listings in MongoDB)
- [x] Scoring harness: issue #1 RoundMetrics (Wilson intervals, `fpr_real`, `adaptive_recall`), encrypted holdout scored to totals only, rounds table from MongoDB
- [x] Factory coordinator loop: per-round Droid SDK session, MCP tools, guard hook, strategist droid, code-enforced promotion (runs against a stub Gate until the Gate branch is merged)
- [ ] Demo UI (rules input, payment view)
