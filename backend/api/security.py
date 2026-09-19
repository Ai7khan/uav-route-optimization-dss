"""Security: JWT auth for operators and Fernet encryption for stored scenarios.

The brief requires data-protection principles (§7). We provide:
* Token-based auth (JWT) with a hashed operator credential -- no plaintext secrets.
* Symmetric encryption (Fernet/AES) for any scenario/route data written to disk.

Keys are read from environment variables with dev fallbacks so the demo runs
out-of-the-box; in production they would come from a secrets manager.
"""
from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256

# --- config (env with dev fallbacks) ---------------------------------------
JWT_SECRET = os.environ.get("UAV_JWT_SECRET", "dev-secret-change-in-prod")
JWT_ALG = "HS256"
TOKEN_TTL_MIN = 12 * 60

# Demo operator. In production this lives in a user store, never in code.
_DEMO_USER = "operator"
_DEMO_HASH = pbkdf2_sha256.hash(os.environ.get("UAV_OPERATOR_PASSWORD", "uav-demo"))


def _fernet() -> Fernet:
    secret = os.environ.get("UAV_DATA_KEY", "dev-data-key-change-in-prod")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def verify_credentials(username: str, password: str) -> bool:
    return username == _DEMO_USER and pbkdf2_sha256.verify(password, _DEMO_HASH)


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MIN),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload.get("sub")
    except JWTError:
        return None


# --- at-rest encryption -----------------------------------------------------
def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def save_encrypted(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(encrypt_bytes(data))


def load_encrypted(path: str) -> bytes:
    with open(path, "rb") as f:
        return decrypt_bytes(f.read())
