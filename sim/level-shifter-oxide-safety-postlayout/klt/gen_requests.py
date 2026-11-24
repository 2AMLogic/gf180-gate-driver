#!/usr/bin/env python3
"""Emit the `klt sim` requests for level-shifter-oxide-safety-postlayout (issue #559). Deterministic.

    python3 sim/level-shifter-oxide-safety-postlayout/klt/gen_requests.py

Writes two requests, one per extracted DUT (body.spice ->
layout/lvs/gate_driver_core.extracted.spice, body-rc.spice ->
layout/lvs/gate_driver_core.extracted-rc.spice):

  * request-norcx.json / request-rc.json: the harness grid's full 60 points
    (5 processes x 3 temperatures x 4 tied rail points -- 2.97/4.5, 3.3/5.0,
    3.63/5.5 and the 3.3/6.0 vdrv stretch extra), the same grid the baseline
    harness records 20261114-194502-55af608 (no-RC) and
    20261114-202350-bb5cab0 (RC) ran. One request per DUT, not a
    nominal/stretch pair: every bound in ../testbench/tb.json's `checks` is
    tier-independent (the 6 V row is judged at the same 3.63 V / 6 V / 0.95 /
    0.05 bounds as every other row), so `measurements[].limits` needs no
    sharding -- the #560 tier split does not apply here.

This is the first `klt sim` route whose graded figures include quantities the
harness computes as one `.meas` result divided by another (vout_hi_ratio =
v(IN_DRV)@59ns / v(VDD_DRV)@59ns, vout_lo_ratio = v(IN_DRV)@19ns /
v(VDD_DRV)@59ns) -- the exact "derived from another .meas result" shape that
kept the schematic facets on the harness (the batch-backend gap
2AMLogic/klayout-tools#4902 tracks for the scalar-analysis form). The
requests therefore use the `analysis_steps[]` form (one `wave` transient
step, the harness's own `tran 20p 200n`):

  * the step carries the three FIND...AT samples (hi = IN_DRV at 59 ns,
    lo = IN_DRV at 19 ns, drv = VDD_DRV at 59 ns) as step-scoped `.meas`
    cards, the two TRIG/TARG propagation delays at the harness fragment's
    literal 1.65 V / 2.5 V levels, and the waveform reductions as `expr`
    measurements over `vecmax`/`abs` -- the six thin-oxide gate excursion
    differences (dq1..dq6) and four XCCOMP MiM leg voltages (dvc1..dvc4) as
    `intermediate` lets, with the checked maxima (vgate_thinox_max,
    vccomp_dev_max) and the unbounded columns (vna_peak, vnb_peak,
    vccomp_stack_max) as reported step results;
  * the top-level `measurements[]` are the nine record columns as derived
    expressions over `wave.*` results -- aliases for the reductions, ns
    conversions for the delays, and the two ratios as `wave.hi / wave.drv`
    and `wave.lo / wave.drv`, graded through `limits` exactly as the harness
    grades them.

Every bound is read from ../testbench/tb.json's `checks` at generate time
(not re-typed), so the request and the harness manifest cannot disagree; the
nine column names and their `measure` expressions are cross-checked against
its `measure` map. The process
axis and the engine/models/batch/options envelope come from
sim/harness/klt_request.py (`steps_envelope`, shared with the other
generators per issue #441). sim/test_gen_requests.py pins that this script
still reproduces its committed request bytes, that the effective limits
still equal the tb.json checks, and that the committed envelopes cover the
60-point grid exactly once per DUT.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # sim/, for the harness package
from harness import klt_request  # noqa: E402

# The harness grid of this facet (sim/README.md "Two-tier checks": the vdrv
# 6 V point is vdrv's opt-in stretch extra; this facet's checks have no
# stretch override, so it is graded at the same bounds as every other row).
PROCESSES = ["tt", "ff", "ss", "fs", "sf"]
TEMPS_C = [-40.0, 27.0, 125.0]
VLOGIC = [2.97, 3.3, 3.63, 3.3]
VDRV = [4.5, 5.0, 5.5, 6.0]

# The nine record columns, in the tb.json `measure` order the harness
# records carry: the unit each is reported in (the delay columns are
# converted to ns at the top level, as the harness's t_plh_ns does), the
# tb.json `measure` expression each column restates (the pre-conversion
# names -- the harness multiplies t_plh/t_phl by 1e9 itself), and the
# derived request expression over `wave.*` results that reproduces it.
COLUMNS = (
    ("vgate_thinox_max", "V", "thinox_worst", "wave.vgate_thinox_max"),
    ("vna_peak", "V", "na_peak", "wave.vna_peak"),
    ("vnb_peak", "V", "nb_peak", "wave.vnb_peak"),
    ("vccomp_dev_max", "V", "vccomp_dev", "wave.vccomp_dev_max"),
    ("vccomp_stack_max", "V", "vccomp_stack", "wave.vccomp_stack_max"),
    ("t_plh_ns", "ns", "t_plh*1e9", "wave.t_plh * 1e9"),
    ("t_phl_ns", "ns", "t_phl*1e9", "wave.t_phl * 1e9"),
    ("vout_hi_ratio", "V/V", "outhi_ratio", "wave.hi / wave.drv"),
    ("vout_lo_ratio", "V/V", "outlo_ratio", "wave.lo / wave.drv"),
)


def manifest():
    """The harness manifest this request restates, loaded and sanity-checked."""
    tb = json.loads((HERE / ".." / "testbench" / "tb.json").read_text())
    if list(tb["measure"].items()) != [(n, s) for n, _, s, _ in COLUMNS]:
        raise SystemExit(
            "tb.json `measure` map drifted from the generator's COLUMNS: "
            f"{list(tb['measure'].items())} vs "
            f"{[(n, s) for n, _, s, _ in COLUMNS]} -- update COLUMNS "
            "together with the request bodies."
        )
    return tb


def step_measurements():
    """The `wave` step's own measurements, over one `tran 20p 200n` solve.

    Mirrors ../testbench/tb.json's `analyses` block: the six `dq*` /
    four `dvc*` waveform reductions are its `let`/`meas max` pairs restated
    as `vecmax(abs(...))` expressions (`intermediate`: let-only, not
    reported), the checked maxima are its `thinox_worst`/`vccomp_dev` lets,
    and the `.meas` cards are its trig/targ and FIND...AT lines verbatim
    (name, nodes, literal 1.65 V / 2.5 V levels, 19 ns / 59 ns instants).
    """
    def inter(name, expr):
        return {"name": name, "expr": expr, "intermediate": True}

    def expr(name, expr):
        return {"name": name, "expr": expr, "unit": "V"}

    def spice(name, card):
        return {"name": name, "spice": card}

    dq = [
        inter("dq1", "vecmax(abs(v(IN)-v(x1_inb)))"),
        inter("dq2", "vecmax(abs(v(IN)-v(GND_LOGIC)))"),
        inter("dq3", "vecmax(abs(v(IN)-v(VDD_LOGIC)))"),
        inter("dq4", "vecmax(abs(v(IN)-v(x1_na)))"),
        inter("dq5", "vecmax(abs(v(x1_inb)-v(x1_nb)))"),
        inter("dq6", "vecmax(abs(v(x1_inb)-v(GND_LOGIC)))"),
    ]
    dvc = [
        inter("dvc1", "vecmax(abs(v(x1_ncb)-v(ANON293)))"),
        inter("dvc2", "vecmax(abs(v(ANON293)-v(ANON294)))"),
        inter("dvc3", "vecmax(abs(v(ANON294)-v(ANON295)))"),
        inter("dvc4", "vecmax(abs(v(ANON295)-v(IN_DRV)))"),
    ]
    return dq + dvc + [
        # max()/min() are the two-argument control-language forms; a plain
        # max(x) over a vector is vecmax(x) (klt sim docs, "Functions expr
        # does not have").
        expr("vgate_thinox_max",
             "max(max(max(dq1,dq2),max(dq3,dq4)),max(dq5,dq6))"),
        expr("vna_peak", "vecmax(v(x1_na))"),
        expr("vnb_peak", "vecmax(v(x1_nb))"),
        expr("vccomp_dev_max",
             "max(max(dvc1,dvc2),max(dvc3,dvc4))"),
        expr("vccomp_stack_max", "vecmax(abs(v(x1_ncb)-v(IN_DRV)))"),
        spice("t_plh",
              ".meas tran t_plh TRIG v(IN) VAL=1.65 RISE=1 "
              "TARG v(IN_DRV) VAL=2.5 RISE=1"),
        spice("t_phl",
              ".meas tran t_phl TRIG v(IN) VAL=1.65 FALL=1 "
              "TARG v(IN_DRV) VAL=2.5 FALL=1"),
        spice("hi", ".meas tran hi FIND v(IN_DRV) AT=59n"),
        spice("lo", ".meas tran lo FIND v(IN_DRV) AT=19n"),
        spice("drv", ".meas tran drv FIND v(VDD_DRV) AT=59n"),
    ]


def measurements(tb):
    """The nine record columns as derived expressions over `wave.*` results."""
    out = []
    for name, unit, _, request_expr in COLUMNS:
        entry = {"name": name, "unit": unit, "expr": request_expr}
        # The checked bounds come from the manifest itself, never re-typed:
        # vgate_thinox_max / vccomp_dev_max / vout_hi_ratio / vout_lo_ratio
        # are exactly tb.json's four `checks`.
        check = tb["checks"].get(name)
        if check is not None:
            limits = {}
            if "max" in check:
                limits["max"] = check["max"]
            if "min" in check:
                limits["min"] = check["min"]
            if not limits:
                raise SystemExit(f"tb.json check {name} carries no min/max")
            entry["limits"] = limits
        out.append(entry)
    unexpected = set(tb["checks"]) - {name for name, *_ in COLUMNS}
    if unexpected:
        raise SystemExit(f"tb.json checks drifted: unexpected {sorted(unexpected)}")
    return out


def request(netlist, tb):
    return klt_request.steps_envelope(
        netlist,
        {
            "process": klt_request.process_entries(PROCESSES),
            "temperature_c": TEMPS_C,
            "supply_v": {"vsup_logic": VLOGIC, "vsup_drv": VDRV},
        },
        [{
            "name": "wave",
            "analysis": {"kind": "tran", "args": "20p 200n"},
            "measurements": step_measurements(),
        }],
        measurements(tb),
    )


def main():
    tb = manifest()
    for body, suffix in (("body.spice", "-norcx"), ("body-rc.spice", "-rc")):
        name = f"request{suffix}.json"
        (HERE / name).write_text(
            json.dumps(request(body, tb), indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
