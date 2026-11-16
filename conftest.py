"""Make repository tooling importable during test collection."""

import sys
from pathlib import Path

# Insert repo root at position 0 so ``scripts.*`` imports always resolve
# against *this* tree, not any installed copy.
_REPO_ROOT = str(Path(__file__).resolve().parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
