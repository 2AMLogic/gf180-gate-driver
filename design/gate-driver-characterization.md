# Block-level performance characterization vs. spec §3 (issue #101)

This report aggregates `spec/gate-driver.md` §3's block-level performance
rows — drive strength, propagation delay, rise/fall — into one place, with
citations to the raw evidence behind each verdict. It exists because those
results currently live only inside their own per-experiment raw tables
(`sim/gate-driver-core-drive/records/`, `sim/output-stage-drive/records/`,
`sim/level-shifter-oxide-safety/records/`) and were never rolled up against
spec §3's own rows (`#62`'s re-read, item 8).

**No claim without a testbench.** Every number below is a simulated result
recorded under `sim/gate-driver-core-drive/`, `sim/output-stage-drive/`, or
`sim/level-shifter-oxide-safety/` (all append-only per `sim/README.md`);
nothing here is re-derived or re-simulated, only cited. `spec/gate-driver.md`
is unchanged by this issue.

**This report is now end-to-end for every row it covers.** Issue #100's
`sim/gate-driver-core-drive/` campaign composes the block's actual signal
path — 3.3 V logic `IN` → level shifter → output stage → the real 1 nF
reference load — as one measured chain, rather than two separately-loaded,
separately-driven per-cell campaigns summed or eyeballed together. See
"Coverage" below for exactly what that record does and does not establish,
and "Methodology" for how its grid differs from the two older per-cell
records it is cross-checked against.

## TL;DR

- **Propagation delay** (spec §3: < 50 ns nominal / < 25 ns stretch): now a
  single measured end-to-end number (level shifter + output stage, one
  chain) instead of two unsummed partial segments — worst-case nominal
  `tpdlh` 6.82 ns, `tpdhl` 6.35 ns; worst-case stretch `tpdlh` 5.33 ns,
  `tpdhl` 5.39 ns; all four **PASS** with wide margin
  (`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md`).
- **Drive strength** (spec §3: ≥ 0.5 A peak source/sink, stretch 1 A): met
  at every nominal-tolerance point — worst-case nominal peak source
  0.5963 A, worst-case nominal peak sink 0.5796 A, same record. At the 6 V
  stretch rail, peak source clears the 1 A stretch target (worst 1.0195 A)
  but peak sink does **not** (worst 0.8827 A, 117 mA short) — a pre-existing
  shortfall already visible in `sim/output-stage-drive/` in isolation, now
  confirmed under real end-to-end drive and stated explicitly against the
  stretch target (see "Results" below).
