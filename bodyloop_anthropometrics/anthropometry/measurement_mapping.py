"""Measurement type and mapping utilities for anthropometric data.

The :class:`Measurement` Pydantic model is the canonical representation for
every measurement produced by this pipeline.  It carries full provenance so
that downstream consumers can audit the origin, confidence, and validation
status of every value.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Measurement(BaseModel):
    """A single anthropometric measurement with full provenance tracking.

    Parameters
    ----------
    value : float
        Measurement value in SI units (metres for lengths, kg for mass,
        m² for areas, rad for angles).
    unit : str
        SI unit string, e.g. ``"m"``, ``"kg"``, ``"m^2"``, ``"rad"``.
    frame : str
        Reference frame, e.g. ``"bodyloop_global"``,
        ``"anatomical_local_right"``.
    source : Literal
        Provenance type:

        - ``"direct"``        — measured directly by BodyLoop sensors.
        - ``"calculated"``    — computed from other measurements or the mesh.
        - ``"interpolated"``  — estimated from neighbouring values.
        - ``"external"``      — from an external database or literature.
        - ``"manual"``        — entered by a human operator.

    confidence : float
        Confidence score ``[0.0, 1.0]``.  ``1.0`` = direct measurement,
        lower values indicate derived or uncertain quantities.
    bodyloop_path : str or None
        JSON path in BodyLoop normalised data,
        e.g. ``"distances.shoulder_width"``.  ``None`` if no direct path
        exists.
    notes : str or None
        Free-text notes, caveats, or validation flags.
    manual_validation_required : bool
        If ``True``, this measurement must be reviewed by a human operator
        before use in downstream computations.
    """

    value: float
    unit: str
    frame: str
    source: Literal["direct", "calculated", "interpolated", "external", "manual"]
    confidence: float = Field(ge=0.0, le=1.0)
    bodyloop_path: str | None = None
    notes: str | None = None
    manual_validation_required: bool = False


def build_measurement(
    value: float,
    unit: str,
    frame: str,
    source: Literal["direct", "calculated", "interpolated", "external", "manual"],
    confidence: float,
    bodyloop_path: str | None = None,
    notes: str | None = None,
    manual_validation_required: bool = False,
) -> Measurement:
    """Convenience constructor for :class:`Measurement`.

    Parameters
    ----------
    value : float
        Measurement value in SI units.
    unit : str
        SI unit string.
    frame : str
        Reference frame name.
    source : Literal
        Provenance type (see :class:`Measurement`).
    confidence : float
        Confidence score ``[0.0, 1.0]``.
    bodyloop_path : str or None, optional
        JSON path in BodyLoop normalised data.
    notes : str or None, optional
        Free-text notes.
    manual_validation_required : bool, optional
        If ``True``, flag for human review.

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
    )
