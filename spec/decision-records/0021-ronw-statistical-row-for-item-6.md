# 0021: `Ron·W` is a statistical row for T1 item 6, graded against a 5 %-of-window excursion bound

- **Status**: Ratified 2026-10-29 by the operator (Robb, attended fleet:decide q133, option 1 of #379: as drafted)
- **Date**: 2026-10-28
- **Decided by**: operator (Robb), ratifying the Builder draft from issue #379 (tracker #370)
- **Extends**: `spec/low-side-power-switch.md` §2.1, §2.2. **Supersedes**: none.
  Does not edit §2.1 or §2.2; no ratified value changes.

## Context

T1 item 6 requires every statistical spec row to carry `klt yield` evidence
graded against a bound. Three rows are `met` (#368). The fourth,
`ronw_nfet_06v0`, is a declared gap in `verification/signoff/manifest.json`
(rendered in `tier-report.json`): the `Ron·W` campaign is a spread
measurement with no ratified per-row bound. §2.1's worst figure
(4.5719 Ω·mm at `Vgs` = 3.6 V, `ss`/125 °C) is one deterministic sample, not a
limit; roughly half of all draws at that corner exceed it by construction, so
it cannot serve as the bound. Settling this is a spec decision, which an
agent cannot ratify.

Evidence (committed, nothing re-simulated):
`sim/low-side-power-switch-ronw-mismatch/records/20260821-134653-804155b.md`,
15 PVT points x 200 draws, 3000/3000 converged, deterministic control bit-exact;
per-draw data in
`sim/low-side-power-switch-ronw-mismatch/corners/20260821-134653-804155b/samples-*.csv`.

## Decision

**Proposed**: `Ron·W` of `nfet_06v0` is a statistical row (local mismatch is
a matching effect). For the worst design row (`Vgs` = 3.6 V, the row §2.2
sizes from), at every PVT point separately (never pooled):

- bound: `Ron·W` of a mismatch draw ≤ that PVT point's own deterministic
  control + 5 % of the §2.1 window width, i.e. + 0.13432 Ω·mm
  (5 % x (4.5719 − 1.8855)); the 5 % is the materiality threshold the sim
  record already uses. Against §2.2's reference 0.10 Ω budget (W ≈ 45.7 mm)
  that is at most +2.9 mΩ on the channel.
- target yield: ≥ 0.98 at 95 % confidence. N = 200 draws per point with zero
  failures gives a two-sided Clopper-Pearson low end of 0.9817, so 0.98 is
  the highest round target the existing campaign supports; a higher target
  needs a larger campaign (0.99 needs N ≥ 368), which this record does not
  request.
- `klt yield` cites the 15 per-PVT populations of `ronw_n06_3.6`, one limit
  each (`max` = control + 0.13432).

Result against the committed samples: 0 failures in all 3000 draws; the worst
excursion is 28.078 mΩ·mm (`ss_125c`), 20.9 % of the allowed 134.320 mΩ·mm.
Reproduce with `python3 -I verification/signoff/derive_ronw_bound.py`
(add `--emit-samples OUT.json` for a `klt yield` sample-set). The script's
per-PVT σ and excursions match the sim record's table.

On ratification, the follow-up pass updates `spec_rows."6"` to a graded
`klt yield` citation and re-renders `tier-report.json`.

## Alternatives considered

- **`Ron·W` is not a statistical claim; item 6 drops the row** (§2.1 is a
  nominal design rule with a stated 3:1 window). Not chosen: the grader
  treats a `not_applicable` entry as contradicting a declared row set, and
  the tier text calls any matching row statistical. If the operator prefers
  it, the record must cite a committed statement that accounts for every
  row, and the sim record's own finding (window set by corner and bias skew,
  not mismatch) is the supporting evidence.
- **Grade against 4.5719 Ω·mm as the limit.** Rejected: a single
  deterministic sample, not an independently set margin.
- **A grid-wide absolute bound (e.g. 1.05 x 4.5719 = 4.8005 Ω·mm).** Passes
  trivially at the 14 non-worst PVT points, so it grades the corner window
  and not mismatch.
- **Yield target 0.99 or higher.** Not supported by N = 200 per point.

## Consequences

- If ratified, item 6 can grade `met` with four graded rows; the open gap in
  `verification/signoff/README.md` closes.
- The 5 % threshold and 0.98 target become spec-level numbers; tightening
  either needs a new record, and a higher target needs a larger campaign.
- The bound is on mismatch excursion, not on absolute `Ron·W`; it says
  nothing about the 3:1 corner window, which §2.1 already states.
- Inherits decision record 0017's limit: the PDK models `nfet_06v0`
  threshold mismatch only (no β mismatch), so the evidence does not cover
  β spread.
- `klt yield` was not run for this draft (the native extension is not
  installed on this host); the sample-size statement above is the
  Clopper-Pearson arithmetic and should be confirmed with `klt yield` at
  ratification.
- Until ratified, item 6 stays `partial_coverage`.
