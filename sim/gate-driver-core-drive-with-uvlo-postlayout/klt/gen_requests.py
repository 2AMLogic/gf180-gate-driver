#!/usr/bin/env python3
"""Emit the `klt sim` requests for gate-driver-core-drive-with-uvlo-postlayout
(issue #560). Deterministic.

    python3 sim/gate-driver-core-drive-with-uvlo-postlayout/klt/gen_requests.py

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

Every bound is copied from ../testbench/tb.json's `checks` (23 checks; four
with a `stretch` override: tpdlh_s, tpdhl_s, ipeak_source_a, ipeak_sink_a),
including the nominal bounds on the checks without an override, which keep
their nominal bound in the stretch request too. No corner-scoped decision
record is imported: this facet's tb.json carries none -- its ipeak_sink_a
entry notes DR-0016 as record-narrative context, not a bound -- so the
stretch sink bound is 1 A even at ss/sf 125 C, the same un-sharded policy as
the PEX requests (../../gate-driver-core-drive-with-uvlo/klt/pex/, signoff
item 7).

Measurements follow the schematic-facet method signoff Item 5 records
(verification/signoff/README.md): crossings on the rail-normalised monitors
(vin_n, vout_n) rather than the harness's measured-swing thresholds, the IN
pulse built from a unit pulse scaled by v(VDD_LOGIC), and the flat extracted
probe names (v(x2_n1)..v(x2_n5), v(x3_lockout)) the deck-level DUT .include
preserves. All three 200 ns probes of the harness bench are kept: they are
FIND-based (crossing-free), so unlike the timing rows they return a value at
every corner, UVLO-locked included -- that asymmetry is how a locked corner
is told apart from a switching one, and why a locked corner's rise/fall/
propagation rows report no value rather than a swing-relative score on a
glitch (signoff Item 5's honest-recording note; draft DR-0022 at the
schematic level). vin_max_v / vin_min_v are carried ungraded (informational
columns of this facet's records; no tb.json check). See this directory's
README.md.

The 20 base checks, the corner axes, the request builder, and the four-file
writer are not restated here (issue #584): this script loads the sibling
drive generator -- sim/gate-driver-core-drive-postlayout/klt/gen_requests.py,
whose ``gen_requests`` basename collides with this file's own, hence the
by-path importlib load rather than ``import gen_requests`` -- and passes the
three 200 ns probes below as ``extra_measurements``, appended after the base
set exactly where the committed request-*.json files carry them. The process
axis and the engine/models/batch/options envelope likewise come from
sim/harness/klt_request.py, shared with the other generators (issue #441).
sim/test_gen_requests.py pins that this script still reproduces its committed
request bytes and that the effective limits still equal the tb.json checks.
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIBLING = (
    HERE.parents[1] / "gate-driver-core-drive-postlayout" / "klt" / "gen_requests.py"
)

_spec = importlib.util.spec_from_file_location("drive_postlayout_gen", SIBLING)
drive_postlayout = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drive_postlayout)


def uvlo_probes():
    """The three 200 ns probes this facet adds to the sibling's base 20.

    tb.json analyses: lockout_at_in_high / vout_at_in_high /
    vdrv_at_in_high, mid-way through IN's first high pulse, decision record
    0001 Decision 5 evidence: FIND-based, so they never go missing at a
    UVLO-locked corner. Flat extracted name v(x3_lockout) in place of the
    schematic's v(x3.lockout). Key order matches the sibling's ``add()``
    (name, unit, form, limits) so the emitted bytes are unchanged.
    """
    return [
        {
            "name": "uvlo_lockout_at_in_high",
            "unit": "V",
            "spice": (
                ".meas tran uvlo_lockout_at_in_high FIND v(x3_lockout) AT=200n"
            ),
            "limits": {"min": -0.5, "max": 6.6},
        },
        {
            "name": "uvlo_vout_at_in_high_v",
            "unit": "V",
            "spice": ".meas tran uvlo_vout_at_in_high_v FIND v(OUT) AT=200n",
            "limits": {"min": -0.05, "max": 6.6},
        },
        {
            "name": "uvlo_vdrv_at_in_high_v",
            "unit": "V",
            "spice": ".meas tran uvlo_vdrv_at_in_high_v FIND v(VDD_DRV) AT=200n",
            "limits": {"min": -0.05, "max": 6.6},
        },
    ]


def main():
    drive_postlayout.write_requests(HERE, uvlo_probes())


if __name__ == "__main__":
    main()
