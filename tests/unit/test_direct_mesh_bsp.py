"""Unit tests for :mod:`bodyloop_anthropometrics.anthropometry.direct_mesh_bsp`.

The mesh-cutting tests rely on volume conservation, which is the property that
matters for BSP: cutting a closed mesh at a plane must split its volume exactly,
with both halves watertight, otherwise the mass integrals are meaningless.

The full-body test uses a synthetic humanoid built from primitives (synthetic
data only — AGENTS.md, Security).  It needs a boolean backend and is skipped
when none is installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import (
    SEGMENT_DENSITIES_KG_M3,
    BodyBSP,
    bsp_to_measurements,
    compute_all_bsp,
    compute_body_bsp,
    cut_mesh_at_plane,
    define_segment_boundaries,
    export_bsp_json,
)
from bodyloop_anthropometrics.geometry.mass_properties import (
    check_mesh_integrity,
    compute_volume,
)

pytestmark = pytest.mark.unit

JOINTS: dict[str, np.ndarray] = {
    "head_top": np.array([0.0, 0.0, 1.80]),
    "neck": np.array([0.0, 0.0, 1.55]),
    "left_shoulder": np.array([0.14, 0.0, 1.45]),
    "right_shoulder": np.array([-0.14, 0.0, 1.45]),
    "left_elbow": np.array([0.24, 0.0, 1.15]),
    "right_elbow": np.array([-0.24, 0.0, 1.15]),
    "left_wrist": np.array([0.27, 0.0, 0.90]),
    "right_wrist": np.array([-0.27, 0.0, 0.90]),
    "left_hip": np.array([0.10, 0.0, 0.95]),
    "right_hip": np.array([-0.10, 0.0, 0.95]),
    "left_knee": np.array([0.10, 0.0, 0.52]),
    "right_knee": np.array([-0.10, 0.0, 0.52]),
    "left_ankle": np.array([0.10, 0.0, 0.10]),
    "right_ankle": np.array([-0.10, 0.0, 0.10]),
}


def _limb(start: np.ndarray, end: np.ndarray, radius: float) -> trimesh.Trimesh:
    """Return a capped cylinder spanning two points."""
    return trimesh.creation.cylinder(radius=radius, segment=np.array([start, end]), sections=24)


@pytest.fixture(scope="module")
def humanoid_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write a synthetic watertight humanoid mesh and return its path."""
    pytest.importorskip("manifold3d", reason="boolean union backend required")
    parts = [
        trimesh.creation.icosphere(subdivisions=3, radius=0.11).apply_translation(
            [0.0, 0.0, 1.67]
        ),
        _limb(np.array([0.0, 0.0, 0.90]), np.array([0.0, 0.0, 1.58]), 0.16),
    ]
    for side, sign in (("left", 1.0), ("right", -1.0)):
        parts += [
            _limb(JOINTS[f"{side}_shoulder"], JOINTS[f"{side}_elbow"], 0.045),
            _limb(JOINTS[f"{side}_elbow"], JOINTS[f"{side}_wrist"], 0.038),
            _limb(
                JOINTS[f"{side}_wrist"],
                JOINTS[f"{side}_wrist"] + np.array([sign * 0.02, 0.0, -0.17]),
                0.033,
            ),
            _limb(JOINTS[f"{side}_hip"], JOINTS[f"{side}_knee"], 0.075),
            _limb(JOINTS[f"{side}_knee"], JOINTS[f"{side}_ankle"], 0.055),
            _limb(
                JOINTS[f"{side}_ankle"],
                JOINTS[f"{side}_ankle"] + np.array([0.0, 0.16, -0.06]),
                0.045,
            ),
        ]
    body = trimesh.boolean.union(parts)
    path = tmp_path_factory.mktemp("mesh") / "synthetic_body.obj"
    body.export(path)
    return path


@pytest.fixture(scope="module")
def body_bsp(humanoid_path: Path) -> BodyBSP:
    """Run the full pipeline once on the synthetic humanoid."""
    return compute_body_bsp(
        humanoid_path,
        JOINTS,
        target_mass_kg=70.0,
        sex="male",
        subject_id="SYNTH-01",
    )


