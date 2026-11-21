# `klt sim` requests for gate-driver-core-drive-with-uvlo-postlayout (issue #560)

The same end-to-end bench as `../testbench/` (logic-in (IN) -> level shifter
-> output stage -> 1 nF, plus x3=uvlo actively pulling OUT low below the trip
point, against the extracted netlist of layout/gate_driver_core.gds),
restated as `klt sim` requests so the 60-point matrix can run on the Spot
batch fleet instead of a dispatch worker (#558's drive deliverable; #485
reruns both drive facets through this route). The harness records in
`../records/` are untouched. Conventions shared with the schematic item-5
route are documented once in
[`sim/README.md`](../../README.md#post-layout-drive-facets-on-the-batch-fleet-issue-560).

| File | What |
|---|---|
| `gen_requests.py` | Emits the four requests (deterministic). Every bound is copied from `../testbench/tb.json`'s `checks` (23 checks; four with a `stretch` override); the process axis and the `engine`/`models`/`batch`/`options` envelope come from [`sim/harness/klt_request.py`](../../harness/klt_request.py), shared with the other generators (issue #441). |
| `body.spice`, `body-rc.spice` | Circuit body per DUT: identical stimulus, 1 nF reference load, `vimeas` ammeter polarity and `reltol=1e-4` as the harness fragment; they differ only in which extracted DUT they `.include` at deck level — `layout/lvs/gate_driver_core.extracted.spice` (no-RC, `--combine`) and `.extracted-rc.spice` (`--parasitics`). Deck-level inclusion (no `.subckt` re-wrap) keeps the flat extracted probe names (`v(x2_n1)`..`v(x2_n5)`, `v(x3_lockout)`) addressable, exactly as the harness deck `.include`s the DUT ahead of the testbench fragment; each run's `environment.netlist_closure` pins the DUT sha256 it actually used. |
| `design.ngspice` | The PDK global-switch include the corner `.lib` sections need, copied so the batch worker can stage it (same copy as `../../gate-driver-core-drive-with-uvlo/klt/design.ngspice`). |
| `request-nominal.json` / `request-nominal-rc.json` | tt/ff/ss/fs/sf x {-40, 27, 125} C x 3 tied rail points (2.97/4.5, 3.3/5.0, 3.63/5.5 V) = 45 corners, nominal bounds — no-RC and RC DUT respectively. |
| `request-stretch.json` / `request-stretch-rc.json` | tt/ff/ss/fs/sf x {-40, 27, 125} C at 3.3/6.0 V = 15 corners, stretch bounds. |

`measurements[].limits` is min/max only and applies to every corner of a
request, so the tier split **is** the sharding: the 6 V rows — the only
stretch points of the grid (`sim/README.md` "Two-tier checks") — are their own
request, and the union of the two is the harness grid exactly, each point
once. No corner-scoped exception is encoded: this facet's `tb.json` carries
none (its `ipeak_sink_a` entry notes DR-0016 as record-narrative context, not
a bound), so the stretch sink bound is 1 A even at ss/sf 125 C — the same
un-sharded policy as the PEX requests (signoff item 7).
`sim/test_gen_requests.py` pins both the committed bytes and the manifest
equality.

All three 200 ns probes of the harness bench are kept
(`uvlo_lockout_at_in_high` on the flat extracted `v(x3_lockout)`,
`uvlo_vout_at_in_high_v`, `uvlo_vdrv_at_in_high_v`): they are FIND-based
(crossing-free), so they return a value at every corner, UVLO-locked
included. The timing rows are not: at a locked corner the rail-normalised
10/50/90 % crossings never fire and the row reports **no value** — a
failing, honestly-recorded corner — where the harness's swing-relative
thresholds would score a delay on a glitch (the same asymmetry signoff Item
5 records for the schematic facet, bounded there by draft DR-0022). The
probes' lockout/OUT correlation is what separates "locked" from "switching"
in the envelope.

Other method differences from the harness bench (same list as the drive
facet, signoff Item 5): rail-normalised monitors with literal thresholds, IN
pulse scaled by `v(VDD_LOGIC)`, body-level `.options reltol=1e-4`, and
`vin_max_v` / `vin_min_v` carried ungraded (record columns, not `tb.json`
checks).

Reproduce (all four requests are multi-unit — 45 / 15 corners each — so they
go to the batch fleet; `capacity_wait_s=1800` is in the shared envelope):

```bash
python3 sim/gate-driver-core-drive-with-uvlo-postlayout/klt/gen_requests.py
cd sim/gate-driver-core-drive-with-uvlo-postlayout/klt
for r in nominal nominal-rc stretch stretch-rc; do
  klt sim --report-out envelopes/<date>-<sha>-klt-sim-$r.json --format json request-$r.json
done
```

Envelopes are committed append-only under `envelopes/`; a record citing one
still states the GDS sha256 and the DUT sha256 it ran (the latter from the
envelope's `environment.netlist_closure`) — the #558 citation rule.
