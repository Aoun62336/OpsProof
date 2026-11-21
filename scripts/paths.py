"""Local tool storage and read-only resolution of preserved historical evidence.

Current run output stays in the checkout's ignored .runtime directory. Large
tools/caches and retained historical records live in a separate user-local root.
Frozen evidence bytes and recorded relative locators are never rewritten.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_AREAS = {"platform": "m5", "reliability": "m6"}


def local_root() -> Path:
    override = os.environ.get("OPSPROOF_LOCAL_DIR")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError("OPSPROOF_LOCAL_DIR must be an absolute directory")
    elif os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "OpsProof"
    else:
        path = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "opsproof"
    path = path.resolve()
    if path == ROOT or path.is_relative_to(ROOT):
        raise ValueError("Local tool storage must stay outside the source checkout")
    return path


def tools(*parts: str) -> Path:
    return local_root().joinpath("tools", *parts)


def cache(*parts: str) -> Path:
    return local_root().joinpath("cache", *parts)


def archive_root() -> Path:
    return local_root() / "private/archive/legacy-runtime"


def _relative(value: str) -> Path:
    if not isinstance(value, str) or "\\" in value or ":" in value:
        raise ValueError("Canonical relative runtime locator required")
    parts = value.split("/")
    if parts[0] != ".runtime" or any(part in ("", ".", "..") for part in parts):
        raise ValueError("Runtime locator must stay within its declared root")
    return Path(*parts)


def read_artifact(relative: str, *, root: Path = ROOT) -> Path:
    """Find current output or preserved legacy evidence without changing it."""
    path = _relative(relative)
    root = root.resolve()
    current = root / path
    if current.exists():
        if not current.resolve().is_relative_to(root):
            raise ValueError("Artifact locator escapes the checkout")
        return current
    # Existing frozen locators can still refer to the active renamed area.
    parts = list(path.parts[1:])
    aliases = {old: new for new, old in LEGACY_AREAS.items()}
    if parts and parts[0] in aliases:
        active = root / ".runtime" / aliases[parts[0]]
        active = active.joinpath(*parts[1:])
        if active.exists() and active.resolve().is_relative_to(root):
            return active
    # Isolated test/source roots must never consult another workspace's archive.
    if root != ROOT:
        raise FileNotFoundError(relative)
    parts = list(path.parts[1:])
    if parts:
        parts[0] = LEGACY_AREAS.get(parts[0], parts[0])
    archived = archive_root().joinpath(*parts)
    if not archived.resolve().is_relative_to(archive_root().resolve()):
        raise ValueError("Artifact locator escapes the archive")
    if not archived.exists():
        raise FileNotFoundError(relative)
    return archived


def artifact_locator(path: Path) -> str:
    """Keep archive identities relative; do not expose a private absolute path."""
    path = path.resolve()
    if path.is_relative_to(ROOT):
        return path.relative_to(ROOT).as_posix()
    if path.is_relative_to(archive_root().resolve()):
        return ".runtime/" + path.relative_to(archive_root().resolve()).as_posix()
    raise ValueError("Artifact is outside the source or preserved evidence roots")
