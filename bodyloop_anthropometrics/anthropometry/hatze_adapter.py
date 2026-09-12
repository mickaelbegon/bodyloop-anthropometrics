"""Hatze (1979) anthropometric model adapter.

Extracts the 242-measurement Hatze input set from BodyLoop ``ViatarData`` and
reports, per measurement, where the value came from.  The mapping itself lives
in ``configs/bodyloop_to_hatze.yaml`` so that anatomical definitions can be
reviewed by a scientist without reading Python.

What this module deliberately does **not** do
---------------------------------------------
The ``hatze-biomech`` cheatsheet (transcribed in ``docs/HATZE_EQUATIONS.md``)
contains the geometric primitive library A1.1-A1.9 and the segment figures, but
**not** the equations that map the 242 measurements onto the primitive
parameters ``(a, b, c, r, h, l)``.  Those require the primary source:

    Hatze, H. (1979). A model for the computational determination of parameter
    values of anthropomorphic segments.  CSIR Technical Report TWISK 79,
    Pretoria, South Africa.

Until that source is obtained, :meth:`HatzeAdapter.compute_primitive_params`
and :meth:`HatzeAdapter.export_segment_bsp` raise :class:`NotImplementedError`
with a ``TODO_SCIENTIFIC`` message.  Extraction and provenance reporting work
today; inertia computation does not, and is not faked.

Blocked primitive A1.4
----------------------
The elliptic octoparaboloid A1.4 was numerically audited and its published
coefficients are wrong (``validation/HATZE_PRIMITIVES_AUDIT.md``): the value
``0.19473`` is structurally unattainable for that surface family, and direct
integration of the printed surface disagrees with all four printed constants by
1.6-3.3 %.  Any attempt to use A1.4 raises :class:`RuntimeError`
unconditionally -- a warning would not be enough, because a 3 % inertia error
is invisible downstream.

Invariants (``AGENTS.md``)
--------------------------
* Rule 2 -- a measurement that cannot be obtained is reported in
  :attr:`~measurement_mapping.MeasurementSet.missing` or raises
  :class:`MissingMeasurementError`; it is never imputed.
* Rule 3 -- every :class:`~measurement_mapping.Measurement` carries an explicit
  ``source``.
* Rule 5 -- internal units are metres, kilograms and radians.  Native BodyLoop
  units (mm, cm, deg) are converted on read; an unrecognised unit makes the
  measurement missing rather than silently mis-scaled.

References
----------
.. [1] Hatze, H. (1979). CSIR Technical Report TWISK 79, Pretoria.
.. [2] Hatze, H. (1980). A mathematical model for the computational
       determination of parameter values of anthropomorphic segments.
       Journal of Biomechanics, 13(10), 833-843.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
    Measurement,
    MeasurementSet,
    build_measurement,
)

__all__ = [
    "MAPPING_FILE",
    "EXPECTED_MEASUREMENT_COUNT",
    "BLOCKED_PRIMITIVES",
    "HATZE_SEGMENTS",
    "MissingMeasurementError",
    "assert_primitive_usable",
    "HatzeAdapter",
]


#: Default location of the BodyLoop -> Hatze mapping file.
MAPPING_FILE: Path = (
    Path(__file__).parent.parent.parent / "configs" / "bodyloop_to_hatze.yaml"
)

#: Number of measurements in Hatze's input set (Hatze 1979/1980).
EXPECTED_MEASUREMENT_COUNT: int = 242

#: Primitives that must never be evaluated numerically.
#:
#: A1.4 (elliptic octoparaboloid) failed the numerical audit -- see
#: ``validation/HATZE_PRIMITIVES_AUDIT.md`` section 3.
BLOCKED_PRIMITIVES: frozenset[str] = frozenset({"A1.4"})

#: The 17 Hatze segments, in Hatze's numbering (docs/HATZE_EQUATIONS.md §1).
HATZE_SEGMENTS: dict[int, str] = {
    1: "abdomino-thoracic trunk",
    2: "head-neck",
    3: "left shoulder",
    4: "right shoulder",
    5: "left forearm",
    6: "right forearm",
    7: "left upper arm",
    8: "right upper arm",
    9: "left hand",
    10: "right hand",
    11: "abdomino-pelvic",
    12: "right thigh",
    13: "right shank",
    14: "right foot",
    15: "left thigh",
    16: "left shank",
    17: "left foot",
}

#: Multiplicative factors converting a native BodyLoop unit to metres.
_LENGTH_TO_METRE: dict[str, float] = {
    "m": 1.0,
    "metre": 1.0,
    "meter": 1.0,
    "cm": 1.0e-2,
    "mm": 1.0e-3,
}

#: Multiplicative factors converting a native BodyLoop unit to radians.
_ANGLE_TO_RADIAN: dict[str, float] = {
    "rad": 1.0,
    "radian": 1.0,
    "deg": math.pi / 180.0,
    "degree": math.pi / 180.0,
    "degrees": math.pi / 180.0,
}

#: Sections of ``ViatarData`` a ``bodyloop_path`` may start from.
_VIATAR_SECTIONS: frozenset[str] = frozenset(
    {
        "markers",
        "axes",
        "distances",
        "heights",
        "crosssections",
        "crosssection_series",
        "properties",
        "angles",
    }
)

#: Accepted spellings for the ``ViatarData`` sections whose names vary between
#: the API schema and the normalised export.
_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "crosssections": ("crosssections", "cross_sections"),
    "crosssection_series": ("crosssection_series", "cross_section_series"),
}

_SENTINEL = object()


class MissingMeasurementError(Exception):
    """Raised when a required measurement is absent and imputation is refused.

    Parameters
    ----------
    key : str
        Hatze measurement key, e.g. ``"h7_s03_ml"``.
    reason : str
        Why the measurement could not be obtained.
    bodyloop_path : str or None, optional
        The path that failed to resolve, when there was one.

    Notes
    -----
    ``AGENTS.md`` rule 2 forbids silently imputing a missing measurement.  This
    exception is the loud alternative: either the caller accepts a reported gap
    (``raise_on_missing=False``, the value lands in
    :attr:`~measurement_mapping.MeasurementSet.missing`) or it gets an error.
    There is no third option in which a number appears from nowhere.
    """

    def __init__(self, key: str, reason: str, bodyloop_path: str | None = None) -> None:
        self.key = key
        self.reason = reason
        self.bodyloop_path = bodyloop_path
        location = f" (bodyloop_path={bodyloop_path!r})" if bodyloop_path else ""
        super().__init__(f"Hatze measurement {key!r} is unavailable: {reason}{location}")


def assert_primitive_usable(primitive: str) -> None:
    """Refuse any use of a primitive that failed the numerical audit.

    Parameters
    ----------
    primitive : str
        Primitive identifier from Table A1, e.g. ``"A1.1"`` or ``"A1.4"``.

    Raises
    ------
    RuntimeError
        Unconditionally when ``primitive`` is in :data:`BLOCKED_PRIMITIVES`
        (currently only ``"A1.4"``).

    Notes
    -----
    # TODO_SCIENTIFIC: A1.4 primitive coefficients wrong -- see
    # validation/HATZE_PRIMITIVES_AUDIT.md.  Do not use until Hatze (1979)
    # primary source is verified.

    Examples
    --------
    >>> assert_primitive_usable("A1.1")
    >>> assert_primitive_usable("A1.4")
    Traceback (most recent call last):
        ...
    RuntimeError: Hatze primitive A1.4 is BLOCKED: ...
    """
    if primitive in BLOCKED_PRIMITIVES:
        raise RuntimeError(
            f"Hatze primitive {primitive} is BLOCKED: its published coefficients are "
            "numerically wrong (M is off by -1.60 %, k_x^2 by -3.29 %, k_z^2 by -2.42 %, "
            "and k_y^2 = 0.19473 is structurally unattainable for this surface family). "
            "See validation/HATZE_PRIMITIVES_AUDIT.md. "
            "TODO_SCIENTIFIC: do not use until Hatze (1979) primary source is verified."
        )


def _section(viatar_data: Any, name: str) -> Any:  # noqa: ANN401
    """Return one top-level section of ``viatar_data``, honouring aliases.

    Parameters
    ----------
    viatar_data : Any
        A :class:`~bodyloop_anthropometrics.api.schemas.ViatarData` instance, or
        any object or mapping exposing the same sections.
    name : str
        Canonical section name, e.g. ``"crosssections"``.

    Returns
    -------
    Any
        The section, or the module sentinel when absent under every spelling.

    Notes
    -----
    The return type is deliberately ``Any``: a section is a list of Pydantic
    models, a sub-model, or decoded JSON depending on where the data came from.
    """
    for candidate in _SECTION_ALIASES.get(name, (name,)):
        if isinstance(viatar_data, dict):
            if candidate in viatar_data:
                return viatar_data[candidate]
        elif hasattr(viatar_data, candidate):
            return getattr(viatar_data, candidate)
    return _SENTINEL


def _step(current: Any, key: str) -> Any:  # noqa: ANN401
    """Resolve one dot-separated step of a ``bodyloop_path``.

    Parameters
    ----------
    current : Any
        Container reached so far: a mapping, a sequence of labelled items, or an
        object.
    key : str
        Next path component.

    Returns
    -------
    Any
        The value reached, or the module sentinel when the step fails.

    Notes
    -----
    Sequences are matched on the ``label`` field carried by every BodyLoop
    schema (``Marker3D``, ``Distance``, ``Height``, ``CrossSection``, ...), so a
    path such as ``crosssections.left_thigh_level_03.width_ml`` reads naturally
    even though ``crosssections`` is a list, not a dict.
    """
    if isinstance(current, dict):
        return current.get(key, _SENTINEL)
    if isinstance(current, (list, tuple)):
        for item in current:
            label = item.get("label") if isinstance(item, dict) else getattr(item, "label", None)
            if label == key:
                return item
        return _SENTINEL
    value = getattr(current, key, _SENTINEL)
    return value


def _resolve_path(viatar_data: Any, path: str) -> tuple[Any, Any]:  # noqa: ANN401
    """Resolve a dotted ``bodyloop_path`` and return the value and its owner.

    Parameters
    ----------
    viatar_data : Any
        BodyLoop viatar data.
    path : str
        Dotted path, e.g. ``"crosssections.trunk_level_01.width_ml"``.

    Returns
    -------
    value : Any
        The resolved leaf value, or the module sentinel when unresolved.
    owner : Any
        The object the leaf was read from, used to find its native ``unit``.
        The sentinel when the path could not be resolved.
    """
    parts = [part for part in path.split(".") if part]
    if not parts or parts[0] not in _VIATAR_SECTIONS:
        return _SENTINEL, _SENTINEL

    current = _section(viatar_data, parts[0])
    if current is _SENTINEL:
        return _SENTINEL, _SENTINEL

    owner: Any = viatar_data
    for part in parts[1:]:
        owner = current
        current = _step(current, part)
        if current is _SENTINEL:
            return _SENTINEL, _SENTINEL
    return current, owner


def _to_si(value: Any, owner: Any, target_unit: str) -> float | None:  # noqa: ANN401
    """Convert a resolved BodyLoop value to the internal SI unit.

    Parameters
    ----------
    value : Any
        Raw value read from the scan data.
    owner : Any
        Object the value was read from; its ``unit`` attribute, when present,
        gives the native unit.
    target_unit : {"m", "rad"}
        Internal unit requested by the mapping entry.

    Returns
    -------
    float or None
        The converted, finite value, or ``None`` when the value is not a finite
        real number or its native unit cannot be converted.

    Notes
    -----
    # ASSUMPTION: when the owning object carries no ``unit`` field, the value is
    # taken to be already expressed in the internal unit (metres or radians),
    # i.e. it has passed through the normalisation layer.  An unrecognised unit
    # string is never guessed: the measurement is reported missing instead,
    # because a silent mm/m confusion is a factor-1000 error in the inertia.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None

    native = getattr(owner, "unit", None)
    if isinstance(owner, dict):
        native = owner.get("unit", None)
    if native is None or not isinstance(native, str):
        return numeric

    table = _ANGLE_TO_RADIAN if target_unit == "rad" else _LENGTH_TO_METRE
    factor = table.get(native.strip().lower())
    if factor is None:
        return None
    return numeric * factor


