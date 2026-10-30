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

## `pex/` (issue #369)

The same requests restated for `klt pex` (T1 item 7): `dut.spice` wraps the DUT
fragment as `.subckt gate_driver_core`, `body.spice` instantiates it as `xdut`
and carries the single DUT `.include`, and `gen_pex_requests.py` reuses
`../gen_requests.py` (same corners, measurements, bounds) with `remote.hosts`
set because `klt pex` has no `--hosts` flag. The diagnostic
`uvlo_lockout_at_in_high` probe is omitted. Command and result:
`verification/signoff/README.md` § "Item 7".
