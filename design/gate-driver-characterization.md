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

**Refresh note (issue #233, 2026-09-09):** the TL;DR and Results tables below
were re-derived against
[`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md),
the current, ratified ([decision record
0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md))
post-layout, RC-parasitic-extracted record for the **complete block including
`uvlo`** (`layout/gate_driver_core.gds`, issue #221/#222), with
[`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md)
(same layout, no interconnect parasitics) cited alongside it as the no-RC
cross-check, per this report's existing RC-primary/no-RC-cross-check
convention (previously used for the pre-UVLO `af13899` postlayout facet).
This supersedes this report's prior primary citation of
`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md` (schematic,
no `uvlo`) and, in the "Post-layout coverage" section below, of
`sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md`
(post-layout, no `uvlo`) — both of which PR #225 (layout) and PR #227
(simulation, decision record 0019) have since superseded with a UVLO-
instantiated complete-block equivalent; those prior records' own figures are
retained below as prior/superseded columns, per this report's existing
convention, not deleted. **Two verdict changes are expected and are both
already-ratified, bounded exceptions, not new findings**: the 6 V
stretch-rail peak-*sink*-current shortfall this report already tracked
(decision record 0016, bounded at **≥ 0.85 A**) is unchanged in kind but now
cited against the complete-block-with-UVLO evidence; and a second, new
bounded exception now applies to the nominal ±10 % peak-*source*-current row
— exactly one corner, `ss_-40c_vlogic2p97v-vdrv4p50v`, misses the ≥ 0.5 A
nominal target once `uvlo` is instantiated, bounded at **≥ 0.45 A** by
[decision record
0020](../spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md)
(the corner is fully UVLO-locked, `vout_max_v` ≈ 0.24 V, and the sub-0.5 A
reading is a contention-current artifact of that lockout, not a weakened
drive attempt). Every other spec §3 row/corner combination stays PASS by a
wide margin; propagation delay and rise/fall verdicts are unaffected.

## TL;DR

- **Propagation delay** (spec §3: < 50 ns nominal / < 25 ns stretch): a
  single measured end-to-end number (level shifter + output stage + `uvlo`,
  one chain) — worst-case nominal `tpdlh` 19.11 ns, `tpdhl` 14.53 ns;
  worst-case stretch `tpdlh` 15.40 ns, `tpdhl` 12.59 ns; all four **PASS**
  with wide margin against the 50 ns/25 ns budget, though materially slower
  than the pre-UVLO/no-RC figures this report previously cited — RC
  interconnect parasitics measurably shift propagation delay (decision
  record 0019 Finding 3) — see "Results" below
  (`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`).
- **Drive strength** (spec §3: ≥ 0.5 A peak source/sink, stretch 1 A): met
  at every nominal-tolerance point **except one** — worst-case nominal peak
  source **0.4754 A — FAIL** at `ss_-40c_vlogic2p97v-vdrv4p50v`, a
  ratified, bounded exception (decision record 0020, **≥ 0.45 A**; the
  corner is fully UVLO-locked, not a weakened drive attempt); worst-case
  nominal peak sink 0.5550 A, same corner, **PASS**. At the 6 V stretch
  rail, peak source clears the 1 A stretch target (worst 1.0040 A) but peak
  sink does **not** (worst 0.8764 A, ~124 mA short), the same pre-existing
  shortfall this report has tracked since before `uvlo` existed, a ratified,
  bounded exception (decision record 0016, **≥ 0.85 A**) — see "Results"
  below.
- **Rise/fall into the 1 nF reference load** (spec §3: < 50 ns, 10–90 %):
  met at all measured corners with wide margin — worst-case nominal rise
  8.42 ns, worst-case nominal fall 7.59 ns; worst-case stretch rise 6.57 ns,
  fall 6.59 ns — essentially unchanged from the pre-UVLO figures this report
  previously cited (see "Results").
- The primary cited record spans the full CLAUDE.md PVT matrix (process
  corners `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C × tied two-rail supply
  point, 60 points) against the extracted, LVS-matched, RC-parasitic
  complete-block layout (`layout/gate_driver_core.gds`, including `uvlo`);
  see "Methodology" for the one genuine grid-convention difference that
  remains against the two older per-cell records still cross-checked below.

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

Three schematic-level campaigns are described below; **the "Results" section
above now cites the post-layout, complete-block-with-`uvlo` campaign
(`sim/gate-driver-core-drive-with-uvlo-postlayout/`, [decision record
0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md))
as the primary source for every §3 row** (see the "Refresh note" and
"Post-layout coverage" above). The schematic-level end-to-end campaign
(`sim/gate-driver-core-drive/`, described next) remains the primary source
for the §2.3 thick-oxide gate-ceiling exceedance discussion at the end of
"Results" (out of this report's §3 scope) and is retained, alongside the two
older per-cell campaigns, as a cross-check the post-layout numbers are
compared against (Results, "Cross-check" paragraphs); `sim/level-shifter-oxide-safety/`
additionally carries the block's thin-oxide safety claim, which this report
does not duplicate.

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

### `sim/gate-driver-core-drive/` — the full chain, end-to-end, schematic-level (cross-check; §2.3 gate-ceiling primary source)

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
- **Record**: [`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`](../sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md),
  overall **FAIL** — two classes of miss, neither on any spec §3
  drive/timing/rise-fall row this report evaluates as a per-row PASS/FAIL
  (see "Results" below, which states each spec §3 row's own verdict
  explicitly): the same 6 V stretch-rail peak-sink-current shortfall this
  report already tracks against spec §3's own ≥ 1 A stretch target (now also
  surfaced as a direct per-corner harness check, at the same two corners as
  every prior record of this experiment), and 16 of 60 points on the
  *inherited −50 mV undershoot sanity band* on the output stage's `x2.n1`
  taper node (a larger point-count but a smaller worst-case magnitude than
  the pre-`XCCOMP` uncompensated control — see the record's own comparison
  table). This is the first full-grid re-run of this experiment since
  `design/netlist/gate_driver_core.spice`'s `XCCOMP` feedforward
  compensation capacitor was re-modeled as four series
  `cap_mim_2f0_m4m5_noshield` devices ([decision record
  0014](../spec/decision-records/0014-xccomp-mim-density-and-series-stack.md),
  issue #192); it also re-measures the inter-cell node `IN_DRV`'s spec §2.3
  thick-oxide gate-ceiling exceedance at the 6 V stretch rail, narrowing the
  ceiling excess from the uncompensated circuit's −148.3 mV margin to
  **−2.66 mV**. That exceedance is outside this report's §3 scope (see the
  note at the end of "Results") and is formally scoped in
  `spec/gate-driver.md` §5 Exception 3 by [decision record
  0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md)
  (issue #136), with its measured figure since re-stated by decision record
  0014 to match this citation's current record.

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

Source (primary): [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md)
(`ipeak_source_a` / `ipeak_sink_a` columns), the RC-parasitic-extracted,
post-layout, complete-block-with-`uvlo` record ([decision record
0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md)),
full 60-point grid, worst nominal (45-point, ≤ 5.5 V rail) and worst stretch
(15-point, 6.0 V rail) values read directly from that record's own
corner-by-corner result table; no-RC cross-check:
[`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md).

| Measurement | Nominal target | Worst-case nominal | Nominal binding corner | Stretch target | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|---|---|
| Peak source current | ≥ 0.5 A (**≥ 0.45 A** at `ss_-40c_vlogic2p97v-vdrv4p50v`, [decision record 0020](../spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md)) | **0.4754 A — FAIL, bounded** (decision record 0020) | `ss_-40c_vlogic2p97v-vdrv4p50v` | ≥ 1 A | 1.0040 A — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| Peak sink current | ≥ 0.5 A | 0.5550 A — **PASS** | `ss_-40c_vlogic2p97v-vdrv4p50v` | ≥ 1 A (**≥ 0.85 A**, [decision record 0016](../spec/decision-records/0016-output-stage-stretch-sink-current-shortfall.md)) | **0.8764 A — FAIL, bounded** (decision record 0016) | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means (60-point grid): peak source 1.1293 A, peak sink 1.0084 A.

**Decision record 0020 (peak source, nominal, new in this refresh)**: at
exactly one nominal ±10 % corner, `ss_-40c_vlogic2p97v-vdrv4p50v`, `uvlo`'s
comparator is already fully locked out throughout `IN`'s high pulse
(`uvlo_lockout_at_in_high` ≈ `VDD_DRV`, `vout_max_v` = 0.2445 V — `OUT` never
rises above a quarter of a volt) — the measured 0.4754 A is a sub-nanosecond
contention-current transient between the output driver and the already-
engaged UVLO pulldown, not a sustained charge-delivery attempt. Decision
record 0020 bounds this specific corner at **≥ 0.45 A** (0.4754 A sits inside
that bound with ~5.6 % headroom); no other nominal ±10 % corner misses the
≥ 0.5 A target. This finding is inherited unchanged from issue #220's
schematic-level UVLO measurement (`sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md`,
0.499165 A at the same corner) — layout and extraction narrow it slightly
(0.499696 A no-RC, 0.475414 A RC) rather than introduce it.

**Decision record 0016 (peak sink, 6 V stretch, carried forward)**: the
stretch-rail sink-current shortfall this report has tracked since before
`uvlo` existed is unchanged in mechanism — decision record 0016 bounds the
two hot/slow corners (`ss_125c`/`sf_125c` at `vdrv6p00v`) at **≥ 0.85 A**;
this record measures 0.8764 A / 0.9242 A there, both inside the bound. Peak
source at the 6 V stretch rail continues to clear its own ≥ 1 A target
(worst 1.0040 A, same binding corner as the sink shortfall).

**Cross-check against the schematic-with-UVLO and no-RC post-layout
facets**: decision record 0019's own evidence table shows all three facets
(schematic `6299c36`, post-layout no-RC `063405`, post-layout RC `072640`)
agree on both bounded exceptions' corners and stay within a few percent of
each other at every other point (decision record 0019 Findings 1 and 3);
neither exception is an extraction artifact. Resolving either shortfall is a
design change, not a verification task (decision records 0016 and 0020).

### Rise/fall into the 1 nF reference load (spec §3: < 50 ns, 10–90 %)

Source (primary): same complete-block-with-`uvlo` post-layout RC record
(`20260826-072640-a7dcce1`), `trise_s` / `tfall_s` columns, full 60-point
grid, worst nominal/stretch values read the same way as the drive strength
table above (rise/fall have no separate stretch target in §3, so only one
column applies at each rail); no-RC cross-check: `20260826-063405-a7dcce1`.

| Measurement | Worst-case nominal | Nominal binding corner | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|
| 10–90 % rise time | 8.42 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | 6.57 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| 10–90 % fall time | 7.59 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | 6.59 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means (60-point grid): rise 5.02 ns, fall 4.88 ns.

**Cross-check against the pre-UVLO schematic/post-layout facets**: this
report previously cited a pre-UVLO end-to-end schematic worst-case of rise
8.37 ns / fall 7.53 ns
(`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`) and a
pre-UVLO post-layout RC worst-case in the same range
(`sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md`).
The complete-block-with-`uvlo` numbers above are essentially unchanged
(within a few tens of picoseconds) — `uvlo`'s comparator and bias network
sit off the `IN`→`OUT` signal path and do not materially load the output
stage's own, load-dominated rise/fall into 1 nF, consistent with decision
record 0019 Finding 3's own observation that RC parasitics move
`trise_s`/`tfall_s` by only 8–36 ps.

### Propagation delay (spec §3: < 50 ns nominal, < 25 ns stretch)

This row is a single measured end-to-end number — the level shifter, output
stage, and `uvlo` composed into one chain, `IN` → `OUT`, against the
extracted, LVS-matched, RC-parasitic complete-block layout. Source
(primary): same complete-block-with-`uvlo` post-layout RC record
(`20260826-072640-a7dcce1`), `tpdlh_s` / `tpdhl_s` columns, full 60-point
grid, worst nominal/stretch values read the same way as the drive strength
table above; no-RC cross-check: `20260826-063405-a7dcce1`.

| Measurement | Nominal target | Worst-case nominal | Nominal binding corner | Stretch target | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|---|---|
| Low→high propagation delay (`tpdlh`) | < 50 ns | 19.11 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | < 25 ns | 15.40 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| High→low propagation delay (`tpdhl`) | < 50 ns | 14.53 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | < 25 ns | 12.59 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means (60-point grid): `tpdlh` 12.11 ns, `tpdhl` 9.71 ns.

**RC parasitics materially shift this row relative to the pre-UVLO/no-RC
figures this report previously cited** (nominal `tpdlh`/`tpdhl` of
6.95/6.38 ns from the pre-UVLO schematic end-to-end record,
`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`) — per
decision record 0019 Finding 3, `tpdlh_s` shifts +5.4 to +12.1 ns and
`tpdhl_s` shifts +4.1 to +8.1 ns once interconnect RC parasitics and `uvlo`
are both in the loop, comparing the no-RC (`20260826-063405-a7dcce1`) and RC
(`20260826-072640-a7dcce1`) complete-block-with-`uvlo` facets directly. Every
corner still clears its target with wide margin — the worst-case nominal
figures above clear the 50 ns budget by more than 2.6×, and the worst-case
stretch figures clear the 25 ns budget by more than 1.6×. `design/output-stage-sizing.md`
§5's design allocation (≤ 20 ns / ≤ 10 ns of the propagation-delay budget to
the output-stage segment alone) is not disturbed by this — the shift is
attributable to layout interconnect and `uvlo`'s own loading, not the output
stage's own sizing.

