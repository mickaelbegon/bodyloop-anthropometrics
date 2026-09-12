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

## [2026-09-11] Segment density values for direct mesh BSP (TODO_SCIENTIFIC)

- **Decision**: Using de Leva (1996) / Dempster (1955) population-average densities as
  placeholder in `anthropometry/direct_mesh_bsp.py::SEGMENT_DENSITIES_KG_M3`.
- **Values used** (kg/m³): head = 1100, trunk = 1000, upper_arm = 1056, forearm = 1130,
  hand = 1160, thigh = 1050, shank = 1065, foot = 1090.  Left and right share the same
  value.  These differ slightly from the coarser per-segment-class table in
  `geometry/mass_properties.py::SEGMENT_DENSITY_KG_M3`, which is kept for the
  segment-class API; the two tables must be reconciled once real densities are available.
- **Rationale / Why**: No DEXA calibration available at project start.  de Leva (1996)
  provides the most widely cited tabulated adjustments to Zatsiorsky-Seluyanov's data.
  Densities are then uniformly rescaled so that the summed segment mass matches the
  measured body mass; the scale factor is reported as `BodyBSP.density_scale_factor` and
  a pre-calibration error above 1 % raises a warning note rather than being absorbed.
- **Reference**: de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment
  inertia parameters. J Biomech 29(9):1223-1230.
  Dempster, W.T. (1955). Space requirements of the seated operator. WADC TR 55-159.
- **Validation status**: PENDING
- **Validator**: (unassigned)

## [2026-09-11] Pulmonary volume correction for trunk BSP (TODO_SCIENTIFIC)

- **Decision**: ICRP reference lung volumes are tabulated in
  `direct_mesh_bsp.py::DEFAULT_LUNG_VOLUME_M3` (male 3.0 L, female 2.3 L, other 2.65 L)
  and the correction is implemented, but it is DISABLED by default
  (`compute_body_bsp(..., apply_lung_correction=False)`).
- **Rationale / Why**: The surface mesh does not represent internal cavities, so the raw
  volume over-estimates the mass of tissue in the thorax.  However, the de Leva /
  Dempster trunk density (1000 kg/m³) is itself a whole-trunk average that already
  embeds the pulmonary cavity — applying both would double-count the lungs.  Enabling
  the correction is only correct together with a lung-free trunk tissue density.  When
  enabled, the effective density becomes ρ_trunk · (1 − V_lung / V_trunk) and both the
  segment and the body-level notes record it.
- **Reference**: ICRP (2002). Publication 89: Basic Anatomical and Physiological Data
  for Use in Radiological Protection. Annals of the ICRP 32(3-4).
  Dumas, R. et al. (2015). Inertial properties of the human trunk. J Biomech 48(6).
- **Validation status**: PENDING — requires a subject-specific lung volume (spirometry
  or CT) and a lung-free trunk tissue density before it can be switched on.
- **Validator**: (unassigned)

## [2026-09-11] Segment boundary planes and the shoulder convention (TODO_SCIENTIFIC)

- **Decision**: `direct_mesh_bsp.define_segment_boundaries` cuts each joint with a plane
  through the joint centre perpendicular to the long axis of the DISTAL segment
  (Dempster / de Leva convention).  Two extra, non-anatomical planes are required for the
  cuts to actually disconnect the segments: a parasagittal plane through each
  glenohumeral centre (`<side>_axilla`), because with the arms hanging the arm and trunk
  remain joined below a transverse shoulder plane; and a mid-sagittal plane through the
  hip midpoint (`sagittal_pelvis`), because a hip cut alone leaves the two thighs joined
  through the perineal region.
- **Consequence**: tissue lateral to the glenohumeral centre and proximal to the shoulder
  plane (the superior deltoid cap) is assigned to NO segment.  It is not redistributed;
  `compute_body_bsp` reports the segmented-versus-whole-body volume residual in
  `BodyBSP.notes` and warns above 2 %.  Perineal tissue below the hip planes is assigned
  to the thighs.
