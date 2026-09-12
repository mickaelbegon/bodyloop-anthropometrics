# bodyloop-anthropometrics

[![CI](https://github.com/mickael-begon/bodyloop-anthropometrics/actions/workflows/ci.yml/badge.svg)](https://github.com/mickael-begon/bodyloop-anthropometrics/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/mickael-begon/bodyloop-anthropometrics/branch/main/graph/badge.svg)](https://codecov.io/gh/mickael-begon/bodyloop-anthropometrics)
[![PyPI](https://img.shields.io/pypi/v/bodyloop-anthropometrics.svg)](https://pypi.org/project/bodyloop-anthropometrics/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Reproducible pipeline** from a [BodyLoop](https://bodyloop.io/) 3D body scan to
anthropometric models (Yeadon 1990, Hatze 1979) and inertial parameters for
[biorbd](https://github.com/pyomeca/biorbd) and [OpenSim](https://opensim.stanford.edu/).

> **Status:** Pre-Alpha — API stubs only.  No computation is implemented yet.
> Scientific decisions are tracked in [`SCIENCE_DECISIONS.md`](SCIENCE_DECISIONS.md).

---

## Architecture

```
BodyLoop Scanner
      |
      v
┌─────────────────────────────────────────────────────────┐
│  bodyloop_anthropometrics/api/                           │
│  BodyLoopClient  ──►  ViatarData (Pydantic schemas)     │
│  ExportPipeline  ──►  normalized/  +  *.glb  +  manifest│
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼──────────────────┐
          │               │                  │
          v               v                  v
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  geometry/      │ │  rigging/    │ │  anthropometry/  │
│  coordinates    │ │  gltf_audit  │ │  measurement_    │
│  mesh_repair    │ │  skeleton_   │ │  mapping         │
│  cross_sections │ │  mapping     │ │  yeadon_adapter  │
│  mass_properties│ │  bodiesreg_  │ │  hatze_adapter   │
└────────┬────────┘ │  adapter     │ │  direct_mesh_bsp │
         │          │  skin_weight_│ └────────┬─────────┘
         │          │  transfer    │          │
         │          │  export_gltf │          │
         │          └──────────────┘          │
         └──────────────────┬─────────────────┘
                            │
                            v
              ┌─────────────────────────┐
              │  biomechanics/          │
              │  biorbd_export  ──► .bioMod │
              │  opensim_export ──► .osim   │
              └─────────────────────────┘
```

---

## Installation

### Standard install

```bash
pip install bodyloop-anthropometrics
```

### Development install

```bash
git clone https://github.com/mickael-begon/bodyloop-anthropometrics.git
cd bodyloop-anthropometrics
pip install -e ".[dev]"
pre-commit install
```

### Optional: SMPL/SMPLX fitting support

```bash
pip install -e ".[smpl]"
```

> Requires PyTorch >= 2.3.  Install a CUDA-enabled wheel manually if GPU acceleration
> is needed.

---

## Configuration

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

| Variable | Description | Example |
|---|---|---|
| `BODYLOOP_BASE_URL` | BodyLoop REST API base URL | `https://bodyloop-control-pc/api/v2` |
| `BODYLOOP_API_TOKEN` | Bearer token for authentication | `eyJ...` |

> **Security:** Never commit `.env`.  The token grants full API access.

---

## CLI Usage

All commands are available under the `bodyloop-anthro` entry point.

### `inspect-api` — Check API connectivity

```bash
bodyloop-anthro inspect-api
```

Reads `BODYLOOP_BASE_URL` and `BODYLOOP_API_TOKEN` from the environment and
prints API version, available scan presets, and current credit balance.

---

### `export` — Download scan data

```bash
bodyloop-anthro export \
    --viatar-id VIATAR_001 \
    --output ./output/VIATAR_001 \
    --format normalized
```

| Option | Description |
|---|---|
| `--viatar-id` | BodyLoop viatar (subject scan) identifier |
| `--output` | Output directory |
| `--format` | `normalized` (default), `raw`, or `glb` |

Output structure:

```
output/VIATAR_001/
    manifest.json          ← versions, timestamps, assumptions
    normalized/
        distances.json
        heights.json
        markers.json
        cross_sections.json
        angles.json
        properties.json
    VIATAR_001.glb         ← 3D mesh with skeleton (if format includes glb)
```

---

### `audit-rig` — Validate GLB skeleton

```bash
bodyloop-anthro audit-rig output/VIATAR_001/VIATAR_001.glb
```

Prints joint hierarchy, skin count, vertex count, and JOINTS_0/WEIGHTS_0 accessor status.

---

### `build-yeadon` — Yeadon (1990) inertia model

```bash
bodyloop-anthro build-yeadon output/VIATAR_001/normalized/ \
    --output output/VIATAR_001/yeadon/
```

Produces:
- `yeadon_measurements.yaml` — 95-key measurement file for the `yeadon` Python package
- `yeadon_bsp.json` — body-segment parameters (mass, centroid, inertia tensor)

---

### `build-hatze` — Hatze (1979) segment parameters

```bash
bodyloop-anthro build-hatze output/VIATAR_001/normalized/ \
    --output output/VIATAR_001/hatze/
```

> **Warning:** Hatze equations are not yet validated.  Do not use for published research
> without scientific review.  See `SCIENCE_DECISIONS.md`.

---

### `fit-body-model` — Parametric model registration

```bash
bodyloop-anthro fit-body-model output/VIATAR_001/VIATAR_001.glb \
    --model smpl \
    --device cuda:0 \
    --output output/VIATAR_001/registration/
```

| `--model` | Description |
|---|---|
| `smpl` | SMPL (Loper et al. 2015) |
| `smplx` | SMPL-X with hands and face |
| `skel` | SKEL (Keller et al. 2023) |

---

### `transfer-weights` — Skin-weight transfer

```bash
bodyloop-anthro transfer-weights output/VIATAR_001/VIATAR_001.glb \
    --method barycentric \
    --output output/VIATAR_001/rigged/
```

---

### `compute-bsp` — Direct mesh BSP

```bash
bodyloop-anthro compute-bsp output/VIATAR_001/VIATAR_001.glb \
    --output output/VIATAR_001/bsp/
```

Computes mass, centroid, and inertia tensor for each segment directly from
the 3D mesh using volumetric integration (trimesh).

---

### `export-biorbd` — biorbd .bioMod export

```bash
bodyloop-anthro export-biorbd output/VIATAR_001/bsp/bsp.json \
    --output output/VIATAR_001/biorbd/ \
    --model-name VIATAR_001
```

---

### `run-all` — Full pipeline

```bash
bodyloop-anthro run-all \
    --viatar-id VIATAR_001 \
    --output output/VIATAR_001/ \
    --model smpl
```

Runs all steps in sequence and writes a `manifest.json` recording all
versions, presets, and scientific assumptions.

---

## Supported Models

| Model | Reference | Status |
|---|---|---|
| **Yeadon (1990)** | Yeadon, M.R. (1990). J Biomech 23(1):67-74. | Mapping config pending |
| **Hatze (1979)** | Hatze, H. (1979). CSIR Technical Report TWISK 79. | Equations pending validation |
| **Direct mesh BSP** | de Leva (1996) densities | Stub only |

## Export Targets

| Target | Format | Status |
|---|---|---|
| biorbd | `.bioMod` text file | Stub only |
| OpenSim 4.x | `.osim` XML file | Stub only |

---

## Scientific Notes

### Open scientific decisions

All open decisions are tracked in [`SCIENCE_DECISIONS.md`](SCIENCE_DECISIONS.md).
Key open items:

1. **Segment density values** — placeholder values from Dempster (1955) / de Leva (1996).
   DEXA calibration needed for the target population.
2. **Hatze equation audit** — every equation must be verified against the original
   CSIR Technical Report before use.
3. **Yeadon mapping completeness** — 94 of 95 measurement keys still need BodyLoop paths.
4. **BodiesReg objective function weights** — not yet empirically tuned.

### Markers in code

| Marker | Meaning |
|---|---|
| `# TODO_SCIENTIFIC:` | Blocking scientific decision — see `SCIENCE_DECISIONS.md` |
| `# TODO_VALIDATE:` | Requires cross-check against original publication |
| `# ASSUMPTION:` | Documented working assumption |

---

## Data Privacy

- Subject identifiers are pseudonymised by `ExportPipeline.pseudonymize_subject()`
  before any data is written to disk.
- API tokens are never logged or printed.
- No real patient data is committed to this repository.
  All test fixtures use synthetic data (`tests/fixtures/synthetic_data.py`).
- GLB files from real subjects must be stored outside the repository root
  and are excluded by `.gitignore`.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Add tests in `tests/unit/` for any new code.
3. For scientific changes, open an issue using the **Scientific question** template
   and update `SCIENCE_DECISIONS.md`.
4. Run `ruff check . && ruff format . && mypy bodyloop_anthropometrics` before pushing.
5. Submit a pull request using the provided template.

See also [`AGENTS.md`](AGENTS.md) for AI agent contribution rules.

---

## License

MIT — see [LICENSE](LICENSE) file.

Copyright (c) 2026 Mickael Begon, Universite de Montreal.
