"""Registro de estrategias."""

from __future__ import annotations

from extractor.engine.strategies.base import Strategy
from extractor.engine.strategies.columns import ColumnsStrategy

STRATEGIES: dict[str, Strategy] = {
    "columns": ColumnsStrategy(),
}


def get_strategy(name: str) -> Strategy:
    try:
        return STRATEGIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy: {name}") from exc