- **Rise/fall into the 1 nF reference load** (spec §3: < 50 ns, 10–90 %):
  met at all measured corners with wide margin — worst-case nominal rise
  8.36 ns, worst-case nominal fall 7.53 ns, essentially unchanged from the
  isolated output-stage-only numbers (see "Results" — the level shifter's
  own edge is sub-nanosecond and does not materially slow the output
  stage's own rise/fall into the load).
- All three cited records span the full CLAUDE.md PVT matrix (process
  corners `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C × supply tolerance,
  60 points each) — though not the same *supply grid*; see "Methodology"
  for the one genuine grid-convention difference that remains.

## Spec §3 rows covered here

| Spec §3 row | Target | Stretch |
|---|---|---|
| Peak source/sink current | ≥ 0.5 A | 1 A |
| Propagation delay | < 50 ns | < 25 ns |
| Rise/fall into reference load | < 50 ns (10–90 %) | — |

(Drive rail, logic input, reference load, and signoff are the other rows in
spec §3's table; they are design parameters/conditions rather than measured
performance rows and are out of scope for this issue — see the issue text.)

## Methodology: which record measures what

Three campaigns exist today. The end-to-end one
(`sim/gate-driver-core-drive/`) is now the primary source for every row in
this report; the two per-cell campaigns are retained below because they are
still cited for cross-checking and because `sim/level-shifter-oxide-safety/`
carries the block's thin-oxide safety claim, which this report does not
duplicate.

**Grid-convention note (edge case, per issue #107's test plan):**
`sim/gate-driver-core-drive/` and `sim/level-shifter-oxide-safety/` both
sweep the *tied* two-rail grid (`vlogic` ∈ {2.97, 3.30, 3.63 V} × `vdrv` ∈
{4.50, 5.00, 5.50, 6.00 V}, tied per `sim/README.md`'s convention) because
both have a real 3.3 V-logic-domain input pin. `sim/output-stage-drive/`
sweeps `vdrv` alone (its testbench declares a single custom rail and drives
`IN_DRV` directly at the drive-rail voltage, bypassing the logic domain
entirely) — so its 60 points are process × temperature × `vdrv` only, not
process × temperature × (`vlogic`, `vdrv`) like the other two. All three use
the same 1 nF reference load and the same process/temperature axes, so the
cross-checks below compare like corners (same `vdrv`, same process, same
temperature) across grids of different shape, not identical grids.

### `sim/gate-driver-core-drive/` — the full chain, end-to-end (primary source)

- **DUT**: `design/netlist/gate_driver_core.spice` (issue #98's combined
  top-level netlist — `x1` = `level_shifter`, `x2` = `output_stage`, wired
  `IN` → level shifter → `IN_DRV` → output stage → `OUT`), driving spec §3's
  actual 1 nF reference load.
- **Stimulus (`IN`)**: a real 3.3 V-logic-domain pulse — the block's actual
  logic input, not an idealized already-level-shifted edge. This is the
  first record in which the output stage's drive is generated by the real
  level shifter rather than assumed.
- **Grid**: 60 points — `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C × tied
  (`vlogic`, `vdrv`) supply point (nominal ±10 % plus the 6 V stretch rail).
- **Record**: [`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md`](../sim/gate-driver-core-drive/records/20260817-013400-ae66957.md),
  overall **FAIL** — but every one of the five harness-check misses behind
  that FAIL is on the *inherited −50 mV undershoot sanity band* on
  inter-cell/taper nodes (`IN_DRV`, `x2.n1`), not on any spec §3 drive,
  timing, or rise/fall target this report cites. Spec §3's own six rows
  (peak source/sink current, `tpdlh`/`tpdhl`, rise/fall) are all evaluated
  explicitly against their own target column in that record's §1 table —
  see "Results" below. That record also documents new spec §2.3 thick-oxide
  gate-ceiling findings on `IN_DRV`/`x2.n1`…`n5` at the 6 V stretch rail;
  those are outside this report's §3 scope (see the note at the end of
  "Results") and are recorded in that record itself, not resolved here —
  both have since been formally scoped in `spec/gate-driver.md` §5 by
  [decision record 0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md)
  (issue #136).

### `sim/output-stage-drive/` — the output stage only (retained for cross-check)

- **DUT**: `design/output_stage.sch` (the thick-oxide taper/output driver,
  entirely `nfet_06v0`/`pfet_06v0` per spec §2.5), driving spec §3's actual
  1 nF reference load.
- **Stimulus (`IN_DRV`)**: an **idealized, already-level-shifted,
  rail-referenced** pulse — 0 → `vdrv_val` with a 1 ns 0–100 % edge,
  *"representing a reasonably fast level-shifter output"* (testbench's own
  comment, `sim/output-stage-drive/testbench/output_stage_tb.spice`). This
  was, at the time it was captured, a testbench **assumption**; the level
  shifter was not present in that circuit at all, and `IN_DRV` bypassed it
  entirely. `sim/gate-driver-core-drive/` above now supplies the real
  measurement this assumption stood in for.
- **Grid**: 60 points — `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C ×
  `vdrv` ∈ {4.50, 5.00, 5.50, 6.00 V} only (no `vlogic` axis — see the
  grid-convention note above).
- **Record**: [`sim/output-stage-drive/records/20260817-110340-54fdbf8.md`](../sim/output-stage-drive/records/20260817-110340-54fdbf8.md)
  (supersedes
  [`20260812-064304-03699ea`](../sim/output-stage-drive/records/20260812-064304-03699ea.md),
  the version this report cited before issue #147's corner-scoped stretch
  check landed — the underlying measurements are unchanged to the precision
  cited here), overall **FAIL**: the corner-scoped stretch check now applies
  spec §3's ≥ 1 A stretch target at the 6 V rail explicitly, and two
  corners miss it (`ss_125c_vdrv6p00v` 0.875334 A, `sf_125c_vdrv6p00v`
  0.935921 A) — the same shortfall the end-to-end record independently
  confirms (see "Results" below); this is not a new finding, only a newly
  harness-visible one. A separate caveat that is *not* visible in that
  record's own pass/fail column: its internal-node limits are written
  against the PDK's 6.6 V overshoot bias, so the record reads PASS on
  `n1`…`n5` even though those taper nodes transiently exceed **spec §2.3's
  stricter adopted 6.0 V DC gate ceiling** at the 6 V stretch rail (worst
  case `n5` = 6.0538 V at `ss_27c_vdrv6p00v`, margin −53.8 mV). That
  excursion is formally narrowed by
  [decision record 0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md).
  `sim/gate-driver-core-drive/` (above) has since measured a larger worst
  case for the same taper nodes under the real level-shifter edge — see
  that record's Finding 3 — so this idealized-edge number is no longer the
  worst-case figure on record for those nodes, though decision record 0005's
  conclusion is unaffected. `spec/gate-driver.md` §5's Exception 2 and
  decision record 0005's own appended amendment now cite that corrected
  figure (`n1` = 6.10232 V at `sf_-40c_vlogic3p30v-vdrv6p00v`, margin
  −102.3 mV) instead, per
  [decision record 0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md).

### `sim/level-shifter-oxide-safety/` — the level shifter only (refreshed by #100)

- **DUT**: `design/netlist/level_shifter.spice` (the cascode/clamped level
  shifter, spec §4), driving the **real output-stage predriver input
  capacitance** (5.977 fF, derived from `design/output-stage-sizing.md`'s
  first-stage device geometry) — this record supersedes the prior one,
  which used a 20 fF placeholder load explicitly flagged as *"not a
  measured [output-stage] number"* in that testbench.
- **Stimulus (`IN`)**: an ideal 3.3 V-logic-domain pulse, the block's actual
  logic input swing.
- **Grid**: 60 points — `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C ×
  tied (`vlogic`, `vdrv`) supply point, same convention as
  `sim/gate-driver-core-drive/` above.
- **Record**: [`sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md`](../sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md)
  (supersedes
  [`20260808-052057-5fbdb2d`](../sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md)),
  overall **FAIL** — but, as with the superseded record, that FAIL is
  entirely the `vgate_thinox_max` oxide-safety criterion at the
  `vlogic3p63v` (+10 %) corner (the pre-driver inverter overshoot formally
  narrowed by
  [decision record 0003](../spec/decision-records/0003-predriver-inverter-oxide-margin-exception.md)),
  not a timing failure, and the failure pattern is unchanged from the
  superseded record (same 15 corners, same ceiling, values within a few
  parts in 10⁴). The lighter real load measurably speeds up `t_plh`/`t_phl`
  relative to the 20 fF placeholder (e.g. `tt_27c_vlogic3p30v-vdrv5p00v`:
  0.667 ns/0.347 ns here vs. 0.680 ns/0.359 ns previously) but does not
  change the thin-oxide safety finding. This report does not cite this
  record's `t_plh_ns`/`t_phl_ns` columns directly for the propagation-delay
  row below any more — `sim/gate-driver-core-drive/` now supplies the
  composed, end-to-end delay measurement — but this record remains the
  block's thin-oxide (§2.3) safety claim for the level shifter and is cited
  here for that reason and for completeness.

## Results

### Drive strength: peak source/sink current (spec §3: ≥ 0.5 A, stretch 1 A)

Source: [`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md`](../sim/gate-driver-core-drive/records/20260817-013400-ae66957.md)
(`ipeak_source_a` / `ipeak_sink_a` columns), full 60-point grid, spec §3
table in that record's §1.

| Measurement | Nominal target | Worst-case nominal | Nominal binding corner | Stretch target | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|---|---|
| Peak source current | ≥ 0.5 A | 0.5963 A — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | ≥ 1 A | 1.0195 A — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| Peak sink current | ≥ 0.5 A | 0.5796 A — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | ≥ 1 A | **0.8827 A — FAIL** (117 mA short) | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means: peak source 1.1620 A, peak sink 1.0206 A.

**Cross-check against `sim/output-stage-drive/`'s isolated numbers**: that
record's worst-case nominal values were peak source 0.5877 A and peak sink
0.5737 A (`ss_125c_vdrv4p50v`). The end-to-end numbers above are about
1–1.5 % higher at the matching `vdrv`/process/temperature point — a small,
real divergence, not noise: the level shifter's own output impedance and
the composed chain's parasitics change the output stage's effective drive
slightly relative to the idealized-edge testbench. It does not change any
verdict (both nominal rows still clear ≥ 0.5 A with wide margin). The
**stretch-rail shortfall on peak sink current is not new** — the isolated
`sim/output-stage-drive/` record already showed the same shortfall in
isolation (`ss_125c_vdrv6p00v` sink = 0.875334 A, `sf_125c_vdrv6p00v` sink
= 0.935921 A) — the end-to-end record confirms the level shifter is not the
cause (it contributes negligible additional loading ahead of the output
stage's own final push-pull stage) and states the shortfall explicitly
against spec §3's stretch-specific ≥ 1 A target. Resolving it is a design
change, not a verification task; cross-references issue #125 (harness
tooling gap: checks apply the nominal bound uniformly instead of the
stricter stretch bound at 6 V).

### Rise/fall into the 1 nF reference load (spec §3: < 50 ns, 10–90 %)

Source: same end-to-end record, `trise_s` / `tfall_s` columns, full
60-point grid; spec §3 table in that record's §1 (rise/fall have no
separate stretch target in §3, so only one column applies at each rail).

| Measurement | Worst-case nominal | Nominal binding corner | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|
| 10–90 % rise time | 8.36 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | 6.53 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| 10–90 % fall time | 7.53 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | 6.53 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means: rise 5.11 ns, fall 4.99 ns.

**Cross-check against `sim/output-stage-drive/`'s isolated numbers**: that
record's worst-case values were rise 8.36 ns and fall 7.53 ns
(`ss_125c_vdrv4p50v`) — the same to the precision both records report.
Unlike drive strength, rise/fall into the 1 nF load does **not** diverge
once the idealized 1 ns input edge is replaced by the real level-shifter
output edge: the level shifter's own propagation delay is sub-nanosecond
(see the refreshed `sim/level-shifter-oxide-safety/` record) and adds
negligible additional edge time ahead of the output stage's own,
load-dominated rise/fall into 1 nF. This row was already measured against
the real 1 nF load in the isolated record; it is now also measured against
a real level-shifter-driven input edge, and the number does not move.

### Propagation delay (spec §3: < 50 ns nominal, < 25 ns stretch)

This row is now a single measured end-to-end number — the level shifter and
output stage composed into one chain, `IN` → `OUT` — not two unsummed
partial segments. Source: same end-to-end record, `tpdlh_s` / `tpdhl_s`
columns, full 60-point grid; spec §3 table in that record's §1.

| Measurement | Nominal target | Worst-case nominal | Nominal binding corner | Stretch target | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|---|---|
| Low→high propagation delay (`tpdlh`) | < 50 ns | 6.82 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | < 25 ns | 5.33 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| High→low propagation delay (`tpdhl`) | < 50 ns | 6.35 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | < 25 ns | 5.39 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means: `tpdlh` 4.19 ns, `tpdhl` 4.17 ns.

This supersedes the two-segment estimate this report previously carried
(output-stage-only `tpdlh`/`tpdhl` of 5.78/5.88 ns from
`sim/output-stage-drive/`, plus level-shifter-only `t_plh`/`t_phl` of
1.13/0.61 ns from the pre-refresh `sim/level-shifter-oxide-safety/` record,
summed to an order-of-magnitude sanity bound of ≈ 7.0 ns). The end-to-end
measured values (6.82/6.35 ns nominal, 5.33/5.39 ns stretch) are **lower**
than that naive worst-case-plus-worst-case sum, because the sum combined
each segment's own independent worst-case corner rather than one corner's
actual composed delay — the naive sum was never claimed as a measured
number and this report no longer carries it, per issue #107's acceptance
criteria. `design/output-stage-sizing.md` §5's design allocation (≤ 20 ns /
≤ 10 ns of the propagation-delay budget to the output-stage segment alone)
is not disturbed by this — the end-to-end worst case clears the full
50 ns/25 ns budget with more than 6× margin at every rail.

