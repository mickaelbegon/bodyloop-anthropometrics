"""Yeadon (1990) anthropometric model adapter.

Extracts the 95 Yeadon measurements from BodyLoop normalised data, builds a
:class:`yeadon.Human` model, and exports segment inertial parameters.

The mapping itself lives in ``configs/bodyloop_to_yeadon.yaml`` so that the
anatomical definitions can be reviewed by a scientist without reading Python.
This module only resolves paths, enforces provenance, and reports gaps: a
measurement that cannot be obtained is listed in
:attr:`~measurement_mapping.MeasurementSet.missing` and is never imputed
(``AGENTS.md`` rule 2).

References
----------
.. [1] Yeadon, M. R. (1990). The simulation of aerial movement - II. A
       mathematical inertia model of the human body. Journal of Biomechanics,
       23(1), 67-74.
.. [2] https://yeadon.readthedocs.io/en/latest/measurements.html
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml

from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
    Measurement,
    MeasurementSet,
)

try:  # pragma: no cover - import guard, outcome depends on the environment
    import yeadon
except ImportError:  # pragma: no cover
    # The mapping, extraction, and reporting functions of this module do not
    # need yeadon; only build_yeadon_human does, and it raises a clear
    # ImportError.  This keeps the adapter importable (and testable) in
    # environments where the yeadon wheel is unavailable.
    yeadon = None  # type: ignore[assignment]


__all__ = [
    "MAPPING_FILE",
    "YEADON_KEYS_ORDERED",
    "YEADON_REQUIRED_KEYS",
    "load_mapping",
    "extract_measurements",
    "build_yeadon_human",
    "export_inertial_params",
    "coverage_table",
]


#: Default location of the BodyLoop -> Yeadon mapping file.
MAPPING_FILE: Path = (
    Path(__file__).parent.parent.parent / "configs" / "bodyloop_to_yeadon.yaml"
)

#: The 95 Yeadon measurement keys in the canonical order used by
#: ``yeadon.human.Human.measnames`` (yeadon 1.5.0).  Side convention:
#: ``Ls`` torso/head-neck, ``La`` LEFT arm, ``Lb`` RIGHT arm, ``Lj`` LEFT leg,
#: ``Lk`` RIGHT leg.
YEADON_KEYS_ORDERED: tuple[str, ...] = (
    # --- torso + head-neck: 8 lengths, 7 perimeters, 5 widths, 1 depth ---
    "Ls1L", "Ls2L", "Ls3L", "Ls4L", "Ls5L", "Ls6L", "Ls7L", "Ls8L",
    "Ls0p", "Ls1p", "Ls2p", "Ls3p", "Ls5p", "Ls6p", "Ls7p",
    "Ls0w", "Ls1w", "Ls2w", "Ls3w", "Ls4w",
    "Ls4d",
    # --- left arm: 6 lengths, 8 perimeters, 4 widths ---
    "La2L", "La3L", "La4L", "La5L", "La6L", "La7L",
    "La0p", "La1p", "La2p", "La3p", "La4p", "La5p", "La6p", "La7p",
    "La4w", "La5w", "La6w", "La7w",
    # --- right arm ---
    "Lb2L", "Lb3L", "Lb4L", "Lb5L", "Lb6L", "Lb7L",
    "Lb0p", "Lb1p", "Lb2p", "Lb3p", "Lb4p", "Lb5p", "Lb6p", "Lb7p",
    "Lb4w", "Lb5w", "Lb6w", "Lb7w",
    # --- left leg: 7 lengths, 9 perimeters, 2 widths, 1 depth ---
    "Lj1L", "Lj3L", "Lj4L", "Lj5L", "Lj6L", "Lj8L", "Lj9L",
    "Lj1p", "Lj2p", "Lj3p", "Lj4p", "Lj5p", "Lj6p", "Lj7p", "Lj8p", "Lj9p",
    "Lj8w", "Lj9w",
    "Lj6d",
    # --- right leg ---
    "Lk1L", "Lk3L", "Lk4L", "Lk5L", "Lk6L", "Lk8L", "Lk9L",
    "Lk1p", "Lk2p", "Lk3p", "Lk4p", "Lk5p", "Lk6p", "Lk7p", "Lk8p", "Lk9p",
    "Lk8w", "Lk9w",
    "Lk6d",
)

#: Unordered view of :data:`YEADON_KEYS_ORDERED`, for set arithmetic.
YEADON_REQUIRED_KEYS: frozenset[str] = frozenset(YEADON_KEYS_ORDERED)

#: Top-level sections a normalised BodyLoop export must provide.
REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {"markers", "distances", "heights", "crosssections"}
)

#: Accepted spellings for each top-level section.  The normalised export writes
#: ``crosssections.json`` while some fixtures use ``cross_sections``.
_TOP_LEVEL_ALIASES: dict[str, tuple[str, ...]] = {
    "crosssections": ("crosssections", "cross_sections"),
    "crosssection_series": ("crosssection_series", "cross_section_series"),
}


def load_mapping(config_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load the ``bodyloop_to_yeadon.yaml`` mapping file.

    Parameters
    ----------
    config_path : Path or None, optional
        Path to the mapping YAML file.  Defaults to :data:`MAPPING_FILE`.

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping of Yeadon key to its mapping entry (``bodyloop_path``,
        ``source_type``, ``anatomical_definition``, ``calculation``,
        ``units``, ``frame``, ``confidence``, ``manual_validation_required``,
        ``notes``).

    Raises
    ------
    FileNotFoundError
        If the mapping file does not exist at the resolved path.
    ValueError
        If the file does not parse to a mapping, or if its key set is not
        exactly the 95 keys of :data:`YEADON_REQUIRED_KEYS`.

    Notes
    -----
    The key-set check is deliberately strict in both directions: a missing key
    would silently drop a Yeadon input, and an extra key would mean the file
    has drifted from the ``yeadon`` package's ``measnames``.

    References
    ----------
    .. [1] Yeadon, M.R. (1990). J Biomech 23(1):67-74.
    """
    path = MAPPING_FILE if config_path is None else Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Yeadon mapping file not found: {path}")

    with path.open(encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle)

    if not isinstance(parsed, dict):
        raise ValueError(
            f"Yeadon mapping file must parse to a mapping, got {type(parsed).__name__}: {path}"
        )

    keys = set(parsed)
    absent = YEADON_REQUIRED_KEYS - keys
    extra = keys - YEADON_REQUIRED_KEYS
    if absent or extra:
        raise ValueError(
            f"{path} must define exactly the 95 Yeadon keys; "
            f"missing={sorted(absent)}, unexpected={sorted(extra)}"
        )
    return parsed


