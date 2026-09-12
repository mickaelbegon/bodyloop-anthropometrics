"""Unit tests for the BodyLoop API client and export utilities.

Tests use httpx.MockTransport or unittest.mock.patch — no real network
requests are made.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_TOKEN = "test_token_xyz"
_FAKE_BASE_URL = "https://bodyloop-test.local/api/v2"


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the required environment variables for the client."""
    monkeypatch.setenv("BODYLOOP_BASE_URL", _FAKE_BASE_URL)
    monkeypatch.setenv("BODYLOOP_API_TOKEN", _FAKE_TOKEN)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the required environment variables."""
    monkeypatch.delenv("BODYLOOP_BASE_URL", raising=False)
    monkeypatch.delenv("BODYLOOP_API_TOKEN", raising=False)


# ---------------------------------------------------------------------------
# Tests: BodyLoopClient construction
# ---------------------------------------------------------------------------


class TestClientConstruction:
    """Tests for client initialisation and environment variable handling."""

    def test_client_raises_if_base_url_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BodyLoopClient raises EnvironmentError when BODYLOOP_BASE_URL is absent."""
        monkeypatch.delenv("BODYLOOP_BASE_URL", raising=False)
        monkeypatch.setenv("BODYLOOP_API_TOKEN", _FAKE_TOKEN)

        from bodyloop_anthropometrics.api.client import BodyLoopClient

        with pytest.raises(EnvironmentError, match="BODYLOOP_BASE_URL"):
            BodyLoopClient()

    def test_client_raises_if_token_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BodyLoopClient raises EnvironmentError when BODYLOOP_API_TOKEN is absent."""
        monkeypatch.setenv("BODYLOOP_BASE_URL", _FAKE_BASE_URL)
        monkeypatch.delenv("BODYLOOP_API_TOKEN", raising=False)

        from bodyloop_anthropometrics.api.client import BodyLoopClient

        with pytest.raises(EnvironmentError, match="BODYLOOP_API_TOKEN"):
            BodyLoopClient()

    def test_client_raises_if_env_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BodyLoopClient raises EnvironmentError when both env vars are absent."""
        _clear_env(monkeypatch)

        from bodyloop_anthropometrics.api.client import BodyLoopClient

        with pytest.raises(EnvironmentError):
            BodyLoopClient()

    def test_client_initialises_with_valid_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BodyLoopClient initialises without error when env vars are set."""
        _set_env(monkeypatch)

        from bodyloop_anthropometrics.api.client import BodyLoopClient

        client = BodyLoopClient()
        client.close()


# ---------------------------------------------------------------------------
# Tests: Token safety
# ---------------------------------------------------------------------------


class TestTokenSafety:
    """Tests ensuring the API token never leaks into exception messages."""

    def test_token_not_in_error_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """API token must not appear in BodyLoopAPIError messages on 401."""
        _set_env(monkeypatch)

        from bodyloop_anthropometrics.api.client import BodyLoopAPIError, BodyLoopClient

        def _mock_send(request: httpx.Request, **kwargs: object) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Unauthorized"})

        transport = httpx.MockTransport(_mock_send)

        with patch("httpx.Client", autospec=True) as mock_cls:
            # Use a full MagicMock for the response: httpx.Response.is_success is a
            # read-only property and cannot be overridden on a real Response instance.
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_response.status_code = 401
            mock_response.json.return_value = {"detail": "Unauthorized"}

            instance = MagicMock()
            instance.get.return_value = mock_response
            mock_cls.return_value = instance

            client = BodyLoopClient()

            with pytest.raises(BodyLoopAPIError) as exc_info:
                client._get("/viatars/x/markers")

            error_str = str(exc_info.value)
            assert _FAKE_TOKEN not in error_str, (
                "API token must never appear in error messages"
            )

    def test_token_not_in_environment_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """EnvironmentError for missing token must not expose other token values."""
        monkeypatch.setenv("BODYLOOP_BASE_URL", _FAKE_BASE_URL)
        monkeypatch.delenv("BODYLOOP_API_TOKEN", raising=False)

        from bodyloop_anthropometrics.api.client import BodyLoopClient

        with pytest.raises(EnvironmentError) as exc_info:
            BodyLoopClient()

        # The error mentions the variable NAME, not its value
        assert "BODYLOOP_API_TOKEN" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tests: get_markers
# ---------------------------------------------------------------------------


class TestGetMarkers:
    """Tests for the get_markers endpoint."""

    def test_get_markers_returns_typed_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_markers returns a list of Marker3D when the API responds with valid JSON."""
        _set_env(monkeypatch)

        from bodyloop_anthropometrics.api.client import BodyLoopClient
        from bodyloop_anthropometrics.api.schemas import Marker3D

        markers_payload = [
            {"x": 10.0, "y": 20.0, "z": 30.0, "label": "LASI", "confidence": 0.98},
            {"x": -10.0, "y": 20.5, "z": 29.0, "label": "RASI", "confidence": None},
        ]

        with patch("httpx.Client", autospec=True) as mock_cls:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = markers_payload

            instance = MagicMock()
            instance.get.return_value = mock_response
            mock_cls.return_value = instance

            client = BodyLoopClient()
            result = client.get_markers("viatar-001")

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(m, Marker3D) for m in result)
        assert result[0].label == "LASI"
        assert result[0].x == pytest.approx(10.0)
        assert result[1].confidence is None

    def test_get_markers_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_markers returns an empty list when the API returns []."""
        _set_env(monkeypatch)

        from bodyloop_anthropometrics.api.client import BodyLoopClient

        with patch("httpx.Client", autospec=True) as mock_cls:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = []

            instance = MagicMock()
            instance.get.return_value = mock_response
            mock_cls.return_value = instance

            client = BodyLoopClient()
            result = client.get_markers("viatar-empty")

        assert result == []


# ---------------------------------------------------------------------------
# Tests: Properties validation
# ---------------------------------------------------------------------------


class TestPropertiesValidation:
    """Tests for Pydantic validation of Properties schema."""

    def test_get_properties_validates_mass_positive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Properties with mass_kg <= 0 raises a Pydantic ValidationError."""
        from pydantic import ValidationError

        from bodyloop_anthropometrics.api.schemas import Properties

        with pytest.raises(ValidationError, match="mass_kg"):
            Properties(mass_kg=-1.0, height_m=1.75)

    def test_get_properties_validates_height_positive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Properties with height_m <= 0 raises a Pydantic ValidationError."""
        from pydantic import ValidationError

        from bodyloop_anthropometrics.api.schemas import Properties

        with pytest.raises(ValidationError, match="height_m"):
            Properties(mass_kg=70.0, height_m=0.0)

    def test_get_properties_valid_values(self) -> None:
        """Properties with valid positive values parses without error."""
        from bodyloop_anthropometrics.api.schemas import Properties

        p = Properties(mass_kg=70.0, height_m=1.75, sex="male")
        assert p.mass_kg == pytest.approx(70.0)
        assert p.height_m == pytest.approx(1.75)
        assert p.sex == "male"

    def test_get_properties_none_values_allowed(self) -> None:
        """Properties with all-None values is valid."""
        from bodyloop_anthropometrics.api.schemas import Properties

        p = Properties()
        assert p.mass_kg is None
        assert p.height_m is None


# ---------------------------------------------------------------------------
# Tests: pseudonymize_subject
# ---------------------------------------------------------------------------


class TestPseudonymize:
    """Tests for the pseudonymize_subject function."""

    def test_pseudonymize_is_deterministic(self) -> None:
        """Same input always produces the same pseudonymous UUID."""
        from bodyloop_anthropometrics.api.export import pseudonymize_subject

        result1 = pseudonymize_subject("bodyloop-subject-42")
        result2 = pseudonymize_subject("bodyloop-subject-42")
        assert result1 == result2

    def test_pseudonymize_does_not_return_input(self) -> None:
        """The pseudonymous UUID is different from the original ID."""
        from bodyloop_anthropometrics.api.export import pseudonymize_subject

        original = "bodyloop-subject-42"
        result = pseudonymize_subject(original)
        assert result != original

    def test_pseudonymize_different_inputs_differ(self) -> None:
        """Different inputs yield different pseudonymous UUIDs."""
        from bodyloop_anthropometrics.api.export import pseudonymize_subject

        a = pseudonymize_subject("subject-A")
        b = pseudonymize_subject("subject-B")
        assert a != b

    def test_pseudonymize_returns_valid_uuid(self) -> None:
        """The return value is a valid UUID string."""
        import uuid

        from bodyloop_anthropometrics.api.export import pseudonymize_subject

        result = pseudonymize_subject("subject-test")
        # Should not raise
        uuid.UUID(result)


# ---------------------------------------------------------------------------
# Tests: compute_sha256
# ---------------------------------------------------------------------------


class TestComputeSha256:
    """Tests for the compute_sha256 utility."""

    def test_sha256_file(self, tmp_path: Path) -> None:
        """compute_sha256 returns the correct SHA-256 digest for a known file."""
        from bodyloop_anthropometrics.api.export import compute_sha256

        content = b"hello bodyloop"
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        result = compute_sha256(test_file)

        assert result == expected

    def test_sha256_empty_file(self, tmp_path: Path) -> None:
        """compute_sha256 handles empty files correctly."""
        from bodyloop_anthropometrics.api.export import compute_sha256

        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")

        expected = hashlib.sha256(b"").hexdigest()
        result = compute_sha256(test_file)
        assert result == expected

    def test_sha256_missing_file(self, tmp_path: Path) -> None:
        """compute_sha256 raises FileNotFoundError for nonexistent files."""
        from bodyloop_anthropometrics.api.export import compute_sha256

        with pytest.raises(FileNotFoundError):
            compute_sha256(tmp_path / "nonexistent.bin")


# ---------------------------------------------------------------------------
# Tests: manifest.json required keys
# ---------------------------------------------------------------------------

_REQUIRED_MANIFEST_KEYS = {
    "schema_version",
    "extraction_date",
    "sdk_version",
    "viatar_id",
    "subject_id",
    "acquisition_date",
    "base_url",
    "file_hashes",
    "avatar_pose",
    "units",
    "coordinate_frame",
}


class TestManifestKeys:
    """Tests verifying the structure of the manifest.json produced by ExportPipeline."""

    def test_manifest_has_required_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ExportPipeline.run writes a manifest.json containing all required fields."""
        _set_env(monkeypatch)

        from bodyloop_anthropometrics.api.client import BodyLoopClient
        from bodyloop_anthropometrics.api.export import ExportPipeline

        # Build a mock client that returns minimal valid payloads
        mock_client = MagicMock(spec=BodyLoopClient)
        mock_client._base_url = _FAKE_BASE_URL
        mock_client.export_viatar.return_value = b"PK\x03\x04fake_zip"
        mock_client.inspect_api.return_value = {"openapi": "3.0.0", "paths": {}}
        mock_client.get_models.return_value = []
        mock_client.get_viatar_data.return_value = MagicMock(
            properties=MagicMock(
                model_dump=lambda mode=None: {"mass_kg": 70.0, "height_m": 1.75}
            ),
            markers=[],
            axes=[],
            distances=[],
            heights=[],
            crosssections=[],
            crosssection_series=[],
            angles=[],
        )

        # Patch ViatarData sub-lists to have model_dump
        vd = mock_client.get_viatar_data.return_value
        for attr in ("markers", "axes", "distances", "heights",
                     "crosssections", "crosssection_series", "angles"):
            setattr(vd, attr, [])

        pipeline = ExportPipeline(client=mock_client)
        manifest_path = pipeline.run(
            viatar_id="viatar-test-001",
            output_dir=tmp_path,
            subject_id="bodyloop-sub-99",
            acquisition_date="2024-06-01",
        )

        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        missing_keys = _REQUIRED_MANIFEST_KEYS - manifest.keys()
        assert not missing_keys, f"Manifest is missing required keys: {missing_keys}"

    def test_manifest_units_structure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Manifest units field contains distances and angles keys."""
        _set_env(monkeypatch)

        from bodyloop_anthropometrics.api.client import BodyLoopClient
        from bodyloop_anthropometrics.api.export import ExportPipeline

        mock_client = MagicMock(spec=BodyLoopClient)
        mock_client._base_url = _FAKE_BASE_URL
        mock_client.export_viatar.return_value = b"PK\x03\x04fake"
        mock_client.inspect_api.return_value = {}
        mock_client.get_models.return_value = []
        vd = MagicMock()
        vd.properties = MagicMock(
            model_dump=lambda mode=None: {}
        )
        for attr in ("markers", "axes", "distances", "heights",
                     "crosssections", "crosssection_series", "angles"):
            setattr(vd, attr, [])
        mock_client.get_viatar_data.return_value = vd

        pipeline = ExportPipeline(client=mock_client)
        manifest_path = pipeline.run(
            viatar_id="viatar-test-002",
            output_dir=tmp_path,
            subject_id="sub-002",
            acquisition_date="2024-06-02",
        )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "distances" in manifest["units"]
        assert "angles" in manifest["units"]
        assert manifest["avatar_pose"] == "T-pose"
        assert manifest["coordinate_frame"] == "bodyloop_global"
        assert manifest["schema_version"] == "1.0"
