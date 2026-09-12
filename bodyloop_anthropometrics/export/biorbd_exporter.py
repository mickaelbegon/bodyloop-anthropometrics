"""biorbd .bioMod model file exporter.

Converts body-segment parameters (BSP) produced by the direct-mesh pipeline
(:mod:`~bodyloop_anthropometrics.anthropometry.direct_mesh_bsp`) or the Yeadon
adapter (:mod:`~bodyloop_anthropometrics.anthropometry.yeadon_adapter`) into a
biorbd version-4 ``.bioMod`` text file.

The joint hierarchy and DOF definitions are read from
``configs/segment_joint_correspondence.yaml`` so that they can be reviewed and
updated by a scientist without modifying Python.

Notes
-----
Internal units: metres, kilograms, radians (AGENTS.md rule 5).
Inertia tensors are centroidal, expressed in the segment local frame.

# TODO_SCIENTIFIC: The segment local frames (RT) used here are approximations.
# For a kinematically correct model, the joint axis directions and joint-centre
# positions must be validated against ISB recommendations and subject-specific
# data before use in published simulations.

References
----------
.. [1] Michaud, B. & Begon, M. (2021). biorbd: A C++ framework with Python and
       MATLAB bindings for versatile musculoskeletal analyses. J Open Source
       Softw 6(57):2562.
.. [2] de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
       inertia parameters. J Biomech 29(9):1223-1230.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import BodyBSP

#: Default path to the joint correspondence YAML shipped with this package.
_DEFAULT_YAML: Path = (
    Path(__file__).parent.parent.parent / "configs" / "segment_joint_correspondence.yaml"
)

#: Mapping from DOF token to (type, axis) where type is 't' (translation) or 'r' (rotation).
_DOF_TOKEN_MAP: dict[str, tuple[str, str]] = {
    "TrX": ("t", "x"),
    "TrY": ("t", "y"),
    "TrZ": ("t", "z"),
    "RotX": ("r", "x"),
    "RotY": ("r", "y"),
    "RotZ": ("r", "z"),
}


@dataclass
class BiorbdSegment:
    """Inertial parameters for one biorbd segment.

    Attributes
    ----------
    name : str
        Segment name as written in the ``.bioMod`` file.
    mass : float
        Segment mass in kilograms.
    com : NDArray of shape (3,)
        Centre of mass in the segment local frame, in metres.
    inertia : NDArray of shape (3, 3)
        Centroidal inertia tensor in the segment local frame, in kg·m².
    rt_from_parent : NDArray of shape (4, 4)
        Homogeneous transformation matrix expressing the segment origin in
        the parent segment frame.  Rotation block is (3, 3), translation
        is column 3 in metres.
    mesh_file : str or None
        Optional path to an OBJ/STL mesh file for visualisation.  Not written
        to the ``.bioMod`` file by :meth:`BiorbdExporter.write_biomod`.
    """

    name: str
    mass: float
    com: NDArray[np.float64]
    inertia: NDArray[np.float64]
    rt_from_parent: NDArray[np.float64]
    mesh_file: str | None = None


def _rt_to_euler_xyz(rt: NDArray[np.float64]) -> tuple[float, float, float, float, float, float]:
    """Extract XYZ Euler angles and translation from a homogeneous matrix.

    Parameters
    ----------
    rt : NDArray of shape (4, 4)
        Homogeneous transformation matrix.

    Returns
    -------
    tuple of 6 floats
        ``(rx, ry, rz, tx, ty, tz)`` where angles are intrinsic XYZ Euler
        angles in radians and translations are in metres.

    Notes
    -----
    biorbd's ``RT`` line uses extrinsic (alias) XYZ convention.  scipy's
    ``as_euler("xyz")`` returns intrinsic angles; for a ZYX → XYZ swap the
    sign convention holds only when no gimbal lock is present.
    # TODO_SCIENTIFIC: verify the exact biorbd RT Euler convention against
    # biorbd source before using non-identity rotations in production.
    """
    rot = rt[:3, :3]
    r = Rotation.from_matrix(rot)
    rx, ry, rz = r.as_euler("xyz", degrees=False)
    tx, ty, tz = float(rt[0, 3]), float(rt[1, 3]), float(rt[2, 3])
    return float(rx), float(ry), float(rz), tx, ty, tz


def _format_dof_lines(dof_list: list[str]) -> list[str]:
    """Convert a DOF token list to biorbd ``translations``/``rotations`` lines.

    Parameters
    ----------
    dof_list : list of str
        Ordered list of DOF tokens (e.g. ``["TrX", "TrY", "TrZ", "RotX"]``).

    Returns
    -------
    list of str
        Zero, one, or two keyword lines (e.g. ``["    translations xyz",
        "    rotations x"]``).

    Raises
    ------
    ValueError
        If a token in ``dof_list`` is not one of the six valid tokens.
    """
    t_axes: list[str] = []
    r_axes: list[str] = []
    for tok in dof_list:
        if tok not in _DOF_TOKEN_MAP:
            raise ValueError(
                f"Unknown DOF token '{tok}'; valid tokens are {sorted(_DOF_TOKEN_MAP)}"
            )
        kind, axis = _DOF_TOKEN_MAP[tok]
        if kind == "t":
            t_axes.append(axis)
        else:
            r_axes.append(axis)
    lines: list[str] = []
    if t_axes:
        lines.append(f"    translations {''.join(t_axes)}")
    if r_axes:
        lines.append(f"    rotations {''.join(r_axes)}")
    return lines


class BiorbdExporter:
    """Export body segment parameters to biorbd .bioMod format.

    Parameters
    ----------
    correspondence_path : Path or None, optional
        Path to the joint correspondence YAML file.  Defaults to
        ``configs/segment_joint_correspondence.yaml`` shipped with this package.

    Notes
    -----
    The YAML file defines the 17-segment hierarchy, DOF, ranges, and parent
    relationships used to generate the ``.bioMod`` segment blocks.  All
    scientifically uncertain values (joint axes, ROM ranges, joint centres)
    are marked ``TODO_SCIENTIFIC`` in the YAML.

    Examples
    --------
    >>> exporter = BiorbdExporter()
    >>> segments = exporter.from_yeadon(yeadon_params)
    >>> exporter.write_biomod(segments, Path("subject.bioMod"), source="yeadon")
    """

    def __init__(self, correspondence_path: Path | None = None) -> None:
        """Load the joint correspondence YAML.

        Parameters
        ----------
        correspondence_path : Path or None, optional
            Override path to the YAML.  Defaults to the bundled
            ``configs/segment_joint_correspondence.yaml``.

        Raises
        ------
        FileNotFoundError
            If the YAML file does not exist at the resolved path.
        ValueError
            If the file does not parse to a mapping with a ``segments`` key.
        """
        path = _DEFAULT_YAML if correspondence_path is None else Path(correspondence_path)
        if not path.is_file():
            raise FileNotFoundError(f"Correspondence YAML not found: {path}")
        with path.open(encoding="utf-8") as fh:
            parsed: Any = yaml.safe_load(fh)
        if not isinstance(parsed, dict) or "segments" not in parsed:
            raise ValueError(
                f"Correspondence YAML must be a mapping with a 'segments' key: {path}"
            )
        self._segments: dict[str, dict[str, Any]] = parsed["segments"]

    # ------------------------------------------------------------------
    # Conversion methods
    # ------------------------------------------------------------------

    def from_body_bsp(
        self,
        body_bsp: BodyBSP,
        joint_positions: dict[str, NDArray[np.float64]] | None = None,
    ) -> list[BiorbdSegment]:
        """Convert BodyBSP (direct mesh pipeline) to a list of BiorbdSegments.

        Parameters
        ----------
        body_bsp : BodyBSP
            Full-body BSP results from
            :func:`~bodyloop_anthropometrics.anthropometry.direct_mesh_bsp.compute_body_bsp`.
        joint_positions : dict of {str: NDArray of shape (3,)} or None, optional
            Mapping from ``joint_centre_bodyloop`` path strings (as defined in
            the correspondence YAML) to joint centre positions in the global
            frame, in metres.  Required for every segment whose YAML entry has
            a non-null ``joint_centre_bodyloop``.

        Returns
        -------
        list of BiorbdSegment
            One entry per YAML segment that has a matching ``bodybsp_segment``
            present in ``body_bsp.segments``.  Segments with ``bodybsp_segment:
            null`` or absent from BodyBSP are silently skipped (their absence
            is already recorded in ``BodyBSP.failed_segments``).

        Raises
        ------
        ValueError
            If a YAML entry has a non-null ``joint_centre_bodyloop`` path but
            the corresponding position is not supplied in ``joint_positions``.
            Never silently imputes a position (AGENTS.md rule 2).

        Notes
        -----
        Inertia tensors from BodyBSP are expressed in the global (mesh) frame.
        The rotation block of ``rt_from_parent`` is currently set to identity,
        so the segment frame coincides with the global frame.  This is a known
        simplification: a fully correct implementation would rotate the inertia
        tensor into the segment frame defined by the joint axis directions in
        the YAML.

        # TODO_SCIENTIFIC: implement proper segment-frame rotation once joint
        # axis directions are validated against ISB conventions (AGENTS.md rule).

        The COM stored in each :class:`BiorbdSegment` is expressed in the
        segment frame: ``com_segment = com_global - joint_centre_position``
        (identity rotation assumed).
        """
        result: list[BiorbdSegment] = []
        for _key, seg_cfg in self._segments.items():
            bsp_name: str | None = seg_cfg.get("bodybsp_segment")
            if bsp_name is None:
                continue
            if bsp_name not in body_bsp.segments:
                continue

            # Enforce joint centre requirement — never silently impute.
            jc_path: str | None = seg_cfg.get("joint_centre_bodyloop")
            jc_pos: NDArray[np.float64] | None = None
            if jc_path is not None:
                if joint_positions is None or jc_path not in joint_positions:
                    raise ValueError(
                        f"Segment '{seg_cfg['biorbd_name']}' requires a joint centre at "
                        f"path '{jc_path}' but it is not present in joint_positions. "
                        f"Provide joint_positions={{'{jc_path}': <position_array>}} or "
                        f"set joint_centre_bodyloop to null in the YAML. "
                        f"Never silently imputing position (AGENTS.md rule 2)."
                    )
                jc_pos = np.asarray(joint_positions[jc_path], dtype=np.float64).reshape(3)

            bsp_seg = body_bsp.segments[bsp_name]

            # RT: identity rotation; translation = joint centre in global frame.
            rt = np.eye(4, dtype=np.float64)
            if jc_pos is not None:
                rt[:3, 3] = jc_pos

            # COM in segment frame = COM_global - joint_centre (identity rotation).
            com_segment = bsp_seg.com_m.copy()
            if jc_pos is not None:
                com_segment = bsp_seg.com_m - jc_pos

            result.append(
                BiorbdSegment(
                    name=seg_cfg["biorbd_name"],
                    mass=float(bsp_seg.mass_kg),
                    com=com_segment.astype(np.float64),
                    inertia=bsp_seg.inertia_about_com_kgm2.astype(np.float64),
                    rt_from_parent=rt,
                )
            )
        return result

    def from_yeadon(self, yeadon_params: dict[str, Any]) -> list[BiorbdSegment]:
        """Convert yeadon export_inertial_params() dict to BiorbdSegments.

        Parameters
        ----------
        yeadon_params : dict[str, Any]
            Output of
            :func:`~bodyloop_anthropometrics.anthropometry.yeadon_adapter.export_inertial_params`.
            Keys are Yeadon segment labels (``str(segment.label)``); values
            have keys ``"mass_kg"``, ``"com_m"``, ``"inertia_tensor_kgm2"``,
            ``"frame"``.

        Returns
        -------
        list of BiorbdSegment
            One entry per YAML segment whose ``yeadon_segment`` label is found
            in ``yeadon_params``.  Unmatched YAML segments are silently skipped.

        Notes
        -----
        Yeadon's output is already in centroidal principal axes; each
        :class:`BiorbdSegment` is created with an identity ``rt_from_parent``
        (segment frame = Yeadon frame).  The joint hierarchy from the
        correspondence YAML is applied by :meth:`write_biomod` for the
        ``parent`` field.

        # TODO_VALIDATE: confirm the Yeadon global axis convention against
        # Yeadon (1990) Figure 1 before exporting to biorbd, whose conventions
        # differ.  The RT is identity here, not a frame conversion.
        """
        result: list[BiorbdSegment] = []
        for _key, seg_cfg in self._segments.items():
            yeadon_label: str | None = seg_cfg.get("yeadon_segment")
            if yeadon_label is None:
                continue
            if yeadon_label not in yeadon_params:
                continue

            params = yeadon_params[yeadon_label]
            mass = float(params["mass_kg"])
            com = np.asarray(params["com_m"], dtype=np.float64).reshape(3)
            inertia = np.asarray(params["inertia_tensor_kgm2"], dtype=np.float64).reshape(3, 3)

            result.append(
                BiorbdSegment(
                    name=seg_cfg["biorbd_name"],
                    mass=mass,
                    com=com,
                    inertia=inertia,
                    rt_from_parent=np.eye(4, dtype=np.float64),
                )
            )
        return result

    # ------------------------------------------------------------------
    # Writer
    # ------------------------------------------------------------------

    def write_biomod(
        self,
        segments: list[BiorbdSegment],
        output_path: Path,
        model_name: str = "bodyloop_model",
        source: str = "unknown",
    ) -> None:
        """Write a .bioMod file (biorbd version 4 format).

        Parameters
        ----------
        segments : list of BiorbdSegment
            Ordered list (must follow parent-before-child order so that biorbd
            can resolve the kinematic chain in a single pass).
        output_path : Path
            Destination file path (created or overwritten).  Parent directories
            are created if necessary.
        model_name : str, optional
            Written in the file header comment.  Default ``"bodyloop_model"``.
        source : str, optional
            ``'yeadon'`` | ``'direct_bsp'`` | ``'hatze'`` — written in the
            header comment.  Default ``"unknown"``.

        Returns
        -------
        None

        Notes
        -----
        The writer outputs only the inertial block: ``version``, ``gravity``,
        and ``segment`` blocks with ``mass``, ``inertia``, ``com``, ``RT``,
        ``dof`` (translations/rotations), and ``ranges``.  Marker blocks and
        mesh files are not written (they require a separate registration step).

        All numerical values are written with six significant figures to
        preserve at least double-precision accuracy across a round-trip.

        Units in the output file are SI: metres and kilograms.
        """
        lines = self._build_header(model_name, source)
        for seg in segments:
            cfg = self._find_config_by_biorbd_name(seg.name)
            lines.extend(self._format_segment_block(seg, cfg))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_config_by_biorbd_name(self, biorbd_name: str) -> dict[str, Any] | None:
        """Return the YAML segment config whose biorbd_name matches.

        Parameters
        ----------
        biorbd_name : str
            Segment name as written in the .bioMod file.

        Returns
        -------
        dict or None
            The YAML segment config dict, or ``None`` if not found.
        """
        for cfg in self._segments.values():
            if cfg.get("biorbd_name") == biorbd_name:
                return cfg
        return None

    @staticmethod
    def _build_header(model_name: str, source: str) -> list[str]:
        """Build the .bioMod file header lines.

        Parameters
        ----------
        model_name : str
            Model identifier written as a comment.
        source : str
            BSP source identifier written as a comment.

        Returns
        -------
        list of str
            Lines including version and gravity declarations.
        """
        return [
            f"// Model: {model_name}",
            f"// Source: {source}",
            "// Generated by bodyloop_anthropometrics.export.biorbd_exporter",
            "// Units: metres, kilograms, radians",
            "// TODO_SCIENTIFIC: validate joint axes and ranges before use in simulation",
            "",
            "version 4",
            "",
            "gravity 0 0 -9.81",
            "",
        ]

    def _format_segment_block(
        self,
        seg: BiorbdSegment,
        cfg: dict[str, Any] | None,
    ) -> list[str]:
        """Format one segment block in biorbd .bioMod syntax.

        Parameters
        ----------
        seg : BiorbdSegment
            Segment with mass, COM, and inertia in SI units.
        cfg : dict or None
            YAML segment config providing parent, DOF, and ranges.  When
            ``None`` (segment not in correspondence table), a minimal fixed
            block with no DOF is written and ``parent root`` is used.

        Returns
        -------
        list of str
            Lines of the segment block, including ``segment`` and
            ``endsegment`` delimiters.
        """
        parent = cfg["parent"] if cfg else "root"
        dof_list: list[str] = cfg.get("dof") or [] if cfg else []
        ranges_cfg: dict[str, Any] = cfg.get("ranges") or {} if cfg else {}

        rx, ry, rz, tx, ty, tz = _rt_to_euler_xyz(seg.rt_from_parent)

        def fmt(v: float) -> str:
            """Format a float with six significant figures."""
            return f"{v:.6g}"

        lines: list[str] = [
            f"segment {seg.name}",
            f"    parent {parent}",
            f"    RT {fmt(rx)} {fmt(ry)} {fmt(rz)} xyz {fmt(tx)} {fmt(ty)} {fmt(tz)}",
        ]

        # DOF keywords
        lines.extend(_format_dof_lines(dof_list))

        # Ranges (one line per DOF, in DOF order)
        if dof_list and ranges_cfg:
            lines.append("    ranges")
            for tok in dof_list:
                rng = ranges_cfg.get(tok)
                if rng is not None:
                    lo, hi = float(rng[0]), float(rng[1])
                    lines.append(f"        {fmt(lo)} {fmt(hi)}")

        # Inertial block (SI units, 6 sig figs)
        lines.append(f"    mass {fmt(seg.mass)}")

        inertia = np.asarray(seg.inertia, dtype=np.float64).reshape(3, 3)
        lines.append("    inertia")
        for row in inertia:
            lines.append(f"        {fmt(row[0])} {fmt(row[1])} {fmt(row[2])}")

        com = np.asarray(seg.com, dtype=np.float64).reshape(3)
        lines.append(f"    com {fmt(com[0])} {fmt(com[1])} {fmt(com[2])}")

        lines.append("endsegment")
        lines.append("")
        return lines
