"""Adapter from BodyLoop data to Hatze (1979) segment parameters.

Hatze's biomechanical model describes each body segment as a geometric solid
with a density function that varies with anatomical position.  The model
requires specific linear measurements for each of 17 segments.

Warning
-------
The hatze-biomech reference implementation (MATLAB) contains equations that
its README explicitly flags as incomplete or incorrect.  **Every equation
used here must be validated against the original CSIR Technical Report.**

# TODO_SCIENTIFIC: systematic audit of all Hatze equations against
# Hatze (1979) and (1980) — see SCIENCE_DECISIONS.md
"""

from __future__ import annotations

from pathlib import Path

from bodyloop_anthropometrics.anthropometry.measurement_mapping import Measurement


# TODO_SCIENTIFIC: 17-segment list and measurement requirements from Hatze (1980)
# must be confirmed against the original publication — see SCIENCE_DECISIONS.md
HATZE_SEGMENTS: list[str] = []  # TODO: populate


def load_mapping_config(config_path: Path | None = None) -> dict[str, object]:
    """Load the Hatze measurement-mapping YAML configuration.

    Parameters
    ----------
    config_path : Path or None, optional
        Path to the mapping YAML file.  If ``None``, uses
        ``configs/bodyloop_to_hatze.yaml`` relative to the project root.

    Returns
    -------
    dict[str, object]
        Parsed YAML mapping configuration.

    Raises
    ------
    NotImplementedError
        Always.
    FileNotFoundError
        If the config file does not exist.

    References
    ----------
    .. [1] Hatze, H. (1979). CSIR Technical Report TWISK 79.
    .. [2] Hatze, H. (1980). A mathematical model for the computational
           determination of parameter values of anthropomorphic segments.
           J Biomech 13(10):833-843.
    """
    # TODO: resolve path, load with yaml.safe_load
    raise NotImplementedError("Hatze mapping config loader is not yet implemented.")


def extract_hatze_measurements(
    bodyloop_normalised: dict[str, object],
    config: dict[str, object],
) -> dict[str, dict[str, Measurement]]:
    """Extract Hatze segment measurement sets from BodyLoop normalised data.

    Parameters
    ----------
    bodyloop_normalised : dict[str, object]
        Normalised BodyLoop output for one avatar.
    config : dict[str, object]
        Mapping configuration from :func:`load_mapping_config`.

    Returns
    -------
    dict[str, dict[str, Measurement]]
        Outer key: segment name.  Inner key: Hatze measurement key for that
        segment.  Value: :class:`~measurement_mapping.Measurement`.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    # TODO_SCIENTIFIC: verify that every extracted measurement corresponds
    # to the correct anatomical location as defined in Hatze (1979/1980) —
    # see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] Hatze, H. (1979). CSIR Technical Report TWISK 79.
    """
    # TODO: iterate segments and measurement keys per config
    raise NotImplementedError("Hatze measurement extraction is not yet implemented.")


def compute_hatze_bsp(
    measurements: dict[str, dict[str, Measurement]],
) -> dict[str, dict[str, object]]:
    """Compute Hatze body-segment parameters from extracted measurements.

    Parameters
    ----------
    measurements : dict[str, dict[str, Measurement]]
        Output of :func:`extract_hatze_measurements`.

    Returns
    -------
    dict[str, dict[str, object]]
        Outer key: segment name.  Inner dict contains:
        ``"mass_kg"``, ``"centroid_m"``, ``"inertia_tensor_kgm2"``.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    # TODO_SCIENTIFIC: Hatze's density functions use subject-specific
    # parameters — the defaults here are NOT validated.  Every equation
    # must be audited against the original CSIR Technical Report.
    # See SCIENCE_DECISIONS.md.

    # TODO_VALIDATE: cross-check computed BSPs against hatze-biomech MATLAB
    # output for the same measurement set.

    References
    ----------
    .. [1] Hatze, H. (1979). CSIR Technical Report TWISK 79.
    .. [2] Hatze, H. (1980). J Biomech 13(10):833-843.
    """
    # TODO: implement Hatze geometric/density equations per segment
    raise NotImplementedError(
        "Hatze BSP computation is not yet implemented.  "
        "Requires full equation audit — see SCIENCE_DECISIONS.md."
    )
