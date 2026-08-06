"""Loads the tracked-product catalog shared by fixture and live extraction.

Mirrors the "products" collection from the original bot's MongoDB, but as a
static, version-controlled file rather than a database table -- the catalog
is what we track, not something the pipeline itself observes.
"""

from __future__ import annotations

import json
from pathlib import Path

from inventory_pipeline.extractors.base import ProductRef
from inventory_pipeline.models import SourceName

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "products.json"


def load_catalog(path: Path | None = None) -> list[ProductRef]:
    catalog_path = path or DEFAULT_CATALOG_PATH
    raw = json.loads(catalog_path.read_text())
    return [
        ProductRef(
            id=item["id"],
            retailer=SourceName(item["retailer"]),
            retailer_product_id=item["retailer_product_id"],
            name=item["name"],
            url=item["url"],
            category=item.get("category"),
            store_id=item.get("store_id"),
        )
        for item in raw
    ]
