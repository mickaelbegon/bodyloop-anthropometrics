"""Export body-segment parameters to biorbd-compatible model files.

biorbd (Bioaero Rigid-Body Dynamics) uses ``.bioMod`` text files to describe
a musculoskeletal model.  This module generates the inertial parameter blocks
for each segment from BSP data computed by this pipeline.

References
----------
.. [1] biorbd: https://github.com/pyomeca/biorbd
.. [2] Michaud, B. & Begon, M. (2021). biorbd: A C++ framework with Python
       and MATLAB bindings for versatile musculoskeletal analyses.
       J Open Source Softw 6(57):2562.
"""

from __future__ import annotations

from pathlib import Path

from bodyloop_anthropometrics.anthropometry.measurement_mapping import Measurement


def generate_segment_block(
    segment_name: str,
    bsp: dict[str, Measurement],
    parent: str = "ROOT",
    rt_from_global: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
) -> str:
    """Generate a biorbd ``segment`` block string for one body segment.

    Parameters
    ----------
    segment_name : str
        Biomechanical segment name as used in the ``.bioMod`` file.
    bsp : dict[str, Measurement]
        BSP measurements for this segment; expected keys: ``"mass"``,
        ``"com_x"``, ``"com_y"``, ``"com_z"``, ``"ixx"``, ``"iyy"``,
        ``"izz"``, ``"ixy"``, ``"ixz"``, ``"iyz"``.
    parent : str, optional
        Parent segment name in the kinematic chain.  Default ``"ROOT"``.
    rt_from_global : tuple[float, ...], optional
        6-element Euler sequence ``(rx, ry, rz, tx, ty, tz)`` defining the
        segment's local frame relative to the parent.  Default is identity.

    Returns
    -------
    str
        Text block ready to be inserted into a ``.bioMod`` file.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    All values must be in SI units (kg, m, kg·m²) before calling this
    function.  biorbd does not perform unit conversion.

    References
    ----------
    .. [1] biorbd .bioMod format documentation.
    """
    # TODO: template the segment block using f-strings and Measurement.value
    raise NotImplementedError(
        f"biorbd segment block generation for '{segment_name}' is not yet implemented."
    )


def write_biomod(
    all_bsp: dict[str, dict[str, Measurement]],
    output_path: Path,
    model_name: str = "BodyLoop_subject",
) -> None:
    """Write a complete biorbd ``.bioMod`` file from a full-body BSP set.

    Parameters
    ----------
    all_bsp : dict[str, dict[str, Measurement]]
        BSP data for all segments (output of
        :func:`~anthropometry.direct_mesh_bsp.bsp_to_measurements`).
    output_path : Path
        Destination ``.bioMod`` file path.
    model_name : str, optional
        Model identifier string written as a header comment.

    Returns
    -------
    None

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    The joint degrees-of-freedom and constraint definitions are not generated
    here; only the inertial parameter blocks are written.  A human must
    add kinematic constraints before the model can be used for simulation.

    References
    ----------
    .. [1] biorbd: https://github.com/pyomeca/biorbd
    """
    # TODO: build header, call generate_segment_block per segment, write file
    raise NotImplementedError("biorbd .bioMod writer is not yet implemented.")
