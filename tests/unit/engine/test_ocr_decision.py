"""Unit tests de decide_ocr."""

from __future__ import annotations

from extractor.engine.ocr_decision import decide_ocr


def test_image_always_ocr() -> None:
    assert (
        decide_ocr(
            content_type="image/png",
            density=999.0,
            mode="never",
            density_threshold=5.0,
        )
        == "ocr"
    )


def test_never_with_zero_density_is_unreadable() -> None:
    assert (
        decide_ocr(
            content_type="application/pdf",
            density=0.0,
            mode="never",
            density_threshold=5.0,
        )
        == "unreadable"
    )


def test_never_with_text_is_native() -> None:
    assert (
        decide_ocr(
            content_type="application/pdf",
            density=40.0,
            mode="never",
            density_threshold=5.0,
        )
        == "native"
    )


def test_force_always_ocr() -> None:
    assert (
        decide_ocr(
            content_type="application/pdf",
            density=40.0,
            mode="force",
            density_threshold=5.0,
        )
        == "ocr"
    )


def test_auto_below_threshold_uses_ocr() -> None:
    assert (
        decide_ocr(
            content_type="application/pdf",
            density=1.0,
            mode="auto",
            density_threshold=5.0,
        )
        == "ocr"
    )


def test_auto_above_threshold_uses_native() -> None:
    assert (
        decide_ocr(
            content_type="application/pdf",
            density=20.0,
            mode="auto",
            density_threshold=5.0,
        )
        == "native"
    )
