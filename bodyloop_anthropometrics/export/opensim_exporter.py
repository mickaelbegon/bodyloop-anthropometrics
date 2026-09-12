"""OpenSim 4.x .osim model file exporter.

Converts body-segment inertial parameters (from BodyBSP or the Yeadon adapter)
into an OpenSim 4.x XML model file (.osim).  Joint hierarchy and coordinate
systems are read from ``configs/opensim_joint_correspondence.yaml``.

Internal units throughout: metres, kilograms, radians (AGENTS.md rule 5).

Notes
-----
OpenSim 4.x uses an XML-based .osim format (schema version 40000).
Inertia tensors are expressed as [Ixx, Iyy, Izz, Ixy, Ixz, Iyz] in kg·m²
in the body's local frame.

Segment boundary convention differs between the three estimators (Yeadon,
Hatze, direct BSP) -- do not mix outputs from different pipelines without
accounting for convention differences (see SCIENCE_DECISIONS.md).

References
----------
.. [1] OpenSim 4 API Reference, OpenSim::Body and OpenSim::Joint classes.
.. [2] Wu G. et al. (2002). ISB recommendation on joint coordinate systems --
       Part I. J Biomech 35(4):543-548.
.. [3] Wu G. et al. (2005). ISB recommendation on joint coordinate systems --
       Part II. J Biomech 38(5):981-992.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import BodyBSP

#: Default path to the OpenSim joint correspondence YAML.
_DEFAULT_YAML: Path = (
    Path(__file__).parent.parent.parent / "configs" / "opensim_joint_correspondence.yaml"
)

#: OpenSim schema version written in the root XML attribute.
_OPENSIM_VERSION = "40000"


@dataclass
class OpenSimBody:
    """Inertial parameters for one OpenSim Body element.

    Attributes
    ----------
    name : str
        OpenSim body name (e.g. ``"pelvis"``, ``"femur_r"``).
    mass : float
        Segment mass in kg.
    mass_center : NDArray of shape (3,)
        Centre of mass in the body's LOCAL frame, metres.  For bodies
        produced by :meth:`OpenSimExporter.from_body_bsp`, this is the
        global-frame CoM translated to be expressed relative to the joint
        child frame origin.
    inertia : NDArray of shape (6,)
        ``[Ixx, Iyy, Izz, Ixy, Ixz, Iyz]`` in kg·m² expressed in the
        body's LOCAL frame about the mass centre.
    """

    name: str
    mass: float
    mass_center: NDArray[np.float64]
    inertia: NDArray[np.float64]


def _euler_xyz_to_matrix(angles_rad: list[float]) -> NDArray[np.float64]:
    """Build a rotation matrix from XYZ Euler angles (intrinsic, radians).

    Parameters
    ----------
    angles_rad : list of float
        Three Euler angles [rx, ry, rz] in radians (intrinsic XYZ order).

    Returns
    -------
    NDArray of shape (3, 3)
        Rotation matrix R such that v_local = R.T @ v_global.

    Notes
    -----
    OpenSim uses XYZ body-fixed (intrinsic) Euler angles for
    ``PhysicalOffsetFrame.orientation``.  The rotation matrix is the
    composition Rz @ Ry @ Rx (last applied first in intrinsic convention).

    # TODO_SCIENTIFIC: confirm OpenSim orientation convention (intrinsic XYZ
    # vs extrinsic / other order) against the 4.x source before using
    # non-zero orientation offsets.
    """
    rx, ry, rz = float(angles_rad[0]), float(angles_rad[1]), float(angles_rad[2])
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)

    rx_mat = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
    ry_mat = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    rz_mat = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)
    return rz_mat @ ry_mat @ rx_mat


def _rotate_inertia(
    inertia_3x3: NDArray[np.float64],
    orientation_child: list[float],
) -> NDArray[np.float64]:
    """Rotate an inertia tensor from global to body-local frame.

    Parameters
    ----------
    inertia_3x3 : NDArray of shape (3, 3)
        Inertia tensor expressed in the global frame.
    orientation_child : list of float
        XYZ Euler angles of the body's ``orientation_in_child`` offset from
        the YAML, in radians.  If all zeros, returns the input unchanged.

    Returns
    -------
    NDArray of shape (3, 3)
        Inertia tensor in the body local frame:
        ``I_local = R.T @ I_global @ R``.

    Notes
    -----
    # TODO_SCIENTIFIC: frame rotation is only meaningful when
    # ``orientation_in_child`` is validated against the ISB definitions
    # (Wu et al. 2002, 2005).  All YAML offsets are currently [0,0,0]
    # (identity rotation), so this function is a no-op in practice.
    """
    angles = orientation_child or [0.0, 0.0, 0.0]
    if all(abs(a) < 1e-12 for a in angles):
        return inertia_3x3.copy()
    r_mat = _euler_xyz_to_matrix(angles)
    return r_mat.T @ inertia_3x3 @ r_mat


def _tensor_to_6(inertia_3x3: NDArray[np.float64]) -> NDArray[np.float64]:
    """Extract the 6 independent inertia components [Ixx,Iyy,Izz,Ixy,Ixz,Iyz].

    Parameters
    ----------
    inertia_3x3 : NDArray of shape (3, 3)
        Symmetric inertia tensor.

    Returns
    -------
    NDArray of shape (6,)
        ``[Ixx, Iyy, Izz, Ixy, Ixz, Iyz]`` in kg·m².
    """
    i = inertia_3x3
    return np.array(
        [i[0, 0], i[1, 1], i[2, 2], i[0, 1], i[0, 2], i[1, 2]],
        dtype=np.float64,
    )


class OpenSimExporter:
    """Export body segment parameters to OpenSim 4.x .osim format.

    Parameters
    ----------
    correspondence_path : Path or None, optional
        Path to the OpenSim joint correspondence YAML.  Defaults to
        ``configs/opensim_joint_correspondence.yaml`` bundled with the package.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    ValueError
        If the YAML does not parse to a mapping with a ``bodies`` key.

    Notes
    -----
    Internal units: metres, kilograms, radians throughout (AGENTS.md rule 5).
    Skinning weights are never used to distribute mass (AGENTS.md rule 1).

    Examples
    --------
    >>> exporter = OpenSimExporter()
    >>> bodies = exporter.from_yeadon(yeadon_params)
    >>> exporter.write_osim(bodies, Path("output/model.osim"))
    """

    def __init__(self, correspondence_path: Path | None = None) -> None:
        """Load the OpenSim joint correspondence YAML."""
        path = _DEFAULT_YAML if correspondence_path is None else Path(correspondence_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"OpenSim joint correspondence YAML not found: {path}"
            )
        with path.open(encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh)

        if not isinstance(parsed, dict) or "bodies" not in parsed:
            raise ValueError(
                f"OpenSim correspondence YAML must be a mapping with a 'bodies' key: {path}"
            )
        self._bodies_cfg: dict[str, dict[str, Any]] = parsed["bodies"]
        self._yaml_path = path

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _cfg_for_opensim_name(self, opensim_name: str) -> dict[str, Any] | None:
        """Return the YAML config dict for a given OpenSim body name, or None."""
        return self._bodies_cfg.get(opensim_name)

    def _validate_joint_centre(self, body_name: str, cfg: dict[str, Any]) -> None:
        """Raise ValueError if the joint definition is incomplete.

        Parameters
        ----------
        body_name : str
            OpenSim body name (for error messages).
        cfg : dict
            Body config dict from the YAML.

        Raises
        ------
        ValueError
            If the body has a non-null parent but is missing ``joint``,
            or if ``joint.location_in_parent`` / ``location_in_child`` is
            absent.  Never silently imputes a joint centre (AGENTS.md rule 2).
        """
        parent = cfg.get("parent")
        if parent is None:
            return  # ground body: no joint needed
        joint = cfg.get("joint")
        if not joint:
            raise ValueError(
                f"Body '{body_name}' has parent '{parent}' but no joint definition "
                f"in {self._yaml_path}. Cannot determine joint centre. "
                "Add joint.location_in_parent and joint.location_in_child to the YAML."
            )
        for key in ("location_in_parent", "location_in_child"):
            if joint.get(key) is None:
                raise ValueError(
                    f"Body '{body_name}': joint '{joint.get('name')}' is missing "
                    f"'{key}' in {self._yaml_path}. "
                    "Joint centre must be explicitly defined -- never imputed."
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def from_body_bsp(self, body_bsp: BodyBSP) -> list[OpenSimBody]:
        """Convert a :class:`~direct_mesh_bsp.BodyBSP` to OpenSim Bodies.

        Parameters
        ----------
        body_bsp : BodyBSP
            Full-body BSP results from :func:`~direct_mesh_bsp.compute_body_bsp`.

        Returns
        -------
        list of OpenSimBody
            One entry per OpenSim body that has a matching ``bsp_segment``
            in the correspondence YAML and a corresponding segment in
            ``body_bsp.segments``.  Bodies with ``bsp_segment: null`` (e.g.
            ``pelvis``, ``toes``) are omitted because the BSP pipeline does
            not produce them.

        Raises
        ------
        ValueError
            If a matched body is missing a joint centre definition in the YAML.

        Notes
        -----
        Inertia tensors from BodyBSP (``SegmentBSP.inertia_about_com_kgm2``)
        are expressed in the global frame.  This method rotates them into the
        body's local frame using ``orientation_in_child`` from the YAML.
        All current YAML entries have ``orientation_in_child: [0, 0, 0]``
        (identity), so the rotation is a no-op until scientifically validated.

        The centre of mass from BodyBSP is also in the global frame; it is
        passed through unchanged as the ``mass_center`` field of
        :class:`OpenSimBody`.  Downstream tools (biorbd, OpenSim) must
        account for the frame difference.

        # TODO_SCIENTIFIC: rotate CoM into body-local frame once joint
        # axes and orientations are validated (Wu et al. 2002, 2005).
        """
        result: list[OpenSimBody] = []
        for osim_name, cfg in self._bodies_cfg.items():
            bsp_segment = cfg.get("bsp_segment")
            if not bsp_segment:
                continue  # no BSP mapping for this body (e.g. pelvis, toes)
            seg = body_bsp.segments.get(bsp_segment)
            if seg is None:
                continue  # segment not computed (failed or not present)

            self._validate_joint_centre(osim_name, cfg)

            joint = cfg["joint"]
            orientation_child = joint.get("orientation_in_child") or [0.0, 0.0, 0.0]

            inertia_local = _rotate_inertia(
                seg.inertia_about_com_kgm2, orientation_child
            )
            com_global = np.asarray(seg.com_m, dtype=np.float64)

            result.append(
                OpenSimBody(
                    name=osim_name,
                    mass=float(seg.mass_kg),
                    mass_center=com_global.copy(),
                    inertia=_tensor_to_6(inertia_local),
                )
            )
        return result

    def from_yeadon(self, yeadon_params: dict[str, dict[str, Any]]) -> list[OpenSimBody]:
        """Convert :func:`~yeadon_adapter.export_inertial_params` output to OpenSim Bodies.

        Parameters
        ----------
        yeadon_params : dict[str, dict[str, Any]]
            Output of :func:`~yeadon_adapter.export_inertial_params`.  Keys are
            Yeadon segment labels (``"P"``, ``"T"``, ``"C"``, ``"A1"``,
            ``"A2"``, ``"B1"``, ``"B2"``, ``"J1"``, ``"J2"``, ``"J3"``,
            ``"K1"``, ``"K2"``, ``"K3"``).  Each value must have
            ``"mass_kg"``, ``"com_m"``, and ``"inertia_tensor_kgm2"`` keys.

        Returns
        -------
        list of OpenSimBody
            One entry per OpenSim body that has a matching ``yeadon_segment``
            in the correspondence YAML and a corresponding entry in
            ``yeadon_params``.  Bodies with ``yeadon_segment: null`` are
            skipped.

        Raises
        ------
        ValueError
            If a matched body is missing a joint centre definition in the YAML.

        Notes
        -----
        The Yeadon model expresses segment centres of mass in the yeadon
        global frame (origin at pelvis centre Ls0, Z-axis up) and inertia
        tensors about the segment centre of mass.  Frame conventions differ
        from OpenSim (Y-up, ISB).  The ``mass_center`` field is passed
        through unchanged; downstream tools must apply the frame transform.

        # TODO_SCIENTIFIC: apply frame rotation from yeadon_global (Z-up)
        # to OpenSim (Y-up, ISB) before exporting to OpenSim motions.
        # Confirm yeadon global axis convention against Yeadon (1990) Fig. 1.
        """
        result: list[OpenSimBody] = []
        for osim_name, cfg in self._bodies_cfg.items():
            yeadon_label = cfg.get("yeadon_segment")
            if not yeadon_label:
                continue  # no Yeadon mapping for this body
            seg_data = yeadon_params.get(yeadon_label)
            if seg_data is None:
                continue  # not in the provided dict

            self._validate_joint_centre(osim_name, cfg)

            joint = cfg["joint"]
            orientation_child = joint.get("orientation_in_child") or [0.0, 0.0, 0.0]

            inertia_3x3 = np.asarray(
                seg_data["inertia_tensor_kgm2"], dtype=np.float64
            ).reshape(3, 3)
            inertia_local = _rotate_inertia(inertia_3x3, orientation_child)
            com = np.asarray(seg_data["com_m"], dtype=np.float64).reshape(3)

            result.append(
                OpenSimBody(
                    name=osim_name,
                    mass=float(seg_data["mass_kg"]),
                    mass_center=com.copy(),
                    inertia=_tensor_to_6(inertia_local),
                )
            )
        return result

    def write_osim(
        self,
        bodies: list[OpenSimBody],
        output_path: Path,
        model_name: str = "bodyloop_model",
        source: str = "unknown",
    ) -> None:
        """Write an OpenSim 4.x .osim XML file.

        Parameters
        ----------
        bodies : list of OpenSimBody
            Inertial parameters for each body, in parent-before-child order.
            The ``ground`` body is implicit and must NOT be included.
        output_path : Path
            Destination ``.osim`` file.  Parent directories are created.
        model_name : str, optional
            Written in the ``Model name`` XML attribute.
        source : str, optional
            Provenance tag written in a header comment.  Should be one of
            ``'yeadon'``, ``'direct_bsp'``, or ``'hatze'``.

        Returns
        -------
        None

        Notes
        -----
        Writes:

        - ``BodySet`` — one ``Body`` element per entry in ``bodies``.
        - ``JointSet`` — joints read from the correspondence YAML; only joints
          whose child body appears in ``bodies`` are emitted.
        - ``MarkerSet`` — empty, for forward compatibility.

        Muscles, forces, and contact geometry are NOT written; they require a
        separate musculoskeletal registration step.

        Output is indented XML (Python 3.9+ ``ET.indent``) with OpenSim 4.x
        schema version ``40000``.

        Raises
        ------
        ValueError
            If a body in ``bodies`` is not found in the correspondence YAML.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        body_names = {b.name for b in bodies}

        # Validate all requested bodies are in the YAML
        for b in bodies:
            if b.name not in self._bodies_cfg and b.name != "ground":
                raise ValueError(
                    f"Body '{b.name}' is not defined in {self._yaml_path}. "
                    "Cannot write joint hierarchy without YAML definition."
                )

        # Root element
        root = ET.Element("OpenSimDocument")
        root.set("Version", _OPENSIM_VERSION)

        # Header comment
        ts = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        root.append(
            ET.Comment(
                f" Generated by bodyloop-anthropometrics | source={source} | {ts} "
            )
        )

        model_el = ET.SubElement(root, "Model")
        model_el.set("name", model_name)

        # ---- BodySet --------------------------------------------------
        body_set = ET.SubElement(model_el, "BodySet")
        objects_el = ET.SubElement(body_set, "objects")

        for body in bodies:
            body_el = ET.SubElement(objects_el, "Body")
            body_el.set("name", body.name)

            mass_el = ET.SubElement(body_el, "mass")
            mass_el.text = f"{body.mass:.6f}"

            mc_el = ET.SubElement(body_el, "mass_center")
            mc = body.mass_center
            mc_el.text = f"{mc[0]:.6f} {mc[1]:.6f} {mc[2]:.6f}"

            inertia_el = ET.SubElement(body_el, "inertia")
            iv = body.inertia
            inertia_el.text = (
                f"{iv[0]:.6f} {iv[1]:.6f} {iv[2]:.6f} "
                f"{iv[3]:.6f} {iv[4]:.6f} {iv[5]:.6f}"
            )

            ET.SubElement(body_el, "VisibleObject")
            ET.SubElement(body_el, "WrapObjectSet")

        # ---- JointSet -------------------------------------------------
        joint_set = ET.SubElement(model_el, "JointSet")
        joints_objects = ET.SubElement(joint_set, "objects")

        for osim_name, cfg in self._bodies_cfg.items():
            if osim_name == "ground":
                continue
            if osim_name not in body_names:
                continue  # body not in this export; skip its joint

            parent_body = cfg.get("parent", "ground")
            joint_cfg = cfg.get("joint")
            if not joint_cfg:
                continue

            jtype = joint_cfg.get("type", "WeldJoint")
            jname = joint_cfg.get("name", f"{parent_body}_{osim_name}")
            loc_parent = joint_cfg.get("location_in_parent", [0.0, 0.0, 0.0])
            ori_parent = joint_cfg.get("orientation_in_parent", [0.0, 0.0, 0.0])
            loc_child = joint_cfg.get("location_in_child", [0.0, 0.0, 0.0])
            ori_child = joint_cfg.get("orientation_in_child", [0.0, 0.0, 0.0])
            coordinates = cfg.get("coordinates") or []

            joint_el = ET.SubElement(joints_objects, jtype)
            joint_el.set("name", jname)

            # Parent and child frame paths (OpenSim 4 path syntax)
            parent_frame_el = ET.SubElement(joint_el, "parent_frame")
            if parent_body == "ground":
                parent_frame_el.text = "/ground"
            else:
                parent_frame_el.text = f"/bodyset/{parent_body}"

            child_frame_el = ET.SubElement(joint_el, "child_frame")
            child_frame_el.text = f"/bodyset/{osim_name}"

            # PhysicalOffsetFrames
            frames_el = ET.SubElement(joint_el, "frames")

            parent_offset = ET.SubElement(frames_el, "PhysicalOffsetFrame")
            parent_offset.set("name", f"{jname}_parent_offset")
            _vec3_el(parent_offset, "translation", loc_parent)
            _vec3_el(parent_offset, "orientation", ori_parent)

            child_offset = ET.SubElement(frames_el, "PhysicalOffsetFrame")
            child_offset.set("name", f"{jname}_child_offset")
            _vec3_el(child_offset, "translation", loc_child)
            _vec3_el(child_offset, "orientation", ori_child)

            # CoordinateSet (if any)
            if coordinates:
                coord_set = ET.SubElement(joint_el, "CoordinateSet")
                coord_objs = ET.SubElement(coord_set, "objects")
                for coord in coordinates:
                    coord_el = ET.SubElement(coord_objs, "Coordinate")
                    coord_el.set("name", coord["name"])
                    if "motion_type" in coord:
                        mt_el = ET.SubElement(coord_el, "motion_type")
                        mt_el.text = coord["motion_type"]

        # ---- MarkerSet (empty) ----------------------------------------
        marker_set = ET.SubElement(model_el, "MarkerSet")
        ET.SubElement(marker_set, "objects")

        # Write indented XML
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")

        xml_bytes = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(root, encoding="unicode").encode("utf-8")
        )
        output_path.write_bytes(xml_bytes)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _vec3_el(parent: ET.Element, tag: str, values: list[float]) -> ET.Element:
    """Append a ``<tag>x y z</tag>`` child element.

    Parameters
    ----------
    parent : ET.Element
        Parent XML element.
    tag : str
        Tag name.
    values : list of float
        Three values [x, y, z].

    Returns
    -------
    ET.Element
        The created child element.
    """
    el = ET.SubElement(parent, tag)
    el.text = f"{float(values[0]):.6f} {float(values[1]):.6f} {float(values[2]):.6f}"
    return el
