"""
Root conftest.py – adds the repository root to sys.path so that the
``scripts`` package (and sub-packages scripts.m5, scripts.m6, scripts.m7)
are importable with their fully-qualified names from any test directory.
"""
import sys
from pathlib import Path

# Insert repo root at position 0 so ``scripts.*`` imports always resolve
# against *this* tree, not any installed copy.
_REPO_ROOT = str(Path(__file__).resolve().parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
