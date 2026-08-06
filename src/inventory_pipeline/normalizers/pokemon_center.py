"""Normalization for Pokemon Center's public Shopify storefront product.json.

Ported from src/retailers/pokemonCenterClient.ts (mapShopifyAvailability).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from inventory_pipeline.extractors.base import ProductRef, compute_hash
from inventory_pipeline.models import InventoryEvent, InventoryStatus, LocationType, SourceName


def _map_availability(available: bool | None) -> InventoryStatus:
    if available is True:
        return InventoryStatus.IN_STOCK
    if available is False:
        return InventoryStatus.OUT_OF_STOCK
    return InventoryStatus.UNKNOWN


def normalize(
    raw: dict[str, Any],
    product: ProductRef,
    *,
    ingestion_run_id: str,
    observed_at: datetime,
    extracted_at: datetime,
) -> InventoryEvent:
    shopify_product = raw.get("product")
    if not shopify_product:
        raise ValueError(f"PokemonCenter: no product data for handle {product.retailer_product_id}")

    variants = shopify_product.get("variants") or []
    first_variant = variants[0] if variants else {}
    price = first_variant.get("price")
    name = shopify_product.get("title") or product.name

    return InventoryEvent.build(
        source=SourceName.POKEMON_CENTER,
        retailer_product_id=product.retailer_product_id,
        product_name=name,
        product_url=product.url,
        category=product.category,
        sku=first_variant.get("sku"),
        price=float(price) if price is not None else None,
        currency="USD",
        inventory_status=_map_availability(first_variant.get("available")),
        location_type=LocationType.ONLINE,
        observed_at=observed_at,
        extracted_at=extracted_at,
        ingestion_run_id=ingestion_run_id,
        source_response_hash=compute_hash(raw),
    )
