"""Direct body segment parameter estimation from the 3-D mesh.

Computes mass, centre of mass, and inertia tensor for each body segment by
cutting the mesh at segment boundaries defined by joint positions and
anatomical landmarks, then integrating over the resulting closed polyhedra
(see :mod:`~bodyloop_anthropometrics.geometry.mass_properties`).

This is the THIRD independent estimator (alongside Yeadon and Hatze).
Results should be compared, not averaged.

Notes
-----
Segment densities are placeholder values from de Leva (1996) / Dempster (1955).
They have NOT been calibrated for this specific subject.

# TODO_SCIENTIFIC: Replace with subject-specific densities from DEXA calibration
# See SCIENCE_DECISIONS.md

The pulmonary volume and internal cavities are NOT modelled by the surface
mesh.  This is a known source of uncertainty, particularly for the trunk.

# TODO_SCIENTIFIC: Pulmonary volume treatment — default lung volume 3.0 L used
# for adult males, 2.3 L for adult females (ICRP Publication 89).  The
# correction is implemented but DISABLED by default because the de Leva /
# Dempster trunk density is itself a whole-trunk average that already embeds
# the pulmonary cavity; enabling both would double-count the correction.
# See SCIENCE_DECISIONS.md

References
----------
.. [1] de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
       inertia parameters. Journal of Biomechanics, 29(9), 1223-1230.
.. [2] Dempster, W. T. (1955). Space requirements of the seated operator.
       WADC Technical Report 55-159.
.. [3] ICRP (2002). Publication 89: Basic Anatomical and Physiological Data for
       Use in Radiological Protection. Annals of the ICRP 32(3-4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from numpy.typing import NDArray

from bodyloop_anthropometrics.anthropometry.measurement_mapping import Measurement
from bodyloop_anthropometrics.geometry.mass_properties import (
    SEGMENT_DENSITY_KG_M3,
    check_mesh_integrity,
    compute_centroid,
    compute_inertia_tensor,
    compute_volume,
    parallel_axis_theorem,
    validate_inertia_tensor,
)

# Placeholder segment densities from de Leva (1996) / Dempster (1955).
# TODO_SCIENTIFIC: These are population-average values, not subject-specific.
# Replace with DEXA-calibrated values when available — see SCIENCE_DECISIONS.md
SEGMENT_DENSITIES_KG_M3: dict[str, float] = {
    "head": 1100.0,
    "trunk": 1000.0,
    "upper_arm_left": 1056.0,
    "upper_arm_right": 1056.0,
    "forearm_left": 1130.0,
    "forearm_right": 1130.0,
    "hand_left": 1160.0,
    "hand_right": 1160.0,
    "thigh_left": 1050.0,
    "thigh_right": 1050.0,
    "shank_left": 1065.0,
    "shank_right": 1065.0,
    "foot_left": 1090.0,
    "foot_right": 1090.0,
}

# Default lung volume (m^3) by sex — used to correct trunk density.
# TODO_SCIENTIFIC: Use a subject-specific measurement (spirometry / CT) when
# available.  Values are ICRP Publication 89 reference lung volumes.
DEFAULT_LUNG_VOLUME_M3: dict[str, float] = {
    "male": 3.0e-3,  # 3.0 L
    "female": 2.3e-3,  # 2.3 L
    "other": 2.65e-3,  # average of the two reference values
}

DENSITY_SOURCE_DEFAULT = "de_Leva_1996"

# ASSUMPTION: a plane offset below this value (m) is treated as "on the plane";
# it is also the tolerance used to detect coincident capping vertices.
_PLANE_TOL_M: float = 1e-9


@dataclass
class SegmentBSP:
    """Body segment parameters for one segment.

    Attributes
    ----------
    name : str
        Segment name, a key of :data:`SEGMENT_DENSITIES_KG_M3`.
    mass_kg : float
        Segment mass in kg.
    com_m : NDArray of shape (3,)
        Centre of mass in the global (mesh) frame, in metres.
    inertia_about_com_kgm2 : NDArray of shape (3, 3)
        Inertia tensor about the segment's centre of mass, in kg.m^2,
        expressed in the global frame axes.
    volume_m3 : float
        Enclosed volume of the segment mesh in m^3.
    density_kg_m3 : float
        Density actually applied (after mass calibration and any lung
        correction).
    density_source : str
        E.g. ``"de_Leva_1996"`` or ``"dexa_calibrated"``.
    validation : dict
        Output of
        :func:`~bodyloop_anthropometrics.geometry.mass_properties.validate_inertia_tensor`.
    warnings : list[str]
        Per-segment caveats (capping, calibration, lung correction, ...).
    """

    name: str
    mass_kg: float
    com_m: NDArray[np.float64]
    inertia_about_com_kgm2: NDArray[np.float64]
    volume_m3: float
    density_kg_m3: float
    density_source: str
    validation: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class BodyBSP:
    """Full-body BSP results.

    Attributes
    ----------
    segments : dict[str, SegmentBSP]
        Successfully computed segments, keyed by segment name.
    total_mass_kg : float
        Sum of segment masses after calibration.
    total_volume_m3 : float
        Sum of segment volumes.
    mass_conservation_error : float
        ``|uncalibrated_total - target_mass| / target_mass``, i.e. the relative
        disagreement between the mesh volume times literature densities and the
        measured body mass, computed *before* calibration.  Should be < 0.01 for
        a clean mesh with correct densities.  After calibration the residual is
        numerically zero by construction, so this pre-calibration figure is the
        informative diagnostic.
    subject_id : str
        Pseudonymised subject ID.
    notes : list[str]
        Provenance and caveats for the whole computation.
    density_scale_factor : float
        Uniform factor applied to every density during calibration.
    uncalibrated_mass_kg : float
        Total mass before calibration, using literature densities as-is.
    failed_segments : dict[str, str]
        Segment name to the reason extraction or integration failed.  Never
        silently imputed (AGENTS.md rule 2).
    """

    segments: dict[str, SegmentBSP]
    total_mass_kg: float
    total_volume_m3: float
    mass_conservation_error: float
    subject_id: str
    notes: list[str] = field(default_factory=list)
    density_scale_factor: float = 1.0
    uncalibrated_mass_kg: float = 0.0
    failed_segments: dict[str, str] = field(default_factory=dict)


def _boundary_loops(faces: NDArray[np.int64]) -> list[list[int]]:
    """Chain boundary edges of an open mesh into closed vertex loops.

    Parameters
    ----------
    faces : NDArray of shape (M, 3)
        Triangle indices.

    Returns
    -------
    list of list of int
        Each inner list is an ordered vertex loop following the boundary
        half-edge direction of the incident faces.

    Notes
    -----
    A boundary half-edge is a directed edge ``(u, v)`` whose opposite ``(v, u)``
    is absent.  Following ``next[v] = w`` chains them into loops.  Loops that do
    not close (non-manifold boundary vertices) are dropped and reported by the
    caller through the watertight check.
    """
    directed = np.concatenate(
        [faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=0
    )
    edge_set = {(int(u), int(v)) for u, v in directed}
    # A vertex touched by two separate holes has several outgoing boundary
    # half-edges, so the successor map must be a multimap, not a dict of one.
    successors: dict[int, list[int]] = {}
    for u, v in sorted(edge_set):
        if (v, u) not in edge_set:
            successors.setdefault(u, []).append(v)

    loops: list[list[int]] = []
    while successors:
        start = next(iter(successors))
        loop = [start]
        current = successors[start].pop()
        if not successors[start]:
            del successors[start]
        while current != start:
            options = successors.get(current)
            if not options:
                loop = []
                break
            loop.append(current)
            nxt = options.pop()
            if not options:
                del successors[current]
            current = nxt
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def _cap_planar_holes(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, list[str]]:
    """Close planar boundary loops with a triangle fan from the loop centroid.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Mesh with open planar boundaries (the result of an uncapped slice).

    Returns
    -------
    tuple of (trimesh.Trimesh, list of str)
        The capped mesh and a list of warnings.

    Notes
    -----
    A fan triangulation from the centroid of a *planar* loop yields exactly the
    correct signed area, hence exactly the correct volume, centroid and inertia
    integrals, even when the loop is non-convex and the fan triangles overlap:
    the signed contributions of the overlapping parts cancel.  This is why no
    polygon-triangulation library (shapely) is required here.

    # ASSUMPTION: boundary loops produced by a planar cut are planar.  A loop
    # whose vertices deviate from their best-fit plane by more than 1e-6 m is
    # reported as a warning, because the exactness argument above no longer
    # holds.

    References
    ----------
    .. [1] Mirtich (1996), Section 2 (signed contributions cancel for closed
           orientable surfaces).
    """
    warnings: list[str] = []
    # NOTE: no merge_vertices() here.  :func:`_clip_to_half_space` already
    # shares cut vertices exactly by index; merging would additionally collapse
    # *distinct* vertices that happen to lie within trimesh's 1e-8 m merge
    # tolerance, which creates degenerate faces and non-manifold edges along the
    # cut and breaks watertightness.
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)

    loops = _boundary_loops(faces)
    if not loops:
        return mesh, warnings

    new_vertices = [vertices]
    new_faces = [faces]
    next_index = vertices.shape[0]
    for loop in loops:
        ring = vertices[np.asarray(loop, dtype=np.int64)]
        centre = ring.mean(axis=0)
        centred = ring - centre
        # Planarity check via the smallest singular value of the ring.
        singular = np.linalg.svd(centred, compute_uv=False)
        if len(singular) == 3 and singular[2] > 1e-6 * max(1.0, float(singular[0])):
            warnings.append(
                f"boundary loop of {len(loop)} vertices is not planar "
                f"(out-of-plane singular value {singular[2]:.3e} m); cap may be inexact"
            )
        fan = np.empty((len(loop), 3), dtype=np.int64)
        for i, vertex_index in enumerate(loop):
            nxt = loop[(i + 1) % len(loop)]
            # Boundary half-edge (vertex_index -> nxt) belongs to one face; the
            # cap triangle must traverse it backwards to stay outward-oriented.
            fan[i] = (nxt, vertex_index, next_index)
        new_vertices.append(centre.reshape(1, 3))
        new_faces.append(fan)
        next_index += 1

    capped = trimesh.Trimesh(
        vertices=np.vstack(new_vertices),
        faces=np.vstack(new_faces),
        process=False,
        validate=False,
    )
    return capped, warnings


def _clip_to_half_space(
    mesh: trimesh.Trimesh,
    origin: NDArray[np.float64],
    normal: NDArray[np.float64],
) -> trimesh.Trimesh:
    """Keep the part of a mesh on the positive side of a plane (uncapped).

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Input mesh.
    origin : NDArray of shape (3,)
        Point on the plane, in metres.
    normal : NDArray of shape (3,)
        Unit plane normal; the half-space ``(x - origin) . normal >= 0`` is kept.

    Returns
    -------
    trimesh.Trimesh
        Open mesh (the planar hole is not filled).  May have zero faces.

    Notes
    -----
    Each straddling triangle is clipped with the Sutherland-Hodgman algorithm,
    which walks the triangle in its original winding order and therefore
    preserves face orientation; the 3- or 4-gon that comes out is fan
    triangulated.

    Intersection points are cached per *undirected* mesh edge, so the two faces
    sharing an edge reference the same new vertex index with bitwise-identical
    coordinates.  That exact sharing is what makes the capped result watertight;
    recomputing the point per face would leave sub-nanometre cracks.

    This replaces ``trimesh.Trimesh.slice_plane``, which pulls in shapely (an
    undeclared optional dependency) even when ``cap=False``.
    """
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    distance = (vertices - origin.reshape(1, 3)) @ normal
    distance[np.abs(distance) < _PLANE_TOL_M] = 0.0

    inside = distance >= 0.0
    kept_count = inside[faces].sum(axis=1)
    fully_inside = faces[kept_count == 3]
    straddling = faces[(kept_count > 0) & (kept_count < 3)]

    new_vertices: list[NDArray[np.float64]] = []
    edge_cache: dict[tuple[int, int], int] = {}
    new_faces: list[list[int]] = []

    def _intersection(i: int, j: int) -> int:
        """Return the index of the cut vertex on undirected edge ``(i, j)``."""
        key = (i, j) if i < j else (j, i)
        cached = edge_cache.get(key)
        if cached is not None:
            return cached
        a, b = key
        t = distance[a] / (distance[a] - distance[b])
        point = vertices[a] + t * (vertices[b] - vertices[a])
        index = len(vertices) + len(new_vertices)
        new_vertices.append(point)
        edge_cache[key] = index
        return index

    for face in straddling:
        polygon: list[int] = []
        for k in range(3):
            current = int(face[k])
            following = int(face[(k + 1) % 3])
            if inside[current]:
                polygon.append(current)
            if distance[current] * distance[following] < 0.0:
                polygon.append(_intersection(current, following))
        for k in range(1, len(polygon) - 1):
            new_faces.append([polygon[0], polygon[k], polygon[k + 1]])

    all_vertices = (
        np.vstack([vertices, np.asarray(new_vertices, dtype=np.float64).reshape(-1, 3)])
        if new_vertices
        else vertices
    )
    all_faces = np.vstack(
        [fully_inside.reshape(-1, 3), np.asarray(new_faces, dtype=np.int64).reshape(-1, 3)]
    )
    if all_faces.shape[0] == 0:
        return trimesh.Trimesh(
            vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False
        )

    clipped = trimesh.Trimesh(
        vertices=all_vertices, faces=all_faces, process=False, validate=False
    )
    clipped.remove_unreferenced_vertices()
    return clipped


def cut_mesh_at_plane(
    mesh: trimesh.Trimesh,
    plane_origin: NDArray[np.float64],
    plane_normal: NDArray[np.float64],
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    """Cut a mesh at a plane, returning two closed submeshes.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Input watertight mesh.
    plane_origin : NDArray of shape (3,)
        A point on the cutting plane, in metres.
    plane_normal : NDArray of shape (3,)
        Plane normal; need not be normalised.

    Returns
    -------
    tuple of (above, below) trimesh.Trimesh
        ``above`` is the part on the side the normal points to, ``below`` the
        opposite part.  Both meshes are closed (caps added at the cut).  Either
        may be empty (zero faces) if the plane misses the mesh.

    Raises
    ------
    ValueError
        If a non-empty resulting submesh is not watertight after capping.

    Notes
    -----
    Slicing is performed by :func:`_clip_to_half_space` and the planar hole is
    closed by :func:`_cap_planar_holes`; both are pure numpy, so no optional
    trimesh dependency (shapely) is required, and the two parts conserve volume
    to round-off: ``V(above) + V(below) == V(mesh)``.
    """
    origin = np.asarray(plane_origin, dtype=np.float64).reshape(3)
    normal = np.asarray(plane_normal, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(normal))
    if norm < _PLANE_TOL_M:
        raise ValueError("plane_normal must be a non-zero vector")
    normal = normal / norm

    pieces: list[trimesh.Trimesh] = []
    for side in (normal, -normal):
        sliced = _clip_to_half_space(mesh, origin, side)
        if sliced is None or len(sliced.faces) == 0:
            pieces.append(trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), int)))
            continue
        capped, cap_warnings = _cap_planar_holes(sliced)
        integrity = check_mesh_integrity(capped.vertices, capped.faces)
        if not integrity["is_watertight"]:
            raise ValueError(
                "Submesh is not watertight after capping at plane "
                f"origin={origin.tolist()} normal={side.tolist()}: "
                f"{integrity['issues']} {cap_warnings}"
            )
        pieces.append(capped)
    return pieces[0], pieces[1]


def _unit(vector: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return a unit vector, raising if the input is degenerate.

    Parameters
    ----------
    vector : NDArray of shape (3,)
        Input vector.

    Returns
    -------
    NDArray of shape (3,)
        Normalised vector.

    Raises
    ------
    ValueError
        If the norm is below ``1e-9`` m (coincident joint positions).
    """
    v = np.asarray(vector, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(v))
    if norm < 1e-9:
        raise ValueError("Degenerate direction: joint positions are coincident")
    return v / norm


