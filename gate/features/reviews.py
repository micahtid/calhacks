from datetime import date
from itertools import combinations

from features._text import jaccard, tokens
from gatepy.contracts import Snapshot
from gatepy.context import Ctx
from gatepy.registry import feature


@feature("item_review_count")
def item_review_count(s: Snapshot, ctx: Ctx) -> float:
    return float(len(s.reviews))


@feature("review_dup_max")
def review_dup_max(s: Snapshot, ctx: Ctx) -> float:
    """Highest word overlap (Jaccard) between any two reviews; near 1 means copy-paste reviews."""
    toks = [tokens(r.body) for r in s.reviews]
    return max((jaccard(a, b) for a, b in combinations(toks, 2)), default=0.0)


@feature("unverified_frac")
def unverified_frac(s: Snapshot, ctx: Ctx) -> float:
    return sum(not r.verifiedPurchase for r in s.reviews) / len(s.reviews) if s.reviews else 0.0


@feature("review_date_span_days")
def review_date_span_days(s: Snapshot, ctx: Ctx) -> float:
    days = [date.fromisoformat(r.date) for r in s.reviews]
    return float((max(days) - min(days)).days) if len(days) > 1 else 0.0


@feature("review_recent_frac")
def review_recent_frac(s: Snapshot, ctx: Ctx) -> float:
    """Share of reviews posted in the 30 days before the as-of date."""
    if not s.reviews:
        return 0.0
    return sum((ctx.as_of - date.fromisoformat(r.date)).days <= 30 for r in s.reviews) / len(s.reviews)


@feature("review_len_mean")
def review_len_mean(s: Snapshot, ctx: Ctx) -> float:
    return sum(len(r.body.split()) for r in s.reviews) / len(s.reviews) if s.reviews else 0.0


@feature("review_rating_mean")
def review_rating_mean(s: Snapshot, ctx: Ctx) -> float:
    return sum(r.rating for r in s.reviews) / len(s.reviews) if s.reviews else 0.0
