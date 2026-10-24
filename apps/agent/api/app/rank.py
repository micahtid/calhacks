"""The pick: ranks the Gate-approved listings in code, so it is instant, repeatable and never touches the model.

Only listings whose title names the item the user asked for are ranked, so Hunter never buys something else. Each
gets a score from what its page shows: its reviews, how close its price is to the user's target, and its condition.
Each pick's note says why in one short sentence.

Self-check: python -m app.rank (from apps/agent/api)
"""

import re
import statistics

from app.llm import plain

PICKS = 3
EXCERPT = 400  # Page text right after the title, where stores show reviews, condition and price.
# How much each part counts toward a listing's score. They add up to 1.
WEIGHTS = {"reviews": 0.4, "price": 0.35, "condition": 0.25}
# Stars are averaged with PRIOR_STARS as if PRIOR_COUNT more reviews gave them, so 5 stars from 2 reviews doesn't
# beat 4.7 stars from 2,000. A listing with no reviews scores the prior.
PRIOR_STARS, PRIOR_COUNT = 4.0, 20
PREFERENCE = 0.1  # Extra score when the title has a word from one of the user's answers.

# "4.6 ( 1,385 )" is stars and a review count. "( 12,861 ) 99.9% positive" is seller feedback.
STARS = re.compile(r"\b([0-5](?:\.\d)?)\s*\(\s*([\d,]+)\s*\)")
POSITIVE = re.compile(r"\(\s*([\d,]+)\s*\)\s*([\d.]+)%\s*positive", re.IGNORECASE)
# How stores state condition: "Condition: New with tags", a "· Like New ·" detail, or "brand new" in the text.
CONDITION = re.compile(r"(?:condition:\s*|[·•|]\s*)(like new|new with tags|new without tags|brand new|new|"
                       r"excellent|very good|good|fair|used|pre-owned)\b|\b(brand new|new with tags|like new)\b",
                       re.IGNORECASE)
CONDITIONS = {"new": 1.0, "brand new": 1.0, "new with tags": 1.0, "new without tags": 0.95, "like new": 0.9,
              "excellent": 0.85, "very good": 0.75, "good": 0.65, "used": 0.6, "pre-owned": 0.6, "fair": 0.45}
# Resale listings state their condition. Retail listings usually don't, since they are new, so a listing that states
# none scores just under like new.
UNSTATED = 0.8


def stem(word: str) -> str:
    """"jackets" -> "jacket", "dresses" -> "dress", "dress" -> "dress", so singular and plural match."""
    word = word.lower()
    if re.search(r"(ss|ch|sh|x)es$", word):
        return word[:-2]
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word


def words(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z0-9]+", text.lower())}


def is_item(query: str, title: str) -> bool:
    """True when the title names the product: the last word of the search, e.g. "jacket" for "fleece jacket"."""
    product = re.findall(r"[a-z0-9]+", query.lower())
    return bool(product) and stem(product[-1]) in words(title)


def excerpt(page: dict | None) -> str:
    """The page text right after the title, where reviews and condition are."""
    text, h1 = (page or {}).get("text") or "", (page or {}).get("h1") or ""
    start = text.find(h1) + len(h1) if h1 and h1 in text else 0
    return text[start:start + EXCERPT]


def facts(page: dict | None) -> dict:
    """Stars and review count (or seller feedback as stars), and condition, as the page states them."""
    text, out = excerpt(page), {"stars": None, "reviews": 0, "feedback": None, "condition": None}
    if m := POSITIVE.search(text):
        out["feedback"], out["reviews"] = float(m.group(2)), int(m.group(1).replace(",", ""))
        out["stars"] = out["feedback"] / 20
    elif (m := STARS.search(text)) and int(m.group(2).replace(",", "")) > 0:
        out["stars"], out["reviews"] = float(m.group(1)), int(m.group(2).replace(",", ""))
    if m := CONDITION.search(text):
        out["condition"] = (m.group(1) or m.group(2)).lower()
    return out


def score(price: float, target: float, f: dict, liked: set[str], title: str) -> float:
    stars = ((f["stars"] or 0) * f["reviews"] + PRIOR_STARS * PRIOR_COUNT) / (f["reviews"] + PRIOR_COUNT)
    closeness = max(0.0, 1 - abs(price - target) / target) if target > 0 else 1.0
    condition = CONDITIONS.get(f["condition"], UNSTATED)
    bonus = PREFERENCE if liked & words(title) else 0.0
    return WEIGHTS["reviews"] * stars / 5 + WEIGHTS["price"] * closeness + WEIGHTS["condition"] * condition + bonus