def define_segment_boundaries(
    joint_positions: dict[str, NDArray[np.float64]],
) -> list[dict[str, Any]]:
    """Define cutting planes from joint positions.

    Parameters
    ----------
    joint_positions : dict[str, NDArray of shape (3,)]
        Joint names to 3-D positions in the global (mesh) frame, in metres.
        Expected keys: ``"head_top"``, ``"neck"``, ``"left_shoulder"``,
        ``"right_shoulder"``, ``"left_elbow"``, ``"right_elbow"``,
        ``"left_wrist"``, ``"right_wrist"``, ``"left_hip"``, ``"right_hip"``,
        ``"left_knee"``, ``"right_knee"``, ``"left_ankle"``, ``"right_ankle"``.

    Returns
    -------
    list of dict
        Each dict has keys ``'name'``, ``'origin'`` (NDArray ``(3,)``),
        ``'normal'`` (unit NDArray ``(3,)``, pointing from the proximal towards
        the distal segment) and ``'separates'`` — the tuple
        ``(proximal_segment, distal_segment)``.

    Raises
    ------
    KeyError
        If a required joint is missing.  Nothing is imputed (AGENTS.md rule 2).
    ValueError
        If two joints defining a plane normal are coincident.

    Notes
    -----
    # ASSUMPTION: each joint cut is a plane perpendicular to the long axis of
    # the DISTAL segment, passing through the joint centre.  This is the
    # convention of Dempster (1955) and Zatsiorsky-Seluyanov as tabulated by
    # de Leva (1996); it differs from anatomical dissection planes and is the
    # dominant source of systematic difference against cadaver data.

    # ASSUMPTION: the shoulder cut is a plane through the glenohumeral centre
    # perpendicular to the humerus.  This assigns part of the deltoid mass to
    # the trunk, consistent with de Leva (1996) but not with Yeadon (1990),
    # which uses a different shoulder boundary.  Do not compare arm masses
    # between estimators without accounting for this.

    # ASSUMPTION: with the arms hanging, a plane through the glenohumeral
    # centre does NOT disconnect the arm from the trunk — they stay joined
    # through the axilla, which lies below that plane.  A second, parasagittal
    # plane through the glenohumeral centre (``"<side>_axilla"``) performs the
    # lateral separation.  Consequence: tissue lateral to the glenohumeral
    # centre AND proximal to the shoulder plane (the superior deltoid cap) falls
    # in neither the arm nor the trunk.  ``compute_body_bsp`` reports that
    # unassigned volume explicitly instead of redistributing it.
    # TODO_SCIENTIFIC: choose the definitive shoulder boundary convention and
    # decide where the deltoid cap belongs — see SCIENCE_DECISIONS.md

    # ASSUMPTION: an additional mid-sagittal plane through the hip midpoint is
    # needed to separate the left and right thighs, because a hip cut alone
    # leaves them connected through the perineal region.  It is listed as
    # ``"sagittal_pelvis"`` with ``separates=("thigh_right", "thigh_left")``.

    References
    ----------
    .. [1] de Leva, P. (1996). J Biomech 29(9):1223-1230, Table 1
           (segment endpoint definitions).
    .. [2] Dempster, W.T. (1955). WADC TR 55-159.
    """
    required = (
        "head_top",
        "neck",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    )
    missing = [key for key in required if key not in joint_positions]
    if missing:
        raise KeyError(f"Missing joint position(s) for segment boundaries: {missing}")

    joints = {
        key: np.asarray(joint_positions[key], dtype=np.float64).reshape(3) for key in required
    }

    planes: list[dict[str, Any]] = [
        {
            "name": "neck",
            "origin": joints["neck"],
            "normal": _unit(joints["head_top"] - joints["neck"]),
            "separates": ("trunk", "head"),
        }
    ]

    shoulder_mid = 0.5 * (joints["left_shoulder"] + joints["right_shoulder"])
    for side in ("left", "right"):
        shoulder = joints[f"{side}_shoulder"]
        elbow = joints[f"{side}_elbow"]
        wrist = joints[f"{side}_wrist"]
        hip = joints[f"{side}_hip"]
        knee = joints[f"{side}_knee"]
        ankle = joints[f"{side}_ankle"]
        upper_arm_axis = _unit(elbow - shoulder)
        forearm_axis = _unit(wrist - elbow)
        thigh_axis = _unit(knee - hip)
        shank_axis = _unit(ankle - knee)
        planes.extend(
            [
                {
                    "name": f"{side}_shoulder",
                    "origin": shoulder,
                    "normal": upper_arm_axis,
                    "separates": ("trunk", f"upper_arm_{side}"),
                },
                {
                    "name": f"{side}_axilla",
                    "origin": shoulder,
                    "normal": _unit(shoulder - shoulder_mid),
                    "separates": ("trunk", f"upper_arm_{side}"),
                },
                {
                    "name": f"{side}_elbow",
                    "origin": elbow,
                    "normal": forearm_axis,
                    "separates": (f"upper_arm_{side}", f"forearm_{side}"),
                },
                {
                    "name": f"{side}_wrist",
                    "origin": wrist,
                    "normal": forearm_axis,
                    "separates": (f"forearm_{side}", f"hand_{side}"),
                },
                {
                    "name": f"{side}_hip",
                    "origin": hip,
                    "normal": thigh_axis,
                    "separates": ("trunk", f"thigh_{side}"),
                },
                {
                    "name": f"{side}_knee",
                    "origin": knee,
                    "normal": shank_axis,
                    "separates": (f"thigh_{side}", f"shank_{side}"),
                },
                {
                    "name": f"{side}_ankle",
                    "origin": ankle,
                    "normal": shank_axis,
                    "separates": (f"shank_{side}", f"foot_{side}"),
                },
            ]
        )

    planes.append(
        {
            "name": "sagittal_pelvis",
            "origin": 0.5 * (joints["left_hip"] + joints["right_hip"]),
            "normal": _unit(joints["left_hip"] - joints["right_hip"]),
            "separates": ("thigh_right", "thigh_left"),
        }
    )
    return planes


