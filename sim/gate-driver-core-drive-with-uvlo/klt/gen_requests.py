#!/usr/bin/env python3
"""Emit the `klt sim` requests for T1 item 5 (issue #367). Deterministic.

    python3 sim/gate-driver-core-drive-with-uvlo/klt/gen_requests.py

Writes request-nominal.json (the +/-10 % tied-rail matrix, ratified TARGET
bounds) and request-stretch.json (the 6 V stretch rail, ratified STRETCH bounds
for the rows that have one). Every bound is copied from spec/gate-driver.md
Sec.3 / the ratified tb.json checks; nothing is relaxed, and the ratified
exceptions (DR-0016, DR-0020) are NOT encoded: the corners they bound report
FAIL in the envelope by design.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROCESS = {
    "tt": ["typical", "res_typical", "bjt_typical", "diode_typical", "moscap_typical", "mimcap_typical"],
    "ff": ["ff", "res_ff", "bjt_ff", "diode_ff", "moscap_ff", "mimcap_ff"],
    "ss": ["ss", "res_ss", "bjt_ss", "diode_ss", "moscap_ss", "mimcap_ss"],
    "fs": ["fs", "res_typical", "bjt_typical", "diode_typical", "moscap_typical", "mimcap_typical"],
    "sf": ["sf", "res_typical", "bjt_typical", "diode_typical", "moscap_typical", "mimcap_typical"],
}


def measurements(tpd_max, ipk_min):
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
    add("ipeak_source_a", "peak_source_current", "A", {"min": ipk_min}, expr="vecmax(i(vimeas))")
    add("ipeak_sink_a", "peak_sink_current", "A", {"min": ipk_min}, expr="-vecmin(i(vimeas))")
    # UVLO end-to-end behaviour (decision record 0001 Decision 5): reported, not
    # graded -- the harness record scores these informational too, and the UVLO
    # trip points are an open finding (spec Sec.5, DR-0018), not a ratified bound.
    add("uvlo_lockout_at_in_high", None, "V", None, spice=".meas tran uvlo_lockout_at_in_high FIND v(x3.lockout) AT=200n")
    add("uvlo_vout_at_in_high_v", None, "V", None, spice=".meas tran uvlo_vout_at_in_high_v FIND v(OUT) AT=200n")
    for m in meas:
        if m["spec_row"] is None:
            del m["spec_row"]
    return meas


def request(vlogic, vdrv, tpd_max, ipk_min):
    return {
        "netlist": "body.spice",
        "engine": "ngspice",
        "models": {"pdk": "gf180mcuD", "lib": "libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": n, "sections": s} for n, s in PROCESS.items()],
            "temperature_c": [-40.0, 27.0, 125.0],
            "supply_v": {"vsup_logic": vlogic, "vsup_drv": vdrv},
        },
        "batch": {"runner_version_check": "warn", "capacity_wait_s": 1800},
        "analysis": {"kind": "tran", "args": "0.1n 700n"},
        "measurements": measurements(tpd_max, ipk_min),
        "options": {
            "timeout_s": 3000,
            "keep_artifacts": False,
            "ngspice_init": ["set measureprec=10", "set numdgt=10"],
        },
    }


def main():
    # tied two-rail points: (vlogic, vdrv) low / nominal / high, as the harness ties them
    nominal = request([2.97, 3.3, 3.63], [4.5, 5.0, 5.5], 50e-9, 0.5)
    stretch = request([3.3], [6.0], 25e-9, 1.0)
    for name, req in (("request-nominal.json", nominal), ("request-stretch.json", stretch)):
        (HERE / name).write_text(json.dumps(req, indent=2) + "\n")


if __name__ == "__main__":
    main()
