# 0014: `XCCOMP` re-modeled onto four series 2 fF/µm² MIM devices — decision record 0007's device choice corrected against what `gf180mcuD` can actually build

- **Status**: Ratified
- **Date**: 2026-08-18
- **Decided by**: Builder agent, issue #192

- **Supersedes**: none. **Corrects the device choice and sizing of**
  [decision record
  0007](0007-indrv-feedforward-compensation-capacitor.md) — 0007's reason
  for adding a feedforward compensation capacitor, its sizing *criterion*
  (small enough not to spend decision record 0003's Exception 1 margin,
  large enough to compensate), and its narrowing of decision record 0006's
  Exception 3 all stand unchanged. What this record replaces is 0007's
  choice of a specific device that **cannot be fabricated on this PDK
  build**, and the two numeric figures that choice produced.

## Context

Decision record 0007 adopted `XCCOMP`, a feedforward compensation capacitor
from `x1.ncb` to `IN_DRV`, as a single `cap_mim_1f0_m4m5_noshield`
(1.0 fF/µm²) at 3.0 µm × 3.0 µm. Issue #192 reports that the `gf180mcuD`
PDK variant this repo targets is wired for the 2.0 fF/µm² MiM process
option, so that device may not be buildable here at all.

Two independent facts, both confirmed below, make the adopted device
unbuildable — and the second one was not raised by the issue at all.

### Fact 1: MiM density is a fixed process option on this build, not a device choice

The issue cited `.config/nodeinfo.json`'s free-text description. Its
acceptance criteria asked for a citation beyond that. Five, from the PDK's
own tooling and from the published design manual:

1. **The PDK's own LVS runner documents the binding.**
   `libs.tech/klayout/lvs/run_lvs.py` (and its `README.md`), shipped from
   the foundry verification library `gf180mcu_fd_pv`, enumerates the named
   process variants and their switch settings:
   `variant=D: Select metal_top=11K mim_option=B metal_level=5LM
   poly_res=1K, and mim_cap=2`. `mim_cap` **is** the density switch (it
   takes `1`, `1.5`, `2`); all four named variants A–D fix it at `2`. The
   DRC runner (`libs.tech/klayout/drc/run_drc.py`) agrees on the same
   variant table.
2. **Density is a mask option, not a drawable distinction.**
   `libs.tech/klayout/lvs/rule_decks/mimcap_extraction.lvs` extracts all
   three densities from *identical* drawn layers
   (`{'P1' => mimtm_virtual, 'P2' => fuse_cap}`) — only the `MIM_CAP`
   switch and the resulting device name differ. Nothing in layout can
   select 1.0 fF/µm²; the dielectric thickness is set at the wafer.
3. **Signoff tooling on this build knows exactly one MIM device.**
   `libs.tech/magic/gf180mcuD.tech` declares a single MIM extraction rule
   (`device csubcircuit cap_mim_2f0_m4m5_noshield *mimcap *m4 …`), and
   `libs.tech/netgen/gf180mcuD_setup.tcl` lists a single MIM device
   (`lappend devices cap_mim_2f0_m4m5_noshield`). A drawn
   `cap_mim_1f0_m4m5_noshield` has no extractable or LVS-comparable
   counterpart here — the same gap `2AMLogic/klayout-tools#1151` reports
   tool-side.
4. **Upstream `open_pdks` cannot build any other density.** In
   `gf180mcu/gf180mcu.json`, `MIM` is a *binary* define whose only density
   token is `MIM_2P0` (`#ifdef MIM … "MIM_2P0"`); there is no `MIM_1P0` or
   `MIM_1P5`. `gf180mcu/magic/gf180mcu.tech` only ever emits
   `cap_mim_2f0_*` devices, across all four metal-stack variants. All four
   installed variants (A/B/C/D) carry `"options": [… "MIM_2P0" …]`.
5. **The metal pair is not free either.** DRM §10.4.2 states Option A
   (bottom plate on Metal2) and Option B (bottom plate on Metal(n−1)) "can
   not be used in the same process". `gf180mcuD` is a 5-metal Option-B
   build, so its MiM sits on Metal4-FuseTop-Metal5 and nowhere else. This
   **contradicts** decision record 0007's "all four metal-pair variants
   this PDK offers share the same characterized capacitance-per-area model,
   so the pair is a simulation convenience, not an electrical choice" and
   `design/level-shifter-partition.md`'s matching "metal pair deferred to
   layout" note; both are corrected here.

