"""Pydantic mirror of contracts/snapshot.schema.json, plus loaders for the shared contract files."""
import json
from functools import cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gatepy import CONTRACTS

Address = str


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Gen(_Strict):
    model: str
    temperature: float
    batch_id: str
    round: int = Field(ge=0)


class Mandate(_Strict):
    query: str
    max_price_usd: float = Field(gt=0)
    budget_remaining_usd: float = Field(ge=0)


class Store(_Strict):
    name: str
    sellerId: str
    payTo: Address = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    network: str
    currency: str
    sellingSince: int = Field(ge=1990, le=2100)
    rating: float = Field(ge=0, le=5)
    reviewCount: int = Field(ge=0)
    domain: str


class Item(_Strict):
    id: str
    title: str
    platform: str
    condition: Literal["Fair", "Good", "Like New", "New"]
    priceUsd: float = Field(gt=0)
    description: str
    inStock: bool


class Review(_Strict):
    author: str
    rating: int = Field(ge=1, le=5)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    verifiedPurchase: bool
    body: str


class PaymentRequired(_Strict):
    scheme: str
    network: str
    amount: str = Field(pattern=r"^[0-9]+$")
    asset: Address = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    payTo: Address = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    maxTimeoutSeconds: int = Field(ge=0)


class Snapshot(_Strict):
    id: str = Field(min_length=1)
    family: str
    label: Literal["scam", "legit", "unknown"]
    gen: Gen | None
    mandate: Mandate
    store: Store
    item: Item
    reviews: list[Review]
    payment_required: PaymentRequired
    checkout_item_id: str
    tactic_evidence: str | None


def load_json(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


@cache
def families() -> dict[str, dict]:
    return {f["id"]: f for f in load_json("families.json")["families"]}


@cache
def holdout_families() -> frozenset[str]:
    return frozenset(load_json("families.json")["holdout_families"])


def examples() -> list[Snapshot]:
    paths = sorted((CONTRACTS / "examples").glob("*.json"))
    return [Snapshot.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]
