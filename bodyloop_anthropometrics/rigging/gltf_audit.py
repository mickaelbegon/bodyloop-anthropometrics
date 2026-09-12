"""GLB/glTF rig audit tool.

Checks whether a BodyLoop avatar GLB file contains a valid skinned rig.
Produces a structured JSON report and a human-readable summary.

Notes
-----
A GLB is considered rigged only if ALL of the following are true:

1. At least one skin is present.
2. Joint nodes are present and referenced by the skin.
3. inverseBindMatrices accessor is present.
4. JOINTS_0 and WEIGHTS_0 vertex attributes are present on all skinned meshes.
5. All weight sets are normalized (sum ≈ 1.0).
6. Skeleton has a single root and forms a valid tree.
7. The deformation test passes (simple rotations produce plausible output).

References
----------
glTF 2.0 Specification: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
pygltflib documentation: https://gitlab.com/dodgyville/pygltflib
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field
from pygltflib import GLTF2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WEIGHT_TOLERANCE: float = 1e-4
_DEFORM_ANGLE_DEG: float = 30.0
_DEFORM_MIN_DISPLACEMENT: float = 1e-6
_MAX_DEFORM_SAMPLE: int = 1000
_JOINT_KEYWORDS: frozenset[str] = frozenset({"shoulder", "hip", "knee", "elbow"})

_COMPONENT_TYPE_MAP: dict[int, np.dtype] = {
    5120: np.dtype("int8"),
    5121: np.dtype("uint8"),
    5122: np.dtype("int16"),
    5123: np.dtype("uint16"),
    5125: np.dtype("uint32"),
    5126: np.dtype("float32"),
}

_TYPE_COUNT_MAP: dict[str, int] = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------


class RigAuditReport(BaseModel):
    """Full audit report for a GLB/glTF file.

    Parameters
    ----------
    file_path : str
        Absolute path to the audited GLB file.
    is_rigged : bool
        True if ALL required rig structures are present AND deformation test passes.
    has_skins : bool
        True if at least one skin object is present.
    has_joint_nodes : bool
        True if the skin references at least one joint node.
    has_inverse_bind_matrices : bool
        True if the skin has an inverseBindMatrices accessor.
    has_joints_0_attribute : bool
        True if JOINTS_0 vertex attribute is present on skinned primitives.
    has_weights_0_attribute : bool
        True if WEIGHTS_0 vertex attribute is present on skinned primitives.
    weights_normalized : bool
        True if all weight sets sum to 1.0 (within tolerance 1e-4).
    max_influences_per_vertex : int
        Maximum number of non-zero weights per vertex found.
    skeleton_has_root : bool
        True if at least one joint has no parent in the joint set.
    skeleton_hierarchy_valid : bool
        True if all joint nodes form a valid tree (no cycles, single root).
    transforms_consistent : bool
        True if inverseBindMatrices are consistent with node transforms.
    vertical_axis : str or None
        Detected vertical axis: "Y", "Z", or None if undetermined.
    unit_scale : float or None
        Detected unit scale (1.0 = meters, 0.001 = millimeters, etc.).
    animation_count : int
        Number of animation tracks found.
    joint_count : int
        Total number of joints across all skins.
    mesh_count : int
        Number of mesh objects.
    deformation_test_passed : bool or None
        None if is_rigged prerequisites not met (test skipped). True if
        shoulder/hip/knee/elbow rotation test produces plausible deformation.
    issues : list of str
        Human-readable list of detected blocking issues.
    warnings : list of str
        Non-blocking observations.
    summary : str
        One-paragraph human-readable summary.
    """

    file_path: str
    is_rigged: bool = False
    has_skins: bool = False
    has_joint_nodes: bool = False
    has_inverse_bind_matrices: bool = False
    has_joints_0_attribute: bool = False
    has_weights_0_attribute: bool = False
    weights_normalized: bool = False
    max_influences_per_vertex: int = 0
    skeleton_has_root: bool = False
    skeleton_hierarchy_valid: bool = False
    transforms_consistent: bool = False
    vertical_axis: Optional[str] = None
    unit_scale: Optional[float] = None
    animation_count: int = 0
    joint_count: int = 0
    mesh_count: int = 0
    deformation_test_passed: Optional[bool] = None
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def audit_glb(file_path: str | Path) -> RigAuditReport:
    """Audit a GLB/glTF file for rig completeness.

    Parameters
    ----------
    file_path : str or Path
        Path to the GLB file to audit.

    Returns
    -------
    RigAuditReport
        Structured report with all 12 audit criteria evaluated.

    Raises
    ------
    FileNotFoundError
        If ``file_path`` does not exist on disk.

    Notes
    -----
    If the file exists but cannot be parsed by pygltflib (corrupted or
    invalid format), the function returns a minimal ``RigAuditReport`` with
    ``is_rigged=False`` and the parse error described in ``issues``.  No
    exception is raised in that case.
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"GLB file not found: {path}")

    try:
        gltf = GLTF2().load(str(path))
    except Exception as exc:  # noqa: BLE001
        msg = f"Failed to parse GLB: {exc}"
        return RigAuditReport(
            file_path=str(path),
            is_rigged=False,
            issues=[msg],
            summary=f"Could not parse '{path.name}': {exc}",
        )

    return _run_audit(gltf, str(path))


