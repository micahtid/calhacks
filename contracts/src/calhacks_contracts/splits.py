"""The one train/val split rule both sides use. Holdout listings never live in the shared database."""
import hashlib
from typing import Literal


def split_of(listing_id: str) -> Literal["train", "val"]:
    return "val" if int(hashlib.sha256(listing_id.encode()).hexdigest(), 16) % 5 == 0 else "train"