# Half-space recipe per segment: (plane name, side) where side = +1 keeps the
# part the plane normal points to (the distal side) and -1 the proximal side.
_SEGMENT_HALFSPACES: dict[str, tuple[tuple[str, int], ...]] = {
    "head": (("neck", +1),),
    "trunk": (
        ("neck", -1),
        ("left_axilla", -1),
        ("right_axilla", -1),
        ("left_hip", -1),
        ("right_hip", -1),
    ),
    "upper_arm_left": (("left_axilla", +1), ("left_shoulder", +1), ("left_elbow", -1)),
    "upper_arm_right": (("right_axilla", +1), ("right_shoulder", +1), ("right_elbow", -1)),
    "forearm_left": (("left_elbow", +1), ("left_wrist", -1)),
    "forearm_right": (("right_elbow", +1), ("right_wrist", -1)),
    "hand_left": (("left_wrist", +1),),
    "hand_right": (("right_wrist", +1),),
    "thigh_left": (("left_hip", +1), ("left_knee", -1), ("sagittal_pelvis", +1)),
    "thigh_right": (("right_hip", +1), ("right_knee", -1), ("sagittal_pelvis", -1)),
    "shank_left": (("left_knee", +1), ("left_ankle", -1)),
    "shank_right": (("right_knee", +1), ("right_ankle", -1)),
    "foot_left": (("left_ankle", +1),),
    "foot_right": (("right_ankle", +1),),
}

