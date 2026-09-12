"""Export a rigged mesh as a conformant glTF 2.0 / GLB file.

Assembles the mesh geometry, skeleton hierarchy, skin accessors, and
morphological metadata into a single GLB binary that can be consumed by
downstream biomechanics tools.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

import pygltflib
import trimesh


def build_gltf_document(
    mesh: trimesh.Trimesh,
    joint_names: list[str],
    joint_transforms: NDArray[np.float64],
    skin_weights: NDArray[np.float64],
    metadata: dict[str, object] | None = None,
) -> pygltflib.GLTF2:
    """Construct a pygltflib GLTF2 document from rigging data.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Rigged mesh geometry.
    joint_names : list[str]
        Ordered joint names matching columns of ``skin_weights``.
    joint_transforms : NDArray[np.float64]
        Array of shape ``(num_joints, 4, 4)`` containing the inverse bind
        matrices in column-major order.
    skin_weights : NDArray[np.float64]
        Array of shape ``(N_vertices, num_joints)`` normalised skin weights.
    metadata : dict[str, object] or None, optional
        Arbitrary metadata stored in ``gltf.extras``.

    Returns
    -------
    pygltflib.GLTF2
        Assembled glTF 2.0 document (not yet written to disk).

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    The ``metadata`` dict should include the SDK version, BodyLoop preset,
    and any scientific assumptions — these feed ``manifest.json``.

    References
    ----------
    .. [1] glTF 2.0 specification: https://registry.khronos.org/glTF/
    .. [2] pygltflib: https://gitlab.com/dodgyville/pygltflib
    """
    # TODO: build accessors, buffer views, skin node, and mesh primitive
    raise NotImplementedError("GLTF document builder is not yet implemented.")


def write_glb(
    gltf: pygltflib.GLTF2,
    output_path: Path,
) -> None:
    """Write a pygltflib GLTF2 document to a binary GLB file.

    Parameters
    ----------
    gltf : pygltflib.GLTF2
        Document to serialise.
    output_path : Path
        Destination file path.  Extension ``.glb`` is appended if absent.

    Returns
    -------
    None

    Raises
    ------
    NotImplementedError
        Always.
    FileNotFoundError
        If the parent directory of ``output_path`` does not exist.

    Notes
    -----
    Always validate the written file with :func:`~rigging.gltf_audit.load_glb`
    after writing.

    References
    ----------
    .. [1] pygltflib GLTF2.save() documentation.
    """
    # TODO: call gltf.save(str(output_path)) with parent-directory check
    raise NotImplementedError("GLB writer is not yet implemented.")
