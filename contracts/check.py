"""Validate contracts/: every example against snapshot.schema.json, and every example's family against families.json.

Usage:  python contracts/check.py
"""
import json, sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main():
    validator = Draft202012Validator(load("snapshot.schema.json"))
    families = {f["id"]: f for f in load("families.json")["families"]}
    errors = []
    examples = sorted((HERE / "examples").glob("*.json"))
    for path in examples:
        snap = json.loads(path.read_text(encoding="utf-8"))
        errors += [f"{path.name}: {e.json_path}: {e.message}" for e in validator.iter_errors(snap)]
        fam = families.get(snap.get("family"))
        if fam is None:
            errors.append(f"{path.name}: unknown family {snap.get('family')!r}")
        elif fam["label"] != snap.get("label"):
            errors.append(f"{path.name}: label {snap.get('label')!r} != family label {fam['label']!r}")
        ev = snap.get("tactic_evidence")
        if ev and ev not in snap["item"]["description"] and not any(ev in r["body"] for r in snap["reviews"]):
            errors.append(f"{path.name}: tactic_evidence not found in description or reviews")
    for e in errors:
        print("FAIL", e)
    print(f"{len(examples)} examples, {len(errors)} errors")
    return 1 if errors or not examples else 0


if __name__ == "__main__":
    sys.exit(main())
