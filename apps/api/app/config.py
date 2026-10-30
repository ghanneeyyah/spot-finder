import re
from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.database import normalize_database_url

_ORIGIN = re.compile(r"^https?://[^/\s]+$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str
    # Comma-separated in the environment: CORS_ORIGINS=https://a.com,https://b.com
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    firebase_project_id: str | None = None
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: SecretStr | None = None
    cloudinary_api_secret: SecretStr | None = None
    # Number of trusted reverse proxies in front of the API (Railway = 1). 0 ignores
    # X-Forwarded-For entirely, which is the only safe default when no proxy is trusted.
    trusted_proxy_count: int = Field(default=0, ge=0, le=5)
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    log_level: str = "INFO"
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    write_rate_limit_per_minute: int = Field(default=60, ge=1)

    @field_validator("database_url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip().rstrip("/") for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _validate(self) -> Self:
        for origin in self.cors_origins:
            if origin == "*" or not _ORIGIN.match(origin):
                raise ValueError(f"CORS origin {origin!r} must be an explicit origin, never '*'")
        if self.environment == "production":
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must be set in production")
            if any(not o.startswith("https://") for o in self.cors_origins):
                raise ValueError("CORS origins must use https in production")
            missing = [
                name
                for name, value in {
                    "FIREBASE_PROJECT_ID": self.firebase_project_id,
                    "CLOUDINARY_CLOUD_NAME": self.cloudinary_cloud_name,
                    "CLOUDINARY_API_KEY": self.cloudinary_api_key,
                    "CLOUDINARY_API_SECRET": self.cloudinary_api_secret,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
