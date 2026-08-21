"""gf180-gate-driver simulation harness.

Reproducible ngspice + gf180mcu PVT corner running, ported from
`2AMLogic/gf180-bandgap` (per CLAUDE.md: "Harness bootstrap: copy the
sim-harness pattern from 2AMLogic/gf180-bandgap rather than reinventing it")
and adapted for this repo's two-rail design: a 3.3 V logic rail and a 5 V/6 V
drive rail swept together. See sim/README.md.
"""

# 0.2.0 -- adds the Monte Carlo / local-mismatch deck mode (harness/montecarlo.py,
# runner.compose_deck(mc=...), runner.run_samples); issue #204. Additive: a
# deck composed with mc=None is byte-identical to what 0.1.0 produced.
HARNESS_VERSION = "0.2.0"

__all__ = ["HARNESS_VERSION"]
