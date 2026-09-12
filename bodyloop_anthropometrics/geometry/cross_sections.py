"""Planar cross-section extraction from trimesh meshes.

Cross-sections are used to compute perimeters (girths), areas, and shape
descriptors required by Yeadon's (1990) and Hatze's (1979) models, as well
as by stadium-solid approximations.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

import trimesh


def extract_cross_section(
    mesh: trimesh.Trimesh,
    plane_origin: NDArray[np.float64],
    plane_normal: NDArray[np.float64],
) -> trimesh.path.path.Path3D:
    """Compute the intersection polygon of a plane with a trimesh mesh.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Watertight body-segment mesh in ``bodyloop_global`` coordinates.
    plane_origin : NDArray[np.float64]
        A point ``(3,)`` lying on the cutting plane, in metres.
    plane_normal : NDArray[np.float64]
        Unit normal vector ``(3,)`` of the cutting plane.

    Returns
    -------
    trimesh.path.path.Path3D
        Closed 3-D path representing the cross-section boundary.

    Raises
    ------
    NotImplementedError
        Always — wrapping and error-handling around ``trimesh.intersections``
        must be implemented.
    ValueError
        If ``plane_normal`` has zero magnitude.

    Notes
    -----
    The plane normal must be normalised before calling trimesh; this function
    should enforce that internally.

    References
    ----------
    .. [1] trimesh.intersections.mesh_plane documentation.
    """
    # TODO: implement using trimesh.intersections.mesh_plane
    raise NotImplementedError(
        "Cross-section extraction is not yet implemented.  "
        "Use trimesh.intersections.mesh_plane and validate on synthetic data."
    )


def compute_section_perimeter(section: trimesh.path.path.Path3D) -> float:
    """Return the arc length (perimeter) of a closed cross-section path.

    Parameters
    ----------
    section : trimesh.path.path.Path3D
        Closed 3-D cross-section path from :func:`extract_cross_section`.

    Returns
    -------
    float
        Perimeter in metres.

    Raises
    ------
    NotImplementedError
        Always.
    ValueError
        If ``section`` is not closed.

    Notes
    -----
    Used to compute girths (circumferences) for Yeadon's measurement set.

    References
    ----------
    .. [1] Yeadon, M.R. (1990). The simulation of aerial movement — II.
           J Biomech 23(1):67-74.
    """
    # TODO: sum segment lengths of the 3-D path
    raise NotImplementedError("Section perimeter computation is not yet implemented.")


def compute_section_area(section: trimesh.path.path.Path3D) -> float:
    """Return the enclosed area of a planar cross-section.

    Parameters
    ----------
    section : trimesh.path.path.Path3D
        Closed 3-D cross-section path from :func:`extract_cross_section`.

    Returns
    -------
    float
        Enclosed area in square metres.

    Raises
    ------
    NotImplementedError
        Always.
    ValueError
        If ``section`` is not planar or not closed.

    Notes
    -----
    Used by Hatze's segment model and for stadium-solid approximations.

    References
    ----------
    .. [1] Hatze, H. (1979). CSIR Technical Report TWISK 79.
    """
    # TODO: project to 2-D, then apply shoelace formula or trimesh polygon area
    raise NotImplementedError("Section area computation is not yet implemented.")


def extract_girths_at_landmarks(
    mesh: trimesh.Trimesh,
    landmark_heights: dict[str, float],
    up_axis: int = 1,
) -> dict[str, float]:
    """Extract circumference measurements at a set of landmark heights.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Full-body mesh in ``bodyloop_global`` coordinates.
    landmark_heights : dict[str, float]
        Mapping of anatomical landmark name to height along ``up_axis``,
        in metres.  Example: ``{"waist": 1.02, "hip": 0.93}``.
    up_axis : int, optional
        Axis index for height (0=X, 1=Y, 2=Z).  Default ``1`` (Y-up).

    Returns
    -------
    dict[str, float]
        Mapping of landmark name to girth (perimeter) in metres.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    Girths extracted here should be cross-validated against BodyLoop's own
    distance measurements when available.

    References
    ----------
    .. [1] ISO 8559-1:2017 — Body measurements and definitions.
    """
    # TODO: loop over landmark_heights, call extract_cross_section + compute_section_perimeter
    raise NotImplementedError(
        "Bulk girth extraction at landmarks is not yet implemented."
    )
