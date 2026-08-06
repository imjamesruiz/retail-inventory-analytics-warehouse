"""Shared chart styling. A fixed, colorblind-safe categorical palette (Okabe-
Ito) assigned once per retailer and never re-cycled, plus reserved status
colors for restock/stock-out so they're never reused as a 5th series color."""

from __future__ import annotations

RETAILER_COLORS: dict[str, str] = {
    "TARGET": "#0072B2",
    "WALMART": "#E69F00",
    "POKEMON_CENTER": "#56B4E9",
    "GAMESTOP": "#CC79A7",
}

STATUS_COLORS: dict[str, str] = {
    "restocked": "#009E73",
    "went_out_of_stock": "#D55E00",
}

SEQUENTIAL_SCALE = "Blues"


def color_for_retailer(source: str) -> str:
    return RETAILER_COLORS.get(source, "#8C8C8C")
