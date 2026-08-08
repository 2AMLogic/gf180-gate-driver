"""gf180-gate-driver simulation harness.

Reproducible ngspice + gf180mcu PVT corner running, ported from
`2AMLogic/gf180-bandgap` (per CLAUDE.md: "Harness bootstrap: copy the
sim-harness pattern from 2AMLogic/gf180-bandgap rather than reinventing it")
and adapted for this repo's two-rail design: a 3.3 V logic rail and a 5 V/6 V
drive rail swept together. See sim/README.md.
"""

HARNESS_VERSION = "0.1.0"

__all__ = ["HARNESS_VERSION"]
