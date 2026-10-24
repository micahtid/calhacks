import re

from features._text import listing_text
from gatepy.contracts import Snapshot
from gatepy.context import Ctx
from gatepy.registry import feature

AGENT_WORDS = re.compile(r"\b(ai|a\.i\.|llm|assistant|agent|bot|model|gpt|claude)s?\b", re.I)
IMPERATIVE = re.compile(r"\b(must|should|do not|don't|never|always|immediately|ignore|override|proceed)\b", re.I)


@feature("injection_hits")
def injection_hits(s: Snapshot, ctx: Ctx) -> float:
    text = listing_text(s)
    return float(sum(len(p.findall(text)) for p in ctx.injection_patterns))


@feature("zero_width_chars")
def zero_width_chars(s: Snapshot, ctx: Ctx) -> float:
    text = listing_text(s)
    return float(sum(text.count(c) for c in ctx.zero_width_chars))


@feature("imperative_to_agent")
def imperative_to_agent(s: Snapshot, ctx: Ctx) -> float:
    """Sentences that both mention an AI/agent and give an order."""
    sentences = re.split(r"(?<=[.!?])\s+|\n", listing_text(s))
    return float(sum(bool(AGENT_WORDS.search(x) and IMPERATIVE.search(x)) for x in sentences))
