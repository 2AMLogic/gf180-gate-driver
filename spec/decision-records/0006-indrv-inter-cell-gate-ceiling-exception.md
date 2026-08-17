# 0006: `IN_DRV` inter-cell gate ceiling — §5's claim narrowed to a third documented exception

- **Status**: Ratified
- **Date**: 2026-08-17
- **Decided by**: Builder agent, issue #136
- **Supersedes**: none. **Extends** decision records
  [0003](0003-predriver-inverter-oxide-margin-exception.md) and
  [0005](0005-output-stage-gate-ceiling-exception.md), and **amends decision
  record 0005's quantification only** (see "Amendment to decision record
  0005" below) — it does not reopen or contradict either record's decision.
  This is the third instance of the two-step
  *result record → exception record* shape this repo already used twice
  (0002 → 0003, 0004 → 0005); here the result record is the end-to-end
  evidence record
  `sim/gate-driver-core-drive/records/20260817-013400-ae66957.md` (issue
  #100 / PR #135), whose Findings 2 and 3 explicitly deferred this choice to
  a follow-up issue.

## Context

`IN_DRV` is the single signal net between the block's two sub-cells
(`design/gate_driver_core.sch`): it is simultaneously the level shifter's
drive-rail-referenced output — the shared drain of the output-buffer pair
`x1.XMPBUF2`/`x1.XMNBUF2` (`design/level_shifter.sch`) — and the
thick-oxide gate of the output stage's first taper inverter
`x2.XMP1`/`x2.XMN1` (`design/output_stage.sch`). Both endpoints are
`pfet_06v0`/`nfet_06v0`, so `spec/gate-driver.md` §2.3's conservative
**6.0 V** thick-oxide DC gate-node ceiling applies to it.

Neither per-cell campaign could observe this node under real drive:
`sim/output-stage-drive/` drives it from an ideal 1 ns-edge voltage source
with no level shifter present, and `sim/level-shifter-oxide-safety/`
terminates the level shifter's `OUT` in a lumped capacitor with no
output-stage devices attached. The end-to-end campaign
(`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md`, Finding 2)
is the first PVT-wide measurement of the real buffer-driving-a-real-gate-load
excursion, and it found that **`IN_DRV` exceeds the 6.0 V ceiling at all 15
of the 6 V stretch-rail PVT points** (5 process corners × 3 temperatures),
from +3.2 mV (`ff_27c_vlogic3p30v-vdrv6p00v`, 6.00318 V) to **+118.2 mV
(6.11823 V) at `ss_125c_vlogic3p30v-vdrv6p00v`**, while clearing it with
≥ 397 mV of margin at every one of the 45 nominal-tolerance points
(4.5/5.0/5.5 V rail; worst 5.60247 V at `ss_27c_vlogic3p63v-vdrv5p50v`).

That is the same *shape* decision record 0005 already ratified as Exception 2
— but `IN_DRV` is explicitly outside its scope. Exception 2 is worded
verbatim for "the output stage's internal taper nodes (`n1`…`n5`,
`design/output_stage.sch`)"; `IN_DRV` is neither one of those nodes nor
internal to that cell — it is the inter-cell net, a port on both sub-cells.
PR #135 correctly declined to fold it in (`CLAUDE.md`: "Spec changes go
through `spec/` with a decision record; agents do not relax the ratified
spec to make results pass") and recorded it as an open, **unratified** §2.3
exceedance. Issue #136 is the follow-up that resolves it.

## Investigation: the mechanism, measured

All numbers in this section are exploratory single-/multi-corner
measurements taken to inform this decision — **not** a new evidence record
under `sim/README.md`'s convention, following exactly the precedent decision
record 0003 set for the analogous investigation ("nothing here is shipped in
the design, so nothing here carries that record's substantiation burden";
contrast with the Decision below, which changes nothing in
`design/level_shifter.sch`). They were taken against the shipped DUT
fragment `design/netlist/gate_driver_core.spice` driven by the existing
`sim/gate-driver-core-drive/testbench/gate_driver_core_tb.spice`, on
ngspice-46 / gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
The baseline reproduces the ratified campaign exactly — `indrv_max` =
6.1182327 V, `tpdlh` = 5.32820 ns, `tpdhl` = 5.39474 ns, peak source
1.01952 A, peak sink 0.882673 A at `ss_125c_vlogic3p30v-vdrv6p00v`, matching
`20260817-013400-ae66957`'s row to every digit it prints.

