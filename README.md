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
| GET | `/api/catalog?q=fleece` | The 40 listings closest to the query, best first (Atlas Vector Search), so an agent crawls only what the shopper asked for |
| GET | `/api/items/{id}` | One listing with description, rating, reviews |
| POST | `/api/checkout/{id}` | Buy one item, paid via x402 |

Each storefront also has a human-facing search page whose query lives in the URL, so a search can be shared or revisited: mzn and its lookalike use `/s?k=`, by uses `/sch?_nkw=`, dpp uses `/search?q=`. Search is semantic: an Atlas Vector Search index with automated embedding (`listings_title_vector`, Voyage `voyage-4`) embeds every listing title and the query, so "warm jacket" also finds fleeces and parkas. Each store gets the 40 closest titles from its own marketplace, and results for a query are cached for hours. Create the index once per cluster with `node scripts/create-vector-index.mjs` (billed per embedded token; the cluster needs storage autoscaling if it is M10 or larger).

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
  - `q` is passed to each store's `/api/catalog?q=`, so the store ranks its own listings by meaning with Atlas Vector Search and the Actor crawls only those (at most 40 per store); empty lists everything.
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
| `MONGODB_URI` | agent API | MongoDB Atlas, for saved chats (`app/chats.py`). Unset: chats are not saved |
| `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`, `CDP_WALLET_SECRET` | agent API | Coinbase Developer Platform keys for the faucet behind Add Funds (`app/wallet.py`). Unset: only Add Funds fails |

Locally the agent API reads `apps/agent/api/.env` and the web app `apps/agent/web/.env.local`; both have a
`.env.example`. The API depends on `contracts/` (`calhacks-contracts`, a uv path dependency like in `gate/` and
`redteam/`), so Railway builds it from the repo root: root directory `/`, config file `apps/agent/api/railway.json`,
which builds `apps/agent/api/Dockerfile` and redeploys on changes under `apps/agent/api/` or `contracts/`.

## Saved chats

Finished chats are saved in MongoDB (`app/chats.py`): database `agent`, collection `chats`, one document per chat
(`_id`, `owner`, `title`, `prompt`, `status`, `run`, `updatedAt`), indexed on `owner` and `updatedAt`.

- There are no accounts yet, so each browser makes a random owner id (`hunter-owner` in localStorage,
  `apps/agent/web/lib/chats.ts`) and the API only lists, saves and deletes that owner's chats.
- `GET /chats?owner=` lists them, newest first (up to 100). `PUT /chats/{id}` saves a chat when its run finishes
  (`run` is the run as the UI last showed it, so it reopens exactly as it ended); a chat id that belongs to another
  owner is refused with 403. `DELETE /chats/{id}?owner=` deletes one (404 when it isn't theirs).
- Only finished chats are saved, so reloading the page never starts a purchase again.
- In the sidebar, a delete button appears on a chat when you hover it (always shown on touch screens). Deleting the
  open chat goes back to New Chat, and a failed delete puts the chat back.
- Self-check: `uv run python -m app.chats` (from `apps/agent/api`, uses a throwaway database).

## Wallet (Settings and Transactions)

The agent web app reads Hunter's wallet (`AGENT_WALLET` in `apps/agent/web/lib/wallet.ts`) live from Base Sepolia
through the agent API (`app/wallet.py`):

- `GET /wallet/{address}`: the USDC balance, read on chain with `eth_call` on `https://sepolia.base.org`, and every
  USDC transfer in or out (`hash`, `at`, `direction` sent|received, `amount`, `counterparty`, `explorer`), newest
  first, from the Blockscout API (`https://base-sepolia.blockscout.com`, no key needed, up to 250 transfers).
- `POST /wallet/{address}/fund`: test USDC from the CDP faucet (`request_faucet`, Base Sepolia). Measured: 1 USDC a
  request, landing within a few seconds. The faucet rate-limits each address; its refusal comes back as the `detail`.
- **Settings** shows the balance and an Add Funds button, then reads the balance again until the funds land.
- **Transactions** lists the real payments (item photo and name, counterparty, time, amount, Basescan link), with
  totals spent and left. Only payments since `SINCE` (`components/Transactions.tsx`, 2026-10-24 22:30 UTC) are
  listed: earlier test payments are cleared from the page and stay on chain. A payment's photo and name come from the
  saved chat whose receipt has the same transaction hash; payments without one show "Sent" and a no-image icon.
- Self-check: `uv run python -m app.wallet` (from `apps/agent/api`).

## Hunter chat run (Scout + live search)

A new chat in the agent web app is one live run: the browser opens `GET /chat?prompt=` on the agent API as an
`EventSource`, and the stages fill in as events arrive. The Scout is the LLM (Bitdeer, `zai-org/GLM-5.3-Flash`,
OpenAI-compatible at `https://api-inference.bitdeer.ai/v1`); it never touches money.

1. **Understand** (`app/scout.py`): the model reads the request and returns JSON with `item`, `query` (1-3 title
   words), `max_price`, `gender` (men|women|null), `size` and 2-4 `thoughts`, all validated in code. Sent as
   `thought` and `instruction` events.
   - **Clarifying questions:** when a detail that changes which listings fit is missing, the model returns a
     `question` with 2-5 options instead, and the run waits for the answer before searching: for clothing, men's or
     women's first, then the size. Never price, never something already said, one at a time, at most 2. Items that
     aren't worn get none. The answer goes back to the model, which can settle both at once ("for my girlfriend, she
     wears a small").
   - **No repeated questions:** the model is told the item the user named is final, and code drops any question,
     here or when narrowing, with an option the user already said in the request or an earlier answer
     (`scout.settled`): "Jacket or sweatshirt?" after "find me a sweatshirt", or "Men's or women's?" after "a men's
     hoodie". Words under 3 letters don't count, so a size never settles a question by accident.
   - **Why these two:** search words match anywhere in a title, so gender can't go in the query ("men" matches
     "women"). Code filters instead (`scout.fits`): it drops titles only for the other gender (whole words, so
     "Men Women" unisex titles stay) and titles that state only other sizes (`scout.sizes` reads "Size L",
     "sz S M L XL", "Mens Medium", "(Medium)", "2X-Large", ranges as every size; titles with no size stay). Measured
     on the 617 hosted titles: the gender answer removes 23-50% of a search's results, and 182 titles state a size.
     With either filter on, the actor is asked for 50 listings per store instead of 25.
