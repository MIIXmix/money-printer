from __future__ import annotations

import os
import secrets
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _resolve_path(env_var: str, default: Path) -> Path:
    """경로 환경변수를 절대경로로 해석한다.

    상대경로(.env가 'DATABASE_PATH=.data/...' 처럼 줄 때)는 실행 cwd가 아니라
    항상 BASE_DIR(저장소 루트) 기준으로 고정한다 — cwd에 따라 DB 파일이 갈리는 footgun 방지.
    """
    raw = os.getenv(env_var)
    p = Path(raw) if raw else default
    return p if p.is_absolute() else (BASE_DIR / p).resolve()


# Known weak/placeholder values that must never be used as a real secret.
_PLACEHOLDER_SECRETS = {
    "",
    "dev-only-change-me",
    "change-this-long-random-secret",
    "change-me",
    "changeme",
}


def _data_dir() -> Path:
    return _resolve_path("DATABASE_PATH", BASE_DIR / ".data" / "terminal.db").parent


def _restrict_permissions(path: Path) -> None:
    """Lock the secret file to the current user only (defense-in-depth on shared machines)."""
    try:
        if sys.platform == "win32":
            user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if user:
                # Remove inherited ACEs; grant full control to current user only.
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
                    check=False,
                    capture_output=True,
                )
        else:
            os.chmod(path, 0o600)
    except Exception:
        pass


def _load_or_create_secret() -> str:
    """Return a strong app secret.

    Priority:
    1. A non-placeholder APP_SECRET from the environment.
    2. An existing .data/secret.key file (generated on a previous run).
    3. A freshly generated 64-byte url-safe secret, persisted to .data/secret.key
       with owner-only permissions.

    This guarantees the app never ships with a known/guessable secret, which is
    what protects both the auth token signature and the API-key encryption.
    """
    env_secret = (os.getenv("APP_SECRET") or "").strip()
    if env_secret and env_secret not in _PLACEHOLDER_SECRETS:
        return env_secret

    secret_path = _data_dir() / "secret.key"
    try:
        if secret_path.exists():
            existing = secret_path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
    except Exception:
        pass

    secret = secrets.token_urlsafe(64)
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_text(secret, encoding="utf-8")
        _restrict_permissions(secret_path)
    except Exception:
        # If we cannot persist, still return a process-lifetime secret so the app
        # runs; tokens simply won't survive a restart in that degraded case.
        pass
    return secret


_APP_SECRET = _load_or_create_secret()


@dataclass(frozen=True)
class Settings:
    app_name: str = "Korean Finance Terminal"
    database_path: Path = _resolve_path("DATABASE_PATH", BASE_DIR / ".data" / "terminal.db")
    # Auto-generated strong secret (never a shipped placeholder).
    app_secret: str = _APP_SECRET
    token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "240"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
        if origin.strip()
    )
    # Optional fallback keys for power users; the primary path is per-user keys
    # entered in-app and stored encrypted in the DB.
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    dart_api_key: str | None = os.getenv("DART_API_KEY") or None
    sec_user_agent: str = os.getenv(
        "SEC_USER_AGENT",
        "KoreanFinanceTerminal/0.1 admin@example.com",
    )
    live_trading_enabled: bool = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    static_dir: Path = _resolve_path("STATIC_DIR", BASE_DIR / "dist")


settings = Settings()
