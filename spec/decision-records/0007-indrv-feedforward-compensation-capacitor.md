# 0007: `IN_DRV` feedforward compensation capacitor — decision record 0006's Exception 3 bound narrowed

- **Status**: Ratified
- **Date**: 2026-08-17
- **Decided by**: Builder agent, issue #155

- **Supersedes**: none. **Narrows the bound of** [decision record
  0006](0006-indrv-inter-cell-gate-ceiling-exception.md)'s Exception 3 —
  does not reopen or contradict its existence, its zero-margin argument, or
  any other decision record. Per decision record 0006's own "Consequences":
  "If it lands, it supersedes this record's *bound* — not this record's
  existence, since the zero-margin argument above is unchanged by it." This
  record is that follow-up.

## Context

Decision record 0006 ratifies `spec/gate-driver.md` §5's Exception 3: the
inter-cell node `IN_DRV` transiently exceeds §2.3's 6.0 V thick-oxide gate
ceiling at all 15 of the 6 V stretch-rail PVT points, worst case 6.11823 V
(margin −118.2 mV) at `ss_125c_vlogic3p30v-vdrv6p00v`. In the course of
that investigation, decision record 0006 characterized a mitigation that
works — a feedforward compensation capacitor from `IN_DRV` to
`x1.ncb` — but explicitly deferred adopting it, filing the follow-up as
issue #155 (this record).

This record adopts that mitigation, `XCCOMP`, into
`design/level_shifter.sch` and re-verifies both directly-affected
campaigns (`sim/gate-driver-core-drive/`, `sim/level-shifter-oxide-safety/`)
in full.

## Sizing: why this record does not use decision record 0006's characterized 50 fF value

Decision record 0006's exploratory sweep found the compensation effect
flat from 10 fF to 100 fF and picked 50 fF as its headline number, with a
note that "over-compensation is benign." **That sweep only measured the
capacitor's effect on `IN_DRV` and on end-to-end delay/current — it did
not check the capacitor's effect on the thin-oxide `na`/`nb` nodes**
decision record 0002's ratified safety claim depends on, because `ncb` is
the drain of the cascode device `XMNCASB` (`design/level_shifter.sch`),
and `nb` is that same device's source.

Re-measuring during this issue's implementation surfaced exactly that
coupling. Sweeping the capacitor's `W`=`L` geometry (all
`cap_mim_1f0_m4m5_noshield`, `sim/level-shifter-oxide-safety` testbench,
`tt_27c_vlogic3p63v-vdrv5p50v` — the corner decision record 0003's
Exception 1 already binds at):

| `W`=`L` | measured capacitance (tt) | `vgate_thinox_max` | vs. baseline (no cap, 3.65733 V) |
|---|---|---|---|
| 2.0 um | 6.59 fF | 3.65733 V | +0.00 mV |
| 2.5 um | 9.47 fF | 3.65733 V | +0.00 mV |
| 3.0 um | 12.84 fF | 3.65733 V | +0.00 mV |
| 3.65 um | 16.71 fF | 3.66368 V | +6.4 mV |
| 4.0 um | 21.07 fF | 3.67465 V | +17.3 mV |
| 4.5 um | 25.93 fF | 3.69042 V | +33.1 mV |
| 5.5 um | 37.12 fF | 3.72174 V | +64.4 mV |

Exception 1 (decision record 0003) is ratified at a **20–35 mV** overshoot
band; a capacitor sized to decision record 0006's 50 fF headline value
(and even the 37.12 fF point measured above) pushes the same node's
overshoot to roughly double that ratified band — a real regression this
record's job is to catch, not carry forward silently. Below ~15 fF the
coupling is unmeasurable (identical to baseline to 5–6 significant
figures); the effect turns on sharply above that, not gradually — this is
consistent with the mechanism being `ncb`'s *own* collapse waveform
shifting once a large-enough capacitor loads it, rather than the small
linear feedforward decision record 0006's `IN_DRV`-side characterization
assumed.