def _get_section(normalized_data: dict[str, Any], name: str) -> Any:  # noqa: ANN401
    """Return a top-level section of the normalised data, honouring aliases.

    Parameters
    ----------
    normalized_data : dict[str, Any]
        Normalised BodyLoop data.
    name : str
        Canonical section name, e.g. ``"crosssections"``.

    Returns
    -------
    Any
        The section, or ``None`` if absent under every accepted spelling.

    Notes
    -----
    The return type is deliberately ``Any``: a normalised section is arbitrary
    decoded JSON, which may be a dict, a list, or a scalar depending on which
    file of the ``normalized/`` directory it came from.
    """
    for candidate in _TOP_LEVEL_ALIASES.get(name, (name,)):
        if candidate in normalized_data:
            return normalized_data[candidate]
    return None


_SENTINEL = object()


def _resolve_path(normalized_data: dict[str, Any], path: str) -> Any:  # noqa: ANN401
    """Resolve a dot-notation path in normalised BodyLoop data.

    Parameters
    ----------
    normalized_data : dict[str, Any]
        Normalised BodyLoop data, i.e. the ``normalized/`` JSON files merged
        into one dictionary keyed by section name.
    path : str
        Dot-notation path, e.g. ``"crosssections.mid_thigh_left.convex_m"``.

    Returns
    -------
    Any
        The resolved value, or the module-private sentinel when any segment of
        the path cannot be resolved.

    Notes
    -----
    Three container shapes are supported at each step, because the normalised
    export and the test fixtures do not agree on one:

    - a ``dict`` keyed by label;
    - a ``list`` of objects/dicts carrying a ``label`` field (as produced by
      ``api/export.py``), matched on that label;
    - an arbitrary object, matched on attribute name.
    """
    segments = path.split(".")
    if not segments:
        return _SENTINEL

    current = _get_section(normalized_data, segments[0])
    if current is None and segments[0] not in normalized_data:
        return _SENTINEL

    for segment in segments[1:]:
        if isinstance(current, dict):
            if segment not in current:
                return _SENTINEL
            current = current[segment]
        elif isinstance(current, (list, tuple)):
            match = _SENTINEL
            for item in current:
                label = (
                    item.get("label")
                    if isinstance(item, dict)
                    else getattr(item, "label", None)
                )
                if label == segment:
                    match = item
                    break
            if match is _SENTINEL:
                return _SENTINEL
            current = match
        else:
            if not hasattr(current, segment):
                return _SENTINEL
            current = getattr(current, segment)
    return current


