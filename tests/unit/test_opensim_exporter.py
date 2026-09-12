"""Unit tests for the OpenSim 4.x .osim exporter.

All tests are isolated (no I/O other than tmp_path) and use synthetic data
only — no patient information or real BodyLoop scans (AGENTS.md security rule).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from bodyloop_anthropometrics.export.opensim_exporter import (
    OpenSimBody,
    OpenSimExporter,
    _tensor_to_6,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def exporter() -> OpenSimExporter:
    """Return a default OpenSimExporter loaded from the bundled YAML."""
    return OpenSimExporter()


@pytest.fixture()
def minimal_yeadon_params() -> dict:
    """Minimal Yeadon-style params dict covering a few bodies.

    Keys match the ``yeadon_segment`` labels used in
    ``configs/opensim_joint_correspondence.yaml``.
    Diagonal inertia for simplicity; products of inertia = 0.
    """
    def _seg(mass, com, ixx, iyy, izz):
        return {
            "mass_kg": mass,
            "com_m": com,
            "inertia_tensor_kgm2": [
                [ixx, 0.0, 0.0],
                [0.0, iyy, 0.0],
                [0.0, 0.0, izz],
            ],
        }

    return {
        "P": _seg(11.5, [0.0, 0.0, 0.0], 0.085, 0.091, 0.051),   # pelvis
        "T": _seg(20.1, [0.0, 0.0, 0.25], 0.180, 0.170, 0.090),  # torso
        "C": _seg(4.5,  [0.0, 0.0, 0.08], 0.022, 0.019, 0.014),  # head
        "A1": _seg(1.9, [0.0, 0.0, -0.15], 0.011, 0.011, 0.002), # upper_arm_l
        "B1": _seg(1.9, [0.0, 0.0, -0.15], 0.011, 0.011, 0.002), # upper_arm_r
        "A2": _seg(1.4, [0.0, 0.0, -0.13], 0.008, 0.008, 0.001), # radius_l
        "B2": _seg(1.4, [0.0, 0.0, -0.13], 0.008, 0.008, 0.001), # radius_r
        "J1": _seg(7.5, [0.0, 0.0, -0.18], 0.087, 0.087, 0.015), # femur_l
        "K1": _seg(7.5, [0.0, 0.0, -0.18], 0.087, 0.087, 0.015), # femur_r
        "J2": _seg(3.7, [0.0, 0.0, -0.20], 0.044, 0.044, 0.004), # tibia_l
        "K2": _seg(3.7, [0.0, 0.0, -0.20], 0.044, 0.044, 0.004), # tibia_r
        "J3": _seg(1.0, [0.0, 0.05, -0.02], 0.004, 0.001, 0.004), # calcn_l
        "K3": _seg(1.0, [0.0, 0.05, -0.02], 0.004, 0.001, 0.004), # calcn_r
    }


@pytest.fixture()
def osim_bodies(exporter, minimal_yeadon_params) -> list[OpenSimBody]:
    """OpenSimBody list built from the minimal Yeadon params."""
    return exporter.from_yeadon(minimal_yeadon_params)


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_exporter_loads_yaml() -> None:
    """OpenSimExporter() initialises without error from the bundled YAML."""
    exp = OpenSimExporter()
    # The correspondence YAML must define at least 17 bodies (incl. ground).
    assert len(exp._bodies_cfg) >= 17


@pytest.mark.unit
def test_exporter_custom_yaml_not_found(tmp_path: Path) -> None:
    """FileNotFoundError raised when the YAML path does not exist."""
    with pytest.raises(FileNotFoundError, match="not found"):
        OpenSimExporter(correspondence_path=tmp_path / "nonexistent.yaml")


@pytest.mark.unit
def test_exporter_invalid_yaml(tmp_path: Path) -> None:
    """ValueError raised for a YAML without a 'bodies' key."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("key: value\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'bodies'"):
        OpenSimExporter(correspondence_path=bad_yaml)


# ---------------------------------------------------------------------------
# from_yeadon
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_yeadon_returns_list(osim_bodies: list[OpenSimBody]) -> None:
    """from_yeadon with a populated dict returns a non-empty list."""
    assert isinstance(osim_bodies, list)
    assert len(osim_bodies) > 0


@pytest.mark.unit
def test_from_yeadon_returns_opensim_body_instances(osim_bodies: list[OpenSimBody]) -> None:
    """Every element is an OpenSimBody."""
    for body in osim_bodies:
        assert isinstance(body, OpenSimBody)


@pytest.mark.unit
def test_from_yeadon_empty_dict(exporter: OpenSimExporter) -> None:
    """from_yeadon({}) returns an empty list (no matches)."""
    result = exporter.from_yeadon({})
    assert result == []


@pytest.mark.unit
def test_from_yeadon_mass_preserved(
    exporter: OpenSimExporter, minimal_yeadon_params: dict
) -> None:
    """Mass values are preserved to machine precision."""
    bodies = exporter.from_yeadon(minimal_yeadon_params)
    by_name = {b.name: b for b in bodies}
    # pelvis (P) -> pelvis
    assert "pelvis" in by_name
    assert abs(by_name["pelvis"].mass - 11.5) < 1e-9


