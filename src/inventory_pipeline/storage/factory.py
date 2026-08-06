"""Selects a raw storage backend based on Settings.raw_storage_backend."""

from __future__ import annotations

from inventory_pipeline.config import RawStorageBackend, Settings
from inventory_pipeline.storage.base import RawStorage
from inventory_pipeline.storage.local import LocalRawStorage
from inventory_pipeline.storage.s3 import S3RawStorage


def get_storage(settings: Settings) -> RawStorage:
    if settings.raw_storage_backend == RawStorageBackend.S3:
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET must be set when RAW_STORAGE_BACKEND=s3")
        return S3RawStorage(bucket=settings.s3_bucket, region=settings.aws_region)
    return LocalRawStorage(base_dir=settings.raw_data_dir())
