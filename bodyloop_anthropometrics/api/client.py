"""BodyLoop API v2 client.

Authentication is handled via the BODYLOOP_API_TOKEN environment variable.
The token is NEVER logged, stored in files, or exposed in error messages.

Examples
--------
>>> import os
>>> os.environ["BODYLOOP_BASE_URL"] = "https://bodyloop-control-pc/api/v2"
>>> os.environ["BODYLOOP_API_TOKEN"] = "your_token"
>>> client = BodyLoopClient()
>>> viatar = client.get_viatar_data("viatar-123")
"""

from __future__ import annotations

import os
from typing import Any

import httpx

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
    "BodyLoopClient",
    "BodyLoopAPIError",
]

_RETRY_ATTEMPTS = 3
_BACKOFF_FACTOR = 0.5
_TIMEOUT_SECONDS = 30.0


class BodyLoopAPIError(Exception):
    """Exception raised when the BodyLoop API returns an error.

    Parameters
    ----------
    status_code : int
        HTTP status code returned by the API.
    message : str
        Human-readable error message. Must never contain the API token.
    """

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"BodyLoop API error {status_code}: {message}")


def _build_transport_with_retries() -> httpx.HTTPTransport:
    """Build an httpx transport with retry logic.

    Returns
    -------
    httpx.HTTPTransport
        Transport configured with retry logic.
    """
    return httpx.HTTPTransport(retries=_RETRY_ATTEMPTS)


