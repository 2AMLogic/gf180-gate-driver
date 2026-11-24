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

**Refresh note (issue #590, 2026-11-24):** the TL;DR and Results tables
below are re-derived against issue #485's clean-tree re-run of both
post-layout drive facets on the #510-regenerated extraction:
[`20261123-222300-23c67d0`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md)
(with-UVLO, RC — now this report's primary source),
[`20261123-222200-23c67d0`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222200-23c67d0.md)
(with-UVLO, no-RC — now the cross-check), and the pre-UVLO pair
[`20261123-222100-23c67d0`](../sim/gate-driver-core-drive-postlayout/records/20261123-222100-23c67d0.md)
/
[`20261123-222000-23c67d0`](../sim/gate-driver-core-drive-postlayout/records/20261123-222000-23c67d0.md)
(retained for the historical comparison in the "Diagnosis" section). This
retires #485's own re-run note (the tables no longer defer to the records)
and supersedes the 2026-08-26 / 2026-08-18 figures this report previously
quoted as current; those records remain cited below as superseded prior
columns and as the diagnosis controls. What moved with the re-derivation:
RC `tpdlh`/`tpdhl` are ~9–15 % slower than the superseded August RC record;
the two low-rail −40 °C corners (`ss`/`sf` at 2.97/4.50 V) now report
OUT-never-switching as **ERROR** on *both* facets — on the with-UVLO facet
a re-classification of stuck behaviour the 2026-08-26 records already
contained, on the drive facet genuinely new to that facet because its DUT
now contains `uvlo`. Root cause, the regression-window verdict, and the
carried `n1_min_v` / 6 V hot-sink findings are stated in the "Diagnosis"
section below; no `tb.json` bound changed.

## TL;DR

- **Propagation delay** (spec §3: < 50 ns nominal / < 25 ns stretch): a
  single measured end-to-end number (level shifter + output stage + `uvlo`,
  one chain) — worst-case *measured* nominal `tpdlh` 21.14 ns, `tpdhl`
  16.01 ns; worst-case stretch `tpdlh` 17.14 ns, `tpdhl` 13.99 ns; all four
  **PASS** with wide margin against the 50 ns/25 ns budget (worst nominal
  clears its budget by more than 2.3×, worst stretch by ~1.46×), though
  materially slower than every figure this report previously cited — RC
  interconnect parasitics measurably shift propagation delay (decision
  record 0019 Finding 3), and the #510-regenerated extraction adds a
  further +9–15 % on `tpdlh`/`tpdhl` over the superseded August RC record.
  **Timing-coverage caveat**: 2 of the 45 nominal corners — `ss_-40c` and
  `sf_-40c` at 2.97/4.50 V — produce **no** timing value at all (UVLO
  false lockout, OUT never switches; see "Diagnosis" below), so the
  nominal extrema above are over the 43 measured corners; the no-value
  rows are bounded only by *proposed* decision record 0022, not yet
  ratified (`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md`).
- **Drive strength** (spec §3: ≥ 0.5 A peak source/sink, stretch 1 A): met
  at every nominal-tolerance point **except one** — worst-case nominal peak
  source **0.4655 A — FAIL** at `ss_-40c_vlogic2p97v-vdrv4p50v`, inside the
  ratified, bounded exception (decision record 0020, **≥ 0.45 A**, ~3.4 %
  headroom — the tightest reading yet, but per that record only a landing
  below 0.45 A would be a new finding; the corner is fully UVLO-locked,
  not a weakened drive attempt); worst-case nominal peak sink 0.5455 A,
  same corner, **PASS**. At the 6 V stretch rail, peak source clears the
  1 A stretch target by 0.13 % (worst 1.0013 A) but peak sink does
  **not** (worst 0.8626 A, the two hot/slow corners), the same
  pre-existing shortfall this report has tracked since before `uvlo`
  existed, a ratified, bounded exception (decision record 0016,
  **≥ 0.85 A**) — see "Results" below.
- **Rise/fall into the 1 nF reference load** (spec §3: < 50 ns, 10–90 %):
  met at all measured corners with wide margin — worst-case nominal rise
  8.40 ns, worst-case nominal fall 7.66 ns; worst-case stretch rise 6.57 ns,
  fall 6.65 ns — essentially unchanged from the pre-UVLO and August
  with-UVLO figures this report previously cited (within ~0.1 ns; see
  "Results"). The same two UVLO-locked nominal corners carry no rise/fall
  value (caveat above).
- The primary cited record spans the full CLAUDE.md PVT matrix (process
  corners `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C × tied two-rail supply
  point, 60 points — 58 with timing values, the two locked corners above
  excepted) against the #510-regenerated extraction of the LVS-matched,
  RC-parasitic complete-block layout (`layout/gate_driver_core.gds`,
  including `uvlo`); see "Methodology" for the one genuine
  grid-convention difference that remains against the two older per-cell
  records still cross-checked below.

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

Source (primary): [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md)
(`ipeak_source_a` / `ipeak_sink_a` columns), the RC-parasitic-extracted,
post-layout, complete-block-with-`uvlo` record (#485's clean-tree re-run on
the #510-regenerated extraction), full 60-point grid, worst nominal
(45-point, ≤ 5.5 V rail) and worst stretch (15-point, 6.0 V rail) values
read directly from that record's own corner-by-corner result table; no-RC
cross-check:
[`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222200-23c67d0.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222200-23c67d0.md).

| Measurement | Nominal target | Worst-case nominal | Nominal binding corner | Stretch target | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|---|---|
| Peak source current | ≥ 0.5 A (**≥ 0.45 A** at `ss_-40c_vlogic2p97v-vdrv4p50v`, [decision record 0020](../spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md)) | **0.4655 A — FAIL, bounded** (decision record 0020) | `ss_-40c_vlogic2p97v-vdrv4p50v` | ≥ 1 A | 1.0013 A — **PASS** (0.13 % margin) | `ss_125c_vlogic3p30v-vdrv6p00v` |
| Peak sink current | ≥ 0.5 A | 0.5455 A — **PASS** | `ss_-40c_vlogic2p97v-vdrv4p50v` | ≥ 1 A (**≥ 0.85 A**, [decision record 0016](../spec/decision-records/0016-output-stage-stretch-sink-current-shortfall.md)) | **0.8626 A — FAIL, bounded** (decision record 0016) | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means (60-point grid): peak source 1.1266 A, peak sink 0.9964 A. The
nominal binding corner for both rows is one of the two UVLO-locked ERROR
corners (see "Diagnosis"): its current readings are the locked-state
contention transient decision record 0020 characterizes, retained here as
recorded measurements, not drive results — the worst *released* nominal
corners are `ss_125c_vlogic2p97v-vdrv4p50v` (source 0.5803 A, sink
0.5638 A), both **PASS**.

**Decision record 0020 (peak source, nominal)**: at exactly one nominal
±10 % corner, `ss_-40c_vlogic2p97v-vdrv4p50v`, `uvlo`'s comparator is
already fully locked out throughout `IN`'s high pulse
(`uvlo_lockout_at_in_high` = 4.5 V ≈ `VDD_DRV`, `vout_max_v` = 0.2512 V RC /
0.2412 V no-RC — `OUT` stays at about a quarter of a volt, the RC peak
just above 0.25 V) — the
measured current is a sub-nanosecond contention-current transient between
the output driver and the already-engaged UVLO pulldown, not a sustained
charge-delivery attempt. Decision record 0020 bounds this specific corner
at **≥ 0.45 A**; the November facets read 0.465489 A (RC) and 0.498025 A
(no-RC) there — the RC value is the tightest reading yet, below the
August facets' 0.475414–0.499696 A range but still inside the bound with
~3.4 % headroom, so per that record's own rule (only a landing below
0.45 A is a new finding) the exception holds unchanged. No other nominal
±10 % corner misses the ≥ 0.5 A target. This finding is inherited from
issue #220's schematic-level UVLO measurement
(`sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md`,
0.499165 A at the same corner) and is unchanged in kind across every
facet since.

**Decision record 0016 (peak sink, 6 V stretch, carried forward)**: the
stretch-rail sink-current shortfall this report has tracked since before
`uvlo` existed is unchanged in mechanism — decision record 0016 bounds the
two hot/slow corners (`ss_125c`/`sf_125c` at `vdrv6p00v`) at **≥ 0.85 A**;
the November RC record measures 0.862625 A / 0.908398 A there (no-RC:
0.878891 A / 0.921416 A), all inside the bound. Peak source at the 6 V
stretch rail continues to clear its own ≥ 1 A target (worst 1.0013 A RC,
1.0076 A no-RC, same binding corner as the sink shortfall — the RC margin
has narrowed from the August record's 1.0040 A to 0.13 %, worth watching
on any future re-run, but still a PASS).

**Cross-check against the schematic-with-UVLO, no-RC and drive facets**:
the schematic-level item-5 envelopes
(`sim/gate-driver-core-drive-with-uvlo/klt/envelopes/20261028-d7a2b69-*`,
see `verification/signoff/README.md` § "Item 5") encode the same two
ratified exceptions at the same corners, and the November no-RC and
pre-UVLO-drive records agree with the RC record at every non-locked corner
within the few-percent deltas their own comparison tables record. The
drive facet's November values are identical to the with-UVLO facet's on
every shared column — both facets run the same extracted DUT and stimulus,
so the drive facet is now a same-DUT replication, not an independent
no-UVLO control (the "Diagnosis" section uses the 2026-08-18 records for
that role). Resolving either shortfall is a design change, not a
verification task (decision records 0016 and 0020).

### Rise/fall into the 1 nF reference load (spec §3: < 50 ns, 10–90 %)

Source (primary): same complete-block-with-`uvlo` post-layout RC record
(`20261123-222300-23c67d0`), `trise_s` / `tfall_s` columns, full 60-point
grid, worst nominal/stretch values read the same way as the drive strength
table above (rise/fall have no separate stretch target in §3, so only one
column applies at each rail); no-RC cross-check: `20261123-222200-23c67d0`.

| Measurement | Worst-case nominal | Nominal binding corner | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|
| 10–90 % rise time | 8.40 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | 6.57 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| 10–90 % fall time | 7.66 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | 6.65 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means (60-point grid): rise 5.16 ns, fall 5.09 ns (timing means over
the 58 corners that produce timing values). The two UVLO-locked nominal
corners (`ss`/`sf` −40 °C, 2.97/4.50 V) produce no rise/fall value — see
"Diagnosis".

**Cross-check against the pre-UVLO schematic/post-layout and August
with-UVLO facets**: this report previously cited a pre-UVLO end-to-end
schematic worst-case of rise 8.37 ns / fall 7.53 ns
(`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`), a
pre-UVLO post-layout RC worst-case in the same range
(`sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md`),
and an August with-UVLO RC worst-case of 8.42 ns / 7.59 ns
(`20260826-072640-a7dcce1`). The November with-UVLO numbers above (8.40 /
7.66 ns) are unchanged within ~0.1 ns — `uvlo`'s comparator and bias
network sit off the `IN`→`OUT` signal path and the extraction regeneration
does not materially load the output stage's own, load-dominated rise/fall
into 1 nF, consistent with decision record 0019 Finding 3's own observation
that RC parasitics move `trise_s`/`tfall_s` by only tens of picoseconds.

### Propagation delay (spec §3: < 50 ns nominal, < 25 ns stretch)

This row is a single measured end-to-end number — the level shifter, output
stage, and `uvlo` composed into one chain, `IN` → `OUT`, against the
extracted, LVS-matched, RC-parasitic complete-block layout. Source
(primary): same complete-block-with-`uvlo` post-layout RC record
(`20261123-222300-23c67d0`), `tpdlh_s` / `tpdhl_s` columns, full 60-point
grid, worst nominal/stretch values read the same way as the drive strength
table above; no-RC cross-check: `20261123-222200-23c67d0`.

| Measurement | Nominal target | Worst-case nominal | Nominal binding corner | Stretch target | Worst-case stretch | Stretch binding corner |
|---|---|---|---|---|---|---|
| Low→high propagation delay (`tpdlh`) | < 50 ns | 21.14 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | < 25 ns | 17.14 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |
| High→low propagation delay (`tpdhl`) | < 50 ns | 16.01 ns — **PASS** | `ss_125c_vlogic2p97v-vdrv4p50v` | < 25 ns | 13.99 ns — **PASS** | `ss_125c_vlogic3p30v-vdrv6p00v` |

Grid means (60-point grid): `tpdlh` 13.60 ns, `tpdhl` 10.94 ns.

**Timing coverage**: the worst-case nominal figures above are over the **43
of 45** nominal corners that produce a timing value; `ss_-40c` and `sf_-40c`
at 2.97/4.50 V produce none (UVLO false lockout — see "Diagnosis"; bounded
only by proposed decision record 0022, not yet ratified, so this report
does not score them as anything other than open ERROR rows). All 15 stretch
corners are measured.

**RC parasitics materially shift this row**, and the #510 regeneration
added a step further: per decision record 0019 Finding 3, `tpdlh_s` shifts
+5.4 to +12.1 ns and `tpdhl_s` +4.1 to +8.1 ns once interconnect RC
parasitics and `uvlo` are both in the loop (comparing the August no-RC and
RC complete-block-with-`uvlo` facets directly); the November RC record then
adds another +1.07 to +2.03 ns on `tpdlh_s` and +0.93 to +1.48 ns on
`tpdhl_s` (mean +11.9 % on both) against the superseded August RC record
across the 58 comparable corners, and its no-RC facet is within ~0.6 % of
the August no-RC record — so the further shift is an RC-extraction
difference, not a circuit change. Every measured corner still clears its
target with wide margin — the worst-case nominal figures above clear the
50 ns budget by more than 2.3×, and the worst-case stretch figures clear
the 25 ns budget by ~1.46×. `design/output-stage-sizing.md` §5's design
allocation (≤ 20 ns / ≤ 10 ns of the propagation-delay budget to the
output-stage segment alone) is not disturbed by this — the shift is
attributable to layout interconnect and `uvlo`'s own loading, not the
output stage's own sizing.

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

## Diagnosis: the ss/sf −40 °C low-rail ERROR corners (issue #590)

Issue #485's re-run of both drive post-layout facets against the
#510-regenerated extraction left two corners at the low-line operating
point `vlogic2p97v-vdrv4p50v`, −40 °C, with **no value** for
`trise_s`/`tfall_s`/`tpdlh_s`/`tpdhl_s` on every one of the four records
(RC and no-RC, drive and with-UVLO): `ss_-40c_vlogic2p97v-vdrv4p50v` and
`sf_-40c_vlogic2p97v-vdrv4p50v`, `vout_max_v` pinned at 0.2512/0.3485 V
(RC) and 0.2412/0.3342 V (no-RC) — OUT never switches. #485 reported them
without diagnosing them; this section is the diagnosis. It cites only
committed measurements — the #485 records' own per-corner lockout probes
and single-corner harness probes, and the standalone trip-verification
evidence decision record 0018 ratifies — so it adds no unrecorded claim.

### Root cause: the UVLO comparator, not the drive path

The with-UVLO facet records a three-probe lockout snapshot at every
corner. At exactly the two ERROR corners the comparator is fully asserted
throughout `IN`'s high pulse, while the `tt` control at identical rails
and temperature is released and switches normally
([`20261123-222300-23c67d0`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md),
RC — the no-RC record
[`20261123-222200-23c67d0`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222200-23c67d0.md)
shows the same lockout at slightly lower levels, 0.241168/0.334197 V at
ss/sf):

| Process (−40 °C, 2.97/4.50 V) | Lockout while IN high | Peak OUT (RC / no-RC) | Four timing measurements |
|---|---:|---:|---|
| ss | 4.50 V (locked) | 0.251249 / 0.241168 V | no value |
| sf | 4.50 V (locked) | 0.348534 / 0.334197 V | no value |
| tt | ≈ 0 V (−2.1 × 10⁻⁷, released) | 4.5043 V (RC) | all present |

In the RC record, `uvlo_vout_at_in_high_v` — OUT sampled at 200 ns, after
`IN` rises at 20 ns — reads 0.250417/0.347807 V at ss/sf, within 1 mV of
the respective `vout_max_v` maxima. OUT therefore sits at a low, stuck
level for the whole pulse: this is the output level measured during
lockout, the output driver held down by the already-engaged UVLO pulldown
(`MPD`, `nfet_06v0`
W = 10 µm m = 800, sized in `design/uvlo-comparator-sizing.md`
specifically to dominate the output stage's own strongest device). The
transient interpretation of decision record 0020 applies to the *peak
current* (`ipeak_source_a`) at this corner, not to the OUT level. The drive path itself is not implicated: in the
same rows, `indrv_max_v` and every taper node `n1`…`n5` swing to full rail
(e.g. ss row: `indrv_max_v` 4.50002 V, `n1_max_v` 4.50538 V).

**Device-level cause — decision record 0018 Finding 2's open false-trip
finding.** The standalone trip facet measured the comparator's thresholds
directly (decision record 0018, ratified): at `ss`/−40 °C the
falling/rising thresholds are 4.737/5.115 V and at `sf`/−40 °C they are
4.526/4.876 V — every one above the 4.50 V rail these corners are biased
at, so the comparator never releases and holds lockout for the entire
transient. The mechanism is decision record 0018 Finding 1's: the ~5×
divider gain amplifies the diode-connected `Vt` reference's process *and*
temperature spread into a ~2.5 V peak-to-peak falling-threshold spread
(2.231–4.737 V, a 2.506 V span across the 15-point PVT grid), so at the slow/cold corners
the trip point sits above the spec's own −10 % low-line floor (4.50 V) —
precisely the false-trip failure mode decision record 0001 Decision 4's
margin rationale ("the worst-case-high rising threshold… sits 300 mV below
the 4.50 V low-line floor") was written against. Decision record 0018
keeps this open as an unresolved safety finding rather than a bounded
exception, and its full-block schematic corroboration already named these
exact two corners as "the only two of 60 points" that lock at `vdrv4p50v`.

**Route- and extraction-independence (the probe criterion).** Each #485
record carries a single-corner local harness probe reproducing its batch
envelope on the shared DUT to the printed digits (RC: `vout_max_v`
0.251249 V, `n1_min_v` −0.00274481 V, `ipeak_source_a` 0.465489 A; no-RC:
0.241168 V / −0.0528776 V / 0.498025 A) — the DUT, not the batch route.
The stuck levels also agree across the no-RC and RC DUTs to within
10.081 mV (ss) and 14.337 mV (sf) of each other, so interconnect parasitics are not the cause
either. The committed lockout measurements above are the probe record
this issue's acceptance criteria ask for; no additional targeted probe
was needed to close the causal attribution.

### Regression-window verdict: the corner never worked post-UVLO

On `gate-driver-core-drive-postlayout` the same two corners **are** a
verdict regression — the facet's superseded 2026-08-18 records
([`20260818-111748-af13899`](../sim/gate-driver-core-drive-postlayout/records/20260818-111748-af13899.md)
no-RC,
[`20260818-112446-af13899`](../sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md)
RC) show both corners switching normally (`vout_max_v` 4.50571/4.50552 V
no-RC; 4.50538/4.50496 V RC, with measured timing; RC PASS with clean
`n1_min_v`; no-RC `ss` an overall FAIL on its −0.0531022 V undershoot
alone, `sf` PASS). The evidence places the regression in **the 2026-08-26 UVLO
instantiation in the layout, not the 2026-11 extraction regeneration**:

- **DUT contents, 2026-08-18 (`af13899` era)**: the pre-UVLO extraction —
  959 transistor fingers plus the four `XCCOMP*` MiM caps, no comparator,
  no OUT pulldown, no bias-resistor network. UVLO lockout is not merely
  inactive at these corners in that DUT; it is *impossible* — there is no
  `uvlo` in it. Those corners passed because nothing could trip.
- **DUT contents, 2026-08-26 on (`a7dcce1` → current)**: issue #221
  (commit `a7dcce1a`) extended `gate_driver_core.gds` with the `uvlo`
  sub-cell, and commit `ebbb9e6c` (PR #227) re-extracted the DUT from it
  — 1769 transistor fingers (1105 `nfet` + 664 `pfet`), the 4 MiM caps,
  and 271 `ppolyf_u` bias resistors = 2044 devices, the LVS-matched
  census the current extraction still carries. The with-UVLO records
  taken on that extraction
  ([`20260826-063405-a7dcce1`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md)
  no-RC,
  [`20260826-072640-a7dcce1`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md)
  RC) **already show both corners stuck at the same levels** the November
  records reproduce (0.241182/0.334204 V no-RC; 0.244517/0.338903 V RC).
  From the first extraction containing `uvlo`, the corner never switched.
- **What changed in November is the classification, not the behaviour.**
  The harness's measured-swing monitors read degenerate sub-nanosecond
  "timing" values off the ~0.24–0.39 V stuck level (the August RC record's
  rise times there were sub-ns, `trise_s` 8.16 × 10⁻¹⁰ s at the ss corner,
  8.54 × 10⁻¹⁰ s at sf, while its low-to-high propagation readings were
  11.47/9.45 ns), so the 2026-08-26 records verdicted those corners FAIL/PASS.
  The #485 batch route's rail-normalised 10/50/90 % crossings — the
  pre-registered `klt/README.md` method, the same one behind the item-5
  envelopes — report *no value* for a block that never reaches 90 % of
  the rail, i.e. ERROR. On the with-UVLO facet that re-classified
  existing stuck behaviour; on the drive facet both behaviour and verdict
  are new to the facet, because the facet's DUT content caught up with
  the block: both November facets share one extracted DUT per RC setting,
  and their per-corner values are identical on every shared column.
- **The #510 regeneration is not the cause.** The regenerated extraction
  (report
  `layout/lvs/reports/gate_driver_core/20261114-194121-cbf0cd4.pex-extract.json`,
  from the unchanged `15fa5b64` GDS) carries an identical device/parasitic
  census to the 2026-08-26 one (2044 devices, 6128 R legs / 295 C) apart
  from tool version, and it moved the stuck levels only mV-scale
  (no-RC by ≤ 15 µV; RC by 6.7/9.6 mV). A regeneration cannot produce a
  behaviour the very first post-UVLO extraction already exhibited.

**Verdict:** the with-UVLO 2026-08-26 layout change (the UVLO
instantiation, issue #221) is responsible for the drive-facet regression
in the strict sense that no extraction containing `uvlo` has ever switched
at `ss`/`sf` −40 °C 2.97/4.50 V — the corner never worked post-UVLO; the
#456/#510 regeneration merely re-exposed and re-classified it. Closing it
means closing decision record 0018 Finding 2 — the deferred
reference-topology redesign decision records 0018 and 0020 already scope
as multi-PR work with its own re-verification pass — not touching the
drive path, the harness, or the extraction.

### Carried-over secondary findings (reported here, not diagnosed)

- **`n1_min_v` undershoot, no-RC DUT only.** 9 of 60 no-RC measurements
  (each November no-RC record) are below the inherited −50 mV sanity band
  on the output stage's `x2.n1` taper node, worst −0.0529 V at
  `ss_-40c_vlogic3p30v-vdrv5p00v`. Eight are the corners listed in the
  records' Finding 2 (which fails them); the ninth,
  `ss_-40c_vlogic2p97v-vdrv4p50v` (−0.0528776 V), is classified ERROR
  because its timing is missing, so Finding 2 does not list it. The count
  is reproducible per record with
  `awk -F'|' '$2 ~ /vlogic/ && $16 != "" && $16+0 < -0.05 {n++} END {print n+0}' "$record"`.
  The superseded no-RC records (`20260818-111748-af13899`,
  `20260826-063405-a7dcce1`) have 12/60 below the band (−0.0500…−0.0537 V),
  a superset of the nine; the three that moved inside the band are
  `ss_125c` at 2.97/4.50 V, 3.30/5.00 V and 3.30/6.00 V. The August 18
  control at `ss_-40c_vlogic2p97v-vdrv4p50v` switched to 4.50571 V with
  valid timing, but its −0.0531022 V undershoot gave it an overall FAIL;
  that verdict became ERROR in November (timing missing). The measurement
  is carried over; the verdict changes are listed in "Diagnosis". The
  RC DUT is clean (worst −0.0035 V): the extracted net capacitance damps
  the ringing. This is a non-spec sanity band, not a §3 row; no bound is
  changed, and circuit changes are outside this report.
- **6 V stretch hot sink-current misses.** `ss_125c_vlogic3p30v-vdrv6p00v`
  0.8626 A and `sf_125c_vlogic3p30v-vdrv6p00v` 0.9084 A (RC; no-RC
  0.8789/0.9214 A) miss the ≥ 1 A stretch target — decision record 0016's
  ratified bounded exception (≥ 0.85 A), carried forward from every
  superseded record (see "Results"). #557 owns the separate ss/27 °C
  layout-attribution work on the `klt pex` extracted leg (T1 item 7's
  0.9996 A miss); that miss belongs to item 7's report, not these records.

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
[`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md),
issue #485's clean-tree re-run; DUT `layout/lvs/gate_driver_core.extracted-rc.spice`,
sha256 `2c3cd778…`, the #510-regenerated extraction of the unchanged
`15fa5b64` GDS, report
`layout/lvs/reports/gate_driver_core/20261114-194121-cbf0cd4.pex-extract.json`;
supersedes this section's prior citation of the 2026-08-26
[`20260826-072640-a7dcce1`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md)
(decision record
[0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md)'s
record), which itself superseded the
pre-UVLO
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
  (`layout/lvs/reports/gate_driver_core/20261024-090826-de97a29.lvs.json`,
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
  compute it for this layout (304 coupling-capacitor pairs, 41.90 fF total,
  vs. 16053.57 fF total net-to-ground capacitance, in the extraction JSON's
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
top-level DUT including `uvlo`. Against the schematic-level evidence
(decision record 0019 Findings 1–2, 4 for the 2026-08-26 generation; the
item-5 envelopes and the #485 records for the current one), no
schematic-switching corner regresses to a post-layout failure: the November
records' verdict changes against their August predecessors are the
two UVLO-locked low-line corners (both RC records; the no-RC records also
record FAIL → PASS at `ss_125c` on the 4.50 V and 5.00 V rails, where the
no-RC undershoot moved inside the −50 mV band — see "Diagnosis"), and the schematic-level
item-5 envelopes error the same four timing rows at the same two corners
(`verification/signoff/README.md` § "Item 5") — the lockout is a circuit
property, not an extraction artifact. This includes both of this report's
ratified, bounded exceptions — [decision record
0016](../spec/decision-records/0016-output-stage-stretch-sink-current-shortfall.md)'s
6 V stretch-rail peak-sink shortfall at the same two corners (`ss_125c`
0.8626 A, `sf_125c` 0.9084 A in the RC record above, inside the ≥ 0.85 A
bound) and [decision record
0020](../spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md)'s
nominal peak-source miss at `ss_-40c_vlogic2p97v-vdrv4p50v` (0.4655 A
here, inside the ≥ 0.45 A bound — the tightest reading yet) — and the
improvement in the inherited −50 mV undershoot band that `layout/README.md`
attributes to the extracted net capacitance damping the ringing (0/60
points below the band under RC vs. 9/60 parasitic-free, all ss-family; see
"Diagnosis"). What it does **not** re-verify post-layout:

- ~~**`spec/gate-driver.md` §5 Exception 1** — the level shifter's own
  internal thin-oxide overshoot on `inb` (decision records 0003/0015). No
  `sim/gate-driver-core-drive-with-uvlo-postlayout/` (nor the pre-UVLO
  `sim/gate-driver-core-drive-postlayout/`) record measures `inb`, `na`, or
  `nb` (its per-corner table's measured columns are `trise`/`tfall`/`tpdlh`/
  `tpdhl`/`ipeak_source`/`ipeak_sink`/`vout`/`vin`/`indrv`/`n1`…`n5`/
  `uvlo_lockout_at_in_high`/`uvlo_vout_at_in_high_v`/`uvlo_vdrv_at_in_high_v`
  only — the level shifter's own internal nodes are not on that list). That
  claim's only evidence remained schematic-level,
  `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`, and
  there was no `level-shifter-oxide-safety`-equivalent postlayout facet
  directory.~~ **Resolved by `sim/level-shifter-oxide-safety-postlayout/`**
  (issue #235): the schematic facet's full measurement set
  (`vgate_thinox_max`, `vna_peak`, `vnb_peak`, `vccomp_dev_max`/
  `vccomp_stack_max`, `t_plh_ns`/`t_phl_ns`, the two functional ratios) is
  now ported to the flat, hierarchy-prefixed node names (`x1_inb`, `x1_na`,
  `x1_nb`, `IN_DRV`) the whole-block extracted DUT
  (`layout/lvs/gate_driver_core.extracted{,-rc}.spice`) uses — the level
  shifter has no independent top-cell boundary in `layout/gate_driver_core.gds`
  ([decision record
  0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md)
  Finding 6 records the same fact for `uvlo`), so this facet reuses the
  same whole-block DUT `sim/gate-driver-core-drive-with-uvlo-postlayout/`
  runs against, not a standalone extracted level shifter. The four
  extracted `XCCOMP` series-stack inter-cap nodes (`nccomp1`/`nccomp2`/
  `nccomp3` in the schematic) have no schematic-level port name of their
  own, so `klt extract` reports them as anonymous nets; per this facet's
  testbench header they are real, reproducible, directly-probeable
  `ANON<N>` nodes in both committed extracted netlists (not silently
  dropped), so `vccomp_dev_max`/`vccomp_stack_max` port unchanged too. Both
  DUT variants reproduce the same verdict pattern as the schematic facet
  (15/60 points FAIL the uniform 3.63 V check at the `vlogic3p63v` +10 %
  corner, decision record 0003/0015's ratified Exception 1) and stay
  inside decision record 0015's ≤ 3.670 V bound: worst `inb` excursion
  3.66471 V (34.71 mV over the 3.63 V rail, no-RC, binding corner
  `ss_125c_vlogic3p63v-vdrv5p50v`, matching the schematic facet's own
  binding corner) and 3.64277 V (12.77 mV over rail, RC, binding corner
  `ss_-40c_vlogic3p63v-vdrv5p50v` — RC parasitics shrink the overshoot by
  roughly an order of magnitude and shift the binding corner from
  `ss_125c` to `ss_-40c`, both records' own "Finding" sections have the
  full per-corner comparison table). `vna_peak`/`vnb_peak` stay comfortably
  under the 3.63 V ceiling at all 60 points in both DUTs (worst 2.7716 V /
  2.75254 V no-RC, 2.72318 V / 2.63639 V RC). Records:
  [`sim/level-shifter-oxide-safety-postlayout/records/20260910-011224-b6ec657.md`](../sim/level-shifter-oxide-safety-postlayout/records/20260910-011224-b6ec657.md)
  (no-RC),
  [`sim/level-shifter-oxide-safety-postlayout/records/20260910-021137-b6ec657.md`](../sim/level-shifter-oxide-safety-postlayout/records/20260910-021137-b6ec657.md)
  (RC).
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
  post-layout RC facets (decision record 0020; the November RC facet reads
  0.4655 A, the tightest yet, still inside the ≥ 0.45 A bound). Closing
  this is coupled to closing decision record 0018's own open UVLO
  false-trip finding, not independently addressable — see decision record
  0020's "Consequences."
- The two UVLO-locked low-line corners (`ss`/`sf` −40 °C, 2.97/4.50 V)
  produce no timing, rise/fall value on either post-layout facet — the
  ERROR rows the "Diagnosis" section attributes to decision record 0018
  Finding 2's false trip. They have **no ratified exception**: draft
  decision record 0022 (proposed, awaiting operator ratification) is the
  pending per-row bound. They stay open ERROR rows until 0018 Finding 2
  closes.
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
- The inherited, non-spec −50 mV undershoot sanity band on the output
  stage's `x2.n1` taper node: 16 of 60 points on the pre-UVLO schematic
  end-to-end record (`20260818-060517-673fcf0`), and — carried over
  carried over from the superseded extractions (12/60 there) — 9 ss-family
  corners on the post-layout **no-RC** DUT (worst −0.0529 V; eight fail the
  band, the ninth is ERROR on missing timing; the RC DUT has none). See
  "Diagnosis" for the no-RC-only attribution.

## Links

- Gate-driver-core-drive-with-uvlo-postlayout (primary, RC-extracted, #485 re-run on the #510-regenerated extraction) record: [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222300-23c67d0.md)
- Gate-driver-core-drive-with-uvlo-postlayout (no-RC cross-check, #485 re-run) record: [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222200-23c67d0.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20261123-222200-23c67d0.md)
- Gate-driver-core-drive-postlayout (pre-UVLO facet, #485 re-run — historical comparison for the "Diagnosis" section) records: [`20261123-222100-23c67d0`](../sim/gate-driver-core-drive-postlayout/records/20261123-222100-23c67d0.md) (RC), [`20261123-222000-23c67d0`](../sim/gate-driver-core-drive-postlayout/records/20261123-222000-23c67d0.md) (no-RC)
- Gate-driver-core-drive-with-uvlo-postlayout (RC, superseded 2026-08-26): [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-072640-a7dcce1.md)
- Gate-driver-core-drive-with-uvlo-postlayout (no-RC, superseded 2026-08-26): [`sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md`](../sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-063405-a7dcce1.md)
- Gate-driver-core-drive-with-uvlo-postlayout testbench: [`sim/gate-driver-core-drive-with-uvlo-postlayout/testbench/gate_driver_core_uvlo_tb.spice`](../sim/gate-driver-core-drive-with-uvlo-postlayout/testbench/gate_driver_core_uvlo_tb.spice)
- Gate-driver-core-drive-with-uvlo (schematic-level) record: [`sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md`](../sim/gate-driver-core-drive-with-uvlo/records/20260826-013137-6299c36.md)
- Gate-driver-core-drive (pre-UVLO, schematic, superseded as primary source): [`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`](../sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md)
- Gate-driver-core-drive-postlayout (pre-UVLO, extracted, superseded 2026-08-18 controls for the "Diagnosis" section): [`20260818-112446-af13899`](../sim/gate-driver-core-drive-postlayout/records/20260818-112446-af13899.md) (RC), [`20260818-111748-af13899`](../sim/gate-driver-core-drive-postlayout/records/20260818-111748-af13899.md) (no-RC)
- Extracted DUT netlists: [`layout/lvs/gate_driver_core.extracted-rc.spice`](../layout/lvs/gate_driver_core.extracted-rc.spice), [`layout/lvs/gate_driver_core.extracted.spice`](../layout/lvs/gate_driver_core.extracted.spice); extractor tooling: [`layout/lvs/mk_extracted_dut.py`](../layout/lvs/mk_extracted_dut.py)
- Combined top-level netlist: [`design/netlist/gate_driver_core.spice`](netlist/gate_driver_core.spice) (from issue #98)
- Output-stage-drive record (current): [`sim/output-stage-drive/records/20260817-110340-54fdbf8.md`](../sim/output-stage-drive/records/20260817-110340-54fdbf8.md)
- Output-stage-drive record (superseded): [`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../sim/output-stage-drive/records/20260812-064304-03699ea.md)
- Output-stage-drive testbench: [`sim/output-stage-drive/testbench/output_stage_tb.spice`](../sim/output-stage-drive/testbench/output_stage_tb.spice)
- Output-stage-drive design/sizing notes: [`design/output-stage-sizing.md`](output-stage-sizing.md) (§5's delay-budget allocation, §6's per-cell summary tables)
- Level-shifter-oxide-safety record (current): [`sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md`](../sim/level-shifter-oxide-safety/records/20260817-010243-2165a49.md)
- Level-shifter-oxide-safety record (superseded): [`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`](../sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md)
- Level-shifter-oxide-safety testbench: [`sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice`](../sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice)
- Level-shifter-oxide-safety-postlayout record (no-RC): [`sim/level-shifter-oxide-safety-postlayout/records/20260910-011224-b6ec657.md`](../sim/level-shifter-oxide-safety-postlayout/records/20260910-011224-b6ec657.md)
- Level-shifter-oxide-safety-postlayout record (RC): [`sim/level-shifter-oxide-safety-postlayout/records/20260910-021137-b6ec657.md`](../sim/level-shifter-oxide-safety-postlayout/records/20260910-021137-b6ec657.md)
- Level-shifter-oxide-safety-postlayout testbench: [`sim/level-shifter-oxide-safety-postlayout/testbench/gate_driver_core_level_shifter_oxide_tb.spice`](../sim/level-shifter-oxide-safety-postlayout/testbench/gate_driver_core_level_shifter_oxide_tb.spice)
- Spec: [`spec/gate-driver.md`](../spec/gate-driver.md) §3 (targets), §5 (protection scope / documented exceptions)
- Decision records: [0003](../spec/decision-records/0003-predriver-inverter-oxide-margin-exception.md), [0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md), [0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md), [0014](../spec/decision-records/0014-xccomp-mim-density-and-series-stack.md), [0016](../spec/decision-records/0016-output-stage-stretch-sink-current-shortfall.md), [0018](../spec/decision-records/0018-uvlo-comparator-pvt-measurement.md), [0019](../spec/decision-records/0019-postlayout-pvt-reverification-complete-block.md), [0020](../spec/decision-records/0020-uvlo-locked-corner-ipeak-source-artifact.md), [0022](../spec/decision-records/0022-uvlo-low-line-lockout-no-value-timing-rows.md) (proposed, unratified)
- Re-read table: issue #62 (item 8); epic tracking: issue #22; end-to-end campaign: issue #100 (closed, PR #135); this rollup: issue #107; UVLO schematic PVT: issue #220; layout UVLO extension: issue #221 (PR #225); post-layout re-verification with UVLO: issue #222 (PR #227, decision record 0019); this refresh: issue #233; Exception 1 post-layout re-verification: issue #235; the #485 re-run: issue #485 (PR #591); this re-derivation and the ERROR-corner diagnosis: issue #590
