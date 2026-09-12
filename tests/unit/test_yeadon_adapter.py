"""Unit tests for the Yeadon (1990) adapter and the measurement data model.

These tests never touch the BodyLoop API and never use real subject data: all
inputs are synthetic (see ``tests/fixtures/synthetic_data.py``).

``build_yeadon_human`` is exercised with ``unittest.mock`` rather than a real
:class:`yeadon.Human`, so the suite passes whether or not the ``yeadon`` wheel
is installed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from pydantic import ValidationError

from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
    Measurement,
    MeasurementSet,
)
from bodyloop_anthropometrics.anthropometry.yeadon_adapter import (
    MAPPING_FILE,
    YEADON_KEYS_ORDERED,
    YEADON_REQUIRED_KEYS,
    build_yeadon_human,
    coverage_table,
    export_inertial_params,
    extract_measurements,
    load_mapping,
)

EXPECTED_KEY_COUNT = 95

#: Number of keys per Yeadon region, from Yeadon (1990) and
#: ``yeadon.human.Human.measnames`` in yeadon 1.5.0.
KEYS_PER_REGION = {"Ls": 21, "La": 18, "Lb": 18, "Lj": 19, "Lk": 19}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mapping() -> dict[str, dict[str, object]]:
    """Return the real ``configs/bodyloop_to_yeadon.yaml`` mapping.

    Returns
    -------
    dict[str, dict[str, object]]
        Parsed mapping keyed by Yeadon measurement key.
    """
    return load_mapping()


@pytest.fixture
def partial_normalized(mapping: dict[str, dict[str, object]]) -> dict[str, object]:
    """Build synthetic normalised data that resolves exactly five Yeadon keys.

    Parameters
    ----------
    mapping : dict[str, dict[str, object]]
        The real mapping, used so that the fixture stays in sync with the
        paths the adapter actually looks for.

    Returns
    -------
    dict[str, object]
        Synthetic normalised BodyLoop sections.  Values are plausible for a
        1.75 m adult but are entirely fictitious.
    """
    return {
        "markers": {"vertex": [0.0, 1.75, 0.0]},
        "distances": {
            "hand_length_left": 0.189,
            "foot_width_left": 0.093,
        },
        "heights": {"standing": 1.75},
        "crosssections": {
            "umbilicus": {"convex_m": 0.840, "width_ml_m": 0.290},
            "head_max": {"convex_m": 0.570},
        },
    }


@pytest.fixture
def resolvable_keys() -> set[str]:
    """Return the Yeadon keys the ``partial_normalized`` fixture can satisfy.

    Returns
    -------
    set[str]
        Keys expected to be present after extraction.
    """
    return {"Ls1p", "Ls1w", "Ls7p", "La7L", "Lj8w"}


def _complete_measurement_set() -> MeasurementSet:
    """Build a MeasurementSet holding all 95 keys with placeholder values.

    Returns
    -------
    MeasurementSet
        Fully populated set.  Values are dimensionally plausible but
        scientifically meaningless -- they exist only to satisfy the
        completeness check of :func:`build_yeadon_human`.
    """
    return MeasurementSet(
        subject_id="SYNTHETIC_001",
        acquisition_date="2026-09-11",
        measurements={
            key: Measurement(
                value=0.1,
                unit="m",
                frame="bodyloop_global",
                source="manual",
                confidence=0.6,
                notes="Synthetic placeholder - not a real measurement.",
            )
            for key in YEADON_KEYS_ORDERED
        },
        missing=[],
    )


# ---------------------------------------------------------------------------
# Mapping completeness
# ---------------------------------------------------------------------------


def test_all_95_keys_in_mapping(mapping: dict[str, dict[str, object]]) -> None:
    """The YAML mapping defines exactly the 95 Yeadon keys, no more, no less."""
    assert len(mapping) == EXPECTED_KEY_COUNT
    assert set(mapping) == set(YEADON_REQUIRED_KEYS)
    assert len(YEADON_KEYS_ORDERED) == EXPECTED_KEY_COUNT


def test_mapping_regions_have_expected_counts(
    mapping: dict[str, dict[str, object]],
) -> None:
    """Each Yeadon region contributes its documented number of measurements."""
    counts: dict[str, int] = {}
    for key in mapping:
        counts[key[:2]] = counts.get(key[:2], 0) + 1
    assert counts == KEYS_PER_REGION


def test_mapping_matches_installed_yeadon_measnames() -> None:
    """The mapping key set equals ``yeadon.human.Human.measnames``.

    Skipped when ``yeadon`` is not installed, since the assertion is about the
    package's own definition of the measurement set.
    """
    yeadon_human = pytest.importorskip("yeadon.human")
    assert set(YEADON_KEYS_ORDERED) == set(yeadon_human.Human.measnames)


def test_mapping_entries_are_well_formed(
    mapping: dict[str, dict[str, object]],
) -> None:
    """Every entry carries the full provenance schema with valid values."""
    valid_sources = {"direct", "calculated", "interpolated", "external", "manual"}
    for key, entry in mapping.items():
        assert entry["source_type"] in valid_sources, key
        assert entry["units"] == "m", key
        assert 0.0 <= float(entry["confidence"]) <= 1.0, key
        assert isinstance(entry["manual_validation_required"], bool), key
        assert entry["anatomical_definition"], key
        if entry["source_type"] != "direct":
            assert entry["calculation"], key


def test_mapping_low_confidence_entries_have_notes(
    mapping: dict[str, dict[str, object]],
) -> None:
    """Low-confidence entries carry notes, so Measurement construction cannot fail."""
    for key, entry in mapping.items():
        if float(entry["confidence"]) < 0.5:
            assert entry["notes"], key


def test_mapping_difficult_landmarks_flagged(
    mapping: dict[str, dict[str, object]],
) -> None:
    """Keys resting on a difficult landmark require manual validation.

    The landmarks concerned are listed in ``SCIENCE_DECISIONS.md``: hip joint
    centre, shoulder joint centre, acromion, crotch, heel, foot arch, nipple,
    base of the thumb, and lowest anterior rib.
    """
    difficult = [
        "Ls1L",  # measured from the hip joint centre
        "Ls3L",  # nipple level
        "Ls2L",  # lowest anterior rib
        "Ls5L",  # acromion level
        "La5L",  # base of the thumb
        "Lj1L",  # crotch
        "Lj6L",  # heel
        "Lj7p",  # foot arch
        "Lk6d",  # heel depth
    ]
    for key in difficult:
        assert mapping[key]["manual_validation_required"] is True, key
        assert mapping[key]["notes"], key


def test_mapping_file_declares_convex_perimeter_convention() -> None:
    """The file header documents the convex-vs-perimeter decision."""
    text = MAPPING_FILE.read_text(encoding="utf-8")
    assert "convex" in text.lower()
    assert "TODO_SCIENTIFIC" in text


def test_load_mapping_rejects_incomplete_file(tmp_path: Path) -> None:
    """A file that is not exactly the 95 keys is rejected, not silently used."""
    truncated = tmp_path / "partial.yaml"
    truncated.write_text(
        yaml.safe_dump({"Ls1L": {"bodyloop_path": None}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="exactly the 95 Yeadon keys"):
        load_mapping(truncated)


def test_load_mapping_missing_file(tmp_path: Path) -> None:
    """A non-existent mapping path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_mapping(tmp_path / "does_not_exist.yaml")


