# Block-level performance characterization vs. spec §3 (issue #101)

This report aggregates `spec/gate-driver.md` §3's block-level performance
rows — drive strength, propagation delay, rise/fall — into one place, with
citations to the raw evidence behind each verdict. It exists because those
results currently live only inside their own per-experiment raw tables
(`sim/output-stage-drive/records/`, `sim/level-shifter-oxide-safety/records/`)
and were never rolled up against spec §3's own rows (`#62`'s re-read, item 8).

**No claim without a testbench.** Every number below is a simulated result
recorded under `sim/output-stage-drive/` or `sim/level-shifter-oxide-safety/`
(both append-only per `sim/README.md`); nothing here is re-derived or
re-simulated, only cited. `spec/gate-driver.md` is unchanged by this issue.

**This report is explicitly not end-to-end.** Read "Coverage: per-cell only,
not end-to-end" below before treating any row as a verified block-level
number — see that section for exactly what is and is not measured yet, and
why. In short: the two campaigns cited here exercise the level shifter and
the output stage as **separate cells with idealized boundary conditions**,
never as one composed chain from the block's actual 3.3 V logic input to its
5 V/6 V drive output. Item 5 / issue #100's end-to-end PVT campaign is the
one that will close that gap; this report should be revisited once it lands
(see "Follow-up" below).

## TL;DR

- **Drive strength** (spec §3: ≥ 0.5 A peak source/sink, stretch 1 A): met
  at all 60 measured PVT corners — worst-case peak source 0.5877 A, worst-case
  peak sink 0.5737 A (`sim/output-stage-drive/records/20260812-064304-03699ea.md`).
- **Rise/fall into the 1 nF reference load** (spec §3: < 50 ns, 10–90 %):
  met at all 60 measured corners with wide margin — worst-case rise 8.36 ns,
  worst-case fall 7.53 ns, same record.
- **Propagation delay** (spec §3: < 50 ns nominal / < 25 ns stretch): the
  *output-stage-only* segment meets it with wide margin (worst case 5.88 ns);
  the *level-shifter-only* segment is sub-nanosecond (worst case 1.13 ns).
  Neither of these two numbers is the spec's own end-to-end quantity, and no
  simulation currently composes them into one chain — see "Coverage" below.
  A naive sum of the two worst cases (≈ 7.0 ns) stays far under budget, but
  that sum is an analytical bound over two separately-loaded, separately-driven
  partial results, not a measured number, and is not treated as a verified
  result in this report.
- Both records span the full CLAUDE.md PVT matrix (process corners `tt`/
  `ff`/`ss`/`fs`/`sf` × −40/27/125 °C × supply tolerance, 60 points each).

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

Two independent, per-cell campaigns exist today. Neither one alone, nor a
sum of the two, is the spec's own end-to-end measurement — see "Coverage"
below for why.

### `sim/output-stage-drive/` — the output stage only

- **DUT**: `design/output_stage.sch` (the thick-oxide taper/output driver,
  entirely `nfet_06v0`/`pfet_06v0` per spec §2.5), driving spec §3's actual
  1 nF reference load.
- **Stimulus (`IN_DRV`)**: an **idealized, already-level-shifted,
  rail-referenced** pulse — 0 → `vdrv_val` with a 1 ns 0–100 % edge,
  *"representing a reasonably fast level-shifter output"* (testbench's own
  comment, `sim/output-stage-drive/testbench/output_stage_tb.spice`). This is
  a testbench **assumption**, not a measured level-shifter edge rate — the
  level shifter is not present in this circuit at all; `IN_DRV` bypasses it
  entirely.
- **Grid**: 60 points — `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C ×
  `vdrv` ∈ {4.50, 5.00, 5.50, 6.00 V} (nominal ±10 % plus the 6 V stretch
  rail).
- **Record**: [`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../sim/output-stage-drive/records/20260812-064304-03699ea.md),
  overall **PASS**. One caveat that is *not* visible in that record's own
  pass/fail column: its internal-node limits are written against the PDK's
  6.6 V overshoot bias, so the record reads PASS on `n1`…`n5` even though
  those taper nodes transiently exceed **spec §2.3's stricter adopted 6.0 V
  DC gate ceiling** at the 6 V stretch rail (worst case `n5` = 6.0538 V at
  `ss_27c_vdrv6p00v`, margin −53.8 mV). That excursion is formally narrowed
  by [decision record 0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md)
  and is an oxide-safety finding, not a drive-strength or timing one — it
  does not affect the rows this report cites, but it is stated here so this
  record's "PASS" is not read as unqualified.

### `sim/level-shifter-oxide-safety/` — the level shifter only

- **DUT**: `design/netlist/level_shifter.spice` (the cascode/clamped level
  shifter, spec §4), driving a **20 fF placeholder** load, explicitly
  flagged in its own testbench as *"a placeholder representative pre-driver
  input gate capacitance, not a measured [output-stage] number"*
  (`sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice`) —
  written before `sim/output-stage-drive/` existed, and not refreshed against
  the output stage's real input capacitance since.
