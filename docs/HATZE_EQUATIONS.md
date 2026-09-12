# Hatze Cheatsheet — Extracted Equations

**Source:** `wspr/hatze-biomech` repository, `hatze-cheatsheet.pdf`  
**Extraction date:** 2026-09-12  
**Pages read:** 1–11 (image-based PDF, rendered at 2.5× and read visually)  
**Validation status:** NUMERICALLY AUDITED 2026-09-12 — see `validation/HATZE_PRIMITIVES_AUDIT.md`  
**Audit method:** Two independent engines — nested adaptive Gauss–Kronrod quadrature (1e-10 accuracy)  
and 10M-sample Monte-Carlo rejection sampling. Full derivations in the audit file.

> ⚠️ **Scientific caveat:** The `hatze-biomech` repository README explicitly states that
> some equations are incomplete or incorrect. Every equation below must be verified
> against the original publication before use:
>
> Hatze, H. (1979). A model for the computational determination of parameter values
> of anthropomorphic segments. CSIR Technical Report TWISK 79, Pretoria, South Africa.
>
> See `SCIENCE_DECISIONS.md` for the audit tracking.

---

## 1. Model Structure

The Hatze model comprises **17 body segments** with local coordinate systems
(O_i, X_i, Y_i, Z_i) for i = 1, …, 17 (Figure 1a of the cheatsheet).

The configuration of the hominoid is described by **42 generalized coordinates**
q_i, i = 1, …, 42 (Figure 1 of the cheatsheet).

### Segment numbering

| No. | Segment | Primitive(s) |
|-----|---------|-------------|
| 1 | Abdomino-thoracic trunk | Stacked elliptic cylinders (i=1…10) with hollow lung cavities (A1.6) |
| 2 | Head-neck | Truncated ellipsoid (parameters a, b, c, k, h) |
| 3 | Left shoulder | Composite shape |
| 4 | Right shoulder | Composite shape |
| 5 | Left forearm | Series of elliptic sections |
| 6 | Right forearm | Series of elliptic sections |
| 7 | Left upper arm | Series of 10 elliptic cross-sections (Fig. F2.5) |
| 8 | Right upper arm | Series of 10 elliptic cross-sections |
| 9 | Left hand | Composite hoof + plate |
| 10 | Right hand | Composite hoof + plate |
| 11 | Abdomino-pelvic segment | Composite with proportions 0.3ℓ, 0.437ℓ, 0.874ℓ |
| 12 | Right thigh | Truncated elliptic cone, 10 cross-sections (Fig. F2.11) |
| 13 | Right shank | Truncated cone, circular distal section radius r |
| 14 | Right foot | Trapezoidal wedge plate, divisions ℓ/3 |
| 15 | Left thigh | Truncated elliptic cone, 10 cross-sections |
| 16 | Left shank | Truncated cone, circular distal section radius r (Fig. F2.12) |
| 17 | Left foot | Trapezoidal wedge plate (Fig. F2.13) |

---

## 2. Geometric Primitive Library (Table A1)

Notation:
- γ = volumetric density [kg/m³]
- Ī_x, Ī_y, Ī_z = principal moments of inertia about centroid G [kg·m²]
- x̄, ȳ, z̄ = centroid coordinates relative to local origin
- All products of inertia are zero for all primitives listed (bodies are symmetric)

### A1.1 — Elliptic Cylinder

Parameters: semi-axes **a (X)**, **b (Y)**, height h (Z)

> ⚠️ **AUDIT CORRECTION:** The cheatsheet header stated `a (Y), b (X)` — that is wrong.
> The inertia formulas are internally consistent only with **a = X semi-axis, b = Y semi-axis**.
> A literal reading of the header would swap Ī_x and Ī_y (~21–26 % error).

```
M  = γπabh
x̄ = ȳ = z̄ = 0

Ī_x = M(3b² + h²) / 12      [b = Y semi-axis; verified exact]
Ī_y = M(3a² + h²) / 12      [a = X semi-axis; verified exact]
Ī_z = M(a² + b²)  / 4       [verified exact]
```

