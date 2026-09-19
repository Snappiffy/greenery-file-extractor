"""Golden set: documentos → salida esperada."""

from __future__ import annotations

import json

import pytest

from tests.fixtures.golden import _generate as gen
from tests.golden.helpers import canonical_payload, golden_dirs, run_golden


@pytest.fixture(scope="session", autouse=True)
def _ensure_golden_fixtures() -> None:
    gen.main()
    # Regenerar expected si falta (primera corrida local).
    for folder in golden_dirs():
        expected_path = folder / "catalog.expected.json"
        if not expected_path.exists():
            payload = canonical_payload(run_golden(folder))
            expected_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


@pytest.mark.golden
@pytest.mark.parametrize("folder", golden_dirs(), ids=lambda p: p.name)
def test_golden_matches_expected(folder) -> None:  # type: ignore[no-untyped-def]
    expected = json.loads((folder / "catalog.expected.json").read_text(encoding="utf-8"))
    actual = canonical_payload(run_golden(folder))
    assert actual == expected
