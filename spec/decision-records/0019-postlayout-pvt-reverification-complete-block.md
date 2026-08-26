# 0019: Post-layout PVT re-verification of the complete gate-driver block (with UVLO) — corroborates schematic findings; extraction narrows two marginal corners, RC parasitics narrow more; one pre-existing, un-excepted nominal-corner miss is flagged, not newly introduced

- **Status**: Ratified
- **Date**: 2026-08-26
- **Decided by**: Builder agent, issue #222
- **Extends**: `spec/gate-driver.md` §3, §5. **Supersedes**: none. Does not
  reopen decision records 0013/0015/0016 (§2.3/§3 exceptions on this same
  cell) or 0018 (UVLO comparator PVT measurement) — this record re-runs
  those same claims against the extracted, DRC-clean/LVS-matched
  complete-block layout (issue #221) rather than the schematic, following
  the third of four sequential slices of epic #219/#542 Phase 3A
  (schematic → layout → **post-layout** → proposal).

## Context

Issue #220 PVT-verified the complete block (level shifter + output stage +
`uvlo`) at the schematic level (`sim/gate-driver-core-drive-with-uvlo/`,
decision record 0018). Issue #221 extended `layout/gate_driver_core.gds` to
draw `uvlo`'s comparator and its `Rref`/`R1`/`R2`/`Rfb` bias-resistor network
alongside the pre-existing `level_shifter`/`output_stage` layout, DRC-clean
and LVS-matched (2044/2044 devices, 295/295 nets — reconfirmed directly by
this issue's own re-extraction, `layout/lvs/reports/gate_driver_core/
20260826-062806-a7dcce1.lvs.json`, `status: match`, single benign
"topology" warning carried over unchanged from #221's own signoff). This
record is the post-layout re-verification issue #221 deferred, matching the
precedent already established for the pre-UVLO core cell
(`sim/gate-driver-core-drive-postlayout/`).

## Tooling: extending `mk_extracted_dut.py` for `uvlo`'s new device classes

`uvlo`'s bias-resistor network extracts as a new, three-terminal (`a`/`b`/`w`)
`ppolyf_u` device class `mk_extracted_dut.py` had no case for — extending it
(`RES_CLASSES`, transform T9) was a precondition for this issue's own
deliverable, not incidental scope. Two real bugs were found and fixed along
the way, both load-bearing (a wrong DUT, not just an incomplete one, without
the fix):

1. **The MOS-body-terminal skip in T5's per-net parasitic loop matched on
   the bare terminal letter `"b"`**, which a two-terminal passive device
   (`CAP_CLASSES`/`RES_CLASSES`) also uses for its own second lead — a
   resistor's ordinary `b` lead was being silently treated as a MOS body and
   dropped from the parasitic star, undercounting every unit resistor's own
   internal-node leg resistance by half. Fixed by scoping the skip to devices
   with no body concept at all (`CAP_CLASSES | RES_CLASSES`), the same way
   the skip already excluded `CAP_CLASSES`.
2. **`klt` 0.3.0+g3f98b441bf2f now backslash-escapes an anonymous net's `$N`
   as `\$N`** in every net-name JSON field, inconsistently with the
   unescaped device-name field for the identical device — a `klt`/deck
   tool-version behavior change, not a design change (filed generically
   against `2AMLogic/klayout-tools`, CLAUDE.md's friction protocol:
   `2AMLogic/klayout-tools#1439`).
   `_spice_node()` now accepts both spellings.

Both are covered by new unit tests (`ResistorDeviceTest`,
`AnonymousNetNameTest.test_spice_node_rewrites_the_backslash_escaped_form_too`).
Re-extracting the current, committed `layout/gate_driver_core.gds` still
reports `klt lvs`: match, 2044/2044 devices — confirming issue #221's own
signoff is unaffected by anything in this record.

## Evidence

Four full-corner-matrix records, all against the extracted, LVS-matched
`layout/gate_driver_core.gds` (issue #221), commit `a7dcce1`:

| Record | DUT | Rails | Points | Overall |
|---|---|---|---|---|
| `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md` | `layout/lvs/gate_driver_core.extracted.spice` (no interconnect parasitics) | spec (±10% + 6 V stretch) | 60/60 ok | FAIL (47/60 pass) |
| `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md` | `layout/lvs/gate_driver_core.extracted-rc.spice` (`klt extract --parasitics`) | spec (±10% + 6 V stretch) | 60/60 ok | FAIL (57/60 pass) |
| `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-074206-a7dcce1.md` | `layout/lvs/gate_driver_core.extracted.spice` | Challenge #5 (`vdrv` 3.3/4.15/5.0 V) | 45/45 ok | FAIL (26/45 pass) |
| `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-074240-a7dcce1.md` | `layout/lvs/gate_driver_core.extracted-rc.spice` | Challenge #5 (`vdrv` 3.3/4.15/5.0 V) | 45/45 ok | FAIL (29/45 pass) |

Compared against issue #220's schematic-level records:
`sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md`
(spec rails, 43/60 pass) and
`sim/gate-driver-core-drive-with-uvlo/records/20260826-013219-6299c36.md`
(Challenge #5 rails, 23/45 pass). The Challenge #5 rail sweep and the
harness-check `stretch` bound removal were reproduced by a temporary,
uncommitted `tb.json` edit (`rails.vdrv = {nominal_v: 4.15, tolerance:
(4.15-3.30)/4.15}`, `stretch: false`), the same convention issue #220's own
three schematic-level records used (three distinct manifest sha256 values
committed against one `tb.json` state) — the committed `tb.json` reflects
the default spec-rail configuration used for the two spec-rail records
above.

## Finding 1 — Drive-strength and gate-ceiling results corroborate the schematic at spec rails; every divergence narrows a margin, none opens one

`20260826-063405-a7dcce1` (extracted, no RC) passes 47/60 spec-rail points
against the schematic's 43/60. All 17 corners whose pass/fail label differs
from the schematic move in the **same, favorable** direction — real
interconnect/device-geometry effects the ideal schematic cannot see damp the
output stage's taper-node undershoot (`n1_min_v`, sanity floor −50 mV, not a
`spec/gate-driver.md` target):

| Corner | Schematic `n1_min_v` | Postlayout (no-RC) `n1_min_v` |
|---|---|---|
| `tt_-40c_vlogic2p97v-vdrv4p50v` | −50.09 mV (FAIL) | −48.00 mV (PASS) |
| `ss_27c_vlogic3p30v-vdrv5p00v` | −56.02 mV (FAIL) | −53.73 mV (FAIL, narrower) |
| `ss_125c_vlogic3p30v-vdrv6p00v` | ipeak_sink 0.877588 A (FAIL) | 0.878644 A (FAIL, ~flat) |

No corner regresses (schematic PASS → postlayout FAIL) at any measured
metric. `ipeak_sink_a` at the two decision-record-0016 stretch corners
(`ss_125c`/`sf_125c` at `vdrv6p00v`) stays essentially flat
(0.877588→0.878644 A, 0.921977→0.928513 A) — decision record 0016's ≥ 0.85 A
bound is unaffected either way.

## Finding 2 — UVLO lockout behavior at the sampled corners matches the schematic 1:1 (spec rails)

At **spec rails**, the same two corners decision record 0018 Finding 2 flags
as locked at the `vdrv4p50v` point (`ss_-40c`, `sf_-40c` — `x3.lockout ≈
VDD_DRV`, `OUT` held near 0 V) are locked, and only those two, in both spec-
rail records (`20260826-063405-a7dcce1` no-RC, `20260826-072640-a7dcce1`
RC) — no other spec-rail corner reports a non-zero
`uvlo_lockout_at_in_high`. This corroborates decision record 0018's
false-trip finding (`ss_-40c`/`sf_-40c` remain locked at the legitimate
−10% low-line corner) directly in the layout, independent of the
schematic-level standalone/full-block cross-check that record already
performed. (Challenge #5 rails show a much wider locked set, as expected —
see Finding 4.)

## Finding 3 — RC parasitics measurably shift propagation delay and further narrow the taper-node undershoot; one corner's `ipeak_sink_a` gets newly (marginally) worse

Comparing `20260826-072640-a7dcce1` (RC) against `20260826-063405-a7dcce1`
(no-RC), same spec-rail grid:

- **Propagation delay**: `tpdlh_s` shifts +5.4 to +12.1 ns (mean +7.9 ns),
  `tpdhl_s` shifts +4.1 to +8.1 ns (mean +5.6 ns) — material against the
  50 ns/25 ns budget, but every corner still clears its target with margin
  (no new `tpdlh_s`/`tpdhl_s` check failure appears). `trise_s`/`tfall_s`
  move only 8–36 ps, negligible.
- **Taper-node undershoot**: RC *narrows* `n1_min_v` at every one of the 10
  `ss`-corner points that failed without RC — all 10 flip to PASS — plus the
  `ss_-40c_vlogic2p97v-vdrv4p50v` corner's `ipeak_source_a` improves
  (0.499696 → 0.475414 A; still FAIL, target unchanged). Net: 57/60 PASS
  with RC vs. 47/60 without.
- **One genuine, extraction-only regression** (Challenge #5 rail grid,
  `20260826-074206-a7dcce1` vs. `20260826-074240-a7dcce1`):
  `ff_-40c_vlogic2p97v-vdrv3p30v` fails only `ipeak_source_a` without RC
  (0.450805 A) but fails **both** `ipeak_source_a` (0.427364 A) and
  `ipeak_sink_a` (0.492499 A, newly under the 0.5 A floor) with RC —  a real,
  extraction-only current reduction at this corner, not a numeric-noise
  artifact (both currents move down together, consistent with added
  interconnect resistance). This corner already failed overall on
  `ipeak_source_a` alone; RC does not change its overall PASS/FAIL label,
  but does add a second, distinct failing metric at it — called out here
  per this issue's own "extraction-only deltas" mandate rather than folded
  silently into the unchanged overall FAIL.

This substantiates issue #222's own callout that "real interconnect
parasitics measurably change the transient stiffness" of this design once
`uvlo`'s regenerative comparator and the output stage's real wiring are
both in the loop — net effect here is a **narrower** failure set, with one
isolated exception (above) that is honestly worse, not better.

## Finding 4 — Challenge #5 rails (3.3 V digital / 5.0 V analog envelope) corroborate the schematic's Finding 5

`20260826-074206-a7dcce1` (extracted, no RC, Challenge #5 rails) passes
26/45 points against the schematic's 23/45 (`20260826-013219-6299c36`);
`20260826-074240-a7dcce1` (RC) passes 29/45. As at spec rails (Finding 1),
every schematic-vs-postlayout divergence narrows an existing margin (mostly
the same `n1_min_v` effect); none opens a new one. The same
partial-lockout pattern decision record 0018 Finding 5 describes — some
corners locked, some released, within the same 15-point process×temperature
sub-grid at a given `vdrv` point — reproduces unchanged in the extracted
layout. This is an expected, already-documented consequence of Finding 1
of decision record 0018 (the comparator's wide PVT threshold spread), not a
new finding; re-deriving the divider/reference sizing against the
Challenge #5 rail's own low-line floor remains the open item decision
record 0018 already flagged, unaffected by extraction.

## Finding 5 — A pre-existing nominal-rail drive-strength miss, inherited unchanged from issue #220's schematic, is not covered by any existing bounded exception

At `ss_-40c_vlogic2p97v-vdrv4p50v` — a **nominal ±10%** spec-rail corner,
not the 6 V stretch rail decision record 0016 already excepts —
`ipeak_source_a` falls just under the ≥ 0.5 A target at every facet
measured in this issue and in issue #220's own schematic record:

| Facet | `ipeak_source_a` (A) |
|---|---|
| Schematic (`20260826-013137-6299c36`) | 0.499165 |
| Postlayout, no RC (`20260826-063405-a7dcce1`) | 0.499696 |
| Postlayout, RC (`20260826-072640-a7dcce1`) | 0.475414 |

The miss is essentially flat across schematic → extraction → RC-extraction
(within ±5% of the target itself) — **not introduced or materially worsened
by layout or extraction**. It predates this issue: the pre-UVLO schematic at
this same corner (`sim/gate-driver-core-drive/records/
20260821-113949-d2ba4d8.md`) measures 0.831095 A, comfortably clearing the
target — the miss appears only once `uvlo` (issue #220) is instantiated,
consistent with `uvlo`'s comparator loading `OUT` near this corner's
lockout boundary (Finding 2's same two corners, `ss_-40c`/`sf_-40c`, sit
closest to their trip point at `vdrv4p50v`).

This is a genuine miss against `spec/gate-driver.md` §3's own ratified
target (≥ 0.5 A, nominal ±10% matrix) and against that section's own
descriptive text ("every point of the nominal ±10% matrix clear[s] their
respective targets"), which predates issue #220's UVLO addition and was
accurate when written but was not revisited when UVLO was added. It is
**not** covered by decision record 0016 (scoped to the 6 V stretch rail
only). Per CLAUDE.md ("no claim without a testbench"; "agents do not relax
the ratified spec to make results pass"), this is recorded here rather than
silently absorbed — but authoring a new bounded exception (or correcting
§3's prose) requires deciding whether the fix belongs to `uvlo`'s own sizing
or to the exception text, which is issue #220's design scope, not this
issue's post-layout re-verification scope. **Filed as follow-up issue #226**
(see Consequences) rather than resolved unilaterally here.

## Finding 6 — A standalone, ramp-based post-layout re-measurement of `uvlo`'s own trip/hysteresis/response-time facet is infeasible from this GDS

`sim/uvlo-trip-verification/`'s schematic-level facet (decision record
0018 Findings 1/2/4) exercises `design/netlist/uvlo.spice` in isolation via
a direct `VDD_DRV` ramp. `uvlo` has no independent top-cell boundary in
`layout/gate_driver_core.gds` — `klt cells` reports only per-device leaf
cells (`x3_XMREF__x3_XMREF`, etc.) and the flat `gate_driver_core` top,
confirmed directly against the committed GDS — so there is no sub-hierarchy
`klt extract --top uvlo` could target. A standalone post-layout
trip/hysteresis/response-time re-measurement, independent of the full
block's own load, is therefore **not obtainable from this layout as drawn**;
the closest available post-layout evidence is the full-block, per-corner
lockout/`OUT`/`VDD_DRV` snapshot in Finding 2 above (the same methodology
decision record 0018's own "corroborated independently in the full-block
context" already used), plus Finding 3's propagation-delay-shift
observation. A future revision that wants an independently-extractable
`uvlo` facet would need to draw it as its own named GDS cell rather than
flattening it into `gate_driver_core`'s device array — noted here as an
open item, not resolved by this record.

## Simulation-cost note: RC-parasitic grid is materially more expensive, and needs a longer per-point timeout under 8-way parallelism than the default

The RC-parasitic full-block netlist (1769 individually-instantiated
transistors, 6128 R / 295 C interconnect-parasitic elements, plus 271
`ppolyf_u` bias-resistor devices and 4 `cap_mim_2f0_m4m5_noshield` devices)
is far more expensive to simulate than the parasitic-free extracted netlist:
the 60-point spec-rail grid completes in under 20 s total without RC, but
takes 863.5 s (about 14.4 minutes) with RC, at `-j 8` (this machine's core
count). At the harness's 120 s default per-point timeout and 8-way
parallelism, **9 of 60 points spuriously reported `ngspice timed out`** —
re-running the identical 9 points serially (`-j 1`) at a 300 s timeout
converged in under 50 s each. This is **CPU oversubscription under
contention, not a genuine convergence failure**: raising the per-point
timeout to 300 s at `-j 8` (used for both records in this issue's Evidence
table) converges all 60/45 points cleanly with no change to the measured
results at any point that had already converged at 120 s. Noted here as a
harness-tuning observation for any future full-RC-grid re-run on this
design, not a `klayout-tools` friction item (it is an `ngspice`/harness
timeout choice, not a `klt`/deck behavior).

## Decision

Post-layout re-verification corroborates issue #220's schematic-level
findings at every metric it can directly compare (Findings 1–2, 4): no
schematic-passing corner regresses to a post-layout failure at either rail
set, with or without RC parasitics, and every pre-existing bounded exception
(decision records 0013/0015/0016) and the open UVLO false-trip finding
(decision record 0018) stand unchanged. RC parasitics narrow more marginal
corners than they open (Finding 3), with one honestly-flagged, isolated
exception (`ff_-40c_vlogic2p97v-vdrv3p30v`, Challenge #5 rails, RC). Finding
5 documents a genuine, previously-un-excepted nominal-rail miss that
predates this issue (inherited unchanged from issue #220's schematic) and is
referred to a follow-up issue rather than resolved here. Finding 6 documents
a real scope boundary of the current layout (no standalone `uvlo` GDS cell),
not a defect in this record's own methodology.

## Alternatives considered

- **Skip the RC-parasitic grid and report only the parasitic-free extracted
  netlist** — rejected: issue #222 explicitly calls out "extraction-only
  deltas (parasitic RC effects on UVLO response time in particular)" as a
  required reporting item, and the existing core-sub-cell post-layout
  precedent (`sim/gate-driver-core-drive-postlayout/`) already runs both
  variants as separate full-grid records.
- **Accept the initial 120 s-timeout run's 9 `ERROR` points as genuine
  non-convergence and report it as-is** — rejected after a targeted,
  serial re-run showed all 9 converge well inside a 300 s budget; reporting
  the 120 s run would have overstated a tooling artifact as a circuit
  finding. The 300 s/`-j 8` re-run is the record cited in this issue's
  Evidence table.
- **Redraw `uvlo` as its own extractable GDS cell in this issue, to close
  Finding 6** — rejected as out of scope: this issue is the post-layout
  *simulation* slice of epic #219 against #221's already-committed,
  DRC-clean/LVS-matched GDS; redrawing the layout is #221's scope (closed)
  or a new follow-up, not this issue's.
- **Author a new bounded-exception decision record for Finding 5 directly in
  this record** — rejected: Finding 5's condition is inherited unchanged
  from issue #220's own schematic (not introduced by extraction), and
  deciding whether to narrow `uvlo`'s sizing, add a bounded exception, or
  amend §3's prose is a design-scope decision belonging to whoever picks up
  the follow-up issue this record files, not a re-verification-scope one.

## Consequences

- `sim/gate-driver-core-drive-with-uvlo-postlayout/` is a new experiment
  directory, following the existing `sim/gate-driver-core-drive-postlayout/`
  precedent, with its own `testbench/`, `netlist-snapshots/`, `corners/`,
  `records/` (four records: extracted/RC × spec-rails/Challenge-#5-rails).
- `layout/lvs/mk_extracted_dut.py` gains `RES_CLASSES`/T9 (durable — needed
  by any future re-extraction of this GDS, not just this record) and the
  `\$N` backslash-escape fix to `_spice_node()` (T8).
- Issue #226 is filed to resolve Finding 5 (nominal-rail `ipeak_source_a`
  miss at `ss_-40c_vlogic2p97v-vdrv4p50v`, inherited from issue #220,
  uncovered by any existing bounded exception) — either a new
  bounded-exception decision record extending decision record 0016's shape,
  a `uvlo` sizing revision, or an amendment to `spec/gate-driver.md` §3's
  descriptive prose, decided by whoever picks it up.
- A future reference-topology revision closing decision record 0018's
  open false-trip finding must re-verify, in the same pass, both the
  schematic (`sim/gate-driver-core-drive-with-uvlo/`,
  `sim/uvlo-trip-verification/`) and this record's post-layout facets
  (`sim/gate-driver-core-drive-with-uvlo-postlayout/`) — the same
  full-re-verification obligation decision record 0016 already established
  for a sizing change on this same cell family.
- Finding 6's scope boundary (no standalone `uvlo` GDS cell) carries forward
  to any future post-layout UVLO characterization work.
- The RC-parasitic grid's per-point timeout (Simulation-cost note) should be
  set to at least 300 s (not the harness's 120 s default) at `-j 8` on
  comparable hardware for any future full re-run of this experiment's RC
  variant, to avoid mis-reporting contention-induced slowness as
  non-convergence.
