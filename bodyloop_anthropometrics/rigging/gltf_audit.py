"""GLB/glTF structure validation and joint-hierarchy audit.

Checks that a BodyLoop GLB export contains the expected node hierarchy,
skin, and mesh accessors before downstream processing.
"""

from __future__ import annotations

from pathlib import Path

import pygltflib


def load_glb(path: Path) -> pygltflib.GLTF2:
    """Load a GLB file from disk and perform basic sanity checks.

    Parameters
    ----------
    path : Path
        Filesystem path to the ``.glb`` file.

    Returns
    -------
    pygltflib.GLTF2
        Parsed glTF 2.0 document.

    Raises
    ------
    NotImplementedError
        Always.
    FileNotFoundError
        If ``path`` does not exist.

    Notes
    -----
    Does not validate semantic content — call :func:`audit_joint_hierarchy`
    for that.

    References
    ----------
    .. [1] pygltflib documentation: https://gitlab.com/dodgyville/pygltflib
    """
    # TODO: call pygltflib.GLTF2().load(path) with error handling
    raise NotImplementedError("GLB loading wrapper is not yet implemented.")


def audit_joint_hierarchy(
    gltf: pygltflib.GLTF2,
    expected_joints: list[str] | None = None,
) -> dict[str, object]:
    """Verify that a glTF document contains the expected skeleton hierarchy.

    Parameters
    ----------
    gltf : pygltflib.GLTF2
        Parsed glTF 2.0 document.
    expected_joints : list[str] or None, optional
        List of joint names that must be present.  If ``None``, uses the
        BodyLoop standard joint set.

    Returns
    -------
    dict[str, object]
        Audit report with keys:
        ``"missing_joints"``, ``"extra_joints"``, ``"depth"``,
        ``"skin_count"``, ``"pass"`` (bool).

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    A failed audit (``"pass": False``) should be treated as a hard error
    before any skeleton mapping or skin-weight operation.

    References
    ----------
    .. [1] glTF 2.0 specification — Skins: https://registry.khronos.org/glTF/
    """
    # TODO: walk gltf.nodes, compare with expected_joints list
    raise NotImplementedError("Joint hierarchy audit is not yet implemented.")


def list_mesh_primitives(
    gltf: pygltflib.GLTF2,
) -> list[dict[str, object]]:
    """Return a summary of all mesh primitives in the glTF document.

    Parameters
    ----------
    gltf : pygltflib.GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    list[dict[str, object]]
        One entry per primitive with keys:
        ``"mesh_index"``, ``"primitive_index"``, ``"vertex_count"``,
        ``"has_joints"``, ``"has_weights"``, ``"material"``.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    Used to confirm that joint/weight accessors are present before
    skin-weight transfer.

    References
    ----------
    .. [1] glTF 2.0 specification — Meshes.
    """
    # TODO: iterate gltf.meshes → primitives, read accessor metadata
    raise NotImplementedError("Mesh primitive listing is not yet implemented.")
