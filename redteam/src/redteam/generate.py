"""Attack factory (plan C9a, issue #1 schema 3): AttackSpec -> SyntheticListing + Case, written to MongoDB.

mode=mutate_real (primary): each slot copies a real listing from MongoDB and changes one thing (mutate.py); families
with needs_llm also get item.text or reviews rewritten through Bitdeer. mode=generate: Bitdeer writes fresh text for
the base listing's product; code still sets every structural field. Every listing is validated with the pydantic
models; LLM slots that fail are retried once, then dropped, and drops are counted per family.

Usage (needs real listings in MongoDB, see contracts-ingest; LLM families need BITDEER_API_KEY):
  uv run --project redteam python -m redteam.generate --round 1 --family too_cheap --n 40 --legit-ratio 0.4
  uv run --project redteam python -m redteam.generate --round 1 --spec spec.json
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from calhacks_contracts import AttackSpec, Listing
from calhacks_contracts.db import ReferenceSet, Repo
from pydantic import ValidationError

from redteam import bitdeer, mutate, prompts, store
from redteam.config import (BATCH_SIZE, BULK_MODELS, CONCURRENCY, families, holdout_families, legit_families,
                            legit_hard, usd)


class SpecError(ValueError):
    pass


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def parse_spec(spec: dict | AttackSpec, *, allow_holdout: bool = False) -> AttackSpec:
    try:
        s = spec if isinstance(spec, AttackSpec) else AttackSpec.model_validate(spec)
    except ValidationError as e:
        raise SpecError(f"invalid AttackSpec: {e.errors()[:3]}") from None
    if s.family != "legit_hard" and s.family not in families():
        raise SpecError(f"unknown family {s.family!r}")
    if s.family in holdout_families() and not allow_holdout:
        raise SpecError(f"family {s.family!r} is reserved for the holdout")
    if s.family != "legit_hard" and families()[s.family]["label"] == "legit":
        raise SpecError("family must be an attack family or 'legit_hard'; honest listings come from legit_ratio")
    return s


def plan_families(s: AttackSpec, rng: random.Random) -> list[str]:
    if s.family == "legit_hard":
        pool = list(legit_hard())
        fams = [pool[i % len(pool)] for i in range(s.n)]
    else:
        n_legit = round(s.n * s.legit_ratio)
        pool = legit_families()
        fams = [s.family] * (s.n - n_legit) + [pool[i % len(pool)] for i in range(n_legit)]
    rng.shuffle(fams)
    return fams


def _bases(r: Repo, s: AttackSpec) -> list[Listing]:
    ids = s.base_listing_ids or r.real_listing_ids()
    real = set(r.real_listing_ids())
    bad = [i for i in ids if i not in real]
    if bad:
        raise SpecError(f"base_listing_ids must be real listings in MongoDB; not found: {bad[:5]}")
    bases = list(r.listings(ids))
    if not bases:
        raise SpecError("no real listings in MongoDB to mutate; ingest some with contracts-ingest listings")
    return sorted(bases, key=lambda l: l.listing_id)


def _apply_llm(m: mutate.Mutation, base: Listing, out: dict, task: str | None) -> tuple[str, list[str], str | None]:
    text = out.get("text") or base.item.text
    reviews = out.get("reviews") if out.get("reviews") is not None else list(base.reviews)
    ev = out.get("tactic_evidence")
    if text != base.item.text:
        m.listing["item"]["text"] = text
        m.diff["item.text"] = f"rewritten by LLM ({task or 'honest'})" + (f": {ev[:80]!r}" if ev else "")
    if reviews != list(base.reviews):
        m.listing["reviews"] = reviews
        m.diff["reviews"] = f"rewritten by LLM ({task or 'honest'}), {len(reviews)} reviews"
    return text, reviews, ev


def run_spec(spec: dict | AttackSpec, *, round_: int, r: Repo | None = None, client=None, write: bool = True,
             allow_holdout: bool = False, seed: int = 0, white_box: dict | None = None,
             models: list[str] | None = None, token_budget: int = 10 ** 12, id_prefix: str = "S") -> dict:
    s = parse_spec(spec, allow_holdout=allow_holdout)
    r = r or store.repo()
    refs: ReferenceSet = r.reference_snapshot()
    bases = _bases(r, s)
    others = bases
    rng = random.Random(_seed(s.spec_id, seed))
    fams = plan_families(s, rng)
    models = [s.model] if s.model else (models or BULK_MODELS)
    tally = bitdeer.Tally()
    dropped: list[dict] = []
    kept: list = []
    sim = mutate.SimRefs()
    llm_queue = []  # (slot_id, family, base, mutation, mandate)

    for i, fam in enumerate(fams):
        lid = f"{id_prefix}{round_}-{s.spec_id}-{i:04d}"
        pool = mutate.eligible_bases(fam, bases, refs)
        if not pool:
            dropped.append({"listing_id": lid, "family": fam,
                            "why": "no base listing priced within unknown_seller_cap_usd"})
            continue
        base = rng.choice(pool)
        srng = random.Random(_seed(s.spec_id, seed, i))
        try:
            m = mutate.apply(fam, base, refs, srng, others)
        except mutate.MutationError as e:
            dropped.append({"listing_id": lid, "family": fam, "why": str(e)})
            continue
        mandate = mutate.default_mandate(base, refs, r.case(base.listing_id))
        if m.llm_task or s.mode == "generate":
            llm_queue.append((lid, fam, base, m, mandate))
            continue
        try:
            kept.append(mutate.finish(lid, fam, base, m, mandate, spec_id=s.spec_id, knowledge=s.attacker_knowledge,
                                      model=None, temperature=None, mode=s.mode))
            sim.extend(m.refs)
        except (ValidationError, ValueError) as e:
            dropped.append({"listing_id": lid, "family": fam, "why": f"invalid: {str(e)[:120]}"})

    if llm_queue and client is None:
        try:
            client = bitdeer.make_client()
        except RuntimeError as e:  # no key: code-only slots still count, LLM slots are dropped and logged
            dropped += [{"listing_id": q[0], "family": q[1], "why": f"no Bitdeer client: {e}"} for q in llm_queue]
            llm_queue = []
    if llm_queue:
        chunks = [llm_queue[j:j + BATCH_SIZE] for j in range(0, len(llm_queue), BATCH_SIZE)]

        def run_chunk(ci_chunk):
            ci, chunk = ci_chunk
            model = models[ci % len(models)]
            temp = s.temperature if s.temperature is not None else round(random.Random(_seed(s.spec_id, ci)).uniform(0.8, 1.0), 2)
            done, fails = [], []
            pending = chunk
            for attempt in range(2):
                if not pending:
                    break
                if tally.total >= token_budget:
                    fails = [(p, "token budget exhausted") for p in pending]
                    break
                slots = [prompts.LlmSlot(lid, m.llm_task, s.mode, b.item.product_key, b.item.condition, b.item.text,
                                         tuple(b.reviews)) for lid, _, b, m, _ in pending]
                payload = bitdeer.complete_json(client, model, prompts.build_messages(slots, s.target_weakness,
                                                                                      white_box), temp, tally)
                outs = prompts.parse_slots(payload) if payload is not None else {}
                fails = []
                for p in pending:
                    lid, fam, base, m, mandate = p
                    out = outs.get(lid)
                    if out is None:
                        fails.append((p, "no text returned"))
                        continue
                    trial = mutate.Mutation({**m.listing, "item": dict(m.listing["item"]),
                                             "reviews": list(m.listing["reviews"])}, dict(m.diff), m.refs, m.llm_task)
                    text, reviews, ev = _apply_llm(trial, base, out, m.llm_task)
                    errs = prompts.problems(m.llm_task, s.mode, text, reviews, ev)
                    if errs:
                        fails.append((p, errs[0]))
                        continue
                    try:
                        done.append((mutate.finish(lid, fam, base, trial, mandate, spec_id=s.spec_id,
                                                   knowledge=s.attacker_knowledge, model=model, temperature=temp,
                                                   mode=s.mode), trial.refs))
                    except (ValidationError, ValueError) as e:
                        fails.append((p, f"invalid: {str(e)[:120]}"))
                pending = [p for p, _ in fails]
            return done, [{"listing_id": p[0], "family": p[1], "why": why} for p, why in fails]

        with ThreadPoolExecutor(CONCURRENCY) as ex:
            for done, fails in ex.map(run_chunk, enumerate(chunks)):
                for item, refs_ in done:
                    kept.append(item)
                    sim.extend(refs_)
                dropped += fails

    kept.sort(key=lambda it: it[0].listing.listing_id)
    cost = sum(usd(m, p, c) for m, (p, c) in tally.by_model.items())
    summary = {
        "spec_id": s.spec_id, "round": round_, "family": s.family, "mode": s.mode, "requested": s.n,
        "kept": len(kept), "dropped": len(dropped),
        "drops_by_family": dict(Counter(d["family"] for d in dropped)),
        "drop_reasons": Counter(d["why"][:60] for d in dropped).most_common(5),
        "by_family": dict(Counter(it[0].answer_key.family for it in kept)),
        "models": sorted({it[0].gen.model for it in kept if it[0].gen.model}),
        "tokens": tally.as_dict(), "usd": round(cost, 4),
    }
    if write:
        r.put_synthetic(kept)
        for w, seen in sim.wallets.items():
            r.touch_wallet(w, seen)
        store.record_spec(r, s.model_dump(mode="json"), round_, summary)
    summary["_items"] = kept
    summary["_refs"] = sim
    summary["_dropped"] = dropped
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--spec", help="JSON file with an AttackSpec")
    ap.add_argument("--family")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--legit-ratio", type=float, default=0.4)
    ap.add_argument("--mode", default="mutate_real", choices=["mutate_real", "generate"])
    ap.add_argument("--target-weakness")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    if a.spec:
        spec = json.loads(open(a.spec, encoding="utf-8").read())
    else:
        if not a.family:
            ap.error("--family or --spec is required")
        spec = {"spec_id": f"R{a.round}-{a.family}-{a.seed}", "family": a.family, "n": a.n,
                "legit_ratio": a.legit_ratio, "mode": a.mode, "target_weakness": a.target_weakness}
    try:
        summary = run_spec(spec, round_=a.round, seed=a.seed)
    except SpecError as e:
        print(json.dumps({"error": str(e)}))
        return 2
    for k in ("_items", "_refs", "_dropped"):
        summary.pop(k)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
