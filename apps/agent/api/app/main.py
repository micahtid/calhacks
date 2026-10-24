import json
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.search import search


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No read timeout: a search stream stays open while the actor works.
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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
async def search_stream(q: str = "", max: int = Query(0, ge=0, description="Max listings per store, 0 for all")):
    """Server-sent events, one per actor event, named by its type (listing, store, page, error, done)."""

    async def events():
        try:
            async for event in search(app.state.client, q, max):
                yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        except (httpx.HTTPError, RuntimeError) as e:  # actor down or misconfigured: tell the client, then end
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': repr(e)})}\n\n"

    # X-Accel-Buffering stops proxies from holding events back until the stream ends.
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
