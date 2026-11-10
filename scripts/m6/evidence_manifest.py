"""Content-hash a curated, explicit set of nonsecret M6 evidence files.

This is reproducibility metadata, NOT a digital signature or proof that the
contained results are truthful. Never point it at .env/kubeconfig/secret files.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

FORBIDDEN = frozenset((".env", "kubeconfig", "secret", "secrets", "token", "credential",
                       "credentials", "private_key", "id_rsa", "id_ed25519"))


def hash_evidence(root: Path, paths: list[Path]) -> dict:
    root = root.resolve(strict=True)
    if not paths or len(paths) > 150:
        raise ValueError("Provide 1..150 explicitly selected evidence files")
    hashes = []
    seen = set()
    for candidate in paths:
        requested = root / candidate
        # Resolve only after checking the requested path and each parent for
        # symlinks; an internal symlink is still disallowed even if safe today.
        if requested.is_symlink() or any(parent.is_symlink() for parent in requested.parents
                                         if parent != root and parent.is_relative_to(root)):
            raise ValueError("Symbolic links are not accepted as evidence")
        path = requested.resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError("Evidence must stay inside project root")
        relative = path.relative_to(root)
        if any(any(bad in part.lower() for bad in FORBIDDEN)
               for part in relative.parts):
            raise ValueError("Sensitive or linked evidence path blocked")
        if not path.is_file() or path.stat().st_size > 10_000_000:
            raise ValueError("Evidence file must be regular and <=10 MB")
        if relative.as_posix() in seen:
            raise ValueError("Duplicated evidence source")
        seen.add(relative.as_posix())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.append({"path": relative.as_posix(), "bytes": path.stat().st_size,
                       "sha256": digest})
    return {"manifest_version": 1, "created_utc": datetime.now(UTC).isoformat(),
            "files": sorted(hashes, key=lambda x: x["path"]),
            "limitations": (
                "Checksums demonstrate byte identity only, "
                "not authenticity or causality"
            )}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--file", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = hash_evidence(args.root, args.file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(report['files'])} selected file hashes")


if __name__ == "__main__":
    main()
