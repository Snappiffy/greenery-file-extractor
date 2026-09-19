"""Tests del CLI de parse."""

from __future__ import annotations

import json

from extractor.cli import main


def test_cli_parse_price(capsys: object) -> None:
    code = main(["parse", "--parser", "price", "--text", "$12.50"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert out["value"] == "12.50"
    assert out["issues"] == []


def test_cli_parse_quantity_empty(capsys: object) -> None:
    code = main(["parse", "--parser", "quantity", "--text", ""])
    assert code == 0
    out = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert out["value"] is None