**The excursion is gate-drive feedthrough through the output buffer's own
`C_gd`, not coupling from the load.** The worst-case peak occurs at
t = 321.875 ns, i.e. *during the level shifter's own internal transition*,
not during the output stage's: at that instant the latch node `x1.ncb` has
already collapsed (6.0 V → 0.35 V), the buffer-pair gate node `x1.nbuf1` is
mid-rise at 1.06 V, and `x2.n1` has not moved (6.00024 V). `IN_DRV` is at
that moment still held at exactly `VDD_DRV` by `XMPBUF2`, which is strongly
on (`Vgs` = −4.94 V). The rising `nbuf1` edge injects charge onto `IN_DRV`
through the gate-drain overlap capacitance of `XMPBUF2` and `XMNBUF2` — both
gates tied to `nbuf1`, both drains tied to `IN_DRV` — faster than
`XMPBUF2`'s channel can sink it and before `XMNBUF2` has turned on. This is
the same class of transient decision records 0003 and 0005 characterize (a
gate node parked at its own rail, kicked past it by capacitive coupling from
an adjacent fast transition), differing only in that here the aggressor is
the driving pair's *own* gate node rather than a downstream drain.

**Mitigation shapes tried**, all against the global worst-case point
`ss_125c_vlogic3p30v-vdrv6p00v` (baseline `indrv_max` = 6.11823 V, −118.2 mV;
baseline end-to-end `tpdlh` = 5.328 ns):

| Mitigation tried | Range swept | Best result | `tpdlh` there | Outcome |
|---|---|---|---|---|
| Series gate-isolation resistor between the BUF1 output (`nbuf1`) and the BUF2 pair's gates | 100 Ω – 1 MΩ | 1 MΩ → 6.00264 V (−2.6 mV) | 36.49 ns | Monotonic above ~1 kΩ but strictly asymptotic: 30 kΩ → −43.5 mV, 200 kΩ → −13.0 mV, 1 MΩ → −2.6 mV. Never crosses 6.0 V, and the values that get close blow spec §3's 25 ns stretch propagation-delay budget. |
| Decoupling capacitor at `IN_DRV` | 10 fF – 20 pF | 20 pF → 6.00070 V (−0.7 mV) | 26.42 ns | Same asymptotic behaviour decision record 0003 measured for the identical mechanism: 1 pF → −12.7 mV, 5 pF → −2.7 mV, 20 pF → −0.7 mV, never crossing, and 20 pF is already over §3's stretch budget. |
| Decoupling capacitor on the aggressor node `nbuf1` | 100 fF – 10 pF | 10 pF → 6.00103 V (−1.0 mV) | 24.65 ns | Identical asymptotic shape; 10 pF sits at the edge of §3's stretch budget (`tpdhl` 29.5 ns — over it). |
| Shrinking the BUF2 pair (less `C_gd`) | W = 15 µm → 1 µm | 1 µm → 6.05176 V (−51.8 mV) | 5.40 ns | Weak and non-monotonic (−82.8 mV at 6 µm, −98.2 mV at 3 µm, −51.8 mV at 1 µm). Expected: the kick is ≈ `C_gd · dV/dt · R_on`, and `C_gd ∝ W` while `R_on ∝ 1/W`, so it is W-invariant to first order. It also makes `x2.n1` *worse* (6.0339 V → 6.0683 V at 3 µm), moving stress onto a node already covered by Exception 2. |
| Weakening the BUF1 pair (slower aggressor edge) | W = 5 µm → 0.5 µm | 0.5 µm → 6.02372 V (−23.7 mV) | 6.25 ns | Asymptotic; 0.25 µm is below the PDK's minimum width for these devices, so the sweep is exhausted at −23.7 mV. |
| Asymmetric gate resistors (P-side only, N-side only) | 30 kΩ | P-side only → 6.02097 V (−21.0 mV) | 5.60 ns | Confirms the P-side (`XMPBUF2`) path dominates the injection; N-side only is *far* worse (6.34271 V, −342.7 mV) because it removes the pull-down that terminates the kick. |
| **Feedforward compensation capacitor, `IN_DRV` ↔ `x1.ncb`** | 5 fF – 100 fF | 50 fF → 6.00002 V (−0.02 mV) | 5.64 ns | **Effective.** `ncb` leads `IN_DRV` by two inverter delays and is collapsing during exactly the window `nbuf1` rises, so its coupled charge is opposite in sign to the feedthrough and coincident with it in time. 10 fF already reaches −0.1 mV; it also all but removes the companion undershoot (`indrv_min` −38.3 mV → −0.8 mV). Still does not cross 6.0 V. |
| Control: the same capacitor to the co-timed node `x1.nca` | 20 – 50 fF | 50 fF → 6.16410 V (−164.1 mV) | 5.44 ns | **Worse**, monotonically with size — a sign- and dose-controlled confirmation that the compensation capacitor works by charge cancellation, not by added loading. |

