"""Gate Layer 2: features, training, evaluation and scoring. Layer 1 lives in gate/layer1 (TypeScript)."""
import os
from pathlib import Path

GATE_DIR = Path(__file__).resolve().parents[1]
REPO = GATE_DIR.parent
CONTRACTS = Path(os.environ.get("CALHACKS_CONTRACTS", REPO / "contracts"))
DATA = Path(os.environ.get("CALHACKS_DATA", REPO / "data"))
MODELS = Path(os.environ.get("GATE_MODELS", GATE_DIR / "models"))
LAYER1_CLI = GATE_DIR / "layer1" / "src" / "cli.ts"
