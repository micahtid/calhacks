"""The artifact audit must flag planted tells and pass clean copies."""
import json
import random

from redteam import audit

AS_OF = "2026-10-24"


def listing(i, name, reviews, text, wallet):
    return {"_id": f"L{i}", "listing_id": f"L{i}", "seller": {"id": f"ebay:{name}", "domain": "ebay.com", "pay_to": wallet},
            "item": {"id": f"I{i}", "product_key": "x:jacket", "condition": "used", "price": 30.0, "text": text},
            "reviews": reviews, "checkout": {"pay_to": wallet, "amount": "30000000", "network": "n", "asset": "a",
                                             "item_id": f"I{i}"}}


def write_store(d, rows):
    d.mkdir(parents=True, exist_ok=True)
    cols = {"listings": [], "answer_keys": [], "wallets": [], "gen": [], "known_sellers": []}
    for lst, fam, base in rows:
        cols["listings"].append(lst)
        cols["answer_keys"].append({"_id": lst["_id"], "family": fam, "label": "legit" if fam in ("real", "legit_plain") else "scam",
                                    "base_listing_id": base})
    for name, docs in cols.items():
        (d / f"{name}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in docs), encoding="utf-8")


def real_like(rng, i):
    name = rng.choice(["bob_s", "VintageFinds", "kj-outdoor", "mary.ann", "ThriftKing", "zed"]) + str(rng.randrange(0, 99))
    revs = [("good " * rng.randrange(2, 12)).strip() for _ in range(rng.randrange(0, 9))]
    text = "Jacket. " * rng.randrange(5, 60)
    return listing(i, name, revs, text, "0x" + f"{i:040x}")


def test_planted_name_artifact_is_flagged_and_clean_copies_pass(tmp_path):
    rng = random.Random(1)
    reals = [real_like(rng, i) for i in range(120)]
    rows = [(r, "real", None) for r in reals]
    for j in range(60):  # too_cheap with the old synthetic name shape: must fail
        base = reals[j]
        x = json.loads(json.dumps(base))
        x["_id"] = x["listing_id"] = f"T{j}"
        x["seller"]["id"] = f"ebay:{rng.choice(['pine', 'atlas'])}goods{rng.randrange(100, 999)}"
        rows.append((x, "too_cheap", base["_id"]))
    for j in range(60):  # legit_plain copies of real listings: must pass
        base = reals[60 + j]
        x = json.loads(json.dumps(base))
        x["_id"] = x["listing_id"] = f"P{j}"
        rows.append((x, "legit_plain", base["_id"]))
    write_store(tmp_path, rows)
    res = audit.audit(tmp_path, AS_OF)
    assert res["families"]["too_cheap"]["auc"] > 0.9
    assert res["families"]["too_cheap"]["top_traits"][0][0].startswith("name_")
    assert res["families"]["legit_plain"]["auc"] <= audit.AUC_LIMIT
    assert "too_cheap" in res["failing"] and "legit_plain" not in res["failing"]


def test_touched_traits_are_excluded():
    assert "text" in audit.TOUCHES["hidden_text"] and "wallet" in audit.TOUCHES["unknown_seller"]
    assert "name" not in audit.TOUCHES["unknown_seller"]  # new sellers must still look real
