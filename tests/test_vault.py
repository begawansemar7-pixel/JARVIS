from knowledge.vault import EncryptedVault


def test_encrypted_vault_round_trip(tmp_path):
    vault = EncryptedVault(tmp_path, EncryptedVault.generate_key())
    path = vault.put("board-2027", b"confidential strategy")
    assert path.read_bytes() != b"confidential strategy"
    assert vault.get("board-2027") == b"confidential strategy"


def test_delete_removes_ciphertext(tmp_path):
    vault = EncryptedVault(tmp_path, EncryptedVault.generate_key())
    vault.put("doc", b"secret")
    vault.delete("doc")
    assert not (tmp_path / "doc.enc").exists()
