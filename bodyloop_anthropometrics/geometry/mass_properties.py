"""Volumetric mass properties — volume, centroid, and inertia tensor.

Computed directly from the 3-D mesh using divergence-theorem integration
(implemented in trimesh).  Density values are a scientific decision — see
``SCIENCE_DECISIONS.md`` and the ``# TODO_SCIENTIFIC`` markers below.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

import trimesh


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


def compute_volume(mesh: trimesh.Trimesh) -> float:
    """Compute the signed volume of a watertight mesh.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Watertight mesh.  **Must** pass :func:`~geometry.mesh_repair.assert_watertight`
        before calling this function.

    Returns
    -------
    float
        Volume in cubic metres (m³).

    Raises
    ------
    NotImplementedError
        Always — validation wrapper around ``trimesh.Trimesh.volume`` must be
        implemented.
    ValueError
        If ``mesh`` is not watertight.

    Notes
    -----
    Uses the divergence theorem over triangle faces.  Negative volume indicates
    inverted winding; call :func:`~geometry.mesh_repair.repair_mesh` first.

    References
    ----------
    .. [1] trimesh.Trimesh.volume property.
    """
    # TODO: call assert_watertight, then return mesh.volume
    raise NotImplementedError("Volume computation wrapper is not yet implemented.")


def compute_centroid(mesh: trimesh.Trimesh) -> NDArray[np.float64]:
    """Compute the volumetric centroid (centre of volume) of a watertight mesh.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Watertight mesh.

    Returns
    -------
    NDArray[np.float64]
        Centroid coordinates ``(3,)`` in ``bodyloop_global`` frame, in metres.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    The volumetric centroid equals the centre of mass only if the segment has
    uniform density.

    # TODO_SCIENTIFIC: assess whether uniform-density assumption is acceptable
    # for each segment — see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] trimesh.Trimesh.center_mass property.
    """
    # TODO: return mesh.center_mass (requires watertight mesh)
    raise NotImplementedError("Centroid computation wrapper is not yet implemented.")


def compute_inertia_tensor(
    mesh: trimesh.Trimesh,
    density: float,
    reference_point: NDArray[np.float64] | None = None,
) -> NDArray[np.float64]:
    """Compute the 3×3 inertia tensor of a homogeneous mesh segment.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Watertight mesh.
    density : float
        Volumetric density in kg/m³.  Use values from
        :data:`SEGMENT_DENSITY_KG_M3` or a calibrated value.
    reference_point : NDArray[np.float64] or None, optional
        Point ``(3,)`` about which to express the tensor.  If ``None``, uses
        the mesh centroid.

    Returns
    -------
    NDArray[np.float64]
        Symmetric inertia tensor of shape ``(3, 3)`` in kg·m².

    Raises
    ------
    NotImplementedError
        Always.
    ValueError
        If ``density`` is not positive.

    Notes
    -----
    To apply the parallel-axis theorem, pass the desired reference point
    explicitly.  The inertia tensor is expressed in the ``bodyloop_global``
    frame; further rotation may be needed for body-fixed frames.

    # TODO_SCIENTIFIC: density source must be documented per segment —
    # see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] trimesh.Trimesh.moment_inertia property.
    .. [2] de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
           inertia parameters. J Biomech 29(9):1223-1230.
    """
    # TODO: scale mesh.moment_inertia by density, then apply parallel-axis theorem
    raise NotImplementedError("Inertia tensor computation is not yet implemented.")


def compute_bsp_for_segment(
    mesh: trimesh.Trimesh,
    segment_name: str,
) -> dict[str, object]:
    """Return a full body-segment parameter (BSP) dictionary for one segment.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Watertight segment mesh in ``bodyloop_global`` coordinates.
    segment_name : str
        Name key matching :data:`SEGMENT_DENSITY_KG_M3`,
        e.g. ``"thigh"``, ``"upper_arm"``.

    Returns
    -------
    dict[str, object]
        Dictionary with keys:
        ``"segment"``, ``"mass_kg"``, ``"volume_m3"``,
        ``"centroid_m"``, ``"inertia_tensor_kgm2"``.

    Raises
    ------
    NotImplementedError
        Always.
    KeyError
        If ``segment_name`` is not in :data:`SEGMENT_DENSITY_KG_M3`.

    Notes
    -----
    This is the primary output used by :mod:`~biomechanics.biorbd_export`
    and :mod:`~biomechanics.opensim_export`.

    References
    ----------
    .. [1] Dempster, W.T. (1955). Space requirements of the seated operator.
           WADC Technical Report.
    """
    # TODO: compose volume, centroid, and inertia calls; look up density
    raise NotImplementedError(
        f"BSP computation for segment '{segment_name}' is not yet implemented."
    )
