#!/usr/bin/env python3
"""Emit the `klt pex` testbench requests for T1 item 7 (issue #369). Deterministic.

    python3 sim/gate-driver-core-drive-with-uvlo/klt/pex/gen_pex_requests.py

Reuses ../gen_requests.py unchanged (same corners, same measurements, same
ratified bounds, nothing relaxed) and only re-points `netlist` at ./body.spice,
whose single `.include` is dut.spice, the schematic DUT wrapped as
`.subckt gate_driver_core` and instantiated as `xdut` -- the swap point `klt pex`
re-points at the extracted netlist.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import gen_requests  # noqa: E402


def main():
    nominal = gen_requests.request([2.97, 3.3, 3.63], [4.5, 5.0, 5.5], 50e-9, 0.5)
    stretch = gen_requests.request([3.3], [6.0], 25e-9, 1.0)
    for name, req, hosts in (
        ("request-nominal.json", nominal, 15),
        ("request-stretch.json", stretch, 5),
    ):
        req["netlist"] = "body.spice"
        # uvlo_lockout_at_in_high probes the internal node v(x3.lockout): a diagnostic
        # with no spec_row and no bound, and a hierarchical name that has no
        # equivalent in the flat extracted netlist (ngspice: "no such vector"). Every
        # spec-row measurement is kept unchanged.
        req["measurements"] = [m for m in req["measurements"] if "x3." not in m.get("spice", "")]
        # klt pex has no --hosts flag; shard via the request so each job fits the
        # fleet's whole-job ceiling and survives a Spot reclaim.
        req.setdefault("remote", {})["hosts"] = hosts
        (HERE / name).write_text(json.dumps(req, indent=2) + "\n")


if __name__ == "__main__":
    main()
