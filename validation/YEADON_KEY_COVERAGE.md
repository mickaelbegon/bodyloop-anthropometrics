# Yeadon 95-Measurement Key Coverage Validation

**Report generated:** 2026-09-12  
**yeadon package version:** >=1.3  
**Configuration:** `configs/bodyloop_to_yeadon.yaml`

---

## Executive Summary

All **95 measurement keys** required by the Yeadon (1990) 17-segment anthropometric model are present in the BodyLoop-to-Yeadon mapping configuration. The mapping is **complete and correct**:

- **Total expected by yeadon:** 95
- **Total in YAML configuration:** 95
- **Correctly mapped:** 95 (100%)
- **Extra keys (ERROR):** 0
- **Missing keys (WARNING):** 0

**Status:** ✓ PASS — No typos, no missing coverage, no extra keys.

---

## Measurement Distribution

| Region | Segment | Count | All Verified |
|--------|---------|-------|--------------|
| Torso + Head-Neck | Ls | 21 | ✓ |
| Left Arm | La | 18 | ✓ |
| Right Arm | Lb | 18 | ✓ |
| Left Leg | Lj | 19 | ✓ |
| Right Leg | Lk | 19 | ✓ |
| **Total** | | **95** | **✓** |

---

## Source Type Distribution

| Source Type | Count | Percentage |
|-------------|-------|-----------|
| **calculated** | 60 | 63.2% |
| **direct** | 21 | 22.1% |
| **interpolated** | 14 | 14.7% |
| **Total** | 95 | 100.0% |

**Note:** "Calculated" measurements derive from anatomical landmarks or geometric relationships. "Direct" measurements read directly from BodyLoop data. "Interpolated" measurements fall back to interpolation if direct measurements are unavailable.

---

## Manual Validation Status

| Status | Count | Percentage |
|--------|-------|-----------|
| Manual validation **required** | 65 | 68.4% |
| Manual validation **not required** | 30 | 31.6% |

**Important:** The high proportion of measurements marked `manual_validation_required: true` reflects anatomical landmarks that have no unambiguous optical-scan definition (hip joint centre, shoulder joint centre, acromion, crotch, heel, foot arch, nipple, base of thumb, lowest anterior rib). These must be digitised or confirmed on real scans against Yeadon (1990) Table 1 and Figure 1. See SCIENCE_DECISIONS.md, entry "Yeadon difficult anatomical landmarks."

---

## Complete Key Coverage Table

### Torso and Head-Neck (Ls) — 21 measurements

| Key | Source Type | Manual | bodyloop_path | Notes |
|-----|-------------|--------|---------------|-------|
| Ls1L | calculated | ✓ | null | Hip to umbilicus distance |
| Ls2L | calculated | ✓ | null | Hip to lowest front rib |
| Ls3L | calculated | ✓ | null | Hip to nipple level |
| Ls4L | calculated | ✓ | null | Hip to shoulder joint centre |
| Ls5L | calculated | ✓ | null | Hip to acromion |
| Ls6L | calculated | ✓ | null | Acromion to below nose |
| Ls7L | calculated | ✓ | null | Acromion to above ear |
| Ls8L | calculated | ✓ | null | Acromion to top of head |
| Ls0p | calculated | ✓ | null | Perimeter at hip joint centre |
| Ls1p | direct | ✗ | crosssections.umbilicus.convex_m | Perimeter at umbilicus |
| Ls2p | calculated | ✓ | null | Perimeter at lowest front rib |
| Ls3p | interpolated | ✓ | crosssections.nipple.convex_m | Perimeter at nipple |
| Ls5p | interpolated | ✓ | crosssections.neck_base.convex_m | Perimeter at acromion |
| Ls6p | interpolated | ✗ | crosssections.below_nose.convex_m | Perimeter at below nose |
| Ls7p | direct | ✗ | crosssections.head_max.convex_m | Perimeter at head max |
| Ls0w | calculated | ✓ | null | Medio-lateral width at hip centre |
| Ls1w | direct | ✗ | crosssections.umbilicus.width_ml_m | Width at umbilicus |
| Ls2w | calculated | ✓ | null | Width at lowest front rib |
| Ls3w | interpolated | ✓ | crosssections.nipple.width_ml_m | Width at nipple |
| Ls4w | calculated | ✓ | null | Width at shoulder joint centre |
| Ls4d | calculated | ✓ | null | Antero-posterior depth at Ls4 |

