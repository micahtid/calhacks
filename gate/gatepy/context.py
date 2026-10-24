"""Ctx: the fixed reference data features may consult (medians, known sellers, injection patterns, as-of date)."""
import os
import re
from dataclasses import dataclass, field
from datetime import date

from gatepy.contracts import load_json

DEFAULT_AS_OF = "2026-10-24"


@dataclass(frozen=True)
class Ctx:
    medians: dict[str, float]
    known_sellers: list[dict]
    injection_patterns: list[re.Pattern] = field(repr=False)
    zero_width_chars: list[str]
    as_of: date

    def median(self, item_id: str) -> float | None:
        m = self.medians.get(item_id)
        return float(m) if m else None

    @property
    def known_wallets(self) -> list[str]:
        return [s["payTo"].lower() for s in self.known_sellers]


def load_ctx(as_of: str | None = None) -> Ctx:
    inj = load_json("injection_patterns.json")
    return Ctx(
        medians={k: v for k, v in load_json("market_medians.json")["medians"].items() if v is not None},
        known_sellers=load_json("known_sellers.json")["sellers"],
        injection_patterns=[re.compile(p, re.I) for p in inj["patterns"]],
        zero_width_chars=inj["zero_width_chars"],
        as_of=date.fromisoformat(as_of or os.environ.get("GATE_AS_OF", DEFAULT_AS_OF)),
    )
