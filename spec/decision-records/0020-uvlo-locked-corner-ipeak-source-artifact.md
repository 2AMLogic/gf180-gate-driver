# 0020: `ss_-40c_vlogic2p97v-vdrv4p50v` nominal `ipeak_source_a` miss — a locked-corner measurement artifact of decision record 0018's already-open false-trip finding, not a new drive-strength defect

- **Status**: Ratified
- **Date**: 2026-08-26
- **Decided by**: Builder agent, issue #226
- **Extends**: `spec/gate-driver.md` §3 (peak source/sink current target),
  alongside decision record 0016's exception on the same table. **Does not
  reopen or amend** decision record 0018 (UVLO comparator PVT measurement) —
  this record explains an additional *consequence* of decision record 0018's
  already-open Finding 2 (false-trip lockout at `ss_-40c`/`sf_-40c` at the
  `vdrv4p50v` low-line corner), it does not re-derive or narrow that finding.
  Does not reopen decision record 0016 (a different corner set, a different
  rail, a different current direction).

## Context

Issue #222's post-layout PVT re-verification (decision record 0019 Finding
5) found `ipeak_source_a` — spec §3's nominal ≥ 0.5 A peak source-current
target — falling just short at exactly one nominal ±10 % corner,
`ss_-40c_vlogic2p97v-vdrv4p50v`, across every facet measured:

| Facet | `ipeak_source_a` (A) | Record |
|---|---|---|
| Schematic, with UVLO (issue #220) | 0.499165 | `sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md` |
| Post-layout, extracted, no RC (issue #222) | 0.499696 | `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md` |
| Post-layout, extracted, RC parasitics (issue #222) | 0.475414 | `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md` |

Issue #226 was filed to determine why, and to pick one of: (1) re-size
`uvlo` so this corner's trip point moves away from `vdrv4p50v`; (2) a new
bounded exception; (3) amend §3's now-stale "every point... clears" prose.

## Finding — this corner is already fully locked out, exactly as decision record 0018 Finding 2 documented; the sub-0.5 A reading is a transient contention-current artifact of that lockout, not a weakened drive attempt

`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`
(and the two other facets above) log, at this exact corner:

- `uvlo_lockout_at_in_high` = 4.5 V ≈ `VDD_DRV` — `x3.lockout` is fully
  asserted (comparator says "locked") throughout `IN`'s high pulse.
- `vout_max_v` = 0.2445 V (post-layout, RC facet; 0.2412–0.2414 V at the
  other two facets) — `OUT` **never rises above a quarter of a volt** at
  any point in the simulated transient. This is not a block that attempts
  to drive the 1 nF load and comes up short; it is a block that, per its
  own (out-of-spec) comparator trip point, correctly stays locked the
  entire time `IN` is high, exactly as decision record 0018 Finding 2 says
  it will at this corner (`ss_-40c`'s measured falling/rising thresholds,
  4.737 V/5.115 V, both sit above the 4.50 V rail this corner is biased
  at).
- `tb.json`'s own `ipeak_source_a` check description already anticipates
  this case: *"a locked corner sources no peak current by design."* The
  measured 0.475414–0.499696 A here is not that zero — it is `i(vimeas)`'s
  peak value over the ~1 ns window in which the output stage's own driver
  very briefly contests the already-engaged UVLO pulldown (`MPD`,
  `nfet_06v0` W=10 µm **m=800**, effective 8000 µm, sized in
  `design/uvlo-comparator-sizing.md` specifically to dominate the output
  stage's own strongest device) before losing — a `dV/dt` artifact of a
  ~0.24 V blip on the 1 nF load capacitance (`trise10_90` at this corner is
  0.58–0.82 ns, two orders of magnitude faster than the 20 ns edge spec §3's
  own drive-strength target is derived against), not a sustained
  charge-delivery result.

**Directly confirmed by the immediately adjacent corner decision record
0018 Finding 2 also flags as locked at this same operating point**:
`sf_-40c_vlogic2p97v-vdrv4p50v` is *also* measured with
`uvlo_lockout_at_in_high` ≈ 4.5 V and `vout_max_v` ≈ 0.33–0.34 V — also
fully locked, same mechanism — yet its own contention-spike magnitude
(0.666–0.694 A across the three facets) clears the 0.5 A floor. Two corners
sharing the identical false-trip lockout condition produce contention
spikes that straddle the 0.5 A line in opposite directions (`ss_-40c`
below, `sf_-40c` above), driven by their differing process-corner speed —
this is the signature of the two corners measuring the same
functionally-irrelevant transient artifact at slightly different
magnitudes, not two independent drive-strength results.

**Root-cause hypothesis in issue #226 is confirmed, with a refinement**:
the issue's own hypothesis ("`uvlo`'s comparator loading `OUT` near its
lockout boundary… weakens drive strength") correctly identifies the
mechanism's origin (the UVLO pulldown) but understates it — this is not
partial loading that shaves margin off an otherwise-successful drive
attempt; `vout_max_v` ≈ 0.24 V shows the block is **already fully locked**
at this corner (an unambiguous DC operating point: this corner's own
measured falling threshold, 4.737 V, exceeds the 4.50 V bias, so no
hysteresis ambiguity is even in play), and the near-0.5 A reading is the
locked pulldown's own contention transient, exactly the case `tb.json`
already documents as expected to read "no peak current."

## Why option (1) — re-size `uvlo` to move this corner's trip point — is not undertaken here

Fixing this corner's `ipeak_source_a` reading in any way that reflects a
*genuinely working* drive attempt (rather than a smaller or larger version
of the same locked-corner contention artifact) requires this corner to stop
being falsely locked at `vdrv4p50v` in the first place — i.e. it requires
closing decision record 0018 Finding 2, not tuning a separate parameter.
Decision record 0018 already evaluated exactly this class of fix and
declined it in the same issue that produced the finding:

- Finding 2's cause (decision record 0018 Finding 1) is the ~5× divider
  gain amplifying the diode-connected `Vt` reference's own process *and*
  temperature spread — a resistor-ratio tweak moves **every** corner's
  trip point together (widening some margins while narrowing others), not
  just `ss_-40c`'s. Decision record 0018 itself flags `sf_-40c` as the
  other corner sitting closest to the boundary; this record's own evidence
  above shows `sf_-40c` is *also* already locked at this exact corner
  today, just with a contention spike that happens to still clear 0.5 A —
  a naive re-tune aimed at un-locking `ss_-40c` has no guarantee of not
  pushing `sf_-40c` (or a third corner) into the same or a worse failure,
  exactly the "reopening decision record 0018's wider PVT-spread finding"
  risk issue #226 itself flags.
- Decision record 0018's own "Why no design fix is undertaken here" section
  states plainly that closing Finding 2 "requires reducing the divider's
  amplification of the reference's own PVT spread — e.g. a multi-diode
  reference stack… or an actual bandgap… a materially different circuit
  from decision record 0001 Decision 5's specified topology… and would need
  their own PVT re-verification pass" — explicitly deferred as "a new issue
  with its own decision record, not folded silently into this one."
  Issue #226's shortfall is that exact deferred work resurfacing in a
  different spec metric (§3 drive current instead of §5 protection scope),
  not an independent problem with an independent, narrower fix available.
- A resistor-only tweak that nudges `ss_-40c`'s contention spike from
  0.475–0.499 A up over 0.5 A **without** closing the underlying false-trip
  lockout would not produce a working drive-strength result at this corner
  either — `OUT` would still never leave its ~0.24 V floor while `IN` is
  high, and the block would still fail the false-trip safety finding
  decision record 0018 already opened. That would be tuning the artifact,
  not fixing the defect — worse than the status quo, since it would read as
  a resolved §3 metric while leaving the real (already-documented, already
  more consequential) §5 safety finding untouched.

This is a strictly narrower, better-evidenced restatement of decision
record 0016's own reasoning for declining a design fix on this same cell
family: the redesign needed is real, but it is a multi-PR reference-topology
change with its own full-PVT re-verification obligation, not a single-pass
Builder-scope sizing edit.

## Decision

**§3's ≥ 0.5 A nominal peak *source* current target is narrowed with a
fourth documented, bounded exception, following the same shape as decision
record 0016's third exception** — not folded into the general claim, not
achieved by loosening the harness bound, and not resolved by resizing
`uvlo` (see above).

`spec/gate-driver.md` §3 gains a note alongside decision record 0016's
existing exception:

- **New**: the ≥ 0.5 A nominal peak *source* current target is **not met**
  at exactly one nominal ±10 % corner — `ss_-40c_vlogic2p97v-vdrv4p50v` —
  once `uvlo` (issue #220) is instantiated. Measured 0.475414–0.499696 A
  depending on facet (schematic / post-layout no-RC / post-layout with RC;
  worst case is the RC-extracted facet). This is **not** an independent
  drive-strength weakness: at this corner the block is already fully locked
  out (`vout_max_v` ≈ 0.24 V, `uvlo_lockout_at_in_high` ≈ `VDD_DRV`) per
  decision record 0018 Finding 2's already-open false-trip finding, and the
  measured current is a sub-nanosecond contention-current artifact between
  the output driver and the engaged UVLO pulldown, not a sustained
  charge-delivery result — see Finding above. **Bounded at ≥ 0.45 A** at
  this corner specifically (the tightest measurement, 0.475414 A, sits
  inside this bound with ~5.6 % headroom) — any future re-run landing below
  0.45 A at this corner, or a locked-corner miss appearing at any *other*
  nominal ±10 % corner, is a new finding requiring its own investigation,
  not silently covered by this exception.
- All other nominal ±10 % points, and every point of the 6 V stretch rail
  aside from decision record 0016's existing sink-current exception, clear
  their respective §3 targets with `uvlo` instantiated.
- §3's descriptive claim that "every point of the nominal ±10 % matrix
  clear[s] their respective targets" is corrected: it now reads (with
  `uvlo` instantiated) as clearing at every point **except** the one
  bounded exception this record documents.
- This exception's closure is coupled to decision record 0018 Finding 2's
  closure, not addressable independently: a future reference-topology
  revision that closes the false-trip lockout at `ss_-40c`/`sf_-40c` (per
  decision record 0018's own "Consequences" obligations) must re-verify
  `sim/gate-driver-core-drive-with-uvlo/` and
  `sim/gate-driver-core-drive-with-uvlo-postlayout/` in the same pass and
  should expect this exception to become moot (a released corner sourcing
  its full ~0.83 A pre-UVLO baseline, per the pre-UVLO schematic record
  `sim/gate-driver-core-drive/records/20260821-113949-d2ba4d8.md`) rather
  than separately re-tuned.

`design/uvlo.sch`, `design/netlist/uvlo.spice`, `design/uvlo-comparator-sizing.md`,
`layout/gate_driver_core.gds`, and every currently-recorded evidence file
under `sim/gate-driver-core-drive-with-uvlo/` and
`sim/gate-driver-core-drive-with-uvlo-postlayout/` are **unchanged** by this
record — it documents the measured behavior of the already-committed
design, per `CLAUDE.md`'s "agents do not relax the ratified spec to make
results pass." The FAIL verdicts already on file for this corner stand as
this exception's evidence; no new `sim/` record is required, matching the
precedent decision record 0016 established.

## Alternatives considered

- **Re-size `uvlo`'s comparator/reference (option 1)** — considered in
  detail above; rejected as disproportionate and unlikely to succeed
  without closing decision record 0018 Finding 2's own already-deferred,
  multi-PR reference-topology redesign first. Not ruled out permanently: a
  future revision closing Finding 2 should expect this exception to become
  moot as a side effect, per "Consequences" below.
- **Amend only §3's prose (option 3), without a numeric bound** — rejected:
  a bare prose correction without a numeric bound would not give a future
  re-run a concrete pass/fail line to check itself against, unlike decision
  record 0016's precedent; folding the numeric bound into this same record
  (which also amends the prose, per the Decision above) is more useful and
  costs nothing extra.
- **Treat the measured value as noise and pass anyway** — rejected: the
  reading is consistent across three independent facets (schematic,
  post-layout no-RC, post-layout RC) and directly traceable, via the
  `vout_max_v`/`uvlo_lockout_at_in_high` evidence above, to a specific,
  already-documented physical cause (decision record 0018 Finding 2), the
  signature of a real, repeatable, understood result — not simulation
  noise.
- **Fold this into decision record 0018 directly, reopening it** — rejected
  per this record's own header: decision record 0018 explicitly covers the
  §5 protection-scope claim (trip thresholds, response time,
  guaranteed-on/off); this record covers a distinct §3 drive-strength
  target that the same underlying physical condition happens to also
  affect. Keeping them separate matches the convention decision record 0016
  established relative to decision records 0013/0015 (same cell, same kind
  of physical root cause, different spec section, separate records).

## Consequences

- `spec/gate-driver.md` §3 gains a fourth documented, bounded exception
  (after decision records 0003/0005/0006's §5-node exceptions and decision
  record 0016's stretch-sink-current exception), the second against a §3
  drive-strength target. The ≥ 0.5 A nominal source-current target is
  unchanged for every other point; the harness's per-corner `checks` bound
  is unchanged and continues to report `ss_-40c_vlogic2p97v-vdrv4p50v`
  FAIL.
- `sim/gate-driver-core-drive-with-uvlo/` and
  `sim/gate-driver-core-drive-with-uvlo-postlayout/` continue to report
  FAIL overall for any record including this corner — intentional and
  expected; a reviewer should check this record (and decision record 0018)
  before treating that FAIL as a regression.
- This exception is explicitly **coupled** to decision record 0018's open
  false-trip finding, unlike decision record 0016's exception (which stands
  on its own, unrelated device-current-density physics). A future
  UVLO reference-topology revision that closes decision record 0018 Finding
  2 should re-verify this corner specifically and expect this exception to
  become moot rather than needing its own separate re-tuning — noted here
  so that future work does not treat the two as independent problems
  requiring independent fixes.
- No new `sim/` evidence record is required by this decision record itself;
  the existing FAIL verdicts across all three cited facets stand as its
  evidence.
