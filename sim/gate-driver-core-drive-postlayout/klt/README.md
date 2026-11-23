# `klt sim` requests for gate-driver-core-drive-postlayout (issue #560)

The same end-to-end bench as `../testbench/` (logic-in (IN) -> level shifter
-> output stage -> 1 nF, against the extracted netlist of
layout/gate_driver_core.gds), restated as `klt sim` requests so the 60-point
matrix can run on the Spot batch fleet instead of a dispatch worker
(#558's drive deliverable; #485 reruns both drive facets through this route).
The harness records in `../records/` are untouched. Conventions shared with
the schematic item-5 route are documented once in
[`sim/README.md`](../../README.md#post-layout-drive-facets-on-the-batch-fleet-issue-560).

| File | What |
|---|---|
| `gen_requests.py` | Emits the four requests (deterministic). Every bound is copied from `../testbench/tb.json`'s `checks` (20 checks; four with a `stretch` override); the process axis and the `engine`/`models`/`batch`/`options` envelope come from [`sim/harness/klt_request.py`](../../harness/klt_request.py), shared with the other generators (issue #441). |
| `body.spice`, `body-rc.spice` | Circuit body per DUT: identical stimulus, 1 nF reference load, `vimeas` ammeter polarity and `reltol=1e-4` as the harness fragment; they differ only in which extracted DUT they `.include` at deck level — `layout/lvs/gate_driver_core.extracted.spice` (no-RC, `--combine`) and `.extracted-rc.spice` (`--parasitics`). Deck-level inclusion (no `.subckt` re-wrap) keeps the flat extracted probe names (`v(x2_n1)`..`v(x2_n5)`) addressable, exactly as the harness deck `.include`s the DUT ahead of the testbench fragment; each run's `environment.netlist_closure` pins the DUT sha256 it actually used. |
| `design.ngspice` | The PDK global-switch include the corner `.lib` sections need, copied so the batch worker can stage it (same copy as `../../gate-driver-core-drive-with-uvlo/klt/design.ngspice`). |
| `request-nominal.json` / `request-nominal-rc.json` | tt/ff/ss/fs/sf x {-40, 27, 125} C x 3 tied rail points (2.97/4.5, 3.3/5.0, 3.63/5.5 V) = 45 corners, nominal bounds — no-RC and RC DUT respectively. |
| `request-stretch.json` / `request-stretch-rc.json` | tt/ff/ss/fs/sf x {-40, 27, 125} C at 3.3/6.0 V = 15 corners, stretch bounds. |

`measurements[].limits` is min/max only and applies to every corner of a
request, so the tier split **is** the sharding: the 6 V rows — the only
stretch points of the grid (`sim/README.md` "Two-tier checks") — are their own
request, and the union of the two is the harness grid exactly, each point
once. No corner-scoped exception is encoded: this facet's `tb.json` carries
none, so unlike the schematic item-5 shards
(`../../gate-driver-core-drive-with-uvlo/klt/`) the stretch sink bound is 1 A
even at ss/sf 125 C and the nominal source bound is 0.5 A even at
ss / -40 C / low line — the same un-sharded policy as the PEX requests
(signoff item 7). `sim/test_gen_requests.py` pins both the committed bytes
and the manifest equality.

Method differences from the harness bench, in the way signoff Item 5 records
them for the schematic facet (`verification/signoff/README.md` § "Item 5"):

- crossings are taken on rail-normalised monitors (`vin_n`, `vout_n`) with
  literal 0.1/0.5/0.9 thresholds, not on the harness's measured-swing vectors
  — identical numbers wherever OUT actually switches;
- the IN pulse is built from a unit pulse scaled by `v(VDD_LOGIC)`
  (`supply_v` alters DC sources only);
- `reltol=1e-4` is a body-level `.options` card (the batch runner drops
  `options.ngspice_options`);
- `vin_max_v` / `vin_min_v` are carried ungraded (record columns of the
  harness facet, not `tb.json` checks).

Reproduce (all four requests are multi-unit — 45 / 15 corners each — so they
go to the batch fleet; `capacity_wait_s=1800` is in the shared envelope):

```bash
python3 sim/gate-driver-core-drive-postlayout/klt/gen_requests.py
cd sim/gate-driver-core-drive-postlayout/klt
for r in nominal nominal-rc stretch stretch-rc; do
  klt sim --report-out envelopes/<date>-<sha>-klt-sim-$r.json --format json request-$r.json
done
```

Envelopes are committed append-only under `envelopes/`; a record citing one
still states the GDS sha256 and the DUT sha256 it ran (the latter from the
envelope's `environment.netlist_closure`) — the #558 citation rule.