# ---------------------------------------------------------------------------
# Measurement validation
# ---------------------------------------------------------------------------


def test_measurement_low_confidence_requires_notes() -> None:
    """Confidence < 0.5 without notes is a validation error, not a warning."""
    with pytest.raises(ValidationError):
        Measurement(
            value=0.3,
            unit="m",
            frame="bodyloop_global",
            source="calculated",
            confidence=0.3,
            notes=None,
        )


def test_measurement_low_confidence_with_notes_is_accepted() -> None:
    """The same low-confidence value is accepted once it is explained."""
    meas = Measurement(
        value=0.3,
        unit="m",
        frame="bodyloop_global",
        source="calculated",
        confidence=0.3,
        notes="Derived from an unvalidated heel landmark.",
    )
    assert meas.confidence == pytest.approx(0.3)


def test_measurement_confidence_out_of_range() -> None:
    """Confidence outside [0, 1] is rejected."""
    with pytest.raises(ValidationError):
        Measurement(
            value=0.3,
            unit="m",
            frame="bodyloop_global",
            source="direct",
            confidence=1.4,
        )


def test_measurement_set_rejects_present_and_missing_key() -> None:
    """A key cannot be both extracted and reported missing."""
    with pytest.raises(ValidationError):
        MeasurementSet(
            subject_id="S",
            acquisition_date="2026-09-11",
            measurements={
                "Ls1p": Measurement(
                    value=0.84,
                    unit="m",
                    frame="bodyloop_global",
                    source="direct",
                    confidence=0.8,
                )
            },
            missing=["Ls1p"],
        )


