"""Schema 4: the Gate's input (`GateRequest`) and output (`GateDecision`).

The Gate never trusts the Scout's copy of a listing: it re-fetches store.json and the 402 itself and resolves the
request into a `GateInput` (mandate + the listing it fetched + references it looked up).
"""
from typing import Annotated, Literal

from pydantic import Field

from calhacks_contracts._base import Address, IsoDate, Strict
from calhacks_contracts.listing import Listing


class Mandate(Strict):
    """The user's rules, set once."""
    product_key: str = Field(description="What the user wants; stops injections that switch the product")
    max_price: float = Field(gt=0)
    spend_remaining: float = Field(ge=0)


class Proposal(Strict):
    """From the Scout."""
    listing_id: str
    scout_notes: str | None = Field(default=None, description="Logged only; never used in decisions")


class KnownSeller(Strict):
    seller_id: str
    pay_to: Address
    domain: str


class CrsResult(Strict):
    seller_id: str
    verified: bool
    verified_at: IsoDate | None = Field(default=None, description="When verification was granted")
    source: str = Field(default="crs", description="'crs' for the real API, 'stub' for the stand-in collection")


class References(Strict):
    """Looked up by the Gate. Never supplied by the store."""
    known_sellers: list[KnownSeller] = []
    crs_result: CrsResult | None = None
    market_median: float | None = Field(default=None, gt=0)
    pay_to_first_seen: IsoDate | None = None


class GateRequest(Strict):
    mandate: Mandate
    proposal: Proposal
    references: References


class GateInput(Strict):
    """A GateRequest after the Gate fetched the listing itself. This is what Layer 1 and Layer 2 evaluate."""
    mandate: Mandate
    listing: Listing
    references: References


class Case(Strict):
    """An offline evaluation case: which listing the Scout proposed under which mandate."""
    listing_id: str
    mandate: Mandate


RuleId = Literal[
    "L1_PAYTO_MISMATCH", "L1_SELLER_UNTRUSTED", "L1_UNKNOWN_SELLER_CAP", "L1_AMOUNT_MISMATCH", "L1_OVER_MAX",
    "L1_OVER_BUDGET", "L1_NETWORK", "L1_ASSET", "L1_ITEM_MISMATCH", "L1_PRODUCT_MISMATCH", "L1_TIMEOUT",
]


class Check(Strict):
    rule: RuleId
    passed: bool
    detail: str | None = None


class Reason(Strict):
    feature: str
    value: float
    contribution: float


class GateDecision(Strict):
    decision: Literal["buy", "skip"] = Field(description="The only thing the wallet obeys")
    decided_by: Literal["layer1", "layer2"] | None = Field(description="Which layer caused a skip; null on buy")
    failed_rule: RuleId | None = None
    risk_score: float | None = None
    threshold: float | None = None
    top_reasons: Annotated[list[Reason], Field(max_length=3)] = []
    model_version: str | None = None
    checks: list[Check] = []