*Used for: trunk slices, limb cross-sections*

---

### A1.2 — Parabolic Plate

Parameters: semi-axes a (X, parabola depth), b (Y), thickness h (Z)

```
M  = 4γabh / 3
x̄ = −0.4a,   ȳ = z̄ = 0

Ī_x = M(b²/5      + h²/12)     [verified exact]
Ī_y = M(12a²/175  + h²/12)     [12/175 is EXACT — derived via Beta functions; verified]
Ī_z = M(12a²/175  + b²/5)      [verified exact]
```

*Fully verified — axis labels correct. 12/175 = 0.068571… exact.*

---

### A1.3 — Semi-elliptic Plate

Parameters: semi-axes **a (X)**, **b (Y)**, thickness **h (Z)**

> ⚠️ **AUDIT CORRECTION:** The cheatsheet header stated `a (Z), b (Y), h (X)` — that is wrong.
> The formulas are consistent only with **a = X semi-axis, b = Y, h = Z thickness**.
> Axis swap would cause ~21–27 % errors on Ī_x and Ī_z.

```
M  = γabhπ / 2
x̄ = 0,   ȳ = −4b/(3π),   z̄ = 0

Ī_x = M((1/4 − 16/(9π²))b² + h²/12)   [exact; 0.07 ≈ 0.06987, 0.18 % rounding — acceptable]
Ī_y = M(a²/4 + h²/12)                  [verified exact]
Ī_z = M(a²/4 + (1/4 − 16/(9π²))b²)    [exact]
```

---

### A1.4 — Elliptic Octoparaboloid

Parameters: semi-axes a (X), b (Y), c (Z half-depth)

Surface definition:
```
z = ±ck(1 − (x/(ak))⁸),   for z ≥ 0
where k = (1 − (y/b)²)^(1/2)
```

> ❌ **AUDIT FINDING — GENUINELY WRONG COEFFICIENTS.** Direct numerical integration
> of the surface definition above gives values **inconsistent** with the printed
> coefficients. The value 0.19473 for b² is **structurally unattainable** by any
> member of this surface family (it is identically 1/5 = 0.2 for all n and α, β).
>
> **Corrected values from integration of the printed surface:**
> ```
> M  = γ × (128/27) × abc = γ × 4.74074 × abc   [printed: 4.66493 — error −1.60 %]
> k_y² = b²/5 = 0.2                               [printed: 0.19473 — structurally wrong]
> k_x² = 12a²/55 ≈ 0.21818a²                      [printed: 0.211a² — error −3.29 %]
> k_z² = 512c²/2125 ≈ 0.24094c²                   [printed: 0.23511c² — error −2.42 %]
> ```
>
> **Either the surface equation or the printed coefficients were mis-transcribed.**
> The printed numbers do not correspond to *any* single solid in the stated family.
>
> ⛔ **DO NOT IMPLEMENT A1.4 without verifying against Hatze (1979) original.**
> Mark all code using these coefficients with `TODO_SCIENTIFIC`.

*Used for: trunk and torso slices*

---

### A1.5 — Hemisphere

Parameters: radius r

```
M  = γ × 2πr³ / 3
x̄ = ȳ = 0,   z̄ = 3r/8

Ī_x = Ī_y = Mr²(2/5 − 9/64)
Ī_z = 2Mr² / 5
```

---

### A1.6 — Hollow Right Circular Half-Cylinder

Parameters: outer radius R, inner radius r, height h (along Z)

```
M  = γπh(R² − r²) / 2
x̄ = 4(R³ − r³) / [3π(R² − r²)]
ȳ = 0,   z̄ = h/2

Ī_x = M(R² + r² + h²/3) / 4
Ī_y = Ī_x − Mx̄²
Ī_z = M((R² + r²)/2 − x̄²)
```

*Used for: lung cavity correction in thorax segment*

---

### A1.7 — Elliptic Paraboloid