@pytest.mark.unit
def test_from_yeadon_inertia_shape(osim_bodies: list[OpenSimBody]) -> None:
    """Every OpenSimBody has inertia of shape (6,)."""
    for body in osim_bodies:
        assert body.inertia.shape == (6,), f"body '{body.name}' inertia shape wrong"


@pytest.mark.unit
def test_from_yeadon_mass_center_shape(osim_bodies: list[OpenSimBody]) -> None:
    """Every OpenSimBody has mass_center of shape (3,)."""
    for body in osim_bodies:
        assert body.mass_center.shape == (3,), (
            f"body '{body.name}' mass_center shape wrong"
        )


@pytest.mark.unit
def test_from_yeadon_diagonal_inertia_products_zero(
    exporter: OpenSimExporter, minimal_yeadon_params: dict
) -> None:
    """Products of inertia (Ixy, Ixz, Iyz) are zero for diagonal input."""
    bodies = exporter.from_yeadon(minimal_yeadon_params)
    for body in bodies:
        iv = body.inertia
        assert abs(iv[3]) < 1e-12, f"{body.name}: Ixy={iv[3]}"
        assert abs(iv[4]) < 1e-12, f"{body.name}: Ixz={iv[4]}"
        assert abs(iv[5]) < 1e-12, f"{body.name}: Iyz={iv[5]}"


# ---------------------------------------------------------------------------
# from_body_bsp
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_from_body_bsp_with_empty_segments(exporter: OpenSimExporter) -> None:
    """from_body_bsp with a BodyBSP with no segments returns empty list."""
    from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import BodyBSP

    empty_bsp = BodyBSP(
        segments={},
        total_mass_kg=0.0,
        total_volume_m3=0.0,
        mass_conservation_error=0.0,
        subject_id="test",
    )
    result = exporter.from_body_bsp(empty_bsp)
    assert result == []


@pytest.mark.unit
def test_from_body_bsp_maps_trunk(exporter: OpenSimExporter) -> None:
    """trunk segment maps to 'torso' OpenSim body."""
    from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import BodyBSP, SegmentBSP

    trunk_seg = SegmentBSP(
        name="trunk",
        mass_kg=25.0,
        com_m=np.array([0.0, 0.0, 1.0]),
        inertia_about_com_kgm2=np.eye(3) * 0.5,
        volume_m3=0.025,
        density_kg_m3=1000.0,
        density_source="test",
        validation={"is_valid": True, "issues": []},
    )
    bsp = BodyBSP(
        segments={"trunk": trunk_seg},
        total_mass_kg=25.0,
        total_volume_m3=0.025,
        mass_conservation_error=0.0,
        subject_id="test",
    )
    result = exporter.from_body_bsp(bsp)
    names = [b.name for b in result]
    assert "torso" in names
    torso = next(b for b in result if b.name == "torso")
    assert abs(torso.mass - 25.0) < 1e-9