**Decision: size for corner margin against both metrics, not for
`IN_DRV` alone.** `IN_DRV` compensation is already effectively saturated
at 10–14 fF (indistinguishable from the 50 fF result to three significant
figures in the full-grid re-run below), so there is no compensation
benefit to sizing larger, and every additional femtofarad above ~15 fF
only spends margin against Exception 1 for no further gain on Exception 3.
This record therefore sizes `XCCOMP` at the **small end** of decision
record 0006's characterized effective range, not its middle:
`cap_mim_1f0_m4m5_noshield` (1 fF/um², rated to 20 V — ample headroom over
the ~6 V stretch-rail swing directly across it — vs. `cap_mim_2f0_*`'s
6 V rating; all four metal-pair variants this PDK offers share the same
characterized capacitance-per-area model, confirmed directly against
`sm141064.ngspice`, so the pair is a simulation convenience, not an
electrical choice — see `design/level-shifter-partition.md`) at
**3.0 um x 3.0 um**, measured **11.56 fF (ff) / 12.84 fF (tt) / 14.13 fF
(ss)** — the PVT harness's own `mimcap_ff`/`mimcap_typical`/`mimcap_ss`
corner sections already vary this ±10% around nominal, so the full-grid
re-runs below carry that process-corner margin on the capacitor itself,
not just on the surrounding MOS devices. This sits comfortably above the
~10 fF point where `IN_DRV` compensation saturates (a ~40% margin at the
worst-case low corner, `ff` at 11.56 fF) and comfortably below the ~15 fF
point where `na`/`nb` coupling becomes measurable (even the worst-case
high corner, `ss` at 14.13 fF, is below it) — margin in both directions,
against both risks, not a single-corner fit.

## Decision

`XCCOMP`, a ~12–14 fF MIM feedforward compensation capacitor
(`cap_mim_1f0_m4m5_noshield`, 3.0 um x 3.0 um) from `x1.ncb` to `IN_DRV`,
is added to `design/level_shifter.sch` (and regenerated into
`design/netlist/level_shifter.spice` / `design/netlist/gate_driver_core.spice`
per `design/README.md`). `design/level-shifter-partition.md`'s
device-by-device domain table gains an entry for it (this cell's first
passive component — no diffusion/well terminal, co-located with the
`DNWELL_DRV` group its two terminal nodes already belong to; final
metal-pair choice deferred to layout, per that document).

Full 60-point re-runs of both directly-affected campaigns, against a
clean tree:

- `sim/gate-driver-core-drive/records/20260817-201007-ce8027d.md` —
  `indrv_max` worst case improves from **6.11823 V (margin −118.2 mV)** at
  `ss_125c_vlogic3p30v-vdrv6p00v` to **6.0003 V (margin −0.3 mV)** at
  `fs_-40c_vlogic3p30v-vdrv6p00v` — a **~394x reduction** in the excess
  over the 6.0 V ceiling. `indrv_min` and the previously-failing
  `n1_min_v` (`ss_125c_vlogic3p30v-vdrv6p00v`, −57.65 mV in the baseline
  record, over the inherited −50 mV sanity band) both improve as a side
  effect and no longer fail anywhere in the grid. Spec §3 drive/timing
  targets (rise/fall, `tpdlh`/`tpdhl`, peak source/sink current) are
  unregressed (differences from baseline under 2%, within run-to-run
  noise). The only two harness-check misses are the same
  narrative-documented, pre-existing `ipeak_sink_a` 1 A stretch-target
  shortfall the baseline record already carried, essentially unchanged.
- `sim/level-shifter-oxide-safety/records/20260817-201021-ce8027d.md` —
  decision record 0002's thin-oxide claim is **unregressed**: all 15
  affected `vlogic3p63v-vdrv5p50v` points match the pre-`XCCOMP` baseline
  (`sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md`) to
  the harness's printed precision, and `vna_peak`/`vnb_peak` are unchanged
  across the full 60-point grid. `t_plh`/`t_phl` shift by `XCCOMP`'s own
  delay cost (grid range 0.408–1.109 ns baseline -> 0.447–1.240 ns here),
  expected and budgeted per decision record 0006 (the level shifter's
  `IN`->`OUT` segment is allocated ≥ 30 ns nominal / ≥ 15 ns stretch by
  `design/output-stage-sizing.md` §5).

`spec/gate-driver.md` §5's Exception 3 bullet is updated to cite this
record's measured worst case (6.0003 V, margin −0.3 mV) in place of
decision record 0006's 6.11823 V / −118.2 mV figure, and to note the
bound is now narrowed rather than merely characterized-and-deferred.
**Exception 3 itself is not removed**: decision record 0006's zero-margin
argument (`IN_DRV`'s quiescent high level is `VDD_DRV` by construction, so
§2.3 has exactly zero margin at the 6 V stretch rail regardless of any
shaping) is unaffected by this capacitor, which only reduces the size of
an excursion that must, structurally, still exist.

## Alternatives considered

- **Adopt decision record 0006's characterized 50 fF value directly** —
  rejected: measured during this issue (table above) to regress decision
  record 0003's ratified Exception 1 bound (20–35 mV) to roughly double
  that at the same corner, because decision record 0006's characterization
  never checked the capacitor's effect on the thin-oxide `na`/`nb` path
  it directly loads.
- **Size for the tightest possible `indrv_max` margin (e.g. the 5.5 um /
  ~37–41 fF point that reaches essentially the theoretical best
  cancellation)** — rejected for the same reason: `IN_DRV` compensation is
  already saturated well below that size, so the extra margin bought on
  Exception 3 is negligible while the cost to Exception 1's margin is not.
- **Use `cap_mim_2f0_m4m5_noshield` (2 fF/um², rated to 6 V) for a smaller
  footprint at the same capacitance** — considered and rejected in favor
  of `cap_mim_1f0_*` (1 fF/um², rated to 20 V): `IN_DRV`'s swing directly
  across this capacitor's terminals is the full ~6 V stretch rail, so a
  device rated with no headroom above that (`cap_mim_2f0_*`) repeats
  exactly the zero-margin pattern this issue's own context is about,
  where a device rated with ample headroom is available at a footprint
  cost this design does not need to optimize for at the schematic stage.
- **A different metal-pair variant (M2-M3, M3-M4, M5-M6) for the MIM
  cap** — not a real alternative at the schematic level: all four pairs
  the PDK offers share the same characterized capacitance-per-area
  formula (confirmed directly against `sm141064.ngspice`), so the choice
  is deferred to layout per `design/level-shifter-partition.md` rather
  than decided here.

## Consequences

- `design/level_shifter.sch`, `design/netlist/level_shifter.spice`, and
  `design/netlist/gate_driver_core.spice` now carry `XCCOMP`.
  `design/level-shifter-partition.md` documents its domain placement and
  defers its metal-pair choice to layout. This is the level shifter's
  (and this block's) first passive component.
- `spec/gate-driver.md` §5's Exception 3 bullet now cites the narrower
  6.0003 V / −0.3 mV bound. §2.3's 6.0 V ceiling itself is unchanged, and
  Exception 3 still exists — this record narrows its measured bound, it
  does not remove the exception.
- Two new append-only `sim/` evidence records substantiate this change:
  `sim/gate-driver-core-drive/records/20260817-201007-ce8027d.md` and
  `sim/level-shifter-oxide-safety/records/20260817-201021-ce8027d.md`.
  Neither existing record they compare against
  (`20260817-013400-ae66957.md`, `20260817-010243-2165a49.md`) is edited.
- **A margin lesson for future passive additions to this design**: a
  mitigation characterized against one metric (here, `IN_DRV`) can carry
  an uncosted side effect on a *different*, already-ratified metric
  reachable through the same node (here, `na`/`nb` through the shared
  cascode). Any future passive or shaping component landing on a node
  that is also a device terminal elsewhere in the topology should be
  swept against every claim that node's neighborhood touches, not just
  the claim motivating the addition.
- The level shifter's propagation delay grows modestly (worst-case
  `t_plh`/`t_phl` up to ~1.24 ns, from a ~1.11 ns baseline) but stays far
  inside its allocated budget (`design/output-stage-sizing.md` §5), so
  this costs no headroom against spec §3's end-to-end timing targets.
