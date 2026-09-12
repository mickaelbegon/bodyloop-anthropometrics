"""Adapter from BodyLoop data to Yeadon (1990) measurement keys.

Yeadon's geometric model requires approximately 95 anthropometric measurements
(lengths, perimeters, and widths) that define the solid of revolution for
each body segment.  This module maps BodyLoop's normalised data onto those keys.

Warning
-------
All anatomical definitions must be validated against the original publication:
Yeadon, M.R. (1990). The simulation of aerial movement — II. A mathematical
inertia model of the human body. J Biomech 23(1):67-74.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from bodyloop_anthropometrics.anthropometry.measurement_mapping import Measurement


# TODO_SCIENTIFIC: the complete mapping of all 95 Yeadon keys to BodyLoop
# paths must be defined and validated against Yeadon (1990) — see SCIENCE_DECISIONS.md
YEADON_KEYS: list[str] = []  # TODO: populate from yeadon docs


def load_mapping_config(config_path: Path | None = None) -> dict[str, object]:
    """Load the Yeadon measurement-mapping YAML configuration.

    Parameters
    ----------
    config_path : Path or None, optional
        Path to the mapping YAML file.  If ``None``, uses
        ``configs/bodyloop_to_yeadon.yaml`` relative to the project root.

    Returns
    -------
    dict[str, object]
        Parsed YAML mapping configuration.

    Raises
    ------
    NotImplementedError
        Always — path resolution and YAML parsing must be implemented.
    FileNotFoundError
        If the config file does not exist at the resolved path.

    Notes
    -----
    The YAML schema is defined in ``configs/bodyloop_to_yeadon.yaml``.

    References
    ----------
    .. [1] Yeadon, M.R. (1990). J Biomech 23(1):67-74.
    """
    # TODO: resolve config_path, load with yaml.safe_load
    raise NotImplementedError("Yeadon mapping config loader is not yet implemented.")


def extract_yeadon_measurements(
    bodyloop_normalised: dict[str, object],
    config: dict[str, object],
) -> dict[str, Measurement]:
    """Extract all Yeadon measurement keys from BodyLoop normalised data.

    Parameters
    ----------
    bodyloop_normalised : dict[str, object]
        Normalised BodyLoop output for one avatar (from the API client).
    config : dict[str, object]
        Mapping configuration from :func:`load_mapping_config`.

    Returns
    -------
    dict[str, Measurement]
        Mapping of Yeadon key (e.g. ``"Ls"``) to a :class:`~measurement_mapping.Measurement`.
        Missing keys map to a :class:`~measurement_mapping.Measurement` with
        ``source="manual"`` and ``manual_validation_required=True``.

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    Any key with ``confidence < 0.5`` should be flagged for human review.

    # TODO_SCIENTIFIC: define acceptable confidence thresholds for each
    # Yeadon measurement category — see SCIENCE_DECISIONS.md

    References
    ----------
    .. [1] Yeadon, M.R. (1990). J Biomech 23(1):67-74.
    .. [2] https://yeadon.readthedocs.io/en/latest/measurements.html
    """
    # TODO: iterate config keys, resolve bodyloop_path, compute derived values
    raise NotImplementedError("Yeadon measurement extraction is not yet implemented.")


def build_yeadon_input_file(
    measurements: dict[str, Measurement],
    output_path: Path,
) -> None:
    """Write a Yeadon-compatible measurement file from extracted measurements.

    Parameters
    ----------
    measurements : dict[str, Measurement]
        Output of :func:`extract_yeadon_measurements`.
    output_path : Path
        Destination YAML or CSV file path in the format expected by the
        ``yeadon`` Python package.

    Returns
    -------
    None

    Raises
    ------
    NotImplementedError
        Always.

    Notes
    -----
    Raises an error if any measurement has ``manual_validation_required=True``
    and the value has not been confirmed.

    References
    ----------
    .. [1] yeadon Python package: https://yeadon.readthedocs.io/
    """
    # TODO: serialise to YAML matching yeadon's expected input schema
    raise NotImplementedError(
        "Yeadon input-file builder is not yet implemented."
    )
