"""Command-line interface for bodyloop-anthropometrics.

All commands are implemented as stubs that raise :exc:`NotImplementedError`.
Each command signature is final; implementations will be added incrementally
per the project roadmap.

Usage
-----
.. code-block:: console

    bodyloop-anthro --help
    bodyloop-anthro inspect-api
    bodyloop-anthro export --viatar-id <ID> --output <PATH>
    bodyloop-anthro audit-rig <PATH>
    bodyloop-anthro build-yeadon <PATH>
    bodyloop-anthro build-hatze <PATH>
    bodyloop-anthro fit-body-model <PATH> --model smpl
    bodyloop-anthro transfer-weights <PATH>
    bodyloop-anthro compute-bsp <PATH>
    bodyloop-anthro export-biorbd <PATH>
    bodyloop-anthro run-all --viatar-id <ID> --output <PATH>
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option()
def cli() -> None:
    """BodyLoop Anthropometrics pipeline.

    Converts BodyLoop 3-D scans into Yeadon/Hatze anthropometric models
    and inertial parameters for biorbd and OpenSim.
    """


@cli.command("inspect-api")
def inspect_api() -> None:
    """Check connectivity and authentication with the BodyLoop REST API.

    Reads BODYLOOP_BASE_URL and BODYLOOP_API_TOKEN from the environment
    (or .env file) and prints API version, available presets, and
    current credit balance.

    Raises
    ------
    NotImplementedError
        Always — requires the API client from Agent C.
    """
    # TODO: instantiate BodyLoopClient and call health-check endpoint
    raise NotImplementedError(
        "inspect-api is not yet implemented.  "
        "Requires bodyloop_anthropometrics.api.client.BodyLoopClient."
    )


@cli.command("export")
@click.option(
    "--viatar-id",
    required=True,
    help="BodyLoop viatar (subject scan) identifier.",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output directory for exported data.",
)
@click.option(
    "--format",
    "fmt",
    default="normalized",
    show_default=True,
    type=click.Choice(["normalized", "raw", "glb"], case_sensitive=False),
    help="Export format.",
)
def export(viatar_id: str, output: str, fmt: str) -> None:
    """Download and export a viatar's scan data from the BodyLoop API.

    Writes the downloaded data to OUTPUT/normalized/, OUTPUT/raw/, or
    OUTPUT/<viatar_id>.glb depending on FORMAT.  A manifest.json is
    always written to OUTPUT/.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: call api.ExportPipeline.run(viatar_id, output, format=fmt)
    raise NotImplementedError(
        f"export command is not yet implemented for viatar_id={viatar_id!r}, "
        f"output={output!r}, format={fmt!r}."
    )


@cli.command("audit-rig")
@click.argument("path", type=click.Path(exists=True))
def audit_rig(path: str) -> None:
    """Audit the skeleton and skin-weight data in a GLB file.

    PATH is the filesystem path to a .glb file exported by BodyLoop or
    produced by the `export` command.  Prints a joint hierarchy summary,
    skin count, vertex count, and JOINTS/WEIGHTS accessor status.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: call rigging.gltf_audit.load_glb + audit_joint_hierarchy, print report
    raise NotImplementedError(
        f"audit-rig is not yet implemented for path={path!r}."
    )


@cli.command("build-yeadon")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--config",
    default=None,
    type=click.Path(),
    help="Path to custom bodyloop_to_yeadon.yaml.  Uses bundled config if omitted.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output directory.  Defaults to PATH parent directory.",
)
def build_yeadon(path: str, config: str | None, output: str | None) -> None:
    """Build a Yeadon (1990) inertia model from BodyLoop normalised data.

    PATH is a normalised JSON file (output of the `export` command).
    Produces a Yeadon-format measurement YAML and a BSP JSON file.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: load normalised JSON, call anthropometry.yeadon_adapter pipeline
    raise NotImplementedError(
        f"build-yeadon is not yet implemented for path={path!r}."
    )


@cli.command("build-hatze")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--config",
    default=None,
    type=click.Path(),
    help="Path to custom bodyloop_to_hatze.yaml.  Uses bundled config if omitted.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output directory.  Defaults to PATH parent directory.",
)
def build_hatze(path: str, config: str | None, output: str | None) -> None:
    """Build Hatze (1979) segment parameters from BodyLoop normalised data.

    PATH is a normalised JSON file.  Produces a per-segment BSP JSON file.

    Warning
    -------
    Hatze equation implementations are NOT yet validated.
    Do not use output for published research without scientific review.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: load normalised JSON, call anthropometry.hatze_adapter pipeline
    raise NotImplementedError(
        f"build-hatze is not yet implemented for path={path!r}."
    )


@cli.command("fit-body-model")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--model",
    default="smpl",
    show_default=True,
    type=click.Choice(["smpl", "smplx", "skel"], case_sensitive=False),
    help="Parametric body model to fit.",
)
@click.option(
    "--device",
    default="cpu",
    show_default=True,
    help="Torch device string, e.g. 'cpu' or 'cuda:0'.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output directory.",
)
def fit_body_model(path: str, model: str, device: str, output: str | None) -> None:
    """Register a BodyLoop scan to a parametric body model via BodiesReg.

    PATH is a GLB file.  Writes a registration result (.npz) and a
    registered mesh (.glb) to the output directory.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: call rigging.bodiesreg_adapter.register_to_template
    raise NotImplementedError(
        f"fit-body-model is not yet implemented for path={path!r}, model={model!r}."
    )