The **only** variant tried that clears 6.0 V is 100 kΩ + 5 pF + 1 µm BUF2
combined (5.92724 V, +72.8 mV) — and it clears for the wrong reason: at
`tpdlh` = 85.4 ns / `tpdhl` = 46.5 ns it is 3.4× over spec §3's 25 ns
stretch budget *and* over the 50 ns nominal budget, and `IN_DRV` no longer
settles to its own rail within the testbench's 300 ns input pulse. It is not
a smaller overshoot; it is a node that is no longer a valid logic level.

**The Curator's hypothesis about the delay budget is confirmed — and it is
the reason decision record 0005's argument is *not* reused here.** Decision
record 0005 rejected mitigation for `output_stage.sch`'s `n5` partly because
that cell's stretch-rail delay already consumes roughly half its ≤ 10 ns
allocation. `IN_DRV` sits on a far slacker path. Measured per-segment split
(mid-rail crossing to mid-rail crossing):

| Corner | level shifter, `IN` → `IN_DRV` (lh / hl) | output stage, `IN_DRV` → `OUT` (lh / hl) |
|---|---|---|
| `ss_125c` @ 6.00 V | 0.879 / 0.545 ns | 4.450 / 4.848 ns |
| `ss_125c` @ 4.50 V | 1.156 / 0.625 ns | 5.664 / 5.723 ns |
| `ss_-40c` @ 6.00 V | 0.621 / 0.436 ns | 3.243 / 3.691 ns |
| `tt_27c` @ 5.00 V | 0.685 / 0.396 ns | 3.441 / 3.646 ns |

The level shifter is allocated **≥ 30 ns nominal / ≥ 15 ns stretch** of
spec §3's budget (`design/output-stage-sizing.md` §5's split) and uses at
most 1.16 ns of it — under 8 % of its stretch allocation, against the output
stage's ~50 %. So delay cost is *not* what rules mitigation out here, and a
mitigation had to be judged on its own merits. It was: the compensation
capacitor above costs +0.30 ns / +0.12 ns on the level shifter's own segment
and +0.01 ns on the output stage's, which this budget absorbs without
argument.