# Joint whose position identifies the correct connected component of a segment.
_SEGMENT_ANCHOR_JOINTS: dict[str, tuple[str, ...]] = {
    "head": ("neck", "head_top"),
    "trunk": ("neck", "left_hip", "right_hip"),
    "upper_arm_left": ("left_shoulder", "left_elbow"),
    "upper_arm_right": ("right_shoulder", "right_elbow"),
    "forearm_left": ("left_elbow", "left_wrist"),
    "forearm_right": ("right_elbow", "right_wrist"),
    "hand_left": ("left_wrist",),
    "hand_right": ("right_wrist",),
    "thigh_left": ("left_hip", "left_knee"),
    "thigh_right": ("right_hip", "right_knee"),
    "shank_left": ("left_knee", "left_ankle"),
    "shank_right": ("right_knee", "right_ankle"),
    "foot_left": ("left_ankle",),
    "foot_right": ("right_ankle",),
}


def _select_component(
    mesh: trimesh.Trimesh,
    anchor: NDArray[np.float64],
) -> tuple[trimesh.Trimesh, list[str]]:
    """Keep the connected component closest to an anatomical anchor point.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Possibly disconnected mesh resulting from successive plane cuts.
    anchor : NDArray of shape (3,)
        Reference point (typically the mean of the segment's joint centres).

    Returns
    -------
    tuple of (trimesh.Trimesh, list of str)
        The selected component and any warnings raised.

    Notes
    -----
    # ASSUMPTION: after all bounding cuts, the target segment is the connected
    # component that contains the segment's anatomical anchor point, or failing
    # that the one whose SURFACE passes closest to it.  Discarded components are
    # reported as warnings with their volume so that a badly-placed cutting
    # plane cannot silently drop tissue.

    Distance is measured to the closest point of the component's triangles, not
    to its nearest vertex: vertex distance depends on tessellation density (a
    trimesh cylinder carries vertices only on its two end rings) and picks the
    wrong component on coarse meshes.
    """
    warnings: list[str] = []
    components = mesh.split(only_watertight=False)
    if len(components) <= 1:
        return mesh, warnings

    query = anchor.reshape(1, 3)
    distances: list[float] = []
    contains: list[bool] = []
    for component in components:
        _, distance, _ = trimesh.proximity.closest_point_naive(component, query)
        distances.append(float(distance[0]))
        try:
            contains.append(bool(component.contains(query)[0]))
        except BaseException:  # noqa: BLE001 - ray engine issues must not abort BSP
            contains.append(False)

    if sum(contains) == 1:
        best = contains.index(True)
    else:
        best = int(np.argmin(distances))
    discarded_volume = sum(
        abs(compute_volume(c.vertices, c.faces)) for i, c in enumerate(components) if i != best
    )
    kept_volume = abs(compute_volume(components[best].vertices, components[best].faces))
    warnings.append(
        f"{len(components)} connected components after cutting; kept the one "
        f"{distances[best] * 1e3:.1f} mm from the anchor "
        f"(anchor {'inside' if contains[best] else 'outside'} it; "
        f"kept {kept_volume * 1e3:.3f} L, discarded {discarded_volume * 1e3:.3f} L)"
    )
    return components[best], warnings