class BodyLoopClient:
    """Client for the BodyLoop API v2.

    Reads credentials exclusively from environment variables to prevent
    accidental token exposure in logs or tracebacks.

    Parameters
    ----------
    None
        All configuration comes from environment variables.

    Raises
    ------
    EnvironmentError
        If ``BODYLOOP_BASE_URL`` or ``BODYLOOP_API_TOKEN`` are not set.

    Notes
    -----
    SSL verification is disabled (``verify=False``) because the BodyLoop
    control PC typically uses a self-signed certificate on the local network.
    """

    def __init__(self) -> None:
        base_url = os.environ.get("BODYLOOP_BASE_URL")
        token = os.environ.get("BODYLOOP_API_TOKEN")

        if not base_url:
            raise EnvironmentError(
                "BODYLOOP_BASE_URL environment variable is not set. "
                "Set it to the base URL of the BodyLoop API "
                "(e.g. https://bodyloop-control-pc/api/v2)."
            )
        if not token:
            raise EnvironmentError(
                "BODYLOOP_API_TOKEN environment variable is not set. "
                "Set it to your BodyLoop API token."
            )

        self._base_url = base_url.rstrip("/")
        # Token stored privately; never exposed in logs or errors.
        self._headers = {"Authorization": f"Bearer {token}"}

        self._client = httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            verify=False,  # Self-signed cert on BodyLoop control PC
            timeout=_TIMEOUT_SECONDS,
            transport=_build_transport_with_retries(),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        """Perform a GET request and return parsed JSON.

        Parameters
        ----------
        path : str
            API path relative to the base URL.

        Returns
        -------
        Any
            Parsed JSON response.

        Raises
        ------
        BodyLoopAPIError
            If the server returns a non-2xx status code. The token is
            never included in the error message.
        """
        try:
            response = self._client.get(path)
        except httpx.RequestError as exc:
            # Strip any URL that might contain credentials from exc message
            raise BodyLoopAPIError(
                status_code=0,
                message=f"Network error contacting BodyLoop API: {type(exc).__name__}",
            ) from exc

        if not response.is_success:
            raise BodyLoopAPIError(
                status_code=response.status_code,
                message=(
                    f"BodyLoop API returned HTTP {response.status_code} "
                    f"for path '{path}'. Check the server and your credentials."
                ),
            )

        return response.json()

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_markers(self, viatar_id: str) -> list[Marker3D]:
        """Retrieve all 3D markers for a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of Marker3D
            List of parsed 3D marker objects.
        """
        data = self._get(f"/viatars/{viatar_id}/markers")
        return [Marker3D.model_validate(item) for item in data]

    def get_axes(self, viatar_id: str) -> list[Axis]:
        """Retrieve all anatomical axes for a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of Axis
            List of parsed axis objects.
        """
        data = self._get(f"/viatars/{viatar_id}/axes")
        return [Axis.model_validate(item) for item in data]

    def get_distances(self, viatar_id: str) -> list[Distance]:
        """Retrieve all distance measurements for a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of Distance
            List of parsed distance measurement objects.
        """
        data = self._get(f"/viatars/{viatar_id}/distances")
        return [Distance.model_validate(item) for item in data]

    def get_heights(self, viatar_id: str) -> list[Height]:
        """Retrieve all height measurements for a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of Height
            List of parsed height measurement objects.
        """
        data = self._get(f"/viatars/{viatar_id}/heights")
        return [Height.model_validate(item) for item in data]

    def get_crosssections(self, viatar_id: str) -> list[CrossSection]:
        """Retrieve all individual cross-sections for a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of CrossSection
            List of parsed cross-section objects.
        """
        data = self._get(f"/viatars/{viatar_id}/crosssections")
        return [CrossSection.model_validate(item) for item in data]

    def get_properties(self, viatar_id: str) -> Properties:
        """Retrieve biometric properties of the scanned subject.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        Properties
            Parsed subject properties.
        """
        data = self._get(f"/viatars/{viatar_id}/properties")
        return Properties.model_validate(data)

    def get_angles(self, viatar_id: str) -> list[Angle]:
        """Retrieve all angular measurements for a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of Angle
            List of parsed angle objects.
        """
        data = self._get(f"/viatars/{viatar_id}/angles")
        return [Angle.model_validate(item) for item in data]

    def get_crosssection_series(self, viatar_id: str) -> list[CrossSectionSeries]:
        """Retrieve all cross-section series for a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of CrossSectionSeries
            List of parsed cross-section series.
        """
        data = self._get(f"/viatars/{viatar_id}/crosssection-series")
        return [CrossSectionSeries.model_validate(item) for item in data]

    def get_crosssection_series_path(
        self, viatar_id: str, series_path: str
    ) -> CrossSectionSeries:
        """Retrieve a specific cross-section series by its path.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.
        series_path : str
            Path identifier for the series (e.g. ``"right_thigh"``).

        Returns
        -------
        CrossSectionSeries
            Parsed cross-section series.
        """
        data = self._get(
            f"/viatars/{viatar_id}/crosssection-series/{series_path}"
        )
        return CrossSectionSeries.model_validate(data)

    def get_models(self, viatar_id: str) -> list[ModelInfo]:
        """Retrieve metadata for all 3D models associated with a viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        list of ModelInfo
            List of parsed model metadata objects.
        """
        data = self._get(f"/viatars/{viatar_id}/models")
        return [ModelInfo.model_validate(item) for item in data]

    def get_transform_series_to_cartesian(self, viatar_id: str) -> dict:
        """Retrieve the raw transform-series-to-Cartesian data for a viatar.

        The format of this endpoint is not fully specified; the raw JSON
        dictionary is returned without Pydantic validation.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        dict
            Raw JSON response from the API.
        """
        return self._get(
            f"/viatars/{viatar_id}/transform-series-to-cartesian"
        )

    def get_viatar_data(self, viatar_id: str) -> ViatarData:
        """Retrieve and aggregate all data for a viatar.

        Calls every available endpoint sequentially and assembles the
        results into a single :class:`ViatarData` object.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.

        Returns
        -------
        ViatarData
            Aggregate of all measurement data for the viatar.
        """
        return ViatarData(
            viatar_id=viatar_id,
            markers=self.get_markers(viatar_id),
            axes=self.get_axes(viatar_id),
            distances=self.get_distances(viatar_id),
            heights=self.get_heights(viatar_id),
            crosssections=self.get_crosssections(viatar_id),
            crosssection_series=self.get_crosssection_series(viatar_id),
            properties=self.get_properties(viatar_id),
            angles=self.get_angles(viatar_id),
            models=self.get_models(viatar_id),
            transform_series_to_cartesian=self.get_transform_series_to_cartesian(
                viatar_id
            ),
        )

    def export_viatar(self, viatar_id: str, options: ExportOptions) -> bytes:
        """Export a viatar as a binary archive (zip).

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar.
        options : ExportOptions
            Format options for the export.

        Returns
        -------
        bytes
            Raw binary content of the export archive.

        Raises
        ------
        BodyLoopAPIError
            If the server returns a non-2xx status code.
        """
        params = {
            "measurements_format": options.measurements_format,
            "contour_format": options.contour_format,
            "mesh_3d_format": options.mesh_3d_format,
            "avatar_3d_format": options.avatar_3d_format,
        }
        try:
            response = self._client.get(
                f"/viatars/{viatar_id}/export", params=params
            )
        except httpx.RequestError as exc:
            raise BodyLoopAPIError(
                status_code=0,
                message=f"Network error during export: {type(exc).__name__}",
            ) from exc

        if not response.is_success:
            raise BodyLoopAPIError(
                status_code=response.status_code,
                message=(
                    f"BodyLoop export returned HTTP {response.status_code} "
                    f"for viatar '{viatar_id}'."
                ),
            )

        return response.content

    def inspect_api(self) -> dict:
        """Fetch the OpenAPI specification and return a summary.

        Returns
        -------
        dict
            Parsed OpenAPI JSON from ``/openapi.json``.

        Raises
        ------
        BodyLoopAPIError
            If the OpenAPI spec cannot be retrieved.
        """
        return self._get("/openapi.json")

    def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        self._client.close()

    def __enter__(self) -> "BodyLoopClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