- **Stimulus (`IN`)**: an ideal 3.3 V-logic-domain pulse, the block's actual
  logic input swing.
- **Grid**: 60 points — `tt`/`ff`/`ss`/`fs`/`sf` × −40/27/125 °C ×
  (`vlogic` ∈ {2.97, 3.30, 3.63 V}, `vdrv` ∈ {4.50, 5.00, 5.50, 6.00 V},
  tied per `sim/README.md`'s tied-supply-grid convention).
- **Record**: [`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`](../sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md),
  overall **FAIL** — but that FAIL is entirely the `vgate_thinox_max`
  oxide-safety criterion at the `vlogic3p63v` (+10 %) corner (the pre-driver
  inverter overshoot formally narrowed by
  [decision record 0003](../spec/decision-records/0003-predriver-inverter-oxide-margin-exception.md)),
  not a timing failure. The `t_plh_ns`/`t_phl_ns` values cited below are
  valid measurements at every corner, including the corners where the
  oxide-safety criterion fails — the two verdicts are independent columns of
  the same table.

## Results

### Drive strength: peak source/sink current (spec §3: ≥ 0.5 A, stretch 1 A)

Source: [`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../sim/output-stage-drive/records/20260812-064304-03699ea.md)
(`ipeak_source_a` / `ipeak_sink_a` columns), full 60-point grid.

| Measurement | Worst-case corner | Worst-case value | Grid mean | Target | Verdict |
|---|---|---|---|---|---|
| Peak source current | `ss_125c_vdrv4p50v` | 0.5877 A | 1.1579 A | ≥ 0.5 A | **PASS** (every corner) |
| Peak sink current | `ss_125c_vdrv4p50v` | 0.5737 A | 1.0219 A | ≥ 0.5 A | **PASS** (every corner) |

The 1 A stretch target is met at many corners (grid mean is above 1 A for
source current) but not at the slow/hot/low-rail corner — that corner is
the worst case, not representative, and the stretch goal is explicitly
aspirational per spec §3.

### Rise/fall into the 1 nF reference load (spec §3: < 50 ns, 10–90 %)

Source: same record, `trise_s` / `tfall_s` columns, full 60-point grid;
enforced with an explicit `max = 50 ns` limit in the record itself.

| Measurement | Worst-case corner | Worst-case value | Grid mean | Target | Verdict |
|---|---|---|---|---|---|
| 10–90 % rise time | `ss_125c_vdrv4p50v` | 8.36 ns | 5.11 ns | < 50 ns | **PASS** (every corner) |
| 10–90 % fall time | `ss_125c_vdrv4p50v` | 7.53 ns | 4.99 ns | < 50 ns | **PASS** (every corner) |

This measurement is against the real spec §3 1 nF load, so the load side of
this row is exactly what spec §3 asks for. The **input** side is not: the
edge driving the output stage here is the testbench's idealized 1 ns
0–100 % pulse, not a measured level-shifter output edge (see "Coverage"
below) — the output stage's own rise/fall time into the load is real,
measured data; whether that number would change once driven by the actual
(slower, corner-dependent) level-shifter output edge is not yet measured.

### Propagation delay (spec §3: < 50 ns nominal, < 25 ns stretch)

Two **partial** segments are measured; no end-to-end number exists yet.

**Output-stage segment** (`IN_DRV` → `OUT`, idealized already-level-shifted
input, into the 1 nF load) — source: same output-stage-drive record,
`tpdlh_s` / `tpdhl_s` columns, full 60-point grid:

| Measurement | Worst-case corner | Worst-case value | Grid mean |
|---|---|---|---|
| Low→high propagation delay | `ss_125c_vdrv4p50v` | 5.78 ns | 3.61 ns |
| High→low propagation delay | `ss_125c_vdrv4p50v` | 5.88 ns | 3.93 ns |

**Level-shifter segment** (`IN` (3.3 V logic) → `OUT` (level-shifted),
into a 20 fF placeholder load) — source:
[`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`](../sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md),
`t_plh_ns` / `t_phl_ns` columns, full 60-point grid:

| Measurement | Worst-case corner | Worst-case value | Grid mean |
|---|---|---|---|
| Low→high propagation delay | `ss_125c_vlogic2p97v-vdrv4p50v` | 1.13 ns | 0.69 ns |
| High→low propagation delay | `ss_125c_vlogic2p97v-vdrv4p50v` | 0.61 ns | 0.37 ns |

Both segments individually sit far under spec §3's 50 ns / 25 ns budget, and
`design/output-stage-sizing.md` §5 records a **design allocation** (not a
verified split) of ≤ 20 ns / ≤ 10 ns of that budget to the output-stage
segment alone, leaving ≥ 30 ns / ≥ 15 ns for the level shifter and
interconnect — the output-stage segment's own worst case (5.88 ns) clears
that allocation with large margin. But this report does not add the two
segments together and call the sum an end-to-end verified result: they were
measured with different loads (1 nF real reference load vs. a 20 fF
placeholder that predates the output stage's own record and was never
refreshed against it) and different drive edges (the output stage's input
edge is an assumed idealization, not the level shifter's actual measured
output edge). A worst-case-plus-worst-case sum (≈ 5.88 ns + 1.13 ns ≈
7.0 ns) is offered here only as an order-of-magnitude sanity bound — it
comfortably clears the 50 ns/25 ns spec target either way — not as a
substitute for a genuine end-to-end simulation.

## Coverage: per-cell only, not end-to-end

**Every row above is currently backed by isolated per-cell campaigns, not an
end-to-end simulation of the block's actual signal path (3.3 V logic `IN` →
level shifter → output stage → 1 nF load).** Concretely:

- `output-stage-drive`'s `IN_DRV` is an **ideal, already-level-shifted**
  source — the level shifter is entirely absent from that circuit. Its
  rise/fall and drive-strength numbers are real measurements of the output
  stage driving the real 1 nF reference load, but the edge rate feeding it
  is a testbench assumption, not the level shifter's own measured output.
- `level-shifter-oxide-safety`'s `OUT` drives a 20 fF placeholder
  capacitance, explicitly flagged in that testbench as not a measured
  number from the output stage — and that placeholder has not been
  refreshed now that `sim/output-stage-drive/` exists and could supply a
  real number.
- No record in this repository currently simulates the level shifter driving
  the output stage's actual input, nor the output stage's input edge
  actually originating from the level shifter's measured output — i.e.
  no record composes the two cells into one chain.
- Because of this, the "propagation delay" row above is reported as **two
  separate partial numbers**, not one composed end-to-end verdict — treating
  their sum as a verified result would overstate what has actually been
  simulated.

Item 5 of the T1 gap re-read (`#62`), tracked as issue **#100** ("end-to-end
PVT corner campaign against ratified spec §3, incl. refreshing the stale
level-shifter-oxide-safety record"), is the follow-on work that closes this
gap: a single testbench chaining the block's real `IN` pin through the level
shifter into the output stage's real input, driving the real 1 nF reference
load, across the full PVT matrix. That campaign is explicitly the trigger
for superseding this report's propagation-delay section — see "Follow-up"
below. Drive strength and rise/fall, by contrast, are already measured
against the real 1 nF reference load in `sim/output-stage-drive/`; #100 may
still refine them (e.g. with a realistic level-shifter-driven input edge
instead of the idealized one), but they are not blocked on #100 the way the
propagation-delay row is.

## Follow-up

This report is current as of the two records cited above
(`20260812-064304-03699ea` for `output-stage-drive`,
`20260808-052057-5fbdb2d` for `level-shifter-oxide-safety`) and does **not**
reflect issue #100's end-to-end campaign, which has not landed yet. Once
#100 produces a new evidence record:

- This report's propagation-delay section should be rewritten around the
  new end-to-end record rather than the two-segment estimate above.
- The drive-strength and rise/fall sections should be cross-checked against
  #100's numbers (same 1 nF load, but now driven by a real level-shifter
  output edge instead of the idealized one) and updated if they diverge.
- The report's "Coverage" section should be updated to say which rows are
  then end-to-end-backed, rather than continuing to disclaim coverage it has.
- If #100 also refreshes the stale `level-shifter-oxide-safety` record (it is
  scoped to), the level-shifter citations here should be re-pointed at the
  new record id.