- **Rationale / Why**: Boundary definitions differ between estimators — Yeadon (1990)
  uses a different shoulder boundary from de Leva (1996) — so arm and trunk masses are
  not comparable across the three estimators without accounting for the convention.
- **Reference**: de Leva, P. (1996). J Biomech 29(9):1223-1230, Table 1.
  Yeadon, M.R. (1990). J Biomech 23(1):67-74.
- **Validation status**: PENDING — the definitive shoulder boundary and the destination
  of the deltoid cap must be chosen before cross-estimator comparison.
- **Validator**: (unassigned)

## [2026-09-12] Hatze primitive equation audit — numerical validation

- **Decision**: PARTIALLY RESOLVED — all 9 geometric primitives (A1.1–A1.9) were
  validated by two independent numerical engines (adaptive Gauss–Kronrod quadrature at
  1e-10 accuracy and 10M-sample seeded Monte-Carlo) plus closed-form derivations.
  Results written to `validation/HATZE_PRIMITIVES_AUDIT.md` and `docs/HATZE_EQUATIONS.md`.
- **Findings (8 corrections applied to `docs/HATZE_EQUATIONS.md`):**
  1. **A1.4 (Octoparaboloid) is WRONG.** All 4 coefficients diverge 1.6–3.3 % from
     the printed surface definition. The coefficient 0.19473 for b² is *structurally
     unattainable* (must be 1/5 for any member of that surface family). Either the
     surface equation or the coefficients were mis-transcribed in the cheatsheet.
     `⛔ DO NOT IMPLEMENT A1.4 without verifying against Hatze (1979).`
  2. **A1.7 centroid wrong:** printed `z̄ = a/3`; correct is `z̄ = c/3` (depth axis).
  3. **5 primitives have swapped axis labels** in the header (A1.1, A1.3, A1.7, A1.8,
     A1.9): the inertia formulas are internally consistent but the `Parameters: a(Y), b(X)`
     annotation is inverted. A literal implementation would swap Ī_x/Ī_y (~20–26 % error).
  4. **A1.8 is a thin-plate approximation** — drops `Mh²/12`; 8.2 % error at foot-
     segment thickness (h ≈ 20 mm). Real implementation should use the full formula.
  5. **3 TODO_VALIDATE flags closed:** A1.9 coefficients (0.0686 = 12/175, 0.15 = 3/20)
     and A1.2 coefficient (12/175) are exact rationals. A1.3 coefficient 0.07 ≈
     1/4 − 16/(9π²) = 0.06987 is correct to 0.18 % rounding.
  6. **A1.2, A1.5, A1.6** fully verified as printed — no corrections needed.
- **What this audit covers / does NOT cover:** This validates the geometric primitive
  library (mass, centroid, inertia tensors). It does NOT validate: the mapping from
  Hatze's 242 measurements to primitive parameters (a, b, c, h, …), the subcutaneous
  fat density model, or the 17-segment anatomy. These require Hatze (1979) original.
- **Reference**: Hatze, H. (1979). CSIR Technical Report TWISK 79, Pretoria.
  Hatze, H. (1980). J Biomech 13(10):833-843.
  `validation/HATZE_PRIMITIVES_AUDIT.md`, `validation/validate_hatze_primitives.py`.
- **Validation status**: PARTIALLY RESOLVED — primitives audited; A1.4 UNRESOLVED pending
  primary source; measurement-to-parameter mapping PENDING.
- **Validator**: Val-Hatze agent (Claude Opus), 2026-09-12.

## [2026-09-12] Hatze 242-measurement reconstruction and A1.4 segment assignment (ASSUMPTION)