# ---------------------------------------------------------------------------
# write_osim
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_osim_creates_file(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """write_osim creates a non-empty file at the specified path."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    assert out.exists()
    assert out.stat().st_size > 1024  # non-trivial XML


@pytest.mark.unit
def test_write_osim_valid_xml(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """write_osim produces well-formed XML (parseable by ET.parse)."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    tree = ET.parse(out)
    assert tree.getroot() is not None


@pytest.mark.unit
def test_write_osim_opensim_version(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """Output contains OpenSimDocument Version='40000'."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    content = out.read_text(encoding="utf-8")
    assert 'Version="40000"' in content


@pytest.mark.unit
def test_write_osim_contains_pelvis_body(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """Output contains a <Body name='pelvis'> element."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    tree = ET.parse(out)
    root = tree.getroot()
    bodies = root.findall(".//Body")
    names = [b.get("name") for b in bodies]
    assert "pelvis" in names


@pytest.mark.unit
def test_write_osim_mass_values_accurate(
    exporter: OpenSimExporter,
    minimal_yeadon_params: dict,
    tmp_path: Path,
) -> None:
    """<mass> values in XML match input to 4 decimal places."""
    bodies = exporter.from_yeadon(minimal_yeadon_params)
    out = tmp_path / "model.osim"
    exporter.write_osim(bodies, out)

    tree = ET.parse(out)
    root = tree.getroot()
    mass_by_name: dict[str, float] = {}
    for body_el in root.findall(".//Body"):
        name = body_el.get("name", "")
        mass_el = body_el.find("mass")
        if mass_el is not None and mass_el.text:
            mass_by_name[name] = float(mass_el.text.strip())

    # Pelvis (P -> pelvis): 11.5 kg
    assert "pelvis" in mass_by_name
    assert abs(mass_by_name["pelvis"] - 11.5) < 5e-5  # 4 decimal places


@pytest.mark.unit
def test_write_osim_inertia_six_values(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """Every <inertia> element contains exactly 6 space-separated values."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    tree = ET.parse(out)
    root = tree.getroot()
    for inertia_el in root.findall(".//inertia"):
        text = (inertia_el.text or "").strip()
        values = text.split()
        assert len(values) == 6, (
            f"<inertia> should have 6 values, got {len(values)}: '{text}'"
        )
        for v in values:
            float(v)  # must be parseable as float


@pytest.mark.unit
def test_write_osim_diagonal_products_zero_in_xml(
    exporter: OpenSimExporter,
    minimal_yeadon_params: dict,
    tmp_path: Path,
) -> None:
    """Products of inertia (Ixy, Ixz, Iyz) are ~0 for diagonal input in XML."""
    bodies = exporter.from_yeadon(minimal_yeadon_params)
    out = tmp_path / "model.osim"
    exporter.write_osim(bodies, out)
    tree = ET.parse(out)
    root = tree.getroot()
    for inertia_el in root.findall(".//inertia"):
        parts = (inertia_el.text or "").strip().split()
        if len(parts) == 6:
            ixy, ixz, iyz = float(parts[3]), float(parts[4]), float(parts[5])
            assert abs(ixy) < 1e-9, f"Ixy not zero: {ixy}"
            assert abs(ixz) < 1e-9, f"Ixz not zero: {ixz}"
            assert abs(iyz) < 1e-9, f"Iyz not zero: {iyz}"


@pytest.mark.unit
def test_write_osim_contains_joint_set(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """Output contains a JointSet element."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    tree = ET.parse(out)
    root = tree.getroot()
    assert root.find(".//JointSet") is not None


@pytest.mark.unit
def test_write_osim_contains_marker_set(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """Output contains an empty MarkerSet element."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    tree = ET.parse(out)
    root = tree.getroot()
    assert root.find(".//MarkerSet") is not None


@pytest.mark.unit
def test_write_osim_model_name(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """Model name attribute is written correctly."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out, model_name="test_subject_001")
    tree = ET.parse(out)
    root = tree.getroot()
    model_el = root.find("Model")
    assert model_el is not None
    assert model_el.get("name") == "test_subject_001"


@pytest.mark.unit
def test_write_osim_creates_parent_dirs(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """write_osim creates missing parent directories."""
    out = tmp_path / "subdir" / "nested" / "model.osim"
    exporter.write_osim(osim_bodies, out)
    assert out.exists()


@pytest.mark.unit
def test_write_osim_file_size_exceeds_1kb(
    exporter: OpenSimExporter,
    osim_bodies: list[OpenSimBody],
    tmp_path: Path,
) -> None:
    """Output file size exceeds 1 KB (non-trivial XML)."""
    out = tmp_path / "model.osim"
    exporter.write_osim(osim_bodies, out)
    assert out.stat().st_size > 1024


# ---------------------------------------------------------------------------
# Missing joint centre raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_missing_joint_centre_raises(tmp_path: Path) -> None:
    """ValueError raised when a body in the YAML is missing location_in_parent."""
    broken_yaml = tmp_path / "broken.yaml"
    broken_yaml.write_text(
        """
bodies:
  ground:
    opensim_name: "ground"
    parent: null
    joint: null

  pelvis:
    opensim_name: "pelvis"
    bsp_segment: null
    yeadon_segment: "P"
    hatze_segment: null
    parent: "ground"
    joint:
      name: "ground_pelvis"
      type: "FreeJoint"
      location_in_parent: null
      orientation_in_parent: [0.0, 0.0, 0.0]
      location_in_child: [0.0, 0.0, 0.0]
      orientation_in_child: [0.0, 0.0, 0.0]
    coordinates: []
    notes: ""
""",
        encoding="utf-8",
    )
    exp = OpenSimExporter(correspondence_path=broken_yaml)
    params = {
        "P": {
            "mass_kg": 10.0,
            "com_m": [0.0, 0.0, 0.0],
            "inertia_tensor_kgm2": [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.1]],
        }
    }
    with pytest.raises(ValueError, match="location_in_parent"):
        exp.from_yeadon(params)


# ---------------------------------------------------------------------------
# _tensor_to_6 helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tensor_to_6_diagonal() -> None:
    """_tensor_to_6 extracts correct components from a diagonal tensor."""
    t = np.diag([1.0, 2.0, 3.0])
    result = _tensor_to_6(t)
    np.testing.assert_allclose(result, [1.0, 2.0, 3.0, 0.0, 0.0, 0.0])


@pytest.mark.unit
def test_tensor_to_6_full() -> None:
    """_tensor_to_6 extracts products of inertia correctly."""
    t = np.array(
        [[1.0, 0.1, 0.2], [0.1, 2.0, 0.3], [0.2, 0.3, 3.0]], dtype=np.float64
    )
    result = _tensor_to_6(t)
    np.testing.assert_allclose(result, [1.0, 2.0, 3.0, 0.1, 0.2, 0.3])
