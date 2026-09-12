"""Integration tests: GLB rig audit on synthetic inputs.

All tests write synthetic bytes to a tmp_path file; no real GLB assets are
required.  The audit_glb() function is expected to return a valid
RigAuditReport for any file that exists on disk, even if it cannot be parsed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# pygltflib is an optional dependency used only by the rigging sub-package.
# Skip the whole module gracefully when it is not installed so the rest of
# the integration suite can still be collected and run.
pytest.importorskip("pygltflib", reason="pygltflib not installed in this environment")

from bodyloop_anthropometrics.rigging.gltf_audit import RigAuditReport, audit_glb  # noqa: E402


@pytest.mark.integration
class TestRiggingAudit:
    """Integration: GLB audit on synthetic GLB bytes."""

    def test_audit_empty_bytes_returns_not_rigged(self, tmp_path: Path) -> None:
        """audit_glb with invalid bytes returns is_rigged=False, no exception.

        If the file cannot be parsed by pygltflib, audit_glb catches the
        exception internally and returns a minimal RigAuditReport with
        is_rigged=False rather than propagating the parse error to the caller.
        """
        fake_glb = tmp_path / "invalid.glb"
        fake_glb.write_bytes(b"NOT A VALID GLB FILE")

        report = audit_glb(fake_glb)

        assert isinstance(report, RigAuditReport), (
            "audit_glb must always return a RigAuditReport, even for invalid bytes"
        )
        assert report.is_rigged is False, (
            "A file that cannot be parsed must be reported as not rigged"
        )

    def test_audit_report_has_required_fields(self, tmp_path: Path) -> None:
        """RigAuditReport always has all required fields.

        Every field defined in the RigAuditReport model must be present on the
        returned instance, with the correct Python type, even for invalid input.
        """
        fake_glb = tmp_path / "invalid2.glb"
        fake_glb.write_bytes(b"\x00\x01\x02\x03 GARBAGE")

        report = audit_glb(fake_glb)

        # Boolean fields
        for bool_field in (
            "is_rigged",
            "has_skins",
            "has_joint_nodes",
            "has_inverse_bind_matrices",
            "has_joints_0_attribute",
            "has_weights_0_attribute",
            "weights_normalized",
            "skeleton_has_root",
            "skeleton_hierarchy_valid",
            "transforms_consistent",
        ):
            assert hasattr(report, bool_field), (
                f"RigAuditReport is missing field '{bool_field}'"
            )
            assert isinstance(getattr(report, bool_field), bool), (
                f"Field '{bool_field}' must be bool, "
                f"got {type(getattr(report, bool_field))}"
            )

        # Integer fields
        for int_field in (
            "max_influences_per_vertex",
            "animation_count",
            "joint_count",
            "mesh_count",
        ):
            assert hasattr(report, int_field), (
                f"RigAuditReport is missing field '{int_field}'"
            )
            assert isinstance(getattr(report, int_field), int), (
                f"Field '{int_field}' must be int"
            )

        # List fields
        assert isinstance(report.issues, list), "issues must be a list"
        assert isinstance(report.warnings, list), "warnings must be a list"

        # String field
        assert isinstance(report.summary, str), "summary must be a string"

        # Optional fields (may be None)
        assert hasattr(report, "vertical_axis")
        assert hasattr(report, "unit_scale")
        assert hasattr(report, "deformation_test_passed")

    def test_audit_lbs_test_skipped_when_not_rigged(self, tmp_path: Path) -> None:
        """deformation_test_passed is False or None when mesh is not rigged.

        The LBS deformation test is only executed when all structural rig
        prerequisites pass (has_skins, has_joints, etc.).  For an invalid or
        non-rigged file the test is skipped, leaving deformation_test_passed
        as None (or False if it was attempted but failed).
        """
        fake_glb = tmp_path / "invalid3.glb"
        fake_glb.write_bytes(b"INVALID BYTES FOR AUDIT")

        report = audit_glb(fake_glb)

        assert report.is_rigged is False
        # The deformation test must not have passed — it is either skipped
        # (None) or explicitly failed (False), never True.
        assert report.deformation_test_passed is not True, (
            "deformation_test_passed must not be True when is_rigged=False; "
            f"got deformation_test_passed={report.deformation_test_passed}"
        )
