"""Pydantic schemas for BodyLoop API v2 responses.

All values are stored in their original BodyLoop units.
Unit conversion to SI happens in the normalization layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

__all__ = [
    "Marker3D",
    "Axis",
    "Distance",
    "Height",
    "CrossSection",
    "CrossSectionSeries",
    "Properties",
    "Angle",
    "ModelInfo",
    "ViatarData",
    "ExportOptions",
]


class Marker3D(BaseModel):
    """3D marker position from BodyLoop.

    Parameters
    ----------
    x : float
        X coordinate in BodyLoop global frame (mm).
    y : float
        Y coordinate in BodyLoop global frame (mm).
    z : float
        Z coordinate in BodyLoop global frame (mm).
    label : str
        Anatomical or technical label for the marker.
    confidence : float or None
        Detection confidence in [0, 1], or None if not provided.
    """

    x: float
    y: float
    z: float
    label: str
    confidence: float | None = None


class Axis(BaseModel):
    """Anatomical or technical axis defined by an origin and direction marker.

    Parameters
    ----------
    origin : Marker3D
        Origin point of the axis.
    direction : Marker3D
        Direction vector of the axis (unit vector expected).
    label : str
        Label identifying this axis (e.g. ``"longitudinal_axis"``).
    """

    origin: Marker3D
    direction: Marker3D
    label: str


class Distance(BaseModel):
    """Scalar distance measurement from BodyLoop.

    Parameters
    ----------
    value : float
        Distance value in BodyLoop native units (typically mm).
    unit : str
        Unit string as returned by the API (e.g. ``"mm"``).
    label : str
        Human-readable label for the measurement.
    left_right : {"left", "right", "bilateral"} or None
        Laterality of the measurement, or None for non-lateral measurements.
    """

    value: float
    unit: str
    label: str
    left_right: Literal["left", "right", "bilateral"] | None = None


class Height(BaseModel):
    """Vertical height measurement from BodyLoop.

    Parameters
    ----------
    value : float
        Height value in BodyLoop native units (typically mm).
    unit : str
        Unit string as returned by the API (e.g. ``"mm"``).
    label : str
        Human-readable label for the measurement.
    """

    value: float
    unit: str
    label: str


class CrossSection(BaseModel):
    """Single cross-sectional slice of a body segment.

    Parameters
    ----------
    perimeter : float
        Perimeter of the cross-section contour in native units.
    area : float
        Area of the cross-section in native units squared.
    width_ml : float or None
        Medio-lateral width of the cross-section, or None if not computed.
    depth_ap : float or None
        Antero-posterior depth of the cross-section, or None if not computed.
    unit : str
        Unit string for linear dimensions (e.g. ``"mm"``).
    position : float
        Position along the segment axis at which the slice was taken.
    label : str
        Label identifying this cross-section.
    """

    perimeter: float
    area: float
    width_ml: float | None = None
    depth_ap: float | None = None
    unit: str
    position: float
    label: str


class CrossSectionSeries(BaseModel):
    """Ordered series of cross-sections along a body segment axis.

    Parameters
    ----------
    label : str
        Label identifying the series (e.g. ``"right_thigh"``).
    sections : list of CrossSection
        Ordered list of cross-section slices.
    axis_label : str
        Label of the axis along which sections are arranged.
    """

    label: str
    sections: list[CrossSection]
    axis_label: str


class Properties(BaseModel):
    """Biometric properties of the scanned subject.

    Parameters
    ----------
    mass_kg : float or None
        Body mass in kilograms, must be > 0 if provided.
    height_m : float or None
        Standing height in metres, must be > 0 if provided.
    age_years : float or None
        Age of the subject in years, or None if not recorded.
    sex : {"male", "female", "other"} or None
        Biological sex of the subject, or None if not recorded.
    bmi : float or None
        Body mass index in kg/m², or None if not computed.
    """

    mass_kg: float | None = None
    height_m: float | None = None
    age_years: float | None = None
    sex: Literal["male", "female", "other"] | None = None
    bmi: float | None = None

    @field_validator("mass_kg")
    @classmethod
    def mass_must_be_positive(cls, v: float | None) -> float | None:
        """Validate that mass_kg is strictly positive when provided.

        Parameters
        ----------
        v : float or None
            The value to validate.

        Returns
        -------
        float or None
            The validated value.

        Raises
        ------
        ValueError
            If v is not None and not > 0.
        """
        if v is not None and v <= 0:
            raise ValueError(f"mass_kg must be > 0, got {v}")
        return v

    @field_validator("height_m")
    @classmethod
    def height_must_be_positive(cls, v: float | None) -> float | None:
        """Validate that height_m is strictly positive when provided.

        Parameters
        ----------
        v : float or None
            The value to validate.

        Returns
        -------
        float or None
            The validated value.

        Raises
        ------
        ValueError
            If v is not None and not > 0.
        """
        if v is not None and v <= 0:
            raise ValueError(f"height_m must be > 0, got {v}")
        return v


class Angle(BaseModel):
    """Angular measurement from BodyLoop.

    Parameters
    ----------
    value : float
        Angle value in native units (typically degrees).
    unit : str
        Unit string as returned by the API (e.g. ``"deg"``).
    label : str
        Human-readable label for the measurement.
    """

    value: float
    unit: str
    label: str


class ModelInfo(BaseModel):
    """Metadata for a 3D model associated with a viatar.

    Parameters
    ----------
    model_type : str
        Type of model (e.g. ``"mesh_3d"``, ``"avatar_3d"``).
    format : str
        File format (e.g. ``"glb"``, ``"obj"``).
    url : str or None
        Download URL for the model, or None if not available.
    """

    model_type: str
    format: str
    url: str | None = None


class ViatarData(BaseModel):
    """Aggregate of all measurement data for a BodyLoop viatar.

    Parameters
    ----------
    viatar_id : str
        Unique identifier of the viatar in BodyLoop.
    markers : list of Marker3D
        All 3D markers detected in the scan.
    axes : list of Axis
        All anatomical and technical axes.
    distances : list of Distance
        All scalar distance measurements.
    heights : list of Height
        All height measurements.
    crosssections : list of CrossSection
        All individual cross-section slices.
    crosssection_series : list of CrossSectionSeries
        All cross-section series grouped by segment.
    properties : Properties
        Subject biometric properties.
    angles : list of Angle
        All angular measurements.
    models : list of ModelInfo
        Available 3D model files.
    transform_series_to_cartesian : dict
        Raw transform data (format defined by BodyLoop API).
    """

    viatar_id: str
    markers: list[Marker3D] = []
    axes: list[Axis] = []
    distances: list[Distance] = []
    heights: list[Height] = []
    crosssections: list[CrossSection] = []
    crosssection_series: list[CrossSectionSeries] = []
    properties: Properties = Properties()
    angles: list[Angle] = []
    models: list[ModelInfo] = []
    transform_series_to_cartesian: dict = {}


class ExportOptions(BaseModel):
    """Options controlling the format of a BodyLoop export package.

    Parameters
    ----------
    measurements_format : str
        Format for measurement data (e.g. ``"json"``).
    contour_format : str
        Format for cross-section contour data (e.g. ``"json"``).
    mesh_3d_format : str
        Format for the 3D mesh (e.g. ``"glb"``).
    avatar_3d_format : str
        Format for the avatar mesh (e.g. ``"glb"``).
    """

    measurements_format: str = "json"
    contour_format: str = "json"
    mesh_3d_format: str = "glb"
    avatar_3d_format: str = "glb"