The three densities exist as `.subckt`s in the *shared, variant-independent*
`libs.tech/ngspice/sm141064_mim.ngspice` (byte-identical across gf180mcuA/B/C/D),
which is why decision record 0007 was able to simulate a device this build
cannot make. **The simulation model library is not a device availability
list.**

### Fact 2: DRM rule MIMTM.8a makes every MIM on this process at least 54.5 fF

The issue's premise, and its suggested fix, both assume the correction is a
density re-scale. It is not, because of a rule neither the issue nor
decision record 0007 accounts for:

> **MIMTM.8a** — Minimum MIM cap area (defined by FuseTop area): 5\*5 µm²
> — gf180mcu DRM, `tables_clear/35_MIM2_88.csv`

This is a hard, DRC-coded rule, not a guideline
(`libs.tech/klayout/drc/rule_decks/mim_b.drc`:
`fusetop.with_area(nil, 25.um)`). `XCCOMP`'s drawn 3.0 µm × 3.0 µm = 9 µm²
violates it by ~2.8x **at either density**. The smallest legal MIM on this
process is 5.0 µm × 5.0 µm, and at 2.0 fF/µm² that is **54.52 fF typical**
(measured against the installed models: 49.07 / 54.52 / 59.97 fF at
`mimcap_ff`/`typical`/`ss`) — roughly four times what decision record
0007's own sizing sweep shows this node tolerates.

So there is no single-device answer at any density: the minimum buildable
MIM is far too large.

### The voltage-rating conflict decision record 0007 raised does not exist

Decision record 0007 rejected `cap_mim_2f0_m4m5_noshield` on the grounds
that it is "rated to 6 V" against `cap_mim_1f0_*`'s "20 V", and that
"`IN_DRV`'s swing directly across this capacitor's terminals is the full
~6 V stretch rail", giving zero margin. Both halves of that argument are
wrong, and neither had a testbench behind it.

- **There is no rating differential.** The PDK's own published
  device-model table — `google/gf180mcu-pdk`,
  `docs/analog/model_parameters/LV/tables_clear/08_MIM.csv` — carries one
  row per MiM density and rates **all three identically**: "Model for
  1.5fF/um2 MIM (\*)-usable for Volt <=6V across capacitor", and likewise
  for the 1.0 fF/µm² and 2.0 fF/µm² rows. (That file's `Model Name` column
  is a copy-paste artifact of `07_MOSCAP.csv` — its first three MOSCAP
  names are reproduced verbatim — so the `Description` column is the
  load-bearing content.) No source in the PDK ascribes 20 V to
  `cap_mim_1f0_*`; the ngspice model cards carry no voltage rating at all.
  Decision record 0007's 20 V figure is uncited and, as far as this
  investigation can determine, incorrect.
- **The exposure is not the rail.** `ncb` and `out` are two inversions
  apart in this cell (`ncb` → `nbuf1` → `out`), so they swing **in phase**;
  the capacitor sees only the transient skew between them, never the
  quiescent rail. Measured across the full 60-point grid, including every
  6 V stretch point (`sim/level-shifter-oxide-safety/records/20260818-060158-673fcf0.md`,
  new `vccomp_stack_max` measurement): worst case **5.73731 V**, already
  263 mV inside the 6 V rating with no series division at all.

The rejection in decision record 0007 is therefore void on its own terms.
This record does not adopt `cap_mim_2f0_*` *despite* a voltage-margin
problem; it records that the problem was never there.

## Decision

**`XCCOMP` is realized as four series `cap_mim_2f0_m4m5_noshield` devices,
each at the DRM-minimum 5.0 µm × 5.0 µm**, from `x1.ncb` through
`nccomp1`/`nccomp2`/`nccomp3` to `IN_DRV`. End-to-end capacitance
**12.27 / 13.63 / 14.99 fF** at `mimcap_ff`/`typical`/`ss`, against decision
record 0007's 11.56 / 12.84 / 14.13 fF — 6% larger typical, and the
smallest value any legal MIM realization on this process can reach.