# ---------------------------------------------------------------------------
# MeasurementSet behaviour
# ---------------------------------------------------------------------------


def test_measurement_set_coverage_report() -> None:
    """coverage_report counts present, missing, and manual-review measurements."""
    measurement_set = MeasurementSet(
        subject_id="SYNTHETIC_001",
        acquisition_date="2026-09-11",
        measurements={
            "Ls1p": Measurement(
                value=0.84,
                unit="m",
                frame="bodyloop_global",
                source="direct",
                confidence=0.8,
            ),
            "Ls1w": Measurement(
                value=0.29,
                unit="m",
                frame="bodyloop_global",
                source="direct",
                confidence=0.8,
            ),
            "Ls3L": Measurement(
                value=0.42,
                unit="m",
                frame="bodyloop_global",
                source="calculated",
                confidence=0.45,
                notes="Nipple level - unvalidated landmark.",
                manual_validation_required=True,
            ),
        },
        missing=["Ls2L", "Ls2p"],
    )

    report = measurement_set.coverage_report()

    assert report["total"] == 5
    assert report["present"] == 3
    assert report["missing"] == 2
    assert report["manual_required"] == 1
    assert report["coverage_fraction"] == pytest.approx(0.6)
    assert report["by_source"] == {"direct": 2, "calculated": 1}
    assert report["missing_keys"] == ["Ls2L", "Ls2p"]
    assert report["manual_required_keys"] == ["Ls3L"]
    # Ls3L needs review and nobody has reviewed it yet.
    assert report["pending_validation"] == 1
    assert report["pending_validation_keys"] == ["Ls3L"]
    assert report["approved"] == 0
    assert report["rejected"] == 0
    # The two direct measurements need no review, so they are already usable.
    assert report["usable"] == 2


# ---------------------------------------------------------------------------
# Human validation workflow
# ---------------------------------------------------------------------------


def _reviewable(**overrides: object) -> Measurement:
    """Build a measurement flagged for manual validation.

    Parameters
    ----------
    **overrides : object
        Field overrides applied on top of the reviewable defaults.

    Returns
    -------
    Measurement
        Measurement with ``manual_validation_required=True``.
    """
    fields: dict[str, object] = {
        "value": 0.42,
        "unit": "m",
        "frame": "bodyloop_global",
        "source": "calculated",
        "confidence": 0.45,
        "notes": "Nipple level - unvalidated landmark.",
        "manual_validation_required": True,
    }
    fields.update(overrides)
    return Measurement(**fields)  # type: ignore[arg-type]


def test_measurement_validation_defaults_to_pending() -> None:
    """A freshly extracted measurement is never pre-approved."""
    meas = _reviewable()
    assert meas.validation_status == "pending"
    assert meas.validated_by is None
    assert meas.validated_date is None
    assert meas.validation_notes is None
    assert meas.is_usable is False


def test_measurement_review_requires_validator_and_date() -> None:
    """An approval with no author and no date is rejected as unauditable."""
    with pytest.raises(ValidationError):
        _reviewable(validation_status="approved")
    with pytest.raises(ValidationError):
        _reviewable(validation_status="rejected", validated_by="MB")


def test_measurement_approved_becomes_usable() -> None:
    """An attributed approval clears the measurement for downstream use."""
    meas = _reviewable(
        validation_status="approved",
        validated_by="MB",
        validated_date="2026-09-11",
        validation_notes="Landmark confirmed on the mesh.",
    )
    assert meas.is_usable is True


