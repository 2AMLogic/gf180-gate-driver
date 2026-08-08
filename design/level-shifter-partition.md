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
