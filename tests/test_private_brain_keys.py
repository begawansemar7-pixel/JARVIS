import pytest
from cryptography.fernet import Fernet

from knowledge.keys import ACCOUNT, ENV_VAR, KeyUnavailableError, load_vault_key


class FakeStore:
    def __init__(self, fail=False):
        self.data = {}
        self.fail = fail

    def get_password(self, service, account):
        if self.fail:
            raise RuntimeError("locked")
        return self.data.get((service, account))

    def set_password(self, service, account, value):
        self.data[(service, account)] = value


@pytest.fixture(autouse=True)
def no_env_key(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)


def test_key_is_created_once_and_reused():
    store = FakeStore()
    first = load_vault_key("svc", backend=store)
    assert load_vault_key("svc", backend=store) == first
    assert store.data[("svc", ACCOUNT)] == first.decode()
    Fernet(first)


def test_missing_key_without_create_raises():
    with pytest.raises(KeyUnavailableError):
        load_vault_key("svc", create=False, backend=FakeStore())


def test_env_override_wins(monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv(ENV_VAR, key.decode())
    assert load_vault_key("svc", backend=FakeStore(fail=True)) == key


def test_invalid_key_is_rejected(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "not-a-key")
    with pytest.raises(KeyUnavailableError):
        load_vault_key("svc", backend=FakeStore())


def test_store_failure_does_not_leak_details():
    with pytest.raises(KeyUnavailableError) as exc:
        load_vault_key("svc", backend=FakeStore(fail=True))
    assert "locked" not in str(exc.value)


def test_insecure_default_backend_is_refused(monkeypatch):
    keyring = pytest.importorskip("keyring")
    from keyring.backends.fail import Keyring as FailKeyring

    monkeypatch.setattr(keyring, "get_keyring", lambda: FailKeyring())
    with pytest.raises(KeyUnavailableError):
        load_vault_key("svc")
