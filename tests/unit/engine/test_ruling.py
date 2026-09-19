"""Tests unitarios de la estrategia ruling."""

from __future__ import annotations

from extractor.domain.profile import Profile
from extractor.engine.strategies.ruling import RulingStrategy


def test_ruling_cut_tables_maps_indexes() -> None:
    profile = Profile.from_payload(
        {
            "schema_version": 1,
            "version": 1,
            "document": {"kind": "pdf", "pages": "all"},
            "table": {
                "strategy": "ruling",
                "ruling": {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3.0,
                },
                "multiline": {"enabled": False},
            },
            "columns": [
                {"role": "grower_code", "index": 0},
                {"role": "plant_name", "index": 1, "required": True},
                {"role": "size", "index": 2, "required": True},
                {"role": "price", "index": 3},
            ],
        }
    )
    tables = [
        [
            ["CODE", "Item", "SIZE", "PRICE"],
            ["A-1", "Ficus lyrata", '10"', "$42.50"],
        ]
    ]
    rows = RulingStrategy().cut_tables(tables, profile)
    assert len(rows) == 2
    cells, issues, joined = rows[1]
    assert issues == []
    assert joined == 'A-1 Ficus lyrata 10" $42.50'
    by_role = {cell.role: cell.raw for cell in cells}
    assert by_role["grower_code"] == "A-1"
    assert by_role["plant_name"] == "Ficus lyrata"
    assert by_role["size"] == '10"'
    assert by_role["price"] == "$42.50"