**Note on scope**: the end-to-end record also documents new spec §2.3
thick-oxide gate-ceiling findings on the inter-cell node `IN_DRV` and the
output stage's internal taper nodes (`x2.n1`…`n5`) at the 6 V stretch rail
— these are not spec §3 drive-strength/timing/rise-fall rows and are out of
this report's scope; they are recorded in full, including the exceedance on
`IN_DRV` that decision record 0005 did not cover, in
[`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md`](../sim/gate-driver-core-drive/records/20260817-013400-ae66957.md)
§2. This report does not restate them; both are now formally scoped as
`spec/gate-driver.md` §5 exceptions by
[decision record 0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md).

## Coverage: what is now end-to-end, and what is not

**All three spec §3 rows this report covers — propagation delay, drive
strength, and rise/fall — are now backed by the end-to-end
`sim/gate-driver-core-drive/` record**, which composes the block's real
signal path (3.3 V logic `IN` → level shifter → output stage → the real
1 nF reference load) as one measured chain, driven by the real logic-domain
input rather than an idealized, already-level-shifted edge. Concretely,
relative to the previous per-cell-only version of this report:

- **Propagation delay** was previously two separate partial numbers with no
  composed measurement; it is now one measured end-to-end number per corner
  (see "Results" above) — the gap this report's "Follow-up" section
  previously flagged as blocked on issue #100 is closed.