- **Decision**: ASSUMPTION — `configs/bodyloop_to_hatze.yaml` was reconstructed from the
  segment geometry figures in `docs/HATZE_EQUATIONS.md` §3 (the cheatsheet), not from
  Hatze (1979) directly. The 242 entries match the per-segment budget exactly (trunk 24,
  head-neck 8, shoulders 5+5, arms 4×20, hands 8+8, pelvis 12, thighs/shanks 4×20,
  feet 6+6).
- **A1.4 assignment assumption**: The cheatsheet §3 states the Elliptic Octoparaboloid
  (A1.4) is "used for trunk and torso slices" without naming a specific segment. The
  implementation assumes A1.4 is consumed by the **abdomino-pelvic outer cross-section**
  (segment 11, 4 entries: h11_s01_ml/ap, h11_s02_ml/ap). Trunk slices (segment 1) use
  A1.1 + A1.6 as stated in §3. This assignment must be verified against Hatze (1979).
  **All 4 A1.4 entries are blocked (`blocked: true`) — `HatzeAdapter.compute_primitive_params()`
  raises `RuntimeError` for any call involving A1.4.**
- **Source-type breakdown (242 entries):** 168 direct, 56 calculated, 18 manual.
  All 242 carry `manual_validation_required: true` and provisional `bodyloop_path`.
- **Rationale**: Provides the full extraction infrastructure (schemas, YAML, adapter)
  that can be filled in when the primary source is obtained, without guessing formulas.
- **Reference**: `configs/bodyloop_to_hatze.yaml`, `bodyloop_anthropometrics/anthropometry/hatze_adapter.py`.
  Hatze, H. (1979). CSIR Technical Report TWISK 79 — required to confirm all assignments.
- **Validation status**: PENDING — segment geometry assignment requires Hatze (1979).
- **Validator**: Agent H (Claude Opus), 2026-09-12.

## [2026-09-11] Hatze equation audit — primary source (TODO_SCIENTIFIC)

- **Decision**: PENDING — hatze-biomech cheatsheet equations extracted and audited
  (see entry above), but the 242-measurement-to-parameter mapping requires the original
  publication.
- **Rationale**: The cheatsheet does NOT contain the equations that map Hatze's 242
  body measurements to primitive parameters (a, b, c, r, h, …). These are only in
  the original report.
- **Reference**: Hatze, H. (1979). A model for the computational determination of
  parameter values of anthropomorphic segments. CSIR Technical Report TWISK 79.
  Hatze, H. (1980). A mathematical model for the computational determination of
  parameter values of anthropomorphic segments. J Biomech 13(10):833-843.
- **Validation status**: PENDING — must obtain primary source.
- **Validator**: (unassigned)

## [2026-09-11] Yeadon measurement mapping completeness

- **Decision**: PARTIALLY RESOLVED — `configs/bodyloop_to_yeadon.yaml` now defines all
  95 keys.  The key *set* is closed and verified; the *anatomical content* of each
  entry is not yet validated.  Of the 95 entries: 35 have a resolvable
  `bodyloop_path`, 60 are `calculated` with the derivation documented but not
  implemented, and 65 carry `manual_validation_required: true`.
- **Rationale**: The key set was verified programmatically against
  `yeadon.human.Human.measnames` in yeadon 1.5.0 rather than transcribed by hand
  (Ls 21 + La 18 + Lb 18 + Lj 19 + Lk 19 = 95).  `tests/unit/test_yeadon_adapter.py`
  asserts the equality, so the file cannot silently drift from the package.
- **Reference**: Yeadon, M.R. (1990). The simulation of aerial movement — II. A
  mathematical inertia model of the human body. J Biomech 23(1):67-74.
  https://yeadon.readthedocs.io/en/latest/measurements.html
- **Validation status**: PENDING — key set VALIDATED, anatomical definitions PENDING.
- **Validator**: (unassigned)

## [2026-09-11] Yeadon difficult anatomical landmarks (TODO_SCIENTIFIC)

- **Decision**: PENDING — every measurement resting on one of these landmarks is
  marked `manual_validation_required: true` in `configs/bodyloop_to_yeadon.yaml` and
  is reported by `MeasurementSet.pending_validation()`.
