# 0015: Pre-driver-inverter overshoot — Exception 1 is re-measured at converged solver tolerance and gains an explicit bound

- **Status**: Ratified
- **Date**: 2026-08-18
- **Decided by**: Builder agent, issue #193
- **Supersedes**: none. **Extends** decision record
  [0003](0003-predriver-inverter-oxide-margin-exception.md) —
  **quantification and bound only**, in the same additive-amendment shape
  decision record [0013](0013-output-stage-taper-node-gate-ceiling-bound.md)
  used against decision records 0005/0006 for the sibling Exception 2.
  Decision record 0003's decision, scope, and reasoning are not reopened:
  the physical claim (`inb` never leaves the 3.3 V logic domain; the
  overshoot is ~1 % of that node's own rail; no mitigation is warranted) is
  unchanged, and no PDK duty-cycle TDDB allowance is invoked here either.
  This is the fifth instance of this repo's
  *result record → exception record → bound-narrowing record* shape
  (0002/0003, 0004/0005, 0006/0007, 0013); it is the last of the three §5
  exceptions to acquire an explicit bound.

## Context

Decision record 0003 states Exception 1 as a **measured range**: `inb` (the
level shifter's pre-driver inverter output, gate of thin-oxide `XMNPDB`)
transiently overshoots its own `VDD_LOGIC` rail by **20–35 mV**, worst case
3.65019 V (`ff_-40c`) to 3.66512 V (`ss_125c`), at the 15 `vlogic3p63v`
(+10 %) process×temperature points
(`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`).

That evidence was taken at ngspice's factory-default `reltol=1e-3`. Issue
#156 / PR #165 (commit `a5d4759`) has since made **`reltol=1e-4` the
harness-wide default**, on the finding that the looser default steps over the
peak of exactly this class of sub-nanosecond coupling spike — "the
harness-default figure was a measured lower bound on the excursion, not the
excursion itself". Under the new default the same experiment measures the
*uncompensated* circuit at **35.84 mV**
(`sim/level-shifter-oxide-safety/records/20260817-202836-d7bda87.md`),
0.84 mV outside decision record 0003's stated 35 mV upper figure — before
any compensation capacitor exists in the design at all. Decision record 0014
found the same thing from the other direction and deliberately declined to
widen a ratified record's band as a side effect of an unrelated device
change, filing issue #193 instead. This record is that follow-up.

**This is a solver-fidelity staleness problem, not a newly discovered
risk.** Nothing about the circuit changed; a number fitted to a coarse deck
no longer describes what a finer deck measures. Per `CLAUDE.md` the fix is
not to quietly re-word decision record 0003 (a Ratified record) but to amend
it here, with fresh evidence.

## Evidence: a full grid against `origin/main`, plus the convergence sweep the range never had

**Full 60-point PVT grid, harness-default `reltol=1e-4`, against the design
as it stands on `origin/main` (`5260603` — decision record 0014's four
series `cap_mim_2f0_m4m5_noshield` `XCCOMP` stack):**
`sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`. Band
across the 15 affected points: **20.34–35.33 mV**, worst case **3.66533 V**
at `ss_125c_vlogic3p63v-vdrv5p50v` — the same binding corner every record of
this experiment has found. All 60 points match
`20260818-060158-673fcf0.md` to the six significant figures the harness
prints, so that record is independently reproduced rather than superseded.

**Targeted deck-fidelity sweep at the binding corner.** Decision record 0006
ran such a sweep for `IN_DRV` before setting Exception 3's bound; decision
record 0013 flagged that Exception 2 had never had one and sized its bound
conservatively to compensate. Exception 1 had never had one either. It has
now (exploratory single-corner runs, `--no-write`, not evidence records in
their own right — the same status decision record 0003 gave its own
mitigation sweep; the full-grid record above is the evidence):

| Deck setting | `inb` peak, `ss_125c_vlogic3p63v-vdrv5p50v` | over rail | uncompensated DUT (`d52d7ab6…`), same corner | over rail |
|---|---|---|---|---|
| `reltol=1e-4` (harness default since #156) | 3.66533 V | 35.33 mV | 3.66584 V | 35.84 mV |
| `tran … 20p` max timestep | 3.66533 V | 35.33 mV | — | — |
| `tran … 10p` max timestep | 3.66566 V | 35.66 mV | — | — |
| `reltol=1e-5` | 3.66567 V | **35.67 mV** | 3.66567 V | **35.67 mV** |
| `reltol=1e-5` + `10p` max timestep | 3.66562 V | 35.62 mV | 3.66565 V | 35.65 mV |
| `reltol=1e-6` | 3.66565 V | 35.65 mV | 3.66565 V | 35.65 mV |

The same sweep at the band's *lower* endpoint corner
(`ff_-40c_vlogic3p63v-vdrv5p50v`): 3.65034 V (`reltol=1e-4`) → 3.65020 V
(`1e-5`) → 3.65017 V (`1e-6`), i.e. **20.34 → 20.17 mV**.

Three conclusions, none of which the range in decision record 0003 could
express:

1. **The measurement has converged, and it converged just outside 35 mV.**
   Everything from `reltol=1e-5` down agrees within 0.05 mV, at
   **35.65–35.67 mV**. The harness default is 0.34 mV *low* here, not high —
   the opposite sign to the `IN_DRV` case, where `reltol=1e-4` was 2.3 mV low
   of the converged value (decision record 0006's table). Convergence is much
   faster for this node than for `IN_DRV`, which is why the total movement
   since decision record 0003 is sub-millivolt rather than tens of
   millivolts.
2. **`XCCOMP` is neutral on Exception 1 — exactly neutral.** Compensated and
   uncompensated agree to ≤ 0.02 mV at every converged setting. Decision
   record 0014's reported 0.51 mV *improvement* from the stack, and this
   record's 0.51 mV apparent penalty in the opposite direction if one reads
   the same two runs the other way round, are both solver residue at
   `reltol=1e-4`, not physics. 0014's conclusion stands and is sharpened:
   adding the stack does not spend Exception 1 margin.
3. **A ±0.5 mV scatter band exists at the harness default** between DUT
   variants that converge to the same answer. Any restated *range* narrower
   than that scatter is a range that will move again on the next deck or
   netlist change without anything physical having happened.

## Decision

**Decision record 0003's Exception 1 is amended — quantification and bound
only — to cite this record's re-measured figures and to adopt an explicit
ceiling, following the shape decision records 0006 (Exception 3) and 0013
(Exception 2) established.**

`spec/gate-driver.md` §5's Exception 1 text is updated to state:

> **Exception 1** (decision record 0003, quantification amended and bounded
> by decision record 0015): the level shifter's pre-driver inverter's own
> output (`inb`, gate of thin-oxide `XMNPDB`, internal to the 3.3 V logic
> domain and never touching the drive rail) transiently overshoots its own
> `VDD_LOGIC` rail, **only** at the `vlogic3p63v` (+10 %) PVT corner (never
> at `vlogic2p97v`/`vlogic3p30v`) — **20.34–35.33 mV** across the 15
> affected process×temperature points at the harness's post-issue-#156
> `reltol=1e-4` default, worst case 3.66533 V at
> `ss_125c_vlogic3p63v-vdrv5p50v`,
> `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`; the
> two endpoint corners re-solved to convergence (`reltol` 1e-5/1e-6, 10 ps
> maximum timestep) give **20.17–35.67 mV**. **Bounded at ≤ 40 mV above the
> rail** (`inb` ≤ 3.670 V at the `vlogic3p63v` corner).

**Sizing the bound: ≤ 40 mV.** 4.33 mV of headroom above the converged worst
case (35.67 mV):

- ~13x the residual movement between the harness default and full
  convergence for this node (0.34 mV), and ~9x the ±0.5 mV cross-variant
  scatter the harness default shows at this corner — so the bound survives a
  further deck-fidelity change of the kind that made decision record 0003's
  figure stale, which is the entire reason it is being stated as a bound.
- Tighter in *relative* terms than either sibling bound, as the evidence
  supports: Exception 3 carries ~4x its converged excess (≤ 10 mV against
  −2.66 mV), Exception 2 ~1.2x (≤ 175 mV against −148.0 mV) with no
  convergence sweep behind it at all; this bound is 1.12x a number that
  *has* been swept to convergence at both band endpoints.
- Keeps decision record 0003's physical framing intact. The measured worst
  case is **0.98 %** of the 3.63 V rail — still the "≤ 1 %" gap 0003
  described — and the bound sits at 1.10 % of it. `inb` remains a node that
  never leaves the 3.3 V logic domain, and §2.3's 3.63 V thin-oxide ceiling
  is unchanged.

`design/level_shifter.sch`, `design/netlist/level_shifter.spice`, the
testbench and every existing `sim/` record are **unchanged** by this record.
The one new artifact is the full-grid evidence record above, which the
issue's own test plan required and which `sim/`'s append-only convention
mints rather than edits.

## Alternatives considered

- **Re-state the range only, with no bound (issue #193's Option 1)** —
  rejected. It fixes today's discrepancy and reproduces the failure mode
  next time the deck, the ngspice version, or the netlist moves by half a
  millivolt: a *point range* on a solver-resolution-limited transient is a
  number with no stated tolerance, and this is the second time in ten days
  that such a number has had to be re-litigated (Exception 2, decision
  record 0013, was the first). The range is still worth citing — it says
  what the circuit actually does across PVT — so this record states both,
  with the bound as the ratified obligation and the range as the current
  measurement.
- **State a bound only, dropping the measured range** — rejected. Decision
  record 0003's range is what makes Exception 1 auditable: it names the
  binding corner, shows the exception is confined to the +10 % logic-rail
  points, and lets a future reader see movement rather than merely
  compliance. Exception 3's bullet keeps both, and so does this one.
- **Bound at ≤ 36 mV, flush against the converged 35.67 mV** — rejected.
  0.33 mV of headroom is smaller than the ±0.5 mV cross-variant scatter this
  same corner shows at the harness's own default tolerance, so a legal
  re-run of an unchanged design could breach it. That is not a bound, it is
  the stale-figure problem restated with an extra decimal place.
- **Bound at ≤ 50 mV, matching the round-number habit of the sibling
  records** — rejected as loose without justification. Exception 2's wide
  ≤ 175 mV bound is explicitly sized for an exception whose binding corner
  has *never* been swept to convergence (decision record 0013's own
  reasoning). Exception 1 now has that sweep, at both band endpoints, so its
  bound should be sized against a converged number, not against the
  uncertainty of an unconverged one. A bound should be as tight as the
  evidence supports.
- **Rewrite decision record 0003's own text in place** — forbidden by
  `spec/decision-records/TEMPLATE.md` ("Do not delete or rewrite a ratified
  record — supersede it with a new one") and by the precedent of decision
  records 0006, 0007, 0013 and 0014, each of which amended a ratified
  predecessor additively. Decision record 0003's numbers remain correct *as
  measured at the tolerance it names*, which is exactly why an amendment,
  not a correction, is the right instrument.
- **Treat the >35 mV measurements as a regression and re-open mitigation
  (series resistor / decoupling cap / active clamp)** — rejected. Decision
  record 0003 investigated all three and found none closes a gap of this
  shape without a disproportionate cost; the gap has since moved by
  0.55 mV, which changes none of that analysis. The active-clamp follow-up
  0003 left open stays open on the same terms.
- **Relax §2.3's 3.63 V thin-oxide ceiling, or invoke the PDK's duty-cycle
  TDDB overshoot allowance** — explicitly forbidden by `CLAUDE.md` and
  declined by every record in this family (0003, 0005, 0006, 0007, 0013);
  not considered further.

## Consequences

- `spec/gate-driver.md` §5's Exception 1 text now cites **20.34–35.33 mV**
  at the harness default (worst case 3.66533 V at
  `ss_125c_vlogic3p63v-vdrv5p50v`), **20.17–35.67 mV** converged, the
  evidence record `20260818-071216-5260603`, and an explicit **≤ 40 mV**
  bound. §2.3's 3.63 V ceiling is unchanged and no PDK allowance is invoked.
- **All three of §5's documented exceptions now carry an explicit numeric
  bound** — Exception 3 since decision record 0006/0007 (≤ 10 mV),
  Exception 2 since decision record 0013 (≤ 175 mV), Exception 1 since this
  record (≤ 40 mV). Decision record 0013's closing observation that
  Exception 1 "remains characterized only by its measured 20–35 mV band" is
  superseded by this record; the rest of 0013 is untouched.
- **Decision record 0014's `XCCOMP`-is-favourable-on-Exception-1 claim is
  sharpened to `XCCOMP`-is-neutral.** The measured difference between the
  compensated and uncompensated circuits at this node is ≤ 0.02 mV once the
  transient is resolved. Nothing in 0014's decision depends on the sign of a
  0.5 mV artifact, so 0014 is not otherwise disturbed — but a future record
  should not cite that 0.51 mV as a benefit of the stack.
- **A reusable lesson about the harness's own default.** For `IN_DRV`
  (decision record 0006) `reltol=1e-4` sat ~2.3 mV *below* the converged
  peak; for `inb` it sits 0.34 mV below at one end of the band and 0.17 mV
  *above* at the other. The default is close, but it is not converged, and
  its error is not even single-signed across nodes. Any *bound* stated from
  a single harness-default run should carry headroom for that; any *range*
  stated from one should say what tolerance produced it, which is what
  `sim/README.md`'s Environment block already records and what decision
  record 0003 predates.
- **Exception 2's bound is the remaining unswept one.** Decision record 0013
  sized ≤ 175 mV explicitly because no targeted convergence sweep existed
  for `n1`. This record demonstrates such a sweep is cheap (six single-corner
  runs, seconds each) — running it for `n1` and tightening 0013's bound
  against a converged number is a reasonable follow-up, and would leave all
  three exceptions bounded against converged evidence.
- No design file, testbench, or prior evidence record changes. One new
  evidence record is added under `sim/level-shifter-oxide-safety/records/`.
