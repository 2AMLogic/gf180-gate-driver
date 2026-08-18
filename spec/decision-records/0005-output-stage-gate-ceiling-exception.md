# 0005: Output-stage gate-ceiling — §5's claim narrowed to a second documented exception

- **Status**: Ratified
- **Date**: 2026-08-12
- **Decided by**: Builder agent, issue #24
- **Amended by**: [decision record
  0006](0006-indrv-inter-cell-gate-ceiling-exception.md), 2026-08-17 —
  **quantification only**. This record's decision stands unchanged; its
  cited worst-case number (`n5` = 6.0538 V, margin −53.8 mV, measured under
  `sim/output-stage-drive/`'s ideal 1 ns input edge) is superseded by the
  end-to-end measurement under the real level-shifter edge, `n1` = 6.10232 V
  (margin −102.3 mV) at `sf_-40c_vlogic3p30v-vdrv6p00v`
  (`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md`, Finding
  3). The argument text below is left exactly as ratified — see the
  "Amendment" section at the end of this file, and decision record 0006's
  "Amendment to decision record 0005" section, for the correction. Further
  amended by [decision record
  0013](0013-output-stage-taper-node-gate-ceiling-bound.md), 2026-08-18 —
  **quantification and bound**. Under the harness's post-issue-#156
  `reltol=1e-4` tolerance, the same node re-measures worse still: `n1` =
  6.14803 V (margin −148.0 mV) at `ss_-40c_vlogic3p30v-vdrv6p00v`, and
  decision record 0013 additionally gives this exception its first explicit
  ceiling bound (≤ 175 mV above the 6.0 V ceiling), mirroring decision
  record 0006's Exception 3 bound. This record's argument text is, again,
  left exactly as ratified.
- **Supersedes**: none. **Extends** decision record 0004 (does not reopen or
  contradict it — 0004's own "Consequences" section explicitly deferred this
  exact choice to a follow-up issue; this record is that follow-up, and it
  follows the same two-step shape decision record 0002 → 0003 already used
  for the analogous level-shifter finding).

## Context

Decision record 0004 (issue #6 / PR #23) found that `design/output_stage.sch`
meets every drive-strength (§3) and this cell's own propagation-delay
allocation (§5), but fails the §2.3 gate-ceiling acceptance criterion: at
every one of the 15 PVT points on the 6 V stretch rail (all 5 process corners
× all 3 temperatures), at least one internal taper node (`n1`…`n5`)
transiently exceeds the ratified 6.0 V DC ceiling — worst case `n5` = 6.0538 V
at `ss_27c_vdrv6p00v` (margin **−53.8 mV**), close behind `n4` = 6.0526 V at
`ss_125c_vdrv6p00v` (**−52.6 mV**). `design/output-stage-sizing.md` §4
pre-registered the reason analytically before any simulation ran: this cell
has no cascode or clamp — a plain rail-to-rail complementary push-pull chain
referenced only to `VDD_DRV`/`GND_DRV` — so no node can exceed the convex
hull of its driving sources; at the 6 V stretch rail that bound is *exactly*
6.0 V, zero margin by construction. The measured result is worse than that
quasi-static bound, not merely equal to it, which decision record 0004
attributes to a gate-capacitance/Miller-coupling transient on top of the
quasi-static bound — the same excursion shape already ratified once before in
this repo for a different cell (decision records
[0002](0002-level-shifter-oxide-safety-result.md)/[0003](0003-predriver-inverter-oxide-margin-exception.md):
the level shifter's pre-driver inverter overshooting its own `VDD_LOGIC` rail
by 20–35 mV at its own +10 % corner). Decision record 0004 explicitly deferred
the choice between mitigating (active clamp/cascode, re-verify) and formally
narrowing `spec/gate-driver.md`'s overvoltage-protection claim to a follow-up
issue — issue #24, resolved here.

## Investigation: why mitigation is not attempted here

Issue #24 scoped two candidate mitigation shapes ("an active clamp or
cascode on this cell's final stage") but its own Proposed Solution section
already pre-argued, correctly, that passive R/C shaping is unlikely to help
here for exactly the reason decision record 0003 established with real
single-corner sweep data for the analogous mechanism: a Miller-coupling kick
onto a node already parked at its own rail can only be pushed toward zero
asymptotically by passive shaping, not eliminated, because eliminating it
requires either zero coupling capacitance (not available for a real gate
terminal next to a switching drain) or an active clamp with an essentially
zero forward-conduction onset.

**Re-confirming the mechanism, not re-deriving it from scratch.** A
single-corner reproduction of the worst-case point
(`ss_27c_vdrv6p00v`, the same corner and value driving `n5`'s 6.0538 V global
worst case) was run directly against the DUT fragment
(`sim/output-stage-drive/testbench/output_stage_dut.spice`) outside the
harness, to confirm this is the same class of transient decision record 0003
already characterized, not a different failure mode requiring fresh
mitigation exploration: it reproduced `n5_max_v` = 6.05380 V, matching the
existing evidence record
(`sim/output-stage-drive/records/20260812-064304-03699ea.md`) to 5 significant
figures. This confirms the excursion is deterministic and reproducible
outside the harness's own corner sweep, consistent with a real transient
mechanism (decision record 0004's own "not simulation noise" finding),
before reasoning about mitigation options against it. Exploratory
capacitive-loading sweeps at `n5` (the same "decoupling cap" mitigation shape
decision record 0003 tried and found only asymptotic) were attempted at
this same corner but did not complete before this record's investigation
window closed — the shared build/sim host was running numerous concurrent
PVT sweeps from other agents at load average > 15 during this investigation,
and `n5` is a much stiffer node here than the analogous 0003 case (it drives
this cell's largest devices, `MP6`/`MN6` at `Wp=5000 µm`/`Wn=2200 µm` §2 of
`design/output-stage-sizing.md`, not a single small pre-driver inverter),
which is expected to slow transient convergence further. This is recorded as
an incomplete data point, not evidence either way for capacitive loading
specifically — the decision below does not rely on it, and rests instead on
the two independent, sufficient arguments following.

**Two independent arguments against mitigation, neither of which needs a
completed sweep to stand:**

1. **Passive shaping cannot close this gap, on the same reasoning decision
   record 0003 already established with real data for the identical
   mechanism** (gate node parked at its own rail, kicked by Miller coupling
   from a much larger, faster-switching drain transition on the very next
   stage). `n5` sits at *exactly* `VDD_DRV` through the quiescent phase
   immediately preceding the transition (§4 of
   `design/output-stage-sizing.md`'s own quasi-static bound, confirmed
   exactly by `vout_max_v`/node-`max_v` checks in the evidence record); any
   nonzero charge coupled onto it from the adjacent stage's transition
   necessarily pushes the transient peak past `VDD_DRV`, and passive R/C
   shaping can only drive that excess toward zero asymptotically, never to
   it. Decision record 0003's own capacitor sweep (5 fF – 5 pF) already
   demonstrated this asymptotic-only behavior directly, for the same class
   of node in this same PDK; nothing about this cell's topology suggests a
   different outcome, and the corner-tracking, all-15-points-affected shape
   of this cell's excursion is the same "real, repeatable transient
   mechanism, not noise" signature decision record 0002 established.
2. **This cell's stakes are strictly worse than decision record 0003's,
   making an active clamp/cascode even less proportionate here, not more.**
   Decision record 0003 rejected an active clamp for a ≤1 % margin on a
   thin-oxide node that never leaves the 3.3 V logic domain and carries no
   drive-current responsibility. Here, `n5` (and `n4`, a close second) is the
   gate node of this cell's **final, highest-current stage** — `MP6`/`MN6`,
   sized in §2 of `design/output-stage-sizing.md` to source/sink ≥ 0.5 A at
   every PVT point, the cell's core acceptance criterion (§3, met at every
   point per decision record 0004). Any clamp or cascode device added at
   `n5` sits directly on the highest-capacitance, highest-current node in the
   chain and on the critical path decision record 0004 already confirmed is
   the tightest: this cell's §6 stretch-rail propagation delay
   (`tpdlh`/`tpdhl` = 4.56 ns/5.01 ns) already consumes roughly half its
   ≤ 10 ns stretch-rail allocation (§5 of
   `design/output-stage-sizing.md`), leaving materially less headroom than
   decision record 0003 had (that record's own capacitor experiment pushed
   one delay measurement from 0.99 ns to 7.87 ns, an 8× increase, to close
   only 2 mV of a 35 mV gap — a device on this cell's final-stage node,
   which is both larger and delay-critical, would be expected to cost
   proportionately more for a smaller (53.8 mV) gap). A structural cascode
   (dividing `n5`'s swing across two series devices, rather than clamping
   the existing node) would additionally require re-deriving this cell's
   entire final-stage sizing derivation (§1–§3 of
   `design/output-stage-sizing.md`, its own PVT-swept current-density
   sizing basis) from scratch, since a cascode changes the voltage available
   to drive the output load — a full redesign of the verified device, not a
   bounded addition, disproportionate to closing a sub-1 % margin gap.

## Decision

**§5's oxide-safety claim is narrowed a second time, following exactly the
same shape as decision record 0003's first exception, and the output
stage's internal taper nodes are recorded as a second, distinct, bounded,
measured exception** — not folded into the general claim and not covered by
the PDK's duty-cycle TDDB overshoot allowance (`spec/gate-driver.md` §2.3,
explicitly declined, same as 0003).

`spec/gate-driver.md` §5's "Overvoltage / gate-oxide protection" row is
updated to add a second bullet alongside decision record 0003's existing
exception:

- The domain-crossing claim (§4's cascode/clamped topology) holds, verified
  (decision record 0002).
- The pre-driver inverter's own output overshoots its own `VDD_LOGIC` rail by
  20–35 mV at the `vlogic3p63v` corner only (decision record 0003).
- **New**: `design/output_stage.sch`'s internal taper nodes (`n1`…`n5`, the
  shared gate/drain nodes of the pre-driver taper's complementary pairs,
  never touching a thin-oxide device — this cell is entirely
  `nfet_06v0`/`pfet_06v0`, spec §2.5) transiently exceed the 6.0 V thick-oxide
  DC gate ceiling, **only** at the 6 V stretch rail (never at the
  4.5/5.0/5.5 V nominal-tolerance points, per decision record 0004), measured
  worst case `n5` = 6.0538 V (`ss_27c_vdrv6p00v`, margin −53.8 mV) across all
  15 affected process×temperature points —
  `sim/output-stage-drive/records/20260812-064304-03699ea.md`.

`design/output_stage.sch` is **unchanged** by this record. No new
`sim/output-stage-drive/` evidence record is required (per issue #24's own
Test Plan: "if narrowing the claim, confirm the ratified decision record's
stated bound (≤ 53.8 mV) matches the measured excursion... at all 15
points" — it does, exactly, since nothing in the design or its evidence
trail changes). **`spec/gate-driver.md` §2.3's 6.0 V DC gate-node ceiling
number itself is unchanged** — this record narrows the scope of §5's
protection *claim*, not the ceiling §2.3 measures against.

## Alternatives considered

- **Add an active clamp or cascode to the final stage's taper node(s)
  (issue #24's option 1)** — considered in detail above; rejected. Passive
  shaping is expected to only push the gap toward zero asymptotically, per
  decision record 0003's own real-data precedent for the identical
  Miller-coupling mechanism; an active clamp or structural cascode is a
  nontrivial redesign of this cell's highest-current, most delay-critical
  node, expected to cost proportionately more of this cell's already-tight
  stretch-rail delay budget than 0003's rejected clamp attempt would have
  cost the (lower-stakes) pre-driver-inverter node, to close a smaller
  (53.8 mV vs. 20–35 mV) gap.
- **Treat the −53.8 mV / 0.9 % excursion as within simulation noise and pass
  anyway** — rejected, for the same reason decision record 0004 already
  rejected it: consistent across all 15 process×temperature points at the
  6 V stretch rail and absent at every lower-rail point, the signature of a
  real, repeatable transient mechanism.
- **Relax the 6.0 V ceiling itself, or invoke the PDK's TDDB duty-cycle
  overshoot allowance** — explicitly forbidden by issue #6's original
  instruction, issue #24's acceptance criteria, and `CLAUDE.md` ("agents do
  not relax the ratified spec to make results pass"); not considered
  further.
- **Leave §5's claim as currently worded (do nothing)** — rejected: the
  claim ("no thin-oxide node is designed to exceed 3.63 V", already silent
  on thick-oxide nodes) does not currently address this cell's thick-oxide
  gate ceiling at all, leaving decision record 0004's finding undocumented
  in the ratified spec — the exact gap issue #24 exists to close.

## Consequences

- `spec/gate-driver.md` §5's "Overvoltage / gate-oxide protection" row gains
  a second documented, bounded exception, alongside decision record 0003's
  existing one. §2.3's 6.0 V ceiling itself is unchanged; no PDK allowance
  is invoked.
- `design/output_stage.sch`,
  `design/netlist/output_stage.spice`, and
  `sim/output-stage-drive/records/20260812-064304-03699ea.md` (decision
  record 0004's evidence) are unchanged and remain the authoritative, sole
  evidence trail for this cell — this record adds no new `sim/` record, per
  issue #24's Test Plan for the option chosen here.
- **This repo now has two independent, ratified instances of the same
  excursion class** (a non-cascoded thick- or thin-oxide gate node parked at
  its own rail, kicked past it by Miller coupling from an adjacent
  switching transition) — decision records 0002/0003 and 0004/0005. Any
  future cell in this program reusing a non-cascoded push-pull or tapered
  buffer topology at a rail already parked at its own absolute ceiling
  should expect this same class of small transient overshoot and budget
  margin for it from the outset (or add a structural cascode from the
  start, accepting its sizing cost), rather than assume a gate node is safe
  merely because it never numerically exceeds its own nominal supply value.
- If a future revision of this cell (or a reused instance in another block,
  most plausibly a half-bridge high-side revision per `spec/gate-driver.md`
  §1) needs the output stage's internal taper nodes to also clear 6.0 V with
  margin — not just document why they currently don't — that is new design
  work (most plausibly a structural cascode, re-deriving §1–§3 of
  `design/output-stage-sizing.md` from scratch) requiring its own decision
  record and full-PVT evidence record, not a silent edit to this one.

---

## Amendment (2026-08-17, decision record 0006, issue #136)

*Additive. Nothing above this line is altered — this record's decision, its
scope, and its reasoning all stand as ratified on 2026-08-12. Only the
worst-case number it cites is corrected, exactly as the evidence record
below anticipated ("a future amendment should cite this record's value
instead").*

Every number this record quotes for the taper nodes comes from
`sim/output-stage-drive/records/20260812-064304-03699ea.md`, which drives
`IN_DRV` from an **ideal 1 ns-edge voltage source** with no level shifter
present. The end-to-end campaign
`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md` (issue #100)
has since measured the same nodes under the **real level-shifter output
edge**, and Finding 3 records a worse case:

| | This record (ideal 1 ns edge) | End-to-end (real level-shifter edge) |
|---|---|---|
| Binding node | `n5` | **`n1`** (the stage nearest the level shifter) |
| Worst case | 6.0538 V | **6.10232 V** |
| Margin to §2.3's 6.0 V ceiling | −53.8 mV | **−102.3 mV** (≈ 1.9×) |
| Binding corner | `ss_27c_vdrv6p00v` | `sf_-40c_vlogic3p30v-vdrv6p00v` |

The mechanism is unchanged (a gate-capacitance/Miller-coupling kick onto a
node parked at its own rail); only its magnitude moves, because the first
taper stage now sees a real finite-impedance driver carrying its own
overshoot rather than a stiff ideal source. **The exception's existence and
its 6 V-stretch-rail-only scope are unaffected** — all 45 nominal-tolerance
points still clear the ceiling with wide margin — so this is a correction to
the bound, not a reopening of the decision. `spec/gate-driver.md` §5's
Exception 2 bullet cites the corrected number and the end-to-end record.

Decision record 0006 additionally records a deck-fidelity observation that
bears on this record's numbers: re-solving the analogous excursion with a
bounded maximum timestep or a tighter `reltol` moves the peak outward by
~25 %, so figures measured at the harness's default transient tolerances —
including this record's and decision record 0004's — are likely lower bounds
on the true excursion. That is tracked as its own follow-up; no number in
this record is edited on the strength of it.
