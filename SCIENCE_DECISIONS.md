# Scientific Decisions Log

Format: `## [YYYY-MM-DD] Title`
- **Decision**: ...
- **Rationale**: ...
- **Reference**: ...
- **Validation status**: PENDING | VALIDATED | REJECTED
- **Validator**: ...

---

## [2026-09-11] Segment density values (TODO_SCIENTIFIC)

- **Decision**: PENDING — default values from Dempster (1955) / de Leva (1996) used as
  placeholder in `geometry/mass_properties.py::SEGMENT_DENSITY_KG_M3`.
- **Rationale**: No DEXA calibration available at project start; de Leva (1996) provides
  the most widely cited tabulated adjustments to Zatsiorsky-Seluyanov's cadaver data.
- **Reference**: de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
  inertia parameters. J Biomech 29(9):1223-1230.
- **Validation status**: PENDING
- **Validator**: (unassigned)

## [2026-09-11] Hatze equation audit (TODO_SCIENTIFIC)

- **Decision**: PENDING — hatze-biomech MATLAB implementation used only as a reference,
  not as a validated implementation.  The hatze-biomech README explicitly states that
  some equations are incomplete or incorrect.
- **Rationale**: Primary source (Hatze 1979 CSIR Technical Report) must be obtained and
  all equations transcribed independently before the Python implementation can be trusted.
- **Reference**: Hatze, H. (1979). A model for the computational determination of
  parameter values of anthropomorphic segments. CSIR Technical Report TWISK 79.
  Hatze, H. (1980). A mathematical model for the computational determination of
  parameter values of anthropomorphic segments. J Biomech 13(10):833-843.
- **Validation status**: PENDING
- **Validator**: (unassigned)

## [2026-09-11] Yeadon measurement mapping completeness

- **Decision**: PENDING — `configs/bodyloop_to_yeadon.yaml` contains only the `Ls`
  placeholder.  All 95 Yeadon keys must be populated before `build-yeadon` can be
  considered functional.
- **Rationale**: Requires simultaneous access to Yeadon (1990) and BodyLoop SDK
  documentation to confirm anatomical correspondence.
- **Reference**: Yeadon, M.R. (1990). The simulation of aerial movement — II. A
  mathematical inertia model of the human body. J Biomech 23(1):67-74.
  https://yeadon.readthedocs.io/en/latest/measurements.html
- **Validation status**: PENDING
- **Validator**: (unassigned)

## [2026-09-11] BodiesReg objective function weights (TODO_SCIENTIFIC)

- **Decision**: PENDING — shape vs. pose vs. data-term weights for BodiesReg fitting
  must be chosen based on empirical evaluation on BodyLoop scans.
- **Rationale**: Default weights may favour shape accuracy over pose accuracy or
  vice versa; the impact on downstream BSP must be quantified.
- **Reference**: BodiesReg repository (verify URL before use).
  Loper, M. et al. (2015). SMPL: A skinned multi-person linear model.
  ACM Trans. Graph. 34(6).
- **Validation status**: PENDING
- **Validator**: (unassigned)

## [2026-09-11] Uniform-density assumption within segments (ASSUMPTION)

- **Decision**: Each body segment is modelled as a homogeneous solid with a single
  density value from `SEGMENT_DENSITY_KG_M3`.  Hatze's position-dependent density
  function is only implemented in `hatze_adapter.py`.
- **Rationale**: Uniform density is the standard simplification used by Yeadon (1990)
  and direct-mesh BSP pipelines.  It introduces known errors, particularly in trunk
  segments containing the lungs.
- **Reference**: Yeadon, M.R. (1990). J Biomech 23(1):67-74.
  Dumas, R. et al. (2015). Inertial properties of the human trunk. J Biomech 48(6).
- **Validation status**: PENDING — lung volume correction not yet implemented.
- **Validator**: (unassigned)