def _extract_segment_mesh(
    mesh: trimesh.Trimesh,
    segment: str,
    planes_by_name: dict[str, dict[str, Any]],
    joints: dict[str, NDArray[np.float64]],
) -> tuple[trimesh.Trimesh, list[str]]:
    """Cut the full-body mesh down to a single closed segment mesh.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Watertight full-body mesh.
    segment : str
        Segment name, a key of :data:`_SEGMENT_HALFSPACES`.
    planes_by_name : dict[str, dict]
        Planes from :func:`define_segment_boundaries`, keyed by name.
    joints : dict[str, NDArray]
        Joint positions, used to anchor connected-component selection.

    Returns
    -------
    tuple of (trimesh.Trimesh, list of str)
        Closed segment mesh and accumulated warnings.

    Raises
    ------
    ValueError
        If a cut leaves nothing, or the result is not watertight.
    """
    warnings: list[str] = []
    current = mesh
    for plane_name, side in _SEGMENT_HALFSPACES[segment]:
        plane = planes_by_name[plane_name]
        above, below = cut_mesh_at_plane(current, plane["origin"], plane["normal"])
        current = above if side > 0 else below
        if len(current.faces) == 0:
            raise ValueError(
                f"cut at plane '{plane_name}' (side {side:+d}) left an empty mesh"
            )

    anchor = np.mean(
        [joints[j] for j in _SEGMENT_ANCHOR_JOINTS[segment]], axis=0
    ).astype(np.float64)
    current, component_warnings = _select_component(current, anchor)
    warnings.extend(component_warnings)

    integrity = check_mesh_integrity(current.vertices, current.faces)
    if not integrity["is_watertight"]:
        raise ValueError(f"segment mesh is not watertight: {integrity['issues']}")
    if not integrity["volume_positive"]:
        raise ValueError(f"segment mesh has non-positive volume: {integrity['issues']}")
    return current, warnings


