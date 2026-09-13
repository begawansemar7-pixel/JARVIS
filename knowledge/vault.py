"""Encrypted local document vault primitives for JARVIS Private Brain.

The vault stores ciphertext only. Key management is deliberately external: in
production use an OS keychain, KMS, HSM, or enterprise secrets manager rather
than committing a key to the repository or storing it beside the vault.
"""
from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet


class EncryptedVault:
    def __init__(self, root: str | Path, key: bytes):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._cipher = Fernet(key)

    @staticmethod
    def generate_key() -> bytes:
        return Fernet.generate_key()

    def put(self, document_id: str, plaintext: bytes) -> Path:
        safe_id = "".join(ch for ch in document_id if ch.isalnum() or ch in "-_.")
        if not safe_id:
            raise ValueError("invalid document_id")
        target = self.root / f"{safe_id}.enc"
        target.write_bytes(self._cipher.encrypt(plaintext))
        return target

    def get(self, document_id: str) -> bytes:
        safe_id = "".join(ch for ch in document_id if ch.isalnum() or ch in "-_.")
        if not safe_id:
            raise ValueError("invalid document_id")
        return self._cipher.decrypt((self.root / f"{safe_id}.enc").read_bytes())

    def delete(self, document_id: str) -> None:
        safe_id = "".join(ch for ch in document_id if ch.isalnum() or ch in "-_.")
        if not safe_id:
            raise ValueError("invalid document_id")
        (self.root / f"{safe_id}.enc").unlink(missing_ok=True)


__all__ = ["EncryptedVault"]
