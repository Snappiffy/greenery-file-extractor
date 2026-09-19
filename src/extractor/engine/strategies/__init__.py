"""Registro de estrategias."""

from __future__ import annotations

from extractor.engine.strategies.base import Strategy
from extractor.engine.strategies.columns import ColumnsStrategy
from extractor.engine.strategies.regex import RegexStrategy
from extractor.engine.strategies.ruling import RulingStrategy

STRATEGIES: dict[str, Strategy] = {
    "columns": ColumnsStrategy(),
    "ruling": RulingStrategy(),
    "regex": RegexStrategy(),
}


def get_strategy(name: str) -> Strategy:
    try:
        return STRATEGIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy: {name}") from exc
