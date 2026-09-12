# bodyloop-anthropometrics

[![CI](https://github.com/mickaelbegon/bodyloop-anthropometrics/actions/workflows/ci.yml/badge.svg)](https://github.com/mickaelbegon/bodyloop-anthropometrics/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Reproducible pipeline** from a [BodyLoop](https://bodyloop.io/) 3D body scan to
anthropometric models ([Yeadon 1990](#yeadon-1990-17-segment-model),
[Hatze 1979](#hatze-1979-17-segment-model)) and inertial parameters for
[biorbd](https://github.com/pyomeca/biorbd) and [OpenSim 4.x](https://opensim.stanford.edu/).

> **Status — Phase 3 complete (pre-alpha).** The full extraction and export pipeline
> is implemented and tested. Several scientific decisions remain open — every one is
> tracked in [`SCIENCE_DECISIONS.md`](SCIENCE_DECISIONS.md) and blocked in code with
> `TODO_SCIENTIFIC` markers. See [Scientific Status](#scientific-status) below.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [CLI Usage](#cli-usage)
5. [Python API](#python-api)
6. [Supported Models](#supported-models)
7. [Export Targets](#export-targets)
8. [Scientific Status](#scientific-status)
9. [Measurement Validation Viewer](#measurement-validation-viewer)
10. [Data Privacy](#data-privacy)
11. [Development](#development)
12. [References](#references)

---

## Architecture

```
BodyLoop Scanner
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│  bodyloop_anthropometrics/api/                            │
│  BodyLoopClient  ──►  ViatarData (Pydantic v2 schemas)  │
│  ExportPipeline  ──►  normalized/ + *.glb + manifest.json│
└─────────────────────┬────────────────────────────────────┘
                      │
         ┌────────────┼───────────────┐
         │            │               │
         ▼            ▼               ▼
┌──────────────┐ ┌──────────┐ ┌────────────────────────┐
│  geometry/   │ │ rigging/ │ │  anthropometry/         │
│  mass_       │ │ gltf_    │ │  measurement_mapping    │
│  properties  │ │ audit    │ │  yeadon_adapter (95 m.) │
│  (Mirtich)   │ │          │ │  hatze_adapter (242 m.) │
│  direct_mesh_│ │          │ │  direct_mesh_bsp        │
│  bsp         │ │          │ └──────────┬──────────────┘
└──────┬───────┘ └──────────┘            │
       └──────────────────┬──────────────┘
                          │
                          ▼
             ┌────────────────────────┐
             │  export/               │
             │  biorbd_exporter ─► .bioMod │
             │  opensim_exporter ─► .osim  │
             └────────────────────────┘
                          │
                          ▼
             ┌────────────────────────┐
             │  visualization/        │
             │  measurement_viewer    │
             │  (Dash + Plotly 3D)    │
             └────────────────────────┘
```

### Module overview

| Module | Description |
|--------|-------------|
| `api/client.py` | BodyLoop REST API client — reads credentials from environment only, never from function parameters |
| `api/schemas.py` | Pydantic v2 schemas for all API responses (Marker3D, Distance, CrossSection, …) |
| `api/export.py` | ExportPipeline — versioned directory tree, SHA-256 hashing, UUID-v5 pseudonymisation |
| `anthropometry/measurement_mapping.py` | `Measurement` model with full provenance (`source`, `confidence`, validation workflow) |
| `anthropometry/yeadon_adapter.py` | Map BodyLoop data to Yeadon (1990) 95 measurements; call `yeadon.Human` |
| `anthropometry/hatze_adapter.py` | Extract Hatze (1979) 242 measurements with provenance; compute primitive params (blocked pending primary source) |
| `anthropometry/direct_mesh_bsp.py` | 14-segment BSP from mesh: Sutherland–Hodgman cutting + Mirtich polyhedral integration |
| `geometry/mass_properties.py` | Pure-NumPy signed tetrahedral decomposition (Mirtich 1996); validated < 0.1 % on known shapes |
| `rigging/gltf_audit.py` | GLB/glTF rig audit: skins, JOINTS_0/WEIGHTS_0, LBS deformation test |
| `export/biorbd_exporter.py` | Write biorbd v4 `.bioMod` from BodyBSP or Yeadon inertial params |
| `export/opensim_exporter.py` | Write OpenSim 4.x `.osim` XML from BodyBSP or Yeadon inertial params |
| `visualization/measurement_viewer.py` | Interactive 3D viewer (Dash + Plotly) for approving/rejecting measurements |

---

## Installation

### Standard

```bash
pip install bodyloop-anthropometrics
```

### Development

```bash
git clone https://github.com/mickaelbegon/bodyloop-anthropometrics.git
cd bodyloop-anthropometrics
pip install -e ".[dev]"
pre-commit install
```

### Optional: interactive measurement viewer

```bash
pip install -e ".[viz]"
```

### Optional: SMPL/SMPLX parametric model fitting

```bash
pip install -e ".[smpl]"
```

> Requires PyTorch ≥ 2.3. Install a CUDA-enabled wheel manually for GPU acceleration.

### Python version notes

| Component | Python |
|-----------|--------|
| Core pipeline | ≥ 3.11 |
| BODIESReg subprocess adapter | 3.10 (separate venv) |
| SKEL model | ≥ 3.12 (separate venv) |

---

## Configuration

Copy `.env.example` to `.env` and fill in your BodyLoop credentials:

```bash
cp .env.example .env
```

| Variable | Description | Example |
|----------|-------------|---------|
| `BODYLOOP_BASE_URL` | BodyLoop REST API base URL | `https://bodyloop-control-pc/api/v2` |
| `BODYLOOP_API_TOKEN` | Bearer token for authentication | `eyJ...` |

> **Security:** Never commit `.env`. The token grants full API access. It is never
> logged, printed, or accepted as a function argument — only read from the environment.

---

## CLI Usage

All commands are available under the `bodyloop-anthro` entry point.

### `inspect-api` — Check API connectivity

```bash
bodyloop-anthro inspect-api
```

### `export` — Download scan data

```bash
bodyloop-anthro export \
    --viatar-id VIATAR_001 \
    --output ./output/VIATAR_001 \
    --format normalized
```

Output layout:

```
output/VIATAR_001/
    manifest.json          ← schema version, timestamps, SDK/API versions, SHA-256 hashes
    normalized/
        distances.json
        heights.json
        markers.json
        cross_sections.json
        angles.json
        properties.json
    VIATAR_001.glb         ← 3D mesh with skeleton (when format includes glb)
```

### `audit-rig` — Validate GLB skeleton

```bash
bodyloop-anthro audit-rig output/VIATAR_001/VIATAR_001.glb
```

Reports: joint hierarchy, skin count, vertex count, JOINTS_0/WEIGHTS_0 accessor status,
and a linear blend skinning deformation test on shoulder/hip/knee/elbow joints.

### `build-yeadon` — Yeadon (1990) inertia model

```bash
bodyloop-anthro build-yeadon output/VIATAR_001/normalized/ \
    --output output/VIATAR_001/yeadon/
```

Produces:
- `yeadon_measurements.json` — 95-key `MeasurementSet` with provenance and validation status
- `yeadon_bsp.json` — segment inertial parameters from `yeadon.Human`

> **65 of 95 measurements require manual validation** (landmark-dependent: hip joint
> centre, acromion, crotch, heel, foot arch, etc.). Run `visualize-measurements` to
> review them. See [`validation/YEADON_KEY_COVERAGE.md`](validation/YEADON_KEY_COVERAGE.md).

### `build-hatze` — Hatze (1979) measurement extraction

```bash
bodyloop-anthro build-hatze output/VIATAR_001/normalized/ \
    --output output/VIATAR_001/hatze/
```

Extracts all 242 Hatze measurements with full provenance into a `MeasurementSet`.

> **Note:** Measurement-to-primitive-parameter formulas are NOT implemented.
> `compute_primitive_params()` raises `NotImplementedError` for all 17 segments
> until Hatze (1979) CSIR TWISK 79 is obtained. The A1.4 (Elliptic Octoparaboloid)
> primitive raises `RuntimeError` unconditionally — its coefficients are incorrect in
> the available cheatsheet. See [`SCIENCE_DECISIONS.md`](SCIENCE_DECISIONS.md).

### `compute-bsp` — Direct mesh BSP

```bash
bodyloop-anthro compute-bsp output/VIATAR_001/VIATAR_001.glb \
    --output output/VIATAR_001/bsp/
```

Computes mass, centroid, and inertia tensor for 14 body segments directly from the
3D mesh using Mirtich (1996) polyhedral signed tetrahedral decomposition (validated
< 0.1 % against analytical formulas for sphere, cylinder, ellipsoid, cube).

### `export-biorbd` — Write biorbd `.bioMod`

```bash
bodyloop-anthro export-biorbd output/VIATAR_001/bsp/bsp.json \
    --output output/VIATAR_001/biorbd/ \
    --model-name VIATAR_001 \
    --source direct_bsp
```

Writes a biorbd v4 `.bioMod` text file using the 17-segment joint hierarchy from
[`configs/segment_joint_correspondence.yaml`](configs/segment_joint_correspondence.yaml).

> **Joint axes and ROM ranges are provisional.** All values carry `TODO_SCIENTIFIC`
> markers. Verify against ISB recommendations before use in simulations.

### `visualize-measurements` — Interactive 3D validation viewer

```bash
bodyloop-anthro visualize-measurements output/VIATAR_001/yeadon/yeadon_measurements.json \
    --mesh output/VIATAR_001/VIATAR_001.glb
```

Opens a Dash + Plotly 3D browser application for reviewing and approving individual
measurements against the 3D mesh. Approved/rejected decisions are saved to
`*_validated.json` without overwriting the original. Requires `pip install -e ".[viz]"`.

### `run-all` — Full pipeline

```bash
bodyloop-anthro run-all \
    --viatar-id VIATAR_001 \
    --output output/VIATAR_001/ \
    --model smpl
```

---

## Python API

### Yeadon inertia model

```python
from bodyloop_anthropometrics.anthropometry.yeadon_adapter import YeadonAdapter
from bodyloop_anthropometrics.api.client import BodyLoopClient

client = BodyLoopClient()            # reads BODYLOOP_BASE_URL + BODYLOOP_API_TOKEN
viatar_data = client.get_viatar_data("VIATAR_001")

adapter = YeadonAdapter()
meas = adapter.extract_measurements(viatar_data)

print(adapter.coverage_table(meas))  # rich table: key | value | source | status

# Review pending measurements before building the model
pending = meas.pending_validation()
print(f"{len(pending)} measurements need manual validation")

human = adapter.build_yeadon_human(meas)   # calls yeadon.Human
params = adapter.export_inertial_params(human)
```

### Direct mesh BSP

```python
from bodyloop_anthropometrics.anthropometry.direct_mesh_bsp import compute_body_bsp
import trimesh

mesh = trimesh.load("VIATAR_001.glb")
body_bsp = compute_body_bsp(mesh, mass_kg=70.0)

for seg_name, seg in body_bsp.segments.items():
    print(f"{seg_name}: mass={seg.mass_kg:.2f} kg  COM={seg.com_m}")
```

### biorbd / OpenSim export

```python
from bodyloop_anthropometrics.export.biorbd_exporter import BiorbdExporter
from bodyloop_anthropometrics.export.opensim_exporter import OpenSimExporter
from pathlib import Path

# From direct BSP
biorbd = BiorbdExporter()
segments = biorbd.from_body_bsp(body_bsp)
biorbd.write_biomod(segments, Path("model.bioMod"), source="direct_bsp")

opensim = OpenSimExporter()
bodies = opensim.from_body_bsp(body_bsp)
opensim.write_osim(bodies, Path("model.osim"), source="direct_bsp")

# From Yeadon
segments = biorbd.from_yeadon(params)
biorbd.write_biomod(segments, Path("model_yeadon.bioMod"), source="yeadon")
```

### Hatze measurement extraction

```python
from bodyloop_anthropometrics.anthropometry.hatze_adapter import HatzeAdapter

adapter = HatzeAdapter()
meas = adapter.extract_measurements(viatar_data)
print(adapter.coverage_table(meas))   # 242 entries with source + blocked status

# NOTE: compute_primitive_params() raises NotImplementedError for all segments
# until Hatze (1979) primary source is integrated.
```

---

## Supported Models

| Model | Reference | Measurements | Status |
|-------|-----------|-------------|--------|
| **Yeadon (1990)** | Yeadon (1990) J Biomech 23(1):67-74 | 95 (verified 100% key coverage) | ✅ Extraction + inertia model implemented |
| **Hatze (1979)** | Hatze (1979) CSIR TWISK 79 | 242 (reconstructed from cheatsheet) | ⚠️ Extraction only — primitive-parameter formulas blocked pending primary source |
| **Direct mesh BSP** | Mirtich (1996), de Leva (1996) densities | — (from mesh geometry) | ✅ Implemented, validated < 0.1 % |

---

## Export Targets

| Target | Format | Status |
|--------|--------|--------|
| **biorbd** | `.bioMod` text (v4) | ✅ Implemented — joint axes TODO_SCIENTIFIC |
| **OpenSim 4.x** | `.osim` XML | ✅ Implemented — joint axes TODO_SCIENTIFIC |

Joint hierarchies are defined in:
- [`configs/segment_joint_correspondence.yaml`](configs/segment_joint_correspondence.yaml) — biorbd
- [`configs/opensim_joint_correspondence.yaml`](configs/opensim_joint_correspondence.yaml) — OpenSim (ISB, Wu et al. 2002/2005)

---

## Scientific Status

All open decisions are tracked with validation status in
[`SCIENCE_DECISIONS.md`](SCIENCE_DECISIONS.md).

### Completed validations

| Validation | Method | Result |
|-----------|--------|--------|
| Yeadon 95-key coverage | Cross-check vs. `yeadon` 1.5.0 package | ✅ 95/95 correct, 0 missing ([report](validation/YEADON_KEY_COVERAGE.md)) |
| Mirtich polyhedral BSP | Analytical cross-check on sphere/cylinder/ellipsoid/cube | ✅ < 0.1 % error ([report](validation/MASS_PROPERTIES_AUDIT.md)) |
| Hatze primitive equations (A1.1–A1.9) | Two independent numerical engines (quadrature + Monte-Carlo 10M) | 8/9 verified; A1.4 **wrong** ([report](validation/HATZE_PRIMITIVES_AUDIT.md)) |

### Hatze primitive equation audit (2026-09-12)

| Primitive | Status | Notes |
|-----------|--------|-------|
| A1.1 Elliptic Cylinder | ✅ Verified | Axis labels corrected (a=X, b=Y) |
| A1.2 Parabolic Plate | ✅ Verified | 12/175 is exact |
| A1.3 Semi-elliptic Plate | ✅ Verified | 0.07 = 1/4−16/(9π²) to 0.18 % |
| **A1.4 Octoparaboloid** | ❌ **Wrong** | All 4 coefficients incorrect (1.6–3.3 %); 0.19473 structurally unattainable. **Blocked.** |
| A1.5 Hemisphere | ✅ Verified | |
| A1.6 Hollow Half-Cylinder | ✅ Verified | |
| A1.7 Elliptic Paraboloid | ✅ Verified | Centroid corrected z̄=c/3, axis labels corrected |
| A1.8 Trapezoidal Plate | ⚠️ Thin-plate approx. | Drops Mh²/12 terms; 8 % error at foot thickness |
| A1.9 Hoof | ✅ Verified | 0.0686=12/175, 0.15=3/20 (exact rationals) |

### Open scientific decisions

| Decision | Status |
|----------|--------|
| Segment density values (de Leva 1996 placeholder) | PENDING — DEXA calibration needed |
| Hatze measurement→parameter formulas (242 measurements) | PENDING — requires Hatze (1979) CSIR TWISK 79 |
| Hatze A1.4 primitive coefficients | OPEN — primary source required |
| Yeadon difficult landmarks (hip centre, acromion, crotch, heel) | PENDING — 65/95 need manual validation on real scans |
| Segment boundary plane positions | PENDING — de Leva convention applied, not verified |
| Joint axes and ROM ranges in biorbd/OpenSim export | PENDING — TODO_SCIENTIFIC in both YAML configs |
| Lung volume correction for trunk BSP | PENDING — disabled by default (would double-count with de Leva density) |

### Code markers

| Marker | Meaning |
|--------|---------|
| `# TODO_SCIENTIFIC:` | Blocking scientific decision — see `SCIENCE_DECISIONS.md` |
| `# TODO_VALIDATE:` | Requires cross-check against original publication |
| `# ASSUMPTION:` | Documented working assumption — must be validated |

---

## Measurement Validation Viewer

The interactive viewer (`visualization/measurement_viewer.py`) overlays extracted
measurements on the 3D mesh for manual review:

- **Colour by source:** direct (green), calculated (blue), interpolated (orange), manual (red)
- **Approve / Reject** each measurement with a timestamped record of who validated it
- Auto-saves to `*_validated.json` without overwriting the original extraction
- Loads `*_validated.json` preferentially on restart

```bash
# Install visualization dependencies
pip install -e ".[viz]"

# Launch
bodyloop-anthro visualize-measurements path/to/measurements.json --mesh path/to/mesh.glb
```

---

## Data Privacy

- Subject identifiers are pseudonymised with UUID v5 by `ExportPipeline.pseudonymize_subject()` before any data is written to disk.
- API tokens are never logged, printed, or passed as function arguments — only read from `BODYLOOP_API_TOKEN`.
- No real subject data is committed to this repository. All test fixtures use synthetic data.
- GLB files from real subjects must be stored outside the repository root and are excluded by `.gitignore`.

---

## Development

### Run tests

```bash
# Unit tests only (fast, no network)
pytest tests/unit/ -v

# Scientific validation tests
pytest tests/scientific/ -v

# Integration tests (mock network, real geometry)
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=bodyloop_anthropometrics --cov-report=term-missing
```

### Lint and type-check

```bash
ruff check . && ruff format --check . && mypy bodyloop_anthropometrics
```

### Test suite summary (Phase 3)

| Test suite | Count | Notes |
|-----------|-------|-------|
| Unit — API client | 21 | Token safety, schema validation, manifest |
| Unit — Yeadon adapter | 18 | 95-key extraction, coverage, validation workflow |
| Unit — Hatze adapter | 65 | 242-key extraction, A1.4 blocking, provenance |
| Unit — GLB audit | ~15 | LBS deformation, hierarchy, report fields |
| Unit — biorbd exporter | 21 | .bioMod format, mass/inertia round-trip |
| Unit — OpenSim exporter | 27 | .osim XML schema, joint hierarchy |
| Scientific — BSP analytical | 23 | Mirtich vs. sphere/cylinder/ellipsoid/cube |
| Integration — full pipelines | 17 + 2 skipped | Yeadon, Hatze, BSP, CLI, GLB |

### Project structure

```
bodyloop_anthropometrics/
├── api/            client.py  schemas.py  export.py
├── anthropometry/  measurement_mapping.py  yeadon_adapter.py  hatze_adapter.py  direct_mesh_bsp.py
├── geometry/       mass_properties.py
├── rigging/        gltf_audit.py
├── export/         biorbd_exporter.py  opensim_exporter.py
├── visualization/  measurement_viewer.py
└── cli.py

configs/
├── bodyloop_to_yeadon.yaml          (95 measurements)
├── bodyloop_to_hatze.yaml           (242 measurements)
├── segment_joint_correspondence.yaml  (biorbd joint hierarchy)
└── opensim_joint_correspondence.yaml  (OpenSim 4.x ISB hierarchy)

docs/
└── HATZE_EQUATIONS.md   (extracted + numerically audited primitive equations)

validation/
├── YEADON_KEY_COVERAGE.md
├── MASS_PROPERTIES_AUDIT.md
├── HATZE_PRIMITIVES_AUDIT.md
└── validate_hatze_primitives.py

tests/
├── unit/          (per-module unit tests)
├── scientific/    (analytical cross-checks)
└── integration/   (end-to-end pipeline tests)
```

### Contributing

1. Fork and create a feature branch.
2. Add tests in `tests/unit/` for every new module.
3. For scientific decisions, open an issue with the **Scientific question** template and update `SCIENCE_DECISIONS.md`.
4. Run `ruff check . && ruff format . && mypy bodyloop_anthropometrics` before pushing.
5. Submit a pull request. See [`AGENTS.md`](AGENTS.md) for AI agent contribution rules.

---

## References

- Yeadon, M.R. (1990). The simulation of aerial movement — II. A mathematical inertia model of the human body. *J Biomech* 23(1):67–74.
- Hatze, H. (1979). A model for the computational determination of parameter values of anthropomorphic segments. CSIR Technical Report TWISK 79, Pretoria, South Africa.
- Hatze, H. (1980). A mathematical model for the computational determination of parameter values of anthropomorphic segments. *J Biomech* 13(10):833–843.
- de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters. *J Biomech* 29(9):1223–1230.
- Mirtich, B. (1996). Fast and accurate computation of polyhedral mass properties. *J Graphics Tools* 1(2):31–50.
- Wu, G. et al. (2002). ISB recommendation on definitions of joint coordinate system of various joints for the reporting of human joint motion. *J Biomech* 35(4):543–548.
- Wu, G. et al. (2005). ISB recommendation on definitions of joint coordinate systems of various joints for the reporting of human joint motion — Part II. *J Biomech* 38(5):981–992.

---

## License

MIT — see [LICENSE](LICENSE).

Copyright © 2026 Mickael Begon, Université de Montréal.
