"""Common extractor contract every data source implements.

Every extractor: takes a catalog of tracked products, fetches one raw
payload per product (from fixtures or a live endpoint), and normalizes each
payload into an InventoryEvent. Malformed payloads become RejectedRecord
entries instead of being silently dropped.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from inventory_pipeline.logging_config import get_logger
from inventory_pipeline.models import InventoryEvent, RejectedRecord, SourceName, hash_payload

logger = get_logger()


@dataclass(frozen=True)
class ProductRef:
    """A tracked product from the catalog, independent of which mode fetched it."""

    id: str
    retailer: SourceName
    retailer_product_id: str
    name: str
    url: str
    category: str | None = None
    store_id: str | None = None


@dataclass
class SourcePayload:
    """One raw response, still unvalidated, paired with the product it answers for."""

    product: ProductRef
    raw: dict[str, Any]
    observed_at: datetime


@dataclass
class ExtractionResult:
    source: SourceName
    events: list[InventoryEvent] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)
    raw_payloads: list[SourcePayload] = field(default_factory=list)

    @property
    def payloads_received(self) -> int:
        return len(self.raw_payloads)


class BaseExtractor(ABC):
    source: SourceName

    def __init__(self, ingestion_run_id: str) -> None:
        self.ingestion_run_id = ingestion_run_id

    @abstractmethod
    def fetch_payloads(self, products: list[ProductRef]) -> list[SourcePayload]:
        """Retrieve one raw payload per product. Must not raise on a single product's
        failure — log and skip it so the rest of the batch still completes."""
        raise NotImplementedError

    @abstractmethod
    def normalize_payload(self, payload: SourcePayload) -> InventoryEvent:
        """Turn one raw payload into a canonical InventoryEvent. Raise ValueError (or a
        subclass) on malformed input; the caller converts that into a RejectedRecord."""
        raise NotImplementedError

    def extract(self, products: list[ProductRef]) -> ExtractionResult:
        products = [p for p in products if p.retailer == self.source]
        result = ExtractionResult(source=self.source)

        result.raw_payloads = self.fetch_payloads(products)

        for payload in result.raw_payloads:
            try:
                event = self.normalize_payload(payload)
                result.events.append(event)
            except Exception as err:  # noqa: BLE001 - malformed input, not a bug
                logger.warning(
                    "normalization_rejected",
                    source=self.source.value,
                    retailer_product_id=payload.product.retailer_product_id,
                    reason=str(err),
                )
                result.rejected.append(
                    RejectedRecord(
                        source=self.source,
                        reason=str(err),
                        retailer_product_id=payload.product.retailer_product_id,
                        raw_excerpt=_safe_excerpt(payload.raw),
                    )
                )

        logger.info(
            "extraction_completed",
            source=self.source.value,
            payloads_received=result.payloads_received,
            events_normalized=len(result.events),
            events_rejected=len(result.rejected),
        )
        return result


def _safe_excerpt(raw: dict[str, Any], max_len: int = 300) -> str:
    """Truncated, non-sensitive fragment of a payload for debugging rejected records."""
    text = str({k: raw[k] for k in list(raw)[:5]})
    return text[:max_len]


def compute_hash(raw: dict[str, Any]) -> str:
    return hash_payload(raw)
