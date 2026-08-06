"""Extractor factory, mirroring src/retailers/retailerFactory.ts."""

from __future__ import annotations

from datetime import datetime

from inventory_pipeline.config import Settings
from inventory_pipeline.extractors.base import BaseExtractor
from inventory_pipeline.extractors.gamestop import GamestopExtractor
from inventory_pipeline.extractors.pokemon_center import PokemonCenterExtractor
from inventory_pipeline.extractors.target import TargetExtractor
from inventory_pipeline.extractors.walmart import WalmartExtractor
from inventory_pipeline.models import SourceName

_EXTRACTOR_CLASSES = {
    SourceName.TARGET: TargetExtractor,
    SourceName.WALMART: WalmartExtractor,
    SourceName.POKEMON_CENTER: PokemonCenterExtractor,
    SourceName.GAMESTOP: GamestopExtractor,
}


def get_extractor(
    source: SourceName,
    *,
    ingestion_run_id: str,
    settings: Settings,
    observed_at: datetime,
    day_offset: int = 0,
) -> BaseExtractor:
    extractor_cls = _EXTRACTOR_CLASSES.get(source)
    if extractor_cls is None:
        raise ValueError(f"No extractor registered for source: {source}")
    return extractor_cls(
        ingestion_run_id=ingestion_run_id,
        settings=settings,
        observed_at=observed_at,
        day_offset=day_offset,
    )


def all_sources() -> list[SourceName]:
    return list(_EXTRACTOR_CLASSES.keys())
