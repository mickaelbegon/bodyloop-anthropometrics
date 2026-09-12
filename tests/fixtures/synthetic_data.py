"""Synthetic anthropometric data generator for testing.

All data in this module is entirely fictitious.  Values are chosen to be
anthropometrically plausible for a 70 kg / 1.75 m adult male but do NOT
represent any real subject.  No real patient data is or will ever be
committed to this repository.

Usage
-----
.. code-block:: python

    from tests.fixtures.synthetic_data import make_synthetic_viatar

    data = make_synthetic_viatar()
    assert data["properties"]["height_m"] == pytest.approx(1.75)
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_synthetic_viatar(
    viatar_id: str = "SYNTHETIC_001",
    height_m: float = 1.75,
    mass_kg: float = 70.0,
    sex: str = "male",
) -> dict[str, object]:
    """Generate a complete synthetic BodyLoop normalised data dictionary.

    Parameters
    ----------
    viatar_id : str, optional
        Fictitious viatar identifier.  Default ``"SYNTHETIC_001"``.
    height_m : float, optional
        Subject height in metres.  Default ``1.75``.
    mass_kg : float, optional
        Subject body mass in kg.  Default ``70.0``.
    sex : str, optional
        Biological sex used for proportional scaling.  Default ``"male"``.

    Returns
    -------
    dict[str, object]
        Dictionary mimicking the normalised BodyLoop API output with
        ``"viatar_id"``, ``"properties"``, ``"distances"``, ``"heights"``,
        ``"markers"``, ``"cross_sections"``, and ``"angles"`` keys.

    Notes
    -----
    Proportions are loosely derived from de Leva (1996) for a 70 kg / 1.75 m
    male.  They are NOT validated against real BodyLoop scanner output.

    References
    ----------
    .. [1] de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
           inertia parameters. J Biomech 29(9):1223-1230.
    """
    h = height_m
    m = mass_kg

    # Segment length fractions (de Leva 1996, male, approximate)
    head_h = 0.130 * h
    neck_h = 0.052 * h
    trunk_h = 0.288 * h
    upper_arm_len = 0.186 * h
    forearm_len = 0.146 * h
    hand_len = 0.108 * h
    thigh_len = 0.245 * h
    shank_len = 0.246 * h
    foot_len = 0.152 * h

    # Girth/width approximations (very rough, for plausibility only)
    shoulder_width = 0.259 * h
    hip_width = 0.191 * h
    waist_girth = 0.480  # m (circumference)
    hip_girth = 0.960    # m
    chest_girth = 0.980  # m
    thigh_girth = 0.540  # m
    calf_girth = 0.360   # m
    upper_arm_girth = 0.280  # m

    return {
        "viatar_id": viatar_id,
        "properties": {
            "height_m": h,
            "mass_kg": m,
            "sex": sex,
            "bmi": m / (h ** 2),
            "age_years": None,  # not collected
        },
        "distances": {
            "shoulder_width": shoulder_width,
            "hip_width": hip_width,
            "head_depth": 0.200,
            "head_width": 0.155,
            "foot_length": foot_len,
            "foot_width": 0.093,
            "hand_length": hand_len,
            "hand_width": 0.085,
        },
        "heights": {
            "standing": h,
            "hip": 0.530 * h,
            "knee": 0.285 * h,
            "ankle": 0.042 * h,
            "shoulder": 0.817 * h,
            "elbow": 0.630 * h,
            "wrist": 0.480 * h,
            "navel": 0.600 * h,
            "xiphoid": 0.720 * h,
            "nipple": 0.740 * h,
            "chin": 0.870 * h,
            "top_of_head": h,
        },
        "markers": {
            # 3-D positions in bodyloop_global frame (metres), Y-up
            "vertex": [0.0, h, 0.0],
            "sellion": [0.075, 0.930 * h, 0.085],
            "chin": [0.0, 0.870 * h, 0.065],
            "suprasternale": [0.0, 0.820 * h, 0.050],
            "xiphoid": [0.0, 0.720 * h, 0.060],
            "navel": [0.0, 0.600 * h, 0.045],
            "ASIS_right": [0.095, 0.530 * h, 0.020],
            "ASIS_left": [-0.095, 0.530 * h, 0.020],
            "greater_trochanter_right": [0.100, 0.525 * h, -0.020],
            "greater_trochanter_left": [-0.100, 0.525 * h, -0.020],
            "lateral_knee_right": [0.110, 0.285 * h, 0.0],
            "lateral_knee_left": [-0.110, 0.285 * h, 0.0],
            "lateral_malleolus_right": [0.060, 0.042 * h, 0.0],
            "lateral_malleolus_left": [-0.060, 0.042 * h, 0.0],
            "acromion_right": [0.185, 0.817 * h, -0.010],
            "acromion_left": [-0.185, 0.817 * h, -0.010],
            "lateral_epicondyle_right": [0.210, 0.630 * h, 0.0],
            "lateral_epicondyle_left": [-0.210, 0.630 * h, 0.0],
            "ulnar_styloid_right": [0.200, 0.480 * h, 0.0],
            "ulnar_styloid_left": [-0.200, 0.480 * h, 0.0],
        },
        "cross_sections": {
            # Planar cross-sections at key heights: (perimeter_m, area_m2)
            "head_max": {"height_m": 0.930 * h, "perimeter_m": 0.570, "area_m2": 0.026},
            "neck_mid": {"height_m": 0.845 * h, "perimeter_m": 0.370, "area_m2": 0.011},
            "shoulder": {"height_m": 0.817 * h, "perimeter_m": chest_girth, "area_m2": 0.075},
            "chest_max": {"height_m": 0.750 * h, "perimeter_m": chest_girth, "area_m2": 0.077},
            "waist": {"height_m": 0.620 * h, "perimeter_m": waist_girth, "area_m2": 0.018},
            "hip_max": {"height_m": 0.550 * h, "perimeter_m": hip_girth, "area_m2": 0.073},
            "mid_thigh_right": {"height_m": 0.410 * h, "perimeter_m": thigh_girth, "area_m2": 0.023},
            "knee_right": {"height_m": 0.285 * h, "perimeter_m": 0.360, "area_m2": 0.010},
            "mid_calf_right": {"height_m": 0.165 * h, "perimeter_m": calf_girth, "area_m2": 0.010},
            "ankle_right": {"height_m": 0.060 * h, "perimeter_m": 0.230, "area_m2": 0.004},
            "upper_arm_max_right": {"height_m": 0.720 * h, "perimeter_m": upper_arm_girth, "area_m2": 0.006},
            "forearm_max_right": {"height_m": 0.560 * h, "perimeter_m": 0.250, "area_m2": 0.005},
        },
        "angles": {
            # Segment tilt angles in degrees relative to vertical — synthetic zeros
            "trunk_forward_lean_deg": 0.0,
            "trunk_lateral_lean_deg": 0.0,
        },
        "_synthetic": True,  # sentinel: never present in real data
    }


def make_synthetic_measurement_dict() -> dict[str, object]:
    """Return a small dict of synthetic :class:`~measurement_mapping.Measurement`-compatible
    dictionaries for unit testing.

    Returns
    -------
    dict[str, object]
        Mapping of measurement name to kwargs dict for
        :class:`~bodyloop_anthropometrics.anthropometry.measurement_mapping.Measurement`.

    Notes
    -----
    Uses ``source="calculated"`` and ``confidence=0.9`` as defaults so
    that validation logic can be tested without hitting API stubs.
    """
    return {
        "height": {
            "value": 1.75,
            "unit": "m",
            "frame": "bodyloop_global",
            "source": "direct",
            "confidence": 1.0,
            "bodyloop_path": "heights.standing",
            "notes": "Synthetic test value — not a real subject.",
            "manual_validation_required": False,
        },
        "mass": {
            "value": 70.0,
            "unit": "kg",
            "frame": "bodyloop_global",
            "source": "direct",
            "confidence": 1.0,
            "bodyloop_path": "properties.mass_kg",
            "notes": "Synthetic test value — not a real subject.",
            "manual_validation_required": False,
        },
        "waist_girth": {
            "value": 0.480,
            "unit": "m",
            "frame": "bodyloop_global",
            "source": "calculated",
            "confidence": 0.9,
            "bodyloop_path": "cross_sections.waist.perimeter_m",
            "notes": "Synthetic test value — not a real subject.",
            "manual_validation_required": False,
        },
    }
