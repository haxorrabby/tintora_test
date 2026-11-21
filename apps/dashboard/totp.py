import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _encryption_cipher() -> Fernet:
    configured_key = getattr(settings, "TOTP_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    derived_key = hashlib.sha256(configured_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def encrypt_totp_secret(secret: str) -> str:
    if secret.startswith("fernet:v1:"):
        return secret
    encrypted = _encryption_cipher().encrypt(secret.encode("ascii")).decode("ascii")
    return f"fernet:v1:{encrypted}"


def decrypt_totp_secret(secret: str) -> str:
    if not secret.startswith("fernet:v1:"):
        return secret
    try:
        decrypted = _encryption_cipher().decrypt(secret.removeprefix("fernet:v1:").encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("TOTP secret cannot be decrypted; check the configured encryption key.") from exc
    return decrypted.decode("ascii")


def totp_code(secret: str, timestamp: int | None = None, interval: int = 30) -> str:
    padded_secret = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    counter = int((timestamp if timestamp is not None else time.time()) // interval)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def verify_totp(secret: str, value: str, timestamp: int | None = None, window: int = 1) -> bool:
    candidate = "".join(character for character in value if character.isdigit())
    if len(candidate) != 6 or not secret:
        return False
    now = time.time() if timestamp is None else timestamp
    return any(
        hmac.compare_digest(totp_code(secret, int(now + offset * 30)), candidate)
        for offset in range(-window, window + 1)
    )


def provisioning_uri(secret: str, email: str, issuer: str = "Tintora") -> str:
    account_label = quote(f"{issuer}:{email}", safe="")
    return (
        f"otpauth://totp/{account_label}?secret={quote(secret)}"
        f"&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )
