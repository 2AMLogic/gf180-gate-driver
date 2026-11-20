#!/usr/bin/env python3
"""Emit the `klt sim` requests for gate-driver-core-drive-postlayout (issue #560). Deterministic.

    python3 sim/gate-driver-core-drive-postlayout/klt/gen_requests.py

Writes four requests -- nominal and 6 V stretch, each against both extracted
DUTs (body.spice -> layout/lvs/gate_driver_core.extracted.spice, body-rc.spice
-> layout/lvs/gate_driver_core.extracted-rc.spice):

  * request-nominal.json / request-nominal-rc.json: the 45-point +/-10 %
    tied-rail matrix (5 processes x 3 temperatures x 3 rail points), nominal
    bounds.
  * request-stretch.json / request-stretch-rc.json: the 15-point 6 V stretch
    rail (5 x 3 x 1), stretch bounds. `measurements[].limits` is min/max only
    and applies to every corner of a request, so the 6 V rows -- the only
    points the stretch tier applies to (sim/README.md "Two-tier checks") --
    get their own request; the union of the two requests is exactly the
    harness grid's 45 + 15 points, each once.

Every bound is copied from ../testbench/tb.json's `checks` (20 checks; four
with a `stretch` override: tpdlh_s, tpdhl_s, ipeak_source_a, ipeak_sink_a),
including the nominal bounds on the checks without an override, which keep
their nominal bound in the stretch request too. No corner-scoped decision
record is imported: unlike the schematic item-5 shards
(../../gate-driver-core-drive-with-uvlo/klt/), DR-0016 / DR-0020 live in that
facet's record narrative, not in this facet's tb.json -- so the stretch sink
bound is 1 A even at ss/sf 125 C and the nominal source bound is 0.5 A even
at ss / -40 C / low line, the same un-sharded policy as the PEX requests
(../../gate-driver-core-drive-with-uvlo/klt/pex/, signoff item 7).

Measurements follow the schematic-facet method signoff Item 5 records
(verification/signoff/README.md): crossings on the rail-normalised monitors
(vin_n, vout_n) rather than the harness's measured-swing thresholds, the IN
pulse built from a unit pulse scaled by v(VDD_LOGIC), and the flat extracted
probe names (v(x2_n1)..v(x2_n5)) the deck-level DUT .include preserves.
vin_max_v / vin_min_v are carried ungraded (informational columns of this
facet's records; no tb.json check). See this directory's README.md.

The process axis and the engine/models/batch/options envelope are not defined
here: both come from sim/harness/klt_request.py, shared with the other
generators (issue #441). sim/test_gen_requests.py pins that this script still
reproduces its committed request bytes and that the effective limits still
equal the tb.json checks.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # sim/, for the harness package
from harness import klt_request  # noqa: E402

# The full five-corner MOS axis and temperature grid of the harness records,
# in the order the committed request-*.json files carry them.
PROCESSES = ["tt", "ff", "ss", "fs", "sf"]
TEMPS_C = [-40.0, 27.0, 125.0]

# The harness's tied two-rail grid (corners.DEFAULT_RAILS): vlogic/vdrv swept
# together at low/nominal/high, plus vdrv's opt-in 6 V stretch extra.
NOMINAL_VLOGIC = [2.97, 3.3, 3.63]
NOMINAL_VDRV = [4.5, 5.0, 5.5]
STRETCH_VLOGIC = [3.3]
STRETCH_VDRV = [6.0]


def measurements(stretch):
    """The tb.json checks as klt measurements, at this tier's bounds.

    The four §3 rows with a stretch override tighten with the tier; every
    other check keeps its (tier-independent) nominal bound in both requests.
    """
    tpd_max = 25e-9 if stretch else 50e-9
    ipk_min = 1.0 if stretch else 0.5
    meas = []

    def add(name, unit, limits, spec_row=None, **form):
        entry = {"name": name, "unit": unit}
        if spec_row is not None:
            entry["spec_row"] = spec_row
        entry.update(form)
        if limits is not None:
            entry["limits"] = limits
        meas.append(entry)

    rise = ".meas tran trise_s TRIG v(vout_n) VAL=0.1 RISE=1 TARG v(vout_n) VAL=0.9 RISE=1"
    fall = ".meas tran tfall_s TRIG v(vout_n) VAL=0.9 FALL=1 TARG v(vout_n) VAL=0.1 FALL=1"
    plh = ".meas tran tpdlh_s TRIG v(vin_n) VAL=0.5 RISE=1 TARG v(vout_n) VAL=0.5 RISE=1"
    phl = ".meas tran tpdhl_s TRIG v(vin_n) VAL=0.5 FALL=1 TARG v(vout_n) VAL=0.5 FALL=1"
    add("trise_s", "s", {"max": 50e-9}, spec_row="rise_fall_time", spice=rise)
    add("tfall_s", "s", {"max": 50e-9}, spec_row="rise_fall_time", spice=fall)
    add("tpdlh_s", "s", {"max": tpd_max}, spec_row="propagation_delay", spice=plh)
    add("tpdhl_s", "s", {"max": tpd_max}, spec_row="propagation_delay", spice=phl)
    add("ipeak_source_a", "A", {"min": ipk_min}, spec_row="peak_source_current",
        expr="vecmax(i(vimeas))")
    add("ipeak_sink_a", "A", {"min": ipk_min}, spec_row="peak_sink_current",
        expr="-vecmin(i(vimeas))")
    # tb.json sanity and spec Sec.2.3 gate-ceiling rows: every check carried
    # at its own bound, probing the flat extracted node names.
    add("vout_max_v", "V", {"max": 6.6}, expr="vecmax(v(OUT))")
    add("vout_min_v", "V", {"min": -0.05}, expr="vecmin(v(OUT))")
    # measured columns of this facet's records without a tb.json check
    add("vin_max_v", "V", None, expr="vecmax(v(IN))")
    add("vin_min_v", "V", None, expr="vecmin(v(IN))")
    add("indrv_max_v", "V", {"max": 6.6}, expr="vecmax(v(IN_DRV))")
    add("indrv_min_v", "V", {"min": -0.05}, expr="vecmin(v(IN_DRV))")
    for i in range(1, 6):
        add(f"n{i}_max_v", "V", {"max": 6.6}, expr=f"vecmax(v(x2_n{i}))")
        add(f"n{i}_min_v", "V", {"min": -0.05}, expr=f"vecmin(v(x2_n{i}))")
    return meas


def request(netlist, stretch):
    vlogic, vdrv = (
        (STRETCH_VLOGIC, STRETCH_VDRV) if stretch
        else (NOMINAL_VLOGIC, NOMINAL_VDRV)
    )
    return klt_request.envelope(
        netlist,
        {
            "process": klt_request.process_entries(PROCESSES),
            "temperature_c": TEMPS_C,
            "supply_v": {"vsup_logic": vlogic, "vsup_drv": vdrv},
        },
        {"kind": "tran", "args": "0.1n 700n"},
        measurements(stretch),
    )


def main():
    for body, suffix in (("body.spice", ""), ("body-rc.spice", "-rc")):
        for tier in ("nominal", "stretch"):
            name = f"request-{tier}{suffix}.json"
            (HERE / name).write_text(
                json.dumps(request(body, tier == "stretch"), indent=2) + "\n"
            )


if __name__ == "__main__":
    main()
