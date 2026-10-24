"""Paths, model ids and budgets. Everything else imports from here."""
import json
import os
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[3]
load_dotenv(REPO / ".env")

CONTRACTS = REPO / "contracts"
GATE_DIR = REPO / "gate"  # the coordinator's cwd
MODELS_DIR = GATE_DIR / "models"
DATA = Path(os.environ.get("CALHACKS_DATA", REPO / "data")).resolve()
ROUNDS = DATA / "rounds"
HOLDOUT = Path(os.environ.get("CALHACKS_HOLDOUT", REPO.parent / "calhacks-holdout")).resolve()
HOLDOUT_FILE = HOLDOUT / "holdout.jsonl.enc"
HOLDOUT_KEY_FILE = HOLDOUT / "holdout.key"
FACTORY_SETTINGS = REPO / "redteam" / "factory" / "settings.json"

BITDEER_BASE = "https://api-inference.bitdeer.ai/v1"
BULK_MODELS = ["zai-org/GLM-5.3-Flash", "deepseek-ai/DeepSeek-V4.1-Flash"]
HOLDOUT_MODEL = "nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B"
COORDINATOR_MODEL = "custom:DeepSeek-V4.1-Flash-(Bitdeer)-0"
STRATEGIST_DROID = "attack-strategist"

BATCH_SIZE = 15          # slots per Bitdeer call (plan C2)
CONCURRENCY = 16
MAX_N_PER_SPEC = 600
ROUND_TOKEN_BUDGET = 3_000_000     # bulk generation tokens per round (C8)
ROUND_WALL_SECONDS = 45 * 60

# C6 promotion rule
MAX_FPR = 0.02
MAX_FAMILY_DROP = 0.05


@cache
def contract(name: str):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def families() -> dict:
    return {f["id"]: f for f in contract("families.json")["families"]}


def holdout_families() -> list[str]:
    return list(contract("families.json")["holdout_families"])


def scam_families(include_holdout=False) -> list[str]:
    hold = set(holdout_families())
    return [k for k, f in families().items() if f["label"] == "scam" and (include_holdout or k not in hold)]


def legit_families() -> list[str]:
    return [k for k, f in families().items() if f["label"] == "legit"]


def round_dir(n: int) -> Path:
    d = ROUNDS / f"R{n}"
    d.mkdir(parents=True, exist_ok=True)
    return d