def test_cut_mesh_at_plane_conserves_volume() -> None:
    """Both halves are watertight and their volumes sum to the original."""
    cylinder = trimesh.creation.cylinder(radius=0.05, height=0.4, sections=48)
    above, below = cut_mesh_at_plane(
        cylinder, np.array([0.0, 0.0, 0.05]), np.array([0.0, 0.0, 1.0])
    )

    total = compute_volume(cylinder.vertices, cylinder.faces)
    v_above = compute_volume(above.vertices, above.faces)
    v_below = compute_volume(below.vertices, below.faces)

    assert check_mesh_integrity(above.vertices, above.faces)["is_watertight"]
    assert check_mesh_integrity(below.vertices, below.faces)["is_watertight"]
    assert v_above + v_below == pytest.approx(total, rel=1e-12)
    # The plane at z = +0.05 leaves 0.15 m of the 0.4 m height above it.
    assert v_above / total == pytest.approx(0.375, rel=1e-9)


def test_cut_mesh_at_plane_oblique_non_convex_cap() -> None:
    """An oblique cut through a sphere still conserves volume exactly."""
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=0.2)
    above, below = cut_mesh_at_plane(
        sphere, np.array([0.03, 0.0, 0.02]), np.array([0.3, 0.5, 1.0])
    )
    total = compute_volume(sphere.vertices, sphere.faces)
    assert compute_volume(above.vertices, above.faces) + compute_volume(
        below.vertices, below.faces
    ) == pytest.approx(total, rel=1e-12)


def test_cut_mesh_at_plane_misses_mesh() -> None:
    """A plane outside the mesh returns one empty part and the intact mesh."""
    box = trimesh.creation.box(extents=(0.2, 0.2, 0.2))
    above, below = cut_mesh_at_plane(box, np.array([0.0, 0.0, 5.0]), np.array([0.0, 0.0, 1.0]))
    assert len(above.faces) == 0
    assert compute_volume(below.vertices, below.faces) == pytest.approx(0.008, rel=1e-12)


def test_cut_mesh_at_plane_rejects_zero_normal() -> None:
    """A degenerate normal is an error, not a silent no-op."""
    box = trimesh.creation.box(extents=(0.2, 0.2, 0.2))
    with pytest.raises(ValueError, match="non-zero"):
        cut_mesh_at_plane(box, np.zeros(3), np.zeros(3))


def test_define_segment_boundaries_structure() -> None:
    """Every plane carries a unit normal, an origin and the pair it separates."""
    planes = define_segment_boundaries(JOINTS)
    names = [plane["name"] for plane in planes]

    assert "neck" in names
    assert "sagittal_pelvis" in names
    for side in ("left", "right"):
        for joint in ("shoulder", "axilla", "elbow", "wrist", "hip", "knee", "ankle"):
            assert f"{side}_{joint}" in names
    assert len(names) == len(set(names))

    for plane in planes:
        assert np.linalg.norm(plane["normal"]) == pytest.approx(1.0, rel=1e-12)
        assert plane["origin"].shape == (3,)
        assert len(plane["separates"]) == 2


def test_define_segment_boundaries_normals_point_distally() -> None:
    """Joint plane normals point from the proximal towards the distal segment."""
    planes = {plane["name"]: plane for plane in define_segment_boundaries(JOINTS)}
    knee_to_ankle = JOINTS["left_ankle"] - JOINTS["left_knee"]
    assert float(planes["left_knee"]["normal"] @ knee_to_ankle) > 0.0
    assert planes["left_knee"]["separates"] == ("thigh_left", "shank_left")
    assert float(planes["neck"]["normal"] @ (JOINTS["head_top"] - JOINTS["neck"])) > 0.0


def test_define_segment_boundaries_missing_joint() -> None:
    """A missing joint raises instead of being imputed (AGENTS.md rule 2)."""
    incomplete = {k: v for k, v in JOINTS.items() if k != "left_knee"}
    with pytest.raises(KeyError, match="left_knee"):
        define_segment_boundaries(incomplete)