**Note on scope**: the end-to-end record also re-measures spec §2.3
thick-oxide gate-ceiling findings on the inter-cell node `IN_DRV` and the
output stage's internal taper nodes (`x2.n1`…`n5`) at the 6 V stretch rail
— these are not spec §3 drive-strength/timing/rise-fall rows and are out of
this report's scope; they are recorded in full in
[`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`](../sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md).
This report does not restate them; they are formally scoped as
`spec/gate-driver.md` §5 exceptions by
[decision record 0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md)
(issue #136), with Exception 3's measured figure since re-stated by
[decision record 0014](../spec/decision-records/0014-xccomp-mim-density-and-series-stack.md)
(issue #192) to match this citation's current record.

## Post-layout coverage: what extraction models, what it does not, and what it does not re-verify (issue #22 item 7)

`sim/gate-driver-core-drive-with-uvlo-postlayout/` re-runs this report's
three spec §3 rows against `layout/gate_driver_core.gds`'s LVS-clean
extraction (now including `uvlo`'s comparator and bias-resistor network,
issue #221) instead of the schematic — following the precedent the
pre-UVLO core cell established (`sim/gate-driver-core-drive-postlayout/`,
still cited below where its own historical figures remain useful context).
Two DUTs exist, built by
[`layout/lvs/mk_extracted_dut.py`](../layout/lvs/mk_extracted_dut.py) from
the same `klt extract` output — see that script's own module docstring
(transforms T1–T9, T9 added by decision record 0019 for `uvlo`'s
`ppolyf_u` bias resistors) and [`layout/README.md`'s "Post-layout
simulation"](../layout/README.md#post-layout-simulation) section for the
full derivation; this section states, for this report's own scope, what
that extraction does and does not model, and whether its coverage matches
the full spec suite.

**What it models** (current-latest, freshness-checked record:
[`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md),
[decision record
0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md),
DUT `layout/lvs/gate_driver_core.extracted-rc.spice`, sha256 matches the
committed file as of `ebbb9e6` (PR #227); supersedes this section's prior
citation of the pre-UVLO
[`sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md`](../sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md)):

- The same active-device SPICE models and the same `tt`/`ff`/`ss`/`fs`/`sf`
  × −40/27/125 °C × two-rail-supply PVT grid as the schematic-level
  `sim/gate-driver-core-drive-with-uvlo/` campaign — the DUT swaps, nothing
  about the corner sweep does.
- 1769 individually-extracted transistor fingers (1105 `nfet` + 664 `pfet`
  drawn devices, rebound to their real `nfet_06v0`/`pfet_06v0`/
  `nfet_03v3`/`pfet_03v3` flavors, T2), the four `XCCOMP*` MiM series
  capacitors, and 271 `ppolyf_u` bias-resistor devices from `uvlo`'s
  `Rref`/`R1`/`R2`/`Rfb` network (new device class, T9, decision record
  0019) — 2044 devices total, matching the LVS-clean signoff
  (`layout/lvs/reports/gate_driver_core/20260826-062806-a7dcce1.lvs.json`,
  2044/2044, 295/295 nets) — plus real, drawn body-tie geometry for both
  device flavors (T4, issue #132).
- Per-net **interconnect parasitics** from `klt extract --parasitics`: a
  single lumped resistance per net, distributed as a star across that net's
  device terminals (6128 R legs in the emitted netlist), plus one
  net-to-ground capacitor per net (295 C) — quasi-static (one
  frequency-independent R and C per net; no skin effect, no
  transmission-line behavior), per the extraction report's own `model`
  field
  (`layout/lvs/reports/gate_driver_core/20260826-062028-a7dcce1.pex-extract.json`
  `parasitics.model`).

**What it does not model**:

- **Net-to-net coupling capacitance.** `klt extract --parasitics` *did*
  compute it for this layout (304 coupling-capacitor pairs, 42.10 fF total,
  vs. 11072.95 fF total net-to-ground capacitance, in the extraction JSON's
  `parasitics` block) — but `mk_extracted_dut.py`'s T5 transform
  deliberately does not emit `parasitics.nets[].coupled` into the simulated
  netlist. This is stated as a scope reduction in both
  `layout/lvs/gate_driver_core.extracted-rc.spice`'s own generated header
  and `layout/README.md`, not a silent drop, but it means the ~42 fF of
  computed coupling on this layout is not part of any postlayout number in
  this report.
- **Distributed (segment-by-segment) RC.** Every net's parasitic is a
  single-hub star (issue #592 model), not a chain of per-segment
  resistors/capacitors — this design declared no `--critical-net`, so the
  finer-grained `--distributed-rc` mode (issue #977) never engaged
  (`distributed_rc: false`, `critical_nets: []` in the extraction JSON).
- **Lateral (same-layer, sidewall) coupling** between any net pair, and
  **parasitic inductance** (`l_count: 0`, `total_inductance_nh: 0.0`) —
  neither is modeled at all for this design, critical-net or not.
- **Corner-dependent parasitics.** The 6128 R / 295 C values come from one
  `klt extract` pass at nominal drawn geometry and are held fixed across
  every one of the 60 PVT points; only the active-device (MOS/BJT/diode/MIM)
  `.lib` corner sections vary process/temperature. Metal sheet resistance
  and dielectric capacitance are not re-derived per process corner.
- **Self-heating** and any other thermal-electrical coupling beyond the
  `.temp`-driven ambient-temperature device models already used at the
  schematic level.

**Whether postlayout coverage matches the full spec suite: no.** The
postlayout campaign covers exactly this report's three spec §3 rows (peak
source/sink current, `tpdlh`/`tpdhl`, rise/fall) end-to-end, on the combined
top-level DUT including `uvlo` — and confirms the same verdict pattern as
the schematic-with-UVLO campaign at every metric it can directly compare
([decision record
0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md)
Findings 1–2, 4): no schematic-passing corner regresses to a post-layout
failure. This includes both of this report's ratified, bounded exceptions —
[decision record
0016](../spec/decision-records/0016-output-stage-stretch-sink-current-shortfall.md)'s
6 V stretch-rail peak-sink shortfall at the same two corners (`ss_125c`
0.8764 A, `sf_125c` 0.9242 A in the RC record above, inside the ≥ 0.85 A
bound) and [decision record
0020](../spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md)'s
nominal peak-source miss at `ss_-40c_vlogic2p97v-vdrv4p50v` (0.4754 A here,
inside the ≥ 0.45 A bound) — and the improvement in the inherited −50 mV
undershoot band that `layout/README.md` attributes to the extracted net
capacitance damping the ringing (0/60 points fail under RC vs. 12/60
parasitic-free). What it does **not** re-verify post-layout:

- **`spec/gate-driver.md` §5 Exception 1** — the level shifter's own
  internal thin-oxide overshoot on `inb` (decision records 0003/0015). No
  `sim/gate-driver-core-drive-with-uvlo-postlayout/` (nor the pre-UVLO
  `sim/gate-driver-core-drive-postlayout/`) record measures `inb`, `na`, or
  `nb` (its per-corner table's measured columns are `trise`/`tfall`/`tpdlh`/
  `tpdhl`/`ipeak_source`/`ipeak_sink`/`vout`/`vin`/`indrv`/`n1`…`n5`/
  `uvlo_lockout_at_in_high`/`uvlo_vout_at_in_high_v`/`uvlo_vdrv_at_in_high_v`
  only — the level shifter's own internal nodes are not on that list). That
  claim's only evidence remains schematic-level,
  `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`, and
  there is no `level-shifter-oxide-safety`-equivalent postlayout facet
  directory today.
- **A standalone, post-layout re-measurement of `uvlo`'s own
  trip/hysteresis/response-time facet** — `uvlo` has no independent top-cell
  boundary in `layout/gate_driver_core.gds` (only per-device leaf cells and
  the flat `gate_driver_core` top), so there is no sub-hierarchy `klt
  extract --top uvlo` could target ([decision record 0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md)
  Finding 6). The closest available post-layout evidence is the full-block,
  per-corner lockout/`OUT`/`VDD_DRV` snapshot cited above.
- **The `spec/low-side-power-switch.md` facet** — no layout exists for that
  facet yet (`layout/` contains only `gate_driver_core.gds`), so its
  `Ron·W`, EM-budget and protection claims have no postlayout counterpart to
  even ask this question of.

This section documents evidence status; it does not itself change any
verdict or spec text, per `CLAUDE.md`'s "no claim without a testbench" and
"spec changes go through `spec/` with a decision record."

## Coverage: what is now end-to-end, and what is not

**All three spec §3 rows this report covers — propagation delay, drive
strength, and rise/fall — are backed by an end-to-end measurement** that
composes the block's real signal path (3.3 V logic `IN` → level shifter →
output stage → `uvlo` → the real 1 nF reference load) as one measured chain,
driven by the real logic-domain input rather than an idealized,
already-level-shifted edge — now the post-layout, complete-block-with-`uvlo`
record cited as this report's primary source (see "Results" above), with the
schematic-level `sim/gate-driver-core-drive/` record that first established
this end-to-end methodology (issue #100) retained as a cross-check.
Concretely, relative to the original per-cell-only version of this report:

- **Propagation delay** was previously two separate partial numbers with no
  composed measurement; it is now one measured end-to-end number per corner
  (see "Results" above) — the gap this report's "Follow-up" section
  previously flagged as blocked on issue #100 is closed.
- **Drive strength and rise/fall** were previously measured against the
  real 1 nF load but with an idealized input edge (the level shifter was
  entirely absent from that circuit); they are now also measured with the
  real level-shifter-driven edge feeding the output stage. Rise/fall did
  not move measurably; drive strength moved by a small (under ~0.5 %),
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
  stretch target (decision record 0016).
- The nominal ±10 % peak-source-current miss at
  `ss_-40c_vlogic2p97v-vdrv4p50v`, present only once `uvlo` is instantiated
  and confirmed unchanged across schematic, post-layout no-RC, and
  post-layout RC facets (decision record 0020). Closing this is coupled to
  closing decision record 0018's own open UVLO false-trip finding, not
  independently addressable — see decision record 0020's "Consequences."
- ~~The new, unratified spec §2.3 thick-oxide ceiling exceedance on
  `IN_DRV`~~ — **resolved by
  [decision record 0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md)**
  (issue #136), which ratifies it as `spec/gate-driver.md` §5's Exception 3
  and corrects Exception 2's cited worst case to the
  larger-than-previously-recorded taper-node figure on `x2.n1`, with the
  exception's measured figure since narrowed and re-stated by [decision
  record 0014](../spec/decision-records/0014-xccomp-mim-density-and-series-stack.md)
  (issue #192) following the `XCCOMP` compensation-stack rework. Both are
  documented in the end-to-end record and not restated in full here because
  they fall outside this report's spec §3 scope (see the scope note at the
  end of "Results"). Decision record 0006 also leaves one item open: a
  deck-fidelity question about whether the harness's default transient
  tolerances resolve narrow coupling transients.
- 16 of 60 points on the inherited, non-spec −50 mV undershoot sanity band
  on the output stage's `x2.n1` taper node, documented in the end-to-end
  record and not restated here for the same reason.

## Links

- Gate-driver-core-drive-with-uvlo-postlayout (primary, RC-extracted) record: [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md)
- Gate-driver-core-drive-with-uvlo-postlayout (no-RC cross-check) record: [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md)
- Gate-driver-core-drive-with-uvlo-postlayout testbench: [`sim/gate-driver-core-drive-with-uvlo-postlayout/testbench/gate_driver_core_uvlo_tb.spice`](../sim/gate-driver-core-drive-with-uvlo-postlayout/testbench/gate_driver_core_uvlo_tb.spice)
- Gate-driver-core-drive-with-uvlo (schematic-level) record: [`sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md`](../sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md)
- Gate-driver-core-drive (pre-UVLO, schematic, superseded as primary source): [`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`](../sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md)
- Gate-driver-core-drive-postlayout (pre-UVLO, extracted, superseded as primary source): [`sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md`](../sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md)
- Extracted DUT netlists: [`layout/lvs/gate_driver_core.extracted-rc.spice`](../layout/lvs/gate_driver_core.extracted-rc.spice), [`layout/lvs/gate_driver_core.extracted.spice`](../layout/lvs/gate_driver_core.extracted.spice); extractor tooling: [`layout/lvs/mk_extracted_dut.py`](../layout/lvs/mk_extracted_dut.py)
- Combined top-level netlist: [`design/netlist/gate_driver_core.spice`](netlist/gate_driver_core.spice) (from issue #98)
- Output-stage-drive record (current): [`sim/output-stage-drive/records/20260817-110340-54fdbf8.md`](../sim/output-stage-drive/records/20260817-110340-54fdbf8.md)
- Output-stage-drive record (superseded): [`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../sim/output-stage-drive/records/20260812-064304-03699ea.md)
- Output-stage-drive testbench: [`sim/output-stage-drive/testbench/output_stage_tb.spice`](../sim/output-stage-drive/testbench/output_stage_tb.spice)
- Output-stage-drive design/sizing notes: [`design/output-stage-sizing.md`](output-stage-sizing.md) (§5's delay-budget allocation, §6's per-cell summary tables)
- Level-shifter-oxide-safety record (current): [`sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md`](../sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md)
- Level-shifter-oxide-safety record (superseded): [`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`](../sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md)
- Level-shifter-oxide-safety testbench: [`sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice`](../sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice)
- Spec: [`spec/gate-driver.md`](../spec/gate-driver.md) §3 (targets), §5 (protection scope / documented exceptions)
- Decision records: [0003](../spec/decision-records/0003-predriver-inverter-oxide-margin-exception.md), [0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md), [0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md), [0014](../spec/decision-records/0014-xccomp-mim-density-and-series-stack.md), [0016](../spec/decision-records/0016-output-stage-stretch-sink-current-shortfall.md), [0018](../spec/decision-records/0018-uvlo-comparator-pvt-measurement.md), [0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md), [0020](../spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md)
- Re-read table: issue #62 (item 8); epic tracking: issue #22; end-to-end campaign: issue #100 (closed, PR #135); this rollup: issue #107; UVLO schematic PVT: issue #220; layout UVLO extension: issue #221 (PR #225); post-layout re-verification with UVLO: issue #222 (PR #227, decision record 0019); this refresh: issue #233
