from __future__ import annotations

import hashlib
from pathlib import Path


class SkillIntegrityError(ValueError):
    pass


def package_checksum(root: Path) -> str:
    """Return deterministic SHA-256 for a skill package.

    Paths and bytes are hashed in sorted relative-path order. Runtime/cache
    files are excluded so the same package produces a reproducible checksum.
    """
    if not root.is_dir():
        raise SkillIntegrityError(f"skill root is not a directory: {root}")

    digest = hashlib.sha256()
    excluded = {"__pycache__", ".git", ".DS_Store"}
    files = [
        p for p in root.rglob("*")
        if p.is_file() and not any(part in excluded for part in p.relative_to(root).parts)
    ]
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def verify_checksum(root: Path, expected: str) -> bool:
    return package_checksum(root) == expected.lower().strip()
