import pytest

from redteam.config import families, contract
from redteam.mutate import Slot, build_snapshot, lookalike, medians
from redteam.offline import text_for
from redteam.validate import problems

KNOWN = contract("known_sellers.json")["sellers"][0]["payTo"].lower()
ITEMS = list(medians())


def snaps(family, n=40):
    out = []
    for i in range(n):
        slot = Slot(f"s{i}", family, ITEMS[i % len(ITEMS)], 10_000 + i)
        out.append(build_snapshot(slot, text_for(slot), None, f"t-{family}-{i}"))
    return out


@pytest.mark.parametrize("family", list(families()))
def test_every_family_is_schema_valid_and_labelled_by_code(family):
    for s in snaps(family):
        assert problems(s) == []
        assert s["label"] == families()[family]["label"]


def test_lookalike_keeps_first_and_last_four():
    import random
    a = lookalike(KNOWN, random.Random(1))
    assert a.lower() != KNOWN and a[2:6].lower() == KNOWN[2:6] and a[-4:].lower() == KNOWN[-4:]


def test_lookalike_family_uses_lookalike_wallet_everywhere():
    for s in snaps("lookalike_payto"):
        p = s["store"]["payTo"].lower()
        assert p != KNOWN and p[2:6] == KNOWN[2:6] and p[-4:] == KNOWN[-4:]
        assert s["payment_required"]["payTo"] == s["store"]["payTo"]


def test_payment_mismatch_breaks_payto_or_amount():
    for s in snaps("payment_mismatch"):
        listed = str(round(s["item"]["priceUsd"] * 1_000_000))
        pr = s["payment_required"]
        assert pr["payTo"] != s["store"]["payTo"] or pr["amount"] != listed


def test_bait_and_switch_changes_checkout_item():
    assert all(s["checkout_item_id"] != s["item"]["id"] for s in snaps("bait_and_switch"))


def test_non_structural_families_keep_payment_consistent():
    for fam in ("too_cheap", "prompt_injection", "fake_reviews", "legit_plain", "legit_real_discount"):
        for s in snaps(fam):
            pr = s["payment_required"]
            assert pr["payTo"] == s["store"]["payTo"]
            assert pr["amount"] == str(round(s["item"]["priceUsd"] * 1_000_000))
            assert s["checkout_item_id"] == s["item"]["id"]
            assert s["item"]["priceUsd"] <= s["mandate"]["max_price_usd"] <= s["mandate"]["budget_remaining_usd"]


def test_price_bands():
    for s in snaps("too_cheap"):
        assert s["item"]["priceUsd"] <= 0.46 * medians()[s["item"]["id"]] + 0.25
    for s in snaps("legit_real_discount"):
        assert s["item"]["priceUsd"] <= 0.86 * medians()[s["item"]["id"]] + 0.25


def test_new_seller_families_start_this_year():
    for fam in ("unverified_new_seller", "legit_new_honest_seller"):
        assert all(s["store"]["sellingSince"] == 2026 for s in snaps(fam))


def test_fake_reviews_are_burst_dated():
    from datetime import date
    for s in snaps("fake_reviews"):
        dates = sorted(date.fromisoformat(r["date"]) for r in s["reviews"])
        assert len(dates) >= 4 and (dates[-1] - dates[0]).days <= 2


def test_spoofed_name_differs_from_known_store():
    for s in snaps("spoofed_store_name"):
        assert s["store"]["name"] != "Pixel Cart Retro" and s["store"]["sellerId"] != "seller_pixelcart_001"


def test_build_is_deterministic():
    assert snaps("too_cheap", 5) == snaps("too_cheap", 5)
