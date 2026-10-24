"""Load Snapshot JSONL files or directories and turn them into feature matrices."""
import hashlib
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from gatepy.contracts import Snapshot
from gatepy.context import Ctx
from gatepy.registry import Feature, compute


class GateInputError(ValueError):
    """Bad input: the CLIs exit 2 with {"error": ...}."""


def iter_paths(paths: list[str | Path]) -> list[Path]:
    out = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(p.rglob("*.jsonl"))
        elif p.is_file():
            out.append(p)
        else:
            raise GateInputError(f"no such file or directory: {p}")
    return out


def load_snapshots(paths: list[str | Path]) -> list[Snapshot]:
    snaps = []
    for path in iter_paths(paths):
        with path.open(encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    snaps.append(Snapshot.model_validate_json(line))
                except ValidationError as e:
                    raise GateInputError(f"{path}:{n}: invalid snapshot: {e.errors()[0]['msg']} at {e.errors()[0]['loc']}") from e
    ids = [s.id for s in snaps]
    if len(ids) != len(set(ids)):
        dup = next(i for i in ids if ids.count(i) > 1)
        raise GateInputError(f"duplicate snapshot id {dup!r}")
    return snaps


def data_hash(snaps: list[Snapshot]) -> str:
    h = hashlib.sha256()
    for s in sorted(snaps, key=lambda s: s.id):
        h.update(s.model_dump_json().encode("utf-8"))
    return h.hexdigest()


def featurize(snaps: list[Snapshot], ctx: Ctx, feats: list[Feature]) -> np.ndarray:
    if not snaps:
        return np.zeros((0, len(feats)))
    return np.array([compute(s, ctx, feats) for s in snaps], dtype=np.float64)