`design/level_shifter.sch`, `design/netlist/level_shifter.spice` and
`design/netlist/gate_driver_core.spice` carry the four devices;
`design/level-shifter-partition.md`'s device table and its
"metal pair deferred to layout" note are corrected accordingly.

**Four is forced from below and best from above.** Below: `N ≥ 4` is
arithmetic — `N = d·A/C ≥ 2.0 × 25 / 15 = 3.3` for any usable `C`, given
MIMTM.8a's `A ≥ 25 µm²`. Above: deeper stacks were measured and are worse
on Exception 3, not better (table under "Alternatives considered"). Four is
simultaneously the shallowest legal stack, the smallest-area one (100 µm² of
FuseTop; total MIM area scales as `N²` for fixed `C`), and the
best-performing one.

### Re-verified evidence

Both directly-affected campaigns re-run full-grid (60 points each) against a
clean tree at commit `673fcf0`:

- **Exception 1 (decision record 0003) holds, unregressed** —
  `sim/level-shifter-oxide-safety/records/20260818-060158-673fcf0.md`.
  `inb`'s overshoot above `VDD_LOGIC` spans **20.34–35.33 mV** across the 15
  affected `vlogic3p63v` points. The apples-to-apples uncompensated control
  at the same solver tolerance
  (`sim/level-shifter-oxide-safety/records/20260817-202836-d7bda87.md`)
  spans 20.42–35.84 mV, so the stack *lowers* the worst point by 0.51 mV.
  An A/B run of decision record 0007's own (unbuildable) device at this
  tolerance gives **3.66533 V at the binding corner — identical to this
  record's 3.66533 to six significant figures**: the device change
  contributes 0.00 mV.
- **Exception 3 (decision record 0006, bound narrowed by 0007) holds,
  inside its ratified bound** —
  `sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`. Worst
  `indrv_max` = **6.00266 V (margin −2.66 mV)** at
  `ss_125c_vlogic3p30v-vdrv6p00v`, against 6.14833 V (−148.3 mV) for the
  uncompensated control at the same tolerance — a **~56x reduction** in the
  ceiling excess. Spec §5 bounds Exception 3 at **≤ 10 mV above the
  ceiling** (decision record 0007's own bound, deliberately sized to absorb
  exactly this kind of deck-fidelity movement); −2.66 mV is inside it, so
  the ratified bound is **not** relaxed — only the cited measured figure
  moves. `indrv_min` improves (−41.75 → −16.42 mV) and `n1_min_v`'s
  inherited −50 mV sanity-band misses drop from 47/60 to 16/60. Timing and
  drive currents are within ~2% of the control (spec §3 unregressed).

### Why the cited figures move, stated in full

Decision record 0007 printed 6.0003 V / −0.3 mV for Exception 3 and
3.66512 V for Exception 1's worst point. Neither is reproducible today, for
a reason that is **not** this change, and the two causes are separated by
direct A/B measurement rather than assumed:

| Exception 3, worst `indrv_max` | value |
|---|---|
| decision record 0007's device @ `reltol=1e-3` (record `20260817-201007-ce8027d`) | 6.00030 V |
| decision record 0007's device @ `reltol=1e-4` (A/B control run for this record) | 6.00150 V |
| this record's four series devices @ `reltol=1e-4` | 6.00266 V |

**+1.20 mV is the solver-tolerance tightening** that landed in issue #156 /
PR #165 (commit `a5d4759`) *after* decision record 0007's evidence was
recorded — that commit's own rationale is that the looser default "was a
measured lower bound on the excursion, not the excursion itself".
**+1.16 mV is this record's device change**, the unavoidable cost of a 6%
larger typical capacitance that MIMTM.8a leaves no way to avoid. Per
CLAUDE.md, both are reported rather than absorbed: `spec/gate-driver.md`
§5's Exception 3 bullet is updated to 6.00266 V / −2.66 mV.