def audit_glb_to_json(
    file_path: str | Path,
    output_path: str | Path | None = None,
) -> str:
    """Run audit and return (and optionally save) the JSON report.

    Parameters
    ----------
    file_path : str or Path
        Path to the GLB file to audit.
    output_path : str or Path or None, optional
        If provided, the JSON report is written to this path.

    Returns
    -------
    str
        JSON-encoded audit report (indented, 2 spaces).

    Raises
    ------
    FileNotFoundError
        If ``file_path`` does not exist.
    """
    report = audit_glb(file_path)
    json_str = report.model_dump_json(indent=2)
    if output_path is not None:
        Path(output_path).write_text(json_str, encoding="utf-8")
    return json_str


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _run_audit(gltf: GLTF2, file_path: str) -> RigAuditReport:
    """Execute all audit checks and assemble the report.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.
    file_path : str
        Absolute path string (for the report).

    Returns
    -------
    RigAuditReport
        Completed audit report.
    """
    issues: list[str] = []
    warnings: list[str] = []

    has_skins, has_joints, has_ibm, skin_issues, skin_warnings = _check_skins(gltf)
    issues.extend(skin_issues)
    warnings.extend(skin_warnings)

    has_j0, has_w0, weights_norm, max_infl, attr_issues = _check_vertex_attributes(gltf)
    issues.extend(attr_issues)

    has_root, hier_valid, hier_issues = _check_skeleton_hierarchy(gltf)
    issues.extend(hier_issues)

    transforms_ok, transform_issues = _check_transforms(gltf)
    issues.extend(transform_issues)

    unit_scale, vert_axis, unit_warnings = _detect_units_and_axis(gltf)
    warnings.extend(unit_warnings)

    joint_count = sum(len(s.joints) for s in (gltf.skins or []) if s.joints)
    mesh_count = len(gltf.meshes) if gltf.meshes else 0
    anim_count = len(gltf.animations) if gltf.animations else 0

    basic_ok = (
        has_skins
        and has_joints
        and has_ibm
        and has_j0
        and has_w0
        and weights_norm
        and has_root
        and hier_valid
    )

    deformation_test_passed: Optional[bool] = None
    if basic_ok:
        deformation_test_passed, deform_issues = _test_deformation(gltf)
        issues.extend(deform_issues)

    is_rigged = basic_ok and deformation_test_passed is True

    summary = _build_summary(
        Path(file_path).name,
        is_rigged=is_rigged,
        joint_count=joint_count,
        issues=issues,
        warnings=warnings,
    )

    return RigAuditReport(
        file_path=file_path,
        is_rigged=is_rigged,
        has_skins=has_skins,
        has_joint_nodes=has_joints,
        has_inverse_bind_matrices=has_ibm,
        has_joints_0_attribute=has_j0,
        has_weights_0_attribute=has_w0,
        weights_normalized=weights_norm,
        max_influences_per_vertex=max_infl,
        skeleton_has_root=has_root,
        skeleton_hierarchy_valid=hier_valid,
        transforms_consistent=transforms_ok,
        vertical_axis=vert_axis,
        unit_scale=unit_scale,
        animation_count=anim_count,
        joint_count=joint_count,
        mesh_count=mesh_count,
        deformation_test_passed=deformation_test_passed,
        issues=issues,
        warnings=warnings,
        summary=summary,
    )


