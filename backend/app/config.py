"""Typed settings loaded from environment variables (spec §4).

The app refuses to start if a required variable is missing or invalid.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "test", "production"]
    APP_NAME: str = "DevCommons"
    SECRET_KEY: str = Field(min_length=16)
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    CORS_ORIGINS: Annotated[list[str], NoDecode]

    # Auth / JWT
    JWT_SIGNING_KEYS: Annotated[dict[str, str], NoDecode]
    JWT_ACTIVE_KID: str
    JWT_ISSUER: str = "devcommons-api"
    JWT_AUDIENCE: str = "devcommons-web"
    ACCESS_TOKEN_TTL_SECONDS: int = 900
    REFRESH_TOKEN_TTL_DAYS: int = 30
    SESSION_MAX_AGE_DAYS: int = 90
    REFRESH_COOKIE_NAME: str = "dc_refresh"
    COOKIE_SECURE: bool = True
    FRONTEND_URL: str

    # Email
    EMAIL_PROVIDER: Literal["console", "smtp"] = "console"
    EMAIL_FROM: str = "DevCommons <no-reply@localhost>"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    # starttls (port 587), ssl (port 465), or none (local test servers only)
    SMTP_SECURITY: Literal["starttls", "ssl", "none"] = "starttls"
    SMTP_TIMEOUT_SECONDS: float = 15

    # Sign in with GitHub / Google (OAuth 2.0 authorization code + PKCE). A provider is enabled when
    # both its client ID and secret are set.
    API_PUBLIC_URL: str = "http://localhost:5001"
    GITHUB_OAUTH_CLIENT_ID: str | None = None
    GITHUB_OAUTH_CLIENT_SECRET: SecretStr | None = None
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr | None = None

    # AI
    AI_ENABLED: bool = True
    AI_PROVIDER: Literal["openai", "fake"] = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str | None = None
    OPENAI_FALLBACK_MODEL: str | None = None
    OPENAI_TIMEOUT_SECONDS: float = 60
    AI_MODEL_LABEL: str = "GPT-6"
    AI_PRICING_JSON: Annotated[dict[str, dict[str, float]], NoDecode] = Field(default_factory=dict)
    AI_DAILY_TOKEN_LIMIT: int = 200_000
    AI_DAILY_GENERATION_LIMIT: int = 30
    AI_MONTHLY_BUDGET_USD: float = 100
    AI_MAX_INPUT_CHARS: int = 8000
    AI_MAX_OUTPUT_TOKENS_CHAT: int = 2000
    AI_MAX_OUTPUT_TOKENS_GENERATION: int = 4000
    AI_STREAM_MAX_SECONDS: int = 90

    # Integrations
    GITHUB_TOKEN: str | None = None

    # Infra
    RATELIMIT_STORAGE_URI: str = "memory://"
    RATELIMIT_ENABLED: bool = True
    TRUST_PROXY_HOPS: int = 0
    JOB_SECRET: str = Field(min_length=16)
    SENTRY_DSN: str | None = None
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            items = [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        else:
            items = list(v)
        if not items or "*" in items:
            raise ValueError("CORS_ORIGINS must be an explicit, non-empty list of origins (never '*').")
        return items

    @field_validator("JWT_SIGNING_KEYS", "AI_PRICING_JSON", mode="before")
    @classmethod
    def _parse_json(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return json.loads(v) if v else {}
        return v

    @field_validator("JWT_SIGNING_KEYS")
    @classmethod
    def _check_keys(cls, v: dict[str, str]) -> dict[str, str]:
        if not v:
            raise ValueError("JWT_SIGNING_KEYS must contain at least one key.")
        for kid, secret in v.items():
            raw: bytes
            try:
                raw = base64.b64decode(secret, validate=True)
            except Exception:
                raw = secret.encode()
            if len(raw) < 32:
                raise ValueError(f"JWT signing key '{kid}' must be at least 32 bytes.")
        return v

    @model_validator(mode="after")
    def _cross_checks(self) -> Settings:
        if self.JWT_ACTIVE_KID not in self.JWT_SIGNING_KEYS:
            raise ValueError("JWT_ACTIVE_KID must be one of the keys in JWT_SIGNING_KEYS.")
        if self.APP_ENV == "production":
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be true in production.")
        if self.EMAIL_PROVIDER == "smtp":
            if not self.SMTP_HOST:
                raise ValueError("SMTP_HOST is required when EMAIL_PROVIDER=smtp.")
            if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD and self.SMTP_PASSWORD.get_secret_value()):
                raise ValueError("Set both SMTP_USERNAME and SMTP_PASSWORD, or neither.")
            if self.APP_ENV == "production" and self.SMTP_SECURITY == "none":
                raise ValueError("SMTP_SECURITY=none is not allowed in production.")
        for name in ("GITHUB", "GOOGLE"):
            cid = getattr(self, f"{name}_OAUTH_CLIENT_ID")
            secret = getattr(self, f"{name}_OAUTH_CLIENT_SECRET")
            if bool(cid) != bool(secret and secret.get_secret_value()):
                raise ValueError(f"Set both {name}_OAUTH_CLIENT_ID and {name}_OAUTH_CLIENT_SECRET, or neither.")
        if self.AI_ENABLED and self.AI_PROVIDER == "openai":
            missing = [k for k in ("OPENAI_API_KEY", "OPENAI_MODEL") if not getattr(self, k)]
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} required when AI_ENABLED=true (or set AI_PROVIDER=fake / AI_ENABLED=false)."
                )
        if not self.DATABASE_URL.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg://...).")
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    def signing_key(self, kid: str) -> bytes | None:
        secret = self.JWT_SIGNING_KEYS.get(kid)
        if secret is None:
            return None
        return secret.encode()

    @property
    def ai_model(self) -> str:
        return self.OPENAI_MODEL or "fake-model"


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
