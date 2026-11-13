#!/usr/bin/env python3
"""Emit the `klt sim` requests for T1 item 5 (issues #367, #376). Deterministic.

    python3 sim/gate-driver-core-drive-with-uvlo/klt/gen_requests.py

`measurements[].limits` is min/max only and applies to every corner of a request,
so the ratified exceptions are encoded by sharding each corner matrix into
product-shaped requests: the excepted corners get their own request carrying the
ratified bound, every other corner keeps the spec/gate-driver.md Sec.3 bound.
The union of the shards is exactly the original 45 nominal + 15 stretch corners.

Writes request-nominal-*.json (the +/-10 % tied-rail matrix, TARGET bounds) and
request-stretch-*.json (the 6 V stretch rail, STRETCH bounds for the rows that
have one). Bounds that differ from Sec.3 -- only these three, each stated by a
ratified decision record:

  * DR-0016: stretch ipeak_sink_a >= 0.85 A (not 1.0 A) at ss_125c and sf_125c
    (request-stretch-hot-slow.json).
  * DR-0020: nominal ipeak_source_a >= 0.45 A (not 0.5 A) at the ss / -40 C /
    low-line (2.97 V logic, 4.5 V drive) corner (request-nominal-ss-cold-low.json).

DR-0020 excepts only that source-current bound. Rise/fall/propagation at that
corner stay at Sec.3 and still error; that, and the sf / -40 C low-line corner,
have no ratified exception (issue #378).

The process axis and the engine/models/batch/options envelope are not defined
here: both come from sim/harness/klt_request.py, which derives the five MOS
corner bundles from the harness's own corners.CORNERS (issue #441). Only what
is specific to this testbench -- netlist, analysis, measurements, the sharded
corner matrices -- lives in this file. sim/test_gen_requests.py pins that every
generator still reproduces its committed request bytes.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # sim/, for the harness package
from harness import klt_request  # noqa: E402


def measurements(tpd_max, ipk_source_min, ipk_sink_min):
    meas = []

    def add(name, row, unit, limits, **form):
        entry = {"name": name, "unit": unit, "spec_row": row, **form}
        if limits:
            entry["limits"] = limits
        meas.append(entry)

    rise = ".meas tran trise_s TRIG v(vout_n) VAL=0.1 RISE=1 TARG v(vout_n) VAL=0.9 RISE=1"
    fall = ".meas tran tfall_s TRIG v(vout_n) VAL=0.9 FALL=1 TARG v(vout_n) VAL=0.1 FALL=1"
    plh = ".meas tran tpdlh_s TRIG v(vin_n) VAL=0.5 RISE=1 TARG v(vout_n) VAL=0.5 RISE=1"
    phl = ".meas tran tpdhl_s TRIG v(vin_n) VAL=0.5 FALL=1 TARG v(vout_n) VAL=0.5 FALL=1"
    add("trise_s", "rise_fall_time", "s", {"max": 50e-9}, spice=rise)
    add("tfall_s", "rise_fall_time", "s", {"max": 50e-9}, spice=fall)
    add("tpdlh_s", "propagation_delay", "s", {"max": tpd_max}, spice=plh)
    add("tpdhl_s", "propagation_delay", "s", {"max": tpd_max}, spice=phl)
    add("ipeak_source_a", "peak_source_current", "A", {"min": ipk_source_min}, expr="vecmax(i(vimeas))")
    add("ipeak_sink_a", "peak_sink_current", "A", {"min": ipk_sink_min}, expr="-vecmin(i(vimeas))")
    # UVLO end-to-end behaviour (decision record 0001 Decision 5): reported, not
    # graded -- the harness record scores these informational too, and the UVLO
    # trip points are an open finding (spec Sec.5, DR-0018), not a ratified bound.
    add("uvlo_lockout_at_in_high", None, "V", None, spice=".meas tran uvlo_lockout_at_in_high FIND v(x3.lockout) AT=200n")
    add("uvlo_vout_at_in_high_v", None, "V", None, spice=".meas tran uvlo_vout_at_in_high_v FIND v(OUT) AT=200n")
    for m in meas:
        if m["spec_row"] is None:
            del m["spec_row"]
    return meas


def request(processes, temps, vlogic, vdrv, tpd_max, ipk_source_min, ipk_sink_min):
    return klt_request.envelope(
        "body.spice",
        {
            "process": klt_request.process_entries(processes),
            "temperature_c": temps,
            "supply_v": {"vsup_logic": vlogic, "vsup_drv": vdrv},
        },
        {"kind": "tran", "args": "0.1n 700n"},
        measurements(tpd_max, ipk_source_min, ipk_sink_min),
    )


def main():
    # tied two-rail points: (vlogic, vdrv) low / nominal / high, as the harness ties them
    lo, mid, hi = ([2.97, 4.5], [3.3, 5.0], [3.63, 5.5])

    def rails(points):
        return [p[0] for p in points], [p[1] for p in points]

    # (processes, temps, rail points, tpd_max, source_min, sink_min)
    shards = {
        # Sec.3 target bounds, every corner without a ratified exception
        "request-nominal-main.json": (["tt", "ff", "fs", "sf"], [-40.0, 27.0, 125.0], [lo, mid, hi], 50e-9, 0.5, 0.5),
        "request-nominal-ss-warm-hot.json": (["ss"], [27.0, 125.0], [lo, mid, hi], 50e-9, 0.5, 0.5),
        "request-nominal-ss-cold-mid-high.json": (["ss"], [-40.0], [mid, hi], 50e-9, 0.5, 0.5),
        # DR-0020: ss / -40 C / low line, ipeak_source_a >= 0.45 A
        "request-nominal-ss-cold-low.json": (["ss"], [-40.0], [lo], 50e-9, 0.45, 0.5),
        # Sec.3 stretch bounds
        "request-stretch-main.json": (["tt", "ff", "fs"], [-40.0, 27.0, 125.0], [[3.3, 6.0]], 25e-9, 1.0, 1.0),
        "request-stretch-slow-cold-mid.json": (["ss", "sf"], [-40.0, 27.0], [[3.3, 6.0]], 25e-9, 1.0, 1.0),
        # DR-0016: ss_125c / sf_125c, ipeak_sink_a >= 0.85 A
        "request-stretch-hot-slow.json": (["ss", "sf"], [125.0], [[3.3, 6.0]], 25e-9, 1.0, 0.85),
    }
    for name, (procs, temps, points, tpd, src, snk) in shards.items():
        vlogic, vdrv = rails(points)
        req = request(procs, temps, vlogic, vdrv, tpd, src, snk)
        (HERE / name).write_text(json.dumps(req, indent=2) + "\n")


if __name__ == "__main__":
    main()
