# `klt sim` requests for T1 item 5 (issue #367)

The same end-to-end bench as `../testbench/` (logic-in -> level shifter -> output
stage -> 1 nF, `uvlo` instantiated), restated as `klt sim` requests so the
sign-off grader can read it. The harness records in `../records/` are untouched.

| File | What |
|---|---|
| `gen_requests.py` | Emits all seven requests (deterministic). Bounds are copied from `spec/gate-driver.md` §3; the three corner-scoped ratified exceptions below are the only differences. |
| `body.spice`, `design.ngspice` | Circuit body (includes `design/netlist/gate_driver_core.spice`) and the PDK `design.ngspice` it needs, copied so the batch worker can stage them. |
| `request-nominal-main.json` | tt/ff/fs/sf x 3 temperatures x 3 tied rail points (2.97/4.5, 3.3/5.0, 3.63/5.5 V) = 36 corners, §3 target bounds. |
| `request-nominal-ss-warm-hot.json` | ss x {27, 125} C x 3 rail points = 6 corners, §3 target bounds. |
| `request-nominal-ss-cold-mid-high.json` | ss x -40 C x {3.3/5.0, 3.63/5.5 V} = 2 corners, §3 target bounds. |
| `request-nominal-ss-cold-low.json` | ss / -40 C / 2.97 V logic / 4.5 V drive = 1 corner. **Decision record 0020:** `ipeak_source_a` >= 0.45 A (§3: 0.5 A). Every other limit is the §3 bound. |
| `request-stretch-main.json` | tt/ff/fs x 3 temperatures at 3.3/6.0 V = 9 corners, stretch bounds (>= 1 A, < 25 ns). |
| `request-stretch-slow-cold-mid.json` | ss/sf x {-40, 27} C at 3.3/6.0 V = 4 corners, stretch bounds. |
| `request-stretch-hot-slow.json` | ss/sf x 125 C at 3.3/6.0 V = 2 corners. **Decision record 0016:** `ipeak_sink_a` >= 0.85 A (§3 stretch: 1 A). Every other limit is the stretch bound. |
| `envelopes/` | Committed `klt sim` reports (append-only), cited by `verification/signoff/manifest.json` item 5. The `20261027-*` pair is the superseded un-sharded run (#367); it is kept as evidence but no longer cited. |

`measurements[].limits` is min/max only and applies to every corner of a request,
so a corner-scoped ratified bound is expressed by giving those corners their own
request. The shards partition the original 45 + 15 corners exactly (no corner in
two requests, none dropped). DR-0020 bounds only `ipeak_source_a`; rise/fall/propagation
at `ss`/-40 C/low line and at `sf`/-40 C/low line keep the §3 bound and are
reported as failing (no ratified exception; issue #378).

Reproduce (single-unit shards stay local; multi-unit shards go to the batch fleet):

```bash
python3 sim/gate-driver-core-drive-with-uvlo/klt/gen_requests.py
cd sim/gate-driver-core-drive-with-uvlo/klt
for r in nominal-main nominal-ss-warm-hot nominal-ss-cold-mid-high nominal-ss-cold-low \
         stretch-main stretch-slow-cold-mid stretch-hot-slow; do
  klt sim --report-out envelopes/<date>-<sha>-klt-sim-$r.json --format json request-$r.json
done
```

Result and caveats: `verification/signoff/README.md` § "Item 5".

## `pex/` (issue #369)

The same requests restated for `klt pex` (T1 item 7): `dut.spice` wraps the DUT
fragment as `.subckt gate_driver_core`, `body.spice` instantiates it as `xdut`
and carries the single DUT `.include`, and `gen_pex_requests.py` reuses
`../gen_requests.py` (same corners, measurements, bounds) with `remote.hosts`
set because `klt pex` has no `--hosts` flag. The diagnostic
`uvlo_lockout_at_in_high` probe is omitted. Command and result:
`verification/signoff/README.md` § "Item 7".
