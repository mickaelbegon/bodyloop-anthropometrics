"""Anthropometric measurement data model with full provenance tracking.

All values are stored in SI units (metres, kilograms, radians).  Source type
and confidence are mandatory so that no measurement can be silently imputed:
a quantity that could not be obtained is recorded in
:attr:`MeasurementSet.missing`, never fabricated.

References
----------
.. [1] Yeadon, M.R. (1990). The simulation of aerial movement - II. A
       mathematical inertia model of the human body. J Biomech 23(1):67-74.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "Measurement",
    "MeasurementSet",
    "build_measurement",
]

#: Source types that do not correspond to a value read straight off the scan.
DERIVED_SOURCES: frozenset[str] = frozenset(
    {"calculated", "interpolated", "external", "manual"}
)

#: Confidence at or below which a measurement must carry explanatory notes.
LOW_CONFIDENCE_THRESHOLD: float = 0.5


class Measurement(BaseModel):
    """A single anthropometric measurement with full provenance.

    Parameters
    ----------
    value : float
        Measurement value in SI units (metres for lengths, kg for mass,
        m^2 for areas, rad for angles).
    unit : str
        SI unit string: ``"m"``, ``"kg"``, ``"m^2"`` or ``"rad"``.
    frame : str
        Reference frame, e.g. ``"bodyloop_global"``,
        ``"anatomical_local_right"``.
    source : {"direct", "calculated", "interpolated", "external", "manual"}
        Provenance of the value:

        - ``"direct"``       -- measured directly by the BodyLoop scanner.
        - ``"calculated"``   -- computed from other measurements or the mesh.
        - ``"interpolated"`` -- estimated from neighbouring cross-sections.
        - ``"external"``     -- taken from a clinical file or the literature.
        - ``"manual"``       -- entered by a human operator.

    confidence : float
        Confidence score in ``[0.0, 1.0]``.  ``1.0`` denotes a direct
        measurement; lower values denote derived or uncertain quantities.
    bodyloop_path : str or None, optional
        Dot-notation path in the normalised BodyLoop data, e.g.
        ``"distances.shoulder_width"``.  ``None`` when no direct path exists.
    notes : str or None, optional
        Caveats, validation flags, or references.  Mandatory when
        ``confidence`` is below :data:`LOW_CONFIDENCE_THRESHOLD`.
    manual_validation_required : bool, optional
        If ``True``, a human must review this value before it is used in any
        downstream computation.  Default ``False``.
    validation_status : {"pending", "approved", "rejected"}, optional
        Outcome of human review, as recorded by the interactive visual
        validation tool.  Default ``"pending"``: a value is never considered
        approved until somebody says so.
    validated_by : str or None, optional
        Initials or pseudonymised identifier of the validator.  Mandatory once
        ``validation_status`` leaves ``"pending"``.
    validated_date : str or None, optional
        ISO 8601 date of the review.  Mandatory once ``validation_status``
        leaves ``"pending"``.
    validation_notes : str or None, optional
        Free-text comment left by the validator, e.g. why a value was
        rejected or which landmark was re-digitised.

    Raises
    ------
    pydantic.ValidationError
        If ``confidence`` is outside ``[0.0, 1.0]``; if ``confidence`` is
        below :data:`LOW_CONFIDENCE_THRESHOLD` and ``notes`` is ``None``; or
        if ``validation_status`` is not ``"pending"`` while ``validated_by``
        or ``validated_date`` is ``None``.

    Notes
    -----
    A low-confidence value without an explanation is indistinguishable from a
    silent imputation, which rule 2 of ``AGENTS.md`` forbids.  The validator
    below turns that situation into a hard error rather than a warning.

    The same reasoning applies to the review fields: an approval that records
    no validator and no date is not an audit trail, so it is rejected.

    Examples
    --------
    >>> Measurement(
    ...     value=1.75, unit="m", frame="bodyloop_global",
    ...     source="direct", confidence=0.95,
    ...     bodyloop_path="heights.standing",
    ... ).value
    1.75
    """

    value: float
    unit: str
    frame: str
    source: Literal["direct", "calculated", "interpolated", "external", "manual"]
    confidence: float = Field(ge=0.0, le=1.0)
    bodyloop_path: str | None = None
    notes: str | None = None
    manual_validation_required: bool = False
    validation_status: Literal["pending", "approved", "rejected"] = "pending"
    validated_by: str | None = None
    validated_date: str | None = None
    validation_notes: str | None = None

    @model_validator(mode="after")
    def warn_low_confidence_without_notes(self) -> Measurement:
        """Require explanatory notes on any low-confidence measurement.

        Returns
        -------
        Measurement
            The validated instance, unchanged.

        Raises
        ------
        ValueError
            If ``confidence < 0.5`` and ``notes`` is ``None``.
        """
        if self.confidence < LOW_CONFIDENCE_THRESHOLD and self.notes is None:
            raise ValueError(
                "notes are required when confidence < "
                f"{LOW_CONFIDENCE_THRESHOLD} (got confidence="
                f"{self.confidence})"
            )
        return self

    @model_validator(mode="after")
    def review_outcome_needs_an_author(self) -> Measurement:
        """Require a validator and a date on any completed review.

        Returns
        -------
        Measurement
            The validated instance, unchanged.

        Raises
        ------
        ValueError
            If ``validation_status`` is ``"approved"`` or ``"rejected"`` while
            ``validated_by`` or ``validated_date`` is ``None``.

        Notes
        -----
        This keeps the interactive validation tool from writing back an
        unattributable approval, which would defeat the purpose of the review.
        """
        if self.validation_status != "pending":
            absent = [
                field
                for field, value in (
                    ("validated_by", self.validated_by),
                    ("validated_date", self.validated_date),
                )
                if value is None
            ]
            if absent:
                raise ValueError(
                    f"validation_status={self.validation_status!r} requires "
                    f"{' and '.join(absent)}"
                )
        return self

    @property
    def is_usable(self) -> bool:
        """Whether this measurement may be used without further human review.

        Returns
        -------
        bool
            ``True`` when the measurement either needs no manual validation or
            has been explicitly approved; ``False`` while it is pending or has
            been rejected.
        """
        if self.validation_status == "rejected":
            return False
        return (not self.manual_validation_required) or (
            self.validation_status == "approved"
        )


class MeasurementSet(BaseModel):
    """A named collection of measurements for one subject / acquisition.

    Parameters
    ----------
    subject_id : str
        Pseudonymised subject identifier.  Never a real patient name.
    acquisition_date : str
        ISO 8601 date string, e.g. ``"2026-09-11"``.
    measurements : dict[str, Measurement]
        Mapping from measurement key (e.g. ``"Ls1L"``) to
        :class:`Measurement`.
    missing : list[str], optional
        Keys for which no measurement could be obtained.  These are reported,
        never imputed.

    Notes
    -----
    ``measurements`` and ``missing`` are disjoint by construction: a key that
    appears in one must not appear in the other.  This invariant is enforced.
    """

    subject_id: str
    acquisition_date: str
    measurements: dict[str, Measurement]
    missing: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def measurements_and_missing_are_disjoint(self) -> MeasurementSet:
        """Ensure no key is both present and missing.

        Returns
        -------
        MeasurementSet
            The validated instance, unchanged.

        Raises
        ------
        ValueError
            If any key appears in both ``measurements`` and ``missing``.
        """
        overlap = set(self.measurements) & set(self.missing)
        if overlap:
            raise ValueError(
                "keys cannot be both present and missing: "
                f"{sorted(overlap)}"
            )
        return self

    def pending_validation(self) -> list[str]:
        """List the keys still awaiting human review.

        Returns
        -------
        list[str]
            Sorted keys whose measurement has
            ``manual_validation_required=True`` and
            ``validation_status="pending"``.

        Notes
        -----
        This is the work queue of the interactive visual validation tool: each
        returned key must be approved or rejected against the 3-D mesh before
        the measurement set can be considered scientifically usable.
        """
        return sorted(
            key
            for key, meas in self.measurements.items()
            if meas.manual_validation_required and meas.validation_status == "pending"
        )

    def rejected(self) -> list[str]:
        """List the keys a validator has explicitly rejected.

        Returns
        -------
        list[str]
            Sorted keys whose measurement has
            ``validation_status="rejected"``.

        Notes
        -----
        A rejected measurement must be re-measured or re-derived; it is not
        silently replaced by an estimate.
        """
        return sorted(
            key
            for key, meas in self.measurements.items()
            if meas.validation_status == "rejected"
        )

    def coverage_report(self) -> dict[str, object]:
        """Summarise how much of the measurement set could be filled.

        Returns
        -------
        dict[str, object]
            Dictionary with the keys:

            - ``"total"``            -- present + missing count.
            - ``"present"``          -- number of obtained measurements.
            - ``"missing"``          -- number of unobtainable measurements.
            - ``"manual_required"``  -- number of present measurements flagged
              ``manual_validation_required``.
            - ``"pending_validation"`` -- number of those still ``"pending"``.
            - ``"approved"``         -- number of present measurements with
              ``validation_status="approved"``.
            - ``"rejected"``         -- number with ``"rejected"``.
            - ``"usable"``           -- number that need no review or have
              been approved (see :attr:`Measurement.is_usable`).
            - ``"coverage_fraction"``-- ``present / total``, ``0.0`` if empty.
            - ``"by_source"``        -- count of present measurements per
              ``source`` value.
            - ``"missing_keys"``     -- sorted list of missing keys.
            - ``"manual_required_keys"`` -- sorted list of keys needing review.
            - ``"pending_validation_keys"`` -- sorted list of keys still
              awaiting review, i.e. :meth:`pending_validation`.

        Notes
        -----
        ``coverage_fraction`` counts a measurement as present even when it is
        flagged for manual validation.  Use ``manual_required`` and
        ``pending_validation`` to judge how much of that coverage is
        trustworthy without further human review.
        """
        present_keys = sorted(self.measurements)
        manual_keys = sorted(
            k for k, m in self.measurements.items() if m.manual_validation_required
        )
        by_source: dict[str, int] = {}
        for meas in self.measurements.values():
            by_source[meas.source] = by_source.get(meas.source, 0) + 1

        pending_keys = self.pending_validation()
        total = len(present_keys) + len(self.missing)
        return {
            "total": total,
            "present": len(present_keys),
            "missing": len(self.missing),
            "manual_required": len(manual_keys),
            "pending_validation": len(pending_keys),
            "approved": sum(
                1
                for m in self.measurements.values()
                if m.validation_status == "approved"
            ),
            "rejected": len(self.rejected()),
            "usable": sum(1 for m in self.measurements.values() if m.is_usable),
            "coverage_fraction": (len(present_keys) / total) if total else 0.0,
            "by_source": by_source,
            "missing_keys": sorted(self.missing),
            "manual_required_keys": manual_keys,
            "pending_validation_keys": pending_keys,
        }

    def to_yeadon_dict(
        self,
        required_keys: frozenset[str] | None = None,
    ) -> dict[str, float]:
        """Return ``{key: value_in_metres}`` suitable for :class:`yeadon.Human`.

        Parameters
        ----------
        required_keys : frozenset[str] or None, optional
            Keys that must all be present.  When ``None`` (default), only the
            keys recorded in :attr:`missing` are treated as a failure.

        Returns
        -------
        dict[str, float]
            Mapping of measurement key to its value in metres.

        Raises
        ------
        ValueError
            If any required key is missing, or if any exported measurement is
            not expressed in metres.  ``yeadon`` interprets a raw dictionary
            as metres with no conversion factor, so a non-metre unit would be
            silently misinterpreted.

        Notes
        -----
        No imputation is performed.  A measurement flagged
        ``manual_validation_required`` is still exported -- the caller is
        responsible for checking :meth:`coverage_report` first.
        """
        if self.missing:
            raise ValueError(
                "cannot build a Yeadon dictionary: "
                f"{len(self.missing)} measurement(s) missing: "
                f"{sorted(self.missing)}"
            )

        if required_keys is not None:
            absent = required_keys - set(self.measurements)
            if absent:
                raise ValueError(
                    f"missing required measurement keys: {sorted(absent)}"
                )

        non_metre = sorted(
            k for k, m in self.measurements.items() if m.unit != "m"
        )
        if non_metre:
            raise ValueError(
                "yeadon expects every measurement in metres; these are not: "
                f"{non_metre}"
            )

        return {key: meas.value for key, meas in self.measurements.items()}


def build_measurement(
    value: float,
    unit: str,
    frame: str,
    source: Literal["direct", "calculated", "interpolated", "external", "manual"],
    confidence: float,
    bodyloop_path: str | None = None,
    notes: str | None = None,
    manual_validation_required: bool = False,
    validation_status: Literal["pending", "approved", "rejected"] = "pending",
    validated_by: str | None = None,
    validated_date: str | None = None,
    validation_notes: str | None = None,
) -> Measurement:
    """Build a :class:`Measurement`, the preferred factory for adapter code.

    Parameters
    ----------
    value : float
        Measurement value in SI units.
    unit : str
        SI unit string.
    frame : str
        Reference frame name.
    source : {"direct", "calculated", "interpolated", "external", "manual"}
        Provenance type (see :class:`Measurement`).
    confidence : float
        Confidence score in ``[0.0, 1.0]``.
    bodyloop_path : str or None, optional
        Dot-notation path in the normalised BodyLoop data.
    notes : str or None, optional
        Free-text notes.  Mandatory when ``confidence < 0.5``.
    manual_validation_required : bool, optional
        If ``True``, flag for human review.
    validation_status : {"pending", "approved", "rejected"}, optional
        Outcome of human review.  Default ``"pending"``.
    validated_by : str or None, optional
        Initials or pseudonymised identifier of the validator.
    validated_date : str or None, optional
        ISO 8601 date of the review.
    validation_notes : str or None, optional
        Free-text comment left by the validator.

    Returns
    -------
    Measurement
        Validated measurement instance.

    Raises
    ------
    pydantic.ValidationError
        If any field fails validation.

    Notes
    -----
    Prefer this factory over direct ``Measurement(...)`` construction in
    adapter code so that field-level defaults can be changed centrally.

    References
    ----------
    .. [1] Pydantic v2 documentation: https://docs.pydantic.dev/latest/
    """
    return Measurement(
        value=value,
        unit=unit,
        frame=frame,
        source=source,
        confidence=confidence,
        bodyloop_path=bodyloop_path,
        notes=notes,
        manual_validation_required=manual_validation_required,
        validation_status=validation_status,
        validated_by=validated_by,
        validated_date=validated_date,
        validation_notes=validation_notes,
    )
