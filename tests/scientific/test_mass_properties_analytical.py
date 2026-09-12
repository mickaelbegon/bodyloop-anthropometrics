"""Analytical cross-check of polyhedral mass property computation.

Cross-validates :mod:`bodyloop_anthropometrics.geometry.mass_properties` against
closed-form solutions for four canonical solids — unit cube, sphere, cylinder,
and ellipsoid — following the validation strategy recommended by Mirtich (1996),
Section 6.

All shape tolerances are set to 1 % relative error (``rtol=0.01``).  This is
much wider than the expected discretisation error of the icosphere/cylinder
tessellations (~0.1–0.2 % for the mesh densities used here), so any failure
indicates a real algorithmic defect rather than a tessellation artefact.

Key conventions
---------------
* ``compute_inertia_tensor()`` returns the inertia tensor **about the coordinate
  origin**, not the centroid.
* ``parallel_axis_theorem(I_origin, mass, centroid)`` shifts from origin to
  centroid.
* For shapes already centred at the origin (sphere, cylinder, ellipsoid) the
  shift is numerically negligible; we still apply it for completeness.

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
    compute_centroid,
    compute_inertia_tensor,
    compute_volume,
    parallel_axis_theorem,
    translate_inertia_to_point,
    validate_inertia_tensor,
)

pytestmark = pytest.mark.scientific

# Uniform density used for all shapes except the unit-cube test which uses 1.
DENSITY_KG_M3: float = 1000.0

# Tolerance shared by all shape tests (1 % relative error).
RTOL: float = 0.01


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def unit_cube() -> trimesh.Trimesh:
    """1×1×1 m cube translated so that its corner is at the origin.

    After translation the geometric centre (COM) is at (0.5, 0.5, 0.5) m,
    which is the textbook reference position for the 1/6 formula.
    """
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    mesh.apply_translation([0.5, 0.5, 0.5])
    return mesh


@pytest.fixture
def sphere_r01() -> trimesh.Trimesh:
    """Icosphere of radius r = 0.1 m centred at the origin (2562 vertices)."""
    return trimesh.creation.icosphere(subdivisions=4, radius=0.1)


@pytest.fixture
def cylinder_r005_h02() -> trimesh.Trimesh:
    """Cylinder r = 0.05 m, h = 0.2 m, spin axis along Z, centred at origin."""
    return trimesh.creation.cylinder(radius=0.05, height=0.2, sections=64)


@pytest.fixture
def ellipsoid_abc() -> tuple[trimesh.Trimesh, float, float, float]:
    """Ellipsoid with semi-axes (a, b, c) = (0.1, 0.08, 0.06) m.

    Constructed by scaling a unit icosphere (subdivisions=4) so that x-vertices
    are multiplied by a, y-vertices by b, and z-vertices by c.  This preserves
    the watertight, consistently-wound topology of the base icosphere.
    """
    a, b, c = 0.1, 0.08, 0.06
    mesh = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    mesh.vertices = mesh.vertices * np.array([a, b, c])
    return mesh, a, b, c


# ---------------------------------------------------------------------------
# Unit cube  (density = 1 kg/m³)
# ---------------------------------------------------------------------------


class TestUnitCube:
    """Analytical validation for a 1×1×1 m cube at density = 1 kg/m³.

    For a homogeneous cube of side L = 1 m and density ρ = 1 kg/m³:
      V = L³ = 1 m³
      M = ρ V = 1 kg
      COM = (L/2, L/2, L/2) = (0.5, 0.5, 0.5) m
      I_xx = I_yy = I_zz = M L² / 6 = 1/6 kg·m² (about the centroid)
    """

    DENSITY: float = 1.0   # kg/m³
    SIDE: float = 1.0      # m

    def test_volume(self, unit_cube: trimesh.Trimesh) -> None:
        """Volume equals L³ = 1.0 m³."""
        V_analytic = self.SIDE ** 3
        assert compute_volume(unit_cube) == pytest.approx(V_analytic, rel=RTOL)

    def test_centroid(self, unit_cube: trimesh.Trimesh) -> None:
        """Centroid is at (0.5, 0.5, 0.5) m."""
        com_analytic = np.array([0.5, 0.5, 0.5])
        assert compute_centroid(unit_cube) == pytest.approx(com_analytic, rel=RTOL)

    def test_inertia_tensor(self, unit_cube: trimesh.Trimesh) -> None:
        """Principal moments I_xx = I_yy = I_zz = 1/6 kg·m² at the centroid."""
        volume = compute_volume(unit_cube)
        mass = self.DENSITY * volume
        centroid = compute_centroid(unit_cube)
        I_origin = compute_inertia_tensor(unit_cube, density=self.DENSITY)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        # Analytical: M L² / 6 = 1 * 1 / 6
        I_analytic = self.DENSITY * self.SIDE ** 5 / 6.0
        assert np.diag(I_com) == pytest.approx(np.full(3, I_analytic), rel=RTOL)
        # Products of inertia vanish by symmetry about the centroid.
        off_diag = I_com - np.diag(np.diag(I_com))
        assert np.abs(off_diag).max() == pytest.approx(0.0, abs=1e-10)

    def test_integrity(self, unit_cube: trimesh.Trimesh) -> None:
        """Cube mesh passes all integrity checks."""
        report = check_mesh_integrity(unit_cube)
        assert report["is_watertight"]
        assert report["volume_positive"]
        assert not report["has_degenerate_faces"]
        assert report["issues"] == []

    def test_parallel_axis_round_trip(self, unit_cube: trimesh.Trimesh) -> None:
        """Steiner-shift to an arbitrary point and back recovers the centroid tensor."""
        volume = compute_volume(unit_cube)
        mass = self.DENSITY * volume
        centroid = compute_centroid(unit_cube)
        I_origin = compute_inertia_tensor(unit_cube, density=self.DENSITY)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        arbitrary_point = np.array([1.3, -0.7, 2.1])
        I_at_point = translate_inertia_to_point(I_com, mass, centroid, arbitrary_point)
        I_com_back = parallel_axis_theorem(I_at_point, mass, centroid - arbitrary_point)

        assert I_com_back == pytest.approx(I_com, rel=1e-9)


# ---------------------------------------------------------------------------
# Sphere  (r = 0.1 m, density = 1000 kg/m³)
# ---------------------------------------------------------------------------


class TestSphereR01:
    """Analytical validation for a solid sphere of radius r = 0.1 m.

    Closed-form formulas:
      V = (4/3) π r³
      M = ρ V
      COM = (0, 0, 0)
      I_xx = I_yy = I_zz = (2/5) M r²  (about the centroid = origin)
    """

    R: float = 0.1  # m

    def test_volume(self, sphere_r01: trimesh.Trimesh) -> None:
        """Volume equals (4/3) π r³."""
        V_analytic = 4.0 / 3.0 * np.pi * self.R ** 3
        assert compute_volume(sphere_r01) == pytest.approx(V_analytic, rel=RTOL)

    def test_centroid(self, sphere_r01: trimesh.Trimesh) -> None:
        """Centroid of sphere centred at origin is (0, 0, 0)."""
        com = compute_centroid(sphere_r01)
        # Absolute tolerance because the centroid is analytically zero.
        assert com == pytest.approx(np.zeros(3), abs=1e-10)

    def test_inertia_tensor(self, sphere_r01: trimesh.Trimesh) -> None:
        """Principal moments I_xx = I_yy = I_zz = (2/5) M r²."""
        volume = compute_volume(sphere_r01)
        mass = DENSITY_KG_M3 * volume
        centroid = compute_centroid(sphere_r01)
        I_origin = compute_inertia_tensor(sphere_r01, density=DENSITY_KG_M3)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        V_analytic = 4.0 / 3.0 * np.pi * self.R ** 3
        M_analytic = DENSITY_KG_M3 * V_analytic
        I_analytic = 2.0 / 5.0 * M_analytic * self.R ** 2
        assert np.diag(I_com) == pytest.approx(np.full(3, I_analytic), rel=RTOL)

    def test_integrity(self, sphere_r01: trimesh.Trimesh) -> None:
        """Icosphere mesh passes all integrity checks."""
        report = check_mesh_integrity(sphere_r01)
        assert report["is_watertight"]
        assert report["volume_positive"]
        assert not report["has_degenerate_faces"]
        assert report["issues"] == []

    def test_parallel_axis_round_trip(self, sphere_r01: trimesh.Trimesh) -> None:
        """Steiner-shift to an arbitrary point and back recovers the centroid tensor."""
        volume = compute_volume(sphere_r01)
        mass = DENSITY_KG_M3 * volume
        centroid = compute_centroid(sphere_r01)
        I_origin = compute_inertia_tensor(sphere_r01, density=DENSITY_KG_M3)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        arbitrary_point = np.array([0.5, -0.3, 0.8])
        I_at_point = translate_inertia_to_point(I_com, mass, centroid, arbitrary_point)
        I_com_back = parallel_axis_theorem(I_at_point, mass, centroid - arbitrary_point)

        assert I_com_back == pytest.approx(I_com, rel=1e-9)


# ---------------------------------------------------------------------------
# Cylinder  (r = 0.05 m, h = 0.2 m, density = 1000 kg/m³)
# ---------------------------------------------------------------------------


class TestCylinderR005H02:
    """Analytical validation for a cylinder r = 0.05 m, h = 0.2 m.

    trimesh aligns the cylinder spin axis along Z.  Closed-form formulas:
      V = π r² h
      M = ρ V
      COM = (0, 0, 0)
      I_z = (1/2) M r²          (axial, spin axis)
      I_x = I_y = M (3r²+h²)/12 (transverse)
    """

    R: float = 0.05  # m
    H: float = 0.20  # m

    def test_volume(self, cylinder_r005_h02: trimesh.Trimesh) -> None:
        """Volume equals π r² h."""
        V_analytic = np.pi * self.R ** 2 * self.H
        assert compute_volume(cylinder_r005_h02) == pytest.approx(V_analytic, rel=RTOL)

    def test_centroid(self, cylinder_r005_h02: trimesh.Trimesh) -> None:
        """Centroid of cylinder centred at origin is (0, 0, 0)."""
        com = compute_centroid(cylinder_r005_h02)
        assert com == pytest.approx(np.zeros(3), abs=1e-10)

    def test_inertia_tensor(self, cylinder_r005_h02: trimesh.Trimesh) -> None:
        """I_z = Mr²/2 (axial) and I_x = I_y = M(3r²+h²)/12 (transverse)."""
        volume = compute_volume(cylinder_r005_h02)
        mass = DENSITY_KG_M3 * volume
        centroid = compute_centroid(cylinder_r005_h02)
        I_origin = compute_inertia_tensor(cylinder_r005_h02, density=DENSITY_KG_M3)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        V_analytic = np.pi * self.R ** 2 * self.H
        M_analytic = DENSITY_KG_M3 * V_analytic
        Iz_analytic = 0.5 * M_analytic * self.R ** 2
        Ix_analytic = M_analytic / 12.0 * (3.0 * self.R ** 2 + self.H ** 2)

        diag = np.diag(I_com)
        # Trimesh cylinder axis is Z, so index 2 is the axial moment.
        assert diag[0] == pytest.approx(Ix_analytic, rel=RTOL)  # transverse
        assert diag[1] == pytest.approx(Ix_analytic, rel=RTOL)  # transverse
        assert diag[2] == pytest.approx(Iz_analytic, rel=RTOL)  # axial

    def test_integrity(self, cylinder_r005_h02: trimesh.Trimesh) -> None:
        """Cylinder mesh passes all integrity checks."""
        report = check_mesh_integrity(cylinder_r005_h02)
        assert report["is_watertight"]
        assert report["volume_positive"]
        assert not report["has_degenerate_faces"]
        assert report["issues"] == []

    def test_parallel_axis_round_trip(self, cylinder_r005_h02: trimesh.Trimesh) -> None:
        """Steiner-shift to an arbitrary point and back recovers the centroid tensor."""
        volume = compute_volume(cylinder_r005_h02)
        mass = DENSITY_KG_M3 * volume
        centroid = compute_centroid(cylinder_r005_h02)
        I_origin = compute_inertia_tensor(cylinder_r005_h02, density=DENSITY_KG_M3)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        arbitrary_point = np.array([0.3, 0.1, -0.5])
        I_at_point = translate_inertia_to_point(I_com, mass, centroid, arbitrary_point)
        I_com_back = parallel_axis_theorem(I_at_point, mass, centroid - arbitrary_point)

        assert I_com_back == pytest.approx(I_com, rel=1e-9)


# ---------------------------------------------------------------------------
# Ellipsoid  (a=0.1, b=0.08, c=0.06 m, density = 1000 kg/m³)
# ---------------------------------------------------------------------------


class TestEllipsoidABC:
    """Analytical validation for an ellipsoid with semi-axes a=0.1, b=0.08, c=0.06 m.

    Closed-form formulas (Euler, solid homogeneous ellipsoid):
      V = (4/3) π a b c
      M = ρ V
      COM = (0, 0, 0)
      I_x = M (b² + c²) / 5    (rotation about X)
      I_y = M (a² + c²) / 5    (rotation about Y)
      I_z = M (a² + b²) / 5    (rotation about Z)
    The vertex scaling (a,b,c) maps X→a, Y→b, Z→c, so the semi-axes match
    the coordinate axes and the principal moments follow directly.
    """

    A: float = 0.1   # m
    B: float = 0.08  # m
    C: float = 0.06  # m

    def test_volume(self, ellipsoid_abc: tuple[trimesh.Trimesh, float, float, float]) -> None:
        """Volume equals (4/3) π a b c."""
        mesh, a, b, c = ellipsoid_abc
        V_analytic = 4.0 / 3.0 * np.pi * a * b * c
        assert compute_volume(mesh) == pytest.approx(V_analytic, rel=RTOL)

    def test_centroid(self, ellipsoid_abc: tuple[trimesh.Trimesh, float, float, float]) -> None:
        """Centroid of ellipsoid centred at origin is (0, 0, 0)."""
        mesh, a, b, c = ellipsoid_abc
        com = compute_centroid(mesh)
        assert com == pytest.approx(np.zeros(3), abs=1e-10)

    def test_inertia_tensor(self, ellipsoid_abc: tuple[trimesh.Trimesh, float, float, float]) -> None:
        """Principal moments: Ix=M(b²+c²)/5, Iy=M(a²+c²)/5, Iz=M(a²+b²)/5."""
        mesh, a, b, c = ellipsoid_abc
        volume = compute_volume(mesh)
        mass = DENSITY_KG_M3 * volume
        centroid = compute_centroid(mesh)
        I_origin = compute_inertia_tensor(mesh, density=DENSITY_KG_M3)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        V_analytic = 4.0 / 3.0 * np.pi * a * b * c
        M_analytic = DENSITY_KG_M3 * V_analytic
        Ix_analytic = M_analytic / 5.0 * (b ** 2 + c ** 2)
        Iy_analytic = M_analytic / 5.0 * (a ** 2 + c ** 2)
        Iz_analytic = M_analytic / 5.0 * (a ** 2 + b ** 2)

        diag = np.diag(I_com)
        assert diag[0] == pytest.approx(Ix_analytic, rel=RTOL)
        assert diag[1] == pytest.approx(Iy_analytic, rel=RTOL)
        assert diag[2] == pytest.approx(Iz_analytic, rel=RTOL)

    def test_integrity(self, ellipsoid_abc: tuple[trimesh.Trimesh, float, float, float]) -> None:
        """Scaled icosphere (ellipsoid) passes all integrity checks."""
        mesh, a, b, c = ellipsoid_abc
        report = check_mesh_integrity(mesh)
        assert report["is_watertight"]
        assert report["volume_positive"]
        assert not report["has_degenerate_faces"]
        assert report["issues"] == []

    def test_parallel_axis_round_trip(
        self, ellipsoid_abc: tuple[trimesh.Trimesh, float, float, float]
    ) -> None:
        """Steiner-shift to an arbitrary point and back recovers the centroid tensor."""
        mesh, a, b, c = ellipsoid_abc
        volume = compute_volume(mesh)
        mass = DENSITY_KG_M3 * volume
        centroid = compute_centroid(mesh)
        I_origin = compute_inertia_tensor(mesh, density=DENSITY_KG_M3)
        I_com = parallel_axis_theorem(I_origin, mass, centroid)

        arbitrary_point = np.array([-0.2, 0.4, 0.15])
        I_at_point = translate_inertia_to_point(I_com, mass, centroid, arbitrary_point)
        I_com_back = parallel_axis_theorem(I_at_point, mass, centroid - arbitrary_point)

        assert I_com_back == pytest.approx(I_com, rel=1e-9)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge-case and validation checks for the mass property pipeline."""

    def test_validate_inertia_tensor_accepts_valid(self) -> None:
        """validate_inertia_tensor accepts a physically valid positive-definite tensor."""
        I_valid = np.diag([0.030, 0.025, 0.020])  # kg·m², satisfies triangle inequalities
        report = validate_inertia_tensor(I_valid, mass=5.0, centroid=np.zeros(3))
        assert report["is_symmetric"]
        assert report["eigenvalues_positive"]
        assert report["triangle_inequalities_satisfied"]
        assert report["issues"] == []

    def test_validate_inertia_tensor_rejects_negative_eigenvalue(self) -> None:
        """validate_inertia_tensor flags a tensor with a negative diagonal entry."""
        I_negative = np.diag([-0.010, 0.025, 0.020])  # Ixx < 0: physically impossible
        report = validate_inertia_tensor(I_negative, mass=5.0)
        assert report["eigenvalues_positive"] is False
        assert any("non-positive principal moment" in issue for issue in report["issues"])

    def test_check_mesh_integrity_inconsistent_winding(self) -> None:
        """check_mesh_integrity flags a mesh where one face has its winding reversed.

        Flipping a single face introduces two pairs of duplicated directed edges
        (each edge of the flipped face now appears twice in the same direction),
        so is_consistently_wound must be False and the issues list must mention
        winding.
        """
        cube = trimesh.creation.box(extents=(0.4, 0.4, 0.4))
        faces = cube.faces.copy()
        # Reverse the vertex order of face 0 only, leaving all other faces intact.
        faces[0] = faces[0, ::-1]
        report = check_mesh_integrity(cube.vertices, faces)
        assert report["is_consistently_wound"] is False
        assert any("winding" in issue for issue in report["issues"])
