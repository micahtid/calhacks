"""The one train/val split rule (contracts/interfaces.md). Holdout rows never live under the data root."""
import hashlib


def split_of(snapshot_id: str) -> str:
    return "val" if int(hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest(), 16) % 5 == 0 else "train"