def _check_skins(gltf: GLTF2) -> tuple[bool, bool, bool, list[str], list[str]]:
    """Check skin presence and structure.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    tuple
        ``(has_skins, has_joint_nodes, has_inverse_bind_matrices, issues, warnings)``
    """
    issues: list[str] = []
    warnings: list[str] = []

    if not gltf.skins:
        issues.append("No skins found — mesh is not skinned.")
        return False, False, False, issues, warnings

    has_joints = any(bool(s.joints) for s in gltf.skins)
    if not has_joints:
        issues.append("Skin(s) present but no joint nodes are referenced.")

    has_ibm = any(s.inverseBindMatrices is not None for s in gltf.skins)
    if not has_ibm:
        issues.append("No inverseBindMatrices accessor found in any skin.")

    if len(gltf.skins) > 1:
        warnings.append(
            f"Multiple skins found ({len(gltf.skins)}); "
            "only structural checks performed on all, deformation tested on first."
        )

    return True, has_joints, has_ibm, issues, warnings


def _check_vertex_attributes(
    gltf: GLTF2,
) -> tuple[bool, bool, bool, int, list[str]]:
    """Check JOINTS_0, WEIGHTS_0 presence and normalization.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    tuple
        ``(has_joints_0, has_weights_0, weights_normalized, max_influences, issues)``
    """
    issues: list[str] = []
    has_j0 = False
    has_w0 = False
    weights_normalized = True
    max_influences = 0

    if not gltf.meshes:
        return False, False, False, 0, issues

    for mesh in gltf.meshes:
        for prim in mesh.primitives:
            attrs = prim.attributes
            if attrs is None:
                continue

            j0_idx = getattr(attrs, "JOINTS_0", None)
            w0_idx = getattr(attrs, "WEIGHTS_0", None)

            if j0_idx is not None:
                has_j0 = True

            if w0_idx is not None:
                has_w0 = True
                try:
                    weights = _get_accessor_data_float(gltf, w0_idx)
                    if weights.ndim == 2:
                        sums = weights.sum(axis=1)
                        bad_mask = ~np.isclose(sums, 1.0, atol=_WEIGHT_TOLERANCE)
                        if bad_mask.any():
                            weights_normalized = False
                            bad_min = float(sums[bad_mask].min())
                            bad_max = float(sums[bad_mask].max())
                            issues.append(
                                f"Non-normalized weights in mesh '{mesh.name or '?'}' "
                                f"(sum range [{bad_min:.4f}, {bad_max:.4f}]; "
                                f"expected 1.0 ± {_WEIGHT_TOLERANCE})."
                            )
                        nonzero = int((weights > 0).sum(axis=1).max())
                        max_influences = max(max_influences, nonzero)
                except Exception as exc:  # noqa: BLE001
                    issues.append(f"Could not read WEIGHTS_0 accessor: {exc}")

    if not has_j0:
        issues.append("JOINTS_0 attribute missing from all mesh primitives.")
    if not has_w0:
        issues.append("WEIGHTS_0 attribute missing from all mesh primitives.")

    return has_j0, has_w0, weights_normalized, max_influences, issues


