# 0004: Output-stage gate-ceiling verification result — §2.3 fails at the 6 V stretch rail

- **Status**: Ratified
- **Date**: 2026-08-12
- **Decided by**: Doctor agent, issue #6 / PR #23

## Context

Issue #6 required a full-PVT transient testbench for
`design/output_stage.sch` (the low-side gate-driver output stage) to
substantiate its drive-strength targets and to report the worst-case
thick-oxide gate-node voltage against `spec/gate-driver.md` §2.3's 6.0 V DC
ceiling, with a positive margin as an explicit, pass/fail acceptance
criterion.

`design/output-stage-sizing.md` §4 pre-registered an analytical
convex-hull bound before any simulation ran: because this cell has no
cascode or clamp, no node can exceed the convex hull of its driving
sources, so worst-case `|Vgs|` is bounded above by exactly `VDD_DRV` — at
the 6 V stretch rail, exactly 6.0 V, zero (not positive) margin. §4
anticipated that this shortfall, if confirmed by simulation, would not be
resolved by resizing (the bound is topological, not a function of device
width) and would need to be recorded and referred to a decision record.

`sim/output-stage-drive/` (testbench, DUT netlist, `tb.json`) already
existed from issue #6's Builder pass, but the harness had not actually been
run — no `corners/`, `netlist-snapshots/`, or `records/` existed, and
`design/output-stage-sizing.md` §6 was an unfilled placeholder. A Judge
review of PR #23 ran `python3 sim/run_corners.py output-stage-drive` ad hoc
to check the PR's substance, found a stronger-than-anticipated result
(measured overshoot, not exact equality), and requested the harness be run
and its evidence committed. This record captures that run's actual output:
[`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../../sim/output-stage-drive/records/20260812-064304-03699ea.md)
(60/60 PVT points, 5 process corners × 3 temperatures × 4 tied-supply
points including the 6 V stretch rail).

## Decision

**The record's answer is a qualified fail, not a clean pass — measured
overshoot, not §4's predicted zero-margin equality.** Two claims separate
cleanly in the evidence:

1. **Drive strength (§3) and this cell's own propagation-delay allocation
   (§5) are met at every PVT point**, including the 6 V stretch rail: peak
   source/sink current ≥ 0.5 A (worst case 0.5877 A / 0.5737 A at
   `ss_125c_vdrv4p50v`), 10–90 % rise/fall well under 50 ns (worst case
   8.36 ns / 7.53 ns, same corner), and `tpdlh`/`tpdhl` inside this cell's
   20 ns nominal / 10 ns stretch allocation at every point.
2. **The §2.3 gate-ceiling acceptance criterion (positive margin) fails, at
   every one of the 15 PVT points on the 6 V stretch rail** (all 5 process
   corners × all 3 temperatures — a consistent, corner-tracking pattern,
   not simulation noise). At least one internal taper node (`n1`…`n5`)
   transiently exceeds 6.0 V at each of those 15 points; the global worst
   case is `n5` = 6.0538 V at `ss_27c_vdrv6p00v` (margin **−53.8 mV**),
   close behind by `n4` = 6.0526 V at `ss_125c_vdrv6p00v` (**−52.6 mV**). No
   node exceeds 6.0 V at any of the 4.5/5.0/5.5 V nominal-tolerance points —
   the excursion is confined to the 6 V stretch corners, matching §4's own
   explanation (a gate-capacitance/Miller-coupling transient riding on top
   of the quasi-static convex-hull bound, not a sizing defect fixable by
   choosing different widths). This is the same excursion shape already
   ratified for a different cell in
   [decision record 0002](0002-level-shifter-oxide-safety-result.md) /
   [0003](0003-predriver-inverter-oxide-margin-exception.md) (the level
   shifter's pre-driver inverter overshooting its own rail by 20–35 mV at
   its own +10 % corner) — a non-cascoded node driven at its own rail's
   upper bound transiently exceeding that bound by tens of millivolts is,
   on this repo's now-twice-observed evidence, characteristic of any
   thick-/thin-oxide push-pull stage in this PDK, not particular to either
   cell's sizing.

**No change to `spec/gate-driver.md`.** Per issue #6's explicit instruction
("If a §3 target proves unreachable, do not relax it — record the shortfall
in the sim record and open a decision-record issue instead") and this
repo's own rule (`CLAUDE.md`: "agents do not relax the ratified spec to
make results pass"), the 6.0 V ceiling is not changed and the finding is
not waved through. The decision of *how* to close the gap — add a
clamp/cascode to this cell's final stage (a design change, unverified and
out of this record's scope) or formally narrow §2.3's claim for this
specific device flavor at its native characterization bias (the resolution
decision record 0003 made for the analogous level-shifter finding) — is
deferred to a follow-up issue, not decided here, mirroring how decision
record 0002 deferred its own analogous choice to issue #13.

## Alternatives considered

- **Treat the excursion as within simulation noise and pass anyway** —
  rejected. The excursion appears at all 15 of the 6 V-stretch points
  (every process × temperature combination) and at none of the 45 points
  at lower rails — the same "consistent across every affected corner, absent
  everywhere else" signature decision record 0002 already used to rule out
  noise for the analogous level-shifter finding.
- **Resize the final stage or taper to eliminate the overshoot** — not
  attempted in this record. §4's own analysis already establishes the bound
  is topological (a function of the rail-to-rail, non-cascoded topology,
  not device width), so a resizing pass would not be expected to close a
  Miller-coupling-driven transient; investigating an active mitigation
  (clamp/cascode) is left to the follow-up issue, matching how decision
  record 0003 investigated (and rejected) passive mitigations before
  choosing to narrow the claim for the level-shifter case.
- **Relax the 6.0 V ceiling itself, or invoke the PDK's duty-cycle TDDB
  overshoot allowance to wave the finding through** — explicitly rejected,
  per issue #6's own acceptance criteria and `CLAUDE.md`'s rule against
  relaxing the ratified spec to make results pass.

## Consequences

- `sim/output-stage-drive/corners/20260812-064304-03699ea/`,
  `sim/output-stage-drive/netlist-snapshots/20260812-064304-03699ea.spice`,
  and `sim/output-stage-drive/records/20260812-064304-03699ea.md` land as
  the append-only evidence for issue #6, alongside a filled-in
  `design/output-stage-sizing.md` §6.
- Issue #6's acceptance criterion "worst-case thick-oxide gate-node voltage
  ... is reported with its margin ... and the margin is positive" is
  **not met**, as recorded here. `design/output_stage.sch` otherwise meets
  every other deliverable and acceptance criterion in issue #6 (drive
  strength, propagation delay, device flavor, cross-conduction/energy
  reporting).
- `spec/gate-driver.md` §2.3's 6.0 V ceiling is unchanged and the block's
  overvoltage-protection claim (§5, already carrying one documented
  exception from decision record 0003) needs a second, similarly-scoped
  exception or a design mitigation — tracked in a follow-up issue, not
  resolved here.
