"""Normalization for GameStop's internal product-detail endpoint shape.

Ported from src/retailers/gamestopClient.ts (mapGameStopStock). Fixture-only:
see docs/decisions.md for why this source has no live extractor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from inventory_pipeline.extractors.base import ProductRef, compute_hash
from inventory_pipeline.models import InventoryEvent, InventoryStatus, LocationType, SourceName


def _map_stock(data: dict[str, Any]) -> InventoryStatus:
    availability = data.get("availability") or {}
    if availability.get("isInStock") is True:
        return InventoryStatus.IN_STOCK
    if availability.get("isInStock") is False:
        return InventoryStatus.OUT_OF_STOCK
    if availability.get("isPreOrder") is True:
        return InventoryStatus.PREORDER
    return InventoryStatus.UNKNOWN


def normalize(
    raw: dict[str, Any],
    product: ProductRef,
    *,
    ingestion_run_id: str,
    observed_at: datetime,
    extracted_at: datetime,
) -> InventoryEvent:
    if not raw:
        raise ValueError(f"GameStop: empty response for SKU {product.retailer_product_id}")

    pricing = raw.get("pricing") or {}
    price = pricing.get("salePrice", pricing.get("listPrice"))
    name = raw.get("productName") or product.name

    return InventoryEvent.build(
        source=SourceName.GAMESTOP,
        retailer_product_id=product.retailer_product_id,
        product_name=name,
        product_url=product.url,
        category=product.category,
        sku=raw.get("sku"),
        price=float(price) if price is not None else None,
        currency="USD",
        inventory_status=_map_stock(raw),
        location_type=LocationType.ONLINE,
        observed_at=observed_at,
        extracted_at=extracted_at,
        ingestion_run_id=ingestion_run_id,
        source_response_hash=compute_hash(raw),
    )