def note(price: float, limit: float | None, f: dict) -> str:
    """"Like new, 4.6 stars from 260 reviews, $27.99 of your $50 limit." """
    parts = [f["condition"].capitalize()] if f["condition"] else []
    if f["feedback"] is not None:
        parts.append(f"{f['feedback']:g}% positive seller feedback")
    elif f["stars"] is not None:
        parts.append(f"{f['stars']:g} stars from {f['reviews']:,} reviews")
    else:
        parts.append("no reviews yet")
    parts.append(f"${price:.2f} of your ${limit:g} limit" if limit else f"${price:.2f}")
    return plain(", ".join(parts))


def pick(request: dict, approved: list[tuple[dict, dict | None]], answers: list[str]) -> list[dict]:
    """The best PICKS of `approved` as [{"listing", "note"}], best first. Empty when none is the item asked for.
    The target price is the user's limit, or the middle price of the matching listings when there is none."""
    matching = [(l, p) for l, p in approved if is_item(request["query"], l.get("title") or "")]
    if not matching:
        return []
    limit = request.get("max_price")
    target = limit or statistics.median(l["price"] for l, _ in matching)
    liked = set().union(*(words(a) for a in answers)) - words(request["query"]) if answers else set()
    liked = {w for w in liked if len(w) > 2}
    ranked, seen = [], set()
    for listing, page in matching:
        f = facts(page)
        ranked.append((score(listing["price"], target, f, liked, listing.get("title") or ""), -listing["price"],
                       listing, f))
    ranked.sort(key=lambda r: r[:2], reverse=True)
    picks = []
    for _, _, listing, f in ranked:
        same = ((listing.get("title") or "").lower(), listing["price"])
        if same not in seen:  # The same product listed twice is one choice.
            seen.add(same)
            picks.append({"listing": listing, "note": note(listing["price"], limit, f)})
    return picks[:PICKS]


if __name__ == "__main__":
    assert [stem(w) for w in ["jackets", "dresses", "dress", "boots", "hoodies", "glasses"]] == \
        ["jacket", "dress", "dress", "boot", "hoodie", "glass"]
    assert is_item("fleece jacket", "Columbia Men's Fleece Jackets") and not is_item("fleece jacket", "Fleece Joggers")
    assert is_item("wireless headphones", "Sony Wireless Headphone") and not is_item("headphones", "Gray joggers")
    mzn = {"h1": "Coat", "text": "Nav Coat Visit the Store 4.6 ( 1,385 ) $ 42 99 New $ 42 99"}
    by = {"h1": "Coat", "text": "Coat SP SPEEDGEAR ( 12,861 ) 99.9% positive US $55.00 Condition: New with tags"}
    dpp = {"h1": "Coat", "text": "Coat $11.00 incl. fee REI Co-op · Size M · Like New · black"}
    empty = {"h1": "Coat", "text": "Coat Brand : X 0.0 ( 0 ) $ 10 99"}
    assert facts(mzn) == {"stars": 4.6, "reviews": 1385, "feedback": None, "condition": None}
    assert facts(by)["feedback"] == 99.9 and facts(by)["condition"] == "new with tags"
    assert facts(dpp)["condition"] == "like new" and facts(dpp)["stars"] is None
    assert facts(empty)["stars"] is None
    assert note(27.99, 50, facts(dpp)) == "Like new, no reviews yet, $27.99 of your $50 limit."
    assert note(42.99, None, facts(mzn)) == "4.6 stars from 1,385 reviews, $42.99."
    request = {"query": "fleece jacket", "max_price": 50}
    good = {"title": "Fleece Jacket A", "price": 45.0}
    cheap = {"title": "Fleece Jacket B", "price": 9.0}
    other = {"title": "Fleece Joggers", "price": 48.0}
    picks = pick(request, [(cheap, empty), (good, mzn), (other, mzn)], [])
    assert [p["listing"] for p in picks] == [good, cheap], picks
    assert pick({"query": "headphones", "max_price": 40}, [(other, mzn)], []) == []
    sherpa = {"title": "Sherpa Fleece Jacket", "price": 9.0}
    assert pick(request, [(cheap, empty), (sherpa, empty)], ["Sherpa lined"])[0]["listing"] == sherpa
    print("ok")