class HatzeAdapter:
    """Extract the Hatze (1979) measurement set from BodyLoop viatar data.

    Parameters
    ----------
    config_path : Path or None, optional
        Mapping file to use.  Defaults to :data:`MAPPING_FILE`, i.e.
        ``configs/bodyloop_to_hatze.yaml``.

    Attributes
    ----------
    config_path : Path
        Resolved mapping file path.

    Notes
    -----
    The adapter is stateless apart from a lazy cache of the parsed mapping, so
    one instance may be reused across subjects.

    Examples
    --------
    >>> adapter = HatzeAdapter()
    >>> len(adapter.load_mapping()) == EXPECTED_MEASUREMENT_COUNT
    True

    References
    ----------
    .. [1] Hatze, H. (1979). CSIR Technical Report TWISK 79, Pretoria.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path: Path = MAPPING_FILE if config_path is None else Path(config_path)
        self._mapping: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # mapping
    # ------------------------------------------------------------------
    def load_mapping(self, config_path: Path | None = None) -> dict[str, dict[str, Any]]:
        """Load ``bodyloop_to_hatze.yaml``.

        Parameters
        ----------
        config_path : Path or None, optional
            Override path.  Defaults to :attr:`config_path`.

        Returns
        -------
        dict[str, dict[str, Any]]
            Mapping of Hatze measurement key to its entry, in file order.  Each
            entry carries ``description``, ``primitive``, ``parameter``,
            ``segment``, ``unit``, ``source``, ``bodyloop_path``, ``frame``,
            ``confidence``, ``manual_validation_required``, ``path_note``,
            ``notes`` and, for A1.4 entries only, ``blocked``.

        Raises
        ------
        FileNotFoundError
            If the mapping file does not exist.
        ValueError
            If the file does not parse to a mapping of mappings, if an entry is
            missing its mandatory ``source`` or ``segment`` field, if a
            ``segment`` is outside 1-17, or if an entry feeding a blocked
            primitive is not marked ``blocked: true``.

        Notes
        -----
        The entry count is *not* required to be exactly 242: Hatze's count is
        itself a reconstruction from the segment figures (see the file header).
        A mapping with fewer than 200 entries is rejected, because that would
        mean whole segments are absent rather than a counting difference.
        """
        path = self.config_path if config_path is None else Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"Hatze mapping file not found: {path}")

        with path.open(encoding="utf-8") as handle:
            parsed = yaml.safe_load(handle)

        if not isinstance(parsed, dict):
            raise ValueError(
                f"Hatze mapping file must parse to a mapping, got "
                f"{type(parsed).__name__}: {path}"
            )
        if len(parsed) < 200:
            raise ValueError(
                f"{path} defines {len(parsed)} measurements; Hatze's set has "
                f"{EXPECTED_MEASUREMENT_COUNT} -- whole segments appear to be missing"
            )

        for key, entry in parsed.items():
            if not isinstance(entry, dict):
                raise ValueError(f"{path}: entry {key!r} must be a mapping")
            if not entry.get("source"):
                # AGENTS.md rule 3: provenance is mandatory, never defaulted.
                raise ValueError(f"{path}: entry {key!r} has no 'source' field")
            segment = entry.get("segment")
            if segment not in HATZE_SEGMENTS:
                raise ValueError(
                    f"{path}: entry {key!r} has segment={segment!r}, expected one of 1-17"
                )
            if entry.get("primitive") in BLOCKED_PRIMITIVES and not entry.get("blocked"):
                raise ValueError(
                    f"{path}: entry {key!r} feeds blocked primitive "
                    f"{entry['primitive']} but is not marked 'blocked: true'"
                )

        if config_path is None:
            self._mapping = parsed
        return parsed

    def _mapping_or_load(
        self,
        mapping: dict[str, dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]]:
        """Return the caller's mapping, the cached one, or load it from disk.

        Parameters
        ----------
        mapping : dict[str, dict[str, Any]] or None
            Explicit mapping supplied by the caller, or ``None``.

        Returns
        -------
        dict[str, dict[str, Any]]
            The mapping to use.
        """
        if mapping is not None:
            return mapping
        if self._mapping is None:
            self._mapping = self.load_mapping()
        return self._mapping

    # ------------------------------------------------------------------
    # extraction
    # ------------------------------------------------------------------
    def extract_measurements(
        self,
        viatar_data: Any,  # noqa: ANN401
        mapping: dict[str, dict[str, Any]] | None = None,
        subject_id: str = "unknown",
        acquisition_date: str = "unknown",
        raise_on_missing: bool = False,
    ) -> MeasurementSet:
        """Extract all Hatze measurements with provenance tracking.

        Parameters
        ----------
        viatar_data : ViatarData
            BodyLoop viatar data, or any object exposing the same sections
            (``markers``, ``distances``, ``heights``, ``crosssections``,
            ``crosssection_series``, ``angles``, ``properties``).
        mapping : dict[str, dict[str, Any]] or None, optional
            Override mapping.  Defaults to :meth:`load_mapping`.
        subject_id : str, optional
            Pseudonymised subject identifier.  Default ``"unknown"``.
        acquisition_date : str, optional
            ISO 8601 acquisition date.  Default ``"unknown"``.
        raise_on_missing : bool, optional
            If ``True``, a ``source: "direct"`` measurement that cannot be read
            from ``viatar_data`` raises instead of being reported.  Default
            ``False``.

        Returns
        -------
        MeasurementSet
            Every obtainable measurement, with an explicit ``source`` on each
            (``AGENTS.md`` rule 3).  Keys that could not be obtained are listed
            in :attr:`~measurement_mapping.MeasurementSet.missing`.

        Raises
        ------
        ValueError
            If ``viatar_data`` is ``None``.
        MissingMeasurementError
            If a ``"direct"`` measurement is absent from ``viatar_data`` and
            ``raise_on_missing`` is ``True``.  Never silently imputes.

        Notes
        -----
        A measurement is reported missing when its entry has no
        ``bodyloop_path`` (the quantity must still be derived -- the derivation
        equations are the missing half of Hatze 1979), when the path does not
        resolve against this scan, or when the value is not a finite number in
        a convertible unit.  Derived (``calculated`` / ``manual``) entries are
        *never* raised on, because their absence is expected until the primary
        source is integrated.

        # TODO_SCIENTIFIC: the measurement-to-primitive-parameter equations are
        # absent from the cheatsheet; extraction fills the measurement set but
        # nothing consumes it yet -- see SCIENCE_DECISIONS.md.
        """
        if viatar_data is None:
            raise ValueError("viatar_data must not be None")

        table = self._mapping_or_load(mapping)

        measurements: dict[str, Measurement] = {}
        missing: list[str] = []

        for key, entry in table.items():
            source = str(entry.get("source", "")) or "manual"
            unit = str(entry.get("unit", "m"))
            path = entry.get("bodyloop_path")

            reason: str | None = None
            value: float | None = None

            if not path:
                reason = "no bodyloop_path: the quantity must be derived (Hatze 1979 pending)"
            else:
                raw, owner = _resolve_path(viatar_data, str(path))
                if raw is _SENTINEL:
                    reason = "bodyloop_path does not resolve in this scan"
                else:
                    value = _to_si(raw, owner, unit)
                    if value is None:
                        reason = "value is not a finite number in a convertible unit"

            if value is None:
                if raise_on_missing and source == "direct":
                    raise MissingMeasurementError(
                        key,
                        reason or "unavailable",
                        str(path) if path else None,
                    )
                missing.append(key)
                continue

            notes = entry.get("notes")
            path_note = entry.get("path_note")
            if path_note:
                notes = f"{notes}; {path_note}" if notes else str(path_note)
            if entry.get("blocked"):
                notes = f"BLOCKED PRIMITIVE {entry.get('primitive')}. {notes}"

            measurements[key] = build_measurement(
                value=value,
                unit=unit,
                frame=str(entry.get("frame", "bodyloop_global")),
                source=source,  # type: ignore[arg-type]
                confidence=float(entry.get("confidence", 0.0)),
                bodyloop_path=str(path),
                notes=str(notes) if notes is not None else None,
                manual_validation_required=bool(entry.get("manual_validation_required", True)),
            )

        return MeasurementSet(
            subject_id=subject_id,
            acquisition_date=acquisition_date,
            measurements=measurements,
            missing=missing,
        )

    # ------------------------------------------------------------------
    # geometry (blocked on the primary source)
    # ------------------------------------------------------------------
    def compute_primitive_params(
        self,
        meas: MeasurementSet,
        segment_id: int,
        primitive: str | None = None,
        mapping: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, float]:
        """Compute the geometric primitive parameters of one segment.

        Parameters
        ----------
        meas : MeasurementSet
            Measurements extracted by :meth:`extract_measurements`.
        segment_id : int
            Hatze segment number, 1-17 (see :data:`HATZE_SEGMENTS`).
        primitive : str or None, optional
            Restrict the computation to one primitive of Table A1.  When it
            names a blocked primitive the call fails before anything else.
        mapping : dict[str, dict[str, Any]] or None, optional
            Override mapping, for symmetry with :meth:`extract_measurements`.

        Returns
        -------
        dict[str, float]
            Would map parameter name (``"a_1"``, ``"b_1"``, ``"h"``, ...) to its
            value in metres or radians.  Never returned today.

        Raises
        ------
        ValueError
            If ``segment_id`` is not one of the 17 Hatze segments.
        RuntimeError
            If ``primitive`` is blocked (currently ``"A1.4"``).  Unconditional:
            the audit showed its coefficients are wrong by 1.6-3.3 %, which is
            not something a warning can make safe.
        NotImplementedError
            For every segment, always, until the primary source is integrated.

        Notes
        -----
        # TODO_SCIENTIFIC: Hatze (1979) section 3 gives the equations mapping the
        # 242 measurements onto (a, b, c, r, h, l) per segment.  The cheatsheet
        # (docs/HATZE_EQUATIONS.md §5) explicitly does not contain them, so no
        # formula here would be anything but invention.  See
        # SCIENCE_DECISIONS.md, entry "Hatze equation audit - primary source".

        Examples
        --------
        >>> from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
        ...     MeasurementSet,
        ... )
        >>> empty = MeasurementSet(subject_id="S", acquisition_date="2026-09-12",
        ...                        measurements={}, missing=[])
        >>> HatzeAdapter().compute_primitive_params(empty, 1)
        Traceback (most recent call last):
            ...
        NotImplementedError: ...
        """
        if segment_id not in HATZE_SEGMENTS:
            raise ValueError(
                f"segment_id must be one of the 17 Hatze segments (1-17), got {segment_id!r}"
            )
        if primitive is not None:
            assert_primitive_usable(primitive)

        del meas, mapping  # nothing can be consumed until the equations exist
        raise NotImplementedError(
            f"TODO_SCIENTIFIC: the measurement-to-parameter equations for Hatze segment "
            f"{segment_id} ({HATZE_SEGMENTS[segment_id]}) are not available. The "
            "hatze-biomech cheatsheet (docs/HATZE_EQUATIONS.md §5) contains the primitive "
            "library and the segment figures but NOT the equations mapping the 242 "
            "measurements onto the primitive parameters. Obtain Hatze, H. (1979), CSIR "
            "Technical Report TWISK 79, Pretoria, before implementing this. See "
            "SCIENCE_DECISIONS.md."
        )

    def export_segment_bsp(
        self,
        meas: MeasurementSet,
        density_model: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Export mass, centre of mass and inertia per segment (future work).

        Parameters
        ----------
        meas : MeasurementSet
            Measurements extracted by :meth:`extract_measurements`.
        density_model : str or None, optional
            Name of the density model to apply.  Hatze's model uses a
            position-dependent density with a subcutaneous fat correction,
            which the cheatsheet does not reproduce.

        Returns
        -------
        dict[str, dict[str, Any]]
            Would map segment name to ``{"mass_kg", "com_m",
            "inertia_tensor_kgm2", "frame"}``.  Never returned today.

        Raises
        ------
        NotImplementedError
            Always, until both the measurement-to-parameter mapping and the
            density model of Hatze (1979) are available.

        Notes
        -----
        # TODO_SCIENTIFIC: this is Phase 3 future work.  Three separate pieces
        # are missing: (i) the measurement-to-parameter equations, (ii) the
        # position-dependent density and subcutaneous fat model, and (iii) the
        # lung volume integration formula.  The blocked primitive A1.4 would
        # also have to be re-derived first.  Producing numbers without them
        # would violate AGENTS.md rule 2 in spirit: an inertia tensor invented
        # from an unverified formula is an imputed measurement wearing a hat.
        """
        del meas, density_model
        raise NotImplementedError(
            "TODO_SCIENTIFIC: Hatze segment BSP export is not implemented. It requires "
            "(1) the measurement-to-parameter mapping of Hatze (1979) section 3, "
            "(2) the position-dependent density and subcutaneous fat model, and "
            "(3) the lung volume integration formula -- none of which are in the "
            "cheatsheet (docs/HATZE_EQUATIONS.md §5). Primitive A1.4 is additionally "
            "BLOCKED (validation/HATZE_PRIMITIVES_AUDIT.md). See SCIENCE_DECISIONS.md."
        )

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------
    def coverage_table(
        self,
        meas: MeasurementSet,
        mapping: dict[str, dict[str, Any]] | None = None,
        max_width: int = 160,
    ) -> str:
        """Render a coverage table of the Hatze measurement set.

        Parameters
        ----------
        meas : MeasurementSet
            Measurements extracted by :meth:`extract_measurements`.
        mapping : dict[str, dict[str, Any]] or None, optional
            Override mapping, used for the key order and the segment and
            primitive columns.  Defaults to :meth:`load_mapping`.
        max_width : int, optional
            Console width used to render the table.  Default ``160``.

        Returns
        -------
        str
            A ``rich`` table with one row per Hatze measurement -- columns
            ``key``, ``segment``, ``primitive``, ``status``, ``source``,
            ``confidence``, ``bodyloop_path``, ``manual``, ``validation`` --
            followed by a summary line.  Missing keys are shown with status
            ``MISSING``; blocked keys are shown with status ``BLOCKED``.

        Notes
        -----
        Every mapped key appears, present or not: the point of the table is to
        make the gaps visible rather than to list the successes.

        Examples
        --------
        >>> from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
        ...     MeasurementSet,
        ... )
        >>> empty = MeasurementSet(subject_id="S", acquisition_date="2026-09-12",
        ...                        measurements={}, missing=[])
        >>> "Hatze measurement coverage" in HatzeAdapter().coverage_table(empty)
        True
        """
        table_map = self._mapping_or_load(mapping)

        table = Table(
            title=(
                f"Hatze measurement coverage - subject {meas.subject_id} "
                f"({meas.acquisition_date})"
            ),
            show_lines=False,
        )
        for column in (
            "key",
            "segment",
            "primitive",
            "status",
            "source",
            "confidence",
            "bodyloop_path",
            "manual",
            "validation",
        ):
            table.add_column(column, overflow="fold")

        blocked_present = 0
        for key, entry in table_map.items():
            measurement = meas.measurements.get(key)
            is_blocked = bool(entry.get("blocked"))
            primitive = str(entry.get("primitive", "-"))
            segment = str(entry.get("segment", "-"))
            if measurement is None:
                table.add_row(
                    key, segment, primitive, "MISSING", str(entry.get("source", "-")),
                    "-", str(entry.get("bodyloop_path") or "-"), "YES", "-",
                )
                continue
            if is_blocked:
                blocked_present += 1
            table.add_row(
                key,
                segment,
                primitive,
                "BLOCKED" if is_blocked else "present",
                measurement.source,
                f"{measurement.confidence:.2f}",
                measurement.bodyloop_path or "-",
                "YES" if measurement.manual_validation_required else "no",
                measurement.validation_status,
            )

        console = Console(file=io.StringIO(), width=max_width, record=False, no_color=True)
        console.print(table)
        rendered = console.file.getvalue()  # type: ignore[attr-defined]

        report = meas.coverage_report()
        summary = (
            f"{report['present']}/{len(table_map)} mapped keys present, "
            f"{report['missing']} missing, "
            f"{report['manual_required']} requiring manual validation, "
            f"{report['pending_validation']} pending review, "
            f"{blocked_present} feeding the BLOCKED primitive A1.4 "
            "(see validation/HATZE_PRIMITIVES_AUDIT.md)."
        )
        return f"{rendered}{summary}\n"
