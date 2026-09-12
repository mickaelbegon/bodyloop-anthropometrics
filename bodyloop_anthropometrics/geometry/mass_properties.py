"""Polyhedral mass properties computation.

Computes volume, centroid, and inertia tensor of a closed triangular mesh using
the divergence theorem (Mirtich 1996 / Zhang & Chen 2001 method).

The implementation uses the signed-tetrahedron decomposition of a closed
polyhedron: every triangular face ``(a, b, c)`` forms a tetrahedron with the
coordinate origin, and the signed contributions of those tetrahedra sum exactly
to the integral over the enclosed solid.  This is algebraically equivalent to
Mirtich's projection-integral formulation but requires no face classification,
and it is exact (up to floating-point round-off) for any closed polyhedron.

All computations are in SI units (metres, kilograms).  This module depends on
numpy only — no trimesh, no scipy — so that it can be validated against
analytic solids independently of any mesh library.

References
----------
.. [1] Mirtich, B. (1996). Fast and accurate computation of polyhedral mass
       properties. Journal of Graphics Tools, 1(2), 31-50.
.. [2] Zhang, C., & Chen, T. (2001). Efficient feature extraction for 2D/3D
       objects in mesh representation. ICIP 2001.
.. [3] Tonon, F. (2004). Explicit exact formulas for the 3-D tetrahedron
       inertia tensor in terms of its vertex coordinates. Journal of
       Mathematical and Statistical Sciences, 1(1), 8-11.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray


@runtime_checkable
class MeshLike(Protocol):
    """Structural type for mesh objects, e.g. ``trimesh.Trimesh``.

    Declaring the shape structurally keeps this module free of a trimesh import
    while still accepting a mesh object wherever ``(vertices, faces)`` arrays
    are accepted.

    Attributes
    ----------
    vertices : ArrayLike
        Vertex positions of shape ``(N, 3)``, in metres.
    faces : ArrayLike
        Triangle indices of shape ``(M, 3)``, 0-based.
    """

    vertices: ArrayLike
    faces: ArrayLike


# TODO_SCIENTIFIC: density values below are placeholder defaults from
# Dempster (1955) / de Leva (1996) — must be validated against DEXA or
# literature appropriate for the target population — see SCIENCE_DECISIONS.md
SEGMENT_DENSITY_KG_M3: dict[str, float] = {
    "head": 1110.0,
    "trunk": 1000.0,
    "upper_arm": 1070.0,
    "forearm": 1130.0,
    "hand": 1160.0,
    "thigh": 1050.0,
    "shank": 1090.0,
    "foot": 1100.0,
}

# Covariance matrix (second moments) of the canonical tetrahedron with vertices
# (0,0,0), (1,0,0), (0,1,0), (0,0,1):  C_ij = integral of x_i x_j dV.
# Diagonal terms = 2!/(5!) = 1/60, off-diagonal = 1!1!/(5!) = 1/120, using
# integral of x^a y^b z^c over the unit simplex = a! b! c! / (a+b+c+3)!.
_CANONICAL_TET_COVARIANCE: NDArray[np.float64] = (
    np.array(
        [
            [2.0, 1.0, 1.0],
            [1.0, 2.0, 1.0],
            [1.0, 1.0, 2.0],
        ],
        dtype=np.float64,
    )
    / 120.0
)

# ASSUMPTION: faces whose cross-product norm falls below this threshold (m^2)
# are treated as degenerate (zero-area slivers).  They contribute nothing to the
# mass integrals, so flagging them is diagnostic only.
_DEGENERATE_AREA_TOL_M2: float = 1e-14


def _as_mesh_arrays(
    vertices: ArrayLike | MeshLike,
    faces: ArrayLike | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Normalise mesh input to ``(vertices, faces)`` float/int arrays.

    Accepts either explicit ``(vertices, faces)`` arrays or a single mesh-like
    object exposing ``.vertices`` and ``.faces`` (e.g. ``trimesh.Trimesh``).
    The duck-typed form keeps this module free of a trimesh import while
    remaining usable from the mesh pipeline.

    Parameters
    ----------
    vertices : NDArray or object
        Vertex array of shape ``(N, 3)``, or a mesh-like object.
    faces : NDArray or None, optional
        Triangle index array of shape ``(M, 3)``.  Ignored when ``vertices`` is
        a mesh-like object.

    Returns
    -------
    tuple of (NDArray[np.float64], NDArray[np.int64])
        Vertices ``(N, 3)`` and faces ``(M, 3)``.

    Raises
    ------
    ValueError
        If the arrays do not have shape ``(N, 3)`` / ``(M, 3)``, or if a face
        index is out of range.
    """
    if faces is None and hasattr(vertices, "vertices") and hasattr(vertices, "faces"):
        mesh = vertices
        vertices, faces = mesh.vertices, mesh.faces

    verts = np.asarray(vertices, dtype=np.float64)
    tris = np.asarray(faces, dtype=np.int64)

    if verts.ndim != 2 or verts.shape[1] != 3:
        raise ValueError(f"vertices must have shape (N, 3), got {verts.shape}")
    if tris.ndim != 2 or tris.shape[1] != 3:
        raise ValueError(f"faces must have shape (M, 3), got {tris.shape}")
    if tris.size and (tris.min() < 0 or tris.max() >= verts.shape[0]):
        raise ValueError(
            f"face indices out of range: [{tris.min()}, {tris.max()}] "
            f"for {verts.shape[0]} vertices"
        )
    return verts, tris


