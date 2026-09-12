"""Unit tests for bodyloop_anthropometrics.export.biorbd_exporter.

All tests are marked ``@pytest.mark.unit`` and run without network access,
large mesh files, or the yeadon package.  Fixtures use synthetic data only
(AGENTS.md security rule).

Coverage
--------
- :class:`BiorbdExporter` loads correspondence YAML without error.
- :meth:`from_yeadon` with an empty dict returns an empty list.
- :meth:`from_yeadon` with a minimal matching dict returns BiorbdSegments.
- :meth:`write_biomod` produces a file containing the required keywords.
- :meth:`write_biomod` round-trip: mass in the file matches the input.
- Inertia tensor written to file is symmetric (|I[i,j] - I[j,i]| < 1e-10).
- Missing joint centre raises :exc:`ValueError`, not a silent default.
- All values in the output file are in SI units (metres, kilograms).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import BodyBSP, SegmentBSP
from bodyloop_anthropometrics.export.biorbd_exporter import BiorbdExporter, BiorbdSegment


# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------

def _make_segment_bsp(
    name: str = "head",
    mass_kg: float = 5.0,
    com: tuple[float, float, float] = (0.0, 0.0, 1.7),
    *,
    inertia_scale: float = 0.01,
) -> SegmentBSP:
    """Create a synthetic :class:`SegmentBSP` for testing."""
    return SegmentBSP(
        name=name,
        mass_kg=mass_kg,
        com_m=np.array(com, dtype=np.float64),
        inertia_about_com_kgm2=np.eye(3, dtype=np.float64) * inertia_scale,
        volume_m3=mass_kg / 1100.0,
        density_kg_m3=1100.0,
        density_source="de_Leva_1996",
        validation={},
    )


def _make_body_bsp(segments: dict[str, SegmentBSP]) -> BodyBSP:
    """Wrap a segment dict in a minimal :class:`BodyBSP`."""
    total = sum(s.mass_kg for s in segments.values())
    return BodyBSP(
        segments=segments,
        total_mass_kg=total,
        total_volume_m3=sum(s.volume_m3 for s in segments.values()),
        mass_conservation_error=0.0,
        subject_id="test_subject",
    )


def _simple_correspondence_yaml(tmp_path: Path, *, with_joint_centre: bool = False) -> Path:
    """Write a minimal correspondence YAML for testing write_biomod."""
    jc_line = (
        'joint_centre_bodyloop: "normalized/axes/test_joint/origin"'
        if with_joint_centre
        else "joint_centre_bodyloop: null"
    )
    content = f"""
segments:
  test_seg:
    biorbd_name: TestSeg
    yeadon_segment: null
    bodybsp_segment: null
    hatze_segment: null
    parent: root
    joint_type: free
    dof: [TrX, TrY, TrZ, RotX, RotY, RotZ]
    ranges:
      TrX: [-3.0, 3.0]
      TrY: [-3.0, 3.0]
      TrZ: [-3.0, 3.0]
      RotX: [-3.14159, 3.14159]
      RotY: [-3.14159, 3.14159]
      RotZ: [-3.14159, 3.14159]
    {jc_line}
    notes: "synthetic segment for unit tests"