**Full-grid characterization of the best candidate** (50 fF compensation
capacitor, all 60 PVT points, exploratory): `indrv_max` collapses to
6.00003 V or lower at every one of the 15 stretch points and to the rail
value at every nominal point; `indrv_min` worst case improves from
−38.3 mV to −1.3 mV; end-to-end worst `tpdlh`/`tpdhl` move 6.817/6.351 ns →
7.237/6.477 ns (still > 3× inside §3's 25 ns stretch budget); worst-case
peak source/sink current is unchanged (0.5965 A / 0.5794 A vs. the
baseline's 0.5963 A / 0.5796 A). **The mitigation works.** What it does not
do is clear the ceiling — see the Decision.

**Deck-fidelity caveat, recorded rather than silently absorbed.** The
excursion is a narrow spike, and the harness's default transient tolerances
under-resolve its peak. Re-solving the same worst-case point with a bounded
maximum timestep or a tighter `reltol` moves the *baseline* number
consistently outward:

| Deck setting | baseline `indrv_max` | with 50 fF compensation cap |
|---|---|---|
| harness default (`tran 0.1n 700n`, ngspice default `reltol`) | 6.11823 V (−118.2 mV) | 6.00002 V (−0.02 mV) |
| `maxstep` 20 ps | 6.14362 V (−143.6 mV) | 6.00381 V (−3.8 mV) |
| `maxstep` 10 ps | 6.14767 V (−147.7 mV) | 6.00630 V (−6.3 mV) |
| `reltol` 1e-4 | 6.14569 V (−145.7 mV) | 6.00209 V (−2.1 mV) |
| `reltol` 1e-5 | 6.14801 V (−148.0 mV) | 6.00719 V (−7.2 mV) |
| `maxstep` ≤ 5 ps (with or without tighter `reltol`) | run aborts at 57–133 ns — unusable, not a data point |

The refined settings agree with each other at **−143.6 to −148.0 mV**, so
the ratified campaign's −118.2 mV is a *lower* bound on the true excursion,
not an upper one. This record therefore scopes its exception against the
refined envelope, not against the campaign number alone (see the Decision),
and the underlying harness question — whether the shipped decks resolve
narrow coupling transients, which affects decision records 0004/0005's
numbers as much as this one — is filed as its own follow-up (**issue #156**) rather
than settled by editing any existing record.

## Decision

**`spec/gate-driver.md` §5's oxide-safety claim is narrowed a third time,
following exactly the shape of decision records 0003 and 0005, and the
inter-cell node `IN_DRV` is recorded as a third, distinct, bounded, measured
exception** — not folded into Exception 2, not folded into the general
claim, and not covered by the PDK's duty-cycle TDDB overshoot allowance
(`spec/gate-driver.md` §2.3, explicitly declined here as it was in 0003 and
0005).

**Why an exception is required regardless of mitigation — the decisive
point.** `IN_DRV`'s quiescent high level *is* `VDD_DRV`: it is driven by a
plain complementary push-pull buffer referenced only to
`VDD_DRV`/`GND_DRV`, with no cascode, clamp or level offset in the path, so
by the same convex-hull argument `design/output-stage-sizing.md` §4
pre-registered for `n1`…`n5`, no node in that path can exceed the hull of
its driving sources — and at the 6 V stretch rail that hull is *exactly*
6.0 V, i.e. **zero margin against §2.3 by construction**. Any nonzero charge
coupled onto a node parked exactly at the ceiling puts it above the ceiling.
It follows that no amount of shaping can make `max v(IN_DRV) ≤ 6.0 V` hold
with margin at the 6 V stretch rail; only a structurally different output
stage for the level shifter — one that holds `IN_DRV`'s high level *below*
the drive rail, at a direct cost in the drive available to `x2.XMP1`/`XMN1`
— could, and that is a redesign of a ratified cell, not a bounded addition.
The measured sweeps above are the empirical confirmation of that argument:
seven mitigation shapes, none crossing zero, the best of them landing at
−0.02 mV (harness convention) / −7.2 mV (refined tolerance).

Accordingly:

`spec/gate-driver.md` §5's "Overvoltage / gate-oxide protection" row gains a
third bullet alongside decision records 0003's and 0005's:

- The domain-crossing claim (§4's cascode/clamped topology) holds, verified
  (decision record 0002).
- **Exception 1** (decision record 0003): the level shifter's pre-driver
  inverter output (`inb`) overshoots its own `VDD_LOGIC` rail by 20–35 mV at
  the `vlogic3p63v` corner only.
- **Exception 2** (decision record 0005, quantification amended below): the
  output stage's internal taper nodes (`n1`…`n5`) transiently exceed the
  6.0 V thick-oxide ceiling at the 6 V stretch rail only.
- **New — Exception 3**: `IN_DRV`, the inter-cell net of
  `design/gate_driver_core.sch` (the level shifter's output-buffer drain
  `x1.XMPBUF2`/`x1.XMNBUF2` and the gate of the output stage's first taper
  inverter `x2.XMP1`/`x2.XMN1`, all thick-oxide `pfet_06v0`/`nfet_06v0` and
  never touching a thin-oxide device), transiently exceeds the 6.0 V
  thick-oxide DC gate ceiling (§2.3), **only** at the 6 V stretch rail
  (never at the 4.5/5.0/5.5 V nominal-tolerance points, where it clears the
  ceiling by ≥ 397 mV), at all 15 affected process×temperature points —
  measured worst case **6.11823 V (margin −118.2 mV) at
  `ss_125c_vlogic3p30v-vdrv6p00v`** per
  `sim/gate-driver-core-drive/records/20260817-013400-ae66957.md` (Finding
  2), **bounded at ≤ 150 mV above the ceiling** to cover the −143.6…−148.0 mV
  the same point resolves to under refined transient tolerances (see the
  deck-fidelity caveat above).

`design/level_shifter.sch`, `design/output_stage.sch`,
`design/gate_driver_core.sch` and their netlists are **unchanged** by this
record, and no new `sim/` evidence record is required — nothing in the
design or its evidence trail changes, matching what decision records 0003
and 0005 each concluded for the same choice. **`spec/gate-driver.md` §2.3's
6.0 V DC gate-node ceiling number itself is unchanged**: this record narrows
the scope of §5's protection *claim*, not the ceiling §2.3 measures against.

**The compensation-capacitor mitigation is deferred, not rejected.** Unlike
decision records 0003 and 0005, which found no shape worth carrying forward,
this record hands a fully characterized one to a follow-up: a ~10–50 fF
feedforward capacitor from `IN_DRV` to `x1.ncb` reduces the excursion by
20× (refined tolerance) to > 1000× (harness convention) for +0.3 ns on a
segment with
> 13 ns of slack, with no drive-current cost. It is not adopted *here*
because (a) it does not remove the need for this exception, per the
zero-margin argument above, and (b) adopting it is new design work on a
ratified cell: it deliberately creates a feedforward path from the
drive-rail output node back into the cross-coupled latch node `ncb` whose
regenerative behaviour §4's topology and decision record 0002's ratified
thin-oxide claim both rest on, it would be this block's first passive
component (needing its own entry in `design/level-shifter-partition.md`'s
domain/DNWELL table and its own layout treatment), and it requires
re-verifying `sim/level-shifter-oxide-safety/` and `sim/gate-driver-core-drive/`
in full. That is exactly the class of work decision records 0003 and 0005
both said "requires its own decision record and full-PVT evidence record",
so it gets one: **issue #155**.

## Amendment to decision record 0005 (quantification only)

Decision record 0005 quantifies Exception 2's worst case as `n5` = 6.0538 V
(margin −53.8 mV) at `ss_27c_vdrv6p00v`, measured with
`sim/output-stage-drive/`'s **ideal 1 ns input edge** and no level shifter
present. Under the real level-shifter output edge, Finding 3 of
`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md` measures a
worse taper-node case: **`n1` = 6.10232 V (margin −102.3 mV) at
`sf_-40c_vlogic3p30v-vdrv6p00v`** — roughly 1.9× the ratified overshoot,
with the binding node moving from `n5`/`n4` to `n1`, the stage nearest the
level shifter, as expected once that stage sees a real finite-impedance
driver carrying its own overshoot rather than a stiff ideal source.

**Decision record 0005's decision is unaffected** — Exception 2 exists, is
scoped to the 6 V stretch rail only, and every nominal-tolerance point still
passes with wide margin. Only its *cited worst-case number* is superseded,
exactly as that sim record's own note anticipated ("a future amendment
should cite this record's value instead"). Per this repo's convention a
ratified record is never rewritten, so decision record 0005's argument text
stands untouched; it carries an additive `Amended by` pointer to this
record, and `spec/gate-driver.md` §5's Exception 2 bullet now cites
`n1` = 6.10232 V / −102.3 mV and the end-to-end record.

## Alternatives considered

- **Adopt the feedforward compensation capacitor in this record and ship a
  changed `design/level_shifter.sch`** — measured, effective, and
  *deferred rather than rejected* (see the Decision). Not adopted here
  because it does not remove the need for the exception (`IN_DRV`'s
  quiescent high level is the ceiling, so zero margin is structural) while
  it does open a deliberate feedforward path into the level shifter's
  cross-coupled latch — the node decision record 0002's ratified thin-oxide
  claim depends on — and therefore requires full re-verification of a
  ratified cell plus this block's first passive-component layout treatment.
  Folding that into the record that narrows the claim would be the same
  conflation decision records 0003 and 0005 both explicitly avoided.
- **Passive shaping (series gate resistor, decoupling capacitor at `IN_DRV`
  or at `nbuf1`, resized buffer pairs)** — seven shapes measured above;
  rejected. Every one is asymptotic in exactly the way decision record 0003
  first established with real data for this mechanism: the excess can be
  pushed toward zero but never through it, because eliminating it requires
  either zero coupling capacitance (unavailable for a real gate terminal
  next to a switching drain) or a clamp with an essentially zero
  forward-conduction onset. Resizing the BUF2 pair additionally moves stress
  onto `x2.n1`, which is worse, not better.
- **Fold `IN_DRV` into decision record 0005's Exception 2** — rejected.
  Exception 2 is scoped verbatim to `design/output_stage.sch`'s *internal*
  taper nodes; `IN_DRV` is the inter-cell net and a port on both sub-cells,
  its mechanism is the driving buffer's own gate-drive feedthrough rather
  than a downstream drain's coupling, and its measured excursion is larger
  than any node Exception 2 covers. Widening a ratified claim by
  reinterpretation rather than by a new record is precisely what `CLAUDE.md`
  forbids.
- **Treat the −118.2 mV / 2 % excursion as simulation noise and pass** —
  rejected, for the same reason decision records 0004 and 0005 rejected it,
  and with more evidence than they had: it is present at all 15 stretch
  points and absent at all 45 nominal points, it reproduces outside the
  harness to every digit the ratified record prints (6.11823 V), it grows
  *consistently* (to −148 mV) under
  refined solver tolerances rather than washing out, and its sign and
  magnitude respond dose-dependently to a deliberately injected
  cancellation charge.
- **Relax §2.3's 6.0 V ceiling, or invoke the PDK's TDDB duty-cycle
  overshoot allowance** — explicitly forbidden by issue #136's acceptance
  criteria and by `CLAUDE.md` ("agents do not relax the ratified spec to
  make results pass"); not considered further. Noted only for completeness:
  the measured excursion also stays below the 6.5 V figure §2.3 records as
  the documented absolute limit with no margin, but this record does not
  rely on that.
- **Leave §5's claim as currently worded (do nothing)** — rejected: §5
  currently documents two exceptions and is silent on the inter-cell node,
  leaving the campaign's Finding 2 an open, unratified exceedance in the
  ratified spec — the exact gap issue #136 exists to close.

## Consequences

- `spec/gate-driver.md` §5's "Overvoltage / gate-oxide protection" row now
  carries **three** documented, bounded exceptions instead of two, and
  Exception 2's cited worst case is corrected to the end-to-end measurement.
  §2.3's 6.0 V ceiling itself is unchanged; no PDK allowance is invoked by
  any of the three.
- `design/level_shifter.sch`, `design/output_stage.sch`,
  `design/gate_driver_core.sch`, their netlists, and every existing `sim/`
  record are unchanged. This record adds no new `sim/` evidence record, per
  the same reasoning decision records 0003 and 0005 each applied.
- **The block now has no thick-oxide gate node on the drive-rail signal path
  that clears §2.3's 6.0 V ceiling at the 6 V stretch rail.** `IN_DRV` and
  `n1`…`n5` are all documented exceptions there. The 6 V rail is a *stretch*
  target (§3), not the 5 V nominal rail, and at 4.5/5.0/5.5 V every node
  clears the ceiling with ≥ 397 mV — but any future decision to promote 6 V
  from stretch to nominal must first resolve these three exceptions
  structurally, not inherit them.
- **A characterized mitigation now exists on the shelf.** A follow-up issue
  carries the compensation-capacitor design forward (schematic change,
  `design/level-shifter-partition.md` table entry, layout treatment for the
  block's first passive, and full re-verification of
  `sim/level-shifter-oxide-safety/` and `sim/gate-driver-core-drive/`) —
  filed as issue #155. If it lands, it supersedes this record's *bound* — not this record's
  existence, since the zero-margin argument above is unchanged by it.
- **A deck-fidelity question is now open and affects more than this
  record.** The refined-tolerance re-solve shows the shipped decks
  under-resolve narrow coupling transients by ~25 % at this node. Decision
  records 0004 and 0005 quantify the same class of excursion from decks with
  the same convention, so their numbers are likely lower bounds too. A
  follow-up issue (**#156**) tracks reviewing the harness's transient
  tolerance / maximum-timestep convention; no existing record's number is
  edited on the strength of this observation, and this record's own exception bound is
  scoped to the refined envelope so it does not need to be reopened if that
  review confirms the effect.
- **Carried forward from decision records 0003 and 0005**: this is now the
  *third* independent, ratified instance of the same excursion class in this
  repo — a non-cascoded gate node parked at its own rail, kicked past it by
  capacitive coupling from an adjacent fast transition. It appeared here on
  an *inter-cell* net that neither per-cell campaign could observe, which is
  the transferable lesson: a block composed of individually verified cells
  can still carry an unverified node at the seam between them, and only an
  end-to-end campaign finds it. Any future block in this program should
  probe its inter-cell nets explicitly rather than assume the union of
  per-cell verification covers them.
