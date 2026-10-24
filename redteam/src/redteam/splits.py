"""Train/val assignment and round data loading (contracts/interfaces.md, "Split rule")."""
import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from redteam.config import ROUNDS


# JOIN: replace this copy with `from gatepy.splits import split_of` once feat/gate is merged.
def split_of(snapshot_id: str) -> str:
    return "val" if int(hashlib.sha256(snapshot_id.encode()).hexdigest(), 16) % 5 == 0 else "train"


def round_files(rounds: Iterable[int] | None = None) -> list[Path]:
    """Batch files for the given rounds (all rounds when None), in a stable order."""
    if not ROUNDS.exists():
        return []
    wanted = None if rounds is None else {f"R{r}" for r in rounds}
    return sorted(p for d in ROUNDS.iterdir() if d.is_dir() and (wanted is None or d.name in wanted)
                  for p in d.glob("*.jsonl"))


def iter_rows(paths: Iterable[Path], split: str = "all") -> Iterator[dict]:
    for p in paths:
        with p.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if split == "all" or split_of(row["id"]) == split:
                        yield row
