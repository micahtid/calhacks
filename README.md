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
| `MONGODB_URI` | MongoDB Atlas connection string, used by the agent and all stores |
| `MONGODB_DB_AGENT`, `MONGODB_DB_STORE_A/B/C` | Optional database names (default `agent`, `store-a`, `store-b`, `store-c`) |

Secrets go in `.env` files (gitignored). Commit only `.env.example`. Locally, copy `.env.example` to `.env.local` at the repo root: the agent and every store's `npm run dev` read it (via `scripts/with-env.mjs` for the stores). In production, set `MONGODB_URI` in each service's platform env vars (Vercel/Railway) and allow the platform's egress in Atlas Network Access; `build`/`start` read no env files.

## Prize tracks

Visa, Hyphenate, Coinbase x402 (payment protocol), Apify (real listings), Factory (spec + Fix Droid), CRS, Armadin, Bitdeer (scam generation / classifier), Cal Hacks Overall.

## Repository layout

```
apps/
  agent/     Python FastAPI shopping agent backend (uv, Python 3.13), port 8000
  store-a/   Next.js 16 storefront, port 3001
  store-b/   Next.js 16 storefront
  store-c/   Next.js 16 storefront
scripts/     with-env.mjs: loads root .env.local/.env before `next dev`
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

Health checks report MongoDB connectivity as `"db": "ok"`: agent `GET /health`, stores `GET /api/health` (503 if the database is unreachable). If `uv` fails with a TLS `UnknownIssuer` error (antivirus/proxy interception), set `UV_SYSTEM_CERTS=1`.

## Implementation status

Keep this section current (see `AGENTS.md`).

- [x] Monorepo scaffold: FastAPI agent with `/health`, three default Next.js store apps
- [x] MongoDB Atlas connection: shared client in the agent (PyMongo async) and each store (server-only), DB ping on health endpoints
- [ ] Storefront API (`store.json`, catalog, items, x402 checkout) in each store
- [ ] Scam storefront variants (lookalike domain/wallet, too cheap, prompt injection, fake reviews, unverified seller)
- [ ] Apify listing ingestion
- [ ] Scout (Claude) agent loop
- [ ] Gate (option A rules or option B classifier, undecided)
- [ ] Wallet signer + x402 payment against Base Sepolia
- [ ] Bitdeer fake-listing generation and labeled dataset
- [ ] Scoring harness with held-out set and catch-rate reporting
- [ ] Factory spec + Fix Droid loop
- [ ] Demo UI (rules input, payment view)
