"""Normalization for the Walmart Affiliate API item response shape.

Ported from src/retailers/walmartClient.ts (mapWalmartStock).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from inventory_pipeline.extractors.base import ProductRef, compute_hash
from inventory_pipeline.models import InventoryEvent, InventoryStatus, LocationType, SourceName


def _map_stock(item: dict[str, Any]) -> InventoryStatus:
    if item.get("availableOnline") is True:
        return InventoryStatus.IN_STOCK
    if item.get("availableOnline") is False:
        return InventoryStatus.OUT_OF_STOCK
    stock = str(item.get("stock") or "").lower()
    if stock == "available":
        return InventoryStatus.IN_STOCK
    if stock in ("not available", "unavailable"):
        return InventoryStatus.OUT_OF_STOCK
    if stock == "preorder":
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
        raise ValueError(f"Walmart: empty response for item {product.retailer_product_id}")

    price = raw.get("salePrice", raw.get("msrp"))
    name = raw.get("name") or product.name

    return InventoryEvent.build(
        source=SourceName.WALMART,
        retailer_product_id=product.retailer_product_id,
        product_name=name,
        product_url=product.url,
        category=product.category,
        upc=raw.get("upc"),
        price=float(price) if price is not None else None,
        currency="USD",
        inventory_status=_map_stock(raw),
        location_type=LocationType.ONLINE,
        observed_at=observed_at,
        extracted_at=extracted_at,
        ingestion_run_id=ingestion_run_id,
        source_response_hash=compute_hash(raw),
    )
