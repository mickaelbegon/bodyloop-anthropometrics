---
name: Missing measurement mapping
about: Report a Yeadon or Hatze measurement key that lacks a BodyLoop mapping
title: "[MAPPING] "
labels: mapping, needs-input
assignees: ''
---

## Missing measurement

Which measurement key is missing or incorrectly mapped?

- Model: <!-- Yeadon / Hatze -->
- Key name: <!-- e.g. "Ls1", "thigh_diameter_proximal" -->
- Current mapping: <!-- bodyloop_path or "null" -->

## Anatomical definition

Cite the exact definition from the original publication:

> (paste verbatim definition here)

Reference: <!-- Author, Year, page/equation number -->

## Proposed BodyLoop path

What BodyLoop normalised-data path (or calculation) should supply this value?

```
# Example:
bodyloop_path: "cross_sections.waist.perimeter_m"
source_type: "direct"
confidence: 0.95
```

## Validation

How did you verify that the proposed path matches the anatomical definition?

## Checklist

- [ ] Anatomical definition confirmed against original publication
- [ ] BodyLoop path confirmed in real or synthetic normalised data
- [ ] Config YAML updated in a draft PR
- [ ] Entry added to `SCIENCE_DECISIONS.md` if decision is non-obvious
