import asyncio
import json
import os
import re
import secrets
import statistics
import time
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # Local secrets; Railway sets real env vars instead.

from app import chats, gate, pay, rank, refund, scout, wallet  # noqa: E402
from app.search import search  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No read timeout: search and LLM streams stay open while the work runs.
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=None)) as client:
        app.state.client = client
        if os.environ.get("MONGODB_URI"):
            await chats.setup()
        yield


app = FastAPI(title="Hunter", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/chats")
async def list_chats(owner: str = Query(pattern=chats.ID)) -> list[dict]:
    """The owner's saved chats, newest first."""
    return await chats.list_chats(owner)


@app.put("/chats/{chat_id}")
async def save_chat(chat_id: str, chat: chats.Chat) -> dict:
    """Saves a finished chat, or replaces it when the same owner saves it again."""
    if not re.fullmatch(chats.ID, chat_id):
        raise HTTPException(400, "not a chat id")
    if not await chats.save(chat_id, chat):
        raise HTTPException(403, "This chat belongs to someone else.")
    return {"ok": True}


@app.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, owner: str = Query(pattern=chats.ID)) -> None:
    if not await chats.delete(chat_id, owner):
        raise HTTPException(404, "No such chat.")


@app.get("/health")
def health() -> dict[str, str | None]:
    """`buyer` is the address BUYER_PRIVATE_KEY signs for (public, never the key), or null when it isn't set."""
    return {"status": "ok", "buyer": pay.buyer_address()}


def checked(address: str) -> str:
    if not wallet.ADDRESS.match(address):
        raise HTTPException(400, "not a wallet address")
    return address


@app.get("/wallet/{address}")
async def wallet_info(address: str) -> dict:
    """The wallet's USDC balance and every USDC transfer in or out of it on Base Sepolia, newest first."""
    client = app.state.client
    try:
        return {"address": checked(address), "balance": await wallet.balance(client, address),
                "transactions": await wallet.transfers(client, address)}
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Base Sepolia couldn't be read: {e!r}") from e


@app.post("/wallet/{address}/fund")
async def wallet_fund(address: str) -> dict:
    """Test USDC from the CDP faucet. The faucet's own refusal (e.g. its rate limit) comes back as the detail."""
    try:
        return await wallet.fund(checked(address))
    except HTTPException:
        raise
    except Exception as e:  # Missing CDP credentials, faucet limit, network errors.
        raise HTTPException(502, getattr(e, "error_message", None) or str(e) or repr(e)) from e


