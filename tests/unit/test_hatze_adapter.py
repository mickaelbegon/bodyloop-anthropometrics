"""Unit tests for the Hatze (1979) extraction adapter.

These tests never touch the BodyLoop API and never use real subject data: the
scan is a :class:`unittest.mock.MagicMock` whose sections are built from the
``bodyloop_path`` values of the mapping file itself, so the fixture cannot
silently drift away from ``configs/bodyloop_to_hatze.yaml``.

The scientific content of the adapter is, by design, a set of refusals: the
equations mapping Hatze's measurements onto primitive parameters are not
available (see ``docs/HATZE_EQUATIONS.md`` §5).  These tests therefore assert
that the adapter fails loudly rather than that it computes anything.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from bodyloop_anthropometrics.anthropometry.hatze_adapter import (
    BLOCKED_PRIMITIVES,
    EXPECTED_MEASUREMENT_COUNT,
    HATZE_SEGMENTS,
    MAPPING_FILE,
    HatzeAdapter,
    MissingMeasurementError,
    assert_primitive_usable,
)
from bodyloop_anthropometrics.anthropometry.measurement_mapping import MeasurementSet

#: Required note on every entry feeding the blocked octoparaboloid primitive.
A14_NOTE_FRAGMENT = "A1.4 primitive coefficients wrong"

#: Value written into every synthetic scan field, in metres.
SYNTHETIC_VALUE_M = 0.1


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def adapter() -> HatzeAdapter:
    """Return a :class:`HatzeAdapter` on the repository mapping file.

    Returns
    -------
    HatzeAdapter
        Adapter using ``configs/bodyloop_to_hatze.yaml``.
    """
    return HatzeAdapter()


@pytest.fixture(scope="module")
def mapping(adapter: HatzeAdapter) -> dict[str, dict[str, Any]]:
    """Return the parsed Hatze mapping.

    Parameters
    ----------
    adapter : HatzeAdapter
        Adapter fixture.

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping of Hatze key to mapping entry.
    """
    return adapter.load_mapping()


def _build_viatar(mapping: dict[str, dict[str, Any]], unit: str = "m") -> MagicMock:
    """Build a synthetic scan covering every resolvable ``bodyloop_path``.

    Parameters
    ----------
    mapping : dict[str, dict[str, Any]]
        Parsed Hatze mapping.
    unit : str, optional
        Native unit advertised by every synthetic object.  Default ``"m"``.

    Returns
    -------
    MagicMock
        Object exposing the same sections as
        :class:`~bodyloop_anthropometrics.api.schemas.ViatarData`.

    Notes
    -----
    Every field is filled with the same value: these tests check provenance and
    coverage bookkeeping, never numerical results (there are none to check).
    """
    scale = {"m": 1.0, "mm": 1000.0, "cm": 100.0}.get(unit, 1.0)
    sections: dict[str, dict[str, MagicMock]] = {}
    for entry in mapping.values():
        path = entry.get("bodyloop_path")
        if not path:
            continue
        section, label, field = str(path).split(".")
        item = sections.setdefault(section, {}).get(label)
        if item is None:
            item = MagicMock()
            item.label = label
            item.unit = unit if entry.get("unit") != "rad" else "rad"
            sections[section][label] = item
        setattr(item, field, SYNTHETIC_VALUE_M * scale)

    viatar = MagicMock()
    for section, items in sections.items():
        setattr(viatar, section, list(items.values()))
    return viatar


@pytest.fixture
def viatar(mapping: dict[str, dict[str, Any]]) -> MagicMock:
    """Return a synthetic scan in metres.

    Parameters
    ----------
    mapping : dict[str, dict[str, Any]]
        Parsed Hatze mapping.

    Returns
    -------
    MagicMock
        Synthetic scan.
    """
    return _build_viatar(mapping)


@pytest.fixture
def empty_viatar() -> MagicMock:
    """Return a scan whose every section is empty.

    Returns
    -------
    MagicMock
        Scan with no markers, distances, heights, cross-sections or angles.
    """
    viatar = MagicMock()
    for section in (
        "markers",
        "axes",
        "distances",
        "heights",
        "crosssections",
        "crosssection_series",
        "angles",
    ):
        setattr(viatar, section, [])
    return viatar


# ---------------------------------------------------------------------------
# load_mapping
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestLoadMapping:
    """Tests for :meth:`HatzeAdapter.load_mapping`."""

    def test_returns_at_least_200_keys(self, mapping: dict[str, dict[str, Any]]) -> None:
        """The mapping covers Hatze's measurement set, not a sample of it."""
        assert len(mapping) >= 200
        assert len(mapping) == EXPECTED_MEASUREMENT_COUNT

    def test_default_path_is_the_repository_config(self, adapter: HatzeAdapter) -> None:
        """The default mapping file is ``configs/bodyloop_to_hatze.yaml``."""
        assert adapter.config_path == MAPPING_FILE
        assert MAPPING_FILE.is_file()

    def test_every_entry_declares_a_source(self, mapping: dict[str, dict[str, Any]]) -> None:
        """AGENTS.md rule 3: provenance is mandatory on every entry."""
        for key, entry in mapping.items():
            assert entry.get("source") in {
                "direct",
                "calculated",
                "interpolated",
                "external",
                "manual",
            }, key

    def test_every_entry_names_a_valid_segment(
        self, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """Each measurement belongs to one of the 17 Hatze segments."""
        for key, entry in mapping.items():
            assert entry["segment"] in HATZE_SEGMENTS, key

    def test_all_17_segments_are_covered(self, mapping: dict[str, dict[str, Any]]) -> None:
        """No Hatze segment is left without measurements."""
        covered = {entry["segment"] for entry in mapping.values()}
        assert covered == set(HATZE_SEGMENTS)

    def test_provisional_paths_carry_a_todo_scientific_note(
        self, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """Every entry flags that the BodyLoop path vocabulary is unconfirmed."""
        for key, entry in mapping.items():
            assert "TODO_SCIENTIFIC" in str(entry.get("path_note", "")), key

    def test_a14_entries_are_blocked_and_documented(
        self, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """Entries feeding A1.4 are marked blocked and point at the audit."""
        a14 = [k for k, e in mapping.items() if e.get("primitive") in BLOCKED_PRIMITIVES]
        assert a14, "the mapping must record which measurements feed A1.4"
        for key in a14:
            entry = mapping[key]
            assert entry.get("blocked") is True, key
            assert A14_NOTE_FRAGMENT in str(entry.get("notes", "")), key
            assert "HATZE_PRIMITIVES_AUDIT.md" in str(entry.get("notes", "")), key

    def test_no_interpolated_entry_without_notes(
        self, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """An interpolated value without an explanation is a silent imputation."""
        for key, entry in mapping.items():
            if entry.get("source") == "interpolated":
                assert entry.get("notes"), key

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """A mapping file that does not exist is an error, not an empty mapping."""
        with pytest.raises(FileNotFoundError):
            HatzeAdapter(tmp_path / "absent.yaml").load_mapping()

    def test_truncated_mapping_raises(self, tmp_path: Path) -> None:
        """A mapping with whole segments missing is rejected."""
        path = tmp_path / "short.yaml"
        path.write_text(
            yaml.safe_dump({"h1_s01_ml": {"source": "direct", "segment": 1}}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="whole segments"):
            HatzeAdapter(path).load_mapping()

    def test_entry_without_source_raises(
        self, tmp_path: Path, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """A mapping entry with no ``source`` is rejected (AGENTS.md rule 3)."""
        broken = {k: dict(v) for k, v in mapping.items()}
        first = next(iter(broken))
        broken[first].pop("source")
        path = tmp_path / "nosource.yaml"
        path.write_text(yaml.safe_dump(broken), encoding="utf-8")
        with pytest.raises(ValueError, match="no 'source' field"):
            HatzeAdapter(path).load_mapping()

    def test_unmarked_blocked_primitive_raises(
        self, tmp_path: Path, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """An A1.4 entry that forgot ``blocked: true`` is rejected."""
        broken = {k: dict(v) for k, v in mapping.items()}
        key = next(k for k, e in broken.items() if e.get("primitive") in BLOCKED_PRIMITIVES)
        broken[key].pop("blocked")
        path = tmp_path / "unblocked.yaml"
        path.write_text(yaml.safe_dump(broken), encoding="utf-8")
        with pytest.raises(ValueError, match="blocked"):
            HatzeAdapter(path).load_mapping()


# ---------------------------------------------------------------------------
# extract_measurements
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestExtractMeasurements:
    """Tests for :meth:`HatzeAdapter.extract_measurements`."""

    def test_returns_a_measurement_set_with_consistent_coverage(
        self,
        adapter: HatzeAdapter,
        viatar: MagicMock,
        mapping: dict[str, dict[str, Any]],
    ) -> None:
        """Present + missing accounts for every mapped key, exactly once."""
        result = adapter.extract_measurements(
            viatar, subject_id="S001", acquisition_date="2026-09-12"
        )
        assert isinstance(result, MeasurementSet)
        report = result.coverage_report()
        assert report["total"] == len(mapping)
        assert report["present"] + report["missing"] == len(mapping)
        assert set(result.measurements) & set(result.missing) == set()

        resolvable = sum(1 for e in mapping.values() if e.get("bodyloop_path"))
        assert report["present"] == resolvable
        assert report["missing"] == len(mapping) - resolvable

    def test_entries_without_a_path_are_reported_not_imputed(
        self,
        adapter: HatzeAdapter,
        viatar: MagicMock,
        mapping: dict[str, dict[str, Any]],
    ) -> None:
        """AGENTS.md rule 2: a non-derivable quantity is missing, never guessed."""
        result = adapter.extract_measurements(viatar)
        for key, entry in mapping.items():
            if not entry.get("bodyloop_path"):
                assert key in result.missing, key
                assert key not in result.measurements, key

    def test_every_measurement_has_a_source(
        self, adapter: HatzeAdapter, viatar: MagicMock
    ) -> None:
        """AGENTS.md rule 3: no measurement may omit its provenance."""
        result = adapter.extract_measurements(viatar)
        assert result.measurements
        for key, measurement in result.measurements.items():
            assert measurement.source is not None, key
            assert measurement.source in {
                "direct",
                "calculated",
                "interpolated",
                "external",
                "manual",
            }, key

    def test_no_interpolated_measurement_without_notes(
        self, adapter: HatzeAdapter, viatar: MagicMock
    ) -> None:
        """An interpolated value must always explain itself."""
        result = adapter.extract_measurements(viatar)
        for key, measurement in result.measurements.items():
            if measurement.source == "interpolated":
                assert measurement.notes, key

    def test_internal_units_are_metres_and_radians(
        self, adapter: HatzeAdapter, viatar: MagicMock
    ) -> None:
        """AGENTS.md rule 5: nothing leaves the adapter in a native unit."""
        result = adapter.extract_measurements(viatar)
        assert {m.unit for m in result.measurements.values()} <= {"m", "rad"}

    def test_millimetre_input_is_converted_to_metres(
        self, adapter: HatzeAdapter, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """A scan reported in mm yields metres, not a factor-1000 error."""
        result = adapter.extract_measurements(_build_viatar(mapping, unit="mm"))
        lengths = [m.value for m in result.measurements.values() if m.unit == "m"]
        assert lengths
        assert all(value == pytest.approx(SYNTHETIC_VALUE_M) for value in lengths)

    def test_unknown_unit_makes_the_measurement_missing(
        self, adapter: HatzeAdapter, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """An unconvertible unit is reported, never guessed at."""
        result = adapter.extract_measurements(_build_viatar(mapping, unit="furlong"))
        # Angular quantities keep their own native unit and are unaffected; every
        # length becomes missing rather than being silently mis-scaled.
        assert {m.unit for m in result.measurements.values()} <= {"rad"}
        lengths = [k for k, e in mapping.items() if e.get("unit") != "rad"]
        assert set(lengths) <= set(result.missing)

    def test_blocked_measurements_carry_the_warning(
        self,
        adapter: HatzeAdapter,
        viatar: MagicMock,
        mapping: dict[str, dict[str, Any]],
    ) -> None:
        """A measurement feeding A1.4 says so in its notes."""
        result = adapter.extract_measurements(viatar)
        blocked = [
            key
            for key, entry in mapping.items()
            if entry.get("blocked") and key in result.measurements
        ]
        assert blocked
        for key in blocked:
            assert A14_NOTE_FRAGMENT in str(result.measurements[key].notes), key

    def test_raises_missing_measurement_error_for_a_direct_gap(
        self, adapter: HatzeAdapter, empty_viatar: MagicMock
    ) -> None:
        """``raise_on_missing=True`` refuses to proceed without a direct value."""
        with pytest.raises(MissingMeasurementError) as excinfo:
            adapter.extract_measurements(empty_viatar, raise_on_missing=True)
        assert excinfo.value.key
        assert "unavailable" in str(excinfo.value)

    def test_does_not_raise_by_default(
        self, adapter: HatzeAdapter, empty_viatar: MagicMock
    ) -> None:
        """Without ``raise_on_missing`` the gaps are reported, not fatal."""
        result = adapter.extract_measurements(empty_viatar)
        assert result.measurements == {}
        assert len(result.missing) == EXPECTED_MEASUREMENT_COUNT

    def test_derived_gaps_never_raise(
        self, adapter: HatzeAdapter, viatar: MagicMock, mapping: dict[str, dict[str, Any]]
    ) -> None:
        """Absent *derived* quantities are expected, so they are only reported."""
        result = adapter.extract_measurements(viatar, raise_on_missing=True)
        assert result.missing
        for key in result.missing:
            assert mapping[key]["source"] != "direct", key

    def test_none_scan_raises_value_error(self, adapter: HatzeAdapter) -> None:
        """A ``None`` scan is a programming error, not an empty measurement set."""
        with pytest.raises(ValueError, match="viatar_data"):
            adapter.extract_measurements(None)


# ---------------------------------------------------------------------------
# compute_primitive_params / export_segment_bsp
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestBlockedComputations:
    """The adapter must refuse every computation it cannot justify."""

    @pytest.fixture
    def measurements(self, adapter: HatzeAdapter, viatar: MagicMock) -> MeasurementSet:
        """Return an extracted measurement set.

        Parameters
        ----------
        adapter : HatzeAdapter
            Adapter fixture.
        viatar : MagicMock
            Synthetic scan.

        Returns
        -------
        MeasurementSet
            Extracted measurements.
        """
        return adapter.extract_measurements(viatar)

    @pytest.mark.parametrize("segment_id", sorted(HATZE_SEGMENTS))
    def test_compute_primitive_params_not_implemented(
        self, adapter: HatzeAdapter, measurements: MeasurementSet, segment_id: int
    ) -> None:
        """Every segment refuses: Hatze (1979) section 3 is not available."""
        with pytest.raises(NotImplementedError) as excinfo:
            adapter.compute_primitive_params(measurements, segment_id)
        message = str(excinfo.value)
        assert "TODO_SCIENTIFIC" in message
        assert "Hatze" in message

    def test_unknown_segment_raises_value_error(
        self, adapter: HatzeAdapter, measurements: MeasurementSet
    ) -> None:
        """Segment numbers outside 1-17 are rejected before anything else."""
        for bad in (0, 18, -1):
            with pytest.raises(ValueError, match="17 Hatze segments"):
                adapter.compute_primitive_params(measurements, bad)

    def test_a14_raises_runtime_error_unconditionally(
        self, adapter: HatzeAdapter, measurements: MeasurementSet
    ) -> None:
        """A1.4 is blocked: a RuntimeError, never a warning."""
        with pytest.raises(RuntimeError) as excinfo:
            adapter.compute_primitive_params(measurements, 11, primitive="A1.4")
        assert "BLOCKED" in str(excinfo.value)
        assert "HATZE_PRIMITIVES_AUDIT.md" in str(excinfo.value)

    @pytest.mark.parametrize("segment_id", sorted(HATZE_SEGMENTS))
    def test_a14_is_blocked_for_every_segment(
        self, adapter: HatzeAdapter, measurements: MeasurementSet, segment_id: int
    ) -> None:
        """The block does not depend on which segment asks for A1.4."""
        with pytest.raises(RuntimeError):
            adapter.compute_primitive_params(measurements, segment_id, primitive="A1.4")

    def test_assert_primitive_usable(self) -> None:
        """The guard blocks A1.4 and passes every audited primitive."""
        with pytest.raises(RuntimeError, match="BLOCKED"):
            assert_primitive_usable("A1.4")
        for primitive in ("A1.1", "A1.2", "A1.3", "A1.5", "A1.6", "A1.7", "A1.8", "A1.9"):
            assert_primitive_usable(primitive)

    def test_export_segment_bsp_not_implemented(
        self, adapter: HatzeAdapter, measurements: MeasurementSet
    ) -> None:
        """BSP export names the three missing pieces instead of inventing them."""
        with pytest.raises(NotImplementedError) as excinfo:
            adapter.export_segment_bsp(measurements)
        message = str(excinfo.value)
        assert "TODO_SCIENTIFIC" in message
        assert "Hatze (1979)" in message


# ---------------------------------------------------------------------------
# coverage_table
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestCoverageTable:
    """Tests for :meth:`HatzeAdapter.coverage_table`."""

    def test_returns_a_non_empty_string(
        self, adapter: HatzeAdapter, viatar: MagicMock
    ) -> None:
        """The table renders and carries the subject header."""
        rendered = adapter.coverage_table(adapter.extract_measurements(viatar, subject_id="S1"))
        assert isinstance(rendered, str)
        assert rendered.strip()
        assert "Hatze measurement coverage" in rendered
        assert "S1" in rendered

    def test_reports_missing_and_blocked_rows(
        self,
        adapter: HatzeAdapter,
        viatar: MagicMock,
        empty_viatar: MagicMock,
    ) -> None:
        """Gaps and blocked primitives are visible in the rendered table."""
        assert "MISSING" in adapter.coverage_table(
            adapter.extract_measurements(empty_viatar)
        )
        rendered = adapter.coverage_table(adapter.extract_measurements(viatar))
        assert "BLOCKED" in rendered
        assert "A1.4" in rendered

    def test_summary_line_counts_every_mapped_key(
        self,
        adapter: HatzeAdapter,
        viatar: MagicMock,
        mapping: dict[str, dict[str, Any]],
    ) -> None:
        """The summary reports coverage against the full mapping."""
        result = adapter.extract_measurements(viatar)
        rendered = adapter.coverage_table(result)
        report = result.coverage_report()
        assert f"{report['present']}/{len(mapping)} mapped keys present" in rendered
