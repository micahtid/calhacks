import json
import os
import statistics
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # local secrets; Railway sets real env vars instead

from app import gate, pay, scout  # noqa: E402
from app.search import search  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No read timeout: search and LLM streams stay open while the work runs.
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=None)) as client:
        app.state.client = client
        yield


app = FastAPI(title="Hunter", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str | None]:
    """`buyer` is the address BUYER_PRIVATE_KEY signs for (public, never the key), or null when it isn't set."""
    return {"status": "ok", "buyer": pay.buyer_address()}


def sse(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def stream(events: AsyncIterator[dict]) -> StreamingResponse:
    async def body():
        try:
            async for event in events:
                yield sse(event)
        except (httpx.HTTPError, RuntimeError) as e:  # actor or model down or misconfigured: tell the client, then end
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
            # ponytail: median of the prices seen so far in this search stands in for market medians
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
                held.append(event)  # store and error events before the first listing
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


def brief(listing: dict) -> dict:
    return {k: listing.get(k) for k in ("store", "storeName", "key", "title", "price", "seller", "url")}


@app.get("/chat")
async def chat(prompt: str = Query(min_length=1, max_length=1000),
               max: int = Query(25, ge=1, le=100, description="Max listings per store")):
    """One chat turn as server-sent events, in the order the UI shows them:

    reasoning {stage: understand|pick, text}  the model's thinking, streamed as it arrives
    thought {text}, instruction {item, query, max_price}  the request as the model read it
    search {query}, listing, store, verdict, error, done  the live search and the Gate (pages are not forwarded)
    pick {picks: [listing fields + note]}  best first, all Gate-approved; empty when nothing passed
    checkout {step: 0-5, state: done|failed|blocked, detail}  buying the best pick over x402 (app/pay.py)
    receipt {item, store, amount, network, from, to, order, paidAt, txHash, explorer}  only once paid
    end {status: bought|ready|stopped}  ready: checked and ready to pay, but no BUYER_PRIVATE_KEY is set
    Listings over the user's limit are left out of the stream.
    """
    client = app.state.client

    async def events():
        request = {}
        async for kind, value in scout.understand(client, prompt):
            if kind == "reasoning":
                yield {"type": "reasoning", "stage": "understand", "text": value}
            else:
                request = value
        for thought in request["thoughts"]:
            yield {"type": "thought", "text": thought}
        yield {"type": "instruction", **{k: request[k] for k in ("item", "query", "max_price")}}

        listings, pages, stores, approved, hidden = {}, {}, {}, [], set()
        limit = request["max_price"]
        async for event in found(request["query"], max, limit):
            at = event.get("store"), event.get("key")
            if event["type"] == "page":
                pages[at] = event["page"]  # kept for the Scout, not sent: the verdict is what the UI needs
                continue
            if event["type"] == "store":
                stores[event["store"]] = event
            if event["type"] == "listing":
                listings[at] = event
                # Over the user's limit is a filter, not a scam: the feed only shows what Hunter could buy.
                # The Gate's L1_OVER_MAX and the checkout double-check still enforce the limit.
                if limit is not None and event["price"] > limit:
                    hidden.add(at)
                    continue
            if event["type"] == "verdict":
                if at in hidden:
                    continue
                if event["decision"] == "buy":
                    approved.append((listings[at], pages.get(at)))
            yield event

        picks = []
        async for kind, value in scout.pick(client, prompt, request, approved):
            if kind == "reasoning":
                yield {"type": "reasoning", "stage": "pick", "text": value}
            else:
                picks = value
        yield {"type": "pick", "picks": [{**brief(p["listing"]), "note": p["note"]} for p in picks]}
        if not picks:
            yield {"type": "end", "status": "stopped"}
            return

        best = picks[0]["listing"]
        status = "stopped"
        async for event in pay.checkout(client, best, stores.get(best["store"]), limit):
            if event["type"] == "receipt":
                status = "bought"
            elif event["state"] == "blocked":
                status = "ready"  # everything checked out; only the wallet key is missing
            yield event
        yield {"type": "end", "status": status}

    return stream(events())