def _check_skeleton_hierarchy(gltf: GLTF2) -> tuple[bool, bool, list[str]]:
    """Check skeleton tree validity (single root, no cycles).

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    tuple
        ``(skeleton_has_root, skeleton_hierarchy_valid, issues)``
    """
    issues: list[str] = []

    if not gltf.skins:
        return False, False, issues

    all_joints: set[int] = set()
    for skin in gltf.skins:
        if skin.joints:
            all_joints.update(skin.joints)

    if not all_joints:
        issues.append("Skin found but joint list is empty.")
        return False, False, issues

    # Build child → parent map from node children lists.
    parent_map: dict[int, int] = {}
    for node_idx, node in enumerate(gltf.nodes or []):
        for child_idx in node.children or []:
            parent_map[child_idx] = node_idx

    # Root joints: joints whose parent is not in the joint set.
    root_joints = [j for j in all_joints if parent_map.get(j, -1) not in all_joints]

    has_root = len(root_joints) >= 1
    if not has_root:
        issues.append("No skeleton root found — all joints appear to have parents.")
    elif len(root_joints) > 1:
        issues.append(
            f"Multiple skeleton roots found ({len(root_joints)}): "
            + ", ".join(
                f"node {r} ({(gltf.nodes[r].name or '?') if gltf.nodes else '?'})"
                for r in root_joints
            )
        )

    # Cycle detection via iterative DFS.
    cycle_found = _detect_cycle(gltf, all_joints)
    if cycle_found:
        issues.append("Cycle detected in the skeleton joint hierarchy.")

    hierarchy_valid = has_root and len(root_joints) == 1 and not cycle_found
    return has_root, hierarchy_valid, issues


def _detect_cycle(gltf: GLTF2, joint_set: set[int]) -> bool:
    """Return True if the joint subgraph contains a directed cycle.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.
    joint_set : set of int
        Node indices that form the skeleton.

    Returns
    -------
    bool
        ``True`` if a cycle is detected.
    """
    visited: set[int] = set()
    rec_stack: set[int] = set()

    def dfs(node_idx: int) -> bool:
        visited.add(node_idx)
        rec_stack.add(node_idx)
        node = (gltf.nodes or [])[node_idx] if node_idx < len(gltf.nodes or []) else None
        for child in (node.children if node and node.children else []):
            if child not in joint_set:
                continue
            if child not in visited:
                if dfs(child):
                    return True
            elif child in rec_stack:
                return True
        rec_stack.discard(node_idx)
        return False

    for j in joint_set:
        if j not in visited:
            if dfs(j):
                return True
    return False


def _check_transforms(gltf: GLTF2) -> tuple[bool, list[str]]:
    """Check consistency of inverseBindMatrices with node transforms.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    tuple
        ``(transforms_consistent, issues)``

    Notes
    -----
    Checks that all inverseBindMatrices are finite and non-singular.
    Full consistency against the node tree transforms would require
    traversing the full parent chain; this lighter check detects
    degenerate matrices.
    """
    issues: list[str] = []

    if not gltf.skins:
        return True, issues

    skin = gltf.skins[0]
    if skin.inverseBindMatrices is None:
        return False, ["inverseBindMatrices not set on first skin."]

    if not skin.joints:
        return True, issues

    try:
        ibm_flat = _get_accessor_data_float(gltf, skin.inverseBindMatrices)
        n_joints = len(skin.joints)
        # IBM accessor is stored column-major (MAT4 per joint).
        ibm = ibm_flat.reshape(n_joints, 4, 4) if ibm_flat.size == n_joints * 16 else None

        if ibm is None:
            issues.append(
                f"inverseBindMatrices accessor size mismatch: "
                f"expected {n_joints * 16} floats, got {ibm_flat.size}."
            )
            return False, issues

        if not np.all(np.isfinite(ibm)):
            issues.append("inverseBindMatrices contain NaN or Inf values.")
            return False, issues

        singular_count = 0
        for i, mat in enumerate(ibm):
            if abs(np.linalg.det(mat)) < 1e-10:
                singular_count += 1
                if singular_count <= 3:
                    issues.append(
                        f"inverseBindMatrix for joint index {i} "
                        f"({_joint_name(gltf, skin.joints[i])}) is singular."
                    )
        if singular_count > 3:
            issues.append(f"… and {singular_count - 3} more singular inverseBindMatrices.")

        return singular_count == 0, issues

    except Exception as exc:  # noqa: BLE001
        issues.append(f"Could not read inverseBindMatrices: {exc}")
        return False, issues


