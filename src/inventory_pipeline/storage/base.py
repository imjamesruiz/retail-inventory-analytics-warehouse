"""Append-only raw storage layer.

Every extraction run writes three artifacts under a partitioned prefix:

    raw/source=<source>/year=<YYYY>/month=<MM>/day=<DD>/run_id=<UUID>/
        raw_payloads.ndjson       -- unmodified source responses
        normalized_events.ndjson  -- canonical InventoryEvent records
        manifest.json             -- run metadata

Raw payloads are never overwritten: writing to a prefix that already has a
raw_payloads.ndjson raises, because each run_id is a new, immutable fact.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from inventory_pipeline.extractors.base import SourcePayload
from inventory_pipeline.models import IngestionManifest, InventoryEvent, RejectedRecord, hash_text


@dataclass(frozen=True)
class RawStorageLocation:
    raw_payload_path: str
    normalized_output_path: str
    manifest_path: str


class RawStorage(ABC):
    """Backend-agnostic key/value writer; local filesystem and S3 both implement this."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def write_text(self, key: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_text(self, key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]:
        """List all keys under a prefix, used by the Snowflake loader to discover
        runs and by metrics reporting -- not used on the write path."""
        raise NotImplementedError

    @staticmethod
    def partition_prefix(source: str, observed_at: datetime, run_id: str) -> str:
        return (
            f"raw/source={source}/year={observed_at:%Y}/month={observed_at:%m}/"
            f"day={observed_at:%d}/run_id={run_id}"
        )

    def write_run(
        self,
        *,
        source: str,
        run_id: str,
        observed_at: datetime,
        raw_payloads: list[SourcePayload],
        events: list[InventoryEvent],
        rejected: list[RejectedRecord],
        manifest: IngestionManifest,
    ) -> RawStorageLocation:
        prefix = self.partition_prefix(source, observed_at, run_id)

        raw_key = f"{prefix}/raw_payloads.ndjson"
        if self.exists(raw_key):
            raise FileExistsError(
                f"Raw payload already exists at {raw_key}; refusing to overwrite immutable "
                "raw data. Each ingestion run must use a fresh run_id."
            )

        raw_lines = [
            json.dumps(
                {
                    "retailer_product_id": p.product.retailer_product_id,
                    "observed_at": p.observed_at.isoformat(),
                    "raw_response": p.raw,
                }
            )
            for p in raw_payloads
        ]
        raw_content = "\n".join(raw_lines)
        self.write_text(raw_key, raw_content)

        norm_key = f"{prefix}/normalized_events.ndjson"
        norm_content = "\n".join(event.model_dump_json() for event in events)
        self.write_text(norm_key, norm_content)

        rejected_key = f"{prefix}/rejected_records.ndjson"
        if rejected:
            rejected_content = "\n".join(r.model_dump_json() for r in rejected)
            self.write_text(rejected_key, rejected_content)

        manifest.raw_payload_path = raw_key
        manifest.normalized_output_path = norm_key
        manifest.content_hashes = {
            "raw_payloads": hash_text(raw_content),
            "normalized_events": hash_text(norm_content),
        }

        manifest_key = f"{prefix}/manifest.json"
        manifest.manifest_path = manifest_key
        self.write_text(manifest_key, manifest.model_dump_json(indent=2))

        return RawStorageLocation(
            raw_payload_path=raw_key,
            normalized_output_path=norm_key,
            manifest_path=manifest_key,
        )
