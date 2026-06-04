from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated, Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Depends, Header, HTTPException, status

from .config import settings
from .db import get_db, row_to_dict


# ── Key derivation ─────────────────────────────────────────────────────────
# Two independent keys are derived from the single app secret using HKDF with
# distinct info labels, so the token-signing key and the encryption key are not
# the same material (defense-in-depth: compromise of one does not reveal the other).


def _derive_key(info: bytes, length: int = 32) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=info,
    ).derive(settings.app_secret.encode("utf-8"))


def _token_key() -> bytes:
    return _derive_key(b"kft:token-sign:v1")


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_derive_key(b"kft:apikey-encrypt:v1")))


# ── Password hashing (PBKDF2-HMAC-SHA256) ──────────────────────────────────


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 320_000)
    return "pbkdf2_sha256$320000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_b64, digest_b64 = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ── Token (signed, versioned, expiring) ────────────────────────────────────


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": user["id"],
        "ver": int(user.get("token_version", 0)),
        "exp": int(time.time()) + settings.token_ttl_minutes * 60,
    }
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_token_key(), payload_b64.encode(), hashlib.sha256).digest()
    return payload_b64 + "." + _b64(sig)


def create_guest_token() -> str:
    """읽기전용 게스트 토큰. 마스터 계정 없이 시장 데이터 둘러보기용.
    민감 라우트(키/자동전략/주문/포트폴리오)는 require_auth가 거부한다."""
    payload = {
        "sub": 0,
        "guest": True,
        "exp": int(time.time()) + settings.token_ttl_minutes * 60,
    }
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_token_key(), payload_b64.encode(), hashlib.sha256).digest()
    return payload_b64 + "." + _b64(sig)


def read_token(token: str) -> dict[str, Any]:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        expected = hmac.new(_token_key(), payload_b64.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig_b64)):
            raise ValueError("bad signature")
        payload = json.loads(_unb64(payload_b64))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc


# ── Single local master account ────────────────────────────────────────────
# The app is a single-user local deployment. There is exactly one account row
# (the "master"). `email` is a fixed sentinel; only the password matters.

_MASTER_EMAIL = "local@kft"


def get_master() -> dict[str, Any] | None:
    with get_db() as con:
        row = con.execute(
            "SELECT id, email, password_hash, token_version, created_at FROM users ORDER BY id LIMIT 1"
        ).fetchone()
    return row_to_dict(row)


def is_initialized() -> bool:
    return get_master() is not None


def setup_master(password: str) -> dict[str, Any]:
    if is_initialized():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_initialized")
    with get_db() as con:
        cursor = con.execute(
            "INSERT INTO users(email, password_hash, token_version) VALUES(?, ?, 0)",
            (_MASTER_EMAIL, hash_password(password)),
        )
        user_id = cursor.lastrowid
    return {"id": user_id, "token_version": 0}


def verify_master(password: str) -> dict[str, Any] | None:
    master = get_master()
    if not master or not verify_password(password, master["password_hash"]):
        return None
    return master


def change_master(current_password: str, new_password: str) -> dict[str, Any]:
    master = verify_master(current_password)
    if not master:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    new_version = int(master.get("token_version", 0)) + 1
    with get_db() as con:
        con.execute(
            "UPDATE users SET password_hash = ?, token_version = ? WHERE id = ?",
            (hash_password(new_password), new_version, master["id"]),
        )
    return {"id": master["id"], "token_version": new_version}


def require_auth(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """Gate dependency: every protected route depends on this. Validates the
    bearer token signature, expiry, and that its version matches the current
    master row (so a password change / 'log out everywhere' invalidates old tokens)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login_required")
    payload = read_token(authorization.removeprefix("Bearer ").strip())
    master = get_master()
    if not master or master["id"] != payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    if int(master.get("token_version", 0)) != int(payload.get("ver", -1)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_revoked")
    return {"id": master["id"], "email": master["email"], "created_at": master.get("created_at")}


def require_view(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    """읽기전용 게이트: 마스터 토큰 또는 게스트 토큰을 허용한다.
    시장/뉴스/공시 등 안전한 GET 라우트에만 사용. 민감 라우트는 require_auth 유지."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login_required")
    payload = read_token(authorization.removeprefix("Bearer ").strip())
    if payload.get("guest"):
        return {"id": 0, "role": "guest"}
    master = get_master()
    if not master or master["id"] != payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    if int(master.get("token_version", 0)) != int(payload.get("ver", -1)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_revoked")
    return {"id": master["id"], "role": "master", "email": master["email"]}


# ── API key encryption + retrieval ─────────────────────────────────────────


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "..." + value[-4:]


def get_api_key(provider: str) -> str | None:
    """Return the user's stored (decrypted) key for a provider, falling back to
    an env-configured key. This is what makes in-app keys actually take effect."""
    provider = (provider or "").strip().lower()
    try:
        with get_db() as con:
            row = con.execute(
                "SELECT encrypted_value FROM api_keys WHERE lower(provider) = ? ORDER BY id DESC LIMIT 1",
                (provider,),
            ).fetchone()
        if row and row["encrypted_value"]:
            return decrypt_secret(row["encrypted_value"])
    except Exception:
        pass
    if provider == "gemini":
        return settings.gemini_api_key
    if provider == "dart":
        return settings.dart_api_key
    return None