Parameters: semi-axes **a (X)**, **b (Y)**, **c (Z, paraboloid depth)**

> ⚠️ **AUDIT CORRECTIONS:**
> 1. The cheatsheet header stated `a (Z), b (Y), c (X)` — wrong. Consistent labelling is **a = X, b = Y, c = Z depth**.
> 2. The centroid was printed as `z̄ = a/3`. **WRONG.** The correct centroid is `z̄ = c/3` (depth axis).

```
M  = γπabc / 2
x̄ = ȳ = 0,   z̄ = c/3             [corrected from a/3; verified exact]

Ī_x = M(3b² + c²) / 18            [verified exact in corrected frame]
Ī_y = M(3a² + c²) / 18            [verified exact in corrected frame]
Ī_z = M(a²  + b²) / 6             [verified exact]
```

---

### A1.8 — Thin Trapezoidal Plate

Parameters: length ℓ (Z), parallel sides **b** (proximal, full width) and **c** (distal, full width), thickness h (Y)

> ⚠️ **AUDIT FINDINGS:**
> 1. **Thin-plate approximation** — all `Mh²/12` terms are dropped. At h = 20 mm, ℓ = 150 mm: error on Ī_z ≈ 8.2 %. Falls below 0.5 % only for h ≲ 5 mm. Real foot segments are thicker; this is a modelling limitation, not a typo.
> 2. **Axis label**: thickness is along Y (not X). Swap would produce ~17–18 % errors.
> 3. **b and c are FULL widths** (pinned by M = γℓh(b+c)/2), not semi-widths.

```
M  = γℓh(b + c) / 2
x̄ = 0,   z̄ = ℓ(b + 2c) / [3(b + c)]      [verified exact]

Ī_x = Mℓ²(b² + 4bc + c²) / [18(b + c)²]   [verified; thin-plate limit exact]
Ī_z = M(b² + c²) / 24                       [verified; thin-plate; 8 % error for h = 20 mm]
Ī_y = Ī_x + Ī_z                             [by perpendicular axis theorem for thin plate]
```

*Used for: foot segment*

---

### A1.9 — Ellipto-parabolic Hoof

Parameters: semi-axes **a (X)**, **b (Y)**, height h (Z)

> ⚠️ **AUDIT CORRECTION:** The cheatsheet header stated `a (Y), b (X)` — wrong. Consistent
> frame is **a = X, b = Y**. Axis swap would cause ~3 % errors on Ī_x/Ī_y.

Solid definition (reconstructed from coefficients):
```
0 ≤ z ≤ h,  (x/(a·k))² ≤ 1 − z/h,  k = √(1 − (y/b)²)
```

```
M  = γ × 2πabh / 3
x̄ = ȳ = 0,   z̄ = 2h/5              [verified exact]

Ī_x = M(b²/4 + (12/175)h²)          [0.0686 = 12/175 EXACTLY; verified]
Ī_y = M((3/20)a² + (12/175)h²)      [0.15 = 3/20 EXACTLY; verified]
Ī_z = M((3/20)a² + b²/4)            [verified exact; 0.0 % error]
```

*Both TODO_VALIDATE flags CLOSED — coefficients are exact rational numbers.*

---

## 3. Segment Geometry Figures (F2.1–F2.13)

### Trunk — Segment 1 (Fig. F2.1, F2.2)

- Composed of 10 stacked slices (i = 1, …, 10), each of height ℓ/10
- Each slice i has elliptic cross-section with semi-axes a_i (ML) and b_i (AP)
- Two lung cavities modeled as hollow half-cylinders (A1.6), symmetrically placed
  at distance d/2 from the Z-axis, radius r, starting at ℓ/3 from distal end
- Parameters per slice: a_i, b_i, w_i (wall thickness), c_i (inner core semi-axis)
- Origin O_1 at base (distal end), Z_1 pointing superiorly

### Head-Neck — Segment 2 (Fig. F2.3)

