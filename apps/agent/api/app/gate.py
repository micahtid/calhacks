"""Client for the Gate (gate/, its own service): POST {GATE_URL}/decide with a contracts GateRequest, answered with a
GateDecision. The request carries only the mandate and which listing to judge (its page URL); the Gate reads that
listing, its 402 and the known stores itself, runs Layer 1's rules and then the red-teamed model (gates/CURRENT).

Product matching stays here, before anything can be bought (rank.qualified), so the mandate names the listing's own
product key. Any error, timeout, non-200 answer or missing GATE_URL is a skip, like the Gate's own fail-closed 503.
"""

import os
from urllib.parse import urlparse

import httpx
from calhacks_contracts import GateDecision

TIMEOUT = 30  # Seconds per decision: the Gate reads the store's page and asks its checkout for the 402.


def request(listing: dict, max_price: float | None) -> dict:
    """The GateRequest for one listing. Without a limit from the user there is no over-limit check."""
    limit = max_price if max_price is not None else listing["price"]
    return {"mandate": {"product_key": f"{urlparse(listing['store']).hostname}:{listing['key']}",
                        "max_price": limit, "spend_remaining": limit},
            "proposal": {"listing_id": listing["url"]},
            "references": {"known_sellers": []}}  # The Gate looks references up itself.


def unavailable(error: str) -> dict:
    """No decision means nothing was judged: skip. `error` rides alongside the GateDecision fields, like the
    verdict's store and key."""
    return {**GateDecision(decision="skip", decided_by=None).model_dump(), "error": error}


async def judge(client: httpx.AsyncClient, listing: dict, max_price: float | None) -> dict:
    """The Gate's decision for one listing, or a skip when it can't be had."""
    url = os.environ.get("GATE_URL")
    if not url:
        return unavailable("GATE_URL is not set")
    if not listing.get("url"):
        return unavailable("the listing has no page to judge")
    try:
        res = await client.post(f"{url.rstrip('/')}/decide", json=request(listing, max_price), timeout=TIMEOUT)
        body = res.json()
        if res.status_code != 200:
            return unavailable(body.get("error") or f"the Gate answered {res.status_code}")
        return GateDecision.model_validate(body).model_dump()
    except (httpx.HTTPError, ValueError) as e:  # ValueError: bad JSON, or a reply that isn't a GateDecision.
        return unavailable(f"the Gate is unreachable ({type(e).__name__})")
