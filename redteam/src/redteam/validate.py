"""Check a generated Snapshot before it is kept (plan B2/B4).

The schema is the single source of truth (contracts/snapshot.schema.json). On top of it: the family is known, the label
matches the family (labels come from code), and quoted tactic evidence really appears in the listing.
"""
from functools import cache

from jsonschema import Draft202012Validator

from redteam.config import contract, families

TEXT_TACTICS = {"prompt_injection", "urgency_pressure"}


@cache
def _validator():
    return Draft202012Validator(contract("snapshot.schema.json"))


def problems(snap: dict) -> list[str]:
    out = [f"{e.json_path}: {e.message}" for e in _validator().iter_errors(snap)]
    if out:
        return out
    fam = families().get(snap["family"])
    if fam is None:
        return [f"unknown family {snap['family']!r}"]
    if fam["label"] != snap["label"]:
        out.append(f"label {snap['label']!r} does not match family label {fam['label']!r}")
    ev = snap["tactic_evidence"]
    if snap["family"] in TEXT_TACTICS:
        if not ev or len(ev) < 12:
            out.append("text tactic without tactic_evidence")
        elif ev not in snap["item"]["description"] and not any(ev in r["body"] for r in snap["reviews"]):
            out.append("tactic_evidence not found in description or reviews")
    elif ev is not None:
        out.append("tactic_evidence set on a non-text family")
    if snap["store"]["reviewCount"] < len(snap["reviews"]):
        out.append("store.reviewCount smaller than the number of reviews shown")
    return out


def is_valid(snap: dict) -> bool:
    return not problems(snap)
