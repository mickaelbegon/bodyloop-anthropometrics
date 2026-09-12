r"""Numerical audit of the Hatze (1979) geometric primitive library (Table A1).

This script independently re-derives, for each of the nine primitives A1.1-A1.9
transcribed in ``docs/HATZE_EQUATIONS.md``:

* the mass ``M = gamma * V``,
* the centroid ``(xbar, ybar, zbar)``,
* the centroidal principal moments of inertia ``(Ix, Iy, Iz)``,
* the centroidal products of inertia (symmetry check),

and compares them against the cheatsheet formulas.

Two independent numerical engines are used:

``quad``
    Nested adaptive Gauss-Kronrod quadrature (``scipy.integrate.quad``).  Every
    primitive is "inner-simple": the innermost integration variable has limits
    that are closed-form functions of the two outer variables, so the innermost
    integral of a monomial is done analytically and only a 2-D adaptive
    quadrature remains.  This is the *reference* engine (typically 1e-10
    relative accuracy).

``mc``
    Rejection Monte-Carlo over an axis-aligned bounding box with 10,000,000
    samples and a fixed seed.  This is an *independent* cross-check that shares
    no code path with the quadrature engine: it only uses each primitive's
    ``inside()`` predicate, whereas the quadrature engine only uses each
    primitive's limit functions.  Agreement between the two therefore validates
    the geometric description itself, not just the integration.

Each primitive is built in the coordinate frame **as literally stated in the
cheatsheet header line** ("Parameters: semi-axes a (Y), b (X), ...").  When a
printed inertia triple does not match the numerical triple directly, the script
searches the six axis permutations to report whether the discrepancy is a pure
axis-labelling error (recoverable) or a genuine numerical error.

Run::

    python validation/validate_hatze_primitives.py

Notes
-----
gamma (density) cancels out of every relative comparison; gamma = 1000 kg/m^3
is used for concreteness.  All lengths are in metres.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import permutations

import numpy as np
from scipy import integrate, special

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #

GAMMA = 1000.0  # kg / m^3
SEED = 20260912
N_MC = 10_000_000
MC_CHUNK = 500_000
TOL = 5.0e-3  # 0.5 % relative-error flag threshold

# Representative test dimensions (metres)
A = 0.10
B = 0.08
H = 0.15
C = 0.06
R_HEMI = 0.09
R_OUT = 0.09
R_IN = 0.05
ELL = 0.15
B_TRAP = 0.08
C_TRAP = 0.05
H_TRAP = 0.02

MOMENT_KEYS = [
    (0, 0, 0),
    (1, 0, 0),
    (0, 1, 0),
    (0, 0, 1),
    (2, 0, 0),
    (0, 2, 0),
    (0, 0, 2),
    (1, 1, 0),
    (1, 0, 1),
    (0, 1, 1),
]

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


# --------------------------------------------------------------------------- #
# Primitive description                                                        #
# --------------------------------------------------------------------------- #


@dataclass
class Primitive:
    """A solid described both by integration limits and by a membership test.

    Parameters
    ----------
    key : str
        Cheatsheet identifier, e.g. ``"A1.1"``.
    name : str
        Human-readable name.
    frame : str
        The axis assignment as printed in the cheatsheet header.
    order : tuple of str
        Integration order ``(outer, mid, inner)``, a permutation of
        ``("x", "y", "z")``.
    outer : tuple of float
        Limits of the outer variable.
    mid : callable
        ``mid(u) -> (v0, v1)`` limits of the middle variable.
    inner : callable
        ``inner(u, v) -> (w0, w1)`` limits of the inner variable.
    inside : callable
        Vectorised ``inside(x, y, z) -> bool array`` membership predicate.
    bbox : tuple
        ``((x0, x1), (y0, y1), (z0, z1))`` bounding box for Monte-Carlo.
    expected : dict
        Cheatsheet values, keys among ``M``, ``xbar``, ``ybar``, ``zbar``,
        ``Ix``, ``Iy``, ``Iz``.
    outer_points, mid_points : callable or None
        Optional break points handed to ``quad`` for non-smooth integrands.
    notes : str
        Free-form commentary reproduced in the report.
    """

    key: str
    name: str
    frame: str
    order: tuple[str, str, str]
    outer: tuple[float, float]
    mid: Callable[[float], tuple[float, float]]
    inner: Callable[[float, float], tuple[float, float]]
    inside: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]
    bbox: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    expected: dict[str, float]
    outer_points: list[float] | None = None
    mid_points: Callable[[float], list[float]] | None = None
    notes: str = ""
    symbolic: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Integration engines                                                          #
# --------------------------------------------------------------------------- #


def raw_moments_quad(prim: Primitive) -> dict[tuple[int, int, int], float]:
    """Compute raw geometric moments ``integral of x^p y^q z^r dV`` by quadrature.

    The innermost integral of a monomial is evaluated in closed form, leaving a
    two-dimensional adaptive quadrature.

    Parameters
    ----------
    prim : Primitive
        Primitive whose limit functions are used.

    Returns
    -------
    dict
        Mapping ``(p, q, r) -> moment value``.
    """
    o_u, o_v, o_w = prim.order
    out: dict[tuple[int, int, int], float] = {}

    for key in MOMENT_KEYS:
        p = {"x": key[0], "y": key[1], "z": key[2]}
        pu, pv, pw = p[o_u], p[o_v], p[o_w]

        def inner_line(u: float, v: float, pw: int = pw) -> float:
            w0, w1 = prim.inner(u, v)
            if w1 <= w0:
                return 0.0
            return (w1 ** (pw + 1) - w0 ** (pw + 1)) / (pw + 1)

        def mid_line(u: float, pv: int = pv, pw: int = pw) -> float:
            v0, v1 = prim.mid(u)
            if v1 <= v0:
                return 0.0
            pts = prim.mid_points(u) if prim.mid_points is not None else None
            pts = [q for q in pts if v0 < q < v1] if pts else None
            val, _ = integrate.quad(
                lambda v: v**pv * inner_line(u, v),
                v0,
                v1,
                limit=400,
                epsabs=1e-14,
                epsrel=1e-12,
                points=pts,
            )
            return val

        u0, u1 = prim.outer
        pts = prim.outer_points
        pts = [q for q in pts if u0 < q < u1] if pts else None
        val, _ = integrate.quad(
            lambda u: u**pu * mid_line(u),
            u0,
            u1,
            limit=400,
            epsabs=1e-14,
            epsrel=1e-12,
            points=pts,
        )
        out[key] = val

    return out


def raw_moments_mc(prim: Primitive, n: int = N_MC) -> dict[tuple[int, int, int], float]:
    """Compute raw geometric moments by rejection Monte-Carlo.

    Parameters
    ----------
    prim : Primitive
        Primitive whose ``inside`` predicate and bounding box are used.
    n : int
        Total number of bounding-box samples.

    Returns
    -------
    dict
        Mapping ``(p, q, r) -> moment value``.
    """
    rng = np.random.default_rng(SEED)
    (x0, x1), (y0, y1), (z0, z1) = prim.bbox
    v_box = (x1 - x0) * (y1 - y0) * (z1 - z0)

    acc = {key: 0.0 for key in MOMENT_KEYS}
    n_hit = 0
    done = 0
    while done < n:
        m = min(MC_CHUNK, n - done)
        done += m
        x = rng.uniform(x0, x1, m)
        y = rng.uniform(y0, y1, m)
        z = rng.uniform(z0, z1, m)
        sel = prim.inside(x, y, z)
        x, y, z = x[sel], y[sel], z[sel]
        n_hit += x.size
        if x.size == 0:
            continue
        acc[(0, 0, 0)] += float(x.size)
        acc[(1, 0, 0)] += float(x.sum())
        acc[(0, 1, 0)] += float(y.sum())
        acc[(0, 0, 1)] += float(z.sum())
        acc[(2, 0, 0)] += float((x * x).sum())
        acc[(0, 2, 0)] += float((y * y).sum())
        acc[(0, 0, 2)] += float((z * z).sum())
        acc[(1, 1, 0)] += float((x * y).sum())
        acc[(1, 0, 1)] += float((x * z).sum())
        acc[(0, 1, 1)] += float((y * z).sum())

    scale = v_box / n
    return {k: v * scale for k, v in acc.items()}


def inertial_properties(moments: dict[tuple[int, int, int], float]) -> dict[str, float]:
    r"""Convert raw geometric moments into mass, centroid and centroidal inertia.

    Parameters
    ----------
    moments : dict
        Raw moments ``integral of x^p y^q z^r dV``.

    Returns
    -------
    dict
        Keys ``V``, ``M``, ``xbar``, ``ybar``, ``zbar``, ``Ix``, ``Iy``, ``Iz``,
        ``Ixy``, ``Ixz``, ``Iyz``.
    """
    v = moments[(0, 0, 0)]
    xb = moments[(1, 0, 0)] / v
    yb = moments[(0, 1, 0)] / v
    zb = moments[(0, 0, 1)] / v
    m = GAMMA * v

    # centroidal second moments of the volume
    mxx = moments[(2, 0, 0)] - v * xb * xb
    myy = moments[(0, 2, 0)] - v * yb * yb
    mzz = moments[(0, 0, 2)] - v * zb * zb
    mxy = moments[(1, 1, 0)] - v * xb * yb
    mxz = moments[(1, 0, 1)] - v * xb * zb
    myz = moments[(0, 1, 1)] - v * yb * zb

    return {
        "V": v,
        "M": m,
        "xbar": xb,
        "ybar": yb,
        "zbar": zb,
        "Ix": GAMMA * (myy + mzz),
        "Iy": GAMMA * (mxx + mzz),
        "Iz": GAMMA * (mxx + myy),
        "Ixy": -GAMMA * mxy,
        "Ixz": -GAMMA * mxz,
        "Iyz": -GAMMA * myz,
    }


# --------------------------------------------------------------------------- #
# Primitive definitions (built in the cheatsheet's *printed* axis frame)       #
# --------------------------------------------------------------------------- #


def _ell(u: float, semi: float) -> float:
    """Return ``sqrt(max(0, 1 - (u/semi)**2))``."""
    t = 1.0 - (u / semi) ** 2
    return math.sqrt(t) if t > 0.0 else 0.0


def build_primitives() -> list[Primitive]:
    """Instantiate all nine primitives with the representative test dimensions.

    Returns
    -------
    list of Primitive
    """
    prims: list[Primitive] = []

    # ---------------- A1.1 Elliptic cylinder -------------------------------- #
    # Header: semi-axes a (Y), b (X), height h (Z)  ->  x-semi-axis = b,
    # y-semi-axis = a, z in [-h/2, h/2].
    m1 = GAMMA * math.pi * A * B * H
    prims.append(
        Primitive(
            key="A1.1",
            name="Elliptic Cylinder",
            frame="a -> Y semi-axis, b -> X semi-axis, h -> Z height (as printed)",
            order=("x", "y", "z"),
            outer=(-B, B),
            mid=lambda x: (-A * _ell(x, B), A * _ell(x, B)),
            inner=lambda x, y: (-H / 2, H / 2),
            inside=lambda x, y, z: ((x / B) ** 2 + (y / A) ** 2 <= 1.0) & (np.abs(z) <= H / 2),
            bbox=((-B, B), (-A, A), (-H / 2, H / 2)),
            expected={
                "M": m1,
                "xbar": 0.0,
                "ybar": 0.0,
                "zbar": 0.0,
                "Ix": m1 * (3 * B**2 + H**2) / 12,
                "Iy": m1 * (3 * A**2 + H**2) / 12,
                "Iz": m1 * (A**2 + B**2) / 4,
            },
            symbolic={
                "M": "gamma*pi*a*b*h",
                "Ix": "M(3b^2+h^2)/12",
                "Iy": "M(3a^2+h^2)/12",
                "Iz": "M(a^2+b^2)/4",
            },
            notes="Standard solid; exact closed form known.",
        )
    )

    # ---------------- A1.2 Parabolic plate ---------------------------------- #
    # Header: a (X, parabola depth), b (Y), thickness h (Z).
    # Chord at x = 0 (half-width b), apex at x = -a, so xbar = -0.4 a.
    m2 = GAMMA * 4 * A * B * H / 3
    prims.append(
        Primitive(
            key="A1.2",
            name="Parabolic Plate",
            frame="a -> X (depth, apex at x=-a, chord at x=0), b -> Y, h -> Z",
            order=("x", "y", "z"),
            outer=(-A, 0.0),
            mid=lambda x: (
                -B * math.sqrt(max(0.0, 1 + x / A)),
                B * math.sqrt(max(0.0, 1 + x / A)),
            ),
            inner=lambda x, y: (-H / 2, H / 2),
            inside=lambda x, y, z: (
                (x >= -A) & (x <= 0.0) & ((y / B) ** 2 <= 1 + x / A) & (np.abs(z) <= H / 2)
            ),
            bbox=((-A, 0.0), (-B, B), (-H / 2, H / 2)),
            expected={
                "M": m2,
                "xbar": -0.4 * A,
                "ybar": 0.0,
                "zbar": 0.0,
                "Ix": m2 * (B**2 / 5 + H**2 / 12),
                "Iy": m2 * (12 * A**2 / 175 + H**2 / 12),
                "Iz": m2 * (12 * A**2 / 175 + B**2 / 5),
            },
            symbolic={
                "M": "4*gamma*a*b*h/3",
                "xbar": "-0.4a",
                "Ix": "M(b^2/5+h^2/12)",
                "Iy": "M(12a^2/175+h^2/12)",
                "Iz": "M(12a^2/175+b^2/5)",
            },
            notes="Parabolic segment y = +/- b*sqrt(1+x/a); 12/175 derived analytically.",
        )
    )

    # ---------------- A1.3 Semi-elliptic plate ------------------------------ #
    # Header: semi-axes a (Z), b (Y), thickness h (X); flat side at y = 0,
    # body occupying y <= 0 so that ybar = -4b/(3 pi).
    m3 = GAMMA * A * B * H * math.pi / 2
    prims.append(
        Primitive(
            key="A1.3",
            name="Semi-elliptic Plate",
            frame="a -> Z semi-axis, b -> Y semi-axis (y<=0), h -> X thickness (as printed)",
            order=("z", "y", "x"),
            outer=(-A, A),
            mid=lambda z: (-B * _ell(z, A), 0.0),
            inner=lambda z, y: (-H / 2, H / 2),
            inside=lambda x, y, z: (
                ((z / A) ** 2 + (y / B) ** 2 <= 1.0) & (y <= 0.0) & (np.abs(x) <= H / 2)
            ),
            bbox=((-H / 2, H / 2), (-B, 0.0), (-A, A)),
            expected={
                "M": m3,
                "xbar": 0.0,
                "ybar": -4 * B / (3 * math.pi),
                "zbar": 0.0,
                "Ix": m3 * (0.07 * B**2 + H**2 / 12),
                "Iy": m3 * (A**2 / 4 + H**2 / 12),
                "Iz": m3 * (A**2 / 4 + 0.07 * B**2),
            },
            symbolic={
                "M": "gamma*a*b*h*pi/2",
                "ybar": "-4b/(3pi)",
                "Ix": "M(0.07b^2+h^2/12)",
                "Iy": "M(a^2/4+h^2/12)",
                "Iz": "M(a^2/4+0.07b^2)",
            },
            notes="Exact coefficient is 1/4 - 16/(9 pi^2) = 0.0698733; 0.07 is a rounding.",
        )
    )

    # ---------------- A1.4 Elliptic octoparaboloid -------------------------- #
    # Header: a (X), b (Y), c (Z half-depth);
    # literal surface: z = +/- c k (1 - (x/(a k))^8), k = sqrt(1-(y/b)^2).
    m4 = GAMMA * 4.66493 * A * B * C
    prims.append(
        Primitive(
            key="A1.4",
            name="Elliptic Octoparaboloid",
            frame="a -> X, b -> Y, c -> Z half-depth (as printed)",
            order=("y", "x", "z"),
            outer=(-B, B),
            mid=lambda y: (-A * _ell(y, B), A * _ell(y, B)),
            inner=lambda y, x: _octo_zlim(y, x),
            inside=_octo_inside,
            bbox=((-A, A), (-B, B), (-C, C)),
            expected={
                "M": m4,
                "xbar": 0.0,
                "ybar": 0.0,
                "zbar": 0.0,
                "Ix": m4 * (0.19473 * B**2 + 0.23511 * C**2),
                "Iy": m4 * (0.211 * A**2 + 0.23511 * C**2),
                "Iz": m4 * (0.211 * A**2 + 0.19473 * B**2),
            },
            symbolic={
                "M": "gamma*4.66493*a*b*c",
                "Ix": "M(0.19473b^2+0.23511c^2)",
                "Iy": "M(0.211a^2+0.23511c^2)",
                "Iz": "M(0.211a^2+0.19473b^2)",
            },
            notes="Literal reading of the printed surface equation.",
        )
    )

    # ---------------- A1.5 Hemisphere --------------------------------------- #
    r = R_HEMI
    m5 = GAMMA * 2 * math.pi * r**3 / 3
    prims.append(
        Primitive(
            key="A1.5",
            name="Hemisphere",
            frame="radius r, flat face in z = 0, body in z >= 0",
            order=("x", "y", "z"),
            outer=(-r, r),
            mid=lambda x: (-r * _ell(x, r), r * _ell(x, r)),
            inner=lambda x, y: (0.0, math.sqrt(max(0.0, r * r - x * x - y * y))),
            inside=lambda x, y, z: (x**2 + y**2 + z**2 <= r * r) & (z >= 0.0),
            bbox=((-r, r), (-r, r), (0.0, r)),
            expected={
                "M": m5,
                "xbar": 0.0,
                "ybar": 0.0,
                "zbar": 3 * r / 8,
                "Ix": m5 * r**2 * (2 / 5 - 9 / 64),
                "Iy": m5 * r**2 * (2 / 5 - 9 / 64),
                "Iz": 2 * m5 * r**2 / 5,
            },
            symbolic={
                "M": "2*gamma*pi*r^3/3",
                "zbar": "3r/8",
                "Ix": "M r^2 (2/5-9/64)",
                "Iz": "2 M r^2/5",
            },
            notes="Standard solid; exact closed form known.",
        )
    )

    # ---------------- A1.6 Hollow right circular half-cylinder -------------- #
    rr, ri = R_OUT, R_IN
    m6 = GAMMA * math.pi * H * (rr**2 - ri**2) / 2
    xbar6 = 4 * (rr**3 - ri**3) / (3 * math.pi * (rr**2 - ri**2))
    ix6 = m6 * (rr**2 + ri**2 + H**2 / 3) / 4
    prims.append(
        Primitive(
            key="A1.6",
            name="Hollow Right Circular Half-Cylinder",
            frame="outer R, inner r, height h along Z (z in [0,h]), half x >= 0",
            order=("y", "x", "z"),
            outer=(-rr, rr),
            mid=lambda y: (
                math.sqrt(max(0.0, ri * ri - y * y)),
                math.sqrt(max(0.0, rr * rr - y * y)),
            ),
            inner=lambda y, x: (0.0, H),
            inside=lambda x, y, z: (
                (x**2 + y**2 <= rr * rr)
                & (x**2 + y**2 >= ri * ri)
                & (x >= 0.0)
                & (z >= 0.0)
                & (z <= H)
            ),
            bbox=((0.0, rr), (-rr, rr), (0.0, H)),
            outer_points=[-ri, ri],
            expected={
                "M": m6,
                "xbar": xbar6,
                "ybar": 0.0,
                "zbar": H / 2,
                "Ix": ix6,
                "Iy": ix6 - m6 * xbar6**2,
                "Iz": m6 * ((rr**2 + ri**2) / 2 - xbar6**2),
            },
            symbolic={
                "M": "gamma*pi*h*(R^2-r^2)/2",
                "xbar": "4(R^3-r^3)/(3pi(R^2-r^2))",
                "Ix": "M(R^2+r^2+h^2/3)/4",
                "Iy": "Ix - M xbar^2",
                "Iz": "M((R^2+r^2)/2 - xbar^2)",
            },
            notes="Standard solid; exact closed form known.",
        )
    )

    # ---------------- A1.7 Elliptic paraboloid ------------------------------ #
    # Header: a (Z, paraboloid depth), b (Y), c (X).
    # Solid: z in [0,a], (x/c)^2 + (y/b)^2 <= 1 - z/a.
    m7 = GAMMA * math.pi * A * B * C / 2
    prims.append(
        Primitive(
            key="A1.7",
            name="Elliptic Paraboloid",
            frame="a -> Z depth, b -> Y semi-axis, c -> X semi-axis (as printed)",
            order=("z", "x", "y"),
            outer=(0.0, A),
            mid=lambda z: (
                -C * math.sqrt(max(0.0, 1 - z / A)),
                C * math.sqrt(max(0.0, 1 - z / A)),
            ),
            inner=lambda z, x: _parab_ylim(z, x),
            inside=lambda x, y, z: (
                (z >= 0.0) & (z <= A) & ((x / C) ** 2 + (y / B) ** 2 <= np.maximum(0.0, 1 - z / A))
            ),
            bbox=((-C, C), (-B, B), (0.0, A)),
            expected={
                "M": m7,
                "xbar": 0.0,
                "ybar": 0.0,
                "zbar": A / 3,
                "Ix": m7 * (3 * B**2 + C**2) / 18,
                "Iy": m7 * (3 * A**2 + C**2) / 18,
                "Iz": m7 * (A**2 + B**2) / 6,
            },
            symbolic={
                "M": "gamma*pi*a*b*c/2",
                "zbar": "a/3",
                "Ix": "M(3b^2+c^2)/18",
                "Iy": "M(3a^2+c^2)/18",
                "Iz": "M(a^2+b^2)/6",
            },
            notes="Paraboloid axis along Z with depth a, base semi-axes c (X) and b (Y).",
        )
    )

    # ---------------- A1.8 Thin trapezoidal plate --------------------------- #
    # Header: length l (Z), parallel sides b (proximal, z=0) and c (distal,
    # z=l), thickness h (X).  Widths are laid along Y.
    lt, bt, ct, ht = ELL, B_TRAP, C_TRAP, H_TRAP
    m8 = GAMMA * lt * ht * (bt + ct) / 2
    ix8 = m8 * lt**2 * (bt**2 + 4 * bt * ct + ct**2) / (18 * (bt + ct) ** 2)
    iz8 = m8 * (bt**2 + ct**2) / 24
    prims.append(
        Primitive(
            key="A1.8",
            name="Thin Trapezoidal Plate",
            frame="l -> Z, widths b (z=0) and c (z=l) along Y, h -> X thickness (as printed)",
            order=("z", "y", "x"),
            outer=(0.0, lt),
            mid=lambda z: _trap_ylim(z, lt, bt, ct),
            inner=lambda z, y: (-ht / 2, ht / 2),
            inside=lambda x, y, z: (
                (z >= 0.0)
                & (z <= lt)
                & (np.abs(y) <= 0.5 * (bt + (ct - bt) * z / lt))
                & (np.abs(x) <= ht / 2)
            ),
            bbox=((-ht / 2, ht / 2), (-max(bt, ct) / 2, max(bt, ct) / 2), (0.0, lt)),
            expected={
                "M": m8,
                "xbar": 0.0,
                "ybar": 0.0,
                "zbar": lt * (bt + 2 * ct) / (3 * (bt + ct)),
                "Ix": ix8,
                "Iy": ix8 + iz8,
                "Iz": iz8,
            },
            symbolic={
                "M": "gamma*l*h*(b+c)/2",
                "zbar": "l(b+2c)/(3(b+c))",
                "Ix": "M l^2 (b^2+4bc+c^2)/(18(b+c)^2)",
                "Iz": "M(b^2+c^2)/24",
                "Iy": "Ix+Iz",
            },
            notes="b and c are the full widths; thin-plate limit (h^2/12 terms dropped).",
        )
    )

    # ---------------- A1.9 Ellipto-parabolic hoof --------------------------- #
    # Header: semi-axes a (Y), b (X), height h (Z).
    # Solid reconstructed as the exponent-2 member of the A1.4 family, with the
    # parabolic taper along the "a" direction (Y per the printed header):
    #   z in [0, h],  (y/(a k))^2 <= 1 - z/h,  k = sqrt(1 - (x/b)^2)
    m9 = GAMMA * 2 * math.pi * A * B * H / 3
    prims.append(
        Primitive(
            key="A1.9",
            name="Ellipto-parabolic Hoof",
            frame="a -> Y (parabolic taper), b -> X, h -> Z height (as printed)",
            order=("x", "z", "y"),
            outer=(-B, B),
            mid=lambda x: (0.0, H),
            inner=_hoof_ylim,
            inside=_hoof_inside,
            bbox=((-B, B), (-A, A), (0.0, H)),
            expected={
                "M": m9,
                "xbar": 0.0,
                "ybar": 0.0,
                "zbar": 2 * H / 5,
                "Ix": m9 * (B**2 / 4 + 0.0686 * H**2),
                "Iy": m9 * (0.15 * A**2 + 0.0686 * H**2),
                "Iz": m9 * (0.15 * A**2 + B**2 / 4),
            },
            symbolic={
                "M": "2*gamma*pi*a*b*h/3",
                "zbar": "2h/5",
                "Ix": "M(b^2/4+0.0686h^2)",
                "Iy": "M(0.15a^2+0.0686h^2)",
                "Iz": "M(0.15a^2+b^2/4)",
            },
            notes="Exact coefficients are 12/175 = 0.0685714 and 3/20 = 0.15.",
        )
    )

    return prims


# --- helper limit/membership functions (module level so they stay picklable) - #


def _octo_zlim(y: float, x: float) -> tuple[float, float]:
    """z-limits of the literal A1.4 octoparaboloid at (x, y)."""
    k = _ell(y, B)
    if k <= 0.0:
        return (0.0, 0.0)
    t = 1.0 - (x / (A * k)) ** 8
    if t <= 0.0:
        return (0.0, 0.0)
    zz = C * k * t
    return (-zz, zz)


def _octo_inside(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Membership predicate of the literal A1.4 octoparaboloid."""
    k = np.sqrt(np.clip(1.0 - (y / B) ** 2, 0.0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        u = np.where(k > 0, x / (A * np.where(k > 0, k, 1.0)), np.inf)
    t = 1.0 - u**8
    zz = np.where((k > 0) & (t > 0), C * k * t, 0.0)
    return np.abs(z) <= zz


def _parab_ylim(z: float, x: float) -> tuple[float, float]:
    """y-limits of the A1.7 elliptic paraboloid at (x, z)."""
    t = 1.0 - z / A - (x / C) ** 2
    if t <= 0.0:
        return (0.0, 0.0)
    yy = B * math.sqrt(t)
    return (-yy, yy)


def _trap_ylim(z: float, lt: float, bt: float, ct: float) -> tuple[float, float]:
    """y-limits (half-width) of the A1.8 trapezoidal plate at height z."""
    w = 0.5 * (bt + (ct - bt) * z / lt)
    return (-w, w)


def _hoof_ylim(x: float, z: float) -> tuple[float, float]:
    """y-limits of the A1.9 hoof at (x, z)."""
    k = _ell(x, B)
    t = 1.0 - z / H
    if k <= 0.0 or t <= 0.0:
        return (0.0, 0.0)
    yy = A * k * math.sqrt(t)
    return (-yy, yy)


def _hoof_inside(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Membership predicate of the A1.9 hoof."""
    k2 = np.clip(1.0 - (x / B) ** 2, 0.0, None)
    t = np.clip(1.0 - z / H, 0.0, None)
    return (z >= 0.0) & (z <= H) & (y**2 <= (A**2) * k2 * t)


def _hoof_c_xlim(y: float, z: float) -> tuple[float, float]:
    """x-limits of the corrected-frame A1.9 hoof (taper along X) at (y, z)."""
    k = _ell(y, B)
    t = 1.0 - z / H
    if k <= 0.0 or t <= 0.0:
        return (0.0, 0.0)
    xx = A * k * math.sqrt(t)
    return (-xx, xx)


def _hoof_c_inside(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Membership predicate of the corrected-frame A1.9 hoof."""
    k2 = np.clip(1.0 - (y / B) ** 2, 0.0, None)
    t = np.clip(1.0 - z / H, 0.0, None)
    return (z >= 0.0) & (z <= H) & (x**2 <= (A**2) * k2 * t)


def _parab_c_ylim(z: float, x: float) -> tuple[float, float]:
    """y-limits of the corrected-frame A1.7 paraboloid (depth c along Z)."""
    t = 1.0 - z / C - (x / A) ** 2
    if t <= 0.0:
        return (0.0, 0.0)
    yy = B * math.sqrt(t)
    return (-yy, yy)


def build_corrected_primitives(h_thin: float = 1.0e-5) -> list[Primitive]:
    """Re-instantiate the five suspect primitives in their *corrected* frames.

    The corrected frame is the axis assignment under which the printed inertia
    triple becomes self-consistent (see ``HATZE_PRIMITIVES_AUDIT.md``).

    Parameters
    ----------
    h_thin : float
        Plate thickness used for the A1.8 thin-plate limit check.

    Returns
    -------
    list of Primitive
    """
    prims: list[Primitive] = []

    m1 = GAMMA * math.pi * A * B * H
    prims.append(
        Primitive(
            key="A1.1c",
            name="Elliptic Cylinder (corrected: a -> X, b -> Y)",
            frame="a -> X semi-axis, b -> Y semi-axis, h -> Z",
            order=("x", "y", "z"),
            outer=(-A, A),
            mid=lambda x: (-B * _ell(x, A), B * _ell(x, A)),
            inner=lambda x, y: (-H / 2, H / 2),
            inside=lambda x, y, z: ((x / A) ** 2 + (y / B) ** 2 <= 1.0) & (np.abs(z) <= H / 2),
            bbox=((-A, A), (-B, B), (-H / 2, H / 2)),
            expected={
                "M": m1,
                "Ix": m1 * (3 * B**2 + H**2) / 12,
                "Iy": m1 * (3 * A**2 + H**2) / 12,
                "Iz": m1 * (A**2 + B**2) / 4,
            },
        )
    )

    m3 = GAMMA * A * B * H * math.pi / 2
    prims.append(
        Primitive(
            key="A1.3c",
            name="Semi-elliptic Plate (corrected: a -> X, b -> Y, h -> Z)",
            frame="a -> X semi-axis, b -> Y semi-axis (y<=0), h -> Z thickness",
            order=("x", "y", "z"),
            outer=(-A, A),
            mid=lambda x: (-B * _ell(x, A), 0.0),
            inner=lambda x, y: (-H / 2, H / 2),
            inside=lambda x, y, z: (
                ((x / A) ** 2 + (y / B) ** 2 <= 1.0) & (y <= 0.0) & (np.abs(z) <= H / 2)
            ),
            bbox=((-A, A), (-B, 0.0), (-H / 2, H / 2)),
            expected={
                "M": m3,
                "ybar": -4 * B / (3 * math.pi),
                "Ix": m3 * (0.07 * B**2 + H**2 / 12),
                "Iy": m3 * (A**2 / 4 + H**2 / 12),
                "Iz": m3 * (A**2 / 4 + 0.07 * B**2),
            },
        )
    )

    m7 = GAMMA * math.pi * A * B * C / 2
    prims.append(
        Primitive(
            key="A1.7c",
            name="Elliptic Paraboloid (corrected: a -> X, b -> Y, c -> Z depth)",
            frame="a -> X, b -> Y, c -> Z depth; zbar = c/3 (NOT a/3)",
            order=("z", "x", "y"),
            outer=(0.0, C),
            mid=lambda z: (
                -A * math.sqrt(max(0.0, 1 - z / C)),
                A * math.sqrt(max(0.0, 1 - z / C)),
            ),
            inner=_parab_c_ylim,
            inside=lambda x, y, z: (
                (z >= 0.0) & (z <= C) & ((x / A) ** 2 + (y / B) ** 2 <= np.maximum(0.0, 1 - z / C))
            ),
            bbox=((-A, A), (-B, B), (0.0, C)),
            expected={
                "M": m7,
                "zbar": C / 3,
                "Ix": m7 * (3 * B**2 + C**2) / 18,
                "Iy": m7 * (3 * A**2 + C**2) / 18,
                "Iz": m7 * (A**2 + B**2) / 6,
            },
            notes="zbar corrected from a/3 to c/3.",
        )
    )

    lt, bt, ct, ht = ELL, B_TRAP, C_TRAP, h_thin
    m8 = GAMMA * lt * ht * (bt + ct) / 2
    ix8 = m8 * lt**2 * (bt**2 + 4 * bt * ct + ct**2) / (18 * (bt + ct) ** 2)
    iz8 = m8 * (bt**2 + ct**2) / 24
    prims.append(
        Primitive(
            key="A1.8c",
            name=f"Trapezoidal Plate (corrected: widths along X, h -> Y, h={ht:g})",
            frame="l -> Z, widths b,c along X, thickness h -> Y; thin-plate limit",
            order=("z", "x", "y"),
            outer=(0.0, lt),
            mid=lambda z: _trap_ylim(z, lt, bt, ct),
            inner=lambda z, x: (-ht / 2, ht / 2),
            inside=lambda x, y, z: (
                (z >= 0.0)
                & (z <= lt)
                & (np.abs(x) <= 0.5 * (bt + (ct - bt) * z / lt))
                & (np.abs(y) <= ht / 2)
            ),
            bbox=((-max(bt, ct) / 2, max(bt, ct) / 2), (-ht / 2, ht / 2), (0.0, lt)),
            expected={
                "M": m8,
                "zbar": lt * (bt + 2 * ct) / (3 * (bt + ct)),
                "Ix": ix8,
                "Iy": ix8 + iz8,
                "Iz": iz8,
            },
            notes="h^2/12 terms are dropped by the cheatsheet; exact as h -> 0.",
        )
    )

    m9 = GAMMA * 2 * math.pi * A * B * H / 3
    prims.append(
        Primitive(
            key="A1.9c",
            name="Ellipto-parabolic Hoof (corrected: a -> X taper, b -> Y)",
            frame="a -> X (parabolic taper), b -> Y, h -> Z height",
            order=("y", "z", "x"),
            outer=(-B, B),
            mid=lambda y: (0.0, H),
            inner=_hoof_c_xlim,
            inside=_hoof_c_inside,
            bbox=((-A, A), (-B, B), (0.0, H)),
            expected={
                "M": m9,
                "zbar": 2 * H / 5,
                "Ix": m9 * (B**2 / 4 + 0.0686 * H**2),
                "Iy": m9 * (0.15 * A**2 + 0.0686 * H**2),
                "Iz": m9 * (0.15 * A**2 + B**2 / 4),
            },
        )
    )

    return prims


# --------------------------------------------------------------------------- #
# A1.4 shape-hypothesis scan                                                   #
# --------------------------------------------------------------------------- #


def _j(m: float) -> float:
    """Return the integral of ``(1-v^2)^(m/2)`` over ``[-1, 1]``.

    Parameters
    ----------
    m : float
        Exponent parameter.

    Returns
    -------
    float
        ``sqrt(pi) * Gamma(m/2+1) / Gamma(m/2+3/2)``.
    """
    return math.sqrt(math.pi) * special.gamma(m / 2 + 1) / special.gamma(m / 2 + 1.5)


def octo_family(alpha: float, beta: float, n: float) -> dict[str, float]:
    r"""Closed-form properties of the generalised A1.4/A1.9 family.

    The family is

    .. math::

        |x| \le a k^{\alpha}, \qquad
        |z| \le c k^{\beta}\left(1 - (x/(a k^{\alpha}))^{n}\right),
        \qquad k = \sqrt{1-(y/b)^2}.

    Parameters
    ----------
    alpha, beta : float
        Exponents of ``k`` scaling the x half-width and the z amplitude.
    n : float
        Exponent of the profile (2 = parabolic, 8 = "octo").

    Returns
    -------
    dict
        ``V`` (coefficient of ``a b c``), ``kx2``/``ky2``/``kz2`` (coefficients
        of ``a**2``, ``b**2``, ``c**2`` in the centroidal radii of gyration).
    """
    m = alpha + beta
    v_coef = 4.0 * n / (n + 1.0) * _j(m)
    a_n = 2.0 * n / (3.0 * (n + 3.0))
    b_n = 2.0 * (1.0 - 3.0 / (n + 1.0) + 3.0 / (2.0 * n + 1.0) - 1.0 / (3.0 * n + 1.0))
    kx2 = a_n * (n + 1.0) * _j(3 * alpha + beta) / (2.0 * n * _j(m))
    ky2 = 1.0 / (m + 3.0)
    kz2 = b_n * (n + 1.0) * _j(3 * beta + alpha) / (6.0 * n * _j(m))
    return {"V": v_coef, "kx2": kx2, "ky2": ky2, "kz2": kz2}


def fit_octo_exponent() -> dict[str, float]:
    """Fit the profile exponent ``n`` independently to each A1.4 coefficient.

    Uses the ``alpha = beta = 1`` family (the literal reading of the printed
    surface equation).  If the cheatsheet numbers came from a single solid, all
    four fits would return the same ``n``.

    Returns
    -------
    dict
        Mapping ``quantity -> fitted n`` (``nan`` when unattainable).
    """
    from scipy.optimize import brentq

    target = {"V": 4.66493, "kx2": 0.211, "ky2": 0.19473, "kz2": 0.23511}
    out: dict[str, float] = {}
    for q, tgt in target.items():
        try:
            out[q] = brentq(lambda n, q=q, tgt=tgt: octo_family(1, 1, n)[q] - tgt, 1.05, 400.0)
        except ValueError:
            out[q] = float("nan")
    return out


def scan_octo_hypotheses() -> list[tuple[str, dict[str, float], float]]:
    """Scan candidate readings of the A1.4 surface definition.

    Returns
    -------
    list
        ``(label, properties, max_relative_mismatch)`` sorted by mismatch.
    """
    target = {"V": 4.66493, "kx2": 0.211, "ky2": 0.19473, "kz2": 0.23511}
    out = []
    for alpha in (0, 1):
        for beta in (0, 1):
            for n in (2, 4, 6, 8, 10, 16):
                props = octo_family(alpha, beta, n)
                err = max(abs(props[k] - target[k]) / abs(target[k]) for k in target)
                label = f"alpha={alpha}, beta={beta}, n={n}"
                out.append((label, props, err))
    out.sort(key=lambda t: t[2])
    return out


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #


def rel_err(num: float, ref: float, scale: float) -> float:
    """Relative error of ``ref`` against ``num``, normalised by ``scale``.

    Parameters
    ----------
    num : float
        Numerical (reference) value.
    ref : float
        Cheatsheet value.
    scale : float
        Normalisation used when ``num`` is (near) zero.

    Returns
    -------
    float
    """
    denom = abs(num) if abs(num) > 1e-12 * abs(scale) else abs(scale)
    if denom == 0.0:
        return 0.0
    return abs(ref - num) / denom


def permutation_match(
    num: dict[str, float], exp: dict[str, float]
) -> tuple[tuple[str, str, str], float]:
    """Find the axis permutation minimising the inertia-triple mismatch.

    Parameters
    ----------
    num : dict
        Numerical results with keys ``Ix``, ``Iy``, ``Iz``.
    exp : dict
        Cheatsheet values with the same keys.

    Returns
    -------
    tuple
        ``(permutation, max_relative_error)`` where ``permutation[i]`` names the
        numerical axis that reproduces the printed component ``i``.
    """
    names = ("x", "y", "z")
    best = (names, float("inf"))
    for perm in permutations(names):
        errs = [
            rel_err(num[f"I{perm[i]}"], exp[f"I{names[i]}"], num[f"I{perm[i]}"]) for i in range(3)
        ]
        e = max(errs)
        if e < best[1]:
            best = (perm, e)
    return best


def run_block(prims: list[Primitive]) -> tuple[int, int]:
    """Evaluate and print a report block for a list of primitives.

    Parameters
    ----------
    prims : list of Primitive

    Returns
    -------
    tuple of int
        ``(n_fully_verified, n_flagged)``.
    """
    n_ok = 0
    n_flag = 0

    for prim in prims:
        mq = raw_moments_quad(prim)
        rq = inertial_properties(mq)
        mmc = raw_moments_mc(prim)
        rmc = inertial_properties(mmc)

        print("-" * 78)
        print(f"{prim.key}  {prim.name}")
        print(f"  frame: {prim.frame}")
        if prim.notes:
            print(f"  note : {prim.notes}")
        print(
            f"  {'quantity':10s} {'cheatsheet':>14s} {'quad':>14s} "
            f"{'monte-carlo':>14s} {'rel.err':>10s}  status"
        )

        scale = max(abs(rq["Ix"]), abs(rq["Iy"]), abs(rq["Iz"]), abs(rq["M"]))
        prim_flags = []
        for q in ("M", "xbar", "ybar", "zbar", "Ix", "Iy", "Iz"):
            if q not in prim.expected:
                continue
            num = rq[q]
            ref = prim.expected[q]
            sc = (
                abs(rq["M"])
                if q == "M"
                else (
                    max(abs(rq["xbar"]), abs(rq["ybar"]), abs(rq["zbar"]), 1e-3)
                    if q.endswith("bar")
                    else scale
                )
            )
            e = rel_err(num, ref, sc)
            status = "OK" if e <= TOL else "FLAG"
            if e > TOL:
                prim_flags.append(q)
            print(f"  {q:10s} {ref:14.8g} {num:14.8g} {rmc[q]:14.8g} {e * 100:9.4f}%  {status}")

        # products of inertia (should vanish)
        prod = max(abs(rq["Ixy"]), abs(rq["Ixz"]), abs(rq["Iyz"]))
        print(f"  {'products':10s} max|I_ij| = {prod:.3e}  (vs scale {scale:.3e})")

        # quad / MC consistency
        mc_gap = max(rel_err(rq[q], rmc[q], scale) for q in ("M", "Ix", "Iy", "Iz"))
        print(f"  quad-vs-MC agreement: max rel. diff = {mc_gap * 100:.4f}%")

        if prim_flags:
            perm, perr = permutation_match(rq, prim.expected)
            if perr <= TOL and set(p for p in prim_flags) <= {"Ix", "Iy", "Iz"}:
                print(
                    f"  >>> AXIS-LABEL ISSUE: printed (Ix,Iy,Iz) matches numerical "
                    f"({perm[0]},{perm[1]},{perm[2]}) to {perr * 100:.4f}%"
                )
            else:
                print(
                    f"  >>> NUMERICAL MISMATCH on {', '.join(prim_flags)} "
                    f"(best permutation {perm} still off by {perr * 100:.3f}%)"
                )
            n_flag += 1
        else:
            print("  >>> all printed quantities verified")
            n_ok += 1
        print()

    return n_ok, n_flag


def main() -> int:
    """Run the full audit and print a report.

    Returns
    -------
    int
        Process exit code (always 0; findings are reported, not asserted).
    """
    warnings.filterwarnings("ignore", category=integrate.IntegrationWarning)
    np.set_printoptions(precision=6, suppress=True)

    print("=" * 78)
    print("HATZE GEOMETRIC PRIMITIVE AUDIT (Table A1)")
    print("=" * 78)
    print(f"gamma = {GAMMA} kg/m^3, seed = {SEED}, N_MC = {N_MC:,}")
    print(
        f"test dims: a={A}, b={B}, h={H}, c={C}, r_hemi={R_HEMI}, "
        f"R={R_OUT}, r={R_IN}, l={ELL}, b_trap={B_TRAP}, c_trap={C_TRAP}, "
        f"h_trap={H_TRAP}"
    )
    print(f"flag threshold: {TOL * 100:.1f} % relative error")
    print()
    print("PASS 1 - literal reading of the cheatsheet axis labels")
    print()

    prims = build_primitives()
    n_ok, n_flag = run_block(prims)

    print("=" * 78)
    print(f"primitives with every printed quantity verified : {n_ok}/{len(prims)}")
    print(f"primitives with at least one flagged quantity   : {n_flag}/{len(prims)}")
    print()

    print("=" * 78)
    print("PASS 2 - corrected axis frames (relabelled parameters)")
    print("=" * 78)
    print()
    cprims = build_corrected_primitives()
    c_ok, c_flag = run_block(cprims)
    print("=" * 78)
    print(f"corrected-frame primitives fully verified : {c_ok}/{len(cprims)}")
    print(f"corrected-frame primitives still flagged  : {c_flag}/{len(cprims)}")
    print()

    # ---- A1.8 thin-plate convergence -------------------------------------- #
    print("=" * 78)
    print("A1.8 THIN-PLATE CONVERGENCE (h^2/12 terms omitted by the cheatsheet)")
    print("=" * 78)
    for ht in (0.02, 0.005, 0.001, 1.0e-5):
        p = build_corrected_primitives(h_thin=ht)[3]
        r = inertial_properties(raw_moments_quad(p))
        e = max(rel_err(r[q], p.expected[q], r["Iy"]) for q in ("Ix", "Iy", "Iz"))
        print(f"  h = {ht:9.5f} m   max rel. error on (Ix,Iy,Iz) = {e * 100:8.4f}%")
    print()

    # ---- A1.4 hypothesis scan --------------------------------------------- #
    print("=" * 78)
    print("A1.4 SHAPE-HYPOTHESIS SCAN")
    print("=" * 78)
    print("family: |x| <= a k^alpha,  |z| <= c k^beta (1-(x/(a k^alpha))^n),")
    print("        k = sqrt(1-(y/b)^2)")
    print("target (cheatsheet): V=4.66493, kx2=0.211, ky2=0.19473, kz2=0.23511")
    print()
    print(f"  {'hypothesis':28s} {'V':>10s} {'kx2':>9s} {'ky2':>9s} {'kz2':>9s} {'maxerr':>9s}")
    for label, props, err in scan_octo_hypotheses()[:8]:
        print(
            f"  {label:28s} {props['V']:10.5f} {props['kx2']:9.5f} "
            f"{props['ky2']:9.5f} {props['kz2']:9.5f} {err * 100:8.3f}%"
        )
    print()
    print("Effective profile exponent n fitted independently to each printed")
    print("coefficient (alpha = beta = 1, the literal reading):")
    for q, n in fit_octo_exponent().items():
        print(f"  n fitted from {q:4s} = {n:10.4f}")
    print("  (a single solid would give ONE value of n for all four)")
    print()
    print("A1.9 cross-check of the same family (alpha=1, beta=0, n=2):")
    p9 = octo_family(1, 0, 2)
    print(f"  V(one-sided) = {p9['V'] / 2:.8f} a b h   (cheatsheet 2*pi/3 = {2 * math.pi / 3:.8f})")
    print(f"  kx2 = {p9['kx2']:.8f} (cheatsheet 0.15 along the taper axis)")
    print(f"  ky2 = {p9['ky2']:.8f} (cheatsheet 1/4 = 0.25)")
    print(
        f"  kz2 about base = {p9['kz2']:.8f} h^2, "
        f"centroidal = {p9['kz2'] - 0.16:.8f} h^2 "
        f"(cheatsheet 0.0686; 12/175 = {12 / 175:.8f})"
    )
    print()

    print("Reference exact constants:")
    print(f"  A1.2  12/175                = {12 / 175:.10f}")
    print(f"  A1.3  1/4 - 16/(9 pi^2)     = {0.25 - 16 / (9 * math.pi**2):.10f}")
    print(f"  A1.4  128/27 (literal M)    = {128 / 27:.10f}")
    print(f"  A1.4  12/55  (literal kx2)  = {12 / 55:.10f}")
    print(f"  A1.5  2/5 - 9/64            = {2 / 5 - 9 / 64:.10f}")
    print(f"  A1.9  3/20, 12/175          = {3 / 20:.10f}, {12 / 175:.10f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
