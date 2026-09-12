"""bodyloop_anthropometrics.api — BodyLoop REST API client and data schemas.

Note
----
This sub-package is maintained by Agent C.
Implementation lives in ``client.py``, ``schemas.py``, and ``export.py``.
"""

from bodyloop_anthropometrics.api.client import BodyLoopAPIError, BodyLoopClient
from bodyloop_anthropometrics.api.export import ExportPipeline, compute_sha256, pseudonymize_subject
from bodyloop_anthropometrics.api.schemas import (
    Angle,
    Axis,
    CrossSection,
    CrossSectionSeries,
    Distance,
    ExportOptions,
    Height,
    Marker3D,
    ModelInfo,
    Properties,
    ViatarData,
)

__all__ = [
    # client
    "BodyLoopClient",
    "BodyLoopAPIError",
    # export
    "ExportPipeline",
    "pseudonymize_subject",
    "compute_sha256",
    # schemas
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
