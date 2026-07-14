from app.security import decrypt_secret, encrypt_secret, hash_key, issue_key, member_hash


def test_key_hashing_and_issue_prefix():
    key = issue_key("mcp")
    assert key.plaintext.startswith("mcp_")
    assert key.digest == hash_key(key.plaintext)
    assert len(key.digest) == 64


def test_secret_encryption_roundtrip():
    encrypted = encrypt_secret("provider-secret")
    assert encrypted != "provider-secret"
    assert decrypt_secret(encrypted) == "provider-secret"


def test_member_hash_is_tenant_bound():
    assert member_hash("tenant-a", "member-1") != member_hash("tenant-b", "member-1")
