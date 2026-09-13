"""Vault key management for Private Brain.

The key lives in the OS credential store (macOS Keychain, Windows Credential
Locker, Linux Secret Service) via `keyring` — never in the repository and never
beside the vault. `JARVIS_PRIVATE_BRAIN_KEY` overrides it for headless/CI runs.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet

ENV_VAR = "JARVIS_PRIVATE_BRAIN_KEY"
ACCOUNT = "vault-key"

# Backends that would store the key in plaintext or not at all.
_INSECURE_BACKEND_MODULES = ("keyring.backends.fail", "keyring.backends.null", "keyrings.alt")


class KeyUnavailableError(RuntimeError):
    """Raised when no secure vault key can be obtained."""


def _validated(key: str | bytes, source: str) -> bytes:
    raw = key.encode("ascii") if isinstance(key, str) else key
    try:
        Fernet(raw)
    except Exception:
        raise KeyUnavailableError(f"vault key from {source} is not a valid Fernet key") from None
    return raw


def _default_backend():
    try:
        import keyring
    except ImportError:
        raise KeyUnavailableError("the 'keyring' package is not installed") from None
    module = type(keyring.get_keyring()).__module__
    if module.startswith(_INSECURE_BACKEND_MODULES):
        raise KeyUnavailableError(f"no secure OS credential store available (backend: {module})")
    return keyring


def load_vault_key(service: str, *, create: bool = True, backend=None) -> bytes:
    env_key = os.environ.get(ENV_VAR)
    if env_key:
        return _validated(env_key, ENV_VAR)

    store = backend if backend is not None else _default_backend()
    try:
        stored = store.get_password(service, ACCOUNT)
    except Exception as e:
        raise KeyUnavailableError(f"credential store read failed: {type(e).__name__}") from None
    if stored:
        return _validated(stored, "credential store")
    if not create:
        raise KeyUnavailableError("no vault key in the credential store")

    key = Fernet.generate_key()
    try:
        store.set_password(service, ACCOUNT, key.decode("ascii"))
        if store.get_password(service, ACCOUNT) != key.decode("ascii"):
            raise RuntimeError("read-back mismatch")
    except Exception as e:
        raise KeyUnavailableError(f"credential store write failed: {type(e).__name__}") from None
    return key


__all__ = ["ENV_VAR", "KeyUnavailableError", "load_vault_key"]
