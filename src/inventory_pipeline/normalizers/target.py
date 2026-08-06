"""Normalization for Target's product-detail response shape.

Ported from the original bot's src/retailers/targetClient.ts (mapAvailability
and the price/quantity extraction), translated to Python.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from inventory_pipeline.extractors.base import ProductRef, compute_hash
from inventory_pipeline.models import InventoryEvent, InventoryStatus, LocationType, SourceName


def _map_availability(status: str | None) -> InventoryStatus:
    if not status:
        return InventoryStatus.UNKNOWN
    s = status.upper()
    if s in ("AVAILABLE", "IN_STOCK"):
        return InventoryStatus.IN_STOCK
    if s in ("UNAVAILABLE", "OUT_OF_STOCK", "NOT_AVAILABLE"):
        return InventoryStatus.OUT_OF_STOCK
    if s == "PREORDER":
        return InventoryStatus.PREORDER
    if s == "BACKORDER":
        return InventoryStatus.BACKORDER
    return InventoryStatus.UNKNOWN


def normalize(
    raw: dict[str, Any],
    product: ProductRef,
    *,
    ingestion_run_id: str,
    observed_at: datetime,
    extracted_at: datetime,
) -> InventoryEvent:
    p = (raw.get("data") or {}).get("product")
    if not p:
        raise ValueError(f"Target: no product data for TCIN {product.retailer_product_id}")

    price = (p.get("price") or {}).get("current_retail")
    atp = p.get("available_to_promise") or {}
    quantity = atp.get("available_to_promise_quantity")
    name = ((p.get("item") or {}).get("product_description") or {}).get("title") or product.name

    return InventoryEvent.build(
        source=SourceName.TARGET,
        retailer_product_id=product.retailer_product_id,
        product_name=name,
        product_url=product.url,
        category=product.category,
        price=float(price) if price is not None else None,
        currency="USD",
        inventory_status=_map_availability(atp.get("availability")),
        quantity_available=int(quantity) if quantity is not None else None,
        store_id=product.store_id,
        location_type=LocationType.ONLINE,
        observed_at=observed_at,
        extracted_at=extracted_at,
        ingestion_run_id=ingestion_run_id,
        source_response_hash=compute_hash(raw),
    )
