"""Direct body-segment parameter (BSP) computation from the 3-D mesh.

This module computes segment inertial properties directly from the BodyLoop
mesh without any parametric model intermediary, using volumetric integration
(divergence theorem) as implemented in trimesh.

This is the most geometrically accurate method but requires a clean,
watertight, properly segmented mesh.
"""

from __future__ import annotations

import trimesh

from bodyloop_anthropometrics.anthropometry.measurement_mapping import Measurement


def compute_all_bsp(
    segmented_meshes: dict[str, trimesh.Trimesh],
    density_map: dict[str, float] | None = None,
) -> dict[str, dict[str, object]]:
    """Compute BSPs for all body segments from their meshes.

    Parameters
    ----------
    segmented_meshes : dict[str, trimesh.Trimesh]
        Mapping of segment name to watertight mesh, as produced by
        :func:`~geometry.mesh_repair.split_body_segments`.
    density_map : dict[str, float] or None, optional
        Mapping of segment name to volumetric density in kg/m³.  If ``None``,
        uses the defaults from :data:`~geometry.mass_properties.SEGMENT_DENSITY_KG_M3`.

    Returns
    -------
    dict[str, dict[str, object]]
        Outer key: segment name.  Inner dict:
        ``"mass_kg"``, ``"volume_m3"``, ``"centroid_m"``,
        ``"inertia_tensor_kgm2"``, ``"density_source"``.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    # TODO_SCIENTIFIC: density values must be justified for the specific
    # population studied — see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] Dempster, W.T. (1955). Space requirements of the seated operator.
           WADC Technical Report.
    .. [2] de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
           inertia parameters. J Biomech 29(9):1223-1230.
    """
    # TODO: call geometry.mass_properties.compute_bsp_for_segment per segment
    raise NotImplementedError(
        "Direct mesh BSP computation is not yet implemented.  "
        "Requires segmented watertight meshes from mesh_repair.split_body_segments."
    )


def bsp_to_measurements(
    bsp: dict[str, dict[str, object]],
) -> dict[str, dict[str, Measurement]]:
    """Convert raw BSP dictionaries into :class:`~measurement_mapping.Measurement` objects.

    Parameters
    ----------
    bsp : dict[str, dict[str, object]]
        Output of :func:`compute_all_bsp`.

    Returns
    -------
    dict[str, dict[str, Measurement]]
        Outer key: segment name.  Inner key: property name
        (``"mass"``, ``"volume"``, etc.).  Value: :class:`~measurement_mapping.Measurement`.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    All :class:`~measurement_mapping.Measurement` objects produced here
    have ``source="calculated"`` and ``frame="bodyloop_global"``.

    References
    ----------
    .. [1] :class:`~bodyloop_anthropometrics.anthropometry.measurement_mapping.Measurement`.
    """
    # TODO: wrap each BSP value in a Measurement with correct unit and provenance
    raise NotImplementedError("BSP-to-Measurement conversion is not yet implemented.")


def export_bsp_json(
    measurements: dict[str, dict[str, Measurement]],
    output_path: object,  # pathlib.Path
) -> None:
    """Serialise BSP measurements to a JSON file.

    Parameters
    ----------
    measurements : dict[str, dict[str, Measurement]]
        Output of :func:`bsp_to_measurements`.
    output_path : Path
        Destination ``.json`` file path.

    Returns
    -------
    None

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    The JSON format must be compatible with the biorbd and OpenSim export
    modules so that they can read BSPs without recomputing them.

    References
    ----------
    .. [1] Internal pipeline specification (docs/SCIENCE_DECISIONS.md).
    """
    # TODO: serialise using pydantic model_dump and json.dumps
    raise NotImplementedError("BSP JSON export is not yet implemented.")