**That update is already tracked: issue #107**, filed with this report and
declaring #100 as its dependency. So this report does not rely on someone
noticing it has gone stale — the follow-up exists now and unblocks itself
when #100's evidence lands.

## Links

- Output-stage-drive record: [`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../sim/output-stage-drive/records/20260812-064304-03699ea.md)
- Output-stage-drive testbench: [`sim/output-stage-drive/testbench/output_stage_tb.spice`](../sim/output-stage-drive/testbench/output_stage_tb.spice)
- Output-stage-drive design/sizing notes: [`design/output-stage-sizing.md`](output-stage-sizing.md) (§5's delay-budget allocation, §6's per-cell summary tables)
- Level-shifter-oxide-safety record: [`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`](../sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md)
- Level-shifter-oxide-safety testbench: [`sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice`](../sim/level-shifter-oxide-safety/testbench/level_shifter_tb.spice)
- Spec: [`spec/gate-driver.md`](../spec/gate-driver.md) §3 (targets), §5 (protection scope / documented exceptions)
- Decision records: [0003](../spec/decision-records/0003-predriver-inverter-oxide-margin-exception.md), [0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md)
- Re-read table: issue #62 (item 8); epic tracking: issue #22; end-to-end follow-on: issue #100; scheduled update of this report once #100 lands: issue #107
