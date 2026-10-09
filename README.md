# gf180-gate-driver

A high-voltage gate driver on the
[gf180mcu](https://github.com/google/gf180mcu-pdk) open PDK, designed by AI
agents driving [klayout-tools](https://github.com/2AMLogic/klayout-tools) and
the open-source xschem + ngspice analog flow.

**Status: spec ratified; schematic captured and PVT-simulated; layout
DRC-clean and LVS-match within a stated deck scope; post-layout PVT records
committed. Not tapeout-ready, not tier T1.** Ratified targets are not all met
(two bounded, documented exceptions; one open UVLO finding), and silicon has
not been measured. See [Current status](#current-status) and [Target
specification](#target-specification) below.

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation here is produced by AI agents working from a ratified
spec and an append-only evidence trail — not human-authored work that agents
merely assisted with. Verification is the product: every claim traces to a
recorded result under PVT corners. Where the agents hit friction with the
open-source tooling — most often
[klayout-tools](https://github.com/2AMLogic/klayout-tools) — that friction is
filed as a public issue against the tool itself, so the fix benefits everyone
using gf180mcu, not just this repo.

## Why this block

gf180mcu is a 3.3 V / 5 V / 6 V process, and every sibling canary uses only
the 3.3 V devices. This block is the first to work in the medium-voltage
flavors, which means the tools meet a set of device models, rules, and
extraction behavior they have not yet been exercised against.

A gate driver was chosen over a CAN transceiver for that job deliberately.
ISO 11898-2 demands roughly ±12 V bus common-mode range and fault tolerance
well beyond 6 V, so a CAN block risks dead-ending on device limits before it
produces much useful work. A gate driver exercises the same device flavors
without that risk, belongs to a real mature-node category (motor and power
control), and carries no standards-body entanglement.

## Target specification

Authoritative source: [`spec/gate-driver.md`](spec/gate-driver.md) section 3,
ratified 2026-08-05 (device flavors with PDK electrical specs cited,
low-side-only configuration, drive strength and reference load,
level-shifter topology, and protection scope, each recorded as a decision
with alternatives considered). The table below is a copy of its section 3;
if they ever differ, the spec wins. **These are design targets, not measured
results** -- measured performance, with the ratified exceptions, is in
[`design/gate-driver-characterization.md`](design/gate-driver-characterization.md).

| Parameter | Target | Stretch |
|---|---|---|
| Drive rail | 5 V nominal (+10% overshoot per [DRM 14.1.2](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html)) | 6 V |
| Logic input | 3.3 V | -- |
| Reference load | 1 nF (gate-capacitance stand-in for a mid-size discrete power MOSFET/IGBT) | -- |
| Peak source/sink current | >= 0.5 A | 1 A |
| Propagation delay | < 50 ns | < 25 ns |
| Rise/fall into reference load | < 50 ns (10-90%) | -- |
| Signoff | DRC + LVS clean | -- |

Known, ratified exceptions to that table (not relaxations of it; the targets
stay in force and the affected corners keep reporting FAIL):
[decision record 0016](spec/decision-records/0016-output-stage-stretch-sink-current-shortfall.md)
(6 V stretch-rail peak sink current, bounded >= 0.85 A at two hot/slow
corners) and
[decision record 0020](spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md)
(nominal-rail peak source current at one UVLO-locked corner, bounded
>= 0.45 A).

## Current status

Maturity ladder: spec ratified, schematic simulated across PVT, layout
DRC/LVS-clean, post-layout re-verification, shuttle seat, measured silicon.
**Current position: past post-layout re-verification of facet (a); no shuttle
seat; no measured silicon.** What is committed, and what it does not show:

- **Schematic** (`design/`): level shifter, output stage, UVLO and the
  assembled `gate_driver_core` are captured and netlisted.
- **Simulation** (`sim/`): append-only PVT-grid records for the schematic and
  for the extracted post-layout block (no-RC and RC), plus device
  characterization and Monte Carlo mismatch campaigns. The block-level
  roll-up against spec section 3 is
  [`design/gate-driver-characterization.md`](design/gate-driver-characterization.md).
- **Layout** (`layout/`): `gate_driver_core.gds`, `status: clean` DRC (0
  violations) and `status: match` LVS (2044/2044 devices) -- both **within a
  stated deck scope**; the DRC deck does not cover every DRM chapter, so
  neither is a tapeout signoff. See [`layout/README.md`](layout/README.md).
  (That file's "Post-layout simulation" status row predates the committed
  complete-block post-layout records and is stale; the `sim/` records are
  the evidence.)
- **Open items**: UVLO trip points are wider than the originally budgeted
  band and `ss_-40c` stays locked out above the -10 % low-line floor (decision
  records 0018, 0019; an open finding, not narrowed to pass); the two bounded
  exceptions above; PDK model coverage limits (decision record 0017).
- **Signoff** (`verification/signoff/`): the mechanically graded gap to tier
  T1 is committed in `tier-report.json`; several items are still `unmet`
  (no `klt`-native sim/yield/pex envelopes for items 5-7), so the block is
  **not tier T1**. See [`verification/signoff/README.md`](verification/signoff/README.md)
  for the current count and what each `met` does and does not claim.

## Reproducing the results

All commands run from the repository root. Only some of them *generate new
evidence*; the rest *validate or read what is already committed*.

### Prerequisites

`python3` >= 3.9 (the harness is stdlib-only), `ngspice`, a gf180mcu PDK
(`gf180mcuD` variant, installed with `volare`), `xschem` for netlisting, and
`klt` ([klayout-tools](https://github.com/2AMLogic/klayout-tools)) plus
KLayout for layout generation, DRC, LVS, extraction and ERC. Grading-only
signoff needs just `klt` (no KLayout, no PDK); see
[`verification/signoff/README.md`](verification/signoff/README.md) for the
exact pin. Details: [`sim/harness/README.md`](sim/harness/README.md).

### Validate committed evidence (no new evidence generated)

```bash
python3 sim/run_corners.py --check-env   # is ngspice + the PDK present?
python3 sim/run_corners.py --list        # discoverable experiments, corners, rails
python3 sim/check_records.py             # lint every evidence record's format
npm run lint                             # shellcheck + syntax + evidence-record checks (as CI)
npm run signoff:check                    # signoff manifest/tier-report freshness (needs the pinned klt)
```

### Generate new evidence

Each run mints a new append-only record; nothing is overwritten. A full grid
is a large job -- run it deliberately, not as a casual check.

1. **Schematic netlisting** (xschem): `source sim/env.sh`, then the
   `xschem ... -n` recipe in [`design/README.md`](design/README.md).
2. **Schematic PVT simulation** (`sim/`): e.g.
   `python3 sim/run_corners.py smoke-mv-inverter` (harness self-test) or
   `python3 sim/run_corners.py gate-driver-core-drive` (end-to-end block).
   Each record's Environment section names the PDK path and `open_pdks`
   hash, `ngspice` version, harness version and git commit it ran against.
3. **Layout generation**: `python3 layout/gen_gate_driver_core.py`, then
   `python3 layout/check_gate_driver_core.py` (see
   [`layout/README.md`](layout/README.md)). **Known limitation:** the layout
   README says regeneration is byte-identical; a 2026-10-08 audit with
   `klt` 0.6.0 produced different bytes, and the committed GDS records an
   older `klt` on a dirty tree (details in
   [`verification/signoff/README.md`](verification/signoff/README.md)).
4. **DRC / LVS / extraction / ERC** (append-only reports under
   `layout/*/reports/`): `python3 layout/drc/run_drc.py layout/gate_driver_core.gds`,
   `python3 layout/lvs/run_lvs.py layout/gate_driver_core.gds`,
   `python3 layout/lvs/run_pex_extract.py layout/gate_driver_core.gds`,
   `python3 layout/erc/run_erc.py layout/gate_driver_core.gds`. Reproduce the
   verdicts with the `klt` pin documented in `layout/README.md`; a different
   deck build can change them.
5. **Post-layout simulation**: the same runner against the extracted DUT,
   no-RC or RC, e.g. `python3 sim/run_corners.py gate-driver-core-drive-with-uvlo-postlayout --dut layout/lvs/gate_driver_core.extracted-rc.spice`
   (omit `--dut` for the no-RC DUT; the per-facet invocation is in the
   index below).
6. **Dedicated characterization and Monte Carlo mismatch campaigns**: these
   use their own scripts, not `run_corners.py` alone (which only runs a
   small representative subset for discovery, or nothing, for the mismatch
   campaigns): `sim/device-mv-fet`, `sim/low-side-power-switch`,
   `sim/uvlo-trip-verification/run_uvlo_trip.py`, and the `*-mismatch`
   campaigns. The per-facet cold-start index is the **"Facets in this repo"**
   table in [`sim/README.md`](sim/README.md); the runner, testbench and
   PVT-grid details are in [`sim/harness/README.md`](sim/harness/README.md).
   That table currently lists eleven facets and **omits**
   `gate-driver-core-drive-with-uvlo`, `uvlo-trip-verification`,
   `level-shifter-inb-mismatch` and `output-stage-taper-mismatch`; the
   complete directory-by-directory list, with each testbench hash and
   invocation, is
   [`verification/signoff/testbenches.inventory.md`](verification/signoff/testbenches.inventory.md).

### Reproducibility limits

Records are pinned per record (PDK `open_pdks` revision, `ngspice` version,
harness version, git commit), not machine-pinned at the repo level:
`sim/pdk.json` pins only the PDK variant. Cited post-layout records state
they were taken on a dirty working tree, record `ngspice`-46 where this
README's audit host has `ngspice`-42, and simulator-version comparability is
governed by the decision record in `sim/README.md`. The grading-only signoff
check proves the attested bytes did not change; it does not re-run any
simulation or regenerate any layout.

## Two facets, one shared device base

This repo scopes **two** distinct power-driver use cases on the same
gf180mcu medium-voltage devices, per
[decision record 0008](spec/decision-records/0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md):

- **(a) High-voltage gate driver** (the block above) — an external-FET
  pattern: 3.3 V logic in, level-shifted to a 5–6 V drive rail that sources
  and sinks gate charge into an off-die power switch. This is the ratified
  spec (`spec/gate-driver.md`).
- **(b) Low-side on-die power-NMOS facet** (new) — direct low-side drive of
  a small load (motor/solenoid/LED) straight from a single Li-ion cell,
  where the switch is an **on-die** thick-oxide `nfet_06v0`, `Vgs` is the
  cell's own 3.6–5 V range, and there is no HV rail and no level shifter.
  This facet is **in scope in this repo, not a sibling one** — the device
  characterization it needs (`Ron`, `Vt`, `Ioff`, thermal behavior of the
  same `nfet_06v0`/`pfet_06v0` devices) is already being produced here for
  facet (a)'s output stage. This facet now has its own ratified spec
  (`spec/low-side-power-switch.md`, decision records 0010 and 0011):
  cell-referenced `Ron·W` measured across the full PVT grid, switch sizing,
  the EM/current-density budget at 1 A per channel, per-channel OCP and
  thermal-sense reference structures, and flyback handling. Decision record
  0008's `Ron·W` baseline was a stopgap measured at the wrong gate drive and
  has been replaced as the design baseline by that document's §2.1.
  Everything from the pad outwards — multi-channel bond wires, ground return
  and substrate noise — is decision record 0009. The remaining piece, a
  shared-shuttle test-structure plan, is also now ratified: [decision record
  0012](spec/decision-records/0012-low-side-power-switch-shuttle-test-structure-plan.md)
  sizes a single reduced-scale reference channel and all three flyback
  variants for a wafer.space GF180MCU quarter slot (issue #180). Schematic
  capture, layout, and DRC/LVS closure for those structures are follow-on
  work, not yet started.

  The headline result so far: **a 1 A on-die low-side channel in this
  process is area-dominated** — ~45.7 mm of `nfet_06v0` gate width to hold
  0.10 Ω at end of discharge and 125 °C, with the supply bus itself eating
  26–30 mΩ of that same budget.

## Chipalooza

Facet (a) (the ratified high-voltage gate driver above) is proposed for Open
Circuit Design's Chipalooza Challenge #5 (GF180MCU / Wafer.Space). See
[`docs/chipalooza/challenge-5-proposal.md`](docs/chipalooza/challenge-5-proposal.md)
for the submission-ready proposal: type of block, I/O list mapped to the
Challenge's pad budget, functional description, a target-specification table
with every row cited to a dated `sim/` record, a bench test plan for the
packaged part, and this design's currently-open findings stated plainly, not
relaxed to make a row pass.

## Repo layout

```
spec/          ratified spec + decision records
design/        schematics / netlists (xschem)
sim/           testbenches + PVT corner results (ngspice)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
