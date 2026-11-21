#!/usr/bin/env python3
"""Emit the `klt sim` requests for decision record 0024's adoption gate 3
(issue #556): the startup-path verification grid of the UVLO `Vbe`/`dVbe`
candidate. Deterministic.

    python3 sim/uvlo-reference-study/klt/gen_startup_requests.py

Twelve requests, one per stimulus of the plan committed in ../README.md
("Gate 3: startup path"):

* five power-on ramp rates, 0 -> 6 V, from 200 us per edge down to the 1 ns
  edge of ../../uvlo-trip-verification/klt/body-response.spice;
* three power-ons to a stuck rail (2.0 / 3.0 / 5.0 V), the dynamic form of
  record 0024's settled six-row table;
* one brown-out: 6 V -> 1.5 V in 1 ns, hold, re-ramp (the partially
  discharged state -- 1.5 V is below the core's regulation headroom but not
  0 V);
* two dead-initialised cores (.ic nfb = rail, uic zeroes the rest) at fixed
  2.0 / 5.0 V rails -- 0024's adverse initial condition, expressed natively
  through `options.initial_conditions` (klt issue #3881), never by editing
  the DUT;
* the negative control: the MKICK-deleted DUT
  (../../uvlo_bandgap_ref_nokick.spice), dead-initialised at 2.0 V, at the
  single deterministic point tt/27 C that 0024 measured by hand. It carries
  the SAME measurements and limits as the MKICK-present dead-init request so
  the committed checks demonstrably detect the known-bad circuit.

Pass criterion (tied to the ratified windows of decision record 0001
Decision 4, nothing relaxed): `lockout` must be asserted and OUT unreleased
whenever VDD_DRV is below the ratified falling-trip window's 3.3 V floor --
graded as (a) the release crossing (lockout falling through the harness's
fixed 1.5 V level) occurring at VDD_DRV >= 3.3 V on every ramp and re-ramp,
and (b) settled lockout HIGH / OUT <= 0.5 V (the harness response row's own
low proxy, ../../uvlo-trip-verification/klt/gen_requests.py OUT_LOW_V) on
every stimulus that parks below the window. The reference core must be alive
(settled nvref >= 1.1 V against the measured 1.215-1.239 V corner range)
whenever the UVLO is expected to function. The pre-assert power-up interval
(every node still at 0 V with the rail below the digital chain's own
threshold) is bounded per corner by the reported `assert_v` and is a
property of every UVLO, the DR-0018 baseline included; it is stated in the
plan, not graded.

The process axis and the request envelope come from sim/harness/klt_request.py
(issue #441), exactly as in ../../uvlo-trip-verification/klt/gen_requests.py
-- this is a thin script over the shared helpers, not a third copy of the
scaffolding. Bounds stay literals (klt wants plain numbers), and
sim/test_gen_requests.py pins these generators to their committed request
bytes.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # sim/, for the harness package
from harness import klt_request  # noqa: E402

TEMPS = [-40.0, 27.0, 125.0]

# The harness's fixed absolute lockout level (same literal as
# ../../uvlo-trip-verification/klt/gen_requests.py: below every measured
# corner's trip voltage, above 0 V; klt requires WHEN thresholds as numbers).
LOCKOUT_LEVEL_V = 1.5
# Ratified falling-trip window floor, DR-0001 Decision 4 (3.3-3.9 V): the
# release decision -- lockout falling through the level -- must never happen
# below it.
RELEASE_FLOOR_V = 3.3
# Settled reference floor: the measured 15-corner range is 1.215-1.239 V
# (README study 2); 1.1 V grades "core alive" with >100 mV of margin, and the
# dead core reads 0.117-0.373 V (record 0024).
NVREF_FLOOR_V = 1.1
# OUT low proxy of the ratified response row (gen_requests.py OUT_LOW_V).
OUT_LOW_V = 0.5


def _meas(name, spice, unit, limits=None, spec_row=None, on_unreached=None):
    row = {"name": name, "unit": unit}
    if spec_row is not None:
        row["spec_row"] = spec_row
    row["spice"] = spice
    if limits is not None:
        row["limits"] = limits
    if on_unreached is not None:
        row["on_unreached"] = on_unreached
    return row


def base(netlist, analysis, measurements, initial_conditions=None,
         process=None, temps=None):
    corners = {
        "process": process if process is not None else klt_request.process_entries(),
        "temperature_c": TEMPS if temps is None else temps,
    }
    req = klt_request.envelope(netlist, corners, analysis, measurements)
    if initial_conditions is not None:
        # klt issue #3881: rendered as file-scope `.ic v(n)=<v>` cards plus
        # `uic` on the tran command; every node the map does not name starts
        # the transient at 0 V -- exactly 0024's dead initial condition.
        req["options"]["initial_conditions"] = [
            {"match": {}, "values": dict(initial_conditions)}
        ]
    return req


def _settled(from_s, to_s):
    """Core-alive and released-end-state grades for a ramp that parks at 6 V."""
    return [
        _meas(
            "nvref_settled",
            f".meas tran nvref_settled AVG v(nvref) FROM={from_s} TO={to_s}",
            "V", {"min": NVREF_FLOOR_V}, "uvlo",
        ),
        _meas(
            "lockout_settled",
            f".meas tran lockout_settled AVG v(lockout) FROM={from_s} TO={to_s}",
            "V", {"max": LOCKOUT_LEVEL_V}, "uvlo",
        ),
    ]


def ramp_slow(from_s, to_s):
    """Slow ramps: the comparator resolves during power-up, so the assert and
    release crossings both exist and the release level is the graded safety
    quantity."""
    lvl = f"v(lockout)={LOCKOUT_LEVEL_V:g}"
    return [
        _meas(
            "release_v",
            f".meas tran release_v FIND v(VDD_DRV) WHEN {lvl} FALL=1",
            "V", {"min": RELEASE_FLOOR_V}, "uvlo",
        ),
        # Reported, not graded: bounds the pre-assert power-up interval
        # (lockout cannot be driven high before the chain has supply).
        _meas(
            "assert_v",
            f".meas tran assert_v FIND v(VDD_DRV) WHEN {lvl} RISE=1",
            "V",
        ),
    ] + _settled(from_s, to_s)


def hold_below(from_s, to_s):
    """Rail parked below the window: lockout asserted, OUT low, core alive."""
    return [
        _meas(
            "lockout_min",
            f".meas tran lockout_min MIN v(lockout) FROM={from_s} TO={to_s}",
            "V", {"min": LOCKOUT_LEVEL_V}, "uvlo",
        ),
        _meas(
            "out_max",
            f".meas tran out_max MAX v(OUT) FROM={from_s} TO={to_s}",
            "V", {"max": OUT_LOW_V}, "uvlo",
        ),
        _meas(
            "nvref_settled",
            f".meas tran nvref_settled AVG v(nvref) FROM={from_s} TO={to_s}",
            "V", {"min": NVREF_FLOOR_V}, "uvlo",
        ),
    ]


def hold_5v(from_s, to_s):
    """Rail parked at 5 V (above every corner's rising trip): released with
    the core alive -- the 0024 5 V row at 15 corners."""
    return [
        _meas(
            "lockout_max",
            f".meas tran lockout_max MAX v(lockout) FROM={from_s} TO={to_s}",
            "V", {"max": LOCKOUT_LEVEL_V}, "uvlo",
        ),
        _meas(
            "nvref_settled",
            f".meas tran nvref_settled AVG v(nvref) FROM={from_s} TO={to_s}",
            "V", {"min": NVREF_FLOOR_V}, "uvlo",
        ),
    ]


def brownout():
    lvl = f"v(lockout)={LOCKOUT_LEVEL_V:g}"
    return [
        _meas(
            "hold_out_max",
            ".meas tran hold_out_max MAX v(OUT) FROM=70u TO=105u",
            "V", {"max": OUT_LOW_V}, "uvlo",
        ),
        # Reported, not graded: at a 1.5 V rail the inverters' own high level
        # (~1.5 V) leaves no margin over the 1.5 V level, so OUT -- pulled to
        # the rail by rpu on a wrongful release -- is the discriminator.
        _meas(
            "hold_lockout_min",
            ".meas tran hold_lockout_min MIN v(lockout) FROM=70u TO=105u",
            "V",
        ),
        _meas(
            "rerelease_v",
            f".meas tran rerelease_v FIND v(VDD_DRV) WHEN {lvl} FALL=1 TD=110u",
            "V", {"min": RELEASE_FLOOR_V}, "uvlo",
        ),
        _meas(
            "nvref_settled",
            ".meas tran nvref_settled AVG v(nvref) FROM=150u TO=180u",
            "V", {"min": NVREF_FLOOR_V}, "uvlo",
        ),
    ]


def deadinit(rail_v, graded_output):
    meas = [
        _meas(
            "nvref_settled",
            ".meas tran nvref_settled AVG v(nvref) FROM=150u TO=200u",
            "V", {"min": NVREF_FLOOR_V}, "uvlo",
        ),
        # Reported, not graded: time for the restarted core to reach the
        # alive floor (crossing exists because uic starts nvref at 0 V).
        # on_unreached "null" keeps this report-only probe from erroring the
        # corner in the negative control, where nvref never gets there -- the
        # control must FAIL on the same graded limits, not on this row.
        _meas(
            "t_alive",
            f".meas tran t_alive WHEN v(nvref)={NVREF_FLOOR_V:g} RISE=1",
            "s", None, None, "null",
        ),
    ]
    if graded_output:
        # 2.0 V rail: below the window, so the output state is graded too
        # with the same hold_below checks. At 5.0 V released is the correct
        # settled state, so only the restart is graded there.
        meas += [
            _meas(
                "lockout_min",
                ".meas tran lockout_min MIN v(lockout) FROM=150u TO=200u",
                "V", {"min": LOCKOUT_LEVEL_V}, "uvlo",
            ),
            _meas(
                "out_max",
                ".meas tran out_max MAX v(OUT) FROM=150u TO=200u",
                "V", {"max": OUT_LOW_V}, "uvlo",
            ),
        ]
    else:
        meas.append(
            _meas(
                "lockout_settled",
                ".meas tran lockout_settled AVG v(lockout) FROM=150u TO=200u",
                "V",
            )
        )
    return meas


def settled_1ns(from_s, to_s):
    """The 1 ns step: settled end state plus the reported startup time."""
    return [
        _meas(
            "nvref_settled",
            f".meas tran nvref_settled AVG v(nvref) FROM={from_s} TO={to_s}",
            "V", {"min": NVREF_FLOOR_V}, "uvlo",
        ),
        _meas(
            "lockout_settled",
            f".meas tran lockout_settled AVG v(lockout) FROM={from_s} TO={to_s}",
            "V", {"max": LOCKOUT_LEVEL_V}, "uvlo",
        ),
        _meas(
            "t_alive",
            f".meas tran t_alive WHEN v(nvref)={NVREF_FLOOR_V:g} RISE=1",
            "s", None, None, "null",
        ),
    ]


def main():
    tran = lambda args: {"kind": "tran", "args": args}  # noqa: E731
    reqs = {
        # Power-on ramp rates, slow to the 1 ns edge. Slow: crossings graded.
        "request-startup-ramp-slow.json": base(
            "body-startup-ramp-slow.spice", tran("100n 240u"),
            ramp_slow("220u", "240u"),
        ),
        "request-startup-ramp-harness.json": base(
            "body-startup-ramp-harness.spice", tran("10n 60u"),
            ramp_slow("50u", "60u"),
        ),
        # Fast: no comparator can assert inside the ramp's own sub-us window
        # crossing, so a no-crossing .meas would read as a false error; the
        # settled end state is graded instead (plan states this per rate).
        "request-startup-ramp-fast.json": base(
            "body-startup-ramp-fast.spice", tran("1n 60u"),
            _settled("50u", "60u"),
        ),
        "request-startup-ramp-vfast.json": base(
            "body-startup-ramp-vfast.spice", tran("0.1n 20u"),
            _settled("18u", "20u"),
        ),
        "request-startup-ramp-1ns.json": base(
            "body-startup-ramp-1ns.spice", tran("0.1n 40u"),
            settled_1ns("30u", "40u"),
        ),
        # Stuck rails: the dynamic form of 0024's settled table.
        "request-startup-hold-2v0.json": base(
            "body-startup-hold-2v0.spice", tran("10n 220u"),
            hold_below("120u", "220u"),
        ),
        "request-startup-hold-3v0.json": base(
            "body-startup-hold-3v0.spice", tran("10n 220u"),
            hold_below("120u", "220u"),
        ),
        "request-startup-hold-5v0.json": base(
            "body-startup-hold-5v0.spice", tran("10n 220u"),
            hold_5v("120u", "220u"),
        ),
        # Brown-out and re-ramp from a partially discharged rail.
        "request-startup-brownout.json": base(
            "body-startup-brownout.spice", tran("5n 180u"), brownout(),
        ),
        # Dead-initialised core, 0024's adverse initial condition.
        "request-startup-deadinit-2v0.json": base(
            "body-startup-deadinit-2v0.spice", tran("10n 200u"),
            deadinit(2.0, graded_output=True),
            initial_conditions={"nfb": 2.0},
        ),
        "request-startup-deadinit-5v0.json": base(
            "body-startup-deadinit-5v0.spice", tran("10n 200u"),
            deadinit(5.0, graded_output=False),
            initial_conditions={"nfb": 5.0},
        ),
        # Negative control: same measurements and limits as the 2.0 V
        # dead-init request above, on the MKICK-deleted DUT, at the single
        # deterministic point (tt/27 C) 0024 measured by hand.
        "request-startup-deadinit-2v0-nokick.json": base(
            "body-startup-deadinit-2v0-nokick.spice", tran("10n 200u"),
            deadinit(2.0, graded_output=True),
            initial_conditions={"nfb": 2.0},
            process=klt_request.process_entries(["tt"]),
            temps=[27.0],
        ),
    }
    for name, req in reqs.items():
        (HERE / name).write_text(json.dumps(req, indent=2) + "\n")


if __name__ == "__main__":
    main()
