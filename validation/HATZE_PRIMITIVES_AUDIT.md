# Numerical Audit — Hatze Geometric Primitive Library (Table A1)

**Audited document:** `docs/HATZE_EQUATIONS.md`, section 2 (primitives A1.1–A1.9)
**Audit script:** `validation/validate_hatze_primitives.py`
**Date:** 2026-09-12
**Method:** two independent numerical engines + closed-form re-derivation

- **Quadrature (reference):** nested adaptive Gauss–Kronrod (`scipy.integrate.quad`).
  Every primitive is inner-simple, so the innermost monomial integral is done
  analytically and a 2-D adaptive quadrature remains. Typical accuracy 1e-10 relative.
- **Monte-Carlo (cross-check):** rejection sampling over the bounding box,
  `N = 10 000 000`, `seed = 20260912`. The MC engine uses *only* each solid's
  `inside()` predicate; the quadrature engine uses *only* its limit functions.
  The two share no code path, so agreement validates the geometric description
  itself. Observed quad-vs-MC agreement: **≤ 0.09 %** for every primitive
  (consistent with the 1/√N MC noise floor).
- **Test dimensions (m):** `a = 0.10`, `b = 0.08`, `h = 0.15`, `c = 0.06`,
  `r = 0.09` (hemisphere), `R = 0.09 / r = 0.05` (A1.6),
  `ℓ = 0.15, b = 0.08, c = 0.05, h = 0.02` (A1.8). `γ = 1000 kg/m³`
  (γ cancels out of every relative comparison).
- **Flag threshold:** relative error > 0.5 %.

---

## 1. Executive summary

| Outcome | Count | Primitives |
|---|---|---|
| Fully verified **as printed** (labels + coefficients) | **3 / 9** | A1.2, A1.5, A1.6 |
| Coefficients correct, **axis labels in the header are wrong** | **5 / 9** | A1.1, A1.3, A1.7, A1.8, A1.9 |
| **Genuinely wrong / unresolved coefficients** | **1 / 9** | A1.4 |

Headline findings:

1. **Every flagged coefficient that the cheatsheet itself marked TODO_VALIDATE is
   fine except A1.4.** The A1.9 hoof coefficients are **exact rationals**:
   `0.0686 = 12/175` and `0.15 = 3/20`. The A1.2 coefficient `12/175` is exact.
   The A1.3 coefficient `0.07` is a 0.18 % rounding of the exact
   `1/4 − 16/(9π²) = 0.06987345`.
2. **A1.4 (octoparaboloid) is the one real error.** Direct integration of the
   printed surface definition gives `M = γ(128/27)abc = 4.74074 γabc`, not
   `4.66493`. All three inertia coefficients are likewise off by 2.4–3.3 %, and
   the value `0.19473` is **structurally unattainable** by any member of the
   surface family the equation belongs to (that coefficient is identically `1/5`).
   Either the surface definition or the coefficients were mis-transcribed.
3. **The audit note in `docs/HATZE_EQUATIONS.md` §6 about A1.3 is itself wrong.**
   It suggests `0.07 ≈ π²/4 − 2` or `1/4 − 1/π² ≈ 0.149`. The correct closed form
   is `1/4 − 16/(9π²) ≈ 0.0699`; the printed `0.07` is right and should be kept
   (preferably replaced by the exact expression).
4. **Five headers assign parameters to the wrong axes.** The inertia formulas are
   internally self-consistent; only the "Parameters: semi-axes a (Y), b (X), …"
   annotation contradicts them. A literal implementation from the header would
   swap `Ī_x` and `Ī_y` — a 20–26 % error on realistic dimensions. These must be
   fixed before the primitives are coded.
5. **A1.7 additionally has a wrong centroid:** printed `z̄ = a/3` must be `z̄ = c/3`
   once the parameters are relabelled (the depth is `c`, not `a`).
6. **A1.8 is a thin-plate approximation** — the `Mh²/12` terms are dropped
   everywhere. At `h = 0.02 m, ℓ = 0.15 m` that is an **8.2 %** error on `Ī_z`;
   it falls below 0.5 % only for `h ≲ 5 mm`. Given that Hatze's foot segment is a
   *wedge*, this is a real modelling limitation, not a typo.

