"""Scrape Amazon listings for QUERY, then their reviews, into MongoDB in the listing format.

Usage (from anywhere): python setup/scrape_amazon.py [--count N] [--continue]
"""

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

from apify_common import QUERY, compact, condition, listing, run, scrape, scrape_retrying

PAGE_SIZE = 60  # Amazon search pages hold ~50-60 results, a smaller page just reads as finished
PRODUCTS_ACTOR = "junglee~amazon-crawler"  # Apify Store "Amazon Product Scraper"
PRODUCTS_INPUT = {
    "maxSearchPagesPerStartUrl": 1,  # one search page per run, paging is ours
    "scrapeProductDetails": True,
    "scrapeSellers": True,  # needed for seller rating
    "maxOffers": 0,
    "countryCode": "US",
}
REVIEWS_ACTOR = "junglee~amazon-reviews-scraper"  # Apify Store "Amazon Reviews Scraper"
REVIEWS_TIMEOUT = 120  # seconds; runs usually take 10-40s, but one has hung for 18 minutes
REVIEWS_INPUT = {
    "maxReviews": 10,  # per run, and we run once per product
    "sort": "helpful",
    "filterByRatings": ["allStars"],
    "includeGdprSensitive": False,  # so no reviewer names
    "scrapeProductDetails": False,
}


def key_values(entries) -> dict:
    return {e["key"]: e["value"] for e in entries or [] if e.get("key")}


def to_listing(p: dict) -> dict:
    seller = p.get("seller") or {}
    lifetime = seller.get("ratingLifetime") or {}
    stars = p.get("starsBreakdown")
    attributes = key_values(p.get("productOverview")) | key_values(p.get("attributes"))
    return listing(
        "amazon", external_id(p), p.get("url"),
        store={
            "name": seller.get("name") or p.get("brand") or None,
            "sellerId": seller.get("id"),
            "rating": seller.get("averageRating") or lifetime.get("starsOutOf5"),
            "reviewCount": seller.get("reviewsCount") or lifetime.get("ratingCount"),
        },
        item={
            "title": p.get("title"),
            "price": (p.get("price") or {}).get("value"),
            "condition": condition(p.get("condition") or "new"),  # null means the featured new offer
            "description": p.get("description") or "\n".join(p.get("features") or [])
            or ((p.get("aPlusContent") or {}).get("rawText") or "").removeprefix("Product description\n") or None,
            "listPrice": (p.get("listPrice") or {}).get("value"),
            "images": p.get("highResolutionImages") or compact([p.get("thumbnailImage")]),
            "brand": p.get("brand") or attributes.get("Brand Name") or attributes.get("Brand"),
            "category": (p.get("breadCrumbs") or "").split(" > ")[-1] or None,
            "attributes": attributes,
            "bullets": p.get("features") or None,
            "rating": p.get("stars"),
            "ratingCount": p.get("reviewsCount"),
            "ratingBreakdown": [round(stars.get(f"{n}star", 0) * 100) for n in range(5, 0, -1)] if stars else None,
            "stats": {"boughtLastMonth": p.get("monthlyPurchaseVolume")},
        },
        reviews=[],  # filled in by add_reviews once the listing is saved
    )


def to_review(r: dict) -> dict:
    return {
        "author": "Amazon Customer",
        "date": r.get("date"),
        "rating": r.get("ratingScore"),
        "title": r.get("reviewTitle"),
        "body": r.get("reviewDescription"),
        "helpful": int(r["reviewReaction"]) if str(r.get("reviewReaction")).isdigit() else 0,
        "verified": r.get("isVerified"),
    }


def external_id(p: dict) -> str:
    return p["asin"]


def fetch(token: str, page: int, cap: int) -> list[dict]:
    url = f"https://www.amazon.com/s?k={quote_plus(QUERY)}&page={page}"
    input = {**PRODUCTS_INPUT, "categoryOrProductUrls": [{"url": url}], "maxItemsPerStartUrl": cap}
    return [p for p in scrape_retrying(token, PRODUCTS_ACTOR, input, f"listing[p{page}]") if p.get("asin")]


def add_reviews(token: str, listings: list[dict], save) -> None:
    """Fetch each saved listing's reviews and save it again as soon as they arrive.

    Reviews are extras: a failed or timed-out run leaves that listing with fewer or no reviews
    instead of stopping the scrape.
    """
    # ponytail: a listing saved without reviews (failed run, or the script stopped) is never
    # revisited, since --continue skips it. Add a backfill pass if that starts to matter.
    def one(l: dict) -> None:
        asin = l["source"]["externalId"]
        try:
            reviews = scrape(token, REVIEWS_ACTOR,
                             {**REVIEWS_INPUT, "productUrls": [{"url": f"https://www.amazon.com/dp/{asin}"}]},
                             f"review[{asin}]", timeout=REVIEWS_TIMEOUT)
        except SystemExit as e:  # run FAILED or ABORTED
            print(f"reviews for {asin} skipped: {e}")
            return
        for r in reviews:
            if "error" in r:  # actor emits error items, e.g. product with no reviews
                print(f"reviews error for {asin}: {r['error']}")
        l["reviews"] = [to_review(r) for r in reviews if "error" not in r]
        save([l])

    # maxReviews caps the whole run, not each product, so run once per product.
    # 2 at a time: each run takes 4 GB and the free plan allows 16 GB across all runs.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one, listings))


if __name__ == "__main__":
    run("amazon", fetch, external_id, lambda token, items: [to_listing(p) for p in items], PAGE_SIZE, add_reviews)
