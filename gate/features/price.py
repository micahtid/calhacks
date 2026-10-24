from gatepy.contracts import Snapshot
from gatepy.context import Ctx
from gatepy.registry import feature


@feature("price_ratio", monotone=-1)
def price_ratio(s: Snapshot, ctx: Ctx) -> float:
    """Listed price / market median. 1.0 when the item has no median (see median_known)."""
    m = ctx.median(s.item.id)
    return s.item.priceUsd / m if m else 1.0


@feature("median_known")
def median_known(s: Snapshot, ctx: Ctx) -> float:
    return 1.0 if ctx.median(s.item.id) else 0.0


@feature("amount_vs_listed")
def amount_vs_listed(s: Snapshot, ctx: Ctx) -> float:
    """402 amount / listed price; 1.0 when they agree."""
    return (int(s.payment_required.amount) / 1e6) / s.item.priceUsd