def _tetra_signed_volumes(
    verts: NDArray[np.float64],
    tris: NDArray[np.int64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Return per-face vertices and six times the signed tetrahedron volume.

    Parameters
    ----------
    verts : NDArray[np.float64]
        Vertex array ``(N, 3)``.
    tris : NDArray[np.int64]
        Triangle index array ``(M, 3)``.

    Returns
    -------
    tuple
        ``(a, b, c, det)`` where ``a``, ``b``, ``c`` are ``(M, 3)`` face corner
        positions and ``det`` is ``(M,)`` with ``det_i = a_i . (b_i x c_i)``,
        i.e. six times the signed volume of the tetrahedron ``(O, a, b, c)``.
    """
    a = verts[tris[:, 0]]
    b = verts[tris[:, 1]]
    c = verts[tris[:, 2]]
    det = np.einsum("ij,ij->i", a, np.cross(b, c))
    return a, b, c, det


def compute_volume(vertices: ArrayLike | MeshLike, faces: ArrayLike | None = None) -> float:
    """Compute the signed volume of a closed triangular mesh.

    Parameters
    ----------
    vertices : NDArray of shape (N, 3) or mesh-like
        Vertex positions in metres, or an object exposing ``.vertices`` and
        ``.faces``.
    faces : NDArray of shape (M, 3), optional
        Triangle indices (0-based).

    Returns
    -------
    float
        Signed volume in m^3.  Positive if face normals point outward.

    Notes
    -----
    Uses ``V = (1/6) * sum_i (v0 . (v1 x v2))`` over all triangles, which is the
    divergence theorem applied with the vector field ``F = (x, y, z) / 3``.
    Requires a watertight mesh with consistent winding: non-watertight meshes
    give silently incorrect results, so call :func:`check_mesh_integrity` first.

    References
    ----------
    .. [1] Mirtich (1996), Section 2.
    """
    verts, tris = _as_mesh_arrays(vertices, faces)
    _, _, _, det = _tetra_signed_volumes(verts, tris)
    return float(det.sum() / 6.0)


def compute_centroid(
    vertices: ArrayLike | MeshLike,
    faces: ArrayLike | None = None,
) -> NDArray[np.float64]:
    """Compute the centroid (centre of volume) of a closed mesh.

    Parameters
    ----------
    vertices : NDArray of shape (N, 3) or mesh-like
        Vertex positions in metres.
    faces : NDArray of shape (M, 3), optional
        Triangle indices (0-based).

    Returns
    -------
    NDArray of shape (3,)
        Centroid position in metres, in the input frame.

    Raises
    ------
    ValueError
        If the enclosed volume is zero (degenerate or open mesh).

    Notes
    -----
    Each face forms a tetrahedron with the origin whose own centroid is
    ``(a + b + c) / 4``; the volume-weighted mean of those centroids is exact
    for a closed polyhedron.  The centroid equals the centre of mass only under
    the uniform-density assumption.

    # TODO_SCIENTIFIC: assess whether the uniform-density assumption is
    # acceptable for each segment — see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] Mirtich (1996), Section 3.
    """
    verts, tris = _as_mesh_arrays(vertices, faces)
    a, b, c, det = _tetra_signed_volumes(verts, tris)
    total = det.sum()
    if abs(total) < np.finfo(np.float64).tiny:
        raise ValueError("Cannot compute centroid: enclosed volume is zero.")
    # Weighted sum of tetrahedron centroids (a + b + c) / 4, weights = det / 6.
    weighted = np.einsum("i,ij->j", det, (a + b + c) / 4.0)
    return np.asarray(weighted / total, dtype=np.float64)


def compute_covariance(
    vertices: ArrayLike | MeshLike,
    faces: ArrayLike | None = None,
) -> NDArray[np.float64]:
    """Compute the second-moment (covariance) matrix of a closed mesh.

    Parameters
    ----------
    vertices : NDArray of shape (N, 3) or mesh-like
        Vertex positions in metres.
    faces : NDArray of shape (M, 3), optional
        Triangle indices (0-based).

    Returns
    -------
    NDArray of shape (3, 3)
        ``C_ij = integral over the solid of x_i x_j dV`` in m^5, about the
        origin of the input frame.

    Notes
    -----
    For a tetrahedron spanned by the origin and the face corners ``(a, b, c)``,
    let ``A = [a b c]`` (columns).  The affine map ``x = A u`` sends the
    canonical simplex onto that tetrahedron, so
    ``C_tet = det(A) * A @ C_canonical @ A.T``.  Signed determinants make the
    contributions of tetrahedra outside the solid cancel exactly.

    References
    ----------
    .. [1] Mirtich (1996), Section 4.
    .. [2] Tonon, F. (2004). J. Math. Stat. Sci., 1(1), 8-11.
    """
    verts, tris = _as_mesh_arrays(vertices, faces)
    a, b, c, det = _tetra_signed_volumes(verts, tris)
    # A[i] has columns (a_i, b_i, c_i).
    mats = np.stack([a, b, c], axis=-1)
    transformed = np.einsum(
        "ijk,kl,iml->ijm", mats, _CANONICAL_TET_COVARIANCE, mats
    )
    covariance = np.einsum("i,ijk->jk", det, transformed)
    # Symmetrise to remove round-off asymmetry.
    return np.asarray(0.5 * (covariance + covariance.T), dtype=np.float64)


def compute_inertia_tensor(
    vertices: ArrayLike | MeshLike,
    faces: ArrayLike | None = None,
    density: float = 1.0,
) -> NDArray[np.float64]:
    """Compute the inertia tensor of a closed mesh about the origin.

    Parameters
    ----------
    vertices : NDArray of shape (N, 3) or mesh-like
        Vertex positions in metres.
    faces : NDArray of shape (M, 3), optional
        Triangle indices (0-based).
    density : float, optional
        Volumetric density in kg/m^3.  Default ``1.0`` for unit density.

    Returns
    -------
    NDArray of shape (3, 3)
        Symmetric inertia tensor in kg.m^2, expressed in the input frame.

    Raises
    ------
    ValueError
        If ``density`` is not strictly positive.

    Notes
    -----
    Computed about the origin.  Use :func:`parallel_axis_theorem` to shift it to
    the centroid.  From the covariance matrix ``C``:
    ``I = density * (trace(C) * Identity - C)``, since
    ``I_xx = integral (y^2 + z^2) dm`` and ``I_xy = -integral x y dm``.

    # TODO_SCIENTIFIC: the density source must be documented per segment —
    # see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] Mirtich (1996), Section 4.
    .. [2] de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
           inertia parameters. J Biomech 29(9):1223-1230.
    """
    if not density > 0.0:
        raise ValueError(f"density must be strictly positive, got {density}")
    covariance = compute_covariance(vertices, faces)
    return np.asarray(
        density * (np.trace(covariance) * np.eye(3) - covariance), dtype=np.float64
    )


def parallel_axis_theorem(
    inertia_about_origin: NDArray[np.float64],
    mass: float,
    centroid: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Shift an inertia tensor from the origin to the centroid (Steiner).

    Parameters
    ----------
    inertia_about_origin : NDArray of shape (3, 3)
        Inertia tensor about the origin, in kg.m^2.
    mass : float
        Total mass in kg.
    centroid : NDArray of shape (3,)
        Position of the centroid in metres, in the same frame.

    Returns
    -------
    NDArray of shape (3, 3)
        Inertia tensor about the centroid, in kg.m^2.

    Notes
    -----
    ``I_com = I_origin - m * (|c|^2 * Identity - c c^T)``.  The sign is negative
    because the shift goes *towards* the centre of mass.  Passing
    ``centroid = 0`` returns the input unchanged.

    References
    ----------
    .. [1] Mirtich (1996), Section 5 (translation of inertia tensors).
    """
    inertia = np.asarray(inertia_about_origin, dtype=np.float64)
    c = np.asarray(centroid, dtype=np.float64).reshape(3)
    shift = float(mass) * (float(c @ c) * np.eye(3) - np.outer(c, c))
    return np.asarray(inertia - shift, dtype=np.float64)


def translate_inertia_to_point(
    inertia_about_com: NDArray[np.float64],
    mass: float,
    com: NDArray[np.float64],
    point: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Shift an inertia tensor from the centre of mass to an arbitrary point.

    Parameters
    ----------
    inertia_about_com : NDArray of shape (3, 3)
        Inertia tensor about the centre of mass, in kg.m^2.
    mass : float
        Total mass in kg.
    com : NDArray of shape (3,)
        Centre-of-mass position in metres.
    point : NDArray of shape (3,)
        Target reference point in metres, same frame as ``com``.

    Returns
    -------
    NDArray of shape (3, 3)
        Inertia tensor about ``point``, in kg.m^2.

    Notes
    -----
    Inverse of :func:`parallel_axis_theorem`:
    ``I_point = I_com + m * (|d|^2 * Identity - d d^T)`` with
    ``d = com - point``.
    """
    inertia = np.asarray(inertia_about_com, dtype=np.float64)
    d = np.asarray(com, dtype=np.float64).reshape(3) - np.asarray(
        point, dtype=np.float64
    ).reshape(3)
    return np.asarray(
        inertia + float(mass) * (float(d @ d) * np.eye(3) - np.outer(d, d)),
        dtype=np.float64,
    )


def check_mesh_integrity(
    vertices: ArrayLike | MeshLike,
    faces: ArrayLike | None = None,
) -> dict[str, Any]:
    """Check basic mesh integrity for mass property computation.

    Parameters
    ----------
    vertices : NDArray of shape (N, 3) or mesh-like
        Vertex positions in metres.
    faces : NDArray of shape (M, 3), optional
        Triangle indices (0-based).

    Returns
    -------
    dict
        Keys: ``'is_watertight'``, ``'has_degenerate_faces'``,
        ``'volume_positive'``, ``'face_count'``, ``'vertex_count'``,
        ``'volume_m3'``, ``'is_edge_manifold'``, ``'is_consistently_wound'``,
        ``'issues'`` (list of str).

    Notes
    -----
    Watertightness is tested combinatorially: the mesh is watertight when every
    undirected edge is shared by exactly two faces (edge-manifold) *and* every
    directed edge appears exactly once, which means neighbouring faces are wound
    consistently.  Both conditions are required for the divergence-theorem
    integrals to be valid.

    # ASSUMPTION: vertices that coincide geometrically but carry different
    # indices (unmerged duplicates, e.g. from a GLB with split UV seams) make
    # the mesh look non-watertight here.  Merge vertices before checking.
    """
    verts, tris = _as_mesh_arrays(vertices, faces)
    issues: list[str] = []

    # Degenerate faces: repeated indices or (near) zero area.
    repeated = (
        (tris[:, 0] == tris[:, 1]) | (tris[:, 1] == tris[:, 2]) | (tris[:, 0] == tris[:, 2])
    )
    a, b, c, _ = _tetra_signed_volumes(verts, tris)
    areas = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    degenerate = repeated | (areas < _DEGENERATE_AREA_TOL_M2)
    has_degenerate = bool(degenerate.any())
    if has_degenerate:
        issues.append(f"{int(degenerate.sum())} degenerate face(s) (repeated index or zero area)")

    # Edge bookkeeping.
    directed = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]], axis=0)
    undirected = np.sort(directed, axis=1)
    _, undirected_counts = np.unique(undirected, axis=0, return_counts=True)
    _, directed_counts = np.unique(directed, axis=0, return_counts=True)

    is_edge_manifold = bool(np.all(undirected_counts == 2)) if undirected.size else False
    if not is_edge_manifold and undirected.size:
        n_boundary = int(np.count_nonzero(undirected_counts < 2))
        n_nonmanifold = int(np.count_nonzero(undirected_counts > 2))
        if n_boundary:
            issues.append(f"{n_boundary} boundary edge(s): mesh is open")
        if n_nonmanifold:
            issues.append(f"{n_nonmanifold} non-manifold edge(s) shared by more than 2 faces")

    is_consistently_wound = bool(np.all(directed_counts == 1)) if directed.size else False
    if not is_consistently_wound and directed.size:
        issues.append(
            f"{int(np.count_nonzero(directed_counts > 1))} duplicated directed edge(s): "
            "face winding is inconsistent"
        )

    is_watertight = is_edge_manifold and is_consistently_wound
    if not tris.size:
        issues.append("mesh has no faces")

    volume = compute_volume(verts, tris)
    volume_positive = bool(volume > 0.0)
    if not volume_positive:
        issues.append(
            f"signed volume is not positive ({volume:.6e} m^3): "
            "face normals probably point inward"
        )

    return {
        "is_watertight": is_watertight,
        "has_degenerate_faces": has_degenerate,
        "volume_positive": volume_positive,
        "face_count": int(tris.shape[0]),
        "vertex_count": int(verts.shape[0]),
        "volume_m3": float(volume),
        "is_edge_manifold": is_edge_manifold,
        "is_consistently_wound": is_consistently_wound,
        "issues": issues,
    }


def validate_inertia_tensor(
    inertia: NDArray[np.float64],
    mass: float,
    centroid: NDArray[np.float64] | None = None,
) -> dict[str, Any]:
    """Validate the physical plausibility of an inertia tensor.

    Parameters
    ----------
    inertia : NDArray of shape (3, 3)
        Inertia tensor in kg.m^2, normally expressed about the centre of mass.
    mass : float
        Segment mass in kg.
    centroid : NDArray of shape (3,) or None, optional
        Centre-of-mass position in metres.  Used only to report a
        non-finite/implausible position; it does not change the tensor checks.

    Returns
    -------
    dict
        Keys: ``'is_symmetric'``, ``'eigenvalues_positive'``,
        ``'triangle_inequalities_satisfied'``, ``'principal_moments_kgm2'``,
        ``'radius_of_gyration_m'``, ``'issues'`` (list of str).

    Notes
    -----
    Triangle inequalities on the principal moments:
    ``Ix + Iy >= Iz``, ``Iy + Iz >= Ix``, ``Iz + Ix >= Iy``.  These are
    necessary (but not sufficient) conditions for a tensor to correspond to a
    physical mass distribution.

    # ASSUMPTION: comparisons use a relative tolerance of 1e-9 scaled by the
    # largest principal moment, so that the checks are dimensionally consistent
    # for human segments (typical magnitudes 1e-4 to 1e-1 kg.m^2).

    References
    ----------
    .. [1] Mirtich (1996), Section 6 (validation against analytic solids).
    .. [2] Dumas, R. et al. (2007). Adjustments to McConville et al. and Young
           et al. body segment inertial parameters. J Biomech 40(3):543-553.
    """
    tensor = np.asarray(inertia, dtype=np.float64)
    issues: list[str] = []

    if tensor.shape != (3, 3):
        raise ValueError(f"inertia must have shape (3, 3), got {tensor.shape}")
    if not np.all(np.isfinite(tensor)):
        issues.append("inertia tensor contains non-finite values")
        return {
            "is_symmetric": False,
            "eigenvalues_positive": False,
            "triangle_inequalities_satisfied": False,
            "principal_moments_kgm2": None,
            "radius_of_gyration_m": None,
            "issues": issues,
        }

    scale = float(np.max(np.abs(tensor))) or 1.0
    tol = 1e-9 * scale

    is_symmetric = bool(np.allclose(tensor, tensor.T, atol=tol, rtol=0.0))
    if not is_symmetric:
        issues.append("inertia tensor is not symmetric")

    principal = np.linalg.eigvalsh(0.5 * (tensor + tensor.T))
    eigenvalues_positive = bool(np.all(principal > tol))
    if not eigenvalues_positive:
        issues.append(f"non-positive principal moment(s): {principal.tolist()}")

    ix, iy, iz = (float(v) for v in principal)
    triangle_ok = bool(
        (ix + iy >= iz - tol) and (iy + iz >= ix - tol) and (iz + ix >= iy - tol)
    )
    if not triangle_ok:
        issues.append(
            "triangle inequalities violated by principal moments "
            f"({ix:.6e}, {iy:.6e}, {iz:.6e}): tensor is not physically realisable"
        )

    radius_of_gyration = None
    if mass > 0.0 and eigenvalues_positive:
        radius_of_gyration = np.sqrt(principal / float(mass)).tolist()
    elif mass <= 0.0:
        issues.append(f"mass must be strictly positive, got {mass}")

    if centroid is not None:
        c = np.asarray(centroid, dtype=np.float64).reshape(3)
        if not np.all(np.isfinite(c)):
            issues.append("centroid contains non-finite values")

    return {
        "is_symmetric": is_symmetric,
        "eigenvalues_positive": eigenvalues_positive,
        "triangle_inequalities_satisfied": triangle_ok,
        "principal_moments_kgm2": principal.tolist(),
        "radius_of_gyration_m": radius_of_gyration,
        "issues": issues,
    }


def compute_bsp_for_segment(
    mesh: MeshLike,
    segment_name: str,
    density: float | None = None,
) -> dict[str, object]:
    """Return a full body-segment parameter (BSP) dictionary for one segment.

    Parameters
    ----------
    mesh : trimesh.Trimesh or mesh-like
        Watertight segment mesh in ``bodyloop_global`` coordinates, exposing
        ``.vertices`` and ``.faces``.
    segment_name : str
        Name key matching :data:`SEGMENT_DENSITY_KG_M3`, e.g. ``"thigh"``.
    density : float or None, optional
        Explicit density in kg/m^3.  If ``None``, looked up in
        :data:`SEGMENT_DENSITY_KG_M3`.

    Returns
    -------
    dict[str, object]
        Keys: ``"segment"``, ``"mass_kg"``, ``"volume_m3"``, ``"centroid_m"``,
        ``"inertia_tensor_kgm2"`` (about the segment centroid),
        ``"density_kg_m3"``, ``"density_source"``, ``"integrity"``,
        ``"validation"``.

    Raises
    ------
    KeyError
        If ``segment_name`` is not in :data:`SEGMENT_DENSITY_KG_M3` and no
        explicit ``density`` is given.
    ValueError
        If the mesh encloses a non-positive volume.

    Notes
    -----
    The inertia tensor is returned about the segment centroid, expressed in the
    input (``bodyloop_global``) frame — not rotated into a body-fixed frame.

    References
    ----------
    .. [1] Dempster, W.T. (1955). Space requirements of the seated operator.
           WADC Technical Report 55-159.
    .. [2] de Leva, P. (1996). J Biomech 29(9):1223-1230.
    """
    verts, tris = _as_mesh_arrays(mesh)

    if density is None:
        if segment_name not in SEGMENT_DENSITY_KG_M3:
            raise KeyError(
                f"No default density for segment '{segment_name}'. "
                f"Known segments: {sorted(SEGMENT_DENSITY_KG_M3)}"
            )
        density = SEGMENT_DENSITY_KG_M3[segment_name]
        density_source = "de_Leva_1996/Dempster_1955 (population average, NOT calibrated)"
    else:
        density_source = "explicit"

    integrity = check_mesh_integrity(verts, tris)
    volume = float(integrity["volume_m3"])
    if volume <= 0.0:
        raise ValueError(
            f"Segment '{segment_name}' encloses a non-positive volume ({volume:.6e} m^3); "
            f"integrity issues: {integrity['issues']}"
        )

    centroid = compute_centroid(verts, tris)
    inertia_origin = compute_inertia_tensor(verts, tris, density=density)
    mass = density * volume
    inertia_com = parallel_axis_theorem(inertia_origin, mass, centroid)

    return {
        "segment": segment_name,
        "mass_kg": mass,
        "volume_m3": volume,
        "centroid_m": centroid,
        "inertia_tensor_kgm2": inertia_com,
        "density_kg_m3": density,
        "density_source": density_source,
        "integrity": integrity,
        "validation": validate_inertia_tensor(inertia_com, mass, centroid),
    }
