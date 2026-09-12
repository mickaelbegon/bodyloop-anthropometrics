"""Map BodyLoop joint names to standardised anatomical joint identifiers.

Provides the canonical joint-name registry and bidirectional conversion
between BodyLoop's internal naming scheme and external conventions
(biorbd, OpenSim, SMPL/SMPLX).
"""

from __future__ import annotations

# TODO: populate from BodyLoop SDK documentation — joint names are not yet confirmed
BODYLOOP_TO_BIORBD: dict[str, str] = {}

# TODO: populate from BodyLoop SDK documentation
BODYLOOP_TO_OPENSIM: dict[str, str] = {}

# TODO: populate from SMPL joint order (Loper et al. 2015) and BodyLoop SDK
BODYLOOP_TO_SMPL: dict[str, str] = {}


def get_joint_mapping(
    target: str,
) -> dict[str, str]:
    """Return the joint-name mapping from BodyLoop to ``target`` convention.

    Parameters
    ----------
    target : str
        Target naming convention.  Supported values:
        ``"biorbd"``, ``"opensim"``, ``"smpl"``, ``"smplx"``.

    Returns
    -------
    dict[str, str]
        Mapping ``{bodyloop_joint_name: target_joint_name}``.

    Raises
    ------
    NotImplementedError
        Always — registry must be populated after inspecting BodyLoop GLB
        exports and target SDK documentation.
    ValueError
        If ``target`` is not one of the supported conventions.

    Notes
    -----
    This mapping is critical for all downstream rigging and biomechanics
    operations.  Incorrect mappings produce silently wrong kinematics.

    References
    ----------
    .. [1] Loper, M. et al. (2015). SMPL: A skinned multi-person linear model.
           ACM Trans. Graph. 34(6).
    """
    # TODO: implement look-up table with validation
    raise NotImplementedError(
        f"Joint mapping to '{target}' is not yet implemented.  "
        "Populate the BODYLOOP_TO_* dictionaries from SDK documentation."
    )


def validate_joint_coverage(
    gltf_joint_names: list[str],
    target: str,
) -> dict[str, list[str]]:
    """Check which BodyLoop joints have a mapping and which are missing.

    Parameters
    ----------
    gltf_joint_names : list[str]
        Joint names found in the GLB file.
    target : str
        Target naming convention (see :func:`get_joint_mapping`).

    Returns
    -------
    dict[str, list[str]]
        Dictionary with keys ``"mapped"``, ``"unmapped"``, ``"extra"``
        (joints in the mapping not present in the file).

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    Unmapped joints will be silently dropped; this function makes that
    explicit so the user can decide whether to proceed.

    References
    ----------
    .. [1] BodyLoop SDK documentation (internal).
    """
    # TODO: implement coverage check using get_joint_mapping
    raise NotImplementedError("Joint coverage validation is not yet implemented.")
