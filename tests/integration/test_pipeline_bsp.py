"""Integration tests: mesh → BodyBSP → BiorbdExporter / OpenSimExporter.

Uses real trimesh geometry (icosphere) for mass property verification and
manually constructed BodyBSP stubs for export tests.  No network calls.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
import trimesh

from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import BodyBSP, compute_all_bsp
from bodyloop_anthropometrics.export.biorbd_exporter import BiorbdExporter, BiorbdSegment
from bodyloop_anthropometrics.export.opensim_exporter import OpenSimExporter


@pytest.mark.integration
class TestDirectBSPPipeline:
    """Integration: real mesh → BodyBSP → BiorbdExporter → .bioMod file."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_test_segments(body_bsp: BodyBSP | None = None) -> list[BiorbdSegment]:
        """Create two minimal BiorbdSegment objects for export tests.

        Using BiorbdSegment directly (rather than BiorbdExporter.from_body_bsp)
        avoids the need to supply joint_centre_bodyloop positions, which the
        real YAML requires for the Thorax and Head segments.  The export
        format is tested independently of the joint-hierarchy pipeline.
        """
        head_mass = 4.5
        trunk_mass = 35.0

        if body_bsp is not None:
            head_mass = body_bsp.segments["head"].mass_kg
            trunk_mass = body_bsp.segments["trunk"].mass_kg

        inertia_diag = np.diag([0.010, 0.012, 0.008])
        trunk_inertia_diag = np.diag([0.800, 0.700, 0.300])

        return [
            BiorbdSegment(
                name="Pelvis",  # root segment, parent=root, no joint_centre needed
                mass=trunk_mass,
                com=np.array([0.0, 0.0, 0.0], dtype=np.float64),
                inertia=trunk_inertia_diag,
                rt_from_parent=np.eye(4, dtype=np.float64),
            ),
            BiorbdSegment(
                name="Head",
                mass=head_mass,
                com=np.array([0.0, 0.0, 0.25], dtype=np.float64),
                inertia=inertia_diag,
                rt_from_parent=np.eye(4, dtype=np.float64),
            ),
        ]

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_body_bsp_from_sphere_mesh(self) -> None:
        """compute_all_bsp on a sphere gives total mass = density * 4/3 pi r^3.

        An icosphere is watertight and its volume is known analytically.  The
        Mirtich polyhedral integration must recover the sphere volume to within
        2% (numerical tolerance from tessellation).
        """
        radius = 0.10  # metres
        density = 1100.0  # kg/m^3 (head density)

        sphere = trimesh.creation.icosphere(subdivisions=4, radius=radius)
        result = compute_all_bsp({"head": sphere}, density_map={"head": density})

        expected_mass = density * (4.0 / 3.0) * math.pi * radius**3
        assert result["head"]["mass_kg"] == pytest.approx(expected_mass, rel=0.02), (
            f"Sphere mass={result['head']['mass_kg']:.6f} kg deviates more than 2% "
            f"from analytic value {expected_mass:.6f} kg"
        )

    def test_biorbd_export_from_body_bsp(self, minimal_body_bsp: BodyBSP, tmp_path: Path) -> None:
        """BiorbdExporter.write_biomod → parse output for required keywords.

        The .bioMod file must contain biorbd v4 header tokens and one segment
        block per exported segment, with mass values matching the input.
        """
        exporter = BiorbdExporter()
        segments = self._make_test_segments(minimal_body_bsp)
        out_path = tmp_path / "test.bioMod"
        exporter.write_biomod(segments, out_path, source="direct_bsp")

        content = out_path.read_text(encoding="utf-8")
        assert "version 4" in content, ".bioMod must declare 'version 4'"
        assert "segment" in content, ".bioMod must contain 'segment' blocks"
        assert "mass" in content, ".bioMod must contain 'mass' lines"
        assert "endsegment" in content, ".bioMod must contain 'endsegment' tokens"

        # Mass values must appear in the file.
        for seg in segments:
            mass_str = f"{seg.mass:.6g}"
            assert mass_str in content, (
                f"Expected mass value '{mass_str}' for segment '{seg.name}' "
                f"not found in .bioMod output"
            )

    def test_opensim_export_from_body_bsp(self, minimal_body_bsp: BodyBSP, tmp_path: Path) -> None:
        """OpenSimExporter.from_body_bsp → write_osim → parse XML.

        The .osim XML must declare OpenSim schema version 40000 and contain
        at least one <Body> element.
        """
        exporter = OpenSimExporter()
        bodies = exporter.from_body_bsp(minimal_body_bsp)
        assert len(bodies) >= 1, (
            "from_body_bsp returned no bodies; "
            "expected at least 'head' and/or 'torso' to match the minimal_body_bsp"
        )

        out_path = tmp_path / "test.osim"
        exporter.write_osim(bodies, out_path, source="direct_bsp")

        tree = ET.parse(str(out_path))
        root = tree.getroot()
        assert root.get("Version") == "40000", (
            f"Expected <OpenSimDocument Version='40000'>, "
            f"got Version='{root.get('Version')}'"
        )
        body_elements = root.findall(".//Body")
        assert len(body_elements) >= 1, (
            "No <Body> elements found in the .osim XML"
        )

    def test_biorbd_inertia_symmetry(self, minimal_body_bsp: BodyBSP, tmp_path: Path) -> None:
        """Inertia written to .bioMod is symmetric (Ixy=Ixz=Iyz=0 for principal axes).

        When a segment has a diagonal (principal-axis) inertia tensor, the
        off-diagonal elements written to the .bioMod file must be zero.
        """
        exporter = BiorbdExporter()
        segments = self._make_test_segments(minimal_body_bsp)
        out_path = tmp_path / "symmetry.bioMod"
        exporter.write_biomod(segments, out_path, source="direct_bsp")

        content = out_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "inertia":
                # The three rows immediately following the 'inertia' keyword.
                for row_offset in range(1, 4):
                    if i + row_offset >= len(lines):
                        continue
                    row_line = lines[i + row_offset].strip()
                    values = [float(v) for v in row_line.split()]
                    assert len(values) == 3, (  # noqa: PLR2004
                        f"Inertia row should have 3 values, got: {row_line}"
                    )
                    row_idx = row_offset - 1  # 0-based row index
                    for col_idx, val in enumerate(values):
                        if row_idx != col_idx:  # off-diagonal element
                            assert abs(val) < 1e-9, (
                                f"Off-diagonal inertia element [{row_idx},{col_idx}]={val} "
                                f"is non-zero; expected 0 for a principal-axis tensor"
                            )

    def test_mass_conservation_across_export(  # noqa: PLR0913
        self, minimal_body_bsp: BodyBSP, tmp_path: Path
    ) -> None:
        """Total mass in exported .bioMod equals sum of input segment masses.

        Mass must be conserved through the serialisation round-trip to within
        the 6-significant-figure formatting tolerance.
        """
        exporter = BiorbdExporter()
        segments = self._make_test_segments(minimal_body_bsp)
        expected_total = sum(s.mass for s in segments)

        out_path = tmp_path / "conservation.bioMod"
        exporter.write_biomod(segments, out_path, source="direct_bsp")

        # Parse 'mass <value>' lines from the .bioMod file.
        content = out_path.read_text(encoding="utf-8")
        parsed_total = 0.0
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("mass ") and not stripped.startswith("mass_"):
                parts = stripped.split()
                if len(parts) == 2:  # noqa: PLR2004
                    parsed_total += float(parts[1])

        assert parsed_total == pytest.approx(expected_total, rel=0.02), (
            f"Mass conservation failed: file total={parsed_total:.6f} kg, "
            f"expected={expected_total:.6f} kg"
        )