### Left Arm (La) — 18 measurements

| Key | Source Type | Manual | bodyloop_path | Notes |
|-----|-------------|--------|---------------|-------|
| La2L | calculated | ✓ | null | Shoulder to elbow |
| La3L | calculated | ✓ | null | Shoulder to max forearm perimeter |
| La4L | calculated | ✓ | null | Shoulder to wrist |
| La5L | calculated | ✓ | null | Wrist to base of thumb |
| La6L | calculated | ✓ | null | Wrist to knuckles |
| La7L | direct | ✗ | distances.hand_length_left | Wrist to finger nails |
| La0p | calculated | ✓ | null | Perimeter at shoulder centre |
| La1p | calculated | ✗ | null | Perimeter at mid upper-arm (computed level) |
| La2p | interpolated | ✗ | crosssections.elbow_left.convex_m | Perimeter at elbow |
| La3p | direct | ✗ | crosssections.forearm_max_left.convex_m | Max forearm perimeter |
| La4p | direct | ✗ | crosssections.wrist_left.convex_m | Perimeter at wrist |
| La5p | calculated | ✓ | null | Perimeter at base of thumb |
| La6p | interpolated | ✓ | crosssections.knuckles_left.convex_m | Perimeter at knuckles |
| La7p | calculated | ✓ | null | Perimeter at finger nails |
| La4w | direct | ✗ | crosssections.wrist_left.width_ml_m | Width at wrist |
| La5w | calculated | ✓ | null | Width at base of thumb |
| La6w | direct | ✗ | distances.hand_width_left | Width at knuckles |
| La7w | calculated | ✓ | null | Width at finger nails |

### Right Arm (Lb) — 18 measurements

| Key | Source Type | Manual | bodyloop_path | Notes |
|-----|-------------|--------|---------------|-------|
| Lb2L | calculated | ✓ | null | Shoulder to elbow |
| Lb3L | calculated | ✓ | null | Shoulder to max forearm perimeter |
| Lb4L | calculated | ✓ | null | Shoulder to wrist |
| Lb5L | calculated | ✓ | null | Wrist to base of thumb |
| Lb6L | calculated | ✓ | null | Wrist to knuckles |
| Lb7L | direct | ✗ | distances.hand_length_right | Wrist to finger nails |
| Lb0p | calculated | ✓ | null | Perimeter at shoulder centre |
| Lb1p | calculated | ✗ | null | Perimeter at mid upper-arm (computed level) |
| Lb2p | interpolated | ✗ | crosssections.elbow_right.convex_m | Perimeter at elbow |
| Lb3p | direct | ✗ | crosssections.forearm_max_right.convex_m | Max forearm perimeter |
| Lb4p | direct | ✗ | crosssections.wrist_right.convex_m | Perimeter at wrist |
| Lb5p | calculated | ✓ | null | Perimeter at base of thumb |
| Lb6p | interpolated | ✓ | crosssections.knuckles_right.convex_m | Perimeter at knuckles |
| Lb7p | calculated | ✓ | null | Perimeter at finger nails |
| Lb4w | direct | ✗ | crosssections.wrist_right.width_ml_m | Width at wrist |
| Lb5w | calculated | ✓ | null | Width at base of thumb |
| Lb6w | direct | ✗ | distances.hand_width_right | Width at knuckles |
| Lb7w | calculated | ✓ | null | Width at finger nails |

### Left Leg (Lj) — 19 measurements

| Key | Source Type | Manual | bodyloop_path | Notes |
|-----|-------------|--------|---------------|-------|
| Lj1L | calculated | ✓ | null | Hip to crotch |
| Lj3L | calculated | ✓ | null | Hip to knee |
| Lj4L | calculated | ✓ | null | Hip to max calf perimeter |
| Lj5L | calculated | ✓ | null | Hip to ankle |
| Lj6L | calculated | ✓ | null | Ankle to heel |
| Lj8L | calculated | ✓ | null | Ankle to ball of foot |
| Lj9L | calculated | ✓ | null | Ankle to toe nails |
| Lj1p | interpolated | ✓ | crosssections.upper_thigh_left.convex_m | Perimeter at crotch |
| Lj2p | interpolated | ✗ | crosssections.mid_thigh_left.convex_m | Perimeter at mid-thigh (computed level) |
| Lj3p | direct | ✗ | crosssections.knee_left.convex_m | Perimeter at knee |
| Lj4p | direct | ✗ | crosssections.calf_max_left.convex_m | Max calf perimeter |
| Lj5p | direct | ✗ | crosssections.ankle_left.convex_m | Perimeter at ankle |
| Lj6p | calculated | ✓ | null | Perimeter at heel |
| Lj7p | calculated | ✓ | null | Perimeter at arch (computed level) |
| Lj8p | interpolated | ✗ | crosssections.ball_of_foot_left.convex_m | Perimeter at ball of foot |
| Lj9p | calculated | ✓ | null | Perimeter at toe nails |
| Lj8w | direct | ✗ | distances.foot_width_left | Width at ball of foot |
| Lj9w | calculated | ✓ | null | Width at toe nails |
| Lj6d | calculated | ✓ | null | Antero-posterior depth at heel |

### Right Leg (Lk) — 19 measurements

| Key | Source Type | Manual | bodyloop_path | Notes |
|-----|-------------|--------|---------------|-------|
| Lk1L | calculated | ✓ | null | Hip to crotch |
| Lk3L | calculated | ✓ | null | Hip to knee |
| Lk4L | calculated | ✓ | null | Hip to max calf perimeter |
| Lk5L | calculated | ✓ | null | Hip to ankle |
| Lk6L | calculated | ✓ | null | Ankle to heel |
| Lk8L | calculated | ✓ | null | Ankle to ball of foot |
| Lk9L | calculated | ✓ | null | Ankle to toe nails |
| Lk1p | interpolated | ✓ | crosssections.upper_thigh_right.convex_m | Perimeter at crotch |
| Lk2p | interpolated | ✗ | crosssections.mid_thigh_right.convex_m | Perimeter at mid-thigh (computed level) |
| Lk3p | direct | ✗ | crosssections.knee_right.convex_m | Perimeter at knee |
| Lk4p | direct | ✗ | crosssections.calf_max_right.convex_m | Max calf perimeter |
| Lk5p | direct | ✗ | crosssections.ankle_right.convex_m | Perimeter at ankle |
| Lk6p | calculated | ✓ | null | Perimeter at heel |
| Lk7p | calculated | ✓ | null | Perimeter at arch (computed level) |
| Lk8p | interpolated | ✗ | crosssections.ball_of_foot_right.convex_m | Perimeter at ball of foot |
| Lk9p | calculated | ✓ | null | Perimeter at toe nails |
| Lk8w | direct | ✗ | distances.foot_width_right | Width at ball of foot |
| Lk9w | calculated | ✓ | null | Width at toe nails |
| Lk6d | calculated | ✓ | null | Antero-posterior depth at heel |

---

## Key Observations

### 1. Computed Levels in Yeadon

Per the YAML file header (NOTE 3), the following four quantities are **absent from the 95 keys** because yeadon derives them internally:

- **La1 / Lb1:** mid upper-arm level = 0.5 × La2L / Lb2L
- **Lj2 / Lk2:** mid-thigh level = 0.5 × (Lj1L + Lj3L) / (Lk1L + Lk3L)
- **Lj7 / Lk7:** foot-arch level = 0.5 × (Lj6L + Lj8L) / (Lk6L + Lk8L)
- **Lj0p / Lk0p:** crotch perimeter derived from Ls0p and Ls0w

The perimeters at these computed levels **ARE included** in the 95 keys and must be provided as input:

- La1p, Lb1p (at 0.5 × L2L)
- Lj2p, Lk2p (at mid-thigh)
- Lj7p, Lk7p (at foot-arch)
- Lj0p / Lk0p are NOT in the 95 keys; they are computed from torso measurements.

### 2. Convex vs. Perimeter Convention

All perimeter measurements map to the BodyLoop **convex value**, not the raw perimeter contour. This is critical for accuracy: a taut tape follows the convex hull and cannot enter concavities (waist, ankle, wrist, between toes). Using the raw perimeter would overestimate stadium-solid volumes.

See YAML header, NOTE 1: "Perimeter must be the BodyLoop `convex` value, not `perimeter`".

### 3. Difficult Anatomical Landmarks

65 of 95 measurements (68.4%) are marked `manual_validation_required: true`. These depend on anatomical landmarks with no unambiguous optical-scan definition:

- Hip joint centre (Ls0, Lj0, Lk0)
- Shoulder joint centre (Ls4, La0, Lb0)
- Acromion (Ls5)
- Crotch (Lj1, Lk1)
- Heel (Lj6, Lk6)
- Foot arch (Lj7, Lk7)
- Nipple (Ls3)
- Base of thumb (La5, Lb5)
- Lowest anterior rib (Ls2)

**Action required:** No key may be set to `manual_validation_required: false` until its anatomical definition has been confirmed against Yeadon (1990) Table 1 and Figure 1. This is tracked in SCIENCE_DECISIONS.md, entry "Yeadon difficult anatomical landmarks".

### 4. Direct vs. Calculated vs. Interpolated

- **21 direct** measurements are read directly from BodyLoop cross-section or distance data.
- **60 calculated** measurements derive from anatomical landmarks, geometric relationships (e.g., hip joint centre regression), or axial positions of maximal sections.
- **14 interpolated** measurements have a preferred direct BodyLoop measurement but can fall back to interpolation if unavailable.

The balance of calculated vs. direct reflects the Yeadon protocol's focus on anatomical landmarks, which must be registered on the optical scan.

---

## Validation Status by Measurement Type

### OK — All 95 keys present and correctly mapped

- ✓ No extra keys (typos or unmapped measurements)
- ✓ No missing keys (no gaps in coverage)
- ✓ All keys match yeadon.Human.measnames exactly

### WARNING — High proportion of calculations

- ⚠ 60/95 (63.2%) are calculated, not direct measurements
- ⚠ 65/95 (68.4%) require manual validation of anatomical landmarks
- ⚠ Hand and finger geometry (La6p, La7p, Lb6p, Lb7p, Lj9p, Lk9p, and widths) noted as below resolution of full-body optical scanning

**Risk mitigation:** These measurements must be cross-checked on real scans and validated against Yeadon (1990) prior to use in inertial model calculations. See SCIENCE_DECISIONS.md.

---

## Files Validated

- Configuration: `/configs/bodyloop_to_yeadon.yaml` (95 keys)
- Yeadon package: `yeadon >= 1.3` (measnames tuple: 95 keys)
- Validation date: 2026-09-12

---

## Recommendations

1. **Continue with confidence:** All 95 keys are correctly mapped. The YAML configuration is ready for use.

2. **Prioritize manual validation:** Focus validation efforts on the 65 measurements marked `manual_validation_required: true`, especially joint centres (hip, shoulder, wrist, knee, ankle) and difficult landmarks (acromion, crotch, heel, arch).

3. **Quantify hand/finger geometry:** The notes for La5-La7 and Lb5-Lb7 measurements (and Lj9, Lk9) warn that finger geometry is below the resolution of full-body optical scanning. Empirical validation on a sample of real BodyLoop scans is recommended.

4. **Cross-reference Yeadon (1990):** Before finalizing any landmark definition, confirm it against:
   - M.R. Yeadon (1990). Table 1 (measurement names and definitions)
   - M.R. Yeadon (1990). Figure 1 (graphical landmarks)

5. **Track landmark definitions:** Update SCIENCE_DECISIONS.md as each anatomical landmark is validated, and flip `manual_validation_required` to `false` once confirmed.

---

## Summary for SCIENCE_DECISIONS.md

**Entry:** "Yeadon 95-measurement key coverage — validation status"

**Status:** COMPLETE ✓

The BodyLoop-to-Yeadon measurement mapping configuration (`configs/bodyloop_to_yeadon.yaml`) provides complete coverage of all 95 measurements required by the Yeadon (1990) 17-segment anthropometric model. No keys are missing, and no extra keys are present.

**Source breakdown:**
- 21 direct (BodyLoop measurements directly usable)
- 60 calculated (anatomical landmarks, geometric derivations, interpolations)
- 14 interpolated (with direct measurement fallback)

**Critical dependency:** 65 of 95 measurements depend on anatomical landmarks with no unambiguous optical-scan definition (hip joint centre, shoulder joint centre, acromion, crotch, heel, foot arch, nipple, base of thumb, lowest anterior rib). All such measurements are marked `manual_validation_required: true` in the YAML configuration. Validation against Yeadon (1990) Table 1 and Figure 1 is required before these keys may be used in production calculations.

**Perimeter convention:** All perimeter measurements are mapped to the BodyLoop **convex** value (following the convex hull), not the raw perimeter contour, as specified in Yeadon's protocol.

**Recommendation:** Proceed with data processing for measurement extraction. Parallel validation effort should focus on confirming anatomical landmark definitions on real BodyLoop scans.
