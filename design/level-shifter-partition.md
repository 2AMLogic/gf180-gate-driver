# `level_shifter` — DNWELL domain partition and cascode-bias derivation

- **Cell**: [`design/level_shifter.sch`](level_shifter.sch) /
  [`design/level_shifter.sym`](level_shifter.sym)
- **Spec constraint**: [`spec/gate-driver.md` §2.4](../spec/gate-driver.md)
  ("Both 3.3V and 5V/6V transistors are not allowed in the same DNWELL"),
  applied here per §4's cascode/clamped topology decision.
- **Scope**: schematic/floorplan partition only — no layout has been drawn
  for this cell (issue #7 is schematic capture + PVT verification; layout is
  a separate follow-on issue). This table is the constraint layout inherits,
  per the issue's explicit request, not a layout deliverable itself.

## Device-by-device domain table

| Reference | Device | Oxide | Domain | Bulk/body tie | DNWELL group |
|---|---|---|---|---|---|
| `XMNINV` | `nfet_03v3` | thin | 3.3 V logic | `gnd_logic` (native p-sub / logic pwell) | **none** — outside any DNWELL |
| `XMPINV` | `pfet_03v3` | thin | 3.3 V logic | `vdd_logic` (native nwell) | **none** — outside any DNWELL |
| `XMNPDA` | `nfet_03v3` | thin | 3.3 V logic | `gnd_logic` | **none** — outside any DNWELL |
| `XMNPDB` | `nfet_03v3` | thin | 3.3 V logic | `gnd_logic` | **none** — outside any DNWELL |
| `XMNCASA` | `nfet_06v0` | thick | 5 V/6 V drive | `gnd_drv` (isolated pwell) | `DNWELL_DRV` |
| `XMNCASB` | `nfet_06v0` | thick | 5 V/6 V drive | `gnd_drv` (isolated pwell) | `DNWELL_DRV` |
| `XMPLATA` | `pfet_06v0` | thick | 5 V/6 V drive | `vdd_drv` (nwell) | `DNWELL_DRV` |
| `XMPLATB` | `pfet_06v0` | thick | 5 V/6 V drive | `vdd_drv` (nwell) | `DNWELL_DRV` |
| `XMPBUF1` | `pfet_06v0` | thick | 5 V/6 V drive | `vdd_drv` (nwell) | `DNWELL_DRV` |
| `XMNBUF1` | `nfet_06v0` | thick | 5 V/6 V drive | `gnd_drv` (isolated pwell) | `DNWELL_DRV` |
| `XMPBUF2` | `pfet_06v0` | thick | 5 V/6 V drive | `vdd_drv` (nwell) | `DNWELL_DRV` |
| `XMNBUF2` | `nfet_06v0` | thick | 5 V/6 V drive | `gnd_drv` (isolated pwell) | `DNWELL_DRV` |
| `XCCOMP1`–`XCCOMP4` | `cap_mim_2f0_m4m5_noshield` ×4 in series (MIM, 2 fF/µm², M4-FuseTop-M5), each 5.0 µm × 5.0 µm | n/a — no silicon bulk/well terminal, isolated by inter-metal dielectric | 5 V/6 V drive (the stack's end terminals `ncb` and `out`/`IN_DRV`, and its three internal nodes `nccomp1`–`nccomp3`, are all `DNWELL_DRV`-group nodes) | n/a | co-located with `DNWELL_DRV` — a MIM cap has no diffusion/well terminal of its own to place inside or outside a DNWELL, so it adds no new isolation requirement beyond the domain boundary the 5 V/6 V group already forces |

**Result**: two groups, no group mixes 3.3 V and 5 V/6 V devices — DRM 7.2
satisfied by construction. The 3.3 V group (pre-driver inverter + both
thin-oxide pull-downs) sits entirely outside any DNWELL, matching §2.4's
second allowed option ("or keep the 3.3 V side entirely outside any
DNWELL"). The 5 V/6 V group (both cascodes, the cross-coupled latch, and the
two-stage output buffer) shares a single `DNWELL_DRV` region — they are
already the same electrical domain (`vdd_drv`/`gnd_drv`-referenced) with no
node inside that group ever expected to differ from another by more than one
rail's worth of headroom, so co-locating them in one DNWELL adds no new
isolation requirement beyond what the domain boundary itself already forces.

## Compensation capacitor (`XCCOMP1`–`XCCOMP4`) — this cell's first passive

The compensation capacitor (issue #155, [decision record
0007](../spec/decision-records/0007-indrv-feedforward-compensation-capacitor.md);
re-modeled by issue #192, [decision record
0014](../spec/decision-records/0014-xccomp-mim-density-and-series-stack.md))
is the first passive component in this design. It has no diffusion or well
terminal of its own — a MIM cap is a metal-metal stack sitting above the
active area, isolated from the substrate by inter-metal dielectric — so DRM
7.2's DNWELL-mixing rule, which governs diffusion/well devices, does not
apply to it directly. Every node it touches (`ncb`, `out`, and the stack's
internal `nccomp1`–`nccomp3`) already belongs to the `DNWELL_DRV` group, so
it introduces no new domain-crossing surface for layout to isolate.

**Four series devices, not one — and the metal pair is no longer free.**
Decision record 0014 replaces decision record 0007's single
`cap_mim_1f0_m4m5_noshield` at 3.0 µm × 3.0 µm with four series
`cap_mim_2f0_m4m5_noshield` devices at 5.0 µm × 5.0 µm, for two independent
reasons this document's earlier "metal pair deferred to layout" note did not
anticipate:

- **Density is a process option, not a drawing choice.** `gf180mcuD` is
  wired for the 2.0 fF/µm² MiM option (`.config/nodeinfo.json` option
  `MIM_2P0`; `libs.tech/klayout/lvs/run_lvs.py` binds `variant=D` to
  `mim_cap=2`; `libs.tech/magic/gf180mcuD.tech` and
  `libs.tech/netgen/gf180mcuD_setup.tcl` each define exactly one MIM device,
  `cap_mim_2f0_m4m5_noshield`). The PDK's LVS deck extracts all three
  densities from *identical* drawn layers, confirming the density is set by
  the mask/process option, not by anything layout can draw.
- **The metal pair follows the metal stack, and is therefore already
  fixed.** The earlier note here said all four M(n)-M(n+1) pairs were
  electrically interchangeable and the choice was a layout-time decision.
  That is true of the *model cards*, but not of the *process*: DRM §10.4
  defines exactly two mutually-exclusive MIM options — Option A (bottom
  plate on Metal2, 3-metal-layer processes) and Option B (bottom plate on
  Metal(n−1) of an n-metal stack) — and states they "can not be used in the
  same process." `gf180mcuD` is a 5-metal Option-B build, so its MIM sits on
  Metal4-FuseTop-Metal5 and nowhere else. `m4m5` in the device name is a
  process fact for this PDK variant, not a simulation convenience.

**Layout consequence carried forward.** DRM rule MIMTM.8a sets a 25 µm²
minimum MIM area (FuseTop), which each 5.0 µm × 5.0 µm device meets exactly
at the minimum. Four of them need four separate FuseTop plates with their
own bottom plates: MIMTM.3 requires 0.6 µm bottom-plate overlap of the top
plate on every side (a 6.2 µm × 6.2 µm Metal4 plate per device) and MIMTM.1
requires 1.2 µm bottom-plate-to-adjacent-metal spacing, so a single row of
four is roughly 28.4 µm × 6.2 µm ≈ 176 µm² of Metal4/Metal5 real estate.
That area is over the cell, not beside it — the DRM's own §10.4.2 guideline
is only that no *matching-sensitive* analog circuitry sit underneath, which
this switching level shifter is not — but it does mean Metal4 and Metal5 are
no longer freely available for routing above the shifter, and the three
internal nodes `nccomp1`–`nccomp3` are floating-by-design plate-to-plate
nets that layout must not accidentally strap or shield to anything.

## Guard-ring requirement

Per DRM 7.2, `DNWELL_DRV` must be directly surrounded by a PCOMP guard ring
tied to substrate potential (this design's board-level substrate/`GND_LOGIC`
reference — see decision record 0001, Decision 1, on the two ground pins
being one electrical node). The 3.3 V group, being outside any DNWELL, takes
the standard (non-DNWELL) guard-ring treatment for its own nwell/pwell taps
— no additional isolation ring beyond ordinary substrate contact spacing.

Layout consequence carried forward (not resolved by this record): the
`na`/`nb` and `nca`/`ncb` nets cross the domain boundary at the
`XMNCASA`/`XMNCASB` cascode devices' source/drain — those devices are the
one place in the cell where a single transistor's two diffusion terminals
sit electrically close to the boundary (source at the 3.3 V-referenced `na`
node, drain inside the `DNWELL_DRV` group). This is expected — clamping the
boundary is exactly the cascode's job (see below) — and is recorded here so
layout treats the cascode devices' placement, not just their DNWELL
membership, as boundary-adjacent.

## Cascode bias derivation

The cascode gates (`XMNCASA`/`XMNCASB`) are tied to `vdd_logic`, not to a
dedicated bias generator — a fixed-rail bias, chosen for simplicity (no bias
network, no extra current path, nothing that depends on the drive rail being
established before the logic rail is).

With the cascode gate held at `VDD_LOGIC` and its source at `na`/`nb`, the
device conducts (source-follower-like) only while
`v(na) < VDD_LOGIC - Vgs_sat(nfet_06v0)`; once `na` rises to
`VDD_LOGIC - Vgs_sat`, the cascode's own `Vgs` collapses toward threshold and
it stops pulling `na` any higher, regardless of how much further `nca` (and
therefore the drive-rail-referenced latch) continues toward `VDD_DRV`. This
is the clamp §4 requires: `na`/`nb` (the thin-oxide pull-down drains) never
follow the drive rail past roughly one `Vgs_sat` below `VDD_LOGIC`, no matter
how high `VDD_DRV` stretches (5 V nominal, 6 V stretch, per §3).

Simulated confirmation (nominal `tt_27c_vlogic3p30v-vdrv5p00v` point, see
this issue's oxide-safety record): `na_peak` = 2.53 V, `nb_peak` = 2.32 V —
both well below the 3.63 V thin-oxide DC ceiling and below `VDD_LOGIC`
(3.30 V) itself by roughly the expected `nfet_06v0` `Vgs_sat`, confirming the
clamp engages as designed and tracks `VDD_LOGIC` (not `VDD_DRV`) as intended.
The full corner sweep (this issue's simulation record) is the substantiating
evidence for every corner, not just this one point — see that record for
whether the clamp holds the §2.3 3.63 V ceiling for every thin-oxide node
(not just `na`/`nb`) across the full PVT matrix.