---

## 2. Results table

Relative error is `|cheatsheet − numerical| / |numerical|`. "as printed" means the
solid was built literally in the frame stated in the header line.

| Primitive | Quantity | Cheatsheet value | Numerical (quad) | Rel. error | Status |
|---|---|---|---|---|---|
| **A1.1** Elliptic cylinder | `M = γπabh` | 3.7699112 | 3.7699112 | 0.0000 % | **OK** |
| | `x̄ = ȳ = z̄ = 0` | 0 | 0 | — | **OK** |
| | `Ī_x = M(3b²+h²)/12` (as printed) | 0.01310044 | 0.01649336 | 20.57 % | **WRONG (axis label)** |
| | `Ī_y = M(3a²+h²)/12` (as printed) | 0.01649336 | 0.01310044 | 25.90 % | **WRONG (axis label)** |
| | `Ī_z = M(a²+b²)/4` | 0.01545664 | 0.01545664 | 0.0000 % | **OK** |
| | all three, with `a→X, b→Y` | — | — | 0.0000 % | **OK (relabelled)** |
| **A1.2** Parabolic plate | `M = 4γabh/3` | 1.6 | 1.6 | 0.0000 % | **OK** |
| | `x̄ = −0.4a` | −0.04 | −0.04 | 0.0000 % | **OK** |
| | `Ī_x = M(b²/5 + h²/12)` | 0.00504800 | 0.00504800 | 0.0000 % | **OK** |
| | `Ī_y = M(12a²/175 + h²/12)` | 0.00409714 | 0.00409714 | 0.0000 % | **OK** |
| | `Ī_z = M(12a²/175 + b²/5)` | 0.00314514 | 0.00314514 | 0.0000 % | **OK** |
| **A1.3** Semi-elliptic plate | `M = γπabh/2` | 1.8849556 | 1.8849556 | 0.0000 % | **OK** |
| | `ȳ = −4b/(3π)` | −0.03395306 | −0.03395306 | 0.0000 % | **OK** |
| | `Ī_x` (as printed) | 0.00437875 | 0.00555532 | 21.18 % | **WRONG (axis label)** |
| | `Ī_y = M(a²/4 + h²/12)` | 0.00824668 | 0.00824668 | 0.0000 % | **OK** |
| | `Ī_z` (as printed) | 0.00555685 | 0.00437723 | 26.95 % | **WRONG (axis label)** |
| | coefficient `0.07` vs `1/4−16/(9π²)` | 0.07 | 0.06987345 | 0.181 % | **OK (rounded)** |
| | all three, with `a→X, b→Y, h→Z` | — | — | ≤ 0.035 % | **OK (relabelled)** |
| **A1.4** Octoparaboloid | `M = γ·4.66493·abc` | 2.2391664 | 2.2755556 (`=γ·128/27·abc`) | **1.599 %** | **WRONG** |
| | coefficient of `a²` (`0.211`) | 0.211 | 12/55 = 0.2181818 | **3.29 %** | **WRONG** |
| | coefficient of `b²` (`0.19473`) | 0.19473 | 1/5 = 0.2 | **2.64 %** | **WRONG** |
| | coefficient of `c²` (`0.23511`) | 0.23511 | 512/2125 = 0.2409412 | **2.42 %** | **WRONG** |
| | `Ī_x` | 0.00468583 | 0.00488650 | 4.11 % | **WRONG** |
| | `Ī_y` | 0.00661986 | 0.00693864 | 4.59 % | **WRONG** |
| | `Ī_z` | 0.00751525 | 0.00787756 | 4.60 % | **WRONG** |
| **A1.5** Hemisphere | `M = 2γπr³/3` | 1.5268140 | 1.5268140 | 0.0000 % | **OK** |
| | `z̄ = 3r/8` | 0.03375 | 0.03375 | 0.0000 % | **OK** |
| | `Ī_x = Ī_y = Mr²(2/5 − 9/64)` | 0.00320774 | 0.00320774 | 0.0000 % | **OK** |
| | `Ī_z = 2Mr²/5` | 0.00494688 | 0.00494688 | 0.0000 % | **OK** |
| **A1.6** Hollow half-cylinder | `M = γπh(R²−r²)/2` | 1.3194689 | 1.3194689 | 0.0000 % | **OK** |
| | `x̄ = 4(R³−r³)/[3π(R²−r²)]` | 0.04577599 | 0.04577599 | 0.0000 % | **OK** |
| | `z̄ = h/2` | 0.075 | 0.075 | 0.0000 % | **OK** |
| | `Ī_x = M(R²+r²+h²/3)/4` | 0.00597060 | 0.00597060 | 0.0000 % | **OK** |
| | `Ī_y = Ī_x − Mx̄²` | 0.00320573 | 0.00320573 | 0.0000 % | **OK** |
| | `Ī_z = M((R²+r²)/2 − x̄²)` | 0.00422832 | 0.00422832 | 0.0000 % | **OK** |
| **A1.7** Elliptic paraboloid | `M = γπabc/2` | 0.7539822 | 0.7539822 | 0.0000 % | **OK** |
| | `z̄ = a/3` (as printed) | 0.03333333 | 0.02 (`= c/3`) | **66.7 %** | **WRONG** |
| | `Ī_x` (as printed) | 0.00095504 | 0.00122313 | 21.92 % | **WRONG (axis label)** |
| | `Ī_y` (as printed) | 0.00140743 | 0.00087127 | 61.54 % | **WRONG (axis label)** |
| | `Ī_z` (as printed) | 0.00206088 | 0.00125664 | 64.00 % | **WRONG (axis label)** |
| | all three + `z̄`, with `a→X, b→Y, c→Z` | — | — | 0.0000 % | **OK (relabelled)** |
| **A1.8** Trapezoidal plate | `M = γℓh(b+c)/2` | 0.195 | 0.195 | 0.0000 % | **OK** |
| | `z̄ = ℓ(b+2c)/[3(b+c)]` | 0.06923077 | 0.06923077 | 0.0000 % | **OK** |
| | `Ī_x` (as printed, h = 0.02) | 3.591346e-4 | 4.314471e-4 | 16.76 % | **WRONG (axis label)** |
| | `Ī_y = Ī_x + Ī_z` (as printed) | 4.314471e-4 | 3.656346e-4 | 18.00 % | **WRONG (axis label)** |
| | `Ī_z = M(b²+c²)/24` (as printed) | 7.23125e-5 | 7.88125e-5 | 8.25 % | **WRONG (thin-plate)** |
| | all three, relabelled, `h → 0` | — | — | 0.0000 % | **OK (thin-plate limit)** |
| **A1.9** Ellipto-parabolic hoof | `M = 2γπabh/3` | 2.5132741 | 2.5132741 | 0.0000 % | **OK** |
| | `z̄ = 2h/5` | 0.06 | 0.06 | 0.0000 % | **OK** |
| | `Ī_x` (as printed) | 0.00790048 | 0.00764753 | 3.31 % | **WRONG (axis label)** |
| | `Ī_y` (as printed) | 0.00764915 | 0.00789886 | 3.16 % | **WRONG (axis label)** |
| | `Ī_z = M(0.15a² + b²/4)` | 0.00779115 | 0.00779115 | 0.0000 % | **OK** |
| | coefficient `0.0686` vs `12/175` | 0.0686 | 0.06857143 | 0.042 % | **OK (rounded)** |
| | coefficient `0.15` vs `3/20` | 0.15 | 0.15 | 0.0000 % | **OK (exact)** |
| | all three, with `a→X, b→Y` | — | — | ≤ 0.021 % | **OK (relabelled)** |

