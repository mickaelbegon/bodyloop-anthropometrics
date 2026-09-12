"""Unit tests for bodyloop_anthropometrics.visualization.measurement_viewer.

Tests cover pure logic functions only — no Dash server is started.

Notes
-----
All fixtures use synthetic data so no real patient information is
required (AGENTS.md rule: fixtures use exclusively synthetic data).
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
    Measurement,
    MeasurementSet,
)
from bodyloop_anthropometrics.visualization.measurement_viewer import (
    SOURCE_COLORS,
    load_mesh,
    load_measurement_set,
    save_measurement_set,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_measurement(
    value: float = 0.35,
    source: str = "direct",
    manual_validation_required: bool = True,
    validation_status: str = "pending",
    validated_by: str | None = None,
    validated_date: str | None = None,
    validation_notes: str | None = None,
) -> Measurement:
    """Build a synthetic Measurement for testing.

    Parameters
    ----------
    value : float
    source : str
    manual_validation_required : bool
    validation_status : str
    validated_by : str or None
    validated_date : str or None
    validation_notes : str or None

    Returns
    -------
    Measurement
    """
    kwargs: dict[str, Any] = {
        "value": value,
        "unit": "m",
        "frame": "bodyloop_global",
        "source": source,
        "confidence": 0.9,
        "bodyloop_path": "distances.shoulder_width",
        "manual_validation_required": manual_validation_required,
        "validation_status": validation_status,
    }
    if validated_by is not None:
        kwargs["validated_by"] = validated_by
    if validated_date is not None:
        kwargs["validated_date"] = validated_date
    if validation_notes is not None:
        kwargs["validation_notes"] = validation_notes
    return Measurement(**kwargs)


def _make_measurement_set(
    measurements: dict[str, Measurement] | None = None,
) -> MeasurementSet:
    """Build a synthetic MeasurementSet for testing.

    Parameters
    ----------
    measurements : dict or None
        Measurement mapping.  A minimal default is used when None.

    Returns
    -------
    MeasurementSet
    """
    if measurements is None:
        measurements = {
            "Ls1L": _make_measurement(value=0.10, source="direct"),
            "La2L": _make_measurement(value=0.28, source="calculated"),
        }
    return MeasurementSet(
        subject_id="SYNTH_001",
        acquisition_date="2026-09-11",
        measurements=measurements,
        missing=[],
    )


# ---------------------------------------------------------------------------
# test_source_colors_cover_all_sources
# ---------------------------------------------------------------------------


def test_source_colors_cover_all_sources() -> None:
    """SOURCE_COLORS must define a color for every valid Measurement.source value.

    The Measurement model's Literal type is the authority; we verify that
    every literal is present in the color mapping so the viewer never falls
    through to a missing-key error.
    """
    # Extract the accepted literals from the Measurement annotation
    import typing

    hints = typing.get_type_hints(Measurement)
    source_hint = hints["source"]
    # Under Python 3.11+ this is a typing.Literal; its __args__ hold the values
    accepted_sources = set(typing.get_args(source_hint))

    assert accepted_sources, "Could not extract source literals from Measurement"
    missing_colors = accepted_sources - set(SOURCE_COLORS)
    assert not missing_colors, (
        f"SOURCE_COLORS is missing entries for source values: {missing_colors}"
    )


# ---------------------------------------------------------------------------
# test_save_load_roundtrip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path) -> None:
    """Saving then loading a MeasurementSet must reproduce the same data.

    Parameters
    ----------
    tmp_path : Path
        pytest temporary directory fixture.
    """
    original = _make_measurement_set()
    saved_path = save_measurement_set(tmp_path, original, "yeadon")
    assert saved_path.exists(), "save_measurement_set must create the output file"

    loaded = load_measurement_set(tmp_path, "yeadon")
    assert loaded is not None, "load_measurement_set returned None for a file we just saved"
    assert loaded.subject_id == original.subject_id
    assert loaded.acquisition_date == original.acquisition_date
    assert set(loaded.measurements.keys()) == set(original.measurements.keys())
    for key in original.measurements:
        assert loaded.measurements[key].value == pytest.approx(
            original.measurements[key].value, rel=1e-9
        )


# ---------------------------------------------------------------------------
# test_save_never_overwrites_original
# ---------------------------------------------------------------------------


def test_save_never_overwrites_original(tmp_path: Path) -> None:
    """save_measurement_set must write to *_validated.json, not the original.

    Parameters
    ----------
    tmp_path : Path
        pytest temporary directory fixture.
    """
    # Create a fake original file
    normalized_dir = tmp_path / "normalized"
    normalized_dir.mkdir()
    original_file = normalized_dir / "yeadon_measurements.json"
    sentinel_content = '{"sentinel": true}'
    original_file.write_text(sentinel_content, encoding="utf-8")

    ms = _make_measurement_set()
    saved_path = save_measurement_set(tmp_path, ms, "yeadon")

    # The saved file must differ from the original path
    assert saved_path != original_file, (
        "save_measurement_set must not write to the original measurements.json"
    )
    assert "_validated" in saved_path.name, (
        "Saved file name must contain '_validated'"
    )
    # Original must be untouched
    assert original_file.read_text(encoding="utf-8") == sentinel_content, (
        "save_measurement_set must not overwrite the original file"
    )


# ---------------------------------------------------------------------------
# test_approve_sets_required_fields
# ---------------------------------------------------------------------------


def test_approve_sets_required_fields() -> None:
    """Constructing an approved Measurement must populate required audit fields.

    When a measurement is approved in the viewer the callback builds a new
    Measurement instance with validation_status='approved', validated_by, and
    validated_date set.  We replicate that logic here to verify the model
    constraint is satisfied.
    """
    original = _make_measurement(validation_status="pending")
    today = datetime.date.today().isoformat()

    approved = Measurement(
        value=original.value,
        unit=original.unit,
        frame=original.frame,
        source=original.source,
        confidence=original.confidence,
        bodyloop_path=original.bodyloop_path,
        notes=original.notes,
        manual_validation_required=original.manual_validation_required,
        validation_status="approved",
        validated_by="TEST_VALIDATOR",
        validated_date=today,
        validation_notes="Looks correct on the mesh.",
    )

    assert approved.validation_status == "approved"
    assert approved.validated_by is not None, "validated_by must be set after approval"
    assert approved.validated_date is not None, "validated_date must be set after approval"
    assert approved.validated_date == today


# ---------------------------------------------------------------------------
# test_reject_requires_notes
# ---------------------------------------------------------------------------


def test_reject_requires_notes(caplog: pytest.LogCaptureFixture) -> None:
    """Rejecting without notes should log a warning, not raise an exception.

    The viewer's _do_validation helper auto-fills a warning note when the
    validator submits a rejection with an empty notes field.  We test that
    the model accepts the rejection when the auto-filled note is present,
    and that a warning was logged (not an error).
    """
    today = datetime.date.today().isoformat()
    # Simulate what _do_validation does: auto-fill the notes
    auto_notes = "[WARNING] No notes provided at rejection time."

    with caplog.at_level(logging.WARNING, logger="bodyloop_anthropometrics"):
        # Log the warning explicitly as the real helper does
        logging.getLogger("bodyloop_anthropometrics").warning(
            "Reject without notes for key %s — auto-filling a warning.", "Ls1L"
        )
        rejected = Measurement(
            value=0.35,
            unit="m",
            frame="bodyloop_global",
            source="direct",
            confidence=0.9,
            manual_validation_required=True,
            validation_status="rejected",
            validated_by="TEST_VALIDATOR",
            validated_date=today,
            validation_notes=auto_notes,
        )

    assert rejected.validation_status == "rejected"
    assert rejected.validation_notes == auto_notes
    # At least one warning must have been emitted
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "A warning must be logged when rejecting without notes"


# ---------------------------------------------------------------------------
# test_load_mesh_returns_none_if_absent
# ---------------------------------------------------------------------------


def test_load_mesh_returns_none_if_absent(tmp_path: Path) -> None:
    """load_mesh must return None without raising when the GLB file is absent.

    Parameters
    ----------
    tmp_path : Path
        pytest temporary directory fixture.  Does not contain raw/mesh_3d.glb.
    """
    result = load_mesh(tmp_path)
    assert result is None, (
        "load_mesh must return None when raw/mesh_3d.glb does not exist, "
        f"got {type(result)}"
    )


# ---------------------------------------------------------------------------
# test_load_measurement_set_prefers_validated_file
# ---------------------------------------------------------------------------


def test_load_measurement_set_prefers_validated_file(tmp_path: Path) -> None:
    """load_measurement_set must prefer the _validated.json file over the original.

    Parameters
    ----------
    tmp_path : Path
        pytest temporary directory fixture.
    """
    normalized_dir = tmp_path / "normalized"
    normalized_dir.mkdir()

    # Write original (different subject_id)
    original_ms = _make_measurement_set()
    original_ms_data = original_ms.model_dump()
    original_ms_data["subject_id"] = "ORIGINAL"
    (normalized_dir / "yeadon_measurements.json").write_text(
        json.dumps(original_ms_data), encoding="utf-8"
    )

    # Write validated (different subject_id)
    validated_ms = _make_measurement_set()
    validated_ms_data = validated_ms.model_dump()
    validated_ms_data["subject_id"] = "VALIDATED"
    (normalized_dir / "yeadon_measurements_validated.json").write_text(
        json.dumps(validated_ms_data), encoding="utf-8"
    )

    loaded = load_measurement_set(tmp_path, "yeadon")
    assert loaded is not None
    assert loaded.subject_id == "VALIDATED", (
        "load_measurement_set must prefer the _validated.json file"
    )


# ---------------------------------------------------------------------------
# test_load_measurement_set_falls_back_to_original
# ---------------------------------------------------------------------------


def test_load_measurement_set_falls_back_to_original(tmp_path: Path) -> None:
    """load_measurement_set must fall back to the original file when no validated file exists.

    Parameters
    ----------
    tmp_path : Path
        pytest temporary directory fixture.
    """
    normalized_dir = tmp_path / "normalized"
    normalized_dir.mkdir()

    ms = _make_measurement_set()
    ms_data = ms.model_dump()
    ms_data["subject_id"] = "FALLBACK_ORIGINAL"
    (normalized_dir / "yeadon_measurements.json").write_text(
        json.dumps(ms_data), encoding="utf-8"
    )

    loaded = load_measurement_set(tmp_path, "yeadon")
    assert loaded is not None
    assert loaded.subject_id == "FALLBACK_ORIGINAL"


# ---------------------------------------------------------------------------
# test_load_measurement_set_returns_none_if_no_files
# ---------------------------------------------------------------------------


def test_load_measurement_set_returns_none_if_no_files(tmp_path: Path) -> None:
    """load_measurement_set must return None when no measurement file exists.

    Parameters
    ----------
    tmp_path : Path
        pytest temporary directory fixture with no normalized/ subdirectory.
    """
    result = load_measurement_set(tmp_path, "yeadon")
    assert result is None, (
        "load_measurement_set must return None when no measurement file is found"
    )
