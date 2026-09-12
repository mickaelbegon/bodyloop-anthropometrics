"""Unit tests for BodyLoop API Pydantic schemas.

Covers type validation, constraint enforcement, JSON serialisation/
deserialisation, and optional None values.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from bodyloop_anthropometrics.api.schemas import (
    Angle,
    Axis,
    CrossSection,
    CrossSectionSeries,
    Distance,
    ExportOptions,
    Height,
    Marker3D,
    ModelInfo,
    Properties,
    ViatarData,
)


# ---------------------------------------------------------------------------
# Marker3D
# ---------------------------------------------------------------------------


class TestMarker3D:
    """Tests for the Marker3D schema."""

    def test_valid_marker(self) -> None:
        """Marker3D parses a valid dict without errors."""
        m = Marker3D(x=1.0, y=2.0, z=3.0, label="LASI")
        assert m.x == pytest.approx(1.0)
        assert m.label == "LASI"
        assert m.confidence is None

    def test_marker_with_confidence(self) -> None:
        """Marker3D stores confidence when provided."""
        m = Marker3D(x=0.0, y=0.0, z=0.0, label="RASI", confidence=0.95)
        assert m.confidence == pytest.approx(0.95)

    def test_marker_requires_label(self) -> None:
        """Marker3D raises ValidationError when label is missing."""
        with pytest.raises(ValidationError):
            Marker3D(x=1.0, y=2.0, z=3.0)  # type: ignore[call-arg]

    def test_marker_requires_numeric_coordinates(self) -> None:
        """Marker3D raises ValidationError when coordinates are non-numeric."""
        with pytest.raises(ValidationError):
            Marker3D(x="bad", y=2.0, z=3.0, label="X")  # type: ignore[arg-type]

    def test_marker_json_roundtrip(self) -> None:
        """Marker3D serialises to JSON and deserialises back correctly."""
        m = Marker3D(x=10.5, y=-3.2, z=100.0, label="TEST", confidence=0.8)
        json_str = m.model_dump_json()
        m2 = Marker3D.model_validate_json(json_str)
        assert m2.label == m.label
        assert m2.x == pytest.approx(m.x)
        assert m2.confidence == pytest.approx(m.confidence)


# ---------------------------------------------------------------------------
# Axis
# ---------------------------------------------------------------------------


class TestAxis:
    """Tests for the Axis schema."""

    def _make_marker(self, label: str = "M") -> Marker3D:
        return Marker3D(x=0.0, y=0.0, z=1.0, label=label)

    def test_valid_axis(self) -> None:
        """Axis parses correctly from valid nested Marker3D objects."""
        a = Axis(
            origin=self._make_marker("origin"),
            direction=self._make_marker("dir"),
            label="longitudinal",
        )
        assert a.label == "longitudinal"
        assert isinstance(a.origin, Marker3D)

    def test_axis_from_dict(self) -> None:
        """Axis.model_validate accepts nested dicts."""
        data = {
            "origin": {"x": 0.0, "y": 0.0, "z": 0.0, "label": "O"},
            "direction": {"x": 0.0, "y": 1.0, "z": 0.0, "label": "D"},
            "label": "sagittal",
        }
        a = Axis.model_validate(data)
        assert a.direction.y == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------


class TestDistance:
    """Tests for the Distance schema."""

    def test_valid_distance(self) -> None:
        """Distance parses correctly with all fields."""
        d = Distance(value=350.0, unit="mm", label="shoulder_width", left_right="bilateral")
        assert d.value == pytest.approx(350.0)
        assert d.left_right == "bilateral"

    def test_distance_left_right_optional(self) -> None:
        """Distance.left_right defaults to None."""
        d = Distance(value=100.0, unit="mm", label="test")
        assert d.left_right is None

    def test_distance_left_right_invalid(self) -> None:
        """Distance raises ValidationError for unknown laterality values."""
        with pytest.raises(ValidationError):
            Distance(value=1.0, unit="mm", label="x", left_right="centre")  # type: ignore[arg-type]

    def test_distance_valid_lateralities(self) -> None:
        """Distance accepts all valid laterality literals."""
        for side in ("left", "right", "bilateral"):
            d = Distance(value=1.0, unit="mm", label="x", left_right=side)
            assert d.left_right == side


# ---------------------------------------------------------------------------
# Height
# ---------------------------------------------------------------------------


class TestHeight:
    """Tests for the Height schema."""

    def test_valid_height(self) -> None:
        """Height parses correctly."""
        h = Height(value=1750.0, unit="mm", label="standing_height")
        assert h.value == pytest.approx(1750.0)
        assert h.unit == "mm"


# ---------------------------------------------------------------------------
# CrossSection
# ---------------------------------------------------------------------------


class TestCrossSection:
    """Tests for the CrossSection schema."""

    def test_valid_cross_section(self) -> None:
        """CrossSection parses with all fields."""
        cs = CrossSection(
            perimeter=300.0,
            area=7000.0,
            width_ml=100.0,
            depth_ap=80.0,
            unit="mm",
            position=0.5,
            label="thigh_50pct",
        )
        assert cs.area == pytest.approx(7000.0)
        assert cs.width_ml == pytest.approx(100.0)

    def test_cross_section_optional_fields_none(self) -> None:
        """CrossSection width_ml and depth_ap default to None."""
        cs = CrossSection(
            perimeter=200.0, area=3000.0, unit="mm", position=0.3, label="test"
        )
        assert cs.width_ml is None
        assert cs.depth_ap is None


# ---------------------------------------------------------------------------
# CrossSectionSeries
# ---------------------------------------------------------------------------


class TestCrossSectionSeries:
    """Tests for the CrossSectionSeries schema."""

    def _make_cs(self, pos: float) -> CrossSection:
        return CrossSection(perimeter=200.0, area=3000.0, unit="mm", position=pos, label=f"s{pos}")

    def test_valid_series(self) -> None:
        """CrossSectionSeries stores an ordered list of cross-sections."""
        series = CrossSectionSeries(
            label="right_thigh",
            sections=[self._make_cs(0.2), self._make_cs(0.5), self._make_cs(0.8)],
            axis_label="longitudinal_axis",
        )
        assert len(series.sections) == 3
        assert series.axis_label == "longitudinal_axis"

    def test_empty_series(self) -> None:
        """CrossSectionSeries accepts an empty sections list."""
        series = CrossSectionSeries(label="empty", sections=[], axis_label="ax")
        assert series.sections == []


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    """Tests for the Properties schema and its validators."""

    def test_valid_properties(self) -> None:
        """Properties parses with valid positive mass and height."""
        p = Properties(mass_kg=75.0, height_m=1.80, age_years=25.0, sex="female")
        assert p.mass_kg == pytest.approx(75.0)
        assert p.sex == "female"

    def test_mass_negative_raises(self) -> None:
        """Negative mass raises ValidationError."""
        with pytest.raises(ValidationError, match="mass_kg"):
            Properties(mass_kg=-5.0)

    def test_mass_zero_raises(self) -> None:
        """Zero mass raises ValidationError."""
        with pytest.raises(ValidationError, match="mass_kg"):
            Properties(mass_kg=0.0)

    def test_height_zero_raises(self) -> None:
        """Zero height raises ValidationError."""
        with pytest.raises(ValidationError, match="height_m"):
            Properties(height_m=0.0)

    def test_height_negative_raises(self) -> None:
        """Negative height raises ValidationError."""
        with pytest.raises(ValidationError, match="height_m"):
            Properties(height_m=-1.70)

    def test_all_none_valid(self) -> None:
        """Properties with all fields None is valid."""
        p = Properties()
        assert p.mass_kg is None
        assert p.height_m is None
        assert p.sex is None
        assert p.bmi is None

    def test_invalid_sex_value(self) -> None:
        """Unknown sex value raises ValidationError."""
        with pytest.raises(ValidationError):
            Properties(sex="unknown")  # type: ignore[arg-type]

    def test_properties_json_roundtrip(self) -> None:
        """Properties serialises to JSON and deserialises back."""
        p = Properties(mass_kg=80.0, height_m=1.85, sex="male", bmi=23.4)
        json_str = p.model_dump_json()
        p2 = Properties.model_validate_json(json_str)
        assert p2.mass_kg == pytest.approx(80.0)
        assert p2.sex == "male"


# ---------------------------------------------------------------------------
# Angle
# ---------------------------------------------------------------------------


class TestAngle:
    """Tests for the Angle schema."""

    def test_valid_angle(self) -> None:
        """Angle parses correctly."""
        a = Angle(value=45.0, unit="deg", label="knee_flexion")
        assert a.value == pytest.approx(45.0)
        assert a.unit == "deg"


# ---------------------------------------------------------------------------
# ModelInfo
# ---------------------------------------------------------------------------


class TestModelInfo:
    """Tests for the ModelInfo schema."""

    def test_valid_model_info_with_url(self) -> None:
        """ModelInfo stores URL when provided."""
        m = ModelInfo(model_type="mesh_3d", format="glb", url="https://example.com/m.glb")
        assert m.url == "https://example.com/m.glb"

    def test_model_info_url_optional(self) -> None:
        """ModelInfo.url defaults to None."""
        m = ModelInfo(model_type="avatar_3d", format="glb")
        assert m.url is None


# ---------------------------------------------------------------------------
# ViatarData
# ---------------------------------------------------------------------------


class TestViatarData:
    """Tests for the ViatarData aggregate schema."""

    def test_minimal_viatar_data(self) -> None:
        """ViatarData is valid with only viatar_id set."""
        vd = ViatarData(viatar_id="viatar-001")
        assert vd.viatar_id == "viatar-001"
        assert vd.markers == []
        assert isinstance(vd.properties, Properties)

    def test_viatar_data_with_markers(self) -> None:
        """ViatarData stores markers correctly."""
        markers = [Marker3D(x=0.0, y=0.0, z=0.0, label="LASI")]
        vd = ViatarData(viatar_id="viatar-002", markers=markers)
        assert len(vd.markers) == 1
        assert vd.markers[0].label == "LASI"

    def test_viatar_data_json_roundtrip(self) -> None:
        """ViatarData serialises to dict and back without data loss."""
        vd = ViatarData(
            viatar_id="viatar-json",
            heights=[Height(value=1800.0, unit="mm", label="standing")],
        )
        payload = vd.model_dump(mode="json")
        vd2 = ViatarData.model_validate(payload)
        assert vd2.viatar_id == "viatar-json"
        assert len(vd2.heights) == 1
        assert vd2.heights[0].value == pytest.approx(1800.0)


# ---------------------------------------------------------------------------
# ExportOptions
# ---------------------------------------------------------------------------


class TestExportOptions:
    """Tests for the ExportOptions schema."""

    def test_defaults(self) -> None:
        """ExportOptions has sensible defaults."""
        opts = ExportOptions()
        assert opts.measurements_format == "json"
        assert opts.mesh_3d_format == "glb"
        assert opts.avatar_3d_format == "glb"

    def test_custom_formats(self) -> None:
        """ExportOptions accepts custom format strings."""
        opts = ExportOptions(
            measurements_format="csv",
            contour_format="ply",
            mesh_3d_format="obj",
            avatar_3d_format="fbx",
        )
        assert opts.measurements_format == "csv"
        assert opts.mesh_3d_format == "obj"