- Truncated ellipsoid: semi-axes a (X), b (Y), c (Z, superior half)
- Truncation at height k from inferior pole
- Lower cylinder of height h and elliptic base a₁ × b₁

### Shoulder — Segments 3, 7 (Fig. F2.4)

- Composite curved shape with angle θ_7
- Half-width 2b, arc length d
- Inner volume O_8 with semi-axis b₁
- Auxiliary frame Z_h at superior boundary

### Upper Arm — Segments 8, 5 (Fig. F2.5)

- Series of 10 elliptic cross-sections (i = 1, …, 10) of height ℓ/10
- Semi-axes a_i (anterior-posterior) and b_i (medial-lateral) vary along length
- Origin O_9 at distal end

### Forearm — Segments 9, 6 (Fig. F2.6)

- Similar to upper arm: 10 elliptic cross-sections
- Origin O_10 at distal end, Z axis pointing proximally

### Hand — Segments 10, 9 (Fig. F2.7)

- Composite: body = Ellipto-parabolic Hoof (A1.9) with arc length 0.378h
- Coordinate frame rotated by angle θ
- Dimensions: 2b (width), d (length of palm), b₁ (wrist semi-axis)

### Pelvis — Segment 11 (Figs. F2.8, F2.9, F2.10)

- Complex shape with proportional dimensions along ℓ:
  - Superior boundary at 0.3ℓ
  - Centroid landmark at 0.437ℓ
  - Iliac crest at 0.874ℓ
  - Pubic offset 0.037ℓ
  - Distal neck O_11 at 0.7ℓ
- Cross-section (Fig. F2.10): width 2ca_h, inner dimensions a_i, b_i, offset g

### Thigh — Segments 15, 12 (Fig. F2.11)

- Truncated elliptic cone with 10 cross-sections (i = 1, …, 10)
- Semi-axes a_i (AP), b_i (ML) vary linearly from proximal to distal
- Origin O_16 at distal end; distal slice height ℓ/10

### Shank — Segments 16, 13 (Fig. F2.12)

- Truncated cone tapering to circular distal cross-section of radius r
- Proximal: elliptic section; distal: circular (radius r)
- Origin O_17 at distal (ankle) end

### Foot — Segments 17, 14 (Fig. F2.13)

- Trapezoidal wedge (A1.8) with three regions along length ℓ:
  - Heel: ℓ/3, thickness h₁ to h₂
  - Mid: ℓ/3 (central region)
  - Toe: ℓ/3, tapering
- Width b (medial-lateral), depth c (toe side), height h₁ (heel), h₂ (forefoot)
- Rotation angle θ_17 relative to segment frame Z_17

---

## 4. Reference Output — Subject R. Marga (Appendix 4)

**Demographics:** Female, age 31, measured mass 64.7 kg

**Computed totals:** Volume = 63.8 L, mass = 64.42 kg (error < 0.5%)

### Segment inertial parameters (centroidal, principal axes)