def test_measurement_rejected_is_never_usable() -> None:
    """A rejected value stays unusable even if no review was required."""
    meas = _reviewable(
        manual_validation_required=False,
        validation_status="rejected",
        validated_by="MB",
        validated_date="2026-09-11",
    )
    assert meas.is_usable is False


def test_pending_validation_lists_only_unreviewed_flagged_keys() -> None:
    """pending_validation is the work queue of the visual validation tool."""
    measurement_set = MeasurementSet(
        subject_id="SYNTHETIC_001",
        acquisition_date="2026-09-11",
        measurements={
            "Ls3L": _reviewable(),
            "Ls2L": _reviewable(),
            "Ls5L": _reviewable(
                validation_status="approved",
                validated_by="MB",
                validated_date="2026-09-11",
            ),
            "Lj6L": _reviewable(
                validation_status="rejected",
                validated_by="MB",
                validated_date="2026-09-11",
                validation_notes="Heel landmark fell on the sock, not the skin.",
            ),
            "Ls1p": Measurement(
                value=0.84,
                unit="m",
                frame="bodyloop_global",
                source="direct",
                confidence=0.8,
            ),
        },
    )

    assert measurement_set.pending_validation() == ["Ls2L", "Ls3L"]
    assert measurement_set.rejected() == ["Lj6L"]
    report = measurement_set.coverage_report()
    assert report["manual_required"] == 4
    assert report["pending_validation"] == 2
    assert report["approved"] == 1
    assert report["rejected"] == 1
    # Approved (Ls5L) + no-review-needed (Ls1p).
    assert report["usable"] == 2


def test_extracted_measurements_start_pending(
    partial_normalized: dict[str, object],
) -> None:
    """Extraction never marks a measurement as already validated."""
    result = extract_measurements(partial_normalized)
    assert all(
        meas.validation_status == "pending" for meas in result.measurements.values()
    )


def test_coverage_table_shows_validation_status(
    partial_normalized: dict[str, object],
) -> None:
    """The coverage table exposes the review state of every present key."""
    table = coverage_table(extract_measurements(partial_normalized))
    assert "validation" in table
    assert "pending" in table
    assert "pending review" in table


def test_coverage_report_on_empty_set() -> None:
    """An empty set reports zero coverage instead of dividing by zero."""
    empty = MeasurementSet(
        subject_id="S", acquisition_date="2026-09-11", measurements={}
    )
    report = empty.coverage_report()
    assert report["total"] == 0
    assert report["coverage_fraction"] == 0.0


def test_to_yeadon_dict_raises_if_missing() -> None:
    """A set with any missing key refuses to produce a Yeadon dictionary."""
    measurement_set = MeasurementSet(
        subject_id="S",
        acquisition_date="2026-09-11",
        measurements={
            "Ls1p": Measurement(
                value=0.84,
                unit="m",
                frame="bodyloop_global",
                source="direct",
                confidence=0.8,
            )
        },
        missing=["Ls2L"],
    )
    with pytest.raises(ValueError, match="missing"):
        measurement_set.to_yeadon_dict()


def test_to_yeadon_dict_raises_on_absent_required_key() -> None:
    """An explicitly required key that is absent is reported by name."""
    measurement_set = MeasurementSet(
        subject_id="S",
        acquisition_date="2026-09-11",
        measurements={
            "Ls1p": Measurement(
                value=0.84,
                unit="m",
                frame="bodyloop_global",
                source="direct",
                confidence=0.8,
            )
        },
    )
    with pytest.raises(ValueError, match="Ls2L"):
        measurement_set.to_yeadon_dict(required_keys=frozenset({"Ls1p", "Ls2L"}))


def test_to_yeadon_dict_rejects_non_metre_units() -> None:
    """Yeadon reads a raw dict as metres, so other units must not slip through."""
    measurement_set = MeasurementSet(
        subject_id="S",
        acquisition_date="2026-09-11",
        measurements={
            "Ls1p": Measurement(
                value=840.0,
                unit="mm",
                frame="bodyloop_global",
                source="direct",
                confidence=0.8,
            )
        },
    )
    with pytest.raises(ValueError, match="metres"):
        measurement_set.to_yeadon_dict()


