"""Unit tests for :mod:`bodyloop_anthropometrics.geometry.mass_properties`.

Every test validates the polyhedral integration against a solid whose mass
properties are known in closed form (cube, sphere, rectangular prism), which is
the validation strategy recommended by Mirtich (1996), Section 6.

References
----------
.. [1] Mirtich, B. (1996). Fast and accurate computation of polyhedral mass
       properties. Journal of Graphics Tools, 1(2), 31-50.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from bodyloop_anthropometrics.geometry.mass_properties import (
    check_mesh_integrity,
    compute_bsp_for_segment,
    compute_centroid,
    compute_inertia_tensor,
    compute_volume,
    parallel_axis_theorem,
    translate_inertia_to_point,
    validate_inertia_tensor,
)

pytestmark = pytest.mark.unit

# Discretisation tolerance for the icosphere (subdivisions=4): the inscribed
# polyhedron under-estimates the true sphere by roughly 0.1 %.
SPHERE_RTOL = 0.02
# Exact-arithmetic solids (box) — only floating-point round-off is allowed.
EXACT_RTOL = 1e-12

CUBE_SIDE_M = 0.4
SPHERE_RADIUS_M = 0.3
DENSITY_KG_M3 = 1000.0


@pytest.fixture
def cube() -> trimesh.Trimesh:
    """Return a unit-density cube of side 0.4 m centred on the origin."""
    return trimesh.creation.box(extents=(CUBE_SIDE_M,) * 3)


@pytest.fixture
def sphere() -> trimesh.Trimesh:
    """Return an icosphere of radius 0.3 m centred on the origin."""
    return trimesh.creation.icosphere(subdivisions=4, radius=SPHERE_RADIUS_M)


def test_sphere_volume(sphere: trimesh.Trimesh) -> None:
    """Icosphere volume matches (4/3) pi r^3 within the discretisation error."""
    analytic = 4.0 / 3.0 * np.pi * SPHERE_RADIUS_M**3
    assert compute_volume(sphere.vertices, sphere.faces) == pytest.approx(
        analytic, rel=SPHERE_RTOL
    )


def test_cube_volume(cube: trimesh.Trimesh) -> None:
    """Cube volume equals a^3 exactly (up to round-off)."""
    assert compute_volume(cube.vertices, cube.faces) == pytest.approx(
        CUBE_SIDE_M**3, rel=EXACT_RTOL
    )


def test_volume_sign_follows_winding(cube: trimesh.Trimesh) -> None:
    """Reversing the winding flips the sign of the signed volume."""
    flipped = cube.faces[:, ::-1]
    assert compute_volume(cube.vertices, flipped) == pytest.approx(
        -(CUBE_SIDE_M**3), rel=EXACT_RTOL
    )


def test_cube_centroid(cube: trimesh.Trimesh) -> None:
    """Centroid of a translated cube is its geometric centre."""
    assert compute_centroid(cube.vertices, cube.faces) == pytest.approx(
        np.zeros(3), abs=1e-15
    )

    shift = np.array([0.7, -0.2, 0.35])
    moved = cube.copy()
    moved.apply_translation(shift)
    assert compute_centroid(moved.vertices, moved.faces) == pytest.approx(shift, abs=1e-12)


def test_cube_inertia_tensor(cube: trimesh.Trimesh) -> None:
    """Homogeneous cube: Ixx = Iyy = Izz = m a^2 / 6, no products of inertia."""
    inertia = compute_inertia_tensor(cube.vertices, cube.faces, density=DENSITY_KG_M3)
    mass = DENSITY_KG_M3 * CUBE_SIDE_M**3
    expected = mass * CUBE_SIDE_M**2 / 6.0

    assert np.diag(inertia) == pytest.approx(np.full(3, expected), rel=1e-12)
    off_diagonal = inertia - np.diag(np.diag(inertia))
    assert np.abs(off_diagonal).max() == pytest.approx(0.0, abs=1e-15)


def test_prism_inertia_tensor() -> None:
    """Rectangular prism: Ixx = m (b^2 + c^2) / 12 for extents (a, b, c)."""
    extents = np.array([0.2, 0.5, 0.9])
    prism = trimesh.creation.box(extents=extents)
    inertia = compute_inertia_tensor(prism.vertices, prism.faces, density=DENSITY_KG_M3)

    mass = DENSITY_KG_M3 * float(np.prod(extents))
    a, b, c = extents
    expected = mass / 12.0 * np.array([b**2 + c**2, a**2 + c**2, a**2 + b**2])
    assert np.diag(inertia) == pytest.approx(expected, rel=1e-12)


def test_sphere_inertia_tensor(sphere: trimesh.Trimesh) -> None:
    """Solid sphere: I = (2/5) m r^2 about any axis through the centre."""
    inertia = compute_inertia_tensor(sphere.vertices, sphere.faces, density=DENSITY_KG_M3)
    mass = DENSITY_KG_M3 * 4.0 / 3.0 * np.pi * SPHERE_RADIUS_M**3
    expected = 0.4 * mass * SPHERE_RADIUS_M**2
    assert np.diag(inertia) == pytest.approx(np.full(3, expected), rel=SPHERE_RTOL)


def test_inertia_scales_linearly_with_density(cube: trimesh.Trimesh) -> None:
    """Doubling the density doubles the inertia tensor."""
    single = compute_inertia_tensor(cube.vertices, cube.faces, density=DENSITY_KG_M3)
    double = compute_inertia_tensor(cube.vertices, cube.faces, density=2.0 * DENSITY_KG_M3)
    assert double == pytest.approx(2.0 * single, rel=1e-12)


def test_inertia_rejects_non_positive_density(cube: trimesh.Trimesh) -> None:
    """A non-positive density is a programming error, not a silent default."""
    with pytest.raises(ValueError, match="density"):
        compute_inertia_tensor(cube.vertices, cube.faces, density=0.0)


def test_inertia_symmetric(sphere: trimesh.Trimesh) -> None:
    """The tensor is symmetric for an arbitrarily posed mesh."""
    posed = sphere.copy()
    posed.apply_transform(trimesh.transformations.random_rotation_matrix())
    posed.apply_translation([0.31, -0.77, 0.12])
    inertia = compute_inertia_tensor(posed.vertices, posed.faces, density=DENSITY_KG_M3)

    assert inertia == pytest.approx(inertia.T, abs=1e-15)
    assert validate_inertia_tensor(inertia, mass=1.0)["is_symmetric"]


def test_inertia_eigenvalues_positive(cube: trimesh.Trimesh) -> None:
    """Principal moments of a real solid are strictly positive."""
    inertia = compute_inertia_tensor(cube.vertices, cube.faces, density=DENSITY_KG_M3)
    assert np.all(np.linalg.eigvalsh(inertia) > 0.0)

    mass = DENSITY_KG_M3 * CUBE_SIDE_M**3
    report = validate_inertia_tensor(inertia, mass, np.zeros(3))
    assert report["eigenvalues_positive"]
    assert report["issues"] == []


def test_parallel_axis_theorem_identity(cube: trimesh.Trimesh) -> None:
    """Shifting by a zero offset leaves the tensor unchanged."""
    inertia = compute_inertia_tensor(cube.vertices, cube.faces, density=DENSITY_KG_M3)
    mass = DENSITY_KG_M3 * CUBE_SIDE_M**3
    shifted = parallel_axis_theorem(inertia, mass, np.zeros(3))
    assert shifted == pytest.approx(inertia, rel=1e-15)


def test_parallel_axis_theorem_shift(cube: trimesh.Trimesh) -> None:
    """A translated cube returns to its central tensor after the Steiner shift."""
    offset = np.array([0.7, -0.2, 0.35])
    moved = cube.copy()
    moved.apply_translation(offset)

    mass = DENSITY_KG_M3 * CUBE_SIDE_M**3
    inertia_origin = compute_inertia_tensor(moved.vertices, moved.faces, density=DENSITY_KG_M3)
    centroid = compute_centroid(moved.vertices, moved.faces)
    inertia_com = parallel_axis_theorem(inertia_origin, mass, centroid)

    central = mass * CUBE_SIDE_M**2 / 6.0
    assert np.diag(inertia_com) == pytest.approx(np.full(3, central), rel=1e-10)
    assert np.abs(inertia_com - np.diag(np.diag(inertia_com))).max() == pytest.approx(
        0.0, abs=1e-10
    )

    # Analytic check of the shift term itself: I_origin = I_com + m(|d|^2 I - d d^T).
    expected_origin = inertia_com + mass * (
        float(offset @ offset) * np.eye(3) - np.outer(offset, offset)
    )
    assert inertia_origin == pytest.approx(expected_origin, rel=1e-10)


def test_translate_inertia_round_trip(cube: trimesh.Trimesh) -> None:
    """``translate_inertia_to_point`` inverts ``parallel_axis_theorem``."""
    mass = DENSITY_KG_M3 * CUBE_SIDE_M**3
    inertia_com = compute_inertia_tensor(cube.vertices, cube.faces, density=DENSITY_KG_M3)
    point = np.array([-0.4, 0.9, 0.05])
    at_point = translate_inertia_to_point(inertia_com, mass, np.zeros(3), point)
    back = parallel_axis_theorem(at_point, mass, -point)
    assert back == pytest.approx(inertia_com, rel=1e-10)


def test_check_mesh_integrity_closed_mesh(cube: trimesh.Trimesh) -> None:
    """A closed, outward-wound cube passes every integrity check."""
    report = check_mesh_integrity(cube.vertices, cube.faces)
    assert report["is_watertight"]
    assert report["volume_positive"]
    assert not report["has_degenerate_faces"]
    assert report["face_count"] == len(cube.faces)
    assert report["vertex_count"] == len(cube.vertices)
    assert report["issues"] == []


def test_check_mesh_integrity_open_mesh(cube: trimesh.Trimesh) -> None:
    """Removing a triangle opens the mesh: is_watertight is False."""
    report = check_mesh_integrity(cube.vertices, cube.faces[:-1])
    assert report["is_watertight"] is False
    assert any("boundary edge" in issue for issue in report["issues"])


def test_check_mesh_integrity_inverted_normals(cube: trimesh.Trimesh) -> None:
    """Inward-facing normals give a negative volume and are flagged."""
    report = check_mesh_integrity(cube.vertices, cube.faces[:, ::-1])
    assert report["is_watertight"]
    assert report["volume_positive"] is False
    assert any("volume is not positive" in issue for issue in report["issues"])


def test_check_mesh_integrity_degenerate_face(cube: trimesh.Trimesh) -> None:
    """A face with a repeated vertex index is reported as degenerate."""
    faces = np.vstack([cube.faces, [[0, 0, 1]]])
    report = check_mesh_integrity(cube.vertices, faces)
    assert report["has_degenerate_faces"]
    assert any("degenerate" in issue for issue in report["issues"])


def test_triangle_inequalities() -> None:
    """``validate_inertia_tensor`` accepts physical and rejects impossible tensors."""
    physical = np.diag([0.30, 0.25, 0.10])
    report = validate_inertia_tensor(physical, mass=5.0, centroid=np.zeros(3))
    assert report["triangle_inequalities_satisfied"]
    assert report["issues"] == []
    assert report["radius_of_gyration_m"] is not None

    # Iz > Ix + Iy cannot come from any mass distribution.
    impossible = np.diag([0.05, 0.05, 0.50])
    bad = validate_inertia_tensor(impossible, mass=5.0, centroid=np.zeros(3))
    assert bad["triangle_inequalities_satisfied"] is False
    assert any("triangle inequalities" in issue for issue in bad["issues"])


def test_validate_inertia_tensor_flags_asymmetry_and_negativity() -> None:
    """Asymmetric or negative-definite tensors are reported, not silently passed."""
    asymmetric = np.array([[0.3, 0.2, 0.0], [-0.2, 0.25, 0.0], [0.0, 0.0, 0.1]])
    assert validate_inertia_tensor(asymmetric, mass=5.0)["is_symmetric"] is False

    negative = np.diag([-0.1, 0.25, 0.2])
    report = validate_inertia_tensor(negative, mass=5.0)
    assert report["eigenvalues_positive"] is False
    assert any("non-positive principal moment" in issue for issue in report["issues"])


def test_mesh_like_duck_typing(cube: trimesh.Trimesh) -> None:
    """Functions accept a trimesh object directly, not only (vertices, faces)."""
    assert compute_volume(cube) == pytest.approx(compute_volume(cube.vertices, cube.faces))
    assert compute_centroid(cube) == pytest.approx(np.zeros(3), abs=1e-15)


def test_rejects_malformed_arrays() -> None:
    """Shape and index errors raise ValueError instead of producing garbage."""
    with pytest.raises(ValueError, match=r"vertices must have shape"):
        compute_volume(np.zeros((4, 2)), np.zeros((1, 3), dtype=int))
    with pytest.raises(ValueError, match=r"faces must have shape"):
        compute_volume(np.zeros((4, 3)), np.zeros((1, 4), dtype=int))
    with pytest.raises(ValueError, match=r"face indices out of range"):
        compute_volume(np.zeros((4, 3)), np.array([[0, 1, 9]]))


def test_compute_bsp_for_segment(cube: trimesh.Trimesh) -> None:
    """The segment wrapper composes volume, centroid and inertia consistently."""
    moved = cube.copy()
    moved.apply_translation([0.0, 0.0, 0.5])
    bsp = compute_bsp_for_segment(moved, "thigh")

    density = 1050.0  # SEGMENT_DENSITY_KG_M3["thigh"]
    assert bsp["density_kg_m3"] == density
    assert bsp["volume_m3"] == pytest.approx(CUBE_SIDE_M**3, rel=1e-12)
    assert bsp["mass_kg"] == pytest.approx(density * CUBE_SIDE_M**3, rel=1e-12)
    assert bsp["centroid_m"] == pytest.approx([0.0, 0.0, 0.5], abs=1e-12)

    central = density * CUBE_SIDE_M**3 * CUBE_SIDE_M**2 / 6.0
    assert np.diag(bsp["inertia_tensor_kgm2"]) == pytest.approx(np.full(3, central), rel=1e-10)
    assert bsp["validation"]["issues"] == []


def test_compute_bsp_for_segment_unknown_name(cube: trimesh.Trimesh) -> None:
    """An unknown segment name raises KeyError rather than guessing a density."""
    with pytest.raises(KeyError, match="No default density"):
        compute_bsp_for_segment(cube, "tail")
