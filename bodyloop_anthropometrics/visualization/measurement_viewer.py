"""Interactive 3D viewer for anthropometric measurement validation.

Opens a Dash application in the browser showing the 3D body mesh with
annotated measurement lines, landmarks, and cross-sections. Each measurement
flagged as manual_validation_required can be approved or rejected, with the
result written back to the normalized acquisition directory.

Usage
-----
From CLI: bodyloop-anthro visualize-measurements PATH/acquisition --model yeadon
From Python::

    from bodyloop_anthropometrics.visualization.measurement_viewer import run_viewer
    run_viewer(acquisition_dir=Path("subject/2024-06-01"), model="yeadon")

Parameters saved
----------------
On Approve/Reject, updates the MeasurementSet JSON and writes::

    normalized/yeadon_measurements_validated.json

Notes
-----
Color coding by source type:

  direct       -> green (#2ecc71)
  calculated   -> blue (#3498db)
  interpolated -> orange (#f39c12)
  external     -> purple (#9b59b6)
  manual       -> red (#e74c3c)

Color coding by validation_status (border/outline):

  pending  -> grey dashed
  approved -> solid green
  rejected -> solid red

References
----------
Dash documentation: https://dash.plotly.com/
Plotly 3D mesh: https://plotly.com/python/3d-mesh/
"""

from __future__ import annotations

import json
import datetime
import logging
import webbrowser
from pathlib import Path
from typing import Any, Literal

import numpy as np

