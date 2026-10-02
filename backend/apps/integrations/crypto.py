import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    configured = settings.GSC_TOKEN_ENCRYPTION_KEY
    if configured:
        key = configured.encode("ascii")
    else:
        key = base64.urlsafe_b64encode(
            hashlib.sha256(f"argus-gsc:{settings.SECRET_KEY}".encode()).digest()
        )
    return Fernet(key)


def encrypt_token(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt_token(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("GSC token 無法解密，請重新連線。") from exc
