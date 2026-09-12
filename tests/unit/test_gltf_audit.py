"""Unit tests for the GLB/glTF rig audit module.

All tests use entirely synthetic data — no real avatar files are required.
Minimal GLB files are constructed in-memory using pygltflib and saved to
pytest's ``tmp_path`` directory.

Notes
-----
A GLB binary blob layout used in helper functions:
  - bufferView 0 : POSITION  (3×float32 → 12 bytes each)
  - bufferView 1 : JOINTS_0  (4×uint16  →  8 bytes each)
  - bufferView 2 : WEIGHTS_0 (4×float32 → 16 bytes each)
  - bufferView 3 : inverseBindMatrices (J × 16×float32)
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import pytest
from pygltflib import (
    GLTF2,
    Accessor,
    Asset,
    Attributes,
    Buffer,
    BufferView,
    Mesh,
    Node,
    Primitive,
    Scene,
    Skin,
)

from bodyloop_anthropometrics.rigging.gltf_audit import (
    RigAuditReport,
    _check_skeleton_hierarchy,
    _check_vertex_attributes,
    _get_accessor_data_float,
    audit_glb,
    audit_glb_to_json,
)

# ---------------------------------------------------------------------------
# Helpers for building synthetic GLB files
# ---------------------------------------------------------------------------

_TRIANGLE_VERTS = np.array(
    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    dtype=np.float32,
)


def _pack_float32(*values: float) -> bytes:
    return struct.pack(f"{len(values)}f", *values)


def _build_unrigged_glb(tmp_path: Path, filename: str = "unrigged.glb") -> Path:
    """Build a minimal GLB with a triangle mesh but NO skin.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory.
    filename : str, optional
        Output file name.

    Returns
    -------
    Path
        Path to the saved GLB file.
    """
    gltf = GLTF2()
    gltf.asset = Asset(version="2.0", generator="test-synthetic")

    verts_bytes = _TRIANGLE_VERTS.tobytes()
    gltf.buffers = [Buffer(byteLength=len(verts_bytes))]
    gltf.bufferViews = [
        BufferView(buffer=0, byteOffset=0, byteLength=len(verts_bytes), target=34962)
    ]
    gltf.accessors = [
        Accessor(
            bufferView=0,
            byteOffset=0,
            componentType=5126,  # FLOAT
            count=3,
            type="VEC3",
            max=[1.0, 1.0, 0.0],
            min=[0.0, 0.0, 0.0],
        )
    ]
    gltf.meshes = [Mesh(primitives=[Primitive(attributes=Attributes(POSITION=0))])]
    gltf.nodes = [Node(mesh=0)]
    gltf.scenes = [Scene(nodes=[0])]
    gltf.scene = 0
    gltf.set_binary_blob(verts_bytes)

    out = tmp_path / filename
    gltf.save_binary(str(out))
    return out


def _build_rigged_glb(
    tmp_path: Path,
    weights: np.ndarray | None = None,
    create_cycle: bool = False,
    filename: str = "rigged.glb",
) -> Path:
    """Build a minimal rigged GLB for testing.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory.
    weights : numpy.ndarray or None, optional
        Custom 3×4 float32 WEIGHTS_0 array (3 vertices, 4 influences).
        If None, uses unit-weight on joint 0 (fully normalized).
    create_cycle : bool, optional
        If True, introduce a cycle: joint 1 becomes child of joint 2,
        and joint 2 becomes child of joint 1 (cycle between them).
    filename : str, optional
        Output file name.

    Returns
    -------
    Path
        Path to the saved GLB file.
    """
    gltf = GLTF2()
    gltf.asset = Asset(version="2.0", generator="test-rigged")

    # Default weights: each vertex is 100% joint 0.
    if weights is None:
        weights = np.array(
            [[1.0, 0.0, 0.0, 0.0]] * 3,
            dtype=np.float32,
        )

    joints_arr = np.array([[0, 0, 0, 0]] * 3, dtype=np.uint16)

    # Build inverseBindMatrices: 2 joints × 16 floats = identity matrices.
    ibm = np.tile(np.eye(4, dtype=np.float32).flatten(), 2)  # 32 floats

    # Binary layout: position | joints | weights | ibm
    pos_bytes = _TRIANGLE_VERTS.tobytes()   # 36 bytes
    joint_bytes = joints_arr.tobytes()       # 24 bytes (3 × 4 × uint16)
    weight_bytes = weights.tobytes()         # 48 bytes (3 × 4 × float32)
    ibm_bytes = ibm.tobytes()               # 128 bytes (32 × float32)
    blob = pos_bytes + joint_bytes + weight_bytes + ibm_bytes

    off_pos = 0
    off_j = len(pos_bytes)
    off_w = off_j + len(joint_bytes)
    off_ibm = off_w + len(weight_bytes)

    gltf.buffers = [Buffer(byteLength=len(blob))]
    gltf.bufferViews = [
        BufferView(buffer=0, byteOffset=off_pos, byteLength=len(pos_bytes), target=34962),
        BufferView(buffer=0, byteOffset=off_j, byteLength=len(joint_bytes), target=34962),
        BufferView(buffer=0, byteOffset=off_w, byteLength=len(weight_bytes), target=34962),
        BufferView(buffer=0, byteOffset=off_ibm, byteLength=len(ibm_bytes)),
    ]
    gltf.accessors = [
        Accessor(bufferView=0, byteOffset=0, componentType=5126, count=3, type="VEC3",
                 max=[1.0, 1.0, 0.0], min=[0.0, 0.0, 0.0]),  # 0: POSITION
        Accessor(bufferView=1, byteOffset=0, componentType=5123, count=3, type="VEC4"),  # 1: JOINTS_0
        Accessor(bufferView=2, byteOffset=0, componentType=5126, count=3, type="VEC4"),  # 2: WEIGHTS_0
        Accessor(bufferView=3, byteOffset=0, componentType=5126, count=2, type="MAT4"),  # 3: IBM
    ]
    gltf.meshes = [
        Mesh(
            primitives=[
                Primitive(
                    attributes=Attributes(POSITION=0, JOINTS_0=1, WEIGHTS_0=2)
                )
            ]
        )
    ]

    # Two joint nodes: "hip_joint" (0) and "shoulder_joint" (1).
    if create_cycle:
        # Node 0: children = [1]; node 1: children = [0] → cycle.
        gltf.nodes = [
            Node(name="hip_joint", children=[1]),
            Node(name="shoulder_joint", children=[0]),
            Node(mesh=0),
        ]
        gltf.skins = [
            Skin(name="Armature", joints=[0, 1], inverseBindMatrices=3, skeleton=0)
        ]
        gltf.scenes = [Scene(nodes=[2])]
    else:
        # Node 0: root; node 1: child of 0; node 2: mesh node.
        gltf.nodes = [
            Node(name="hip_joint", children=[1]),
            Node(name="shoulder_joint"),
            Node(mesh=0),
        ]
        gltf.skins = [
            Skin(name="Armature", joints=[0, 1], inverseBindMatrices=3, skeleton=0)
        ]
        gltf.scenes = [Scene(nodes=[0, 2])]

    gltf.scene = 0
    gltf.set_binary_blob(blob)
    out = tmp_path / filename
    gltf.save_binary(str(out))
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditNonRiggedGlb:
    """Tests for a GLB that contains geometry but no skin."""

    def test_is_rigged_false(self, tmp_path: Path) -> None:
        """audit_glb returns is_rigged=False for a mesh with no skin."""
        path = _build_unrigged_glb(tmp_path)
        report = audit_glb(path)
        assert isinstance(report, RigAuditReport)
        assert report.is_rigged is False

    def test_has_skins_false(self, tmp_path: Path) -> None:
        """has_skins is False and a relevant issue is reported."""
        path = _build_unrigged_glb(tmp_path)
        report = audit_glb(path)
        assert report.has_skins is False
        assert any("skin" in iss.lower() for iss in report.issues)

    def test_mesh_count_is_one(self, tmp_path: Path) -> None:
        """Mesh count reflects the single triangle mesh."""
        path = _build_unrigged_glb(tmp_path)
        report = audit_glb(path)
        assert report.mesh_count == 1

    def test_file_path_is_absolute(self, tmp_path: Path) -> None:
        """The report file_path field is an absolute path string."""
        path = _build_unrigged_glb(tmp_path)
        report = audit_glb(path)
        assert Path(report.file_path).is_absolute()

    def test_deformation_test_skipped(self, tmp_path: Path) -> None:
        """deformation_test_passed is None when basic rig checks fail."""
        path = _build_unrigged_glb(tmp_path)
        report = audit_glb(path)
        assert report.deformation_test_passed is None


class TestAuditReportJsonSerializable:
    """Tests that audit reports are fully JSON-serializable."""

    def test_model_dump_json_round_trips(self, tmp_path: Path) -> None:
        """model_dump_json produces valid JSON that round-trips via json.loads."""
        path = _build_unrigged_glb(tmp_path)
        report = audit_glb(path)
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "is_rigged" in parsed
        assert "issues" in parsed

    def test_audit_glb_to_json_returns_string(self, tmp_path: Path) -> None:
        """audit_glb_to_json returns a non-empty JSON string."""
        path = _build_unrigged_glb(tmp_path)
        result = audit_glb_to_json(path)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["is_rigged"] is False

    def test_audit_glb_to_json_saves_file(self, tmp_path: Path) -> None:
        """audit_glb_to_json writes the report to disk when output_path is given."""
        glb_path = _build_unrigged_glb(tmp_path)
        out_path = tmp_path / "report.json"
        audit_glb_to_json(glb_path, output_path=out_path)
        assert out_path.exists()
        parsed = json.loads(out_path.read_text(encoding="utf-8"))
        assert "is_rigged" in parsed

    def test_optional_fields_are_json_null_or_value(self, tmp_path: Path) -> None:
        """Optional fields (vertical_axis, unit_scale) are null or a valid value."""
        path = _build_unrigged_glb(tmp_path)
        report = audit_glb(path)
        parsed = json.loads(report.model_dump_json())
        assert parsed["vertical_axis"] is None or isinstance(parsed["vertical_axis"], str)
        assert parsed["unit_scale"] is None or isinstance(parsed["unit_scale"], float)


class TestWeightsNormalizedCheck:
    """Tests for the WEIGHTS_0 normalization check."""

    def test_normalized_weights_pass(self, tmp_path: Path) -> None:
        """weights_normalized=True when all weight rows sum to 1.0."""
        weights = np.array(
            [[1.0, 0.0, 0.0, 0.0], [0.5, 0.5, 0.0, 0.0], [0.25, 0.25, 0.25, 0.25]],
            dtype=np.float32,
        )
        path = _build_rigged_glb(tmp_path, weights=weights, filename="norm.glb")
        report = audit_glb(path)
        assert report.weights_normalized is True
        assert not any("non-normalized" in iss.lower() for iss in report.issues)

    def test_non_normalized_weights_flagged(self, tmp_path: Path) -> None:
        """weights_normalized=False and an issue is reported for bad weights."""
        # Rows sum to 0.5, 0.8, 1.0 — first two are wrong.
        weights = np.array(
            [[0.5, 0.0, 0.0, 0.0], [0.8, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]],
            dtype=np.float32,
        )
        path = _build_rigged_glb(tmp_path, weights=weights, filename="nonnorm.glb")
        report = audit_glb(path)
        assert report.weights_normalized is False
        assert any("non-normalized" in iss.lower() for iss in report.issues)

    def test_max_influences_counted(self, tmp_path: Path) -> None:
        """max_influences_per_vertex reflects the number of non-zero weights."""
        weights = np.array(
            [[0.5, 0.5, 0.0, 0.0], [0.25, 0.25, 0.25, 0.25], [1.0, 0.0, 0.0, 0.0]],
            dtype=np.float32,
        )
        path = _build_rigged_glb(tmp_path, weights=weights, filename="influences.glb")
        report = audit_glb(path)
        # Second vertex has 4 non-zero influences.
        assert report.max_influences_per_vertex == 4


class TestSkeletonCycleDetection:
    """Tests for cycle detection in the joint hierarchy."""

    def test_valid_hierarchy_no_cycle(self, tmp_path: Path) -> None:
        """skeleton_hierarchy_valid=True for a proper parent→child tree."""
        path = _build_rigged_glb(tmp_path, create_cycle=False, filename="valid.glb")
        report = audit_glb(path)
        assert report.skeleton_hierarchy_valid is True
        assert not any("cycle" in iss.lower() for iss in report.issues)

    def test_cyclic_hierarchy_detected(self, tmp_path: Path) -> None:
        """skeleton_hierarchy_valid=False and an issue is reported when a cycle exists."""
        path = _build_rigged_glb(tmp_path, create_cycle=True, filename="cycle.glb")
        report = audit_glb(path)
        assert report.skeleton_hierarchy_valid is False
        assert any("cycle" in iss.lower() for iss in report.issues)

    def test_check_skeleton_hierarchy_directly_with_cycle(self) -> None:
        """_check_skeleton_hierarchy detects a cycle in a GLTF2 object built in memory."""
        gltf = GLTF2()
        gltf.asset = Asset(version="2.0")
        # Two nodes that are each other's child (cycle).
        gltf.nodes = [
            Node(name="A", children=[1]),
            Node(name="B", children=[0]),
        ]
        gltf.skins = [Skin(joints=[0, 1])]
        has_root, hier_valid, issues = _check_skeleton_hierarchy(gltf)
        assert hier_valid is False
        assert any("cycle" in iss.lower() for iss in issues)

    def test_check_skeleton_hierarchy_no_cycle(self) -> None:
        """_check_skeleton_hierarchy passes for a clean linear chain."""
        gltf = GLTF2()
        gltf.asset = Asset(version="2.0")
        gltf.nodes = [
            Node(name="root", children=[1]),
            Node(name="child"),
        ]
        gltf.skins = [Skin(joints=[0, 1])]
        has_root, hier_valid, issues = _check_skeleton_hierarchy(gltf)
        assert has_root is True
        assert hier_valid is True
        assert not any("cycle" in iss.lower() for iss in issues)


class TestAuditMissingFile:
    """Tests that a missing file raises FileNotFoundError."""

    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        """audit_glb raises FileNotFoundError for a non-existent path."""
        missing = tmp_path / "does_not_exist.glb"
        with pytest.raises(FileNotFoundError):
            audit_glb(missing)

    def test_raises_for_relative_missing_path(self) -> None:
        """audit_glb raises FileNotFoundError even for a relative path that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            audit_glb("__nonexistent_avatar__.glb")


