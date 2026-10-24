"""Stand-in for gate-train / gate-eval until feat/gate is merged. Same inputs, same JSON (contracts/interfaces.md).

A tiny logistic regression over six hand-written features plus an emulated Layer 1, so the MCP tools and the
coordinator loop produce realistic, deterministic numbers. It ignores gate/features/*, so coordinator edits have no
effect until the real gate is wired in.
"""
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from redteam.config import MAX_FPR, MODELS_DIR, contract
from redteam.splits import iter_rows

FEATURES = ["price_ratio", "seller_age_years", "injection_hits", "review_dup_max", "unverified_frac", "urgency_hits"]
MONOTONE = [-1, -1, 1, 1, 1, 1]
URGENCY = re.compile(r"\b(hurry|immediately|right away|expires?|last (one|unit)|only 1 left|ends in|act now|"
                     r"before it.?s gone|checking out)\b", re.I)


def _patterns():
    return [re.compile(p, re.I) for p in contract("injection_patterns.json")["patterns"]]


def _tokens(s):
    return set(re.findall(r"[a-z]+", s.lower()))


def featurize(s: dict) -> list[float]:
    med = contract("market_medians.json")["medians"].get(s["item"]["id"]) or s["item"]["priceUsd"]
    text = s["item"]["description"] + " " + " ".join(r["body"] for r in s["reviews"])
    bodies = [_tokens(r["body"]) for r in s["reviews"]]
    dup = max((len(a & b) / max(1, len(a | b)) for i, a in enumerate(bodies) for b in bodies[i + 1:]), default=0.0)
    unverified = sum(not r["verifiedPurchase"] for r in s["reviews"]) / max(1, len(s["reviews"]))
    return [s["item"]["priceUsd"] / med, float(2026 - s["store"]["sellingSince"]),
            float(sum(bool(p.search(text)) for p in _patterns())), dup, unverified, float(len(URGENCY.findall(text)))]


def layer1(s: dict) -> list[str]:
    allow, known = contract("allowlist.json"), contract("known_sellers.json")["sellers"]
    pr, st, out = s["payment_required"], s["store"], []
    if pr["payTo"].lower() != st["payTo"].lower():
        out.append("L1_PAYTO_MISMATCH")
    p = pr["payTo"].lower()
    for k in known:
        kp = k["payTo"].lower()
        if p != kp and p[2:6] == kp[2:6] and p[-4:] == kp[-4:]:
            out.append("L1_PAYTO_LOOKALIKE")
            break
    if int(pr["amount"]) != round(s["item"]["priceUsd"] * 10 ** allow["usdc_decimals"]):
        out.append("L1_AMOUNT_MISMATCH")
    if s["item"]["priceUsd"] > s["mandate"]["max_price_usd"]:
        out.append("L1_OVER_MAX")
    if s["item"]["priceUsd"] > s["mandate"]["budget_remaining_usd"]:
        out.append("L1_OVER_BUDGET")
    if pr["network"] not in allow["networks"]:
        out.append("L1_NETWORK")
    if pr["asset"].lower() != allow["assets"].get(pr["network"], "").lower():
        out.append("L1_ASSET")
    if pr["scheme"] not in allow["schemes"]:
        out.append("L1_SCHEME")
    if pr["maxTimeoutSeconds"] > allow["max_timeout_s"]:
        out.append("L1_TIMEOUT")
    if s["checkout_item_id"] != s["item"]["id"]:
        out.append("L1_ITEM_MISMATCH")
    return out


def _sigmoid(z):
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def _fit(X, y, epochs=400, lr=0.3):
    mu = [sum(c) / len(c) for c in zip(*X)]
    sd = [max(1e-6, (sum((v - m) ** 2 for v in c) / len(c)) ** 0.5) for c, m in zip(zip(*X), mu)]
    Z = [[(v - m) / d for v, m, d in zip(x, mu, sd)] for x in X]
    w, b = [0.0] * len(mu), 0.0
    for _ in range(epochs):
        gw, gb = [0.0] * len(w), 0.0
        for z, t in zip(Z, y):
            e = _sigmoid(sum(a * c for a, c in zip(w, z)) + b) - t
            gw = [g + e * c for g, c in zip(gw, z)]
            gb += e
        w = [a - lr * g / len(Z) for a, g in zip(w, gw)]
        b -= lr * gb / len(Z)
    # Monotone constraints: zero out any weight pointing the wrong way.
    w = [0.0 if m and a * m < 0 else a for a, m in zip(w, MONOTONE)]
    return {"mu": mu, "sd": sd, "w": w, "b": b}


