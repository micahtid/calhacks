"""Shared text helpers for feature modules (registers no features)."""
import re

from gatepy.contracts import Snapshot

WORD = re.compile(r"[a-z0-9']+")


def listing_text(s: Snapshot) -> str:
    """Seller-controlled text the agent reads: title, description and review bodies."""
    return "\n".join([s.item.title, s.item.description, *(r.body for r in s.reviews)])


def tokens(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0