- **Affected landmarks and measurements**:
  - *Hip joint centre* (Ls0 / Lj0 / Lk0): `Ls1L`, `Ls2L`, `Ls3L`, `Ls4L`, `Ls5L`,
    `Ls0p`, `Ls0w`, `Lj1L`, `Lj3L`, `Lj4L`, `Lj5L`, `Lk1L`, `Lk3L`, `Lk4L`, `Lk5L`
  - *Shoulder joint centre* (Ls4 / La0 / Lb0): `Ls4L`, `Ls4w`, `Ls4d`, `La0p`,
    `La2L`, `La3L`, `La4L`, `Lb0p`, `Lb2L`, `Lb3L`, `Lb4L`
  - *Acromion* (Ls5): `Ls5L`, `Ls6L`, `Ls7L`, `Ls8L`, `Ls5p`
  - *Lowest anterior rib* (Ls2): `Ls2L`, `Ls2p`, `Ls2w`
  - *Nipple* (Ls3): `Ls3L`, `Ls3p`, `Ls3w`
  - *Base of thumb* (La5 / Lb5): `La5L`, `La5p`, `La5w`, `Lb5L`, `Lb5p`, `Lb5w`
  - *Crotch* (Lj1 / Lk1): `Lj1L`, `Lj1p`, `Lk1L`, `Lk1p`
  - *Heel* (Lj6 / Lk6): `Lj6L`, `Lj6p`, `Lj6d`, `Lk6L`, `Lk6p`, `Lk6d`
  - *Foot arch* (Lj7 / Lk7): `Lj7p`, `Lk7p`
- **Rationale**: Hip joint centre, shoulder joint centre, acromion, crotch, heel,
  foot arch, nipple, base of thumb, and lowest anterior rib require careful
  anatomical definition to match Yeadon (1990) exactly.  BodyLoop markers are
  surface landmarks detected optically and do not necessarily coincide with
  Yeadon's definitions — joint centres in particular are internal and must be
  regressed, not measured.  An error in a *level* propagates to every length
  measured from it, so these landmarks dominate the error budget of the model.
- **Not an exhaustive list of flagged keys**: 65 of the 95 entries carry
  `manual_validation_required: true`.  The 49 listed above are flagged because of a
  *landmark* problem.  The remaining 16 (`La6L`, `La6p`, `La7p`, `La7w`, `Lb6L`,
  `Lb6p`, `Lb7p`, `Lb7w`, `Lj8L`, `Lj9L`, `Lj9p`, `Lj9w`, `Lk8L`, `Lk9L`, `Lk9p`,
  `Lk9w`) are flagged for a different reason: fingers and toes are below the useful
  resolution of a full-body optical scan, so those values must be taken with a tape
  measure or callipers regardless of how well the landmarks are defined.
- **Reference**: Yeadon, M.R. (1990), Table 1 and Figure 1.
  Harrington, M.E. et al. (2007). Prediction of the hip joint centre in adults,
  children, and patients with cerebral palsy based on magnetic resonance imaging.
  J Biomech 40(3):595-602.
- **Validation status**: PENDING
- **Validator**: (unassigned)

## [2026-09-11] Yeadon perimeters map to BodyLoop `convex`, not `perimeter`

- **Decision**: Every Yeadon perimeter key (`*p`) maps to the BodyLoop **`convex`**
  value of the cross-section, never to the true contour `perimeter`.
- **Rationale**: Yeadon's protocol takes perimeters with a tape measure pulled taut.
  A taut tape follows the convex hull of a cross-section — it cannot enter
  concavities.  The true contour perimeter is therefore the wrong analogue: it
  exceeds the tape value wherever the contour is concave (waist, ankle, wrist,
  between the toes) and inflates the stadium-solid volumes, hence the segment
  masses.  BodyLoop reports both quantities, so the choice must be explicit.
