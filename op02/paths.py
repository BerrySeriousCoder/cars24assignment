"""Load immutable, attributed challenge code without editing it."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
for folder in (VENDOR / "OP-01", VENDOR / "OP-02"):
    sys.path.insert(0, str(folder))
CASES = VENDOR / "OP-01/cases/cases.jsonl"
SEED = VENDOR / "OP-01/harbour/seed.json"
RETIRING = VENDOR / "OP-02/retiring-decisions.jsonl"