from bodyloop_anthropometrics.anthropometry.measurement_mapping import (
    Measurement,
    MeasurementSet,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports with graceful fallbacks
# ---------------------------------------------------------------------------

try:
    import trimesh as _trimesh

    _TRIMESH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _trimesh = None  # type: ignore[assignment]
    _TRIMESH_AVAILABLE = False

try:
    import plotly.graph_objects as go

    _PLOTLY_AVAILABLE = True
except ImportError:  # pragma: no cover
    go = None  # type: ignore[assignment]
    _PLOTLY_AVAILABLE = False

try:
    from dash import Dash, dcc, html, Input, Output, State, callback_context, no_update

    _DASH_AVAILABLE = True
except ImportError:  # pragma: no cover
    Dash = None  # type: ignore[assignment]
    _DASH_AVAILABLE = False

try:
    import dash_bootstrap_components as dbc

    _DBC_AVAILABLE = True
except ImportError:
    dbc = None  # type: ignore[assignment]
    _DBC_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_COLORS: dict[str, str] = {
    "direct": "#2ecc71",
    "calculated": "#3498db",
    "interpolated": "#f39c12",
    "external": "#9b59b6",
    "manual": "#e74c3c",
}

STATUS_SYMBOLS: dict[str, str] = {
    "pending": "⚠",   # ⚠
    "approved": "✓",  # ✓
    "rejected": "✗",  # ✗
}

STATUS_COLORS: dict[str, str] = {
    "pending": "#95a5a6",
    "approved": "#27ae60",
    "rejected": "#c0392b",
}


# ---------------------------------------------------------------------------
# Pure helper functions (testable without Dash)
# ---------------------------------------------------------------------------


def load_mesh(acquisition_dir: Path) -> Any:
    """Load the body mesh from an acquisition directory.

    Parameters
    ----------
    acquisition_dir : Path
        Acquisition directory containing raw/mesh_3d.glb.

    Returns
    -------
    trimesh.Trimesh or None
        Loaded mesh, or None if not found or trimesh unavailable.

    Notes
    -----
    Returns None silently when the GLB file is absent so the viewer can
    still operate in landmark-only mode.
    """
    if not _TRIMESH_AVAILABLE:
        logger.warning("trimesh is not installed; running without 3D mesh.")
        return None

    glb_path = acquisition_dir / "raw" / "mesh_3d.glb"
    if not glb_path.is_file():
        logger.info("No mesh found at %s; running in landmark-only mode.", glb_path)
        return None

    try:
        scene = _trimesh.load(str(glb_path), force="scene")
        # Merge all scene geometries into a single mesh
        if hasattr(scene, "dump"):
            meshes = scene.dump(concatenate=True)
            return meshes
        if hasattr(scene, "geometry") and scene.geometry:
            geometries = list(scene.geometry.values())
            if len(geometries) == 1:
                return geometries[0]
            return _trimesh.util.concatenate(geometries)
        return scene
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load mesh from %s: %s", glb_path, exc)
        return None


def load_measurement_set(
    acquisition_dir: Path,
    model: Literal["yeadon", "hatze"],
) -> MeasurementSet | None:
    """Load a MeasurementSet from the normalized acquisition directory.

    Parameters
    ----------
    acquisition_dir : Path
        Root acquisition directory.
    model : {"yeadon", "hatze"}
        Which model's measurements to load.

    Returns
    -------
    MeasurementSet or None
        Loaded measurement set, or None if the file does not exist.

    Notes
    -----
    Prefers ``<model>_measurements_validated.json`` over
    ``<model>_measurements.json`` so that a previous session's validation
    work is resumed automatically.
    """
    normalized_dir = acquisition_dir / "normalized"
    validated_path = normalized_dir / f"{model}_measurements_validated.json"
    original_path = normalized_dir / f"{model}_measurements.json"

    for candidate in (validated_path, original_path):
        if candidate.is_file():
            try:
                with candidate.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                return MeasurementSet.model_validate(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse %s: %s", candidate, exc)

    logger.warning(
        "No measurement file found under %s for model=%s.", normalized_dir, model
    )
    return None


def save_measurement_set(
    acquisition_dir: Path,
    measurement_set: MeasurementSet,
    model: Literal["yeadon", "hatze"],
) -> Path:
    """Save a validated MeasurementSet to disk.

    Parameters
    ----------
    acquisition_dir : Path
        Root acquisition directory.
    measurement_set : MeasurementSet
        Measurement set to persist.
    model : {"yeadon", "hatze"}
        Target model name, used to build the file name.

    Returns
    -------
    Path
        Absolute path to the saved file.

    Notes
    -----
    Saves to ``normalized/<model>_measurements_validated.json``.
    Never overwrites the original extraction output
    (``<model>_measurements.json``).
    """
    normalized_dir = acquisition_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    out_path = normalized_dir / f"{model}_measurements_validated.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(measurement_set.model_dump(), fh, indent=2, ensure_ascii=False)
    logger.info("Saved validated measurements to %s", out_path)
    return out_path


def build_mesh_trace(mesh: Any) -> Any:
    """Build a semi-transparent Plotly 3D mesh trace.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Body mesh to render.

    Returns
    -------
    plotly.graph_objects.Mesh3d
        Mesh with opacity=0.3, grey colorscale, and ambient lighting.

    Notes
    -----
    Returns ``None`` when Plotly is not installed.
    """
    if go is None or mesh is None:
        return None

    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=int)

    return go.Mesh3d(
        x=vertices[:, 0],
        y=vertices[:, 1],
        z=vertices[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        opacity=0.3,
        color="#aaaaaa",
        lighting={"ambient": 0.8, "diffuse": 0.5, "specular": 0.1},
        hoverinfo="skip",
        name="Body mesh",
        showlegend=False,
    )


def build_measurement_traces(
    measurement_set: MeasurementSet,
    mapping: dict[str, Any],
    selected_key: str | None = None,
) -> list[Any]:
    """Build Plotly traces for all measurements.

    Parameters
    ----------
    measurement_set : MeasurementSet
        Measurement data and provenance.
    mapping : dict
        Loaded bodyloop_to_yeadon.yaml or bodyloop_to_hatze.yaml as a plain
        dictionary, keyed by measurement key.
    selected_key : str or None
        If set, this measurement is highlighted with a larger marker.

    Returns
    -------
    list of plotly.graph_objects trace objects
        Scatter3d traces for landmarks (spheres) and dummy annotation traces
        for measurements without a 3D anchor.

    Notes
    -----
    Measurements without a 3D anchor in ``mapping[key].bodyloop_path`` are
    shown as text annotations only — no 3D position is available.  Actual
    3D coordinates would require resolved landmark positions from the
    normalized export, which are not part of this dataset for most keys; the
    viewer therefore places all present measurements at placeholder positions
    on a unit sphere so the colour-coded legend is always visible.
    """
    if go is None:
        return []

    traces: list[Any] = []

    # Separate keys into those with and without positions
    xs, ys, zs = [], [], []
    colors, texts, sizes = [], [], []

    for i, (key, meas) in enumerate(measurement_set.measurements.items()):
        # Placeholder 3D position: distribute on a circle in XZ plane
        angle = 2.0 * np.pi * i / max(len(measurement_set.measurements), 1)
        radius = 0.9
        x = radius * np.cos(angle)
        y = float(meas.value) if abs(meas.value) < 5.0 else 0.0
        z = radius * np.sin(angle)

        xs.append(x)
        ys.append(y)
        zs.append(z)
        colors.append(SOURCE_COLORS.get(meas.source, "#cccccc"))
        symbol = STATUS_SYMBOLS.get(meas.validation_status, "?")
        texts.append(
            f"{key} {symbol}<br>"
            f"val={meas.value:.4f} {meas.unit}<br>"
            f"source={meas.source}<br>"
            f"confidence={meas.confidence:.2f}"
        )
        sizes.append(16 if key == selected_key else 8)

    if xs:
        traces.append(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers",
                marker={
                    "size": sizes,
                    "color": colors,
                    "symbol": "circle",
                    "line": {"width": 1, "color": "#333333"},
                },
                text=texts,
                hoverinfo="text",
                name="Measurements",
            )
        )

    return traces


def _build_measurement_list_items(
    measurement_set: MeasurementSet,
    status_filter: str = "all",
    selected_key: str | None = None,
) -> list[Any]:
    """Build HTML list items for the measurement panel.

    Parameters
    ----------
    measurement_set : MeasurementSet
        Data source.
    status_filter : str
        One of ``"all"``, ``"pending"``, ``"approved"``, ``"rejected"``.
    selected_key : str or None
        Highlighted key.

    Returns
    -------
    list of dash html components
        One item per measurement (or missing key) after filtering.
    """
    if html is None:
        return []

    items = []
    for key, meas in measurement_set.measurements.items():
        if status_filter != "all" and meas.validation_status != status_filter:
            continue
        symbol = STATUS_SYMBOLS.get(meas.validation_status, "?")
        color = STATUS_COLORS.get(meas.validation_status, "#aaaaaa")
        is_selected = key == selected_key
        bg = "#2c3e50" if is_selected else "transparent"
        items.append(
            html.Div(
                f"{key}  [{meas.validation_status.upper()}] {symbol}",
                id={"type": "meas-item", "key": key},
                n_clicks=0,
                style={
                    "padding": "4px 8px",
                    "cursor": "pointer",
                    "borderLeft": f"4px solid {color}",
                    "marginBottom": "2px",
                    "backgroundColor": bg,
                    "color": "#ecf0f1",
                    "fontFamily": "monospace",
                    "fontSize": "12px",
                    "borderRadius": "2px",
                },
            )
        )
    return items


def _build_detail_panel(
    meas: Measurement | None,
    key: str | None,
    mapping: dict[str, Any],
) -> list[Any]:
    """Build the right-panel detail section for a selected measurement.

    Parameters
    ----------
    meas : Measurement or None
        Selected measurement, or None when nothing is selected.
    key : str or None
        Measurement key.
    mapping : dict
        Full mapping config for contextual info.

    Returns
    -------
    list of dash html components
    """
    if html is None:
        return []
    if meas is None or key is None:
        return [html.P("Select a measurement to see details.", style={"color": "#7f8c8d"})]

    entry = mapping.get(key, {})
    anat_def = entry.get("anatomical_definition", "-")

    return [
        html.Table(
            [
                html.Tr([html.Td("Key:", style={"fontWeight": "bold"}), html.Td(key)]),
                html.Tr([html.Td("Value:"), html.Td(f"{meas.value:.4f} {meas.unit}")]),
                html.Tr([html.Td("Source:"), html.Td(meas.source)]),
                html.Tr([html.Td("Confidence:"), html.Td(f"{meas.confidence:.2f}")]),
                html.Tr(
                    [
                        html.Td("BodyLoop path:"),
                        html.Td(
                            meas.bodyloop_path or "-",
                            style={"fontFamily": "monospace", "fontSize": "11px"},
                        ),
                    ]
                ),
                html.Tr([html.Td("Anatomical def:"), html.Td(anat_def, style={"fontSize": "11px"})]),
                html.Tr([html.Td("Status:"), html.Td(meas.validation_status)]),
                html.Tr([html.Td("Validated by:"), html.Td(meas.validated_by or "-")]),
                html.Tr([html.Td("Validated date:"), html.Td(meas.validated_date or "-")]),
                html.Tr([html.Td("Val. notes:"), html.Td(meas.validation_notes or "-")]),
            ],
            style={"fontSize": "12px", "borderCollapse": "collapse", "width": "100%"},
        )
    ]


# ---------------------------------------------------------------------------
# Dash application builder
# ---------------------------------------------------------------------------


def _make_app(
    acquisition_dir: Path,
    measurement_set: MeasurementSet,
    mesh: Any,
    model: str,
    mapping: dict[str, Any],
) -> Any:
    """Create and configure the Dash application.

    Parameters
    ----------
    acquisition_dir : Path
        Used for auto-saving.
    measurement_set : MeasurementSet
        Initial measurement data.
    mesh : trimesh.Trimesh or None
        Body mesh, or None if unavailable.
    model : str
        ``"yeadon"`` or ``"hatze"``.
    mapping : dict
        Full measurement mapping config.

    Returns
    -------
    dash.Dash
        Configured application (not yet running).
    """
    if Dash is None:
        raise ImportError(
            "Dash is required for the visualization viewer. "
            "Install it with: pip install 'bodyloop-anthropometrics[viz]'"
        )

    external_stylesheets = []
    if _DBC_AVAILABLE:
        external_stylesheets = [dbc.themes.DARKLY]

    app = Dash(
        __name__,
        external_stylesheets=external_stylesheets,
        suppress_callback_exceptions=True,
    )

    # ---- mutable state container (Dash Store alternative) ----
    # We keep a mutable dict in the closure so callbacks can update it.
    state: dict[str, Any] = {
        "measurement_set": measurement_set,
        "selected_key": None,
    }

    # ---- coverage summary ----
    report = measurement_set.coverage_report()

    # ---- initial 3D figure ----
    def make_figure(sel_key: str | None = None) -> Any:
        traces = []
        mesh_trace = build_mesh_trace(mesh)
        if mesh_trace is not None:
            traces.append(mesh_trace)

        if not measurement_set.measurements:
            placeholder_text = "No mesh available — showing landmarks only"
            traces.append(
                go.Scatter3d(
                    x=[0], y=[0], z=[0],
                    mode="text",
                    text=[placeholder_text],
                    hoverinfo="skip",
                    name="",
                )
            )
        else:
            traces.extend(build_measurement_traces(measurement_set, mapping, sel_key))

        fig = go.Figure(data=traces)
        fig.update_layout(
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
            scene={
                "bgcolor": "#1a1a2e",
                "xaxis": {"showgrid": False, "showticklabels": False},
                "yaxis": {"showgrid": False, "showticklabels": False},
                "zaxis": {"showgrid": False, "showticklabels": False},
                "aspectmode": "data",
            },
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            uirevision="constant",
        )
        if mesh is None:
            fig.add_annotation(
                text="No mesh available — showing landmarks only",
                xref="paper", yref="paper",
                x=0.5, y=0.02,
                showarrow=False,
                font={"color": "#e67e22", "size": 12},
            )
        return fig

    # ---- layout ----
    left_panel = html.Div(
        [
            dcc.Graph(
                id="viewer-3d",
                figure=make_figure(),
                style={"height": "100%"},
                config={"displayModeBar": True},
            )
        ],
        style={"flex": "1", "minHeight": "0", "backgroundColor": "#1a1a2e"},
    )

    status_options = [
        {"label": "All", "value": "all"},
        {"label": "Pending ⚠", "value": "pending"},
        {"label": "Approved ✓", "value": "approved"},
        {"label": "Rejected ✗", "value": "rejected"},
    ]

    right_panel = html.Div(
        [
            # Filters
            html.Div(
                [
                    html.Label("Model", style={"color": "#bdc3c7", "fontSize": "12px"}),
                    html.Div(model.upper(), style={"color": "#ecf0f1", "fontWeight": "bold"}),
                    html.Label(
                        "Status filter", style={"color": "#bdc3c7", "fontSize": "12px", "marginTop": "8px"}
                    ),
                    dcc.Dropdown(
                        id="status-filter",
                        options=status_options,
                        value="all",
                        clearable=False,
                        style={"fontSize": "12px"},
                    ),
                ],
                style={"padding": "8px", "borderBottom": "1px solid #34495e"},
            ),
            # Measurement list
            html.Div(
                id="measurement-list",
                children=_build_measurement_list_items(measurement_set),
                style={
                    "overflowY": "auto",
                    "flex": "1",
                    "minHeight": "0",
                    "padding": "4px",
                },
            ),
            # Detail panel
            html.Div(
                id="detail-panel",
                children=_build_detail_panel(None, None, mapping),
                style={
                    "padding": "8px",
                    "borderTop": "1px solid #34495e",
                    "fontSize": "12px",
                    "color": "#ecf0f1",
                    "maxHeight": "280px",
                    "overflowY": "auto",
                },
            ),
            # Validator form
            html.Div(
                [
                    html.Hr(style={"borderColor": "#34495e"}),
                    html.Label("Validator:", style={"color": "#bdc3c7", "fontSize": "12px"}),
                    dcc.Input(
                        id="validator-input",
                        placeholder="Initials / ID",
                        type="text",
                        debounce=True,
                        style={"width": "100%", "marginBottom": "4px", "fontSize": "12px"},
                    ),
                    html.Label("Notes:", style={"color": "#bdc3c7", "fontSize": "12px"}),
                    dcc.Textarea(
                        id="notes-input",
                        placeholder="Validation notes (required for reject)…",
                        style={"width": "100%", "height": "56px", "fontSize": "12px", "marginBottom": "6px"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "✓ Approve",
                                id="approve-btn",
                                n_clicks=0,
                                style={
                                    "backgroundColor": "#27ae60",
                                    "color": "white",
                                    "border": "none",
                                    "padding": "6px 12px",
                                    "cursor": "pointer",
                                    "borderRadius": "4px",
                                    "marginRight": "6px",
                                    "flex": "1",
                                },
                            ),
                            html.Button(
                                "✗ Reject",
                                id="reject-btn",
                                n_clicks=0,
                                style={
                                    "backgroundColor": "#c0392b",
                                    "color": "white",
                                    "border": "none",
                                    "padding": "6px 12px",
                                    "cursor": "pointer",
                                    "borderRadius": "4px",
                                    "flex": "1",
                                },
                            ),
                        ],
                        style={"display": "flex", "gap": "4px"},
                    ),
                ],
                style={"padding": "8px", "borderTop": "1px solid #34495e"},
            ),
            # Coverage summary
            html.Div(
                id="coverage-summary",
                children=[
                    html.Hr(style={"borderColor": "#34495e"}),
                    html.P(
                        f"Coverage: {report['present']}/{report['total']}",
                        style={"color": "#bdc3c7", "fontSize": "12px", "margin": "2px 0"},
                    ),
                    html.P(
                        f"Validated: {report['approved']}/{report['manual_required']} required",
                        style={"color": "#bdc3c7", "fontSize": "12px", "margin": "2px 0"},
                    ),
                    html.P(
                        f"Pending: {report['pending_validation']}",
                        style={"color": "#e67e22", "fontSize": "12px", "margin": "2px 0"},
                    ),
                ],
                style={"padding": "8px"},
            ),
            # Status message
            html.Div(id="status-msg", style={"padding": "4px 8px", "fontSize": "11px", "color": "#27ae60"}),
            # Hidden stores
            dcc.Store(id="selected-key-store", data=None),
        ],
        style={
            "width": "300px",
            "display": "flex",
            "flexDirection": "column",
            "backgroundColor": "#1e2a3a",
            "color": "#ecf0f1",
            "overflowY": "hidden",
        },
    )

    app.layout = html.Div(
        [
            html.Div(
                [
                    html.H4(
                        f"BodyLoop Measurement Validator — {model.upper()} — {measurement_set.subject_id}",
                        style={"color": "#ecf0f1", "margin": "8px 16px", "fontSize": "16px"},
                    )
                ],
                style={"backgroundColor": "#16213e", "borderBottom": "1px solid #34495e"},
            ),
            html.Div(
                [left_panel, right_panel],
                style={"display": "flex", "flex": "1", "minHeight": "0", "overflow": "hidden"},
            ),
        ],
        style={
            "display": "flex",
            "flexDirection": "column",
            "height": "100vh",
            "backgroundColor": "#1a1a2e",
            "fontFamily": "system-ui, sans-serif",
        },
    )

    # ---- Callbacks ----

    @app.callback(
        Output("selected-key-store", "data"),
        Input({"type": "meas-item", "key": "__ALL__"}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _select_measurement(_n_clicks: Any) -> Any:
        """Update selected key when a list item is clicked."""
        ctx = callback_context
        if not ctx.triggered:
            return no_update
        triggered_id = ctx.triggered[0]["prop_id"]
        # Extract key from the pattern-match id JSON
        try:
            import json as _json

            prop_id_str = triggered_id.rsplit(".", 1)[0]
            id_dict = _json.loads(prop_id_str)
            key = id_dict.get("key")
        except Exception:  # noqa: BLE001
            return no_update
        state["selected_key"] = key
        return key

    @app.callback(
        Output("viewer-3d", "figure"),
        Input("selected-key-store", "data"),
        prevent_initial_call=True,
    )
    def update_3d_figure(selected_key: str | None) -> Any:
        """Highlight the selected measurement in the 3D viewer.

        Parameters
        ----------
        selected_key : str or None
            The measurement key that was selected.

        Returns
        -------
        plotly.graph_objects.Figure
        """
        return make_figure(selected_key)

    @app.callback(
        Output("detail-panel", "children"),
        Input("selected-key-store", "data"),
    )
    def update_panel(selected_key: str | None) -> list[Any]:
        """Display details of the selected measurement.

        Parameters
        ----------
        selected_key : str or None

        Returns
        -------
        list of dash components
        """
        meas = state["measurement_set"].measurements.get(selected_key) if selected_key else None
        return _build_detail_panel(meas, selected_key, mapping)

    @app.callback(
        Output("measurement-list", "children"),
        Input("status-filter", "value"),
        Input("selected-key-store", "data"),
    )
    def filter_list(status_filter: str, selected_key: str | None) -> list[Any]:
        """Filter the measurement list by validation status.

        Parameters
        ----------
        status_filter : str
            One of ``"all"``, ``"pending"``, ``"approved"``, ``"rejected"``.
        selected_key : str or None

        Returns
        -------
        list of dash components
        """
        return _build_measurement_list_items(
            state["measurement_set"], status_filter, selected_key
        )

    def _do_validation(
        validator: str,
        notes: str,
        new_status: Literal["approved", "rejected"],
    ) -> str:
        """Apply an approve/reject action to the currently selected measurement.

        Parameters
        ----------
        validator : str
            Validator identifier (initials or pseudonym).
        notes : str
            Free-text notes from the form.
        new_status : {"approved", "rejected"}
            Outcome to record.

        Returns
        -------
        str
            Human-readable status message for the UI banner.
        """
        key = state["selected_key"]
        ms = state["measurement_set"]
        if key is None or key not in ms.measurements:
            return "No measurement selected."
        if not validator or not validator.strip():
            return "Validator field is required."
        if new_status == "rejected" and not (notes and notes.strip()):
            # Log warning but do not block — store a note in validation_notes
            logger.warning("Reject without notes for key %s — auto-filling a warning.", key)
            notes = "[WARNING] No notes provided at rejection time."

        today = datetime.date.today().isoformat()
        old_meas = ms.measurements[key]
        new_meas = Measurement(
            value=old_meas.value,
            unit=old_meas.unit,
            frame=old_meas.frame,
            source=old_meas.source,
            confidence=old_meas.confidence,
            bodyloop_path=old_meas.bodyloop_path,
            notes=old_meas.notes,
            manual_validation_required=old_meas.manual_validation_required,
            validation_status=new_status,
            validated_by=validator.strip(),
            validated_date=today,
            validation_notes=notes.strip() if notes else None,
        )
        updated_measurements = dict(ms.measurements)
        updated_measurements[key] = new_meas
        state["measurement_set"] = MeasurementSet(
            subject_id=ms.subject_id,
            acquisition_date=ms.acquisition_date,
            measurements=updated_measurements,
            missing=ms.missing,
        )
        save_measurement_set(acquisition_dir, state["measurement_set"], model)  # type: ignore[arg-type]
        symbol = STATUS_SYMBOLS[new_status]
        return f"{symbol} {key} → {new_status} (saved)"

    @app.callback(
        Output("status-msg", "children"),
        Output("coverage-summary", "children"),
        Input("approve-btn", "n_clicks"),
        Input("reject-btn", "n_clicks"),
        State("validator-input", "value"),
        State("notes-input", "value"),
        prevent_initial_call=True,
    )
    def handle_validation(
        n_approve: int,
        n_reject: int,
        validator: str | None,
        notes: str | None,
    ) -> tuple[str, list[Any]]:
        """Handle approve or reject button click and persist the result.

        Parameters
        ----------
        n_approve : int
            Approve button click count.
        n_reject : int
            Reject button click count.
        validator : str or None
            Validator identifier from the form.
        notes : str or None
            Optional notes (required for reject).

        Returns
        -------
        tuple[str, list]
            Status message and updated coverage summary component.
        """
        ctx = callback_context
        if not ctx.triggered:
            return no_update, no_update
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "approve-btn":
            msg = _do_validation(validator or "", notes or "", "approved")
        elif trigger_id == "reject-btn":
            msg = _do_validation(validator or "", notes or "", "rejected")
        else:
            return no_update, no_update
        return msg, _coverage_children()

    def _coverage_children() -> list[Any]:
        """Build updated coverage summary children."""
        rep = state["measurement_set"].coverage_report()
        return [
            html.Hr(style={"borderColor": "#34495e"}),
            html.P(
                f"Coverage: {rep['present']}/{rep['total']}",
                style={"color": "#bdc3c7", "fontSize": "12px", "margin": "2px 0"},
            ),
            html.P(
                f"Validated: {rep['approved']}/{rep['manual_required']} required",
                style={"color": "#bdc3c7", "fontSize": "12px", "margin": "2px 0"},
            ),
            html.P(
                f"Pending: {rep['pending_validation']}",
                style={"color": "#e67e22", "fontSize": "12px", "margin": "2px 0"},
            ),
        ]

    return app


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_viewer(
    acquisition_dir: Path,
    model: Literal["yeadon", "hatze"] = "yeadon",
    port: int = 8051,
    debug: bool = False,
) -> None:
    """Launch the measurement validation viewer.

    Parameters
    ----------
    acquisition_dir : Path
        Acquisition directory (must contain raw/mesh_3d.glb and
        normalized/<model>_measurements.json).
    model : {"yeadon", "hatze"}
        Which model's measurements to load and display.
    port : int
        Local port for the Dash server.  Default ``8051``.
    debug : bool
        If ``True``, enables Dash debug mode with hot-reload.

    Notes
    -----
    Prints ``http://localhost:{port}`` to stdout and opens it automatically in
    the default browser before starting the blocking Dash server loop.
    Saves validation results to
    ``normalized/<model>_measurements_validated.json`` on each
    Approve/Reject action — no data is lost if the browser tab is closed.

    Raises
    ------
    ImportError
        If Dash or Plotly is not installed.
    RuntimeError
        If neither a measurement file nor a mesh can be found in
        ``acquisition_dir``.
    """
    if not _DASH_AVAILABLE or not _PLOTLY_AVAILABLE:
        raise ImportError(
            "Dash and Plotly are required for the visualization viewer.\n"
            "Install them with: pip install 'bodyloop-anthropometrics[viz]'"
        )

    acquisition_dir = Path(acquisition_dir).resolve()

    # Load data
    mesh = load_mesh(acquisition_dir)
    measurement_set = load_measurement_set(acquisition_dir, model)

    if measurement_set is None:
        # Create empty placeholder so the viewer can still open
        measurement_set = MeasurementSet(
            subject_id="unknown",
            acquisition_date=datetime.date.today().isoformat(),
            measurements={},
            missing=[],
        )
        logger.warning(
            "No measurement file found — viewer opened with empty dataset."
        )

    # Load mapping for contextual annotations
    try:
        from bodyloop_anthropometrics.anthropometry.yeadon_adapter import load_mapping

        mapping: dict[str, Any] = load_mapping() if model == "yeadon" else {}
    except Exception:  # noqa: BLE001
        mapping = {}

    app = _make_app(acquisition_dir, measurement_set, mesh, model, mapping)

    url = f"http://localhost:{port}"
    print(f"\n  BodyLoop Measurement Viewer\n  Opening {url}\n  Press Ctrl+C to stop.\n")
    webbrowser.open(url)

    app.run(host="localhost", port=port, debug=debug)