def sse(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def stream(events: AsyncIterator[dict]) -> StreamingResponse:
    async def body():
        try:
            async for event in events:
                yield sse(event)
        except (httpx.HTTPError, RuntimeError) as e:  # Actor or model down or misconfigured: tell the client, then end.
            yield sse({"type": "error", "error": repr(e)})

    # X-Accel-Buffering stops proxies from holding events back until the stream ends.
    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def judged(query: str, max_per_store: int, max_price: float | None) -> AsyncIterator[dict]:
    """The actor's search events, plus a `verdict` (GateDecision fields + store, key) right after each item's
    page or page error."""
    listings: dict[tuple[str, str], dict] = {}
    async for event in search(app.state.client, query, max_per_store):
        yield event
        if event["type"] == "listing":
            listings[event["store"], event["key"]] = event
        elif event["type"] in ("page", "error") and "key" in event:
            # ponytail: median of the prices seen so far in this search stands in for market medians.
            median = statistics.median(l["price"] for l in listings.values())
            listing = listings[event["store"], event["key"]]
            decision = (gate.decide(listing, event["page"], max_price, median) if event["type"] == "page"
                        else gate.unavailable(event["error"]))
            yield {"type": "verdict", "store": event["store"], "key": event["key"], **decision}


async def found(query: str, max_per_store: int, max_price: float | None) -> AsyncIterator[dict]:
    """judged(), retried with the first word dropped while a search finds no listings, since the model's query
    can be more specific than store titles ("warm fleece jacket" -> "fleece jacket" -> "jacket").
    A `search` event names each query tried."""
    words = query.split()
    while True:
        yield {"type": "search", "query": " ".join(words)}
        held, hit = [], False
        async for event in judged(" ".join(words), max_per_store, max_price):
            hit = hit or event["type"] == "listing"
            if hit:
                for e in held:
                    yield e
                held = []
                yield event
            else:
                held.append(event)  # Store and error events before the first listing.
        if hit or len(words) <= 1:
            for e in held:
                yield e
            return
        words = words[1:]


@app.get("/search")
async def search_stream(q: str = "", max: int = Query(0, ge=0, description="Max listings per store, 0 for all"),
                        max_price: float | None = Query(None, gt=0, description="The user's limit, checked by the Gate")):
    """Server-sent events, one per actor event, named by its type (listing, store, page, error, done),
    plus a `verdict` after each item's page or page error."""
    return stream(judged(q, max, max_price))


# A run waiting on the user keeps its stream open: a ping goes out while it waits so proxies don't close it, and it
# gives up after ANSWER_TIMEOUT. Answers arrive through POST /chat/{id}/answer.
# ponytail: runs live in this process's memory, so this needs a single API instance.
PING_S = 15
ANSWER_TIMEOUT = 15 * 60
NARROW_MIN = 4  # Fewer approved listings than this are not worth a question.
NO_PREFERENCE = "No Preference"  # Always offered when narrowing. It keeps every listing.
RUNS: dict[str, asyncio.Queue[str]] = {}


class NoAnswer(Exception):
    """The user never answered a question, so the run ends."""


class Answer(BaseModel):
    text: str = Field(min_length=1, max_length=200)


@app.post("/chat/{run_id}/answer")
async def answer(run_id: str, body: Answer) -> dict:
    """The user's answer to the question a running chat is waiting on."""
    if (queue := RUNS.get(run_id)) is None:
        raise HTTPException(404, "This chat is over or isn't waiting for an answer.")
    await queue.put(body.text.strip())
    return {"ok": True}


async def ask(run_id: str, stage: str, text: str, options: list[str], **per_option) -> AsyncIterator[dict]:
    """Sends a `question`, then waits for the answer. Ends with an `answer` event, or an `error` if none came.
    `per_option` lists ride along, one value per option (counts, images)."""
    queue = RUNS[run_id]
    while not queue.empty():  # A double click on the last question must not answer this one.
        queue.get_nowait()
    yield {"type": "question", "stage": stage, "text": text, "options": options, **per_option}
    deadline = time.monotonic() + ANSWER_TIMEOUT
    while time.monotonic() < deadline:
        try:
            reply = await asyncio.wait_for(queue.get(), PING_S)
        except TimeoutError:
            yield {"type": "ping"}
            continue
        yield {"type": "answer", "stage": stage, "question": text, "text": reply}
        return
    yield {"type": "error", "message": "No answer came, so Hunter stopped."}


async def relay(stage: str, steps: AsyncIterator[tuple[str, object]], result: dict) -> AsyncIterator[dict]:
    """Sends a Scout step's thinking as `reasoning` events and keeps its final value in result["value"]."""
    async for kind, value in steps:
        if kind == "reasoning":
            yield {"type": "reasoning", "stage": stage, "text": value}
        else:
            result["value"] = value


def previews(approved: list[tuple[dict, dict | None]], options: list[dict]) -> list[str | None]:
    """One photo per narrowing option: the first photo of the first listing it keeps that is that listing's own.
    Item pages also show related items and banners, so a photo that another safe listing's page shows too isn't
    the listing's own."""
    pages = {id(listing): page or {} for listing, page in approved}
    shown = Counter(image for page in pages.values() for image in dict.fromkeys(page.get("images") or []))

    def own(listing: dict) -> str | None:
        return next((i for i in pages.get(id(listing), {}).get("images") or [] if shown[i] == 1), None)

    return [next(filter(None, map(own, o["keep"])), None) for o in options]


def remaining(options: list[dict], approved: list[tuple[dict, dict | None]]) -> list[dict]:
    """The options that still split what an earlier answer kept: each keeps some listings, but not all of them."""
    alive = {id(listing) for listing, _ in approved}
    kept = [{**o, "keep": [l for l in o["keep"] if id(l) in alive]} for o in options]
    return [o for o in kept if 0 < len(o["keep"]) < len(alive)]


def brief(listing: dict) -> dict:
    return {k: listing.get(k) for k in ("store", "storeName", "key", "title", "price", "seller", "url")}


@app.get("/chat")
async def chat(prompt: str = Query(min_length=1, max_length=1000),
               max: int = Query(25, ge=1, le=100, description="Max listings per store")):
    """One chat turn as server-sent events, in the order the UI shows them:

    run {id}  first; answers to this run's questions go to POST /chat/{id}/answer
    reasoning {stage: understand|pick, text}  the model's thinking, streamed as it arrives
    question {stage: understand|pick, text, options, counts?, images?}, then answer {stage, question, text}
        Hunter asks before searching when a hard requirement is missing (who it is for, size, the model it must
        fit), and again before picking when the safe listings split into clearly different directions (style,
        color). Each stage asks at most two questions, back to back. Pick stage only: counts, the listings each
        option keeps, and images, a photo of one of them or null (see previews()). images has no entry for the
        last option, No Preference, since it has no photo of its own. ping events keep the stream open
        while it waits.
    title {text}  the chat's name, which is the item as the model named it. Sent again only if the name changes.
    thought {text}, instruction {item, query, max_price, gender, size}  the request as the model read it
    search {query}, listing, store, verdict, error, done  the live search and the Gate (pages are not forwarded)
    narrow {kept, total}  how many safe listings the answer to the second question kept
    pick {picks: [listing fields + note]}  best first, all Gate-approved and ranked in code (app/rank.py); empty
        when nothing that passed is the item asked for
    checkout {step: 0-5, state: done|failed|blocked, detail}  buying the best pick over x402 (app/pay.py)
    receipt {item, store, amount, network, from, to, order, paidAt, txHash, explorer}  only once paid
    end {status: bought|ready|stopped}  ready: checked and ready to pay, but no BUYER_PRIVATE_KEY is set
    Listings over the user's limit, made only for the other gender, or stating only other sizes are left out of the
    stream (scout.fits).
    """
    client = app.state.client
    run_id = secrets.token_urlsafe(8)
    RUNS[run_id] = asyncio.Queue()
    answers: list[dict] = []

    async def answered(stage: str, text: str, options: list[str], **per_option) -> AsyncIterator[dict]:
        """ask(), recording the answer in `answers`. Raises NoAnswer when none came."""
        async for event in ask(run_id, stage, text, options, **per_option):
            yield event
            if event["type"] == "answer":
                answers.append({"question": text, "answer": event["text"]})
                return
        raise NoAnswer

    async def events():
        try:
            async for event in run():
                yield event
        except NoAnswer:
            yield {"type": "end", "status": "stopped"}
        finally:
            RUNS.pop(run_id, None)

    async def run():
        yield {"type": "run", "id": run_id}
        title = None
        while True:
            request = {}
            async for event in relay("understand", scout.understand(client, prompt, answers), request):
                yield event
            if request["value"]["item"] != title:
                title = request["value"]["item"]
                yield {"type": "title", "text": title}
            if not (questions := request["value"]["questions"]):
                break
            replies = []
            for question in questions:  # Asked back to back, with no model call between them.
                async for event in answered("understand", question["text"], question["options"]):
                    yield event
                replies.append(answers[-1]["answer"])
            # Men's or women's and size answers are set in code. Only other answers need the model to read again.
            if filled := scout.fill(request["value"], questions, replies):
                request["value"] = filled
                break
        request = request["value"]
        for thought in request["thoughts"]:
            yield {"type": "thought", "text": thought}
        yield {"type": "instruction", **{k: request[k] for k in ("item", "query", "max_price", "gender", "size")}}

        listings, pages, stores, approved, hidden = {}, {}, {}, [], set()
        limit = request["max_price"]
        # The gender and size filters drop listings after the actor finds them, so it is asked for twice as many.
        wanted = max * 2 if request["gender"] or request["size"] else max
        async for event in found(request["query"], wanted, limit):
            at = event.get("store"), event.get("key")
            if event["type"] == "page":
                pages[at] = event["page"]  # Kept for the Scout, not sent: the verdict is what the UI needs.
                continue
            if event["type"] == "store":
                stores[event["store"]] = event
            if event["type"] == "listing":
                listings[at] = event
                # Over the user's limit, for the other gender or in other sizes is a filter, not a scam: the feed
                # only shows what Hunter could buy. The Gate's L1_OVER_MAX and the checkout double-check still
                # enforce the limit.
                if (limit is not None and event["price"] > limit) or not scout.fits(request, event.get("title") or ""):
                    hidden.add(at)
                    continue
            if event["type"] == "verdict":
                if at in hidden:
                    continue
                if event["decision"] == "buy":
                    approved.append((listings[at], pages.get(at)))
            yield event

        narrowing = {"value": []}
        if len(approved) >= NARROW_MIN:
            safe = [listing for listing, _ in approved]
            async for event in relay("pick", scout.narrow(client, prompt, answers, safe), narrowing):
                yield event
        total = len(approved)
        for question in narrowing["value"]:  # Asked back to back, each on what the answers before it kept.
            if len(options := remaining(question["options"], approved)) < 2:
                continue
            async for event in answered("pick", question["text"], [o["label"] for o in options] + [NO_PREFERENCE],
                                        counts=[len(o["keep"]) for o in options] + [len(approved)],
                                        images=previews(approved, options)):
                yield event
            # An option's label keeps that option's listings. Anything typed instead is a preference for the pick.
            reply = answers[-1]["answer"].lower()
            if chosen := next((o for o in options if o["label"].lower() == reply), None):
                keep = {id(l) for l in chosen["keep"]}
                approved = [(l, p) for l, p in approved if id(l) in keep]
        if len(approved) < total:
            yield {"type": "narrow", "kept": len(approved), "total": total}

        picks = rank.pick(request, approved, [a["answer"] for a in answers if a["answer"] != NO_PREFERENCE])
        yield {"type": "pick", "picks": [{**brief(p["listing"]), "note": p["note"]} for p in picks]}
        if not picks:
            yield {"type": "end", "status": "stopped"}
            return

        best = picks[0]["listing"]
        status, receipt = "stopped", None
        async for event in pay.checkout(client, best, stores.get(best["store"]), limit):
            if event["type"] == "receipt":
                status, receipt = "bought", event
            elif event["state"] == "blocked":
                status = "ready"  # Everything checked out; only the wallet key is missing.
            yield event
        if receipt and refund.store_key():
            refund.schedule(client, receipt["from"], receipt["amount"])
        yield {"type": "end", "status": status}

    return stream(events())
