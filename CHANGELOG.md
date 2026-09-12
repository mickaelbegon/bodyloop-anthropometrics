# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffold: package structure, stubs, CLI, configs, CI, fixtures.
- `Measurement` Pydantic model with full provenance tracking.
- Synthetic data generator in `tests/fixtures/synthetic_data.py`.
- GitHub Actions CI workflow (lint + test matrix for Python 3.11/3.12).
- GitHub issue templates: bug report, scientific question, missing measurement.
- Pre-commit configuration (ruff, mypy, standard hooks).
- `SCIENCE_DECISIONS.md` with initial open decisions.
- `AGENTS.md` with multi-agent coordination rules.

## [0.1.0] — 2026-09-11

- Initial release (scaffold only — no implementation).