def compute_body_bsp(
    mesh_path: str | Path,
    joint_positions: dict[str, NDArray[np.float64]],
    target_mass_kg: float,
    sex: str = "male",
    subject_id: str = "unknown",
    densities: dict[str, float] | None = None,
    *,
    apply_lung_correction: bool = False,
    lung_volume_m3: float | None = None,
) -> BodyBSP:
    """Compute BSP for all body segments from a mesh file.

    Parameters
    ----------
    mesh_path : str or Path
        Path to a GLB or OBJ mesh file (the body surface, not the avatar).
    joint_positions : dict[str, NDArray]
        Joint positions in the same frame and units (metres) as the mesh.
    target_mass_kg : float
        Known total body mass, used for calibration.
    sex : str, optional
        ``"male"``, ``"female"`` or ``"other"``.  Selects the default lung
        volume; only used when ``apply_lung_correction`` is true.
    subject_id : str, optional
        Pseudonymised subject ID.
    densities : dict or None, optional
        Override segment densities in kg/m^3.  Defaults to
        :data:`SEGMENT_DENSITIES_KG_M3`.
    apply_lung_correction : bool, keyword-only, optional
        Subtract the pulmonary air volume from the trunk mass.  Default
        ``False``.

        # TODO_SCIENTIFIC: the de Leva / Dempster trunk density is a whole-trunk
        # average that already includes the pulmonary cavity, so enabling this
        # correction on top of it double-counts the lungs.  Enable it only with
        # a lung-free tissue density — see SCIENCE_DECISIONS.md
    lung_volume_m3 : float or None, keyword-only, optional
        Subject-specific lung volume.  Defaults to
        :data:`DEFAULT_LUNG_VOLUME_M3` for ``sex``.

    Returns
    -------
    BodyBSP
        Segment results plus calibration and provenance metadata.

    Raises
    ------
    FileNotFoundError
        If ``mesh_path`` does not exist.
    ValueError
        If the mesh is not watertight, ``target_mass_kg`` is not positive, or
        no segment could be extracted.
    KeyError
        If a required joint position is missing.

    Notes
    -----
    Mass calibration: densities are uniformly scaled so that the computed total
    mass matches ``target_mass_kg``.  This preserves relative density ratios,
    and the scale factor is reported in ``BodyBSP.density_scale_factor`` — a
    factor far from 1.0 indicates a mesh scale error, a segmentation error, or
    inappropriate densities, and must be investigated rather than accepted.

    Segments that cannot be extracted are recorded in ``BodyBSP.failed_segments``
    with a reason, never imputed (AGENTS.md rule 2).  Their volume is therefore
    missing from the calibration, which biases the scale factor upwards; a
    warning note is added when that happens.

    # ASSUMPTION: the mesh is a closed surface of the whole body in metres, in
    # the same frame as ``joint_positions``.  No units conversion is attempted.
    """
    path = Path(mesh_path)
    if not path.exists():
        raise FileNotFoundError(f"Mesh file not found: {path}")
    if not target_mass_kg > 0.0:
        raise ValueError(f"target_mass_kg must be strictly positive, got {target_mass_kg}")
    if sex not in DEFAULT_LUNG_VOLUME_M3:
        raise ValueError(f"sex must be one of {sorted(DEFAULT_LUNG_VOLUME_M3)}, got '{sex}'")

    loaded = trimesh.load(path, force="mesh", process=True)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"{path} does not contain a single triangular mesh")
    mesh: trimesh.Trimesh = loaded
    mesh.merge_vertices()

    notes: list[str] = [
        f"mesh={path.name}",
        f"density_source={DENSITY_SOURCE_DEFAULT} (population average, NOT subject-specific)",
        "uniform density assumed within each segment (see SCIENCE_DECISIONS.md)",
        "internal cavities (lungs, gut gas) are not represented by the surface mesh",
    ]

    integrity = check_mesh_integrity(mesh.vertices, mesh.faces)
    if not integrity["is_watertight"]:
        raise ValueError(
            f"Input mesh is not watertight; repair it first "
            f"(geometry.mesh_repair). Issues: {integrity['issues']}"
        )
    if not integrity["volume_positive"]:
        raise ValueError(
            f"Input mesh has inward-facing normals (volume {integrity['volume_m3']:.4e} m^3)"
        )
    notes.append(
        f"mesh volume={integrity['volume_m3'] * 1e3:.2f} L, "
        f"{integrity['face_count']} faces"
    )

    density_map = dict(SEGMENT_DENSITIES_KG_M3 if densities is None else densities)
    planes = define_segment_boundaries(joint_positions)
    planes_by_name = {plane["name"]: plane for plane in planes}
    joints = {
        key: np.asarray(value, dtype=np.float64).reshape(3)
        for key, value in joint_positions.items()
    }

    raw: dict[str, dict[str, Any]] = {}
    failed: dict[str, str] = {}
    for segment in _SEGMENT_HALFSPACES:
        try:
            segment_mesh, warnings = _extract_segment_mesh(
                mesh, segment, planes_by_name, joints
            )
        except (ValueError, KeyError, IndexError) as exc:  # noqa: PERF203
            failed[segment] = str(exc)
            continue
        volume = compute_volume(segment_mesh.vertices, segment_mesh.faces)
        centroid = compute_centroid(segment_mesh.vertices, segment_mesh.faces)
        raw[segment] = {
            "volume_m3": volume,
            "centroid_m": centroid,
            "vertices": np.asarray(segment_mesh.vertices, dtype=np.float64),
            "faces": np.asarray(segment_mesh.faces, dtype=np.int64),
            "warnings": warnings,
        }

    if not raw:
        raise ValueError(
            f"No segment could be extracted from {path.name}; "
            f"reasons: {failed}"
        )
    if failed:
        notes.append(
            f"{len(failed)} segment(s) failed extraction and are EXCLUDED from "
            f"calibration: {sorted(failed)}"
        )

    # Volume conservation: segments partition the body only up to the boundary
    # convention, so any unassigned (or double-counted) volume must be visible.
    segmented_volume = sum(float(entry["volume_m3"]) for entry in raw.values())
    body_volume = float(integrity["volume_m3"])
    volume_residual = (segmented_volume - body_volume) / body_volume
    notes.append(
        f"segmented volume={segmented_volume * 1e3:.2f} L vs whole-body "
        f"{body_volume * 1e3:.2f} L ({volume_residual * 100:+.2f}%)"
    )
    if not failed and abs(volume_residual) > 0.02:
        notes.append(
            "WARNING: more than 2% of the body volume is unassigned or double-counted "
            "by the segment boundaries (typically the deltoid cap at the shoulder "
            "convention); segment masses are biased accordingly"
        )

    # Lung correction (effective trunk density), before calibration.
    effective_density = dict(density_map)
    lung_note: str | None = None
    if apply_lung_correction and "trunk" in raw:
        v_lung = (
            DEFAULT_LUNG_VOLUME_M3[sex] if lung_volume_m3 is None else float(lung_volume_m3)
        )
        v_trunk = raw["trunk"]["volume_m3"]
        if v_lung >= v_trunk:
            raise ValueError(
                f"lung volume ({v_lung:.4f} m^3) exceeds trunk volume ({v_trunk:.4f} m^3)"
            )
        effective_density["trunk"] = density_map["trunk"] * (1.0 - v_lung / v_trunk)
        lung_note = (
            f"trunk density corrected for {v_lung * 1e3:.1f} L of pulmonary air "
            f"({density_map['trunk']:.0f} -> {effective_density['trunk']:.1f} kg/m^3, "
            f"source={'ICRP_89' if lung_volume_m3 is None else 'subject_specific'})"
        )
        notes.append(lung_note)
    elif "trunk" in raw:
        notes.append(
            "pulmonary volume correction DISABLED (default): the de Leva/Dempster "
            "trunk density already averages over the lung cavity — see SCIENCE_DECISIONS.md"
        )

    missing_density = [segment for segment in raw if segment not in effective_density]
    if missing_density:
        raise KeyError(f"No density provided for segment(s): {missing_density}")

    uncalibrated_mass = sum(
        effective_density[segment] * raw[segment]["volume_m3"] for segment in raw
    )
    mass_conservation_error = abs(uncalibrated_mass - target_mass_kg) / target_mass_kg
    scale = target_mass_kg / uncalibrated_mass
    notes.append(
        f"uncalibrated mass={uncalibrated_mass:.3f} kg vs target={target_mass_kg:.3f} kg "
        f"(relative error {mass_conservation_error * 100:.2f}%); "
        f"densities uniformly scaled by {scale:.4f}"
    )
    if mass_conservation_error > 0.01:
        notes.append(
            "WARNING: pre-calibration mass error exceeds 1% — check mesh scale, "
            "segmentation planes and density choice before using these BSPs"
        )

    segments: dict[str, SegmentBSP] = {}
    total_mass = 0.0
    total_volume = 0.0
    for segment, data in raw.items():
        density = effective_density[segment] * scale
        volume = float(data["volume_m3"])
        mass = density * volume
        inertia_origin = compute_inertia_tensor(
            data["vertices"], data["faces"], density=density
        )
        centroid = data["centroid_m"]
        inertia_com = parallel_axis_theorem(inertia_origin, mass, centroid)
        validation = validate_inertia_tensor(inertia_com, mass, centroid)

        warnings = list(data["warnings"])
        warnings.append(
            f"density scaled by {scale:.4f} to match target body mass "
            f"(literature value {density_map[segment]:.0f} kg/m^3)"
        )
        if segment == "trunk" and lung_note is not None:
            warnings.append(lung_note)
        if validation["issues"]:
            warnings.extend(validation["issues"])

        segments[segment] = SegmentBSP(
            name=segment,
            mass_kg=mass,
            com_m=centroid,
            inertia_about_com_kgm2=inertia_com,
            volume_m3=volume,
            density_kg_m3=density,
            density_source=(
                DENSITY_SOURCE_DEFAULT if densities is None else "caller_supplied"
            )
            + "+mass_calibrated",
            validation=validation,
            warnings=warnings,
        )
        total_mass += mass
        total_volume += volume

    return BodyBSP(
        segments=segments,
        total_mass_kg=total_mass,
        total_volume_m3=total_volume,
        mass_conservation_error=mass_conservation_error,
        subject_id=subject_id,
        notes=notes,
        density_scale_factor=scale,
        uncalibrated_mass_kg=uncalibrated_mass,
        failed_segments=failed,
    )