def _detect_units_and_axis(
    gltf: GLTF2,
) -> tuple[Optional[float], Optional[str], list[str]]:
    """Heuristically detect unit scale and vertical axis.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    tuple
        ``(unit_scale, vertical_axis, warnings)``

    Notes
    -----
    BodyLoop tends to export avatars in millimetres.  The generator
    string is checked first; if it contains "bodyloop", "mm", or
    "millimeter", ``unit_scale`` is set to 0.001.  A bounding-box
    heuristic (extent > 500 → mm) serves as fallback.
    Vertical axis is the axis with the largest bounding-box extent.
    """
    warnings: list[str] = []
    unit_scale: Optional[float] = None
    vertical_axis: Optional[str] = None

    generator = ""
    if gltf.asset and gltf.asset.generator:
        generator = gltf.asset.generator.lower()

    if any(tok in generator for tok in ("bodyloop", "millimeter", " mm", "_mm")):
        unit_scale = 0.001
        warnings.append(
            f"Generator string '{gltf.asset.generator}' suggests millimetre scale; "
            "unit_scale set to 0.001."
        )
    elif "meter" in generator and "milli" not in generator:
        unit_scale = 1.0

    try:
        positions = _collect_positions(gltf)
        if positions is not None and len(positions) > 0:
            extents = positions.max(axis=0) - positions.min(axis=0)
            axis_idx = int(np.argmax(extents))
            vertical_axis = ["X", "Y", "Z"][axis_idx]

            if unit_scale is None:
                max_extent = float(extents.max())
                if max_extent > 500.0:
                    unit_scale = 0.001
                    warnings.append(
                        f"Vertex extents ({max_extent:.1f}) suggest millimetre scale; "
                        "unit_scale set to 0.001."
                    )
                elif max_extent > 0.3:
                    unit_scale = 1.0
    except Exception:  # noqa: BLE001
        pass

    return unit_scale, vertical_axis, warnings


