# 0016: Output-stage 6 V stretch sink current — documented, bounded exception at two hot/slow corners

- **Status**: Ratified
- **Date**: 2026-08-19
- **Decided by**: Builder agent, issue #139
- **Supersedes**: none. **Extends** `spec/gate-driver.md` §3 (peak source/sink
  current target). Does not reopen or amend decision records 0004–0006/0013
  (§2.3 gate-ceiling exceptions) or 0007/0014/0015 (`XCCOMP`) — this record
  covers a different §3 acceptance criterion (drive-strength current, not
  gate-oxide margin) on the same cell.

## Context

Issue #125 fixed the sim harness so each PVT point is judged against its own
corner-scoped `checks` bound — the 6 V `vdrv` rail against spec §3's
**stretch** targets, not the nominal ±10 % ones it was previously (and
incorrectly) judged against. Re-recording the output-stage-drive evidence
under the fixed harness surfaced a pre-existing shortfall that the old,
single-bound harness could not express: 2 of the 15 stretch-rail points fail
the ≥ 1 A peak **sink** current target.

| Corner | `ipeak_sink_a` | Stretch target | Shortfall |
|---|---|---|---|
| `ss_125c_vdrv6p00v` | 0.875334 A | 1.0 A | −12.5 % |
| `sf_125c_vdrv6p00v` | 0.935921 A | 1.0 A | −6.4 % |

