#!/usr/bin/env python3
"""Emit the `klt pex` testbench requests for T1 item 7 (issue #369). Deterministic.

    python3 sim/gate-driver-core-drive-with-uvlo/klt/pex/gen_pex_requests.py

Builds both requests with ../gen_requests.py `request()` unchanged (same corner
construction, same measurement set) over the un-sharded 45 + 15 corner matrices at
the plain `spec/gate-driver.md` Sec.3 bounds -- NOT the seven DR-0016 / DR-0020
shards that `gen_requests.main()` emits for item 5. Those shards relax two bounds at
four corners; the Sec.3 bounds used here are the stricter of the two, so nothing is
relaxed. Whether item 7 should adopt the shards is an open spec/verification
question, not something this generator decides.

`netlist` is re-pointed at ./body.spice, whose single `.include` is dut.spice, the
schematic DUT wrapped as `.subckt gate_driver_core` and instantiated as `xdut` --
the swap point `klt pex` re-points at the extracted netlist.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import gen_requests  # noqa: E402

# The full un-sharded matrix: every process at every temperature, in the order the
# committed request-*.json files carry them.
PROCESSES = ["tt", "ff", "ss", "fs", "sf"]
TEMPS_C = [-40.0, 27.0, 125.0]


def main():
    # The un-sharded 45 + 15 corner matrices at the plain spec/gate-driver.md Sec.3
    # bounds -- equal source and sink minimums, no corner-scoped exception. See the
    # module docstring for why the DR-0016 / DR-0020 shards are deliberately not used.
    nominal = gen_requests.request(
        PROCESSES, TEMPS_C, [2.97, 3.3, 3.63], [4.5, 5.0, 5.5], 50e-9, 0.5, 0.5
    )
    stretch = gen_requests.request(PROCESSES, TEMPS_C, [3.3], [6.0], 25e-9, 1.0, 1.0)
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