For Exception 1 the same tolerance change accounts for the whole movement
(0.21 mV): at `reltol=1e-4` the *uncompensated* circuit already measures
3.66584 V, above decision record 0007's printed figure for a *compensated*
one. This record's design measures 3.66533 V. **Decision record 0003's band
is stated as "20–35 mV" and the current tolerance puts the uncompensated
worst point at 35.84 mV** — i.e. the band's upper figure is now stale by
~0.8 mV for reasons entirely predating and independent of this issue. That
is a real open question about a ratified record, but it is issue #156/#165's
consequence and not #192's to settle: this record does **not** widen
Exception 1's band, and the follow-up is filed separately.

## Alternatives considered

- **Keep `cap_mim_1f0_m4m5_noshield` (do nothing)** — rejected: not
  fabricable, not extractable and not LVS-comparable on `gf180mcuD` (five
  citations under "Fact 1"), and 9 µm² violates DRM MIMTM.8a regardless of
  density. Carrying it forward would ship a schematic whose committed
  capacitance can never be realized — the failure mode issue #192 exists to
  catch.
- **A single `cap_mim_2f0_m4m5_noshield` resized to preserve ~12.8 fF
  (≈2.3 µm × 2.3 µm)** — rejected: 5.3 µm² is well under MIMTM.8a's 25 µm²
  minimum. This is the fix the issue's "Suggested next step" proposes, and
  it is not drawable.
- **A single `cap_mim_2f0_m4m5_noshield` at the legal 5.0 µm × 5.0 µm
  minimum (54.52 fF)** — rejected on measured evidence: `inb`'s overshoot
  rises to **138.83 mV**, roughly 4x decision record 0003's ratified
  Exception 1 band. Exactly the regression decision record 0007's sizing
  criterion exists to prevent.
- **Two or three minimum-area devices in series (27.26 / 18.17 fF)** —
  rejected on measured evidence: `inb` overshoot 70.58 mV and 42.25 mV
  respectively, both outside Exception 1's band (uncompensated reference
  35.84 mV at the same tolerance).
- **Five, six or seven minimum-area devices in series (10.90 / 9.09 /
  7.79 fF)** — rejected: all hold Exception 1, but all are *worse* on
  Exception 3 than four, and cost 25–75% more area:

  | stack depth | C (typ) | worst `indrv_max` | `n1_min_v` misses | FuseTop area |
  |---|---|---|---|---|
  | 4 (chosen) | 13.63 fF | **6.00266 V** | 16/60 | 100 µm² |
  | 5 | 10.90 fF | 6.02205 V | 21/60 | 125 µm² |
  | 6 | 9.09 fF | 6.04351 V | 28/60 | 150 µm² |
  | 7 | 7.79 fF | 6.05860 V | 31/60 | 175 µm² |

  This also **corrects a secondary claim of decision record 0007**: that
  `IN_DRV` compensation "is already effectively saturated at 10–14 fF".
  Once the transient is resolved at `reltol=1e-4` it is not — the response
  is monotone across this whole range. That conclusion was an artifact of
  the pre-#165 solver tolerance.
- **Four devices larger than the minimum (4 × 5.25 µm → 14.96 fF; 4 ×
  5.5 µm → 16.36 fF)** — measured, and rejected. 5.25 µm is not better on
  Exception 3 (6.00279 V, marginally worse than the minimum-size stack) and
  costs 10% more area. 5.5 µm does improve Exception 3 (6.00129 V) but
  pushes `inb`'s overshoot band to 23.24–36.00 mV, above the uncompensated
  35.84 mV reference — it starts spending Exception 1 margin to buy
  Exception 3 margin, the precise trade decision record 0007 ratified
  against. The DRM-minimum geometry is measured-best, not merely
  convenient.
- **A MOSCAP (`cap_nmos_06v0` / `cap_pmos_06v0`), which has no minimum-area
  rule of this kind** — rejected on topology, not on size. Every gf180mcu
  MOSCAP is a three-terminal device with a bulk/well plate; used as a
  *series coupling* capacitor between two signal nodes, its bottom-plate
  junction capacitance shunts one of those nodes to a well, which is a
  functional change to the feedforward path rather than a like-for-like
  substitution. It would also give `XCCOMP` a diffusion/well terminal and
  hence a DNWELL placement constraint that
  `design/level-shifter-partition.md` currently, correctly, records it as
  not having. Its strong C(V) nonlinearity is a further cost.
