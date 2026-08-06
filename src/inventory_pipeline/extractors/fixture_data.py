"""Deterministic fixture payload generators.

Each function builds a raw response shaped like the real retailer endpoint it
stands in for (see docs/architecture.md for the live equivalents), so the
normalization logic exercised in fixture mode is the same logic a live call
would hit. Payloads are seeded by (product id, day offset) so the same
simulated day always reproduces byte-identical output -- re-running a
backfill is idempotent, and reviewers without credentials can still see a
realistic multi-week history.
"""

from __future__ import annotations

import random
from datetime import date
from typing import Any

from inventory_pipeline.extractors.base import ProductRef

_STATUS_CYCLE = ["IN_STOCK", "IN_STOCK", "IN_STOCK", "OUT_OF_STOCK", "OUT_OF_STOCK", "PREORDER"]


def _rng(product: ProductRef, day_offset: int) -> random.Random:
    return random.Random(f"{product.id}:{day_offset}")


def _simulated_status(product: ProductRef, day_offset: int) -> str:
    rng = _rng(product, day_offset)
    return rng.choice(_STATUS_CYCLE)


def _simulated_price(product: ProductRef, day_offset: int, base_price: float) -> float:
    rng = _rng(product, day_offset)
    # Small deterministic drift, occasionally a markdown, never negative.
    drift = rng.choice([0, 0, 0, -5.0, -3.0, 2.0])
    return round(max(base_price + drift, 0.01), 2)


def target_payload(product: ProductRef, day_offset: int) -> dict[str, Any]:
    status = _simulated_status(product, day_offset)
    price = _simulated_price(product, day_offset, base_price=39.99)
    rng = _rng(product, day_offset)
    return {
        "data": {
            "product": {
                "item": {
                    "product_description": {"title": product.name},
                },
                "price": {"current_retail": price},
                "available_to_promise": {
                    "availability": status,
                    "available_to_promise_quantity": rng.randint(0, 25)
                    if status == "IN_STOCK"
                    else 0,
                },
                "tcin": product.retailer_product_id,
            }
        }
    }


def walmart_payload(product: ProductRef, day_offset: int) -> dict[str, Any]:
    status = _simulated_status(product, day_offset)
    price = _simulated_price(product, day_offset, base_price=49.88)
    return {
        "itemId": product.retailer_product_id,
        "name": product.name,
        "salePrice": price,
        "availableOnline": status == "IN_STOCK",
        "stock": "Available" if status == "IN_STOCK" else "Not available",
        "upc": f"0{abs(hash(product.id)) % 10**11:011d}",
    }


def pokemon_center_payload(product: ProductRef, day_offset: int) -> dict[str, Any]:
    status = _simulated_status(product, day_offset)
    price = _simulated_price(product, day_offset, base_price=44.99)
    return {
        "product": {
            "title": product.name,
            "handle": product.retailer_product_id,
            "variants": [
                {
                    "price": f"{price:.2f}",
                    "available": status == "IN_STOCK",
                    "sku": f"PC-{product.retailer_product_id[:8].upper()}",
                }
            ],
        }
    }


def gamestop_payload(product: ProductRef, day_offset: int) -> dict[str, Any]:
    status = _simulated_status(product, day_offset)
    price = _simulated_price(product, day_offset, base_price=59.99)
    return {
        "productName": product.name,
        "pricing": {"salePrice": price, "listPrice": price},
        "availability": {
            "isInStock": status == "IN_STOCK",
            "isPreOrder": status == "PREORDER",
        },
        "sku": product.retailer_product_id,
    }


PAYLOAD_BUILDERS = {
    "TARGET": target_payload,
    "WALMART": walmart_payload,
    "POKEMON_CENTER": pokemon_center_payload,
    "GAMESTOP": gamestop_payload,
}


def day_offset_from_date(observed_at: date, anchor: date) -> int:
    """Stable integer seed component so a given calendar day always yields the same payload."""
    return (anchor - observed_at).days
