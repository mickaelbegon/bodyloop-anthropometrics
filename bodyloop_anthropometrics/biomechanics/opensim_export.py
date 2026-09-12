"""Export body-segment parameters to OpenSim 4.x model files.

OpenSim uses ``.osim`` XML files to describe musculoskeletal models.  This
module generates the ``<Body>`` elements with inertial parameters from BSP
data computed by this pipeline.

References
----------
.. [1] OpenSim: https://opensim.stanford.edu/
.. [2] Seth, A. et al. (2018). OpenSim: Simulating musculoskeletal dynamics
       and neuromuscular control to study human and animal movement.
       PLoS Comput. Biol. 14(7):e1006223.
"""

from __future__ import annotations

from pathlib import Path

from bodyloop_anthropometrics.anthropometry.measurement_mapping import Measurement


def generate_body_element(
    body_name: str,
    bsp: dict[str, Measurement],
) -> str:
    """Generate an OpenSim ``<Body>`` XML element string for one segment.

    Parameters
    ----------
    body_name : str
        Body name as it will appear in the ``.osim`` file.
    bsp : dict[str, Measurement]
        BSP measurements for this segment; expected keys: ``"mass"``,
        ``"com_x"``, ``"com_y"``, ``"com_z"``, ``"ixx"``, ``"iyy"``,
        ``"izz"``, ``"ixy"``, ``"ixz"``, ``"iyz"``.

    Returns
    -------
    str
        XML string for the ``<Body>`` element.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    OpenSim uses kg, m, and kg·m² — same as the internal SI convention.
    No unit conversion is required if BSP data is already in SI.

    References
    ----------
    .. [1] OpenSim 4.x .osim XML schema.
    """
    # TODO: template XML using f-strings and Measurement.value
    raise NotImplementedError(
        f"OpenSim Body element generation for '{body_name}' is not yet implemented."
    )


def write_osim(
    all_bsp: dict[str, dict[str, Measurement]],
    output_path: Path,
    model_name: str = "BodyLoop_subject",
    opensim_version: str = "40000",
) -> None:
    """Write a complete OpenSim ``.osim`` file from a full-body BSP set.

    Parameters
    ----------
    all_bsp : dict[str, dict[str, Measurement]]
        BSP data for all segments.
    output_path : Path
        Destination ``.osim`` file path.
    model_name : str, optional
        Model name string in the XML header.
    opensim_version : str, optional
        OpenSim version string for the XML header.  Default ``"40000"``.

    Returns
    -------
    None

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    As with biorbd export, joint constraints and muscle definitions are NOT
    generated here.  A human must add kinematic and actuator specifications
    before the model can be used for simulation.

    References
    ----------
    .. [1] OpenSim: https://opensim.stanford.edu/
    """
    # TODO: build XML document using xml.etree.ElementTree or lxml
    raise NotImplementedError("OpenSim .osim writer is not yet implemented.")
