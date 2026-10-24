import re
from difflib import SequenceMatcher

from features._text import listing_text
from gatepy.contracts import Snapshot
from gatepy.context import Ctx
from gatepy.registry import feature

URGENCY = [
    re.compile(p, re.I)
    for p in [
        r"\bonly \d+ (left|remaining)\b",
        r"\blast (one|copy|chance)\b",
        r"\b(price|offer|deal|discount) (expires|ends)\b",
        r"\bwithin \d+ (seconds|minutes|mins|hours)\b",
        r"\b(hurry|act now|today only|don't miss|dont miss|before it's gone|selling fast)\b",
        r"\b(immediately|right now|asap)\b",
    ]
]


def _norm(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", x.lower())


@feature("urgency_hits")
def urgency_hits(s: Snapshot, ctx: Ctx) -> float:
    text = listing_text(s)
    return float(sum(len(p.findall(text)) for p in URGENCY))


@feature("store_name_similarity_to_known")
def store_name_similarity_to_known(s: Snapshot, ctx: Ctx) -> float:
    """How close the store name is to a known store's name when it is NOT that store (0 for the real seller)."""
    return max(
        (SequenceMatcher(None, _norm(s.store.name), _norm(k["name"])).ratio()
         for k in ctx.known_sellers if k["sellerId"] != s.store.sellerId),
        default=0.0,
    )


@feature("domain_similarity_to_known")
def domain_similarity_to_known(s: Snapshot, ctx: Ctx) -> float:
    return max(
        (SequenceMatcher(None, _norm(s.store.domain), _norm(k["domain"])).ratio()
         for k in ctx.known_sellers if k["domain"].lower() != s.store.domain.lower()),
        default=0.0,
    )
