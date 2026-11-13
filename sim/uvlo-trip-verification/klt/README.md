# `klt sim` requests for the `uvlo` and `drive_rail` rows of T1 item 5 (issue #377)

The standalone UVLO cell's ratified trip-voltage and response-time rows,
restated from `../run_uvlo_trip.py` as `klt sim` requests so the sign-off
grader can read them, plus the applied drive rail. The harness record in
`../records/` is untouched; these are fresh envelopes with provenance.

| File | What |
|---|---|
| `gen_requests.py` | Emits the four requests (deterministic). Bounds are the ones `run_uvlo_trip.py` scores (`FALLING_RANGE`, `RISING_RANGE`, `RESPONSE_MAX_S`, from decision record 0001 Decisions 4-5) and `spec/gate-driver.md` §3 for the rail; nothing is relaxed and decision record 0018's false-trip finding is not encoded as an exception. The process axis and the `engine`/`models`/`batch`/`options` envelope come from [`sim/harness/klt_request.py`](../../harness/klt_request.py), shared with the item-5 core-drive generator (issue #441). |
| `body-trip.spice`, `body-response.spice`, `body-rail.spice`, `design.ngspice` | Circuit bodies (the first two `.include` `design/netlist/uvlo.spice`) and the PDK `design.ngspice` they need. |
| `request-trip.json` | 15 process x temperature points; 0 -> 6 V -> 0 V `VDD_DRV` triangle. Graded `falling_trip_v` 3.3-3.9 V and `rising_trip_v` 3.6-4.2 V (row `uvlo`); `hysteresis_v` is reported **ungraded** (decision record 0001 gives it a typical value only, 300 mV, no worst-case range). |
| `request-response.json` | Same 15 points; 6.0 -> 1.8 V step with a 1 ns edge. Graded `response_s` < 500 ns (row `uvlo`), timed from `VDD_DRV` crossing 3.6 V to `OUT` reaching 0.5 V. The harness times from each corner's own measured trip; over a 1 ns edge the two differ by about 1 ns against the 500 ns bound. |
| `request-rail-nominal.json`, `request-rail-stretch.json` | `op` assertion of the applied rail at the DUT pin (row `drive_rail`): 4.5-5.5 V over the 45-point tied matrix and 6.0 V at the 15 stretch points. |
| `envelopes/` | Committed `klt sim` reports (append-only), cited by `verification/signoff/manifest.json` item 5. |
| `.klt/sim/batch-receipt.json` | klt's own working state, committed with the evidence in `d72424f`. **Kept deliberately**: it is the only committed copy of the as-submitted `request_sha256` (`5af1515f...`) for job `klt-sim-8453c410117b`, the job behind `envelopes/20261028-d7a2b69-klt-sim-uvlo-rail-stretch.json`; that value is in no other tracked file. `.klt/` is gitignored, so this is the only one: any further `.klt/` file is tool scratch, not evidence. |

`drive_rail` is a condition of §3, not a measured bound, and `klt signoff`'s row
schema has only `{id}` and `{id, gap}`; so it is graded as a limited
measurement. The rail is an ideal source, so this **asserts the condition the
other envelopes ran under** (a corner whose applied rail left the band would
fail); it does not measure the design.

[`sim/test_gen_requests.py`](../../test_gen_requests.py) re-runs `gen_requests.py`
in a temp mirror of `sim/` and fails if it stops reproducing the four committed
request files byte-for-byte, or if the bounds and `.meas` thresholds they carry
stop matching `../run_uvlo_trip.py`'s own `FALLING_RANGE` / `RISING_RANGE` /
`RESPONSE_MAX_S` (issue #441). These requests are inputs of cited, append-only
sign-off evidence, so a generator that silently stops reproducing them must fail
in CI rather than be committed as if nothing moved.

Reproduce (batch fleet; a Spot reclaim can interrupt a job, so shard it):

```bash
python3 sim/uvlo-trip-verification/klt/gen_requests.py
cd sim/uvlo-trip-verification/klt
for n in trip response rail-nominal rail-stretch; do   # one at a time: klt locks its outdir
  klt sim --backend batch --hosts 3 --report-out envelopes/<date>-<sha>-klt-sim-uvlo-$n.json --format json request-$n.json
done
```

Result and caveats: `verification/signoff/README.md` § "Item 5".