def test_compute_all_bsp_on_box_segment() -> None:
    """Segment BSP of a box matches the analytic prism solution."""
    extents = np.array([0.1, 0.12, 0.4])
    box = trimesh.creation.box(extents=extents)
    box.apply_translation([0.0, 0.0, 0.7])

    result = compute_all_bsp({"thigh_left": box})["thigh_left"]
    density = SEGMENT_DENSITIES_KG_M3["thigh_left"]
    volume = float(np.prod(extents))

    assert result["density_kg_m3"] == density
    assert result["volume_m3"] == pytest.approx(volume, rel=1e-12)
    assert result["mass_kg"] == pytest.approx(density * volume, rel=1e-12)
    assert result["centroid_m"] == pytest.approx([0.0, 0.0, 0.7], abs=1e-12)

    mass = density * volume
    a, b, c = extents
    expected = mass / 12.0 * np.array([b**2 + c**2, a**2 + c**2, a**2 + b**2])
    assert np.diag(result["inertia_tensor_kgm2"]) == pytest.approx(expected, rel=1e-10)
    assert result["validation"]["issues"] == []


def test_compute_all_bsp_rejects_open_mesh() -> None:
    """An open segment mesh is refused rather than integrated incorrectly."""
    box = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
    open_mesh = trimesh.Trimesh(vertices=box.vertices, faces=box.faces[:-2], process=False)
    with pytest.raises(ValueError, match="not watertight"):
        compute_all_bsp({"hand_left": open_mesh})


