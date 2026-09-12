"""Coordinate-system normalisation and reference-frame conversions.

All internal coordinates are expressed in SI units (metres) in a right-handed
frame with +Y pointing up, +X pointing right (from the subject's perspective),
and +Z pointing forward — the ``bodyloop_global`` frame.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def normalize_to_global_frame(
    points: NDArray[np.float64],
    source_frame: str,
) -> NDArray[np.float64]:
    """Transform a point cloud into the ``bodyloop_global`` reference frame.

    Parameters
    ----------
    points : NDArray[np.float64]
        Array of shape ``(N, 3)`` containing 3-D coordinates in the source
        frame.
    source_frame : str
        Name of the input reference frame, e.g. ``"scanner_raw"``,
        ``"anatomical_local_right"``, ``"bodyloop_v1"``.

    Returns
    -------
    NDArray[np.float64]
        Array of shape ``(N, 3)`` in ``bodyloop_global`` coordinates.

    Raises
    ------
    NotImplementedError
        Always — the mapping for each source frame must be implemented
        after consulting BodyLoop documentation.
    ValueError
        If ``source_frame`` is empty or ``points`` does not have shape
        ``(N, 3)``.

    Notes
    -----
    Internal unit convention: metres.

    References
    ----------
    .. [1] BodyLoop SDK documentation (internal).
    """
    # TODO: implement per-frame rigid-body transform look-up table
    raise NotImplementedError(
        f"Frame conversion from '{source_frame}' to 'bodyloop_global' is not yet "
        "implemented.  Consult the BodyLoop SDK coordinate-system documentation "
        "and populate the transform registry."
    )


def compute_symmetry_plane(
    mesh_vertices: NDArray[np.float64],
) -> tuple[NDArray[np.float64], float]:
    """Estimate the best-fit bilateral symmetry plane of a body mesh.

    Parameters
    ----------
    mesh_vertices : NDArray[np.float64]
        Array of shape ``(N, 3)`` containing all mesh vertex positions in
        ``bodyloop_global`` coordinates.

    Returns
    -------
    normal : NDArray[np.float64]
        Unit normal vector ``(3,)`` of the symmetry plane.
    offset : float
        Signed distance from the origin to the plane along ``normal``
        (i.e. the plane equation is ``normal @ x == offset``).

    Raises
    ------
    NotImplementedError
        Always — iterative closest-point or ICP-based symmetry fitting must
        be implemented.

    Notes
    -----
    A reliable symmetry plane is required before any left/right landmark
    extraction.

    References
    ----------
    .. [1] Martinet, A. et al. (2006). 3D Shape Matching by Decomposition
           into Primitive Shapes. Comput. Graph. Forum.
    """
    # TODO: implement ICP-based bilateral symmetry plane estimation
    raise NotImplementedError(
        "Symmetry-plane estimation is not yet implemented.  "
        "See 'TODO: implement ICP-based bilateral symmetry plane estimation'."
    )


def project_landmarks_to_frame(
    landmarks: dict[str, NDArray[np.float64]],
    target_frame: str,
) -> dict[str, NDArray[np.float64]]:
    """Project named anatomical landmarks into a target reference frame.

    Parameters
    ----------
    landmarks : dict[str, NDArray[np.float64]]
        Mapping of landmark name to position array ``(3,)`` in
        ``bodyloop_global`` coordinates.
    target_frame : str
        Destination frame identifier.

    Returns
    -------
    dict[str, NDArray[np.float64]]
        Same landmark names mapped to positions in ``target_frame``.

    Raises
    ------
    NotImplementedError
        Always — requires the frame transform registry from
        :func:`normalize_to_global_frame`.

    Notes
    -----
    Internal units: metres.

    References
    ----------
    .. [1] BodyLoop SDK documentation (internal).
    """
    # TODO: re-use transform registry from normalize_to_global_frame
    raise NotImplementedError(
        "Landmark projection is not yet implemented.  "
        "Implement the frame transform registry first."
    )
