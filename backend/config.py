"""Runtime configuration.

Values come from environment variables prefixed ``FINGUARD_``. The development
identity stub is only permitted in ``development`` and ``test`` environments;
any other environment refuses to start with it enabled (see ADR README).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]

_STUB_ALLOWED: frozenset[str] = frozenset({"development", "test"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINGUARD_", env_file=".env", extra="ignore")

    env: Environment = "development"
    database_url: str = "sqlite:///var/finguard.sqlite3"
    # Owner credentials for migrations/seeding; the runtime URL must not own tables.
    database_admin_url: str | None = None
    object_store_path: Path = Path("var/objects")

    # Identity
    dev_identity_enabled: bool = True
    oidc_issuer: str | None = None
    oidc_audience: str | None = None

    # Uploads and object grants
    object_grant_secret: str = "dev-object-grant-secret"
    object_grant_ttl_seconds: int = Field(default=300, gt=0, le=3600)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    allowed_media_types: tuple[str, ...] = (
        "application/pdf",
        "text/csv",
        "text/plain",
        "image/png",
        "image/jpeg",
    )

    # AI and providers
    model_provider: Literal["fake", "bedrock"] = "fake"
    bedrock_model_id: str | None = None
    bedrock_guardrail_id: str | None = None
    bedrock_guardrail_version: str | None = None
    bedrock_region: str = "ap-south-1"
    model_timeout_seconds: float = 30.0
    model_max_input_chars: int = 40_000

    # Field-level encryption for restricted data (beneficiary account numbers).
    field_encryption_key: str = "dev-field-key-0123456789abcdef0123456789abcdef"

    # Payment simulator / webhooks
    simulator_webhook_secret: str = "dev-simulator-secret"

    # Jobs
    job_lease_seconds: int = 60
    job_max_attempts: int = 5

    # CORS for the web app
    web_origin: str = "http://localhost:3000"

    @model_validator(mode="after")
    def _guard_dev_identity(self) -> Settings:
        if self.dev_identity_enabled and self.env not in _STUB_ALLOWED:
            raise ValueError(
                "The development identity stub cannot be enabled in "
                f"'{self.env}'. Configure OIDC instead."
            )
        if self.env in ("staging", "production"):
            for name in ("simulator_webhook_secret", "object_grant_secret", "field_encryption_key"):
                if getattr(self, name).startswith("dev-"):
                    raise ValueError(f"Set FINGUARD_{name.upper()} outside development.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
