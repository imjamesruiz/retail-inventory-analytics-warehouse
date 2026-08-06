import pytest

from inventory_pipeline.config import DataSourceMode, RawStorageBackend, Settings


def test_defaults_to_fixture_and_local(monkeypatch):
    monkeypatch.delenv("DATA_SOURCE_MODE", raising=False)
    monkeypatch.delenv("RAW_STORAGE_BACKEND", raising=False)
    settings = Settings(_env_file=None)
    assert settings.data_source_mode == DataSourceMode.FIXTURE
    assert settings.raw_storage_backend == RawStorageBackend.LOCAL


def test_s3_backend_requires_bucket():
    with pytest.raises(ValueError, match="S3_BUCKET"):
        Settings(_env_file=None, raw_storage_backend=RawStorageBackend.S3, s3_bucket=None)


def test_s3_backend_with_bucket_is_valid():
    settings = Settings(
        _env_file=None, raw_storage_backend=RawStorageBackend.S3, s3_bucket="my-bucket"
    )
    assert settings.s3_bucket == "my-bucket"


def test_require_snowflake_raises_with_missing_fields():
    settings = Settings(_env_file=None)
    with pytest.raises(ValueError, match="SNOWFLAKE_ACCOUNT"):
        settings.require_snowflake()


def test_require_snowflake_passes_with_password_auth():
    settings = Settings(
        _env_file=None,
        snowflake_account="abc123",
        snowflake_user="me",
        snowflake_password="secret",
    )
    settings.require_snowflake()  # should not raise


def test_require_live_credentials_walmart_missing_key():
    settings = Settings(_env_file=None)
    with pytest.raises(ValueError, match="WALMART_API_KEY"):
        settings.require_live_credentials("WALMART")