Products of inertia vanish to machine precision (`max |Ī_ij| ≤ 1.7e-18` vs
inertia scale `~1e-2`) for all nine primitives, confirming the cheatsheet's claim
that every primitive is in principal axes.

---

## 3. Analytical derivations

Throughout, `k_u² ≡ ∫(u − ū)² dV / V` denotes the centroidal squared radius of
gyration along axis `u`, so that
`Ī_x = M(k_y² + k_z²)`, `Ī_y = M(k_x² + k_z²)`, `Ī_z = M(k_x² + k_y²)`.

### 3.1 A1.1 — Elliptic cylinder (exact)

Solid: `(x/a)² + (y/b)² ≤ 1`, `|z| ≤ h/2`.

```
V   = πabh                                        →  M = γπabh          ✔
k_x² = a²/4,  k_y² = b²/4,  k_z² = h²/12
Ī_x = M(b²/4 + h²/12) = M(3b² + h²)/12                                  ✔
Ī_y = M(a²/4 + h²/12) = M(3a² + h²)/12                                  ✔
Ī_z = M(a² + b²)/4                                                      ✔
```

All three printed formulas are exact **provided `a` is the X semi-axis and `b`
the Y semi-axis** — the opposite of what the header states.

### 3.2 A1.5 — Hemisphere (exact)