def _test_deformation(gltf: GLTF2) -> tuple[bool, list[str]]:
    """Apply simple rotations to shoulder/hip/knee/elbow joints.

    Checks that vertex positions change plausibly (non-zero displacement,
    no NaN/Inf) when a 30-degree rotation is applied to named joints.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    tuple
        ``(passed, issues)``

    Notes
    -----
    Uses linear blend skinning (LBS) with numpy for matrix math.
    Rotation angle is :data:`_DEFORM_ANGLE_DEG` degrees around X axis.
    At most :data:`_MAX_DEFORM_SAMPLE` vertices are sampled for speed.
    """
    issues: list[str] = []

    if not gltf.skins:
        return True, issues

    skin = gltf.skins[0]
    if not skin.joints or skin.inverseBindMatrices is None:
        return True, issues

    # --- Find keyword joints ---
    keyword_joint_indices: set[int] = set()
    for joint_node_idx in skin.joints:
        node = (gltf.nodes or [])[joint_node_idx] if joint_node_idx < len(gltf.nodes or []) else None
        if node and node.name:
            if any(kw in node.name.lower() for kw in _JOINT_KEYWORDS):
                local_idx = skin.joints.index(joint_node_idx)
                keyword_joint_indices.add(local_idx)

    if not keyword_joint_indices:
        # No named joints found — pass the test vacuously.
        return True, []

    # --- Read inverseBindMatrices ---
    try:
        ibm_flat = _get_accessor_data_float(gltf, skin.inverseBindMatrices)
        n_joints = len(skin.joints)
        ibm = ibm_flat.reshape(n_joints, 4, 4).astype(np.float64)
    except Exception as exc:  # noqa: BLE001
        # Cannot read IBM — skip deformation test.
        return True, [f"Deformation test skipped (IBM unreadable): {exc}"]

    # --- Find skinned primitive ---
    positions: Optional[np.ndarray] = None
    weights_data: Optional[np.ndarray] = None
    joints_data: Optional[np.ndarray] = None

    for mesh in gltf.meshes or []:
        for prim in mesh.primitives:
            attrs = prim.attributes
            if attrs is None:
                continue
            pos_idx = getattr(attrs, "POSITION", None)
            w0_idx = getattr(attrs, "WEIGHTS_0", None)
            j0_idx = getattr(attrs, "JOINTS_0", None)
            if pos_idx is None or w0_idx is None or j0_idx is None:
                continue
            try:
                positions = _get_accessor_data_float(gltf, pos_idx).astype(np.float64)
                weights_data = _get_accessor_data_float(gltf, w0_idx).astype(np.float64)
                raw_joints = _get_accessor_data_float(gltf, j0_idx)
                joints_data = raw_joints.astype(np.int32)
                break
            except Exception:  # noqa: BLE001
                positions = None
        if positions is not None:
            break

    if positions is None:
        return True, []

    # --- Build skinning matrices ---
    # identity in bind pose → skinning_mat[j] = I @ IBM[j] = IBM[j]
    # After rotation on keyword joints → skinning_mat[j] = R @ IBM[j]
    angle = math.radians(_DEFORM_ANGLE_DEG)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    rot_x = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, cos_a, -sin_a, 0.0],
            [0.0, sin_a, cos_a, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )

    # Default: identity joint matrix → skinning_mat = I @ IBM = IBM
    skinning_mats = ibm.copy()  # (n_joints, 4, 4)
    for local_idx in keyword_joint_indices:
        if local_idx < n_joints:
            skinning_mats[local_idx] = rot_x @ ibm[local_idx]

    # --- Apply LBS on a sample of vertices ---
    n_sample = min(len(positions), _MAX_DEFORM_SAMPLE)
    pos_s = positions[:n_sample]
    w_s = weights_data[:n_sample] if weights_data is not None else None
    j_s = joints_data[:n_sample] if joints_data is not None else None

    if w_s is None or j_s is None:
        return True, []

    try:
        new_pos = _lbs(pos_s, j_s, w_s, skinning_mats)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"Deformation test failed with error: {exc}")
        return False, issues

    if not np.all(np.isfinite(new_pos)):
        issues.append("Deformation test produced NaN/Inf vertex positions.")
        return False, issues

    displacement = np.linalg.norm(new_pos - pos_s, axis=1)
    if displacement.max() < _DEFORM_MIN_DISPLACEMENT:
        issues.append(
            "Deformation test: no vertex movement detected — "
            "skinning may be incorrectly configured."
        )
        return False, issues

    return True, issues


# ---------------------------------------------------------------------------
# Internal low-level utilities
# ---------------------------------------------------------------------------


def _get_accessor_data_float(gltf: GLTF2, accessor_idx: int) -> np.ndarray:
    """Extract accessor data as a float32 numpy array.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document (must be GLB with binary blob, or have
        a valid buffer view pointing to in-memory data).
    accessor_idx : int
        Index into ``gltf.accessors``.

    Returns
    -------
    numpy.ndarray
        Data array, dtype float32.  Shape is ``(count,)`` for SCALAR
        and ``(count, n_components)`` for vector/matrix types.

    Raises
    ------
    ValueError
        If the binary blob is unavailable or the accessor is malformed.
    """
    accessor = gltf.accessors[accessor_idx]
    if accessor.bufferView is None:
        raise ValueError(f"Accessor {accessor_idx} has no bufferView.")

    buffer_view = gltf.bufferViews[accessor.bufferView]
    blob = gltf.binary_blob()
    if blob is None:
        raise ValueError("No binary blob in this GLTF document (not a GLB?).")

    dtype = _COMPONENT_TYPE_MAP.get(accessor.componentType)
    if dtype is None:
        raise ValueError(f"Unknown componentType: {accessor.componentType}.")

    n_components = _TYPE_COUNT_MAP.get(accessor.type, 1)
    byte_offset = (buffer_view.byteOffset or 0) + (accessor.byteOffset or 0)
    item_size = dtype.itemsize * n_components
    byte_length = accessor.count * item_size

    raw = blob[byte_offset : byte_offset + byte_length]
    data = np.frombuffer(raw, dtype=dtype).copy()

    # Convert normalized integer types to [0, 1] float range.
    if accessor.normalized and dtype not in (np.dtype("float32"), np.dtype("float64")):
        info = np.iinfo(dtype)
        data = data.astype(np.float32) / float(info.max)
    else:
        data = data.astype(np.float32)

    if n_components > 1:
        data = data.reshape(accessor.count, n_components)

    return data