def compute_all_bsp(
    segmented_meshes: dict[str, trimesh.Trimesh],
    density_map: dict[str, float] | None = None,
) -> dict[str, dict[str, object]]:
    """Compute BSPs for all body segments from already-segmented meshes.

    Parameters
    ----------
    segmented_meshes : dict[str, trimesh.Trimesh]
        Mapping of segment name to watertight mesh, as produced by
        :func:`~geometry.mesh_repair.split_body_segments` or by
        :func:`cut_mesh_at_plane`.
    density_map : dict[str, float] or None, optional
        Mapping of segment name to volumetric density in kg/m^3.  If ``None``,
        uses :data:`SEGMENT_DENSITIES_KG_M3`, falling back to the generic keys
        of :data:`~geometry.mass_properties.SEGMENT_DENSITY_KG_M3`
        (``"thigh"`` for ``"thigh_left"``, ...).

    Returns
    -------
    dict[str, dict[str, object]]
        Outer key: segment name.  Inner dict: ``"mass_kg"``, ``"volume_m3"``,
        ``"centroid_m"``, ``"inertia_tensor_kgm2"``, ``"density_kg_m3"``,
        ``"density_source"``, ``"validation"``.

    Raises
    ------
    KeyError
        If no density can be resolved for a segment.
    ValueError
        If a segment mesh is not watertight or encloses a non-positive volume.

    Notes
    -----
    No mass calibration is applied here — use :func:`compute_body_bsp` for the
    calibrated full-body pipeline.

    # TODO_SCIENTIFIC: density values must be justified for the specific
    # population studied — see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] Dempster, W.T. (1955). WADC TR 55-159.
    .. [2] de Leva, P. (1996). J Biomech 29(9):1223-1230.
    """
    results: dict[str, dict[str, object]] = {}
    for name, segment_mesh in segmented_meshes.items():
        if density_map is not None and name in density_map:
            density = density_map[name]
            source = "caller_supplied"
        elif name in SEGMENT_DENSITIES_KG_M3:
            density = SEGMENT_DENSITIES_KG_M3[name]
            source = DENSITY_SOURCE_DEFAULT
        else:
            generic = name.removesuffix("_left").removesuffix("_right")
            if generic not in SEGMENT_DENSITY_KG_M3:
                raise KeyError(f"No density available for segment '{name}'")
            density = SEGMENT_DENSITY_KG_M3[generic]
            source = "de_Leva_1996/Dempster_1955 (generic segment key)"

        integrity = check_mesh_integrity(segment_mesh.vertices, segment_mesh.faces)
        if not integrity["is_watertight"]:
            raise ValueError(f"Segment '{name}' is not watertight: {integrity['issues']}")
        volume = float(integrity["volume_m3"])
        if volume <= 0.0:
            raise ValueError(f"Segment '{name}' has non-positive volume ({volume:.4e} m^3)")

        centroid = compute_centroid(segment_mesh.vertices, segment_mesh.faces)
        mass = density * volume
        inertia_com = parallel_axis_theorem(
            compute_inertia_tensor(segment_mesh.vertices, segment_mesh.faces, density=density),
            mass,
            centroid,
        )
        results[name] = {
            "mass_kg": mass,
            "volume_m3": volume,
            "centroid_m": centroid,
            "inertia_tensor_kgm2": inertia_com,
            "density_kg_m3": density,
            "density_source": source,
            "validation": validate_inertia_tensor(inertia_com, mass, centroid),
        }
    return results


