#!/usr/bin/env python3
"""Emit the `klt sim` requests for the UVLO and drive_rail rows of T1 item 5
(issue #377). Deterministic.

    python3 sim/uvlo-trip-verification/klt/gen_requests.py

Writes request-trip.json, request-response.json (the 15 process x temperature
points of the harness record; VDD_DRV is itself the stimulus, so no supply_v
axis) and request-rail-nominal.json / request-rail-stretch.json (the applied
drive rail, as the same tied axis as the item-5 core-drive requests). Every
bound is copied from spec/decision-records/0001 Decisions 4-5 /
spec/gate-driver.md Sec.3 (and run_uvlo_trip.py's FALLING_RANGE, RISING_RANGE,
RESPONSE_MAX_S); nothing is relaxed. Decision record 0018's false-trip finding
is NOT encoded as an exception: the corners it shows outside the ranges FAIL.
Hysteresis has a typical value only (0001 Decision 4), so it is reported
ungraded.
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
TEMPS = [-40.0, 27.0, 125.0]

# LOCKOUT is read at the harness's fixed absolute 1.5 V level (a literal: klt
# requires WHEN thresholds to be numbers).
LOCKOUT_LEVEL_V = 1.5
# Response time is timed from VDD_DRV crossing the ratified typical falling trip
# (3.6 V, DR-0001 Decision 4) to OUT reaching 0.5 V (the harness's low proxy).
# The harness times from each corner's own measured trip; over the 1 ns step edge
# the two differ by at most ~1 ns against a 500 ns bound.
RESPONSE_TRIG_V = 3.6
OUT_LOW_V = 0.5


def base(netlist, analysis, measurements, supply_v=None):
    corners = {
        "process": [{"name": n, "sections": s} for n, s in PROCESS.items()],
        "temperature_c": TEMPS,
    }
    if supply_v:
        corners["supply_v"] = supply_v
    return {
        "netlist": netlist,
        "engine": "ngspice",
        "models": {"pdk": "gf180mcuD", "lib": "libs.tech/ngspice/sm141064.ngspice"},
        "corners": corners,
        "batch": {"runner_version_check": "warn", "capacity_wait_s": 1800},
        "analysis": analysis,
        "measurements": measurements,
        "options": {
            "timeout_s": 3000,
            "keep_artifacts": False,
            "ngspice_init": ["set measureprec=10", "set numdgt=10"],
        },
    }


def trip():
    lvl = f"v(lockout)={LOCKOUT_LEVEL_V:g}"
    meas = [
        {
            "name": "falling_trip_v",
            "unit": "V",
            "spec_row": "uvlo",
            # lockout rises through the level on the way down, after the 20 us peak
            "spice": f".meas tran falling_trip_v FIND v(VDD_DRV) WHEN {lvl} RISE=1 TD=20u",
            "limits": {"min": 3.3, "max": 3.9},
        },
        {
            "name": "rising_trip_v",
            "unit": "V",
            "spec_row": "uvlo",
            # lockout falls through the level as VDD_DRV climbs past the release point
            "spice": f".meas tran rising_trip_v FIND v(VDD_DRV) WHEN {lvl} FALL=1",
            "limits": {"min": 3.6, "max": 4.2},
        },
        # Reported, not graded: 0001 Decision 4 gives hysteresis a typical value
        # (300 mV) and no ratified worst-case range.
        {
            "name": "hysteresis_v",
            "unit": "V",
            "spice": ".meas tran hysteresis_v PARAM='rising_trip_v-falling_trip_v'",
        },
    ]
    return base("body-trip.spice", {"kind": "tran", "args": "10n 40u"}, meas)


def response():
    meas = [
        {
            "name": "response_s",
            "unit": "s",
            "spec_row": "uvlo",
            "spice": (
                f".meas tran response_s TRIG v(VDD_DRV) VAL={RESPONSE_TRIG_V:g} FALL=1 "
                f"TARG v(OUT) VAL={OUT_LOW_V:g} FALL=1"
            ),
            "limits": {"max": 500e-9},
        }
    ]
    return base("body-response.spice", {"kind": "tran", "args": "0.05n 2000n"}, meas)


def rail(vdrv, limits):
    meas = [
        {
            "name": "drive_rail_v",
            "unit": "V",
            "spec_row": "drive_rail",
            "expr": "v(VDD_DRV)",
            "limits": limits,
        }
    ]
    return base("body-rail.spice", {"kind": "op", "args": ""}, meas, supply_v={"vsup_drv": vdrv})


def main():
    reqs = {
        "request-trip.json": trip(),
        "request-response.json": response(),
        # Sec.3: 5 V nominal, +/-10 % (DRM 14.1.2); 6 V stretch.
        "request-rail-nominal.json": rail([4.5, 5.0, 5.5], {"min": 4.5, "max": 5.5}),
        "request-rail-stretch.json": rail([6.0], {"min": 6.0, "max": 6.0}),
    }
    for name, req in reqs.items():
        (HERE / name).write_text(json.dumps(req, indent=2) + "\n")


if __name__ == "__main__":
    main()