- **A MOM / metal-fringe capacitor** — rejected: gf180mcu ships no MOM
  primitive with a characterized model or a `mimcap_ff`/`ss`-style corner
  section. Adopting one would mean simulating an ideal, process-invariant
  capacitor, which cannot satisfy CLAUDE.md's "PVT corners on every recorded
  result" for the one component this record exists to characterize. Left
  open as a real option if a future revision needs a sub-10 fF coupling
  capacitor, where series-MIM area becomes prohibitive.
- **Series-stack the devices to divide the voltage** (the issue's option 3,
  as a *voltage* remedy) — adopted as a *capacitance* remedy, for a
  different reason. The measured stress across the whole stack is 5.73731 V,
  already inside the 6 V rating undivided, so voltage division is a welcome
  by-product (1.43433 V per device, 4.18x margin) rather than the
  justification.

## Consequences

- `design/level_shifter.sch` gains three internal nets
  (`nccomp1`–`nccomp3`) that are **floating by design** — plate-to-plate
  nodes with no DC path except the MiM model's own leakage. In both static
  states the stack's two ends sit at the same potential, so the stack holds
  ~0 V DC and the 5.74 V peak is purely transient, divided capacitively by
  four matched devices (the measured split is exact to six significant
  figures at every one of the 60 points). Layout must not strap, shield or
  tie these nodes.
- **MIM area is now a real floor plan item.** Four 5.0 µm × 5.0 µm FuseTop
  plates with MIMTM.3's 0.6 µm bottom-plate overlap and MIMTM.1's 1.2 µm
  spacing occupy roughly 28.4 µm × 6.2 µm ≈ 176 µm² of Metal4/Metal5. That
  sits *over* the cell (DRM §10.4.2's only caveat is that no
  matching-sensitive analog circuitry sit underneath, which a switching
  level shifter is not), but Metal4 and Metal5 are no longer freely
  available for routing above the level shifter.
- **Issue #166 (draw `XCCOMP` into `gate_driver_core.gds`) is unblocked, and
  its scope changes.** It now draws four minimum-area
  `cap_mim_2f0_m4m5_noshield` devices — the one MIM device
  `gf180mcuD`'s magic/netgen/KLayout decks all recognize, so LVS and
  extraction have a counterpart for it — rather than one non-extractable
  `cap_mim_1f0_*`. The metal pair is no longer a layout choice (Option B,
  M4-FuseTop-M5, fixed by the process). #166 should be re-scoped, not
  simply unblocked, and this record does not close it.
- `spec/gate-driver.md` §5's Exception 3 bullet cites 6.00266 V / −2.66 mV
  and this record's evidence; Exception 1's re-confirmation pointer moves to
  this record's oxide-safety run. §2.3's 6.0 V and 3.63 V ceilings are
  unchanged, Exception 3's ≤ 10 mV bound is unchanged and still met, and no
  PDK duty-cycle TDDB allowance is invoked.
- **Decision record 0003's "20–35 mV" band for Exception 1 is now stale at
  the harness's current solver tolerance** — the *uncompensated* circuit
  measures 35.84 mV there. This record deliberately does not touch it
  (the cause is issue #156 / PR #165, not this change, and 0003 is a
  ratified record whose amendment deserves its own issue and its own
  evidence). Filed as follow-up.
- **A lesson for every future device selection in this repo.** Decision
  record 0007 picked a device that simulates cleanly, has a model card in
  the PDK's ngspice library, and cannot be built. Three checks would have
  caught it, and none of them is a simulation: does the *variant-specific*
  magic/netgen/KLayout deck list this device; does the DRM publish a
  minimum/maximum geometry for it; is the electrical rating cited from a
  published table rather than asserted. `sm141064*.ngspice` is shared
  byte-for-byte across all four gf180mcu variants and is therefore
  **not** evidence that a device exists on the one you build for.
- Two new append-only `sim/` records substantiate this change:
  `sim/level-shifter-oxide-safety/records/20260818-060158-673fcf0.md` and
  `sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`. No
  existing record is edited. The level-shifter testbench manifest gains two
  measurements (`vccomp_dev_max`, `vccomp_stack_max`) and one check
  (`vccomp_dev_max ≤ 6.0 V`), so the MiM voltage rating is now a verified
  claim rather than an assertion — the gap this record found in 0007.