def _score(coef, x):
    z = [(v - m) / d for v, m, d in zip(x, coef["mu"], coef["sd"])]
    contrib = [a * c for a, c in zip(coef["w"], z)]
    return _sigmoid(sum(contrib) + coef["b"]), contrib


def _load(model_id: str) -> dict:
    if model_id == "promoted":
        model_id = json.loads((MODELS_DIR / "promoted.json").read_text())["model_id"]
    return json.loads((MODELS_DIR / f"{model_id}.json").read_text())


def _decide(model, s):
    fails = layer1(s)
    risk, contrib = _score(model["coef"], featurize(s))
    x = featurize(s)
    top3 = sorted(([f, round(v, 4), round(c, 4)] for f, v, c in zip(FEATURES, x, contrib)), key=lambda t: -t[2])[:3]
    layer = "L1" if fails else ("L2" if risk >= model["threshold"] else None)
    return {"id": s["id"], "family": s["family"], "label": s["label"], "decision": "skip" if layer else "buy",
            "layer": layer, "risk": round(risk, 4), "top3": top3, "l1_failures": fails}


def metrics(rows: list[dict], with_rows: bool = False) -> dict:
    scam = [r for r in rows if r["label"] == "scam"]
    legit = [r for r in rows if r["label"] == "legit"]
    l2_scam = [r for r in scam if r["layer"] != "L1"]
    l2_legit = [r for r in legit if r["layer"] != "L1"]
    skip = lambda rs: sum(r["decision"] == "skip" for r in rs)
    rate = lambda rs: round(skip(rs) / len(rs), 4) if rs else 0.0
    fam = defaultdict(list)
    for r in rows:
        fam[r["family"]].append(r)
    per_family = {f: ({"n": len(rs), "recall": rate(rs)} if rs[0]["label"] == "scam" else {"n": len(rs), "fpr": rate(rs)})
                  for f, rs in sorted(fam.items())}
    out = {"n": len(rows), "n_scam": len(scam), "n_legit": len(legit), "recall": rate(scam), "fpr": rate(legit),
           "recall_l2": rate(l2_scam), "fpr_l2": rate(l2_legit), "l1_catches": sum(r["layer"] == "L1" for r in rows),
           "per_family": per_family}
    if with_rows:
        out["rows"] = [{k: r[k] for k in ("id", "family", "label", "decision", "layer", "risk", "top3")} for r in rows]
    return out


def train(paths: list[Path], round_: int) -> dict:
    train_rows = list(iter_rows(paths, "train"))
    val_rows = list(iter_rows(paths, "val"))
    if not train_rows or not val_rows:
        return {"error": "need train and val rows"}
    X = [featurize(s) for s in train_rows]
    coef = _fit(X, [1 if s["label"] == "scam" else 0 for s in train_rows])
    # Threshold: lowest cut whose L2-only val FPR stays within MAX_FPR.
    legit_risks = sorted((_score(coef, featurize(s))[0] for s in val_rows if s["label"] == "legit" and not layer1(s)),
                         reverse=True)
    allowed = int(MAX_FPR * len(legit_risks))
    threshold = round(legit_risks[allowed] + 1e-6, 6) if len(legit_risks) > allowed else 0.5
    data_hash = hashlib.sha256("".join(sorted(s["id"] for s in train_rows)).encode()).hexdigest()[:12]
    model_id = f"r{round_}-stub-{data_hash[:6]}"
    model = {"model_id": model_id, "round": round_, "kind": "stub", "features": FEATURES, "monotone": MONOTONE,
             "threshold": threshold, "booster": None, "coef": coef, "train_data_hash": data_hash,
             "feature_code_hash": "stub", "created_at": datetime.now(timezone.utc).isoformat()}
    model["val_metrics"] = metrics([_decide(model, s) for s in val_rows])
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (MODELS_DIR / f"{model_id}.json").write_text(json.dumps(model, indent=1))
    return {"model_id": model_id, "round": round_, "kind": "stub", "features": FEATURES, "n_train": len(train_rows),
            "n_val": len(val_rows), "threshold": threshold, "val": model["val_metrics"]}


def evaluate(model_id: str, paths: list[Path], split: str = "all", rows: bool = False) -> dict:
    try:
        model = _load(model_id)
    except FileNotFoundError:
        return {"error": f"unknown model {model_id!r}"}
    return metrics([_decide(model, s) for s in iter_rows(paths, split)], with_rows=rows)