class TestAuditInvalidGlb:
    """Tests for graceful handling of corrupt or invalid GLB content."""

    def test_garbage_bytes_returns_report_not_rigged(self, tmp_path: Path) -> None:
        """A file with random bytes returns is_rigged=False (no exception raised)."""
        bad_file = tmp_path / "garbage.glb"
        bad_file.write_bytes(b"\x00\x01\x02\x03NOT A VALID GLB\xff\xfe")
        report = audit_glb(bad_file)
        assert isinstance(report, RigAuditReport)
        assert report.is_rigged is False

    def test_invalid_glb_populates_issues(self, tmp_path: Path) -> None:
        """Parsing failure is recorded in issues, not silently swallowed."""
        bad_file = tmp_path / "invalid.glb"
        bad_file.write_bytes(b"glTF" + b"\x00" * 20)  # truncated magic header
        report = audit_glb(bad_file)
        assert len(report.issues) > 0

    def test_empty_file_returns_report(self, tmp_path: Path) -> None:
        """An empty file returns a report with is_rigged=False, no crash."""
        empty = tmp_path / "empty.glb"
        empty.write_bytes(b"")
        report = audit_glb(empty)
        assert isinstance(report, RigAuditReport)
        assert report.is_rigged is False

    def test_json_file_renamed_as_glb(self, tmp_path: Path) -> None:
        """A JSON file given a .glb extension is handled gracefully."""
        fake_glb = tmp_path / "not_a_glb.glb"
        fake_glb.write_text('{"not": "glb"}', encoding="utf-8")
        report = audit_glb(fake_glb)
        assert isinstance(report, RigAuditReport)
        assert report.is_rigged is False