Solid: `x² + y² + z² ≤ r²`, `z ≥ 0`.

```
V  = 2πr³/3                                       →  M = 2γπr³/3        ✔
z̄  = (∫z dV)/V = (πr⁴/4)/(2πr³/3) = 3r/8                                ✔
I_z = 2Mr²/5              (same as the full sphere, by symmetry)         ✔
I_x about the flat-face centre = 2Mr²/5
Ī_x = 2Mr²/5 − M z̄² = Mr²(2/5 − 9/64)                                   ✔
```

### 3.3 A1.2 — Parabolic plate, coefficient 12/175 (exact)

Place the chord at `x = 0` (half-width `b`) and the apex at `x = −a`, so the
parabola is `y = ± b√(1 + x/a)`, thickness `h` along Z. With `u = 1 + x/a`:

```
A     = ∫_{-a}^{0} 2b√(1+x/a) dx = 2ab ∫₀¹ √u du = 4ab/3
                                                   →  M = 4γabh/3       ✔
∫x dA = −a · 2ab ∫₀¹ (1−u)√u du = −2a²b·(2/3 − 2/5) = −8a²b/15
x̄     = (−8a²b/15)/(4ab/3) = −2a/5 = −0.4a                              ✔
∫x² dA = a²·2ab ∫₀¹ (1−u)²√u du = 2a³b·B(3, 3/2) = 2a³b·16/105 = 32a³b/105
⟨x²⟩  = (32a³b/105)/(4ab/3) = 8a²/35
k_x²  = 8a²/35 − (2a/5)² = (40 − 28)a²/175 = 12a²/175                   ✔ EXACT
∫y² dA = ∫_{-a}^{0} (2/3)(b√(1+x/a))³ dx = (2/3)ab³∫₀¹ u^{3/2} du = 4ab³/15
k_y²  = (4ab³/15)/(4ab/3) = b²/5                                        ✔
k_z²  = h²/12
```

giving exactly the printed `Ī_x = M(b²/5 + h²/12)`,
`Ī_y = M(12a²/175 + h²/12)`, `Ī_z = M(12a²/175 + b²/5)`.
**A1.2 is fully correct, header included.** `12/175 = 0.06857142857`.

### 3.4 A1.3 — Semi-elliptic plate, coefficient 0.07 (exact form)

Half-ellipse `(x/a)² + (y/b)² ≤ 1` restricted to `y ≤ 0`, thickness `h`.

```
A   = πab/2                                       →  M = γπabh/2        ✔
∫y dA = −(2/3)ab²  ⇒  ȳ = −(2/3)ab²/(πab/2) = −4b/(3π)                  ✔
⟨y²⟩ = ½·(πab³/4)/(πab/2) = b²/4          (half of the full ellipse)
k_y² = b²/4 − (4b/(3π))² = b²(1/4 − 16/(9π²)) = 0.06987345 b²           ✔
k_x² = a²/4        (symmetric direction, unaffected by the cut)
k_z² = h²/12
```

The printed `0.07` therefore approximates the exact `1/4 − 16/(9π²)` to
**0.18 %** — acceptable but worth replacing by the exact expression.