Evidence: `sim/output-stage-drive/records/20260817-110340-54fdbf8.md` (60
points, 58 PASS / 2 FAIL; supersedes `20260812-064304-03699ea`, which the
old harness bound had scored PASS despite reporting the same underlying
numbers — only the verdict changed, per that record's own note).

**Independently corroborated three ways**, all pointing at the same two
corners and a consistent magnitude — this is a real, repeatable design
result, not measurement noise or an artifact of one testbench:

1. **End-to-end, schematic, with the real level shifter in the loop**:
   `sim/gate-driver-core-drive/records/20260817-013400-ae66957.md` (merged
   via PR #135) measures `ss_125c_vlogic3p30v-vdrv6p00v` sink = 0.882673 A
   and `sf_125c_vlogic3p30v-vdrv6p00v` sink = 0.931667 A — within ~1 % of
   the output-stage-only numbers above, confirming the level shifter
   contributes negligible additional loading ahead of the output stage's
   own final push-pull stage (that record's own Finding 1).
2. **Post-layout, extracted, DRC/LVS-clean netlist**: every record under
   `sim/gate-driver-core-drive-postlayout/records/` (six records,
   2026-08-17 through 2026-08-18, spanning the `XCCOMP` MiM stack and the
   subsequent post-#166 extraction) reports the same two corners failing,
   in a tight, stable range — `ss_125c…` sink 0.880–0.883 A,
   `sf_125c…` sink 0.923–0.932 A. The extracted, real-parasitic layout does
   not materially move this result in either direction relative to the
   schematic figures above.
3. **Sizing derivation never targeted this point**: `design/output-stage-sizing.md`
   §1.3 explicitly derives the final-stage device widths against the
   **nominal ±10 % range's** worst-case current density
   (`ss`/125 °C/4.5 V, ≥ 0.5 A target) and states the 6 V stretch point "is
   checked separately in §4, not used to relax nominal sizing" — but §4 only
   ever checks the stretch rail's §2.3 gate-ceiling bound, not the §3
   stretch *current* target. The stretch current target was never an input
   to the final-stage sizing derivation at all; the 12.5 % shortfall this
   record documents is the direct, expected consequence of that gap, not a
   surprise.

**Scope of the shortfall** (per `design/output-stage-sizing.md` §6 and the
records above):

- **Sink only.** Peak source current clears 1 A at every stretch point in
  every evidence source (worst-case source figures are 1.01–1.40 A across
  the schematic and post-layout records).
- **Slowest-NMOS corners, hottest temperature only.** `ss` and `sf` share a
  slow-NMOS skew; only their 125 °C point fails. `tt`/`ff`/`fs` clear 1 A at
  every temperature on the 6 V rail, and `ss`/`sf` clear it at −40 °C/27 °C.
  Consistent with the pull-down NMOS being the binding device at its
  lowest-mobility corner.
- **Nominal targets are unaffected.** Every one of the 45 points on the
  4.5/5.0/5.5 V nominal-tolerance rail passes the §3 nominal ≥ 0.5 A / < 50 ns
  bounds at every evidence source above; worst nominal-rail sink current is
  0.573742 A (`ss_125c_vdrv4p50v`, `sim/output-stage-drive/records/20260817-110340-54fdbf8.md`).
- **Delay is unaffected.** The stretch-rail propagation-delay target
  (< 25 ns) has wide margin at every point (worst 5.88 ns) — this is
  specifically a drive-strength finding, not a speed finding.

## Why a design change (sizing the final NMOS up) is not undertaken here

Per `CLAUDE.md`, agents do not relax the ratified spec to make results
pass — the only two remaining paths are fix the design or formally accept
and document the shortfall as an exception. Issue #139 explicitly rejected
loosening the harness's stretch-corner check back to 0.5 A as "exactly the
masking issue #125 removed," and this record does not do that (the harness
`checks` bound stays at ≥ 1 A for the stretch rail; no evidence record's
FAIL verdict is altered).

**Sizing up the final-stage pull-down NMOS (`MN6`) is disproportionate right
now, for reasons distinct from — and in some respects stronger than — the
disproportionality argument decision record 0005 already made for the
§2.3 gate-ceiling exception on this same cell:**

1. **The design this shortfall is measured against already has real,
   DRC/LVS-clean layout.** Unlike decision record 0005 (issue #24, no
   layout existed yet for this cell), `layout/gate_driver_core.gds` now
   contains a full, extracted realization of this exact schematic, verified
   through the `XCCOMP` MiM-stack rework (PR #196) and the post-#166
   extraction re-record (PR #202). Widening `MN6` (and, per the taper's
   `f≈4` geometric derivation in `design/output-stage-sizing.md` §3,
   necessarily re-deriving stage 5 and likely stage 4's widths to keep the
   taper ratio sane) is not a schematic-only edit — it invalidates the
   drawn layout, its DRC/LVS signoff, and every post-layout PVT record
   currently on file (`sim/gate-driver-core-drive-postlayout/`, six
   records), not just the two `sim/` harnesses issue #139 itself names.
2. **The margin needed is small relative to the redesign it would force.**
   Closing a 6.4–12.5 % current gap by widening the pull-down NMOS changes
   the load `MN5` (stage 5) drives and shifts the taper's `Wp/Wn` ratio and
   Miller-coupling behavior at exactly the node (`n5`) already carrying the
   largest of the three ratified §2.3 gate-ceiling exceptions on this cell
   (decision record 0005, bounded at ≤ 175 mV above the ceiling by decision
   record 0013). A wider final NMOS plausibly increases — not decreases —
   the gate-capacitance/Miller-coupling excursion that bound already covers;
   re-deriving the sizing here without re-verifying that interaction risks
   silently breaking an already-ratified, already-bounded exception on the
   same node, which is exactly the "worse, half-verified state" this
   record's own instructions warn against taking on in one pass.
3. **The re-verification surface is broader than the two records issue #139
   names.** A sizing change forces a fresh full-PVT re-run of not just
   `sim/output-stage-drive/` and `sim/gate-driver-core-drive/` (both named
   in the issue) but also `sim/gate-driver-core-drive-postlayout/` (six
   existing records, all now stale against a re-sized device) and a full
   layout redraw + DRC/LVS re-signoff — a multi-PR body of work, not a
   single-pass Builder scope, and one that risks leaving some of those
   evidence trails re-verified and others not if attempted in one PR.

**The shortfall itself is small and tightly scoped**, the same shape decision
record 0005 already accepted for a different §3/§5 acceptance criterion on
this identical cell: consistent across three independent measurement
methods (isolated schematic, end-to-end schematic, extracted post-layout),
confined to exactly 2 of 15 stretch-rail points (both at the hottest,
slowest-NMOS corners), and absent everywhere on the nominal ±10 % rail this
block's actual target operating range covers.

## Decision

**§3's peak sink-current stretch target is narrowed with a third documented,
bounded exception, following the same shape as decision records
0003/0005/0006's exceptions to §5** — not folded into the general claim and
not achieved by loosening the harness bound.

`spec/gate-driver.md` §3 gains a note alongside its drive-strength table:

- The ≥ 0.5 A nominal peak source/sink current target is met at every PVT
  point on the nominal ±10 % rail (verified, decision record 0004 /
  `design/output-stage-sizing.md` §6).
- The ≥ 1 A stretch peak *source* current target is met at every PVT point
  on the 6 V stretch rail (verified).
- **New**: the ≥ 1 A stretch peak *sink* current target is **not met** at
  the two hottest, slowest-NMOS-skew corners of the 6 V stretch rail —
  `ss_125c_vdrv6p00v` (0.875334 A, −12.5 %) and `sf_125c_vdrv6p00v`
  (0.935921 A, −6.4 %) — confirmed across the isolated output-stage,
  end-to-end, and extracted post-layout evidence trails cited above. All
  other 13 of 15 stretch-rail points clear 1 A. **Bounded at ≥ 0.85 A** at
  these two corners specifically (the tightest post-layout measurement,
  0.880232 A, sits inside this bound with ~3.5 % headroom; the schematic
  worst case, 0.875334 A, sits inside it with ~3 % headroom) — any future
  re-run landing below 0.85 A at either corner is a new finding requiring
  its own investigation, not silently covered by this exception.

`design/output_stage.sch`, `design/netlist/output_stage.spice`,
`layout/gate_driver_core.gds`, and every currently-recorded evidence file
under `sim/output-stage-drive/`, `sim/gate-driver-core-drive/`, and
`sim/gate-driver-core-drive-postlayout/` are **unchanged** by this record.
No new `sim/` evidence record is required — the FAIL verdicts already on
file for these two corners stand as the exception's evidence, exactly as
decision record 0005 required no new evidence record for its own exception.

## Alternatives considered

- **Size up the final-stage pull-down NMOS and re-taper the pre-driver
  (issue #139's option 1)** — considered in detail above; rejected for now.
  Disproportionate given already-drawn, DRC/LVS-clean layout and six
  post-layout evidence records that would all go stale, and risks
  interacting badly with the already-ratified, already-bounded §2.3
  gate-ceiling exception on the very node (`n5`) a wider final stage would
  most affect. Not ruled out permanently — see "Consequences" below for
  what a future revision doing this would need to redo.
- **Qualify §3's stretch column to apply only at nominal-process/room-temperature
  (issue #139's option 2)** — rejected. Every other §3 number (including
  the nominal ≥ 0.5 A target this exact cell was sized against,
  `design/output-stage-sizing.md` §1.3) has always been read and verified
  across the **full** PVT matrix, not a single corner; carving out an
  ad hoc process/temperature exemption specifically for the one number that
  currently fails, with no independent physical justification for why
  *this* target alone should be corner-exempt, would be indistinguishable
  from loosening the spec to match the result — the exact anti-pattern
  issue #139 rules out for the harness bound, applied instead to the spec
  text.
- **Treat the shortfall as within simulation noise and pass anyway** —
  rejected: consistent across three independent measurement methods
  (isolated, end-to-end, post-layout extraction) and confined to exactly
  the two corners a slow-NMOS, high-temperature skew predicts, the
  signature of a real, repeatable device-current-density result, not noise.
- **Relax the 1 A stretch target itself, or the harness's stretch-corner
  bound** — explicitly forbidden by issue #139's own instruction and
  `CLAUDE.md` ("agents do not relax the ratified spec to make results
  pass"); not considered further.

## Consequences

- `spec/gate-driver.md` §3 gains a third documented, bounded exception,
  alongside decision records 0003/0005/0006's exceptions to §5. The ≥ 1 A
  stretch sink-current number itself is unchanged for the other 13 of 15
  stretch points; the harness's per-corner `checks` bound (issue #125) is
  unchanged and continues to report these two corners FAIL.
- `sim/output-stage-drive/`, `sim/gate-driver-core-drive/`, and
  `sim/gate-driver-core-drive-postlayout/` all continue to report FAIL
  overall for any record that includes these two corners — this is
  intentional and expected going forward; a reviewer reading a FAIL verdict
  on one of these harnesses should check this record before treating it as
  a regression.
- **This is the fourth documented, bounded exception this cell (or the
  chain it sits in) now carries**, and the first against a §3
  drive-strength target rather than a §2.3/§5 gate-oxide-safety claim. A
  future revision of this cell that widens the final-stage NMOS to close
  this gap must re-verify, in the same pass: `sim/output-stage-drive/`
  (full 60-point grid), `sim/gate-driver-core-drive/` (full grid),
  `sim/gate-driver-core-drive-postlayout/` (full grid, after a layout
  redraw and fresh DRC/LVS/extraction), and explicitly re-check the §2.3
  gate-ceiling exception at `n5` (decision records 0005/0013) for
  regression, since a wider final NMOS is the device most directly coupled
  to that node's Miller-coupling excursion. That is new design work
  requiring its own decision record, not a silent edit to this one.
- If a future half-bridge revision (per `spec/gate-driver.md` §1) reuses
  this output-stage topology, it should budget final-stage NMOS width
  against the stretch-rail current target from the outset (i.e. fold the
  6 V stretch point into `design/output-stage-sizing.md` §1.3's sizing
  basis, not just its §4 gate-ceiling check), rather than discover this
  same gap again after the fact.
