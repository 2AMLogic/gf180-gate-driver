# `klt sim` requests for T1 item 5 (issue #367)

The same end-to-end bench as `../testbench/` (logic-in -> level shifter -> output
stage -> 1 nF, `uvlo` instantiated), restated as `klt sim` requests so the
sign-off grader can read it. The harness records in `../records/` are untouched.

| File | What |
|---|---|
| `gen_requests.py` | Emits both requests (deterministic). Bounds are copied from `spec/gate-driver.md` §3; nothing is relaxed and DR-0016 / DR-0020 are not encoded. |
| `body.spice`, `design.ngspice` | Circuit body (includes `design/netlist/gate_driver_core.spice`) and the PDK `design.ngspice` it needs, copied so the batch worker can stage them. |
| `request-nominal.json` | 5 process x 3 temperature x 3 tied rail points (2.97/4.5, 3.3/5.0, 3.63/5.5 V) = 45 corners, target bounds. |
| `request-stretch.json` | Same 15 process/temperature points at 3.3/6.0 V, stretch bounds (>= 1 A, < 25 ns) for current and propagation delay. |
| `envelopes/` | Committed `klt sim` reports (append-only), cited by `verification/signoff/manifest.json` item 5. |

Reproduce (batch fleet; a 45-unit job outlives a Spot reclaim, so shard it):

```bash
python3 sim/gate-driver-core-drive-with-uvlo/klt/gen_requests.py
cd sim/gate-driver-core-drive-with-uvlo/klt
klt sim --hosts 5 --report-out envelopes/<date>-<sha>-klt-sim-nominal-rail.json --format json request-nominal.json
klt sim            --report-out envelopes/<date>-<sha>-klt-sim-stretch-rail.json --format json request-stretch.json
```

Result and caveats: `verification/signoff/README.md` § "Item 5".