> **Correction to `docs/HATZE_EQUATIONS.md` §6:** the audit note there proposes
> `0.07 ≈ π²/4 − 2 ≈ 0.4674` or `1/4 − 1/π² ≈ 0.149`. Both are wrong; the value
> `0.07` is correct and the exact constant is `1/4 − 16/(9π²)`.

### 3.5 A1.9 — Ellipto-parabolic hoof: 0.0686 and 0.15 are EXACT

The cheatsheet gives the hoof only by name. Its printed values pin the solid
uniquely. Take

```
solid:   0 ≤ z ≤ h,   (x/(a·k))² ≤ 1 − z/h,   k = √(1 − (y/b)²)
```

i.e. cross-sections at height `z` are ellipses with **X semi-axis
`a√(1 − z/h)`** (parabolic taper, `z = h(1 − (x/(ak))²)`) and **constant Y
semi-axis `b`**; equivalently, it is the exponent-2, single-sided member of the
A1.4 surface family. Then, writing `s(z) = √(1 − z/h)`, the cross-sectional
area is `A(z) = πab·s(z)` and:

```
V     = πab ∫₀ʰ (1 − z/h)^{1/2} dz = πab·(2h/3) = 2πabh/3
                                                   →  M = 2γπabh/3      ✔
z̄     = ∫z(1−z/h)^{1/2} dz / ∫(1−z/h)^{1/2} dz = h·(4/15)/(2/3) = 2h/5  ✔
⟨z²⟩  = h²·B(3, 3/2)/B(1, 3/2) = h²·(16/105)/(2/3) = 8h²/35
k_z²  = 8h²/35 − 4h²/25 = 12h²/175 = 0.0685714 h²                       ✔ EXACT
k_y²  = b²/4                (Y semi-axis constant → full-ellipse value)  ✔ EXACT
k_x²  = (a²/4)·∫(1−z/h)^{3/2}dz / ∫(1−z/h)^{1/2}dz
      = (a²/4)·(2/5)/(2/3) = 3a²/20 = 0.15 a²                           ✔ EXACT
```

**Conclusion: `0.0686 = 12/175` (printed to 0.042 %) and `0.15 = 3/20` (exact).**
Both TODO_VALIDATE flags on A1.9 can be closed. Note the coefficient `0.15`
belongs to the **tapering** semi-axis and `b²/4` to the **constant** one; the
header's `a (Y), b (X)` must be swapped to `a (X), b (Y)` for the printed
`Ī_x`/`Ī_y` to be right.

Note also that `12/175` is the *same* constant as in A1.2 — both solids have a
mass distribution `∝ (1 − t)^{1/2}` along the affected axis.

### 3.6 A1.4 — Elliptic octoparaboloid: literal integration

Printed surface: `z = ±ck(1 − (x/(ak))⁸)`, `k = √(1 − (y/b)²)`, so the solid is

```
|y| ≤ b,   |x| ≤ a·k,   |z| ≤ c·k·(1 − (x/(ak))⁸)
```

With `u = x/(ak)`, `v = y/b`, and `∫_{-1}^{1}(1−u⁸)du = 16/9`:

```
V   = ∫_{-b}^{b} 2ck·(ak)·(16/9) dy = (32/9)ac ∫_{-b}^{b} k² dy
    = (32/9)ac·(4b/3) = (128/27)abc = 4.7407407 abc
```

against the printed `4.66493` → **1.60 % too small**.

```
∫_{-1}^{1} u²(1−u⁸) du = 16/33
k_x² = (16/33)·(9/16)·[J(4)/J(2)]·a² = 12a²/55 = 0.2181818 a²
       where J(m) = ∫_{-1}^{1}(1−v²)^{m/2} dv
k_y² = b²/5 = 0.2 b²          (mass per unit y ∝ k², independent of the exponent)
∫_{-1}^{1}(1−u⁸)³ du = 2048/1275
k_z² = (2048/1275)·(9/48)·[J(4)/J(2)]·c² = 512c²/2125 = 0.2409412 c²
```

versus the printed `0.211`, `0.19473`, `0.23511` → **3.29 %, 2.64 %, 2.42 %**
too small. Monte-Carlo (10 M samples) reproduces the quadrature values to
0.02 %, so the closed forms above are the true properties of the printed solid.