def test_bsp_to_measurements_and_export(tmp_path: Path) -> None:
    """Measurements carry provenance and survive a JSON round trip."""
    box = trimesh.creation.box(extents=(0.1, 0.1, 0.4))
    measurements = bsp_to_measurements(compute_all_bsp({"shank_left": box}))["shank_left"]

    assert set(measurements) >= {"mass", "volume", "com_x", "ixx", "iyz"}
    assert measurements["mass"].unit == "kg"
    assert measurements["volume"].unit == "m^3"
    assert measurements["ixx"].unit == "kg*m^2"
    for measurement in measurements.values():
        assert measurement.source == "calculated"
        assert measurement.frame == "bodyloop_global"
        assert measurement.manual_validation_required

    destination = tmp_path / "nested" / "bsp.json"
    export_bsp_json({"shank_left": measurements}, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["shank_left"]["mass"]["value"] == pytest.approx(
        measurements["mass"].value
    )
    assert payload["shank_left"]["mass"]["source"] == "calculated"


def test_compute_body_bsp_missing_file() -> None:
    """A missing mesh file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        compute_body_bsp("does_not_exist.obj", JOINTS, target_mass_kg=70.0)


def test_compute_body_bsp_rejects_bad_mass(humanoid_path: Path) -> None:
    """A non-positive target mass is rejected before any computation."""
    with pytest.raises(ValueError, match="target_mass_kg"):
        compute_body_bsp(humanoid_path, JOINTS, target_mass_kg=0.0)


def test_compute_body_bsp_extracts_all_segments(body_bsp: BodyBSP) -> None:
    """All 14 segments are extracted and no extraction failure is hidden."""
    assert body_bsp.failed_segments == {}
    assert set(body_bsp.segments) == set(SEGMENT_DENSITIES_KG_M3)
    assert body_bsp.subject_id == "SYNTH-01"


def test_compute_body_bsp_mass_calibration(body_bsp: BodyBSP) -> None:
    """Calibrated masses sum to the target; the pre-calibration error is kept."""
    assert body_bsp.total_mass_kg == pytest.approx(70.0, rel=1e-9)
    assert body_bsp.uncalibrated_mass_kg > 0.0
    assert body_bsp.mass_conservation_error == pytest.approx(
        abs(body_bsp.uncalibrated_mass_kg - 70.0) / 70.0, rel=1e-12
    )
    assert body_bsp.density_scale_factor == pytest.approx(
        70.0 / body_bsp.uncalibrated_mass_kg, rel=1e-12
    )
    for segment in body_bsp.segments.values():
        assert segment.density_kg_m3 == pytest.approx(
            SEGMENT_DENSITIES_KG_M3[segment.name] * body_bsp.density_scale_factor, rel=1e-9
        )


def test_compute_body_bsp_segment_plausibility(body_bsp: BodyBSP) -> None:
    """Each segment has a positive volume, a valid tensor, and a sane position."""
    for name, segment in body_bsp.segments.items():
        assert segment.volume_m3 > 0.0, name
        assert segment.mass_kg > 0.0, name
        assert segment.validation["is_symmetric"], name
        assert segment.validation["eigenvalues_positive"], name
        assert segment.validation["triangle_inequalities_satisfied"], name
        assert np.all(np.isfinite(segment.com_m)), name

    # Left/right symmetry of the synthetic body: mirrored masses must match.
    for left, right in (
        ("thigh_left", "thigh_right"),
        ("shank_left", "shank_right"),
        ("upper_arm_left", "upper_arm_right"),
    ):
        assert body_bsp.segments[left].mass_kg == pytest.approx(
            body_bsp.segments[right].mass_kg, rel=1e-6
        )
        assert body_bsp.segments[left].com_m[0] == pytest.approx(
            -body_bsp.segments[right].com_m[0], abs=1e-6
        )

    # Anatomical ordering that any correct segmentation must respect.
    assert body_bsp.segments["head"].com_m[2] > body_bsp.segments["trunk"].com_m[2]
    assert body_bsp.segments["trunk"].com_m[2] > body_bsp.segments["thigh_left"].com_m[2]
    assert body_bsp.segments["thigh_left"].com_m[2] > body_bsp.segments["shank_left"].com_m[2]
    assert body_bsp.segments["shank_left"].com_m[2] > body_bsp.segments["foot_left"].com_m[2]
    assert body_bsp.segments["trunk"].mass_kg > body_bsp.segments["head"].mass_kg


def test_compute_body_bsp_volume_conservation(body_bsp: BodyBSP, humanoid_path: Path) -> None:
    """Segment volumes account for the body volume within the boundary convention."""
    body = trimesh.load(humanoid_path, force="mesh", process=True)
    whole = compute_volume(body.vertices, body.faces)
    assert body_bsp.total_volume_m3 == pytest.approx(whole, rel=0.05)
    assert body_bsp.total_volume_m3 <= whole * (1.0 + 1e-9)
    assert any("segmented volume" in note for note in body_bsp.notes)


def test_compute_body_bsp_reports_density_provenance(body_bsp: BodyBSP) -> None:
    """Placeholder-density provenance is visible in every segment and in notes."""
    for segment in body_bsp.segments.values():
        assert "de_Leva_1996" in segment.density_source
        assert "mass_calibrated" in segment.density_source
        assert any("density scaled by" in warning for warning in segment.warnings)
    assert any("NOT subject-specific" in note for note in body_bsp.notes)
    assert any("uniform density" in note for note in body_bsp.notes)


def test_compute_body_bsp_lung_correction(humanoid_path: Path) -> None:
    """Enabling the lung correction lowers the trunk density and is documented."""
    plain = compute_body_bsp(humanoid_path, JOINTS, target_mass_kg=70.0, sex="male")
    corrected = compute_body_bsp(
        humanoid_path,
        JOINTS,
        target_mass_kg=70.0,
        sex="male",
        apply_lung_correction=True,
    )

    plain_ratio = plain.segments["trunk"].mass_kg / plain.total_mass_kg
    corrected_ratio = corrected.segments["trunk"].mass_kg / corrected.total_mass_kg
    assert corrected_ratio < plain_ratio
    assert corrected.total_mass_kg == pytest.approx(70.0, rel=1e-9)
    assert any("pulmonary air" in note for note in corrected.notes)
    assert any("pulmonary air" in w for w in corrected.segments["trunk"].warnings)
    assert any("DISABLED" in note for note in plain.notes)


def test_compute_body_bsp_rejects_unknown_sex(humanoid_path: Path) -> None:
    """An unsupported sex label raises rather than defaulting silently."""
    with pytest.raises(ValueError, match="sex must be one of"):
        compute_body_bsp(humanoid_path, JOINTS, target_mass_kg=70.0, sex="unspecified")
