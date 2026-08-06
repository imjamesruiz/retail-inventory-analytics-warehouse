"""S3 raw storage backend -- optional, selected via RAW_STORAGE_BACKEND=s3."""

from __future__ import annotations

from functools import cached_property

import boto3
from botocore.exceptions import ClientError

from inventory_pipeline.storage.base import RawStorage


class S3RawStorage(RawStorage):
    def __init__(self, bucket: str, region: str) -> None:
        self.bucket = bucket
        self.region = region

    @cached_property
    def _client(self):  # noqa: ANN202 - boto3 client has no public type
        return boto3.client("s3", region_name=self.region)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as err:
            if err.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise

    def write_text(self, key: str, content: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=content.encode("utf-8"))

    def read_text(self, key: str) -> str:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys
