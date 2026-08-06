"""Canonical data models for the inventory pipeline.

InventoryEvent is the normalized shape every extractor must produce,
regardless of which retailer or fixture the data came from.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = "1.0"

# Fixed namespace so event_id generation is stable across processes and runs.
_EVENT_ID_NAMESPACE = uuid.UUID("6f8f2c2e-9b1d-4b1a-9b3a-1f7d9e6a0c11")


class SourceName(StrEnum):
    TARGET = "TARGET"
    WALMART = "WALMART"
    POKEMON_CENTER = "POKEMON_CENTER"
    GAMESTOP = "GAMESTOP"


class InventoryStatus(StrEnum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PREORDER = "PREORDER"
    BACKORDER = "BACKORDER"
    UNKNOWN = "UNKNOWN"


class LocationType(StrEnum):
    ONLINE = "ONLINE"
    IN_STORE = "IN_STORE"
    UNKNOWN = "UNKNOWN"


def utcnow() -> datetime:
    return datetime.now(UTC)


def make_event_id(source: str, retailer_product_id: str, observed_at: datetime) -> str:
    """Deterministic UUID5 so re-ingesting the same observation yields the same ID.

    Two extraction runs over the same (source, product, observed_at) triple are
    treated as the same event, which is what makes Snowflake loads idempotent.
    """
    key = f"{source}:{retailer_product_id}:{observed_at.astimezone(UTC).isoformat()}"
    return str(uuid.uuid5(_EVENT_ID_NAMESPACE, key))


def hash_payload(payload: Any) -> str:
    """Stable hash of a raw source response, used for change detection and dedup."""
    import json

    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_text(content: str) -> str:
    """Hash of already-serialized text, used for manifest content_hashes."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class InventoryEvent(BaseModel):
    """A single normalized inventory/pricing observation for one product at one point in time."""

    event_id: str
    source: SourceName
    retailer_product_id: str
    product_name: str
    product_url: str
    sku: str | None = None
    upc: str | None = None
    category: str | None = None

    price: float | None = None
    currency: str = "USD"

    inventory_status: InventoryStatus
    quantity_available: int | None = None

    store_id: str | None = None
    location_type: LocationType = LocationType.ONLINE

    observed_at: datetime
    extracted_at: datetime
    ingestion_run_id: str

    raw_file_path: str | None = None
    source_response_hash: str
    schema_version: str = SCHEMA_VERSION

    @field_validator("price")
    @classmethod
    def price_not_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("price must not be negative")
        return v

    @field_validator("quantity_available")
    @classmethod
    def quantity_not_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("quantity_available must not be negative")
        return v

    @field_validator("observed_at", "extracted_at")
    @classmethod
    def timestamp_is_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @classmethod
    def build(
        cls,
        *,
        source: SourceName,
        retailer_product_id: str,
        product_name: str,
        product_url: str,
        inventory_status: InventoryStatus,
        observed_at: datetime,
        ingestion_run_id: str,
        source_response_hash: str,
        extracted_at: datetime | None = None,
        **kwargs: Any,
    ) -> InventoryEvent:
        """Construct an event, deriving the deterministic event_id from its identity fields."""
        event_id = make_event_id(source.value, retailer_product_id, observed_at)
        return cls(
            event_id=event_id,
            source=source,
            retailer_product_id=retailer_product_id,
            product_name=product_name,
            product_url=product_url,
            inventory_status=inventory_status,
            observed_at=observed_at,
            extracted_at=extracted_at or utcnow(),
            ingestion_run_id=ingestion_run_id,
            source_response_hash=source_response_hash,
            **kwargs,
        )


class RejectedRecord(BaseModel):
    """A source payload that failed normalization, kept for diagnosis without leaking secrets."""

    source: SourceName
    reason: str
    retailer_product_id: str | None = None
    raw_excerpt: str | None = Field(
        default=None, description="Truncated, non-sensitive fragment of the offending payload"
    )
    occurred_at: datetime = Field(default_factory=utcnow)


class RunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"


class IngestionManifest(BaseModel):
    """Metadata describing one extraction run, written alongside its raw output."""

    run_id: str
    source: SourceName
    observed_at: datetime
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus = RunStatus.SUCCESS

    payloads_received: int = 0
    events_normalized: int = 0
    events_rejected: int = 0

    raw_payload_path: str | None = None
    normalized_output_path: str | None = None
    manifest_path: str | None = None

    content_hashes: dict[str, str] = Field(default_factory=dict)
    error_summary: list[str] = Field(default_factory=list)
    pipeline_version: str = "0.1.0"