def test_to_yeadon_dict_returns_values_in_metres() -> None:
    """A complete set exports a flat ``{key: metres}`` dictionary."""
    exported = _complete_measurement_set().to_yeadon_dict()
    assert set(exported) == set(YEADON_REQUIRED_KEYS)
    assert all(isinstance(value, float) for value in exported.values())


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def test_extract_measurements_no_silent_imputation(
    partial_normalized: dict[str, object], resolvable_keys: set[str]
) -> None:
    """Unresolvable measurements land in ``missing`` and are never invented."""
    result = extract_measurements(
        partial_normalized,
        subject_id="SYNTHETIC_001",
        acquisition_date="2026-09-11",
    )

    assert set(result.measurements) == resolvable_keys
    # Every key is accounted for exactly once, present or missing.
    assert set(result.measurements) | set(result.missing) == set(YEADON_REQUIRED_KEYS)
    assert len(result.measurements) + len(result.missing) == EXPECTED_KEY_COUNT
    assert not set(result.measurements) & set(result.missing)
    # Nothing was fabricated for a key with no resolvable path.
    for key in result.missing:
        assert key not in result.measurements


def test_extract_measurements_carries_provenance(
    partial_normalized: dict[str, object],
) -> None:
    """Extracted values keep the source, path, and confidence from the mapping."""
    result = extract_measurements(partial_normalized)
    meas = result.measurements["Ls1p"]
    assert meas.value == pytest.approx(0.840)
    assert meas.unit == "m"
    assert meas.source == "direct"
    assert meas.bodyloop_path == "crosssections.umbilicus.convex_m"
    assert meas.confidence > 0.0


def test_extract_measurements_resolves_labelled_lists() -> None:
    """Paths resolve against the list-of-labelled-objects export shape."""
    normalized = {
        "markers": [],
        "heights": [],
        "distances": [{"label": "foot_width_left", "value": 0.093}],
        "crosssections": [
            {"label": "head_max", "convex_m": 0.570, "perimeter_m": 0.560}
        ],
    }
    result = extract_measurements(normalized)
    assert result.measurements["Ls7p"].value == pytest.approx(0.570)
    # distances.foot_width_left resolves to a dict, not a number, so Lj8w is
    # reported missing rather than coerced.
    assert "Lj8w" in result.missing


def test_extract_measurements_rejects_incomplete_input() -> None:
    """Normalised data missing a required section raises ValueError."""
    with pytest.raises(ValueError, match="missing required top-level keys"):
        extract_measurements({"markers": {}, "heights": {}})


def test_extract_measurements_rejects_non_dict_input() -> None:
    """A non-dict payload is rejected with a clear message."""
    with pytest.raises(ValueError, match="must be a dict"):
        extract_measurements(["not", "a", "dict"])  # type: ignore[arg-type]


def test_extract_measurements_ignores_non_numeric_values() -> None:
    """A path that resolves to a non-number is missing, not coerced to zero."""
    normalized = {
        "markers": {},
        "heights": {},
        "distances": {},
        "crosssections": {"head_max": {"convex_m": "not a number"}},
    }
    result = extract_measurements(normalized)
    assert "Ls7p" in result.missing
    assert "Ls7p" not in result.measurements


def test_extract_measurements_accepts_cross_sections_alias(
    partial_normalized: dict[str, object],
) -> None:
    """The ``cross_sections`` spelling used by fixtures resolves identically."""
    aliased = dict(partial_normalized)
    aliased["cross_sections"] = aliased.pop("crosssections")
    result = extract_measurements(aliased)
    assert "Ls1p" in result.measurements


