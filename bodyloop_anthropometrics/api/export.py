"""BodyLoop export pipeline.

Creates a versioned, reproducible directory structure for each acquisition.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from bodyloop_anthropometrics.api.client import BodyLoopClient
from bodyloop_anthropometrics.api.schemas import ExportOptions

__all__ = [
    "ExportPipeline",
    "pseudonymize_subject",
    "compute_sha256",
]

# UUID v5 namespace used for deterministic subject pseudonymisation.
# Using DNS namespace with a fixed name to get a project-specific sub-namespace.
_PSEUDONYM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "bodyloop-anthropometrics")


def pseudonymize_subject(name_or_id: str) -> str:
    """Generate a deterministic pseudonymous UUID from a BodyLoop subject ID.

    Uses UUID v5 (SHA-1 based) with a project-specific namespace so that
    the same input always yields the same output, but the output does not
    reveal the original ID.

    Parameters
    ----------
    name_or_id : str
        The BodyLoop subject or viatar ID. Must not be a real name; pass
        the system-assigned identifier only.

    Returns
    -------
    str
        A UUID v5 string that serves as the pseudonymous identifier.

    Notes
    -----
    This function is deterministic: ``pseudonymize_subject(x) == pseudonymize_subject(x)``
    for any input ``x``. Do NOT pass real names or personally identifying
    information as ``name_or_id``.
    """
    return str(uuid.uuid5(_PSEUDONYM_NAMESPACE, name_or_id))


def compute_sha256(path: Path | str) -> str:
    """Compute the SHA-256 hex digest of a file.

    Parameters
    ----------
    path : Path or str
        Absolute or relative path to the file.

    Returns
    -------
    str
        Lowercase hex string of the SHA-256 digest.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at ``path``.
    """
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class ExportPipeline:
    """Pipeline that exports a BodyLoop viatar to a reproducible directory.

    Parameters
    ----------
    client : BodyLoopClient
        Authenticated client for the BodyLoop API.

    Notes
    -----
    The directory structure created by :meth:`run` is::

        subject_id/
            acquisition_date/
                raw/
                    bodyloop-export.zip
                    openapi.json
                    mesh_3d.glb
                    avatar_3d.glb
                normalized/
                    proband.json
                    markers.json
                    axes.json
                    distances.json
                    heights.json
                    crosssections.json
                    crosssection_series.json
                    properties.json
                    angles.json
                manifest.json
    """

    def __init__(self, client: BodyLoopClient) -> None:
        self._client = client

    def run(
        self,
        viatar_id: str,
        output_dir: Path | str,
        subject_id: str,
        acquisition_date: str,
    ) -> Path:
        """Execute the full export pipeline for one viatar.

        Parameters
        ----------
        viatar_id : str
            Unique identifier of the viatar in BodyLoop.
        output_dir : Path or str
            Root directory under which the acquisition tree is created.
        subject_id : str
            BodyLoop system-assigned subject ID (not a real name). Will be
            pseudonymised before use as a directory name.
        acquisition_date : str
            ISO 8601 date string for the acquisition (e.g. ``"2024-01-15"``).

        Returns
        -------
        Path
            Path to the ``manifest.json`` file that was written.

        Raises
        ------
        BodyLoopAPIError
            If any API call fails.
        OSError
            If directory creation or file writing fails.
        """
        output_dir = Path(output_dir)

        # Pseudonymise subject ID for directory name
        pseudo_id = pseudonymize_subject(subject_id)

        # Build directory tree
        acq_root = output_dir / pseudo_id / acquisition_date
        raw_dir = acq_root / "raw"
        normalized_dir = acq_root / "normalized"
        raw_dir.mkdir(parents=True, exist_ok=True)
        normalized_dir.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # 1. Export archive (ZIP)
        # ------------------------------------------------------------------
        export_opts = ExportOptions()
        archive_bytes = self._client.export_viatar(viatar_id, export_opts)
        archive_path = raw_dir / "bodyloop-export.zip"
        archive_path.write_bytes(archive_bytes)

        # ------------------------------------------------------------------
        # 2. OpenAPI spec
        # ------------------------------------------------------------------
        openapi_data = self._client.inspect_api()
        openapi_path = raw_dir / "openapi.json"
        openapi_path.write_text(
            json.dumps(openapi_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # ------------------------------------------------------------------
        # 3. 3D models (download each GLB via its URL if available)
        # ------------------------------------------------------------------
        models = self._client.get_models(viatar_id)
        mesh_3d_path = raw_dir / "mesh_3d.glb"
        avatar_3d_path = raw_dir / "avatar_3d.glb"

        for model_info in models:
            if model_info.model_type == "mesh_3d" and model_info.url:
                mesh_bytes = self._client._get(model_info.url)  # noqa: SLF001
                if isinstance(mesh_bytes, bytes):
                    mesh_3d_path.write_bytes(mesh_bytes)
            elif model_info.model_type == "avatar_3d" and model_info.url:
                avatar_bytes = self._client._get(model_info.url)  # noqa: SLF001
                if isinstance(avatar_bytes, bytes):
                    avatar_3d_path.write_bytes(avatar_bytes)

        # ------------------------------------------------------------------
        # 4. All measurement data
        # ------------------------------------------------------------------
        viatar_data = self._client.get_viatar_data(viatar_id)

        def _write_json(filename: str, obj: object) -> Path:
            p = normalized_dir / filename
            if hasattr(obj, "model_dump"):
                payload = obj.model_dump(mode="json")
            elif isinstance(obj, list):
                payload = [
                    item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                    for item in obj
                ]
            else:
                payload = obj
            p.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return p

        proband_path = _write_json("proband.json", viatar_data.properties)
        markers_path = _write_json("markers.json", viatar_data.markers)
        axes_path = _write_json("axes.json", viatar_data.axes)
        distances_path = _write_json("distances.json", viatar_data.distances)
        heights_path = _write_json("heights.json", viatar_data.heights)
        crosssections_path = _write_json("crosssections.json", viatar_data.crosssections)
        crosssection_series_path = _write_json(
            "crosssection_series.json", viatar_data.crosssection_series
        )
        properties_path = _write_json("properties.json", viatar_data.properties)
        angles_path = _write_json("angles.json", viatar_data.angles)

        # ------------------------------------------------------------------
        # 5. Compute file hashes
        # ------------------------------------------------------------------
        tracked_files: dict[str, Path] = {
            "raw/bodyloop-export.zip": archive_path,
            "raw/openapi.json": openapi_path,
            "normalized/proband.json": proband_path,
            "normalized/markers.json": markers_path,
            "normalized/axes.json": axes_path,
            "normalized/distances.json": distances_path,
            "normalized/heights.json": heights_path,
            "normalized/crosssections.json": crosssections_path,
            "normalized/crosssection_series.json": crosssection_series_path,
            "normalized/properties.json": properties_path,
            "normalized/angles.json": angles_path,
        }
        # Add GLB files only if they were written
        if mesh_3d_path.exists():
            tracked_files["raw/mesh_3d.glb"] = mesh_3d_path
        if avatar_3d_path.exists():
            tracked_files["raw/avatar_3d.glb"] = avatar_3d_path

        file_hashes = {
            rel_path: compute_sha256(abs_path)
            for rel_path, abs_path in tracked_files.items()
        }

        # ------------------------------------------------------------------
        # 6. SDK version
        # ------------------------------------------------------------------
        try:
            sdk_version = importlib.metadata.version("bodyloop-anthropometrics")
        except importlib.metadata.PackageNotFoundError:
            sdk_version = "unknown"

        # ------------------------------------------------------------------
        # 7. Base URL (domain only, no credentials)
        # ------------------------------------------------------------------
        import urllib.parse  # stdlib; imported here to avoid top-level clutter

        parsed = urllib.parse.urlparse(self._client._base_url)  # noqa: SLF001
        base_url_domain = f"{parsed.scheme}://{parsed.netloc}"

        # ------------------------------------------------------------------
        # 8. Write manifest
        # ------------------------------------------------------------------
        manifest = {
            "schema_version": "1.0",
            "extraction_date": datetime.now(tz=timezone.utc).isoformat(),
            "sdk_version": sdk_version,
            "viatar_id": viatar_id,
            "subject_id": pseudo_id,  # pseudonymised
            "acquisition_date": acquisition_date,
            "base_url": base_url_domain,
            "file_hashes": file_hashes,
            "avatar_pose": "T-pose",
            "units": {
                "distances": "mm",
                "angles": "deg",
            },
            "coordinate_frame": "bodyloop_global",
        }

        manifest_path = acq_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return manifest_path