| Segment | Volume (L) | Mass (kg) | COM_z (m) | Ix (kg·m²) | Iy (kg·m²) | Iz (kg·m²) |
|---------|-----------|-----------|-----------|-----------|-----------|-----------|
| Abd.-thoracic | 14.537 | 12.950 | 0.194 | 0.2069 | 0.2315 | 0.0829 |
| Head-neck | 3.595 | 3.993 | 0.132 | 0.0209 | 0.0176 | 0.0127 |
| Left shoulder | 1.110 | 1.144 | 0.140 | 0.0027 | 0.0022 | 0.0244 |
| Right shoulder | 1.146 | 1.180 | 0.141 | 0.0029 | 0.0023 | 0.0256 |
| Left arm | 1.016 | 1.713 | −0.131 | 0.0137 | 0.0134 | 0.0010 |
| Right arm | 1.505 | 1.595 | −0.129 | 0.0119 | 0.0115 | 0.0013 |
| Left forearm | 0.835 | 0.896 | −0.108 | 0.0046 | 0.0045 | 0.0003 |
| Right forearm | 0.809 | 0.869 | −0.112 | 0.0048 | 0.0046 | 0.0005 |
| Left hand | 0.288 | 0.317 | −0.010 | 0.0002 | 0.0004 | 0.0013 |
| Right hand | 0.288 | 0.319 | −0.009 | 0.0002 | 0.0005 | 0.0014 |
| Abd.-pelvic | 11.208 | 11.304 | −0.050 | 0.0689 | 0.1234 | 0.1516 |
| Left thigh | 9.166 | 9.593 | −0.194 | 0.1563 | 0.1525 | 0.5122 |
| Right thigh | 8.955 | 9.375 | −0.194 | 0.1492 | 0.1469 | 0.4983 |
| Left shank | 3.310 | 3.602 | −0.174 | 0.0453 | 0.0450 | 0.1543 |
| Right shank | 3.487 | 3.794 | −0.183 | 0.0505 | 0.0501 | 0.1772 |
| Left foot | 0.842 | 0.961 | −0.040 | 0.0036 | 0.0038 | 0.0053 |
| Right foot | 0.887 | 1.020 | −0.038 | 0.0038 | 0.0039 | 0.0054 |

---

## 5. What this cheatsheet does NOT contain

The cheatsheet provides:
- The geometric primitive library (A1.1–A1.9)
- The segment geometry figures
- One worked example

It does **not** provide:
- The full 242-measurement input specification per segment
- The equations mapping each measurement to primitive parameters (a, b, c, r, h, ℓ, …)
- The density model and subcutaneous fat correction
- The lung volume integration formula

These require the original publication:

> Hatze, H. (1979). A model for the computational determination of parameter values
> of anthropomorphic segments. CSIR Technical Report TWISK 79, Pretoria, South Africa.

And the follow-up:

> Hatze, H. (1980). A mathematical model for the computational determination of
> parameter values of anthropomorphic segments. Journal of Biomechanics, 13(10), 833–843.

---

## 6. Audit summary — 2026-09-12 (see `validation/HATZE_PRIMITIVES_AUDIT.md`)

**Method:** two independent numerical engines (adaptive quadrature 1e-10 + 10M-point Monte-Carlo).

| Primitive | Status | Issue |
|-----------|--------|-------|
| A1.1 Elliptic Cylinder | ✅ Coefficients correct | Header labels swapped: a = X (not Y), b = Y (not X) |
| A1.2 Parabolic Plate | ✅ Fully correct | No issues; 12/175 is exact |
| A1.3 Semi-elliptic Plate | ✅ Coefficients correct | Header labels swapped; 0.07 = 1/4−16/(9π²) to 0.18 % |
| A1.4 Octoparaboloid | ❌ **WRONG** | All 4 coefficients wrong (1.6–3.3 %); 0.19473 structurally unattainable. Do not implement without Hatze 1979. |
| A1.5 Hemisphere | ✅ Fully correct | No issues |
| A1.6 Hollow Half-Cylinder | ✅ Fully correct | No issues |
| A1.7 Elliptic Paraboloid | ✅ Coefficients correct | Header labels swapped; centroid was **a/3 → must be c/3** |
| A1.8 Trapezoidal Plate | ⚠️ Thin-plate approx. | Drops Mh²/12; 8 % error at realistic foot thickness; axis label swap |
| A1.9 Ellipto-parabolic Hoof | ✅ Fully correct | Header labels swapped; 0.0686 = 12/175, 0.15 = 3/20 (exact rationals) |

**Previous TODO_VALIDATE flags — resolution:**
- A1.9 (0.0686, 0.15): **CLOSED** — both exact rationals, verified numerically
- A1.2 (12/175): **CLOSED** — exact, derived via Beta functions
- A1.3 (0.07): **CLOSED** — 0.07 ≈ 1/4 − 16/(9π²) = 0.06987, 0.18 % rounding
- A1.4 (all coefficients): **OPEN** — printed values are wrong; require Hatze (1979)

See `SCIENCE_DECISIONS.md` for the decision log.
