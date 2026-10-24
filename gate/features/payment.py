from gatepy.contracts import Snapshot
from gatepy.context import Ctx
from gatepy.registry import feature


def _hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a.lower()[2:], b.lower()[2:]))


@feature("payto_known")
def payto_known(s: Snapshot, ctx: Ctx) -> float:
    return 1.0 if s.payment_required.payTo.lower() in ctx.known_wallets else 0.0


@feature("payto_min_hamming_to_known")
def payto_min_hamming_to_known(s: Snapshot, ctx: Ctx) -> float:
    """Hex characters that differ from the closest known wallet (0 = identical, 40 = nothing in common)."""
    return float(min((_hamming(s.payment_required.payTo, w) for w in ctx.known_wallets), default=40))


@feature("payto_store_match")
def payto_store_match(s: Snapshot, ctx: Ctx) -> float:
    return 1.0 if s.payment_required.payTo.lower() == s.store.payTo.lower() else 0.0
