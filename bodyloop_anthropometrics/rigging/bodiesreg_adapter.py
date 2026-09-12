"""Adapter for the BodiesReg parametric body registration framework.

BodiesReg fits a parametric body model (e.g. SMPL/SMPLX) to a point cloud
or mesh.  This module wraps the BodiesReg interface so that BodyLoop scans
can be registered to a consistent topology for downstream rigging and
anthropometry.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

import trimesh


def register_to_template(
    scan_mesh: trimesh.Trimesh,
    model: str = "smpl",
    *,
    num_iterations: int = 100,
    device: str = "cpu",
) -> dict[str, object]:
    """Fit a parametric body model to a BodyLoop scan mesh.

    Parameters
    ----------
    scan_mesh : trimesh.Trimesh
        Target mesh (BodyLoop scan) in ``bodyloop_global`` coordinates.
    model : str, optional
        Parametric model to use.  One of ``"smpl"``, ``"smplx"``, ``"skel"``.
        Default ``"smpl"``.
    num_iterations : int, optional
        Maximum number of optimisation iterations.  Default ``100``.
    device : str, optional
        Torch device string (``"cpu"`` or ``"cuda:0"``).  Default ``"cpu"``.

    Returns
    -------
    dict[str, object]
        Registration result with keys:
        ``"model"``, ``"betas"``, ``"pose"``, ``"translation"``,
        ``"registered_mesh"``, ``"fit_error_mm"``.

    Raises
    ------
    NotImplementedError
        Always — BodiesReg integration must be implemented.

    Notes
    -----
    The objective function weights (shape vs. pose vs. data terms) are a
    scientific decision.

    # TODO_SCIENTIFIC: define and justify objective function weights for
    # BodiesReg fitting — see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] BodiesReg repository: https://github.com/BodiesReg/BodiesReg
           (verify URL before use).
    """
    # TODO: import BodiesReg, run fitting loop, return result dict
    raise NotImplementedError(
        f"BodiesReg registration to '{model}' is not yet implemented.  "
        "Install BodiesReg and implement the fitting interface."
    )


def extract_shape_parameters(
    registration_result: dict[str, object],
) -> NDArray[np.float64]:
    """Extract the shape (beta) parameters from a BodiesReg result.

    Parameters
    ----------
    registration_result : dict[str, object]
        Output of :func:`register_to_template`.

    Returns
    -------
    NDArray[np.float64]
        Shape-parameter vector of shape ``(num_betas,)``.

    Raises
    ------
    NotImplementedError
        Always.
    KeyError
        If ``"betas"`` is absent from ``registration_result``.

    Notes
    -----
    Beta parameters encode subject-specific body shape deviations from
    the population mean.

    References
    ----------
    .. [1] Loper, M. et al. (2015). SMPL. ACM Trans. Graph. 34(6).
    """
    # TODO: extract and validate betas array
    raise NotImplementedError("Shape parameter extraction is not yet implemented.")


def save_registration(
    result: dict[str, object],
    output_path: Path,
) -> None:
    """Serialise a BodiesReg result to disk (NumPy .npz format).

    Parameters
    ----------
    result : dict[str, object]
        Output of :func:`register_to_template`.
    output_path : Path
        Destination file path (extension ``.npz`` is appended if absent).

    Returns
    -------
    None

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    The saved file should also record the model name, SDK version, and
    preset used — these go into ``manifest.json``.

    References
    ----------
    .. [1] numpy.savez documentation.
    """
    # TODO: serialise with np.savez; record provenance metadata
    raise NotImplementedError("Registration serialisation is not yet implemented.")
