"""Integration (smoke) tests: Click CLI commands invoke without crashing.

Uses Click's CliRunner so no subprocess is spawned and no filesystem outside
tmp_path is touched.  All commands are expected to either succeed or fail
with a predictable non-zero exit code; no command should silently corrupt
state or raise an unhandled exception.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# click is a project dependency but may not be installed in all test
# environments (e.g. a minimal CI image).  Skip the whole module gracefully
# rather than letting an ImportError fail the collection step.
pytest.importorskip("click", reason="click not installed in this environment")

from click.testing import CliRunner  # noqa: E402

from bodyloop_anthropometrics.cli import cli  # noqa: E402


@pytest.mark.integration
class TestCLISmoke:
    """Integration: CLI commands invoke without crashing (smoke tests)."""

    def test_cli_help(self) -> None:
        """CLI --help prints usage and exits 0."""
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0, (
            f"Expected exit_code=0 for --help, got {result.exit_code}; "
            f"output: {result.output}"
        )
        assert "Usage" in result.output or "usage" in result.output.lower(), (
            "Expected usage information in --help output"
        )

    def test_inspect_api_missing_env(self) -> None:
        """Verify inspect-api fails gracefully with no environment variables set.

        The command raises NotImplementedError (not yet implemented); the
        CliRunner catches it and returns exit_code != 0.
        """
        result = CliRunner(mix_stderr=False).invoke(
            cli, ["inspect-api"], env={}
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit code for inspect-api without env vars, "
            f"got {result.exit_code}"
        )

    def test_audit_rig_missing_file(self, tmp_path: Path) -> None:
        """Verify audit-rig with nonexistent file exits non-zero.

        Click's ``exists=True`` validation causes a usage error (exit_code=2)
        before the command body executes.
        """
        nonexistent = tmp_path / "nonexistent.glb"
        result = CliRunner().invoke(cli, ["audit-rig", str(nonexistent)])
        assert result.exit_code != 0, (
            f"Expected non-zero exit code for audit-rig with missing file, "
            f"got {result.exit_code}"
        )

    def test_visualize_measurements_missing_file(self, tmp_path: Path) -> None:
        """Verify visualize-measurements with missing acquisition_dir exits non-zero.

        Click's ``exists=True`` validation causes a usage error (exit_code=2)
        before the command body executes.
        """
        missing_dir = tmp_path / "missing_acquisition_dir"
        result = CliRunner().invoke(
            cli, ["visualize-measurements", str(missing_dir)]
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit code for visualize-measurements with "
            f"missing dir, got {result.exit_code}"
        )

    def test_build_yeadon_no_env(self, tmp_path: Path) -> None:
        """Verify build-yeadon fails gracefully with a non-existent path argument.

        The ``path`` argument has ``exists=True``; passing a non-existent path
        causes Click to exit with code 2 before the command body runs.
        """
        nonexistent_path = tmp_path / "vid-001.json"
        result = CliRunner(mix_stderr=False).invoke(
            cli, ["build-yeadon", str(nonexistent_path)], env={}
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit code for build-yeadon with missing file, "
            f"got {result.exit_code}"
        )
