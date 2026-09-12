"""Shared fixtures for integration tests.

All fixtures are designed to avoid real network calls and use only local data.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import yaml

from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import BodyBSP, SegmentBSP

# ---------------------------------------------------------------------------
# Project-root-relative paths to configuration files
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent.parent
YEADON_CONFIG_PATH = _PROJECT_ROOT / "configs" / "bodyloop_to_yeadon.yaml"
HATZE_CONFIG_PATH = _PROJECT_ROOT / "configs" / "bodyloop_to_hatze.yaml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_viatar_data() -> Callable[[Path | str], dict]:
    """Return a factory that builds a normalised BodyLoop data dict from a config YAML.

    Populates every non-null ``bodyloop_path`` in the mapping with a
    placeholder float value (0.5 m), building the nested dict structure that
    the Yeadon and Hatze adapters traverse via dot notation.

    The factory depends only on the YAML file, not on a live API call, so
    it will immediately expose any drift between the config and the actual
    adapter code.

    Parameters
    ----------
    yaml_path : str or Path
        Path to a mapping YAML file (``bodyloop_to_yeadon.yaml`` or
        ``bodyloop_to_hatze.yaml``).

    Returns
    -------
    dict[str, Any]
        Nested dict mimicking the normalised BodyLoop data structure.
    """

    def _factory(yaml_path: Path | str) -> dict:
        with Path(yaml_path).open(encoding="utf-8") as fh:
            mapping: dict = yaml.safe_load(fh)

        # Pre-build all sections that either adapter may request.
        data: dict = {
            "markers": {},
            "axes": {},
            "distances": {},
            "heights": {},
            "crosssections": {},
            "crosssection_series": {},
            "properties": {},
            "angles": {},
        }

        for _key, entry in mapping.items():
            if not isinstance(entry, dict):
                continue
            path = entry.get("bodyloop_path")
            if not path:
                continue

            parts = path.split(".")
            if len(parts) < 2:  # noqa: PLR2004 — need at least section + leaf
                continue

            section = parts[0]
            if section not in data:
                data[section] = {}

            # Walk down the nested dict, creating sub-dicts as needed.
            current = data[section]
            for part in parts[1:-1]:
                if not isinstance(current, dict):
                    break
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set the leaf to a valid float value (0.5 m is anatomically
            # plausible for most length measurements).
            if isinstance(current, dict) and parts[-1]:
                current[parts[-1]] = 0.5

        return data

    return _factory


@pytest.fixture
def minimal_body_bsp() -> BodyBSP:
    """BodyBSP with 2 stub segments (head + trunk).

    Both segments use diagonal inertia tensors in principal axes so that
    off-diagonal elements are exactly zero.  Masses and volumes are
    anatomically plausible for a 70 kg adult.
    """
    # Principal-axis inertia tensors (diagonal → off-diagonal = 0).
    inertia_head = np.diag([0.010, 0.012, 0.008])  # kg·m²
    inertia_trunk = np.diag([0.800, 0.700, 0.300])  # kg·m²

    head_mass = 4.5
    trunk_mass = 35.0
    head_volume = head_mass / 1100.0
    trunk_volume = trunk_mass / 1000.0

    validation_ok: dict = {"is_valid": True, "positive_definite": True, "issues": []}

    head_seg = SegmentBSP(
        name="head",
        mass_kg=head_mass,
        com_m=np.array([0.0, 0.0, 1.72], dtype=np.float64),
        inertia_about_com_kgm2=inertia_head,
        volume_m3=head_volume,
        density_kg_m3=1100.0,
        density_source="de_Leva_1996+mass_calibrated",
        validation=validation_ok,
        warnings=[],
    )
    trunk_seg = SegmentBSP(
        name="trunk",
        mass_kg=trunk_mass,
        com_m=np.array([0.0, 0.0, 1.20], dtype=np.float64),
        inertia_about_com_kgm2=inertia_trunk,
        volume_m3=trunk_volume,
        density_kg_m3=1000.0,
        density_source="de_Leva_1996+mass_calibrated",
        validation=validation_ok,
        warnings=[],
    )

    total_mass = head_mass + trunk_mass
    return BodyBSP(
        segments={"head": head_seg, "trunk": trunk_seg},
        total_mass_kg=total_mass,
        total_volume_m3=head_volume + trunk_volume,
        mass_conservation_error=0.005,
        subject_id="integration-test-stub",
        notes=["integration test: manually constructed stub BodyBSP"],
        density_scale_factor=1.0,
        uncalibrated_mass_kg=total_mass,
        failed_segments={},
    )