- **Reference**: Yeadon, M.R. (1989). The simulation of aerial movement — I. The
  determination of orientation angles from film data. J Biomech 23(1):59-66
  (measurement protocol).  Yeadon, M.R. (1990). J Biomech 23(1):67-74.
- **Validation status**: PENDING — the magnitude of the convex-vs-perimeter
  difference has not yet been quantified on real BodyLoop scans.
- **Validator**: (unassigned)

## [2026-09-11] Stadium consistency constraint between perimeter and width

- **Decision**: PENDING — perimeter/width pairs feeding the same Yeadon level must be
  taken from the *same* cross-section, not from two separately-labelled BodyLoop
  measurements.
- **Rationale**: `yeadon` models most levels as a stadium (a rectangle capped by two
  semicircles) parameterised by a perimeter `p` and a width `w`.  The solid is only
  geometrically valid when `p/w >= pi`; for `2 < p/w < pi` yeadon emits
  "stadium is defined incorrectly, r must be positive and t must be nonnegative"
  and silently degrades the solid, and at `p/w = 2` construction fails outright.
  This was observed while building a `yeadon.Human` from plausible but
  independently-chosen values.  Because the mapping draws some perimeters and some
  widths from different BodyLoop labels, a mismatched pair can violate the
  constraint without either value being individually wrong.
- **Implication**: the extraction layer should validate `p/w >= pi` per level and
  report a violation rather than pass the pair to yeadon.
- **Reference**: yeadon 1.5.0, `yeadon/solid.py::Stadium.__init__`.
  Yeadon, M.R. (1990). J Biomech 23(1):67-74, stadium solid definition.
- **Validation status**: PENDING — the per-level check is not yet implemented.
- **Validator**: (unassigned)

## [2026-09-11] Levels yeadon derives rather than measures

- **Decision**: ACCEPTED — four quantities are absent from the 95 keys because yeadon
  computes them, and the mapping documents this rather than inventing keys for them.
- **Affected levels**: `La1`/`Lb1` mid upper-arm = `0.5 x La2L`; `Lj2`/`Lk2` mid-thigh
  = `0.5 x (Lj1L + Lj3L)`; `Lj7`/`Lk7` foot arch = `0.5 x (Lj6L + Lj8L)`;
  `Lj0p`/`Lk0p` crotch perimeter, derived from `Ls0p` and `Ls0w`.
- **Rationale**: The *perimeters* at those computed levels (`La1p`, `Lj2p`, `Lj7p`,
  and their right-side counterparts) are still required inputs and must be sampled at
  the computed axial location.  Substituting the nearest convenient girth — the
  maximum biceps girth for `La1p`, or the maximum thigh girth for `Lj2p` — is a
  common and silent source of error, so each of those entries carries an explicit
  warning in the mapping file.
- **Reference**: Yeadon, M.R. (1990). J Biomech 23(1):67-74.
  https://yeadon.readthedocs.io/en/latest/measurements.html
- **Validation status**: VALIDATED against yeadon 1.5.0 source.
- **Validator**: (unassigned)

## [2026-09-11] BodyLoop path vocabulary is provisional

- **Decision**: PENDING — the `bodyloop_path` values in
  `configs/bodyloop_to_yeadon.yaml` follow the normalised-export naming convention of
  `bodyloop_anthropometrics/api/export.py`, but the labels the scanner actually emits
  have **not** been confirmed.
- **Rationale**: The complete BodyLoop OpenAPI specification is not publicly
  documented (docs/RESEARCH.md, TODO_SCIENTIFIC #1).  Rather than guess silently, the
  adapter reports any path that does not resolve in
  `MeasurementSet.missing`; nothing is imputed.  Once the real label vocabulary is
  known, only the YAML needs updating — no Python change is required.
- **Reference**: docs/RESEARCH.md § 1; `bodyloop_anthropometrics/api/export.py`.
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