- **Drive strength and rise/fall** were previously measured against the
  real 1 nF load but with an idealized input edge (the level shifter was
  entirely absent from that circuit); they are now also measured with the
  real level-shifter-driven edge feeding the output stage. Rise/fall did
  not move measurably; drive strength moved by a small (~1–1.5 %),
  non-verdict-changing amount — see the cross-checks in "Results" above.
- The **thin-oxide (§2.3) safety claim** for the level shifter, which this
  report does not itself carry a row for, is re-established against the
  real output-stage predriver input capacitance in the refreshed
  `sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md`
  (superseding `20260808-052057-5fbdb2d`) — its verdict pattern (thin-oxide
  ceiling exceeded at the `vlogic3p63v` +10 % corner, per ratified decision
  record 0003) is unchanged by the load refresh.

**What remains open, and is intentionally not resolved by this report**
(per `CLAUDE.md`: "agents do not relax the ratified spec to make results
pass" and "no claim without a testbench" — these are design or
spec-decision follow-ups, not documentation gaps):

- The 6 V stretch-rail peak-sink-current shortfall against spec §3's ≥ 1 A
  stretch target (cross-references issue #125).
- ~~The new, unratified spec §2.3 thick-oxide ceiling exceedance on
  `IN_DRV`~~ — **resolved by
  [decision record 0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md)**
  (issue #136), which ratifies it as `spec/gate-driver.md` §5's Exception 3
  and corrects Exception 2's cited worst case to the
  larger-than-previously-recorded taper-node figure on `x2.n1`. Both are
  documented in the end-to-end record's §2 and not restated in full here
  because they fall outside this report's spec §3 scope (see the scope note
  at the end of "Results"). Decision record 0006 also leaves one item open:
  a characterized-but-not-adopted mitigation for `IN_DRV`, and a
  deck-fidelity question about whether the harness's default transient
  tolerances resolve narrow coupling transients.
- Five harness-check misses on the inherited, non-spec −50 mV undershoot
  sanity band, documented in the end-to-end record's §3 and not restated
  here for the same reason.

## Links

- Gate-driver-core-drive (end-to-end) record: [`sim/gate-driver-core-drive/records/20260817-013400-ae66957.md`](../sim/gate-driver-core-drive/records/20260817-013400-ae66957.md)
- Gate-driver-core-drive testbench: [`sim/gate-driver-core-drive/testbench/gate_driver_core_tb.spice`](../sim/gate-driver-core-drive/testbench/gate_driver_core_tb.spice)
- Combined top-level netlist: [`design/netlist/gate_driver_core.spice`](netlist/gate_driver_core.spice) (from issue #98)
- Output-stage-drive record (current): [`sim/output-stage-drive/records/20260817-110340-54fdbf8.md`](../sim/output-stage-drive/records/20260817-110340-54fdbf8.md)
- Output-stage-drive record (superseded): [`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../sim/output-stage-drive/records/20260812-064304-03699ea.md)
- Output-stage-drive testbench: [`sim/output-stage-drive/testbench/output_stage_tb.spice`](../sim/output-stage-drive/testbench/output_stage_tb.spice)
- Output-stage-drive design/sizing notes: [`design/output-stage-sizing.md`](output-stage-sizing.md) (§5's delay-budget allocation, §6's per-cell summary tables)
- Level-shifter-oxide-safety record (current): [`sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md`](../sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md)
- Level-shifter-oxide-safety record (superseded): [`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`](../sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md)
- Level-shifter-oxide-safety testbench: [`sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice`](../sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice)
- Spec: [`spec/gate-driver.md`](../spec/gate-driver.md) §3 (targets), §5 (protection scope / documented exceptions)
- Decision records: [0003](../spec/decision-records/0003-predriver-inverter-oxide-margin-exception.md), [0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md)
- Re-read table: issue #62 (item 8); epic tracking: issue #22; end-to-end campaign: issue #100 (closed, PR #135); this rollup: issue #107
