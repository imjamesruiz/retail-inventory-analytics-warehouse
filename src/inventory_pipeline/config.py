"""Application configuration, loaded from environment variables / .env.

Validated eagerly at startup so misconfiguration fails fast with a clear
message instead of surfacing as an obscure error mid-pipeline.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataSourceMode(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"


class RawStorageBackend(StrEnum):
    LOCAL = "local"
    S3 = "s3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Data source
    data_source_mode: DataSourceMode = DataSourceMode.FIXTURE

    # Raw storage
    raw_storage_backend: RawStorageBackend = RawStorageBackend.LOCAL
    raw_data_path: str = "./data/raw"

    # AWS / S3 (only required when raw_storage_backend == s3)
    aws_region: str = "us-east-1"
    s3_bucket: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Retailer live-mode credentials
    walmart_api_key: str | None = None
    target_store_id: str = "3991"

    # Snowflake
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_private_key_path: str | None = None
    snowflake_role: str = "RETAIL_INVENTORY_ROLE"
    snowflake_warehouse: str = "RETAIL_INVENTORY_WH"
    snowflake_database: str = "RETAIL_INVENTORY"
    snowflake_schema: str = "RAW"
    # dbt's target schema (see dbt_inventory/profiles.yml); dbt appends
    # _staging/_intermediate/_marts/_seeds per layer via custom schema naming.
    snowflake_schema_analytics: str = "ANALYTICS"

    # App
    log_level: str = "INFO"
    pipeline_version: str = "0.1.0"

    @model_validator(mode="after")
    def validate_storage_requirements(self) -> Settings:
        if self.raw_storage_backend == RawStorageBackend.S3 and not self.s3_bucket:
            raise ValueError(
                "S3_BUCKET is required when RAW_STORAGE_BACKEND=s3. "
                "Set it in .env or switch RAW_STORAGE_BACKEND=local."
            )
        return self

    def require_snowflake(self) -> None:
        """Call before any Snowflake operation; raises with a clear, actionable message."""
        missing = []
        if not self.snowflake_account:
            missing.append("SNOWFLAKE_ACCOUNT")
        if not self.snowflake_user:
            missing.append("SNOWFLAKE_USER")
        if not self.snowflake_password and not self.snowflake_private_key_path:
            missing.append("SNOWFLAKE_PASSWORD or SNOWFLAKE_PRIVATE_KEY_PATH")
        if missing:
            raise ValueError(
                f"Missing required Snowflake configuration: {', '.join(missing)}. "
                "See .env.example and docs/architecture.md for setup steps."
            )

    def require_live_credentials(self, source: str) -> None:
        """Call before a live-mode extractor runs; raises with a clear, actionable message."""
        if source == "WALMART" and not self.walmart_api_key:
            raise ValueError(
                "WALMART_API_KEY is required for live mode. "
                "Register at https://developer.walmart.com/ and set it in .env, "
                "or set DATA_SOURCE_MODE=fixture."
            )

    def raw_data_dir(self) -> Path:
        return Path(self.raw_data_path)


def get_settings() -> Settings:
    """Load settings fresh from the environment. Not cached, so tests can reload per-case."""
    return Settings()