**Why this cannot be repaired by re-reading the exponents.** Consider the family

```
|x| ≤ a k^α,   |z| ≤ c k^β (1 − (x/(a k^α))^n),   k = √(1 − (y/b)²)
```

Within it, `k_y² = b²/(α + β + 3)` — it depends *only* on `α + β`, never on `n`.
So `k_y²` can only be `b²/5` (α+β = 2), `b²/4` (α+β = 1) or `b²/3` (α+β = 0);
**`0.19473` is unattainable**. Fitting `n` independently to each printed number
(with α = β = 1) gives

| fitted from | `M` | `k_x²` | `k_y²` | `k_z²` |
|---|---|---|---|---|
| effective `n` | 6.979 | 6.581 | — (impossible) | 6.403 |

A single solid would yield one `n`. The best single hypothesis in the whole
scan (α = β = 1, n = 6) is still 2.7 % off, and the literal n = 8 is 3.4 % off.

**Verdict: WRONG / UNRESOLVED.** Either the printed surface equation or the four
coefficients were mis-transcribed from Hatze (1979). The only self-consistent
values currently derivable are the literal ones:

```
M   = γ(128/27)abc                       ( = 4.7407407 γabc )
Ī_x = M(b²/5     + 512c²/2125)
Ī_y = M(12a²/55  + 512c²/2125)
Ī_z = M(12a²/55  + b²/5)
```

These should **not** be adopted without checking the original report: the A1.9
cross-check shows Hatze's `k` does *not* scale the z-amplitude for the hoof
(β = 0), which makes the `ck` in the printed A1.4 equation itself suspect.
Under β = 0 the literal values would instead be `M = γ(16π/9)abc`,
`k_x² = 9a²/44`, `k_y² = b²/4`, `k_z² = 0.30118 c²` — even further from print.

**Action:** keep the A1.4 TODO_VALIDATE flag open; do not implement A1.4 until
Hatze (1979) Table A1 is obtained.

### 3.7 A1.7 — Elliptic paraboloid

Solid: `0 ≤ z ≤ d` (depth `d`), `(x/p)² + (y/q)² ≤ 1 − z/d`.

```
V    = πpq·d/2                                     →  M = γπ p q d/2
z̄    = d/3
k_x² = (p²/4)·∫(1−t)²dt/∫(1−t)dt = p²/6,   k_y² = q²/6
k_z² = d²[∫t²(1−t)dt/∫(1−t)dt] − d²/9 = d²/6 − d²/9 = d²/18
Ī_x  = M(q²/6 + d²/18) = M(3q² + d²)/18
Ī_y  = M(p²/6 + d²/18) = M(3p² + d²)/18
Ī_z  = M(p² + q²)/6
```

Matching to the printed `Ī_x = M(3b²+c²)/18`, `Ī_y = M(3a²+c²)/18`,
`Ī_z = M(a²+b²)/6` forces `p = a (X)`, `q = b (Y)`, `d = c (Z depth)`.
The printed header (`a (Z, depth), b (Y), c (X)`) and the printed
`z̄ = a/3` are therefore both **wrong**; the centroid must read **`z̄ = c/3`**.
With the relabelling, all four quantities verify to 0.0000 %.

### 3.8 A1.8 — Thin trapezoidal plate

Plate of length `ℓ` along Z, **full** width `w(z) = b + (c − b)z/ℓ` (`b` at
`z = 0`, `c` at `z = ℓ`), thickness `h` along the plate normal.

```
A    = ℓ(b+c)/2                                    →  M = γℓh(b+c)/2    ✔
z̄    = ℓ(b + 2c)/[3(b + c)]                                             ✔
k_z² = ℓ²(b² + 4bc + c²)/[18(b + c)²]                                   ✔
∫y²dA = ∫₀^ℓ w³/12 dz = ℓ(b+c)(b²+c²)/48  ⇒  k_width² = (b²+c²)/24      ✔
```

Two caveats:

- **`b` and `c` are FULL widths, not half-widths.** This is pinned by
  `M = γℓh(b+c)/2`; using half-widths doubles the mass.
- **The `Mh²/12` terms are omitted.** `Ī_y = Ī_x + Ī_z` is the perpendicular-axis
  theorem, valid only in the thin-plate limit, and it identifies **Y** as the
  plate normal — i.e. the thickness `h` is along **Y**, not X as the header says,
  and `Ī_x` / `Ī_y` are swapped relative to the header. Convergence of the
  printed formulas as the plate is thinned (ℓ = 0.15, b = 0.08, c = 0.05):

  | `h` (m) | max rel. error on (Ī_x, Ī_y, Ī_z) |
  |---|---|
  | 0.020 | 8.247 % |
  | 0.005 | 0.559 % |
  | 0.001 | 0.023 % |
  | 1e-5 | 0.000 % |

  Hatze's foot segment is a *wedge* of finite thickness, so this approximation
  is a genuine modelling error there, not a transcription problem. If A1.8 is
  used for the foot, add `Mh²/12` to `Ī_x` and `Ī_z` (and use
  `Ī_y = k_x² + k_z²` directly).

### 3.9 A1.6 — Hollow right circular half-cylinder (exact)

Half-annulus `r ≤ ρ ≤ R`, `x ≥ 0`, `0 ≤ z ≤ h`.

```
A    = π(R² − r²)/2                                →  M = γπh(R²−r²)/2  ✔
x̄    = [ (2/3)(R³−r³) ] / [ π(R²−r²)/2 ] = 4(R³−r³)/[3π(R²−r²)]         ✔
⟨y²⟩ = ⟨x²⟩ = (R⁴−r⁴)/4 · (π/2) / [π(R²−r²)/2] = (R²+r²)/4
Ī_x  = M[(R²+r²)/4 + h²/12] = M(R² + r² + h²/3)/4                       ✔
Ī_y  = M[(R²+r²)/4 + h²/12 − x̄²] = Ī_x − M x̄²                          ✔
Ī_z  = M[(R²+r²)/2 − x̄²]                                               ✔
```

Fully correct, header included.

---

## 4. Recommended corrections to `docs/HATZE_EQUATIONS.md`

| # | Primitive | Correction |
|---|---|---|
| 1 | A1.1 | Header must read **`a (X), b (Y)`**, height `h (Z)`. |
| 2 | A1.3 | Header must read **`a (X), b (Y)` (body in `y ≤ 0`), thickness `h (Z)`**. Replace `0.07` by the exact `1/4 − 16/(9π²) = 0.0698734513`. |
| 3 | A1.3 §6 note | Delete the "likely `1/4 − 1/π² ≈ 0.149`" claim — it is wrong. |
| 4 | A1.4 | Keep TODO_VALIDATE **open**. Record that literal integration gives `M = γ(128/27)abc`, `k_x² = 12a²/55`, `k_y² = b²/5`, `k_z² = 512c²/2125`, and that `0.19473` is unattainable for this surface family. **Do not implement until Hatze (1979) is obtained.** |
| 5 | A1.7 | Header must read **`a (X), b (Y), c (Z, paraboloid depth)`**, and the centroid must read **`z̄ = c/3`** (not `a/3`). |
| 6 | A1.8 | Header must read thickness **`h (Y)`** (widths `b`, `c` along X), state that `b, c` are **full** widths, and flag that `Ī` are thin-plate values missing `Mh²/12`. |
| 7 | A1.9 | Header must read **`a (X, parabolic taper), b (Y), h (Z)`**. Close TODO_VALIDATE: `0.0686 = 12/175` and `0.15 = 3/20`, both exact. Record the reconstructed solid `(x/(a·k))² ≤ 1 − z/h`, `k = √(1−(y/b)²)`. |
| 8 | §6 audit table | Remove the A1.2 row — `12/175` is exact and verified. |

---

## 5. Reproducing this audit

```bash
python validation/validate_hatze_primitives.py
```

Runtime ≈ 2 min (dominated by the 10 M-sample Monte-Carlo over 14 solids).
Output is deterministic (`seed = 20260912`).
