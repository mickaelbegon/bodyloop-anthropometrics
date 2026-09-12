"""Integration tests: BodyLoop viatar data → Hatze MeasurementSet.

All tests use a mock viatar-data dict populated from the live
``configs/bodyloop_to_hatze.yaml`` mapping, so config drift is detected
immediately.  No network calls are made.
"""

from __future__ import annotations

import pytest

from bodyloop_anthropometrics.anthropometry.hatze_adapter import (
    BLOCKED_PRIMITIVES,
    EXPECTED_MEASUREMENT_COUNT,
    HATZE_SEGMENTS,
    HatzeAdapter,
    MissingMeasurementError,
)
from bodyloop_anthropometrics.anthropometry.measurement_mapping import MeasurementSet

from .conftest import HATZE_CONFIG_PATH


@pytest.mark.integration
class TestHatzePipeline:
    """Integration: mock ViatarData → HatzeAdapter MeasurementSet."""

    # ------------------------------------------------------------------
    # Fixtures / helpers
    # ------------------------------------------------------------------

    @pytest.fixture(autouse=True)
    def _setup(self, mock_viatar_data: object) -> None:
        """Populate mock viatar data and instantiate the adapter."""
        self._adapter = HatzeAdapter()
        self._viatar_data = mock_viatar_data(HATZE_CONFIG_PATH)
        self._mset: MeasurementSet = self._adapter.extract_measurements(
            self._viatar_data,
            subject_id="test-subject-hatze",
            acquisition_date="2026-09-12",
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_extract_returns_242_measurements(self) -> None:
        """HatzeAdapter.extract_measurements accounts for exactly 242 entries.

        The combined count of extracted measurements + missing keys must equal
        EXPECTED_MEASUREMENT_COUNT (242); nothing is dropped.
        """
        total = len(self._mset.measurements) + len(self._mset.missing)
        assert total == EXPECTED_MEASUREMENT_COUNT, (
            f"Expected {EXPECTED_MEASUREMENT_COUNT} total (present + missing), "
            f"got present={len(self._mset.measurements)}, missing={len(self._mset.missing)}"
        )

    def test_all_have_source(self) -> None:
        """Every Measurement has a non-None source field.

        AGENTS.md rule 3: every measurement must carry an explicit provenance;
        no measurement enters the set without a source type.
        """
        for key, meas in self._mset.measurements.items():
            assert meas.source is not None, (
                f"Measurement '{key}' has source=None, violating AGENTS.md rule 3"
            )

    def test_a14_blocked_in_measurement_set(self) -> None:
        """All mapping entries with primitive A1.4 are marked blocked.

        The numerical audit of A1.4 (elliptic octoparaboloid) found errors of
        1.6-3.3% in the published coefficients.  Every entry that feeds A1.4
        must carry ``blocked: true`` so that any use raises RuntimeError.
        """
        mapping = self._adapter.load_mapping()
        a14_keys = [k for k, v in mapping.items() if v.get("primitive") == "A1.4"]
        assert len(a14_keys) > 0, (
            "No A1.4 primitive entries found in the Hatze mapping; "
            "expected the audit-flagged entries to be present"
        )
        for key in a14_keys:
            assert mapping[key].get("blocked") is True, (
                f"Entry '{key}' feeds the blocked A1.4 primitive but is not "
                f"marked 'blocked: true' in {HATZE_CONFIG_PATH}"
            )

    def test_compute_primitive_params_raises_not_implemented(self) -> None:
        """compute_primitive_params raises NotImplementedError for segments 1-17.

        The measurement-to-parameter equations from Hatze (1979) section 3
        are not yet available; all 17 segments must raise NotImplementedError.
        """
        empty_mset = MeasurementSet(
            subject_id="S",
            acquisition_date="2026-09-12",
            measurements={},
            missing=[],
        )
        for seg_id in HATZE_SEGMENTS:
            with pytest.raises(NotImplementedError):
                self._adapter.compute_primitive_params(empty_mset, seg_id)

    def test_a14_raises_runtime_error(self) -> None:
        """compute_primitive_params(meas, segment_id, 'A1.4') raises RuntimeError.

        Primitive A1.4 is unconditionally blocked: even calling it as a named
        primitive must raise RuntimeError before any computation is attempted.
        The check fires before the NotImplementedError for missing equations.
        """
        empty_mset = MeasurementSet(
            subject_id="S",
            acquisition_date="2026-09-12",
            measurements={},
            missing=[],
        )
        blocked_primitive = next(iter(BLOCKED_PRIMITIVES))  # "A1.4"
        # Use segment 11 (abdomino-pelvic) which feeds A1.4 in Hatze (1979).
        with pytest.raises(RuntimeError, match=blocked_primitive):
            self._adapter.compute_primitive_params(empty_mset, 11, blocked_primitive)

    def test_missing_direct_measurement_raises(self) -> None:
        """extract_measurements raises MissingMeasurementError for absent direct meas.

        With raise_on_missing=True, the first 'direct' measurement that cannot
        be resolved from the viatar data raises instead of being silently logged.
        This implements AGENTS.md rule 2: no imputation, ever.
        """
        # An empty dict has no sections → all paths fail to resolve.
        empty_viatar: dict = {}
        with pytest.raises(MissingMeasurementError):
            self._adapter.extract_measurements(empty_viatar, raise_on_missing=True)