def _segment_scalars(values: dict[str, object]) -> dict[str, tuple[float, str]]:
    """Flatten one BSP dict into named scalars with units.

    Parameters
    ----------
    values : dict[str, object]
        One inner dict from :func:`compute_all_bsp`.

    Returns
    -------
    dict[str, tuple[float, str]]
        Property name to ``(value, unit)``.
    """
    centroid = np.asarray(values["centroid_m"], dtype=np.float64).reshape(3)
    inertia = np.asarray(values["inertia_tensor_kgm2"], dtype=np.float64).reshape(3, 3)
    scalars: dict[str, tuple[float, str]] = {
        "mass": (float(values["mass_kg"]), "kg"),  # type: ignore[arg-type]
        "volume": (float(values["volume_m3"]), "m^3"),  # type: ignore[arg-type]
        "com_x": (float(centroid[0]), "m"),
        "com_y": (float(centroid[1]), "m"),
        "com_z": (float(centroid[2]), "m"),
    }
    labels = (("xx", 0, 0), ("yy", 1, 1), ("zz", 2, 2), ("xy", 0, 1), ("xz", 0, 2), ("yz", 1, 2))
    for label, i, j in labels:
        scalars[f"i{label}"] = (float(inertia[i, j]), "kg*m^2")
    return scalars


def bsp_to_measurements(
    bsp: dict[str, dict[str, object]],
) -> dict[str, dict[str, Measurement]]:
    """Convert raw BSP dictionaries into :class:`Measurement` objects.

    Parameters
    ----------
    bsp : dict[str, dict[str, object]]
        Output of :func:`compute_all_bsp`.

    Returns
    -------
    dict[str, dict[str, Measurement]]
        Outer key: segment name.  Inner key: property name (``"mass"``,
        ``"volume"``, ``"com_x"``, ``"ixx"``, ...).

    Notes
    -----
    All :class:`Measurement` objects produced here have ``source="calculated"``
    and ``frame="bodyloop_global"``.  ``manual_validation_required`` is set
    because the underlying densities are uncalibrated population averages and
    the inertia tensor validation may carry issues.

    # ASSUMPTION: confidence 0.7 for mass/inertia (density-dependent) and 0.9
    # for volume (purely geometric).  These are engineering placeholders.
    # TODO_SCIENTIFIC: replace with an uncertainty propagated from the density
    # and mesh-resolution error budget — see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] :class:`~measurement_mapping.Measurement`.
    """
    measurements: dict[str, dict[str, Measurement]] = {}
    for segment, values in bsp.items():
        validation = values.get("validation") or {}
        issues = validation.get("issues", []) if isinstance(validation, dict) else []
        note = f"density_source={values.get('density_source', 'unknown')}"
        if issues:
            note += f"; validation_issues={issues}"
        per_segment: dict[str, Measurement] = {}
        for name, (value, unit) in _segment_scalars(values).items():
            per_segment[name] = Measurement(
                value=value,
                unit=unit,
                frame="bodyloop_global",
                source="calculated",
                confidence=0.9 if name == "volume" else 0.7,
                bodyloop_path=None,
                notes=note,
                manual_validation_required=True,
            )
        measurements[segment] = per_segment
    return measurements


def export_bsp_json(
    measurements: dict[str, dict[str, Measurement]],
    output_path: str | Path,
) -> None:
    """Serialise BSP measurements to a JSON file.

    Parameters
    ----------
    measurements : dict[str, dict[str, Measurement]]
        Output of :func:`bsp_to_measurements`.
    output_path : str or Path
        Destination ``.json`` file path.  Parent directories are created.

    Returns
    -------
    None

    Notes
    -----
    The JSON layout is ``{segment: {property: <Measurement fields>}}`` so that
    the biorbd and OpenSim exporters can read BSPs without recomputing them.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        segment: {name: value.model_dump() for name, value in properties.items()}
        for segment, properties in measurements.items()
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
