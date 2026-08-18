# 0013: Output-stage taper-node gate ceiling — Exception 2 gains an explicit bound

- **Status**: Ratified
- **Date**: 2026-08-18
- **Decided by**: Builder agent, issue #163
- **Supersedes**: none. **Extends** decision records
  [0005](0005-output-stage-gate-ceiling-exception.md) and
  [0006](0006-indrv-inter-cell-gate-ceiling-exception.md) —
  **quantification and bound only**, in the same additive-amendment shape
  0006 already used against 0005. Neither record's decision, scope, or
  reasoning is reopened. This is the fourth instance of the
  *result record → exception record → bound-narrowing record* shape this
  repo has now used repeatedly (0002/0003, 0004/0005, 0006/0007's Exception
  3 narrowing); here the result record is issue #156's harness-tolerance
  fix and the re-run it produced.

## Context

Issue #156 (merged via PR #165) fixed the sim harness so every generated
`tran` deck defaults to `.options reltol=1e-4` (previously ngspice's own
default, `reltol=1e-3` with no bounded `maxstep`), because the
under-resolved default made every §2.3 gate-ceiling number on record a
*lower* bound on the true excursion, not a conservative upper one. Decision
record 0006 anticipated this exact consequence for the taper nodes when it
narrowed its own Exception 3 bound and explicitly deferred the taper-node
question to a follow-up ("no existing record is edited on the strength of
this observation").

The re-run this produced,
`sim/gate-driver-core-drive/records/20260817-202640-d7bda87.md` (supersedes
`20260817-182927-26592a1`, schematic DUT), moves decision record 0005's
Exception 2 (`design/output_stage.sch`'s internal taper nodes `n1`…`n5`) by
more than any of the block's other two documented exceptions:

| | Ratified spec text (decision record 0006's amendment to 0005) | This re-run | Delta |
|---|---|---|---|
| Binding node | `n1` | `n1` (unchanged) | — |
| Worst case | 6.10232 V, margin **−102.3 mV** | 6.14803 V, margin **−148.0 mV** | **+45.7 mV** |
| Binding corner | `sf_-40c_vlogic3p30v-vdrv6p00v` | `ss_-40c_vlogic3p30v-vdrv6p00v` (binding corner moved; the previously-cited corner now reads 6.14332 V / −143.3 mV, within 4.7 mV of the new worst case) | — |

By contrast, Exception 3 (`IN_DRV`, same record) moved only +30.1 mV
(6.11823 V → 6.14833 V, margin −118.2 mV → −148.3 mV, same corner) and, per
decision record 0006's own pre-registered "bounded at ≤ 150 mV above the
ceiling" clause, needed no follow-up action — the new number lands inside a
bound decision record 0006 set specifically to absorb this class of
resolution effect. **Exception 2 has no such clause.** Decision record 0005
(and 0006's amendment to it) states only the single measured number, with
no explicit ceiling the way Exception 3 has.

The companion postlayout re-run,
`sim/gate-driver-core-drive-postlayout/records/20260818-002620-ac84870.md`
(supersedes `20260817-174259-f1a4903`, extracted DUT, no RC-parasitic
extraction — device-level LVS extraction only), shows the same node at
**6.13027 V (margin −130.3 mV)** at the identical binding corner,
`ss_-40c_vlogic3p30v-vdrv6p00v` — smaller in magnitude than the schematic
figure, consistent with the schematic-DUT campaign remaining this exception's
worst-case, conservative citation.

**Provenance caveat, carried forward explicitly rather than silently
assumed away.** Both records above are built from the **pre-`XCCOMP`**
design (`design/netlist/gate_driver_core.spice` sha256
`bf863872ac4ba5fcca2ae114f1ed338c4ce1161f278174e3dc27b8ab32d9d1ba`), not the
post-`XCCOMP` design decision record 0007 adopted (sha256
`0bc2bed8...`) — issue #156 (harness tightening) and issue #155 / PR #167
(`XCCOMP` addition) were developed on parallel branches, and neither was
rebased onto the other before either merged, so no record on `origin/main`
today re-runs the full 60-point grid with both changes combined. `XCCOMP` is
a feedforward capacitor from the level shifter's `x1.ncb` to `IN_DRV`
(`design/level_shifter.sch`) — it sits electrically upstream of the output
stage's taper chain (`design/output_stage.sch`), and decision record 0007's
own re-verification found `IN_DRV`'s corrected drive edge essentially
unchanged in shape (only its peak amplitude falls, from −118.2 mV to
−0.3 mV), which would be expected to reduce, not increase, downstream
coupling into `n1`. So this is **unlikely** to move the numbers below in the
wrong direction — but "unlikely" is not "confirmed," and this record's bound
is sized with that gap in mind rather than assuming it closed (see
"Sizing the bound" below).

## Investigation: why this exception's bound cannot simply mirror Exception 3's ≤ 150 mV

Decision record 0006 set Exception 3's bound only after directly
characterizing `IN_DRV`'s own response to a small deck-fidelity sweep at its
own binding corner (`ss_125c_vlogic3p30v-vdrv6p00v`):

| Deck setting | `IN_DRV` margin |
|---|---|
| harness default (pre-#156, unbounded `reltol`) | −118.2 mV |
| `reltol=1e-4` (this repo's harness default since #156) | −145.7 mV |
| `maxstep` 20 ps | −143.6 mV |
| `maxstep` 10 ps | −147.7 mV |
| `reltol=1e-5` | **−148.0 mV** |

The refined settings converged to a narrow band (−143.6 to −148.0 mV), and
the ≤ 150 mV bound was set with only ~2 mV of headroom above that
**converged** ceiling — a tight bound, but a justified one, because the
deeper sweep had already been run and had stopped moving.

**No equivalent deeper sweep exists for `n1`.** The only refined-tolerance
measurement this record has for the taper nodes is the single
`reltol=1e-4` re-run above (−148.0 mV) — the harness's own default since
#156, not a further-tightened `maxstep`/`reltol=1e-5` point run specifically
against this node's own binding corner. `IN_DRV`'s own table shows a further
~2.3 mV of movement between `reltol=1e-4` (−145.7 mV) and the converged
`reltol=1e-5` point (−148.0 mV) at its corner — i.e., the harness-default
setting alone was not yet the converged value for that node. There is no
reason to assume `n1`'s mechanism (Miller/gate-capacitance coupling from an
adjacent taper stage, decision record 0005's own characterization) resolves
faster than `IN_DRV`'s (gate-drive feedthrough) under further tolerance
tightening; if it behaves similarly, `n1`'s fully-converged worst case could
plausibly land a further few mV beyond the −148.0 mV already measured here.
Setting Exception 2's bound at ≤ 150 mV — the same ~2 mV headroom Exception
3 used — would therefore size the bound against an unconverged number,
which is the wrong reference point to build a hard ceiling on.

## Decision

**Decision record 0005's Exception 2, as amended by decision record 0006, is
amended a second time — quantification and bound only — to cite this
record's re-measured worst case and to adopt an explicit ceiling, following
the shape decision record 0006 established for Exception 3.**

`spec/gate-driver.md` §5's Exception 2 bullet is updated to read:

> **Exception 2** (decision record 0005, quantification amended by decision
> record 0006, further amended and bounded by decision record 0013): the
> output stage's internal taper nodes (`n1`…`n5`, `design/output_stage.sch`,
> entirely thick-oxide `nfet_06v0`/`pfet_06v0`) transiently exceed the 6.0 V
> thick-oxide DC gate ceiling (§2.3), only at the 6 V stretch rail (never at
> the 4.5/5.0/5.5 V nominal-tolerance points) — measured worst case `n1` =
> 6.14803 V (margin −148.0 mV) at `ss_-40c_vlogic3p30v-vdrv6p00v` under the
> harness's `reltol=1e-4` tolerance (post-issue-#156), across the 15
> affected process×temperature points,
> `sim/gate-driver-core-drive/records/20260817-202640-d7bda87.md`; a
> companion extracted-DUT (no RC-parasitic) postlayout re-run corroborates a
> smaller excursion at the same corner (6.13027 V, margin −130.3 mV,
> `sim/gate-driver-core-drive-postlayout/records/20260818-002620-ac84870.md`).
> **Bounded at ≤ 175 mV above the ceiling.**

**Sizing the bound: ≤ 175 mV.** This gives ~27 mV of headroom above the
current measured worst case (−148.0 mV) — deliberately more headroom than
Exception 3's ≤ 150 mV bound carries above *its* converged number (~2 mV),
because Exception 2, unlike Exception 3, has not had a targeted deeper
deck-fidelity sweep (`maxstep` 10–20 ps, `reltol=1e-5`) run against its own
binding node and corner to confirm convergence. 175 mV is chosen, rather
than a bound set flush against −148.0 mV, specifically to absorb the ~2–5 mV
of further degradation the `IN_DRV` analogy above suggests is plausible
under a deeper sweep this record does not itself perform, while still
tracking the same order of headroom (high tens of mV, not hundreds) that
Exception 3's own bound-setting precedent used relative to a number that had
not yet been through its deepest available resolution. It is not a
round-number restatement of Exception 3's 150 mV: Exception 2's mechanism
(Miller/gate-capacitance coupling between adjacent taper stages, decision
record 0005) is a distinct physical path from Exception 3's (gate-drive
feedthrough through a driving buffer's own `C_gd`, decision record 0006),
and the two are not required to share a numeric bound merely because they
share an excursion class.

`design/output_stage.sch` and `design/netlist/output_stage.spice` are
**unchanged** by this record. No new `sim/` evidence record is required —
this record cites the two records issue #163's own investigation already
produced and does not run a new campaign. **`spec/gate-driver.md` §2.3's
6.0 V DC gate-node ceiling number itself is unchanged** — this record only
narrows/bounds the *quantification* of an already-ratified exception, it
does not touch the ceiling the exception is scoped against.

## Alternatives considered

- **Bound Exception 2 at ≤ 150 mV, matching Exception 3's number exactly** —
  rejected. Exception 3's ≤ 150 mV bound was set with only ~2 mV of
  headroom above a number decision record 0006 had already pushed through a
  full deck-fidelity sweep (`maxstep` down to 10 ps, `reltol` down to
  1e-5) and confirmed had converged. Exception 2 has only the single
  `reltol=1e-4` data point (−148.0 mV) — the harness default, not a
  confirmed-converged figure — and the `IN_DRV` analogy shows that setting
  can still move a further few mV under deeper tightening. A ≤ 150 mV bound
  here would carry near-zero, possibly negative, headroom against an
  unconverged number, which is not a genuine bound.
- **Leave Exception 2 unbounded (no explicit ceiling), matching how it reads
  today** — rejected. The whole reason issue #163 exists is that this gap is
  now visible: Exception 2 moved 45.7 mV under a harness fix that Exception
  3 absorbed cleanly only because it had a pre-registered bound. Leaving
  Exception 2 unbounded defers the same reckoning to the next harness or
  design change that moves this number again, with no documented answer for
  whether the new value is still "the same exception" or a regression. The
  issue's own edge-case guidance treats "no bound needed" as an acceptable
  outcome only when stated with rationale — here the rationale runs the
  other way: a bound is warranted and cheap to state.
- **Run the same deeper deck-fidelity sweep (`maxstep`/`reltol=1e-5`)
  decision record 0006 ran for `IN_DRV`, against `n1`'s own binding corner,
  before setting a bound** — considered, and would be the more rigorous
  path, but is out of scope for this issue as filed (a spec-ratification
  decision, not a new simulation campaign) and duplicates exactly the
  investigation decision record 0006 already did for the analogous node.
  Sizing the bound with explicit extra headroom to cover the plausible
  further movement (as this record does) captures the same protection
  without requiring a new campaign; a future record is free to tighten this
  bound if that sweep is run and confirms convergence below 175 mV.
- **Re-run the full grid against the post-`XCCOMP` design before deciding
  anything, to close the provenance caveat first** — considered, and is
  the right thing for a future record to do (the combined re-run this
  issue's own Curator enhancement flags as not yet existing on
  `origin/main`), but is not required to make *this* decision: `XCCOMP` is
  electrically upstream of the output stage and decision record 0007's own
  re-verification found no adverse change to `IN_DRV`'s edge shape, only its
  peak amplitude — a downstream effect expected to help, not hurt, `n1`. Not
  running that combined campaign here is disclosed explicitly (Context,
  above) rather than silently assumed clear, and the bound in this record is
  the one number this decision can set without it.
- **Relax the 6.0 V ceiling itself, or invoke the PDK's TDDB duty-cycle
  overshoot allowance** — explicitly forbidden by `CLAUDE.md` ("agents do
  not relax the ratified spec to make results pass") and by the precedent
  every prior record in this family (0003, 0005, 0006, 0007) already set;
  not considered further.

## Consequences

- `spec/gate-driver.md` §5's Exception 2 bullet now cites the re-measured
  worst case (`n1` = 6.14803 V, margin −148.0 mV) and carries an explicit
  **≤ 175 mV** bound, matching Exception 3's pattern of a bounded, not
  open-ended, exception. §2.3's 6.0 V ceiling itself is unchanged.
- `design/output-stage-sizing.md` §6 is updated (see below) to cite this
  record's number and bound, alongside its existing citations of decision
  records 0005 and 0006, following the same incremental-citation pattern §6
  already uses.
- `design/output_stage.sch`, its netlist, and every existing `sim/` record
  are unchanged. This record adds no new `sim/` evidence record — it cites
  the two records issue #163's investigation (and the harness-fix re-run
  behind it) already produced.
- **The provenance caveat (pre-`XCCOMP` netlist) is now an explicitly
  tracked open item**, not a silent gap: a future combined re-run of
  `sim/gate-driver-core-drive/` and `sim/gate-driver-core-drive-postlayout/`
  against the post-`XCCOMP` design should re-check this record's cited
  numbers and bound before either is treated as fully closed. If that re-run
  moves `n1`'s worst case, the first check is whether it still lands inside
  the ≤ 175 mV bound set here; if not, this record's bound (not its
  existence) needs its own follow-up, in the same "bound narrowed/widened by
  a new record" shape decision record 0007 already used for Exception 3.
- **This is now the second exception in this block's §5 protection claim to
  carry an explicit numeric bound** (Exception 3 since decision record 0006,
  Exception 2 since this record) out of three total. Exception 1 (decision
  record 0003) remains characterized only by its measured 20–35 mV band, not
  a bound — it has shown no comparable sensitivity to the harness-tolerance
  fix (+0.72 mV under the same re-run, well inside its existing
  characterization) and is not reopened by this record.