def test_extract_measurements_on_full_synthetic_scan_reports_gaps() -> None:
    """The shared synthetic fixture yields a set with explicit, honest gaps."""
    from tests.fixtures.synthetic_data import make_synthetic_viatar

    result = extract_measurements(make_synthetic_viatar())
    report = result.coverage_report()
    assert report["total"] == EXPECTED_KEY_COUNT
    assert report["missing"] > 0
    assert report["present"] + report["missing"] == EXPECTED_KEY_COUNT


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_coverage_table_contains_all_keys(
    partial_normalized: dict[str, object],
) -> None:
    """The ASCII table lists every one of the 95 keys, present or missing."""
    table = coverage_table(extract_measurements(partial_normalized))
    for key in YEADON_KEYS_ORDERED:
        assert key in table, key
    assert "MISSING" in table
    assert "manual_required" in table


def test_coverage_table_reports_summary_line(
    partial_normalized: dict[str, object], resolvable_keys: set[str]
) -> None:
    """The table ends with a present/total summary."""
    table = coverage_table(extract_measurements(partial_normalized))
    assert f"{len(resolvable_keys)}/{EXPECTED_KEY_COUNT} present" in table


# ---------------------------------------------------------------------------
# yeadon.Human construction (mocked -- no dependency on the yeadon wheel)
# ---------------------------------------------------------------------------


def test_build_yeadon_human_calls_yeadon_and_scales() -> None:
    """A complete set builds a Human and rescales it to the measured mass."""
    measurement_set = _complete_measurement_set()
    fake_yeadon = MagicMock()
    fake_human = fake_yeadon.Human.return_value

    with patch(
        "bodyloop_anthropometrics.anthropometry.yeadon_adapter.yeadon", fake_yeadon
    ):
        human = build_yeadon_human(measurement_set, mass_kg=70.0, symmetric=False)

    assert human is fake_human
    args, kwargs = fake_yeadon.Human.call_args
    assert set(args[0]) == set(YEADON_REQUIRED_KEYS)
    assert kwargs["symmetric"] is False
    fake_human.scale_human_by_mass.assert_called_once_with(70.0)


def test_build_yeadon_human_raises_if_key_missing() -> None:
    """An incomplete set never reaches yeadon."""
    incomplete = _complete_measurement_set()
    incomplete.measurements.pop("Ls1L")
    fake_yeadon = MagicMock()

    with patch(
        "bodyloop_anthropometrics.anthropometry.yeadon_adapter.yeadon", fake_yeadon
    ):
        with pytest.raises(ValueError, match="Missing Yeadon measurements"):
            build_yeadon_human(incomplete, mass_kg=70.0)

    fake_yeadon.Human.assert_not_called()


def test_build_yeadon_human_rejects_non_positive_mass() -> None:
    """Mass must be strictly positive."""
    with patch(
        "bodyloop_anthropometrics.anthropometry.yeadon_adapter.yeadon", MagicMock()
    ):
        with pytest.raises(ValueError, match="mass_kg must be > 0"):
            build_yeadon_human(_complete_measurement_set(), mass_kg=0.0)


def test_build_yeadon_human_without_yeadon_installed() -> None:
    """A clear ImportError is raised when the yeadon wheel is absent."""
    with patch("bodyloop_anthropometrics.anthropometry.yeadon_adapter.yeadon", None):
        with pytest.raises(ImportError, match="yeadon"):
            build_yeadon_human(_complete_measurement_set(), mass_kg=70.0)


def test_export_inertial_params_shapes() -> None:
    """Segment parameters are exported as plain floats and nested lists."""
    segment = MagicMock()
    segment.label = "thigh"
    segment.mass = 10.5
    segment.center_of_mass = [[0.01], [0.02], [0.45]]
    segment.inertia = [[0.2, 0.0, 0.0], [0.0, 0.2, 0.0], [0.0, 0.0, 0.05]]
    human = MagicMock()
    human.segments = [segment]

    params = export_inertial_params(human)

    assert set(params) == {"thigh"}
    assert params["thigh"]["mass_kg"] == pytest.approx(10.5)
    assert params["thigh"]["com_m"] == pytest.approx([0.01, 0.02, 0.45])
    assert len(params["thigh"]["inertia_tensor_kgm2"]) == 3
    assert all(len(row) == 3 for row in params["thigh"]["inertia_tensor_kgm2"])
    assert "yeadon_global" in params["thigh"]["frame"]