@cli.command("transfer-weights")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--method",
    default="barycentric",
    show_default=True,
    type=click.Choice(["nearest", "barycentric"], case_sensitive=False),
    help="Weight-transfer algorithm.",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output directory.",
)
def transfer_weights(path: str, method: str, output: str | None) -> None:
    """Transfer skin weights from a template to the BodyLoop scan topology.

    PATH is a GLB file that has been registered via `fit-body-model`.
    Produces a new GLB with JOINTS_0/WEIGHTS_0 accessors.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: load GLB, call rigging.skin_weight_transfer pipeline
    raise NotImplementedError(
        f"transfer-weights is not yet implemented for path={path!r}, method={method!r}."
    )


@cli.command("compute-bsp")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output directory.",
)
def compute_bsp(path: str, output: str | None) -> None:
    """Compute body-segment parameters directly from the 3-D mesh.

    PATH is a segmented GLB file.  Produces a bsp.json file containing
    mass, centroid, and inertia tensor for each segment.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: call anthropometry.direct_mesh_bsp.compute_all_bsp pipeline
    raise NotImplementedError(
        f"compute-bsp is not yet implemented for path={path!r}."
    )


@cli.command("export-biorbd")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output directory.",
)
@click.option(
    "--model-name",
    default="BodyLoop_subject",
    show_default=True,
    help="Model name written in the .bioMod header.",
)
def export_biorbd(path: str, output: str | None, model_name: str) -> None:
    """Export BSP data as a biorbd-compatible .bioMod file.

    PATH is a bsp.json file produced by `compute-bsp`.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: load bsp.json, call biomechanics.biorbd_export.write_biomod
    raise NotImplementedError(
        f"export-biorbd is not yet implemented for path={path!r}."
    )


@cli.command("visualize-measurements")
@click.argument("acquisition_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--model",
    type=click.Choice(["yeadon", "hatze"]),
    default="yeadon",
    show_default=True,
    help="Anthropometric model whose measurements to display.",
)
@click.option(
    "--port",
    type=int,
    default=8051,
    show_default=True,
    help="Local port for the Dash server.",
)
def visualize_measurements(acquisition_dir: Path, model: str, port: int) -> None:
    """Launch interactive 3D viewer for measurement validation.

    Opens a browser-based viewer showing the body mesh with annotated
    measurement lines. Approve or reject each measurement flagged for
    manual validation. Results are auto-saved to normalized/.

    ACQUISITION_DIR is the acquisition root directory, expected to contain
    raw/mesh_3d.glb and normalized/<model>_measurements.json.
    """
    from bodyloop_anthropometrics.visualization.measurement_viewer import run_viewer

    run_viewer(acquisition_dir=acquisition_dir, model=model, port=port)  # type: ignore[arg-type]


@cli.command("run-all")
@click.option(
    "--viatar-id",
    required=True,
    help="BodyLoop viatar (subject scan) identifier.",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Root output directory for all pipeline artefacts.",
)
@click.option(
    "--model",
    default="smpl",
    show_default=True,
    type=click.Choice(["smpl", "smplx", "skel"], case_sensitive=False),
    help="Parametric model for body fitting.",
)
@click.option(
    "--skip-biorbd",
    is_flag=True,
    default=False,
    help="Skip biorbd export step.",
)
@click.option(
    "--skip-opensim",
    is_flag=True,
    default=False,
    help="Skip OpenSim export step.",
)
def run_all(
    viatar_id: str,
    output: str,
    model: str,
    skip_biorbd: bool,
    skip_opensim: bool,
) -> None:
    """Run the full pipeline from API download to biomechanics export.

    Steps executed in order:

    1. ``export``       — download normalised data and GLB from BodyLoop API.
    2. ``audit-rig``    — validate GLB skeleton structure.
    3. ``fit-body-model`` — register to parametric model.
    4. ``transfer-weights`` — transfer skin weights to scan topology.
    5. ``build-yeadon`` — extract Yeadon measurements and BSP.
    6. ``build-hatze``  — extract Hatze measurements and BSP.
    7. ``compute-bsp``  — direct mesh BSP.
    8. ``export-biorbd`` — write .bioMod file (unless ``--skip-biorbd``).
    9. OpenSim export  — write .osim file (unless ``--skip-opensim``).

    A manifest.json recording all versions and assumptions is written to OUTPUT/.

    Raises
    ------
    NotImplementedError
        Always.
    """
    # TODO: orchestrate all pipeline steps in sequence, write manifest.json
    raise NotImplementedError(
        f"run-all is not yet implemented for viatar_id={viatar_id!r}, "
        f"output={output!r}."
    )
