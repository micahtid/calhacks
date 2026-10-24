import random

import pytest

from calhacks_contracts.families import families, label_of

from redteam import mutate

CODE_FAMILIES = [f for f, v in families().items() if not v["needs_llm"]]


@pytest.fixture
def ctx(repo):
    refs = repo.reference_snapshot()
    bases = list(repo.listings(repo.real_listing_ids()))
    return refs, bases


def run(family, ctx, seed=1, base_i=0):
    refs, bases = ctx
    m = mutate.apply(family, bases[base_i], refs, random.Random(seed), bases)
    mandate = mutate.default_mandate(bases[base_i], refs, None)
    syn, case = mutate.finish(f"T-{family}", family, bases[base_i], m, mandate, spec_id="S-t", knowledge="blind",
                              model=None, temperature=None, mode="mutate_real")
    return m, syn, case, bases[base_i]


@pytest.mark.parametrize("family", CODE_FAMILIES)
def test_every_code_family_validates_and_is_labelled_by_code(family, ctx):
    m, syn, case, base = run(family, ctx)
    assert syn.answer_key.label == label_of(family)
    assert syn.answer_key.base_listing_id == base.listing_id
    assert syn.gen.model is None and syn.gen.spec_id == "S-t"
    assert case.mandate.product_key == base.item.product_key
    if family != "legit_plain":
        assert m.diff, family


def test_structural_changes(ctx):
    refs, _ = ctx
    known = {k.pay_to.lower() for k in refs.known_sellers}
    _, s, _, base = run("payment_mismatch", ctx, seed=3)
    c = s.listing.checkout
    assert c.pay_to != s.listing.seller.pay_to or c.amount != mutate.amount(s.listing.item.price)
    _, s, _, _ = run("lookalike_payto", ctx)
    p = s.listing.checkout.pay_to.lower()
    assert p not in known and any(p[2:6] == k[2:6] and p[-4:] == k[-4:] for k in known)
    assert s.listing.seller.pay_to == s.listing.checkout.pay_to
    _, s, _, base = run("bait_and_switch", ctx)
    assert s.listing.checkout.item_id != s.listing.item.id
    _, s, case, base = run("product_switch", ctx)
    assert s.listing.item.product_key != case.mandate.product_key
    m, s, _, _ = run("unknown_seller", ctx)
    assert s.listing.checkout.pay_to.lower() not in known and m.refs.wallets


def test_capped_families_only_start_from_bases_within_the_cap(ctx):
    refs, bases = ctx
    cheap = bases[0].model_copy(deep=True)
    cheap.listing_id, cheap.item.price = "R-cheap", 45.0
    pool = [*bases, cheap]
    for fam in mutate.CAPPED:
        assert [b.listing_id for b in mutate.eligible_bases(fam, pool, refs)] == ["R-cheap"], fam


def test_too_cheap_prices_below_median_and_keeps_checkout_consistent(ctx):
    refs, _ = ctx
    _, s, _, base = run("too_cheap", ctx)
    med = refs.median(base.item.product_key, base.item.condition)
    assert 0.14 * med <= s.listing.item.price <= 0.46 * med
    assert s.listing.checkout.amount == mutate.amount(s.listing.item.price)


def test_layer2_families_move_unknown_sellers_to_a_fresh_wallet(ctx):
    refs, bases = ctx
    unknown = bases[0].model_copy(deep=True)
    unknown.seller.pay_to = unknown.checkout.pay_to = "0x" + "ab" * 20
    m = mutate.apply("too_cheap", unknown, refs, random.Random(2), bases)
    assert m.listing["seller"]["pay_to"].lower() in m.refs.wallets  # new unknown wallet with a first-seen date
    assert m.listing["seller"]["id"] != unknown.seller.id
    # a known base seller is kept
    m = mutate.apply("too_cheap", bases[0], refs, random.Random(2), bases)
    assert not m.refs.wallets and m.listing["seller"]["id"] == bases[0].seller.id


def test_hidden_text_inserts_invisible_or_mixed_script_text(ctx):
    for seed in range(6):
        _, s, _, base = run("hidden_text", ctx, seed=seed)
        t = s.listing.item.text
        assert t != base.item.text
        assert any(ch in t for ch in mutate.ZERO_WIDTH) or any(ch in t for ch in mutate.HOMOGLYPHS.values())


def test_lookalike_domain_differs_from_known_domain(ctx):
    refs, _ = ctx
    known = {k.domain for k in refs.known_sellers}
    for seed in range(10):
        _, s, _, _ = run("lookalike_domain", ctx, seed=seed)
        assert s.listing.seller.domain not in known


def test_llm_families_are_flagged_not_applied(ctx):
    refs, bases = ctx
    for fam in ("prompt_injection", "fake_reviews", "urgency_pressure", "legit_mixed_reviews"):
        assert mutate.apply(fam, bases[0], refs, random.Random(0), bases).llm_task == fam


def test_lookalike_payto_needs_known_sellers(ctx):
    refs, bases = ctx
    refs.known_sellers = []
    with pytest.raises(mutate.MutationError):
        mutate.apply("lookalike_payto", bases[0], refs, random.Random(0), bases)


def test_deterministic(ctx):
    a = run("too_cheap", ctx, seed=9)[1]
    b = run("too_cheap", ctx, seed=9)[1]
    assert a == b
