"""bodyloop_anthropometrics — Reproducible pipeline from BodyLoop 3D scan to anthropometric models.

Modules
-------
api          : BodyLoop REST API client and data schemas (Agent C).
geometry     : Mesh utilities — coordinates, repair, cross-sections, mass properties.
rigging      : glTF/GLB audit, skeleton mapping, skin-weight transfer, export.
anthropometry: Measurement extraction and adapter layers (Yeadon, Hatze, direct BSP).
biomechanics : Export to biorbd and OpenSim.
cli          : Click-based command-line interface.
"""

__version__ = "0.1.0"
