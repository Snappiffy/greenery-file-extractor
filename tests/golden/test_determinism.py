"""Determinismo: misma entrada → mismos bytes (salvo duration_ms)."""

from __future__ import annotations

import json

import pytest

from tests.golden.helpers import canonical_payload, golden_dirs, run_golden


@pytest.mark.golden
@pytest.mark.parametrize("folder", golden_dirs(), ids=lambda p: p.name)
def test_extraction_is_byte_identical_across_runs(folder) -> None:  # type: ignore[no-untyped-def]
    a = canonical_payload(run_golden(folder))
    b = canonical_payload(run_golden(folder))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