2. **Search and check:** the live search above with that query and limit, 25 listings per store, and a mock Gate
   `verdict` per listing. If a query finds nothing, it is retried with its first word dropped ("warm fleece jacket",
   then "fleece jacket", then "jacket"), with a `search` event per query. Page text stays on the server for the Scout.
   Listings over the limit or filtered out above never reach the feed.
3. **Narrow:** approved listings whose title doesn't name the item (the query's last word, `rank.qualified`) are
   dropped first, so a sweatshirt search never offers jackets. With 4 or more left, the model looks at up to 60 of
   the cheapest and may ask which direction to take when they split into 2-4 clearly different groups (brand, style,
   type). Each option names the listings it keeps, and code drops options that keep nothing or everything. The UI
   shows each option's count plus **No Preference**. Choosing an option keeps only its listings
   (`narrow {kept, total}`); No Preference or a typed answer keeps them all. Measured: "warm fleece jacket under $50"
   (men's, M) split 63 safe listings into classic brand fleece 37, sherpa 6, tactical 13.
4. **Pick favorites:** every remaining listing with a photo of its own, the same product listed twice kept once,
   goes to the browser as `qualified {items: [{id, image, ...}]}` (all of them if none has a photo). A photo that
   fails to load, or loads narrower than 40px, drops out of the grid, so it never shows an empty tile. The UI shows them as a grid of photos only under
   "Qualified Items", 4 a row and 2 rows a page, with a pager under it. Hovering a photo lifts it slightly (2.5%)
   while the others ease back and fade a little. Only transform and opacity animate, so the layout never moves and
   the motion runs on the GPU; edge photos grow inward so the grid never clips them. The hovered photo is kept in
   state, so crossing the gap between photos never resets it, and Amazon and eBay photos load at 600px instead of
   1500px. The user
   picks up to 5 (each shows the order it was picked in) and clicks Compare, which sends
   `POST /chat/{id}/select {"ids": [...]}`; the stream echoes `selected {ids}`.
5. **Weigh** (`rank.weigh`, in code): each favorite gets four 0-1 factors from its page, and a score out of 100:
   seller trust 30% (the store's base: mzn 0.85, by 0.7, dpp 0.65, others 0.5; 1.0 when the store sells it itself,
   e.g. seller "Amazon.com"; by seller feedback moves it toward its percentage as ratings grow), price 30% (the
   cheapest favorite's price over this one's), reviews 25% (stars averaged with 4.0 as if from 20 more reviews) and
   condition 15%. Sent best first as `pick {picks}` with the photo, score, factors, condition, stars, reviews,
   feedback and a one-line note. The UI shows each favorite's photo, title, store, rating and price, and its score as a short bar (green on the
   best one, Hunter's recommendation).
6. **Confirm:** nothing is bought automatically. The best favorite starts out chosen, and until the user confirms
   or cancels they can click another weighed favorite to choose it instead, like a radio button. The UI shows the
   chosen favorite's photo, title, price, store, seller,
   condition, reviews, score, payment method and listing link. Confirm must be clicked twice: the first
   click turns it green ("Pay 12.98 USDC") for 5 seconds, the second sends
   `POST /chat/{id}/confirm {"confirm": true, "pick": 0}`, where `pick` is the chosen favorite's place in the
   weighed list (0, the best, by default). Cancel sends `false` and the run ends `stopped` with nothing paid. The
   stream echoes `confirmed {ok, pick}`, and the API buys that favorite.
7. **Pay** (`app/pay.py`): the confirmed favorite is bought over x402 in the six steps the UI lists, each sent as a
   `checkout {step, state, detail}` event: start checkout (POST with a ship-to, the store answers 402), read the price
   and wallet from `PAYMENT-REQUIRED`, double-check in code (network and asset as in
   `contracts/allowlist.json`, amount equals the listed price, `payTo` equals the store.json wallet, within the
   limit), sign an EIP-3009 `TransferWithAuthorization` for exactly
   that amount with `BUYER_PRIVATE_KEY`, POST again with `PAYMENT-SIGNATURE`, and read the order and the transaction
   hash (`PAYMENT-RESPONSE`). A `receipt` event (with the item's `image`) follows a real payment, and the receipt
   shows that photo. The facilitator pays gas, so the wallet needs
   USDC but no ETH. Without `BUYER_PRIVATE_KEY` the run stops at "Approve the Exact Amount" (`state: blocked`) and
   nothing is signed. A failed check stops before signing.
   - Verified without paying: all four stores answer a correct v2 402, and a payload signed by `app/pay.py` with an
     unfunded key was rejected by the x402.org facilitator's `/verify` only for insufficient USDC balance.
8. **End:** `end` with `status: bought`, `ready` (everything checked, no wallet key) or `stopped`.

- **Answering:** a run opens with `run {id}`. A question is `question {stage: understand|pick, text, options,
  counts?, images?}`; the browser sends the answer to `POST /chat/{id}/answer` with `{"text": "..."}`, and the stream echoes it
  as `answer {stage, question, text}` before going on. Answers, favorites and the go-ahead share one inbox per run,
  and a step drops replies meant for an earlier one (a double click). While it waits the stream sends a `ping`
  every 15s so proxies keep it open, and after 15 minutes without a reply it ends with an `error`. Waiting runs live
  in the API process's memory, so the API must run as a single instance. The chat badge reads "Needs Your Answer"
  while Hunter waits on a question, the grid or the confirmation.
- **Question card:** like Claude's question picker, a column of numbered options in Title Case with "Something
  Else..." as the last row for typing your own answer. A number key picks that option. Narrowing options also show
  how many listings each keeps and a photo of one of them: the first photo on that listing's page that no other safe
  listing's page shows (item pages also show related items and banners). Rows without a photo show a no-image icon.
- **Reasoning:** GLM-5.3-Flash streams its thinking as `reasoning_content`, which is long working notes ("Max
  price: null"). `app/llm.py` splits it into sentences as they complete and forwards only short plain ones as
  `reasoning {stage: understand|pick, text}` events, speaking to the user ("The user wants" becomes "You want").
  The UI shows just the latest sentence in the active stage, each one replacing the last. Asking for brief thinking
  or for no thinking did not shorten it (measured 650-2000 characters either way). Reasoning counts against
  `max_tokens`, so calls allow 6000 (at 600 the answer came back empty).
- **UI** (`apps/agent/web`): the same stages, summaries and receipt as the scripted demo it replaced
  ("192 Safe · 59 Scams Blocked", "mzn · 8.50 USDC", "Paid 8.50 USDC"), filled from the stream. Found listings
  join the feed one every 55ms and are checked one every 70ms (checking starts once every found listing is on screen),
  and each checkout step appears once its event arrives, with its detail shown only when the step stopped the
  payment. The request shows as one card with the item and a chip per detail (Men's, Size M, Under $40), and each
  answer as the question with the reply as a chip. Resale titles show without bullets and hashtags. Blocked rows show "Fake Store Website", "Hidden
  Instructions", "Too Cheap to Be Real" and similar. Listings over the user's limit are left out of the stream, as a
  price filter; the Gate and the checkout double-check still enforce the limit. The receipt shows the item's photo,
  the amount with a Paid tag, the title, store and time, then the order id and a Basescan link. The store gives no
  delivery date, so there is no "Arrives" row.
- A run lives in its chat view: leaving a chat mid-run ends the stream and coming back starts it over. Finished runs
  are kept with the chat and shown without streaming again.
- **Back:** a small "‹ Back" sits above whatever Hunter is waiting on, whenever there is a step to return to, and
  sends `POST /chat/{id}/back`. The API treats it as a reply: from the go-ahead it shows the grid again (with the
  favorites picked before still picked), from the grid the last narrowing question, from a narrowing question the one
  before it, and from the first step after the search the last question before it, after which the search runs
  again. A question before the search goes back to the one before it. The stream sends `back {to: understand|pick,
  keep}` so the browser keeps the first `keep` answers and resets everything after them.
- **Motion:** each stage's content animates its height as it changes (a question answered, the grid giving way to
  the weighing), the confirm card stays in place while only its content crossfades when the chosen favorite changes,
  and Confirm keeps one width when it turns into "Pay 12.98 USDC". Reduced motion turns all of it off.
- **Automatic** (sidebar, above Settings): a switch for buying without confirming, off and disabled for now.
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
- [x] Storefront search pages with the query in the URL (`/s?k=`, `/sch?_nkw=`, `/search?q=`) and `/api/catalog?q=`, ranked by Atlas Vector Search with automated embedding; the store-crawler Actor crawls only the query's matches
- [x] Scam storefront (mzn Official Outlet: lookalike brand, too cheap, prompt injection, fake reviews)
- [ ] Apify listing ingestion
- [x] Live store search: store-crawler Apify Standby Actor streaming listings and item pages, relayed as SSE by the agent API (`GET /search`)
- [x] Mock Gate verdicts in the search stream (`GateDecision` shape, `model_version: "mock"`), standing in for the real Gate
- [x] Saved chats in MongoDB (`agent.chats`) per browser, with delete in the sidebar
- [x] Wallet in the agent web app: live USDC balance and Add Funds (CDP faucet) in Settings, real Base Sepolia transfers in Transactions
- [x] Agent web chat runs live from `GET /chat` in the demo's design (editable prompt, live feed and checks, picks, collapsed reasoning, checkout steps, receipt)
- [x] x402 checkout in the agent API (`app/pay.py`): real 402, double-check, EIP-3009 signing, settlement; `BUYER_PRIVATE_KEY` is the demo wallet (`0x7D06…Cea8`, also in `apps/agent/web/lib/wallet.ts`)
- [x] Demo refunds (`app/refund.py`): after each purchase the store wallet sends the payment back through the x402.org facilitator (no gas needed), using `STORE_WALLET_PRIVATE_KEY`; the Transactions page lists only payments
- [x] Scout on Bitdeer GLM-5.3-Flash: reads the request, asks narrowing questions over Gate-approved listings, streams its reasoning (`GET /chat`)
- [x] Clarifying questions: men's/women's and size before searching (filtered in code), a narrowing question with per-option counts before picking (`POST /chat/{id}/answer`), and questions the user already answered dropped in code
- [x] Qualified grid: the user picks up to 5 favorites from photos (`POST /chat/{id}/select`), weighed in code by seller trust, price, reviews and condition
- [x] Double confirm before paying (`POST /chat/{id}/confirm`), receipt and Transactions with the item's photo, Transactions cleared before a cutoff
- [ ] Automatic buying (the sidebar switch is off and disabled)
- [x] Gate Layer 1: fixed TypeScript rules over the issue #1 `GateInput`
- [x] Gate Layer 2: LightGBM risk model trained and evaluated on MongoDB data, `POST /gate/risk`
- [ ] Wallet signer + x402 payment against Base Sepolia
- [x] Bitdeer attack generation from real MongoDB listings (`mutate_real` / `generate`), labels and attack diffs set by code
- [ ] Labeled dataset generated from real listings (blocked on real listings in MongoDB)
- [x] Scoring harness: issue #1 RoundMetrics (Wilson intervals, `fpr_real`, `adaptive_recall`), encrypted holdout scored to totals only, rounds table from MongoDB
- [x] Factory coordinator loop: per-round Droid SDK session, MCP tools, guard hook, strategist droid, code-enforced promotion, connected to the real Gate (train, evaluate, promote with holdout totals, restore on revert)
- [ ] Demo UI (rules input, payment view)
