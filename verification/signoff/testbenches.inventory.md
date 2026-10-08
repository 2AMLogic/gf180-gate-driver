# Testbench inventory (T1 item 9)

Bound by `testbenches.generic.json` (T1 item 9). Audited 2026-10-08
(issue #288) against `origin/main` at `545b066`. `klt signoff` hashes **this file's
bytes**; it does not run simulations. `check_tier_report.py` checks the
per-file sha256 values below against the live tree and the test suite checks
that every path named here exists, so editing a listed `tb.json` or the
runner without refreshing this inventory fails.

## Scope of the attestation

The measurements claimed by `design/gate-driver-characterization.md` (spec
section 3: peak source/sink current, propagation delay, rise/fall into the
1 nF load; plus the level-shifter thin-oxide safety result it cites) are in
table A. Every other experiment directory under `sim/` is in table B so the
inventory is complete; for those, existence of the testbench and runner was
checked and the invocation is quoted from the runner's own documented usage.

## Common setup

- Harness: `sim/run_corners.py` (stdlib python3 >= 3.9) driving `ngspice`;
  documented in `sim/README.md` and `sim/harness/README.md`.
- PDK: `sim/pdk.json` (sha256
  `sha256:ac953614c421e8c3d3490a0a9cea0109113ee795f7c9bef7482de9a29a72e6cf`)
  commits only the **variant** (`gf180mcuD`). The PDK **revision** is not
  machine-pinned there; it is recorded per record, and every record cited
  below ran on open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (`sim/harness/README.md` documents `volare enable --pdk gf180mcu <hash>`
  as the install route). The audit host's resolved PDK reported that same
  revision under `python3 sim/run_corners.py --check-env`; `volare` itself
  was not run.
- Environment check: `python3 sim/run_corners.py --check-env`; export the
  resolved PDK to a shell with `source sim/env.sh`.
- The primary record states ngspice-46; the audit host has ngspice-42. No
  record was reproduced on ngspice-42; only the one point set named below was
  run.

## A. Testbenches behind the characterization report

| experiment | testbench manifest | cold-start invocation | claim |
|---|---|---|---|
| `sim/gate-driver-core-drive/` | `sim/gate-driver-core-drive/testbench/tb.json` `sha256:c390436cd0b75e4b53839cb9c36fdee7f359f831d07e01db902764550764065d` | `python3 sim/run_corners.py gate-driver-core-drive` | spec 3 end-to-end, schematic (cross-check) |
| `sim/gate-driver-core-drive-with-uvlo/` | `sim/gate-driver-core-drive-with-uvlo/testbench/tb.json` `sha256:62813d6ffd96c76580dc97bb3e79a0dc2eaa1bac64bd4b1cb01178e498897464` | `python3 sim/run_corners.py gate-driver-core-drive-with-uvlo` | spec 3 + UVLO, schematic |
| `sim/gate-driver-core-drive-postlayout/` | `sim/gate-driver-core-drive-postlayout/testbench/tb.json` `sha256:ac7bb04b4f2e3355c701575d732f5187319e9b0cc0c981573161ba5b6fed057c` | `python3 sim/run_corners.py gate-driver-core-drive-postlayout --dut layout/lvs/gate_driver_core.extracted.spice` | spec 3, post-layout (cross-check) |
| `sim/gate-driver-core-drive-with-uvlo-postlayout/` | `sim/gate-driver-core-drive-with-uvlo-postlayout/testbench/tb.json` `sha256:39da836a5e29368e705a4e94b34715db17bc0a68f8203d4e68b1dfa5e76dfb8b` | no-RC: `python3 sim/run_corners.py gate-driver-core-drive-with-uvlo-postlayout`; RC (the report's primary record): add `--dut layout/lvs/gate_driver_core.extracted-rc.spice` | spec 3, complete block, post-layout (primary) |
| `sim/output-stage-drive/` | `sim/output-stage-drive/testbench/tb.json` `sha256:6811aa2b0145ba6f52813a83c5f21208c367ac4954e69b852839c61beadf6f55` | `python3 sim/run_corners.py output-stage-drive` | spec 3, output stage alone (cross-check) |
| `sim/level-shifter-oxide-safety/` | `sim/level-shifter-oxide-safety/testbench/tb.json` `sha256:26122d87d71f8bf88cf0ba6e8357550c8e1d791ee63601055af14ff2dee60a12` | `python3 sim/run_corners.py level-shifter-oxide-safety` | spec 4, 2.3 |
| `sim/level-shifter-oxide-safety-postlayout/` | `sim/level-shifter-oxide-safety-postlayout/testbench/tb.json` `sha256:691c7e2cc618a13947c4f6495aae33d1146550c474b0eca6a2004660571d9d7d` | `python3 sim/run_corners.py level-shifter-oxide-safety-postlayout` (manifest DUT is the no-RC extraction; add `--dut layout/lvs/gate_driver_core.extracted-rc.spice` for RC) | spec 4, 2.3, post-layout |

Committed files each row depends on (all exist; checked):
`sim/gate-driver-core-drive/testbench/gate_driver_core_tb.spice`,
`sim/gate-driver-core-drive-with-uvlo/testbench/gate_driver_core_uvlo_tb.spice`,
`sim/gate-driver-core-drive-postlayout/testbench/gate_driver_core_tb.spice`,
`sim/gate-driver-core-drive-with-uvlo-postlayout/testbench/gate_driver_core_uvlo_tb.spice`,
`sim/output-stage-drive/testbench/output_stage_tb.spice`,
`sim/output-stage-drive/testbench/output_stage_dut.spice`,
`sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice`,
`sim/level-shifter-oxide-safety-postlayout/testbench/gate_driver_core_level_shifter_oxide_tb.spice`,
`design/netlist/gate_driver_core.spice`, `design/netlist/level_shifter.spice`,
`layout/lvs/gate_driver_core.extracted.spice`,
`layout/lvs/gate_driver_core.extracted-rc.spice`.

Audit findings for table A:

- Each of the five drive/timing manifests declares `trise_s`, `tfall_s`,
  `tpdlh_s`, `tpdhl_s`, `ipeak_source_a` and `ipeak_sink_a` in `measure`
  (checked by reading each `tb.json`). The two level-shifter manifests
  declare the oxide-safety excursions instead.
- `sim/output-stage-drive/testbench/output_stage_dut.spice` is a local copy of
  the DUT; it equals `design/netlist/output_stage.spice` on every non-comment
  line except the trailing `.end`.
- The report's primary record
  (`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`)
  ran against `layout/lvs/gate_driver_core.extracted-rc.spice`, whose live
  sha256 (`6f0c9b8e...db97e`) equals the one the record states. **Both that
  record and the no-RC cross-check record
  (`...records/20260826-063405-a7dcce1.md`, DUT hash equal to the live
  `layout/lvs/gate_driver_core.extracted.spice`) state they were taken
  against a dirty working tree and are "not citable as a clean-tree
  result".** This inventory attests that the testbenches and invocations
  exist and run, not that those records are clean-tree results.
- Executed in this audit (single corner, nothing recorded, `--no-write`):
  `python3 sim/run_corners.py gate-driver-core-drive-with-uvlo-postlayout
  --dut layout/lvs/gate_driver_core.extracted-rc.spice --corner-set tt
  --temps 27 --subset-reason "inventory cold-start check" -j 1` ran 4 of 4
  points to completion with status PASS (about 4 minutes). No other
  invocation in this inventory was executed; the rest were checked by
  `python3 sim/run_corners.py --list` (exit 0, every manifest loads), by the
  existence of the files above, and by the invocation table in
  `sim/README.md`.

## B. Other experiments (present, runner checked, not re-run)

| experiment | testbench / runner | invocation |
|---|---|---|
| `sim/smoke-mv-inverter/` | `sim/smoke-mv-inverter/testbench/tb.json` `sha256:3281867142387840cd9b10590319212fc7d95a5014916f133e687e8030808a56` | `python3 sim/run_corners.py smoke-mv-inverter` (harness self-test, not a design claim) |
| `sim/device-mv-fet/` | `sim/device-mv-fet/testbench/tb.json` `sha256:1e64b7ee190330a3b81d73eb2845be5cbb64ce4f7eba4c3d3181fc356bdb75ed`, `sim/device-mv-fet/run_device_mv_fet.py` | `sim/device-mv-fet/run_device_mv_fet.py` |
| `sim/low-side-power-switch/` | `sim/low-side-power-switch/testbench/tb.json` `sha256:2505bfdb288c795af2a9e7730c8ae6567ef82091c59c0255600a9e24e1b4cc07`, `sim/low-side-power-switch/run_low_side_power_switch.py` | `sim/low-side-power-switch/run_low_side_power_switch.py` |
| `sim/uvlo-trip-verification/` | `sim/uvlo-trip-verification/testbench/tb.json` `sha256:555693500f568a2144f2ea915abd6d59aca7275cdb4055d3ae853cb66fd6429d`, `sim/uvlo-trip-verification/run_uvlo_trip.py` | `sim/uvlo-trip-verification/run_uvlo_trip.py` |
| `sim/gate-driver-indrv-mismatch/` | `sim/gate-driver-indrv-mismatch/run_indrv_mismatch.py` (reuses the `gate-driver-core-drive` testbench) | `sim/gate-driver-indrv-mismatch/run_indrv_mismatch.py [--smoke]` |
| `sim/level-shifter-inb-mismatch/` | `sim/level-shifter-inb-mismatch/run_inb_mismatch.py` (reuses the `level-shifter-oxide-safety` testbench) | `sim/level-shifter-inb-mismatch/run_inb_mismatch.py [--smoke]` |
| `sim/low-side-power-switch-ronw-mismatch/` | `sim/low-side-power-switch-ronw-mismatch/run_ronw_mismatch.py` (reuses the `low-side-power-switch` testbench) | `sim/low-side-power-switch-ronw-mismatch/run_ronw_mismatch.py [--smoke]` |
| `sim/output-stage-taper-mismatch/` | `sim/output-stage-taper-mismatch/run_output_stage_mismatch.py` (reuses the `output-stage-drive` testbench) | `sim/output-stage-taper-mismatch/run_output_stage_mismatch.py [--smoke]` |

Dedicated runners take the PDK from the environment
(`PDK_ROOT=... PDK=gf180mcuD`, or `source sim/env.sh`) per their own module
docstrings. No runner in this table was executed in this audit.

`sim/README.md`'s "Facets in this repo" table lists eleven facets and omits
`gate-driver-core-drive-with-uvlo`, `uvlo-trip-verification`,
`level-shifter-inb-mismatch` and `output-stage-taper-mismatch`, which exist on
disk and are listed above.

The harness entry point `sim/run_corners.py` (sha256
`sha256:9f9b8199b5b20e974c715cbab0f4736394017809ba58604bf35ae683e41f5140`).
