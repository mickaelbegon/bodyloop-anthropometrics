"""Integration tests: BodyLoop normalised data → Yeadon MeasurementSet.

All tests use a mock normalised-data dict populated from the live
``configs/bodyloop_to_yeadon.yaml`` mapping, so config drift is detected
immediately.  No network calls are made.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bodyloop_anthropometrics.anthropometry.measurement_mapping import MeasurementSet
from bodyloop_anthropometrics.anthropometry.yeadon_adapter import (
    YEADON_KEYS_ORDERED,
    coverage_table,
    extract_measurements,
    load_mapping,
)

from .conftest import YEADON_CONFIG_PATH


@pytest.mark.integration
class TestYeadonPipeline:
    """Integration: mock normalised data → MeasurementSet → coverage report."""

    # ------------------------------------------------------------------
    # Fixtures / helpers
    # ------------------------------------------------------------------

    @pytest.fixture(autouse=True)
    def _setup(self, mock_viatar_data: object) -> None:
        """Populate mock data and call extract_measurements once per test."""
        data = mock_viatar_data(YEADON_CONFIG_PATH)
        self._mset: MeasurementSet = extract_measurements(
            data,
            subject_id="test-subject-01",
            acquisition_date="2026-09-12",
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_extract_measurements_returns_correct_count(self) -> None:
        """YeadonAdapter.extract_measurements returns MeasurementSet with 95 entries.

        The combined count of extracted measurements + missing keys must equal
        the canonical 95-key Yeadon set; nothing is silently dropped.
        """
        total = len(self._mset.measurements) + len(self._mset.missing)
        assert total == len(YEADON_KEYS_ORDERED), (
            f"Expected {len(YEADON_KEYS_ORDERED)} total entries (present + missing), "
            f"got present={len(self._mset.measurements)}, missing={len(self._mset.missing)}"
        )

    def test_coverage_report_lists_all_measurements(self) -> None:
        """coverage_table() output contains all 95 Yeadon measurement keys.

        The table is rendered for every key whether present or missing, so
        a scientist can see gaps at a glance.
        """
        table_output = coverage_table(self._mset)
        for key in YEADON_KEYS_ORDERED:
            assert key in table_output, (
                f"Yeadon key '{key}' is absent from coverage_table() output"
            )

    def test_pending_validation_not_empty(self) -> None:
        """pending_validation() returns non-empty list for fresh extraction.

        Every measurement extracted by the adapter has
        ``manual_validation_required=True`` (the default in the YAML), so
        a fresh MeasurementSet always has work in the validation queue.
        """
        # Only check if any measurements were actually extracted.
        if not self._mset.measurements:
            pytest.skip("No measurements resolved — cannot test pending_validation")
        pending = self._mset.pending_validation()
        assert len(pending) > 0, (
            "Expected at least one measurement pending validation, "
            "but pending_validation() returned an empty list"
        )

    def test_measurement_provenance_complete(self) -> None:
        """Every Measurement in MeasurementSet has non-None source.

        AGENTS.md rule 3: provenance is mandatory; no measurement may enter
        the set without an explicit source type.
        """
        for key, meas in self._mset.measurements.items():
            assert meas.source is not None, (
                f"Measurement '{key}' has source=None, violating AGENTS.md rule 3"
            )

    def test_no_silent_imputation(self) -> None:
        """Missing measurements land in the missing list, never silently imputed.

        AGENTS.md rule 2: a value that cannot be read is reported, never
        fabricated.  The practical check is that every key in YEADON_KEYS_ORDERED
        is accounted for in either ``measurements`` or ``missing``, and that
        calling ``to_yeadon_dict()`` raises when the set is incomplete.
        """
        # All 95 keys must be accounted for.
        accounted = set(self._mset.measurements) | set(self._mset.missing)
        assert accounted == set(YEADON_KEYS_ORDERED), (
            "Some Yeadon keys are neither measured nor reported as missing — "
            "silent imputation may have occurred"
        )

        # If any measurements are missing, to_yeadon_dict() must refuse.
        if self._mset.missing:
            with pytest.raises(ValueError, match="missing"):
                self._mset.to_yeadon_dict()

    def test_to_yeadon_dict_raises_before_validation(self, tmp_path: Path) -> None:
        """to_yeadon_dict() raises when measurements are missing.

        The 95-key Yeadon set always has some keys that require anatomical
        derivation (bodyloop_path=null) and therefore land in MeasurementSet.missing.
        Calling to_yeadon_dict() on such a set must raise ValueError rather than
        silently returning a dict with only the available keys.
        """
        mapping = load_mapping()
        # Count how many keys have null bodyloop_path (these will always be missing).
        null_path_keys = [
            k for k, v in mapping.items() if not v.get("bodyloop_path")
        ]

        if not null_path_keys:
            pytest.skip(
                "All 95 Yeadon keys have bodyloop_path in the mapping; "
                "cannot demonstrate missing-key guard with this config"
            )

        # Our mock resolves only keys with non-null paths; null-path keys are missing.
        assert len(self._mset.missing) > 0, (
            "Expected some missing keys (derived measurements have null paths)"
        )
        with pytest.raises(ValueError):
            self._mset.to_yeadon_dict()
