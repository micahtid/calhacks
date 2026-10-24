import math

from gatepy.contracts import Snapshot
from gatepy.context import Ctx
from gatepy.registry import feature


@feature("seller_age_years", monotone=-1)
def seller_age_years(s: Snapshot, ctx: Ctx) -> float:
    return float(max(0, ctx.as_of.year - s.store.sellingSince))


@feature("store_review_count_log")
def store_review_count_log(s: Snapshot, ctx: Ctx) -> float:
    return math.log1p(s.store.reviewCount)


@feature("store_rating")
def store_rating(s: Snapshot, ctx: Ctx) -> float:
    return float(s.store.rating)


@feature("store_reviews_per_year")
def store_reviews_per_year(s: Snapshot, ctx: Ctx) -> float:
    return s.store.reviewCount / (seller_age_years(s, ctx) + 1.0)