def _as_float(value: Any) -> float | None:  # noqa: ANN401
    """Coerce a resolved path value to a float.

    Parameters
    ----------
    value : Any
        Value resolved by :func:`_resolve_path`.

    Returns
    -------
    float or None
        The float value, or ``None`` if the value is not a finite real number.
        Booleans are rejected: ``True`` is not a measurement.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        as_float = float(value)
        return as_float if as_float == as_float and abs(as_float) != float("inf") else None
    return None


def extract_measurements(
    normalized_data: dict[str, Any],
    mapping: dict[str, dict[str, Any]] | None = None,
    subject_id: str = "unknown",
    acquisition_date: str = "unknown",
) -> MeasurementSet:
    """Extract Yeadon measurements from BodyLoop normalised data.

    Parameters
    ----------
    normalized_data : dict[str, Any]
        Dictionary built from the ``normalized/`` directory, i.e. the
        ``markers``, ``distances``, ``heights``, ``crosssections`` (and
        optionally ``crosssection_series``, ``properties``, ``angles``)
        sections merged into one dict.
    mapping : dict[str, dict[str, Any]] or None, optional
        Override mapping.  Defaults to :func:`load_mapping`, i.e.
        ``configs/bodyloop_to_yeadon.yaml``.
    subject_id : str, optional
        Pseudonymised subject identifier.  Default ``"unknown"``.
    acquisition_date : str, optional
        ISO 8601 acquisition date.  Default ``"unknown"``.

    Returns
    -------
    MeasurementSet
        All extracted measurements with provenance.  Every Yeadon key that
        could not be resolved is listed in
        :attr:`~measurement_mapping.MeasurementSet.missing` -- it is never
        silently imputed.

    Raises
    ------
    ValueError
        If ``normalized_data`` is not a dict or is missing one of
        :data:`REQUIRED_TOP_LEVEL_KEYS`.

    Notes
    -----
    A key is reported as missing when its mapping entry has no
    ``bodyloop_path`` (the value must still be derived and validated), when
    the path does not resolve in this scan, or when the resolved value is not
    a finite number.  Values are assumed to be in metres: unit conversion is
    the responsibility of the normalisation layer, not of this adapter.

    # TODO_SCIENTIFIC: the derivations recorded in the ``calculation`` field
    # of the mapping (joint centres, crotch, heel, foot arch, thumb base,
    # lowest anterior rib) are documented but not implemented.  Those keys are
    # reported as missing until their anatomical definitions are validated --
    # see SCIENCE_DECISIONS.md.

    References
    ----------
    .. [1] Yeadon, M.R. (1990). J Biomech 23(1):67-74.
    """
    if not isinstance(normalized_data, dict):
        raise ValueError(
            "normalized_data must be a dict of normalised BodyLoop sections, "
            f"got {type(normalized_data).__name__}"
        )

    absent_sections = sorted(
        name
        for name in REQUIRED_TOP_LEVEL_KEYS
        if _get_section(normalized_data, name) is None
    )
    if absent_sections:
        raise ValueError(
            "normalized_data is missing required top-level keys: "
            f"{absent_sections}"
        )

    table = load_mapping() if mapping is None else mapping

    measurements: dict[str, Measurement] = {}
    missing: list[str] = []

    for key in YEADON_KEYS_ORDERED:
        entry = table.get(key)
        if not isinstance(entry, dict):
            missing.append(key)
            continue

        path = entry.get("bodyloop_path")
        if not path:
            # Derived or unavailable: recorded as missing, never imputed.
            missing.append(key)
            continue

        raw = _resolve_path(normalized_data, str(path))
        if raw is _SENTINEL:
            missing.append(key)
            continue

        value = _as_float(raw)
        if value is None:
            missing.append(key)
            continue

        measurements[key] = Measurement(
            value=value,
            unit=str(entry.get("units", "m")),
            frame=str(entry.get("frame", "bodyloop_global")),
            source=entry.get("source_type", "direct"),
            confidence=float(entry.get("confidence", 0.0)),
            bodyloop_path=str(path),
            notes=entry.get("notes"),
            manual_validation_required=bool(
                entry.get("manual_validation_required", True)
            ),
        )

    return MeasurementSet(
        subject_id=subject_id,
        acquisition_date=acquisition_date,
        measurements=measurements,
        missing=missing,
    )


def build_yeadon_human(
    measurement_set: MeasurementSet,
    mass_kg: float,
    symmetric: bool = False,
) -> yeadon.Human:
    """Build a :class:`yeadon.Human` from a :class:`MeasurementSet`.

    Parameters
    ----------
    measurement_set : MeasurementSet
        Measurements extracted by :func:`extract_measurements`.  All 95 Yeadon
        keys must be present.
    mass_kg : float
        Total body mass in kilograms, used to rescale the segment densities so
        that the model mass matches the measured mass.
    symmetric : bool, optional
        If ``False`` (default), left and right measurements are used
        independently.  If ``True``, ``yeadon`` averages the two sides.

    Returns
    -------
    yeadon.Human
        Human model scaled to ``mass_kg``.

    Raises
    ------
    ImportError
        If the ``yeadon`` package is not installed.
    ValueError
        If any of the 95 required keys is missing, or if ``mass_kg`` is not
        strictly positive.

    Notes
    -----
    ``yeadon`` interprets a raw measurement dictionary as metres with no
    conversion factor, and a dictionary input cannot carry a measured-mass
    override -- hence the explicit
    :meth:`yeadon.Human.scale_human_by_mass` call after construction.

    References
    ----------
    .. [1] Yeadon, M.R. (1990). J Biomech 23(1):67-74.
    """
    if yeadon is None:  # pragma: no cover - environment dependent
        raise ImportError(
            "the 'yeadon' package is required to build a Human model; "
            "install it with `pip install yeadon`"
        )
    if not mass_kg > 0:
        raise ValueError(f"mass_kg must be > 0, got {mass_kg}")

    meas_dict = measurement_set.to_yeadon_dict()
    absent = YEADON_REQUIRED_KEYS - set(meas_dict)
    if absent:
        raise ValueError(f"Missing Yeadon measurements: {sorted(absent)}")

    human = yeadon.Human(meas_dict, symmetric=symmetric)
    human.scale_human_by_mass(mass_kg)
    return human


def export_inertial_params(human: yeadon.Human) -> dict[str, dict[str, Any]]:
    """Export mass, centre of mass, and inertia tensor for each segment.

    Parameters
    ----------
    human : yeadon.Human
        Model returned by :func:`build_yeadon_human`.

    Returns
    -------
    dict[str, dict[str, Any]]
        Keys are Yeadon segment labels (``"head-neck"``, ``"thorax"``,
        ``"upper-arm"``, ...).  Each value is a dict with:

        - ``"mass_kg"`` : float
        - ``"com_m"`` : list of 3 floats, centre of mass.
        - ``"inertia_tensor_kgm2"`` : 3x3 nested list.
        - ``"frame"`` : str, the frame the COM and tensor are expressed in.

    Raises
    ------
    AttributeError
        If ``human`` does not expose a ``segments`` collection.

    Notes
    -----
    ``yeadon`` expresses segment centres of mass in its own global frame,
    whose origin is the pelvis centre (level ``Ls0``) with the ``z`` axis
    pointing up, and expresses each segment inertia tensor about that
    segment's own centre of mass.  The ``"frame"`` field records this
    explicitly so downstream exporters do not have to guess.

    # TODO_VALIDATE: confirm the yeadon global axis convention against
    # Yeadon (1990) Figure 1 before exporting to biorbd or OpenSim, whose
    # conventions differ.
    """
    params: dict[str, dict[str, Any]] = {}
    for segment in human.segments:
        label = str(segment.label)
        # yeadon returns numpy matrices: a 3x1 column vector for the centre of
        # mass and a 3x3 matrix for the inertia tensor.  np.asarray flattens
        # the matrix subclass away so the result is plain JSON-serialisable.
        com = np.asarray(segment.center_of_mass, dtype=float).reshape(3)
        inertia = np.asarray(segment.inertia, dtype=float).reshape(3, 3)
        params[label] = {
            "mass_kg": float(segment.mass),
            "com_m": [float(component) for component in com],
            "inertia_tensor_kgm2": [[float(value) for value in row] for row in inertia],
            "frame": (
                "yeadon_global (origin at pelvis centre Ls0); inertia about "
                "the segment centre of mass"
            ),
        }
    return params


def coverage_table(measurement_set: MeasurementSet) -> str:
    """Render an ASCII coverage table of the 95 Yeadon measurements.

    Parameters
    ----------
    measurement_set : MeasurementSet
        Measurements extracted by :func:`extract_measurements`.

    Returns
    -------
    str
        Fixed-width table with the columns ``key``, ``source``,
        ``confidence``, ``bodyloop_path``, ``manual_required`` and
        ``validation``, one row per Yeadon key in canonical order, followed by
        a summary line.  Keys that could not be obtained are shown with source
        ``MISSING``.

    Notes
    -----
    Every one of the 95 keys appears in the table, present or not: the point
    of the table is to make gaps visible rather than to list successes.

    Examples
    --------
    >>> from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
    ...     MeasurementSet,
    ... )
    >>> empty = MeasurementSet(
    ...     subject_id="S", acquisition_date="2026-09-11",
    ...     measurements={}, missing=list(YEADON_KEYS_ORDERED),
    ... )
    >>> "Ls1L" in coverage_table(empty)
    True
    """
    headers = (
        "key",
        "source",
        "confidence",
        "bodyloop_path",
        "manual_required",
        "validation",
    )
    rows: list[tuple[str, ...]] = []

    for key in YEADON_KEYS_ORDERED:
        meas = measurement_set.measurements.get(key)
        if meas is None:
            rows.append((key, "MISSING", "-", "-", "YES", "-"))
        else:
            rows.append(
                (
                    key,
                    meas.source,
                    f"{meas.confidence:.2f}",
                    meas.bodyloop_path or "-",
                    "YES" if meas.manual_validation_required else "no",
                    meas.validation_status,
                )
            )

    widths = [
        max(len(headers[i]), max(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    separator = "+".join("-" * (w + 2) for w in widths)

    def render(cells: tuple[str, ...]) -> str:
        """Render one table row with padded cells."""
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    report = measurement_set.coverage_report()
    lines = [
        f"Yeadon measurement coverage - subject {measurement_set.subject_id} "
        f"({measurement_set.acquisition_date})",
        separator,
        render(headers),
        separator,
    ]
    lines.extend(render(row) for row in rows)
    lines.append(separator)
    lines.append(
        f"{report['present']}/{report['total']} present "
        f"({report['coverage_fraction'] * 100:.1f}%), "
        f"{report['missing']} missing, "
        f"{report['manual_required']} present but requiring manual validation, "
        f"{report['pending_validation']} still pending review."
    )
    return "\n".join(lines)
