from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass

from cryptography.fernet import Fernet

from app.config import get_settings


@dataclass(frozen=True)
class IssuedKey:
    plaintext: str
    digest: str


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_key(prefix: str) -> IssuedKey:
    plaintext = f"{prefix}_{secrets.token_urlsafe(32)}"
    return IssuedKey(plaintext=plaintext, digest=hash_key(plaintext))


def member_hash(tenant_id: str, member_id: str) -> str:
    settings = get_settings()
    raw = f"{settings.secret_key}:{tenant_id}:{member_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_fernet() -> Fernet:
    settings = get_settings()
    if settings.fernet_key:
        key = settings.fernet_key.encode("utf-8")
    else:
        digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