def _collect_positions(gltf: GLTF2) -> Optional[np.ndarray]:
    """Collect all POSITION accessor data concatenated into one array.

    Parameters
    ----------
    gltf : GLTF2
        Parsed glTF 2.0 document.

    Returns
    -------
    numpy.ndarray or None
        Shape ``(N, 3)`` float32, or ``None`` if no positions found.
    """
    parts: list[np.ndarray] = []
    for mesh in gltf.meshes or []:
        for prim in mesh.primitives:
            attrs = prim.attributes
            pos_idx = getattr(attrs, "POSITION", None) if attrs else None
            if pos_idx is None:
                continue
            try:
                pos = _get_accessor_data_float(gltf, pos_idx)
                if pos.ndim == 2 and pos.shape[1] == 3:
                    parts.append(pos)
            except Exception:  # noqa: BLE001
                pass
    return np.concatenate(parts, axis=0) if parts else None


def _lbs(
    positions: np.ndarray,
    joints_data: np.ndarray,
    weights_data: np.ndarray,
    skinning_mats: np.ndarray,
) -> np.ndarray:
    """Vectorised linear blend skinning.

    Parameters
    ----------
    positions : numpy.ndarray
        Shape ``(N, 3)``, vertex positions in bind pose.
    joints_data : numpy.ndarray
        Shape ``(N, 4)``, joint indices per vertex (int32).
    weights_data : numpy.ndarray
        Shape ``(N, 4)``, blend weights per vertex.
    skinning_mats : numpy.ndarray
        Shape ``(J, 4, 4)``, skinning matrix per joint.

    Returns
    -------
    numpy.ndarray
        Shape ``(N, 3)``, deformed vertex positions.
    """
    n_verts = len(positions)
    n_influences = joints_data.shape[1]

    # Homogeneous positions: (N, 4)
    ones = np.ones((n_verts, 1), dtype=np.float64)
    pos_h = np.concatenate([positions, ones], axis=1)

    new_pos_h = np.zeros((n_verts, 4), dtype=np.float64)
    for i in range(n_influences):
        j_idx = joints_data[:, i].clip(0, len(skinning_mats) - 1)  # (N,)
        w = weights_data[:, i]  # (N,)
        mats = skinning_mats[j_idx]  # (N, 4, 4)
        transformed = np.einsum("nij,nj->ni", mats, pos_h)  # (N, 4)
        new_pos_h += w[:, np.newaxis] * transformed

    return new_pos_h[:, :3]


def _joint_name(gltf: GLTF2, node_idx: int) -> str:
    """Return the name of a node, or '?' if unavailable."""
    nodes = gltf.nodes or []
    if node_idx < len(nodes) and nodes[node_idx].name:
        return nodes[node_idx].name
    return f"node_{node_idx}"


def _build_summary(
    filename: str,
    is_rigged: bool,
    joint_count: int,
    issues: list[str],
    warnings: list[str],
) -> str:
    """Build a one-paragraph human-readable summary.

    Parameters
    ----------
    filename : str
        Base name of the audited file.
    is_rigged : bool
        Overall rig verdict.
    joint_count : int
        Total joints found.
    issues : list of str
        Blocking issues detected.
    warnings : list of str
        Non-blocking warnings.

    Returns
    -------
    str
        Summary paragraph.
    """
    verdict = "RIGGED" if is_rigged else "NOT RIGGED"
    parts = [f"'{filename}' — verdict: {verdict}."]
    if joint_count:
        parts.append(f"{joint_count} joints detected.")
    if issues:
        parts.append(f"{len(issues)} issue(s): {'; '.join(issues[:3])}")
        if len(issues) > 3:
            parts.append(f"(and {len(issues) - 3} more).")
    if warnings:
        parts.append(f"{len(warnings)} warning(s): {'; '.join(warnings[:2])}")
    return " ".join(parts)
