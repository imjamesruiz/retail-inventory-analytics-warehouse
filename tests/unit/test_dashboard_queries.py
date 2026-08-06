"""Tests for dashboard/queries.py's SQL-building helpers.

dashboard/ isn't part of the installed package (Streamlit apps add their own
script directory to sys.path at runtime), so it's added here explicitly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dashboard"))

from queries import _in_clause  # noqa: E402


def test_in_clause_uses_one_placeholder_per_value():
    """Regression test: binding a Python tuple straight to a single
    %(name)s placeholder does not produce a SQL IN-list with the Snowflake
    connector -- it binds the whole tuple as one malformed value and the
    query fails with a syntax error. Each value needs its own placeholder."""
    clause, params = _in_clause("source", ["TARGET", "WALMART"], "retailer")

    assert clause == "source in (%(retailer_0)s, %(retailer_1)s)"
    assert params == {"retailer_0": "TARGET", "retailer_1": "WALMART"}


def test_in_clause_single_value():
    clause, params = _in_clause("source", ["GAMESTOP"], "retailer")

    assert clause == "source in (%(retailer_0)s)"
    assert params == {"retailer_0": "GAMESTOP"}


def test_in_clause_preserves_value_order():
    _, params = _in_clause("product_key", ["c", "a", "b"], "product")

    assert [params[f"product_{i}"] for i in range(3)] == ["c", "a", "b"]