"""
    yaml_path = tmp_path / "test_corr.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


def _make_biorbd_segment(
    name: str = "TestSeg",
    mass: float = 10.0,
    com: tuple[float, float, float] = (0.0, 0.0, 0.05),
    inertia: list[list[float]] | None = None,
) -> BiorbdSegment:
    """Create a synthetic :class:`BiorbdSegment` for testing."""
    if inertia is None:
        inertia = [[0.10, 0.0, 0.0], [0.0, 0.10, 0.0], [0.0, 0.0, 0.05]]
    return BiorbdSegment(
        name=name,
        mass=mass,
        com=np.array(com, dtype=np.float64),
        inertia=np.array(inertia, dtype=np.float64),
        rt_from_parent=np.eye(4, dtype=np.float64),
    )


def _parse_mass_from_biomod(content: str, segment_name: str) -> float:
    """Extract the mass value from a bioMod segment block by parsing the file.

    Parameters
    ----------
    content : str
        Full text of the .bioMod file.
    segment_name : str
        Segment name to look for.

    Returns
    -------
    float
        Parsed mass value.

    Raises
    ------
    ValueError
        If the segment or its mass line is not found.
    """
    in_seg = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == f"segment {segment_name}":
            in_seg = True
        elif stripped == "endsegment":
            in_seg = False
        elif in_seg and stripped.startswith("mass "):
            return float(stripped.split()[1])
    raise ValueError(f"Mass not found for segment '{segment_name}' in bioMod content")


def _parse_inertia_from_biomod(content: str, segment_name: str) -> np.ndarray:
    """Extract the 3x3 inertia tensor from a bioMod segment block.

    Parameters
    ----------
    content : str
        Full text of the .bioMod file.
    segment_name : str
        Segment name to look for.

    Returns
    -------
    NDArray of shape (3, 3)
        Inertia tensor as parsed from the file.

    Raises
    ------
    ValueError
        If the segment or inertia block is not found.
    """
    in_seg = False
    in_inertia = False
    rows: list[list[float]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == f"segment {segment_name}":
            in_seg = True
        elif stripped == "endsegment":
            in_seg = False
            in_inertia = False
        elif in_seg and stripped == "inertia":
            in_inertia = True
        elif in_inertia:
            parts = stripped.split()
            if len(parts) == 3:
                rows.append([float(v) for v in parts])
                if len(rows) == 3:
                    break
            else:
                in_inertia = False
    if len(rows) != 3:
        raise ValueError(f"Inertia block not found for segment '{segment_name}'")
    return np.array(rows, dtype=np.float64)


# ---------------------------------------------------------------------------
# Test: loading
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBiorbdExporterLoading:
    """BiorbdExporter loads the correspondence YAML without error."""

    def test_loads_bundled_yaml(self) -> None:
        """Constructor with no arguments loads the bundled YAML successfully."""
        exporter = BiorbdExporter()
        assert hasattr(exporter, "_segments")
        assert isinstance(exporter._segments, dict)
        assert len(exporter._segments) > 0

    def test_bundled_yaml_has_expected_segments(self) -> None:
        """Bundled YAML contains at least the 17 hierarchy segments."""
        exporter = BiorbdExporter()
        biorbd_names = {cfg["biorbd_name"] for cfg in exporter._segments.values()}
        required = {
            "Pelvis", "Thorax", "Head",
            "ShoulderL", "UpperArmL", "ForearmL", "HandL",
            "ShoulderR", "UpperArmR", "ForearmR", "HandR",
            "ThighL", "ShankL", "FootL",
            "ThighR", "ShankR", "FootR",
        }
        assert required.issubset(biorbd_names), (
            f"Missing segments in YAML: {required - biorbd_names}"
        )

    def test_loads_custom_yaml(self, tmp_path: Path) -> None:
        """Constructor with a custom path loads correctly."""
        yaml_path = _simple_correspondence_yaml(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        assert "test_seg" in exporter._segments

    def test_missing_yaml_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError is raised when the YAML does not exist."""
        with pytest.raises(FileNotFoundError, match="Correspondence YAML not found"):
            BiorbdExporter(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# Test: from_yeadon
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFromYeadon:
    """from_yeadon converts Yeadon output dict to BiorbdSegments."""

    def test_empty_dict_returns_empty_list(self) -> None:
        """Empty Yeadon dict → empty BiorbdSegment list (no match)."""
        exporter = BiorbdExporter()
        result = exporter.from_yeadon({})
        assert result == []

    def test_minimal_matching_dict_returns_segments(self) -> None:
        """A dict with a matching Yeadon label returns the corresponding segment."""
        exporter = BiorbdExporter()
        # Find the first yeadon_segment label defined in the YAML.
        yeadon_label: str | None = None
        for cfg in exporter._segments.values():
            if cfg.get("yeadon_segment"):
                yeadon_label = cfg["yeadon_segment"]
                break
        assert yeadon_label is not None, "YAML has no yeadon_segment entries"

        params: dict[str, Any] = {
            yeadon_label: {
                "mass_kg": 7.5,
                "com_m": [0.01, 0.0, 0.3],
                "inertia_tensor_kgm2": [
                    [0.05, 0.0, 0.0],
                    [0.0, 0.05, 0.0],
                    [0.0, 0.0, 0.02],
                ],
                "frame": "yeadon_global",
            }
        }
        result = exporter.from_yeadon(params)
        assert len(result) == 1
        assert isinstance(result[0], BiorbdSegment)
        assert abs(result[0].mass - 7.5) < 1e-12

    def test_unknown_labels_are_silently_skipped(self) -> None:
        """Keys not in the YAML are ignored, returning an empty list."""
        exporter = BiorbdExporter()
        params: dict[str, Any] = {
            "__nonexistent_label__": {
                "mass_kg": 1.0,
                "com_m": [0.0, 0.0, 0.0],
                "inertia_tensor_kgm2": [[0.0, 0.0, 0.0]] * 3,
                "frame": "test",
            }
        }
        result = exporter.from_yeadon(params)
        assert result == []

    def test_identity_rt_from_parent(self) -> None:
        """from_yeadon always sets rt_from_parent to the 4x4 identity."""
        exporter = BiorbdExporter()
        yeadon_label: str | None = None
        for cfg in exporter._segments.values():
            if cfg.get("yeadon_segment"):
                yeadon_label = cfg["yeadon_segment"]
                break
        assert yeadon_label is not None
        params: dict[str, Any] = {
            yeadon_label: {
                "mass_kg": 1.0,
                "com_m": [0.1, 0.2, 0.3],
                "inertia_tensor_kgm2": [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.05]],
                "frame": "yeadon_global",
            }
        }
        result = exporter.from_yeadon(params)
        assert len(result) == 1
        np.testing.assert_array_equal(result[0].rt_from_parent, np.eye(4))


