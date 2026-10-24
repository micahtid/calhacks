from gatepy.registry import REGISTRY


def f(name, snap, ctx):
    return REGISTRY[name].fn(snap, ctx)


def test_price_features(ex, ctx):
    cheap = ex["ex-too-cheap"]
    assert f("price_ratio", cheap, ctx) == cheap.item.priceUsd / ctx.median(cheap.item.id)
    assert f("amount_vs_listed", ex["ex-legit-plain"], ctx) == 1.0


def test_unknown_item_and_empty_reference_data_are_neutral(ex, ctx):
    """Listings may come from any source: an item with no median, or no known sellers at all, must not crash."""
    import dataclasses
    import math

    from gatepy.registry import select, self_test

    s = ex["ex-legit-plain"].model_copy(deep=True)
    s.item.id = s.checkout_item_id = "some-item-no-source-has-priced"
    assert f("price_ratio", s, ctx) == 1.0
    assert f("median_known", s, ctx) == 0.0
    empty = dataclasses.replace(ctx, medians={}, known_sellers=[], injection_patterns=[], zero_width_chars=[])
    assert self_test(select("all"), [s, *ex.values()], empty) == []
    assert all(math.isfinite(feat.fn(s, empty)) for feat in select("all"))
    assert f("payto_known", s, empty) == 0.0
    assert f("store_name_similarity_to_known", s, empty) == 0.0


def test_seller_features(ex, ctx):
    assert f("seller_age_years", ex["ex-legit-plain"], ctx) == 7.0
    assert f("seller_age_years", ex["ex-legit-new-honest-seller"], ctx) == 0.0


def test_review_features(ex, ctx):
    assert f("review_dup_max", ex["ex-fake-reviews"], ctx) == 1.0
    assert f("review_dup_max", ex["ex-legit-plain"], ctx) < 0.3
    assert f("unverified_frac", ex["ex-fake-reviews"], ctx) == 1.0
    assert f("review_recent_frac", ex["ex-fake-reviews"], ctx) == 1.0


def test_injection_features(ex, ctx):
    assert f("injection_hits", ex["ex-prompt-injection"], ctx) >= 1
    assert f("imperative_to_agent", ex["ex-prompt-injection"], ctx) >= 1
    for clean in ("ex-legit-plain", "ex-legit-new-honest-seller"):
        assert f("injection_hits", ex[clean], ctx) == 0
        assert f("imperative_to_agent", ex[clean], ctx) == 0


def test_payment_and_name_features(ex, ctx):
    assert f("payto_known", ex["ex-legit-plain"], ctx) == 1.0
    assert f("payto_min_hamming_to_known", ex["ex-legit-plain"], ctx) == 0.0
    assert f("payto_store_match", ex["ex-payment-mismatch"], ctx) == 0.0
    assert f("store_name_similarity_to_known", ex["ex-lookalike-payto"], ctx) == 1.0
    assert f("store_name_similarity_to_known", ex["ex-legit-plain"], ctx) == 0.0


def test_urgency(ex, ctx):
    s = ex["ex-legit-plain"].model_copy(deep=True)
    assert f("urgency_hits", s, ctx) == 0
    s.item.description += " Only 1 left, price expires within 10 minutes. Hurry!"
    assert f("urgency_hits", s, ctx) >= 3
