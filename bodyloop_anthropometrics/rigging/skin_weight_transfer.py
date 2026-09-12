"""Skin-weight transfer from a source (template) topology to a target mesh.

Skin weights encode how much each mesh vertex is influenced by each skeleton
joint.  After registration to a parametric model, weights must be transferred
back to the original BodyLoop scan topology for accurate deformation.

Warning
-------
Do **not** use skin weights to distribute segment mass.  Mass distribution
must use volumetric methods (see :mod:`~geometry.mass_properties`).
This rule is enforced by the AGENTS.md invariants.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

import trimesh


def transfer_weights_nearest_neighbour(
    source_mesh: trimesh.Trimesh,
    source_weights: NDArray[np.float64],
    target_mesh: trimesh.Trimesh,
) -> NDArray[np.float64]:
    """Transfer skin weights via nearest-neighbour vertex lookup.

    Parameters
    ----------
    source_mesh : trimesh.Trimesh
        Template mesh with known skin weights.
    source_weights : NDArray[np.float64]
        Array of shape ``(N_source, num_joints)`` with normalised skin weights.
    target_mesh : trimesh.Trimesh
        Destination mesh whose vertices will receive transferred weights.

    Returns
    -------
    NDArray[np.float64]
        Array of shape ``(N_target, num_joints)`` with transferred weights,
        normalised so each row sums to 1.

    Raises
    ------
    NotImplementedError
        Always.
    ValueError
        If ``source_weights`` rows do not sum to 1 within tolerance.

    Notes
    -----
    Nearest-neighbour transfer is fast but produces block artefacts near joint
    boundaries.  Use :func:`transfer_weights_barycentric` for smoother results.

    References
    ----------
    .. [1] Baran, I. & Popovic, J. (2007). Automatic rigging and animation.
           ACM Trans. Graph. 26(3).
    """
    # TODO: implement using scipy.spatial.cKDTree or trimesh ProximityQuery
    raise NotImplementedError(
        "Nearest-neighbour weight transfer is not yet implemented."
    )


def transfer_weights_barycentric(
    source_mesh: trimesh.Trimesh,
    source_weights: NDArray[np.float64],
    target_mesh: trimesh.Trimesh,
) -> NDArray[np.float64]:
    """Transfer skin weights via barycentric interpolation on the source surface.

    Parameters
    ----------
    source_mesh : trimesh.Trimesh
        Template mesh with known skin weights.
    source_weights : NDArray[np.float64]
        Array of shape ``(N_source, num_joints)`` with normalised skin weights.
    target_mesh : trimesh.Trimesh
        Destination mesh.

    Returns
    -------
    NDArray[np.float64]
        Array of shape ``(N_target, num_joints)`` with smoothly interpolated
        weights, normalised so each row sums to 1.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    Preferred over :func:`transfer_weights_nearest_neighbour` when the
    topologies differ significantly.

    References
    ----------
    .. [1] Baran, I. & Popovic, J. (2007). ACM Trans. Graph. 26(3).
    """
    # TODO: project target vertices onto source surface, interpolate barycentrically
    raise NotImplementedError(
        "Barycentric weight transfer is not yet implemented."
    )


def validate_weights(
    weights: NDArray[np.float64],
    tolerance: float = 1e-5,
) -> None:
    """Assert that all rows of a weight matrix sum to 1 and are non-negative.

    Parameters
    ----------
    weights : NDArray[np.float64]
        Weight matrix of shape ``(N_vertices, num_joints)``.
    tolerance : float, optional
        Absolute tolerance for row-sum check.  Default ``1e-5``.

    Returns
    -------
    None

    Raises
    ------
    NotImplementedError
        Always.
    ValueError
        If any row sum deviates from 1 by more than ``tolerance`` or if any
        weight is negative.

    Notes
    -----
    Always call this after any weight transfer before writing to a GLB file.

    References
    ----------
    .. [1] glTF 2.0 specification — WEIGHTS_0 accessor.
    """
    # TODO: implement assertions using numpy
    raise NotImplementedError("Weight validation is not yet implemented.")