# ---------------------------------------------------------------------------
# Test: write_biomod
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestWriteBiomod:
    """write_biomod produces valid .bioMod files."""

    def test_produces_version_4(self, tmp_path: Path) -> None:
        """Output file starts with 'version 4'."""
        yaml_path = _simple_correspondence_yaml(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        seg = _make_biorbd_segment()
        out = tmp_path / "model.bioMod"
        exporter.write_biomod([seg], out)
        content = out.read_text(encoding="utf-8")
        assert "version 4" in content

    def test_produces_required_keywords(self, tmp_path: Path) -> None:
        """Output contains 'segment', 'mass', 'inertia', 'com', 'endsegment'."""
        yaml_path = _simple_correspondence_yaml(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        seg = _make_biorbd_segment()
        out = tmp_path / "model.bioMod"
        exporter.write_biomod([seg], out, model_name="UnitTest", source="yeadon")
        content = out.read_text(encoding="utf-8")
        assert "segment TestSeg" in content
        assert "mass " in content
        assert "inertia" in content
        assert "com " in content
        assert "endsegment" in content

    def test_round_trip_mass(self, tmp_path: Path) -> None:
        """Mass written to file matches the input value."""
        yaml_path = _simple_correspondence_yaml(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        expected_mass = 12.345_678
        seg = _make_biorbd_segment(mass=expected_mass)
        out = tmp_path / "model.bioMod"
        exporter.write_biomod([seg], out)
        content = out.read_text(encoding="utf-8")
        parsed = _parse_mass_from_biomod(content, "TestSeg")
        # Six significant figures: relative error < 1e-5
        assert abs(parsed - expected_mass) / expected_mass < 1e-5, (
            f"Round-trip mass mismatch: expected {expected_mass}, got {parsed}"
        )

    def test_inertia_symmetric(self, tmp_path: Path) -> None:
        """Inertia tensor written to file is symmetric (|I[i,j] - I[j,i]| < 1e-10)."""
        yaml_path = _simple_correspondence_yaml(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        inertia = [
            [0.12, 0.01, 0.02],
            [0.01, 0.15, 0.03],
            [0.02, 0.03, 0.08],
        ]
        seg = _make_biorbd_segment(inertia=inertia)
        out = tmp_path / "model.bioMod"
        exporter.write_biomod([seg], out)
        content = out.read_text(encoding="utf-8")
        parsed = _parse_inertia_from_biomod(content, "TestSeg")
        for i in range(3):
            for j in range(3):
                diff = abs(float(parsed[i, j]) - float(parsed[j, i]))
                assert diff < 1e-10, (
                    f"Inertia tensor not symmetric: I[{i},{j}]={parsed[i,j]:.6e} "
                    f"vs I[{j},{i}]={parsed[j,i]:.6e} (diff={diff:.3e})"
                )

    def test_output_creates_parent_directories(self, tmp_path: Path) -> None:
        """write_biomod creates parent directories if they do not exist."""
        yaml_path = _simple_correspondence_yaml(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        seg = _make_biorbd_segment()
        nested = tmp_path / "a" / "b" / "c" / "model.bioMod"
        exporter.write_biomod([seg], nested)
        assert nested.exists()

    def test_multiple_segments_all_present(self, tmp_path: Path) -> None:
        """All segments in the input list appear in the output file."""
        yaml_content = """
segments:
  s1:
    biorbd_name: SegA
    yeadon_segment: null
    bodybsp_segment: null
    hatze_segment: null
    parent: root
    joint_type: revolute
    dof: [RotX]
    ranges:
      RotX: [-1.5, 1.5]
    joint_centre_bodyloop: null
    notes: "test"
  s2:
    biorbd_name: SegB
    yeadon_segment: null
    bodybsp_segment: null
    hatze_segment: null
    parent: SegA
    joint_type: fixed
    dof: []
    ranges: {}
    joint_centre_bodyloop: null
    notes: "test"
"""
        yaml_path = tmp_path / "multi.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        exporter = BiorbdExporter(yaml_path)
        segs = [
            _make_biorbd_segment("SegA", mass=3.0),
            _make_biorbd_segment("SegB", mass=1.5),
        ]
        out = tmp_path / "multi.bioMod"
        exporter.write_biomod(segs, out)
        content = out.read_text(encoding="utf-8")
        assert "segment SegA" in content
        assert "segment SegB" in content

    def test_units_are_si(self, tmp_path: Path) -> None:
        """Values in the output file are in SI units (no implicit conversion)."""
        yaml_path = _simple_correspondence_yaml(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        # Use distinctive SI values that would look very different in cm or g.
        mass_kg = 8.321
        com_m = (0.012, -0.003, 0.045)
        seg = _make_biorbd_segment(mass=mass_kg, com=com_m)
        out = tmp_path / "model.bioMod"
        exporter.write_biomod([seg], out)
        content = out.read_text(encoding="utf-8")

        parsed_mass = _parse_mass_from_biomod(content, "TestSeg")
        # If mass were written in grams it would be ~8321.
        assert abs(parsed_mass - mass_kg) < 0.01, (
            f"Mass appears to be in wrong units: {parsed_mass}"
        )

        # Check com values in content.
        com_line = next(
            (l.strip() for l in content.splitlines() if l.strip().startswith("com ")),
            None,
        )
        assert com_line is not None, "com line not found in output"
        parts = com_line.split()
        cx, cy, cz = float(parts[1]), float(parts[2]), float(parts[3])
        # Values should be in metres (order of magnitude 0.01–0.1), not cm (order 1–10).
        assert abs(cx - com_m[0]) < 1e-4
        assert abs(cy - com_m[1]) < 1e-4
        assert abs(cz - com_m[2]) < 1e-4


# ---------------------------------------------------------------------------
# Test: missing joint centre
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMissingJointCentre:
    """from_body_bsp raises ValueError when a joint centre is required but absent."""

    def _yaml_with_joint_centre(self, tmp_path: Path) -> Path:
        """Write a YAML where test_seg requires a joint centre path."""
        content = """
segments:
  test_seg:
    biorbd_name: TestSeg
    yeadon_segment: null
    bodybsp_segment: "head"
    hatze_segment: 2
    parent: root
    joint_type: revolute
    dof: [RotX, RotY, RotZ]
    ranges:
      RotX: [-0.5, 0.5]
      RotY: [-0.5, 0.5]
      RotZ: [-0.8, 0.8]
    joint_centre_bodyloop: "normalized/axes/cervicothoracic_joint/origin"
    notes: "test segment with joint centre"
"""
        path = tmp_path / "with_jc.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_raises_value_error_when_joint_positions_not_given(self, tmp_path: Path) -> None:
        """Omitting joint_positions when joint_centre_bodyloop is set → ValueError."""
        yaml_path = self._yaml_with_joint_centre(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        body_bsp = _make_body_bsp({"head": _make_segment_bsp("head")})

        with pytest.raises(ValueError, match="joint centre"):
            exporter.from_body_bsp(body_bsp)

    def test_raises_value_error_when_key_missing_from_positions(self, tmp_path: Path) -> None:
        """Providing joint_positions without the required key → ValueError."""
        yaml_path = self._yaml_with_joint_centre(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        body_bsp = _make_body_bsp({"head": _make_segment_bsp("head")})

        with pytest.raises(ValueError, match="joint centre"):
            exporter.from_body_bsp(
                body_bsp,
                joint_positions={"some/other/path": np.zeros(3)},
            )

    def test_succeeds_when_joint_position_provided(self, tmp_path: Path) -> None:
        """Providing the correct joint position succeeds without error."""
        yaml_path = self._yaml_with_joint_centre(tmp_path)
        exporter = BiorbdExporter(yaml_path)
        body_bsp = _make_body_bsp({"head": _make_segment_bsp("head", mass_kg=5.0)})
        jc = np.array([0.0, 0.0, 1.5])

        result = exporter.from_body_bsp(
            body_bsp,
            joint_positions={"normalized/axes/cervicothoracic_joint/origin": jc},
        )
        assert len(result) == 1
        assert result[0].name == "TestSeg"

    def test_null_joint_centre_bodyloop_does_not_raise(self, tmp_path: Path) -> None:
        """A segment with joint_centre_bodyloop: null never raises, even without positions."""
        content = """
segments:
  root_seg:
    biorbd_name: RootSeg
    yeadon_segment: null
    bodybsp_segment: "head"
    hatze_segment: null
    parent: root
    joint_type: free
    dof: [TrX, TrY, TrZ, RotX, RotY, RotZ]
    ranges:
      TrX: [-3.0, 3.0]
      TrY: [-3.0, 3.0]
      TrZ: [-3.0, 3.0]
      RotX: [-3.14159, 3.14159]
      RotY: [-3.14159, 3.14159]
      RotZ: [-3.14159, 3.14159]
    joint_centre_bodyloop: null
    notes: "root segment"
"""
        yaml_path = tmp_path / "null_jc.yaml"
        yaml_path.write_text(content, encoding="utf-8")
        exporter = BiorbdExporter(yaml_path)
        body_bsp = _make_body_bsp({"head": _make_segment_bsp("head")})

        # Should not raise even when joint_positions is None.
        result = exporter.from_body_bsp(body_bsp)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Test: from_body_bsp – basic mapping
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFromBodyBsp:
    """from_body_bsp correctly maps BodyBSP segments to BiorbdSegments."""

    def test_skips_segments_absent_from_body_bsp(self, tmp_path: Path) -> None:
        """Segments in YAML but missing from BodyBSP are silently skipped."""
        content = """
segments:
  head:
    biorbd_name: Head
    yeadon_segment: null
    bodybsp_segment: "head"
    hatze_segment: 2
    parent: root
    joint_type: revolute
    dof: [RotX]
    ranges:
      RotX: [-0.5, 0.5]
    joint_centre_bodyloop: null
    notes: "test"
  trunk:
    biorbd_name: Thorax
    yeadon_segment: null
    bodybsp_segment: "trunk"
    hatze_segment: 1
    parent: root
    joint_type: revolute
    dof: [RotX]
    ranges:
      RotX: [-0.5, 0.5]
    joint_centre_bodyloop: null
    notes: "test"
"""
        yaml_path = tmp_path / "partial.yaml"
        yaml_path.write_text(content, encoding="utf-8")
        exporter = BiorbdExporter(yaml_path)
        # Only "head" is in the BodyBSP — "trunk" is absent.
        body_bsp = _make_body_bsp({"head": _make_segment_bsp("head", mass_kg=5.0)})
        result = exporter.from_body_bsp(body_bsp)
        assert len(result) == 1
        assert result[0].name == "Head"

    def test_mass_preserved(self, tmp_path: Path) -> None:
        """Mass from BodyBSP is transferred unchanged to BiorbdSegment."""
        content = """
segments:
  head_seg:
    biorbd_name: Head
    yeadon_segment: null
    bodybsp_segment: "head"
    hatze_segment: 2
    parent: root
    joint_type: revolute
    dof: [RotX]
    ranges:
      RotX: [-0.5, 0.5]
    joint_centre_bodyloop: null
    notes: "test"
"""
        yaml_path = tmp_path / "mass_test.yaml"
        yaml_path.write_text(content, encoding="utf-8")
        exporter = BiorbdExporter(yaml_path)
        seg = _make_segment_bsp("head", mass_kg=4.876)
        body_bsp = _make_body_bsp({"head": seg})
        result = exporter.from_body_bsp(body_bsp)
        assert len(result) == 1
        assert abs(result[0].mass - 4.876) < 1e-12
