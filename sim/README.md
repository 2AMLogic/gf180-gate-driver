# sim/ — evidence record format

This directory holds simulation testbenches and their results. Results are
**append-only evidence**: once a record is written, it is never edited or
deleted. A re-run — even one that corrects a mistake — mints a new record
with a new ID; a correction references the record it supersedes rather than
overwriting it in place.

This convention exists because `CLAUDE.md` commits this repo to two rules that
need a concrete schema to be enforceable:

- **Verification is the product.** No claim without a testbench. Every
  recorded result carries the full PVT corner matrix (−40/27/125 °C, ±10 %
  on every supply rail, process corners) unless the record explicitly states
  why a subset was used.
- **`sim/` is append-only evidence.** Re-runs get new records; records are
  never edited or deleted.

This file is ported from `2AMLogic/gf180-bandgap`'s `sim/README.md` (per
`CLAUDE.md`: "Harness bootstrap: copy the sim-harness pattern from
2AMLogic/gf180-bandgap rather than reinventing it") and adapted for this
repo's **two-rail** design. **This file is the authoritative convention.**
The corner runner that produces records in this format — how to run it, how
to write a testbench, PDK resolution, corner definitions — is documented in
[`sim/harness/README.md`](harness/README.md). If the harness and this
document ever disagree, this document wins and the harness is the thing that
gets fixed.

## Decision record: the two-rail `<corner-id>` grammar

`2AMLogic/gf180-bandgap` is single-supply, so its `<corner-id>` carries one
bare `<volts>v` (or `<node><volts>v` for a testbench that names an extra
swept node, e.g. that repo's resistor-characterization `nwell2p97v`). This
design has two independent rails that must both appear on every point:
the 3.3 V logic rail (±10 % → 2.97/3.30/3.63 V) and the 5 V drive rail
(±10 % → 4.50/5.00/5.50 V, per spec §3 and DRM 14.1.2).

| | |
|---|---|
| Options considered | (a) extend the existing `<node><volts>v` form to two named tokens; (b) full-factorial cross product of both rails' tolerance points (9 supply points instead of 3); (c) tie both rails together at the same relative offset (3 points, like the single-rail convention) |
| Trade-offs | (a) vs. leaving supply unnamed: gf180-bandgap already establishes a "name the node when there is more than one thing that could be `<volts>v`" convention (`nwell2p97v`, from that repo's resistor device-characterization script) — reusing it rather than inventing new punctuation keeps one grammar across both repos. (b) vs. (c): a full 3×3 cross product records the two rails moving independently (worst-case skew between them), but triples the point count of every corner/temperature combination CLAUDE.md's PVT matrix already commits to, and spec §3's own phrasing treats "±10% supply" as one axis, not two. (c) preserves the existing axis-count contract (temp × supply × process, same shape as the single-rail harness) while still recording the exact two-rail pair present at each point. |
| Chosen | (a) + (c): `<corner-id> ::= <process>_<temp>c_<rail1><v1>v-<rail2><v2>v[-...]`, e.g. `tt_27c_vlogic3p30v-vdrv5p00v`, with the decimal point rendered as `p` per the existing `nwell2p97v` precedent so the whole supply field stays one underscore-free token. The rails are swept **together**: point 0 is every rail at its low tolerance bound, point 1 is every rail at nominal, point 2 is every rail at its high bound — see `sim/harness/corners.py`'s `tied_supply_grid`. |
| Rationale | Keeps the mandated PVT matrix's size identical to the single-rail convention (no silent widening, per `CLAUDE.md`/this file's append-only-adjacent "don't narrow or widen the axis" spirit) while making the two-rail voltage pair explicit and hand-checkable in every corner-id and log filename. A rail's independent-sweep / stretch-voltage needs (e.g. the 5 V rail's 6 V stretch target from spec §3) are supported as an explicit, opt-in extra composite point (`stretch_points`, `"stretch": true` in a manifest) rather than folded into the default matrix, so a reader can tell "the mandated matrix" from "an extra point this testbench chose to also record" at a glance. |

This decision is implemented in [`sim/harness/corners.py`](harness/corners.py)
(`Rail`, `tied_supply_grid`, `PvtPoint.corner_id`) and enforced in
[`sim/harness/evidence_lint.py`](harness/evidence_lint.py) (`parse_corner_id`,
`_SUPPLY_RE`).

## Directory / naming convention

Each testbench topic gets its own experiment directory:

```
sim/
  <experiment-slug>/                 # e.g. smoke-mv-inverter, output-stage-drive, level-shifter-vgs
    testbench/                       # testbench netlist(s) / xschem export used
    netlist-snapshots/
      <record-id>.spice              # frozen DUT netlist used for this record
    corners/
      <record-id>/
        <corner-id>.log              # raw ngspice output per PVT point
                                      # e.g. ss_-40c_vlogic2p97v-vdrv4p50v.log
    records/
      <record-id>.md                 # append-only summary record
```

- **`<experiment-slug>`** — short, descriptive, kebab-case name for what is
  being verified (`smoke-mv-inverter`, `output-stage-drive`,
  `level-shifter-vgs`, ...). One directory per distinct claim being tested,
  not per run.
- **`<record-id>`** — unique and traceable:
  `<YYYYMMDD>-<HHMMSS>-<short-git-sha>` (e.g. `20260808-153000-1a7ef75`).
  Re-runs simply mint a new `<record-id>`; nothing under `records/` is ever
  edited in place. The same `<record-id>` ties together the netlist snapshot,
  the raw per-corner logs, and the summary record for one run.
- **`<corner-id>`** — `<process-corner>_<temp>c_<supply>`, where `<supply>`
  is one or more `<rail><volts>v` tokens joined by `-` (one per rail declared
  on the testbench; this repo's default two rails are `vlogic` and `vdrv`),
  decimal point rendered as `p`: e.g.
  `ss_-40c_vlogic2p97v-vdrv4p50v.log`, `tt_27c_vlogic3p30v-vdrv5p00v.log`,
  `ff_125c_vlogic3p63v-vdrv5p50v.log`. See the decision record above. A
  device-level testbench that drives its DUT from an ideal source with no
  swept rail at all may use the literal `nosupply` in place of the supply
  field (inherited from gf180-bandgap's device-characterization scripts;
  the record's Corner matrix run field must say why).
- **`testbench/`** is not versioned per record — it holds the current
  testbench netlist(s)/xschem export(s) used to generate records. If the
  testbench itself changes in a way that could affect comparability across
  records, note that in the new record's summary (e.g. under Claim or a
  free-text note).

## Summary record format

Each run produces one `records/<record-id>.md` file with the following
fields:

- **Record ID** — the `<record-id>` for this run (matches the filename and
  the corresponding `netlist-snapshots/` / `corners/` subdirectory).
- **Claim** — which spec parameter/line this record substantiates (reference
  the ratified spec, e.g. `spec/gate-driver.md#<anchor>`).
- **Netlist provenance** — `schematic` (`design/...`) or `extracted`
  (post-layout, `layout/...`). Required so post-layout re-runs are
  distinguishable from the original schematic-level record.
- **Corner matrix run** — explicit list of (process corner, temperature,
  vlogic, vdrv) points actually executed. Must be the full PVT matrix from
  `CLAUDE.md` (−40/27/125 °C, ±10 % on every rail, process corners) unless the
  record states why a subset was used.
- **Statistical convention** (when applicable, e.g. Monte Carlo mismatch
  analysis) — N samples and sigma level reported. Used for distribution
  claims that are not a per-corner pass/fail.
- **Result** — per-corner pass/fail, plus an overall pass/fail against the
  ratified spec value. Where the spec states two tiers for a parameter, each
  point is judged against the tier that applies *at that point* — see
  [Two-tier (nominal / stretch) checks](#two-tier-nominal--stretch-checks)
  below.
- **Links** — paths to the testbench file(s), the frozen netlist snapshot,
  and the raw per-corner logs used to produce this record.
- **Timestamp / author** — when the record was created and who (human or
  agent) created it.
- **Supersedes** (optional) — the prior `<record-id>` this record supersedes,
  for corrections or for a post-layout extracted re-run that reports a
  schematic-vs-extracted delta against the schematic-level record.

## Two-tier (nominal / stretch) checks

`spec/gate-driver.md` §3 states two bounds for several parameters — a
**Target** and a **Stretch** target (peak source/sink current ≥ 0.5 A / 1 A;
propagation delay < 50 ns / < 25 ns) — and the stretch column of that same
table is what the 6 V `vdrv` point in the decision record above *is*. A
record that runs the stretch point must therefore say which of the two
bounds each point was judged against; a single loose bound applied across
the whole grid records a stretch-corner point that misses the stretch target
as PASS, which reads as evidence for a claim the run did not substantiate
(issue #125).

The convention:

- A point sitting at a rail's opt-in `extra_v` voltage (the 6 V `vdrv`
  stretch point) is judged against the **stretch** bound for that parameter.
- Every other point in the grid is judged against the **nominal** bound.
- A parameter with no stretch target in the spec (`—`) keeps its nominal
  bound everywhere, stretch point included. A stretch bound is never
  invented for a spec row that does not state one, and the nominal bound is
  never left standing in for one that does.
- The record makes the tier visible rather than implicit: the limits column
  carries both (`min=0.5, stretch min=1`) and a stretch-tier failure is
  tagged `[stretch]`.

This is implemented in [`sim/harness/report.py`](harness/report.py)
(`is_stretch_point`, `evaluate_checks`) and expressed per testbench as a
`"stretch": {...}` override inside a `checks` entry — see
[`sim/harness/README.md`](harness/README.md#corner-scoped-bounds-nominal-vs-stretch)
for the manifest syntax and the load-time rules that keep such a bound from
being declared where it could never fire.

## Decision record: transient tolerance convention

Every §2.3 gate-ceiling number recorded so far (decision records 0003, 0004,
0005, 0006) is the peak of a narrow capacitive-coupling spike, measured by a
generated `tran <tstep> <tstop>` deck with no maximum-timestep argument and
ngspice's own factory-default `reltol` (1e-3). Re-solving the same point with
a bounded maximum timestep, or a tighter `reltol`, moves the peak *outward*
by ~25% — the harness-default figure is a **lower bound** on the true
excursion, not an upper one, which is the opposite of what a conservative
reliability bound needs (issue #156).

| | |
|---|---|
| Worst-case point measured | `ss_125c_vlogic3p30v-vdrv6p00v` of `sim/gate-driver-core-drive/`, node `IN_DRV`, ngspice-46/gf180mcuD @ open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b` |
| Options considered | (a) an explicit `tran` `maxstep` argument in the generated deck; (b) a tightened `.options reltol` default; (c) per-testbench overrides via the manifest's existing `options` key with no harness-wide default; (d) a documented "peaks are resolution-limited" caveat with no deck change |
| Comparison table (single worst-case point) | harness default (`tran 0.1n 700n`): 6.11823 V (−118.2 mV margin) · `maxstep` 20 ps: 6.14362 V · `maxstep` 10 ps: 6.14767 V · `reltol` 1e-4: 6.14569 V · `reltol` 1e-5: 6.14801 V · `maxstep` ≤ 5 ps (± tighter `reltol`): run aborts ("timestep too small") at 57–133 ns of the 700 ns run |
| Full-grid check (issue #156's own follow-up) | `reltol=1e-5` looked safe on the single worst-case point above but, run across all 60 mandated `sim/gate-driver-core-drive` points, aborted on 7 of 60 with ngspice's "Timestep too small" on `vimeas#branch`/`vgnd_logic#branch` — a *different* device/branch-equation failure mode than the sub-5 ps `maxstep` abort the single-point table found, and one single-point testing alone would not have caught. `reltol=1e-4` completed all 60 points with no aborts. |
| Chosen | (b): a harness-wide default of `.options reltol=1e-4`, applied by `compose_deck` to every generated deck unless a testbench's own manifest already opts into a `reltol` value via `"options": ["reltol=..."]` (per-testbench override stays available for a future point that needs something tighter or looser) |
| Rationale | `reltol=1e-4` recovers nearly all of the outward peak movement a tighter setting would (6.14569 V vs. 6.14801 V @ `reltol`=1e-5, both against the 6.11823 V harness-default baseline) with a one-line, deck-global change — no per-testbench `tran` edit — and, unlike `reltol=1e-5`, completes the full mandated PVT grid with zero aborts. A caveat-only fix (option d) was rejected because it leaves every *existing* recorded number silently understated; a per-testbench-only opt-in (option c) was rejected because every testbench in this repo's grid measures the same class of coupling-transient peak, so a harness-wide default is the more conservative choice by default, with the override still available for a testbench that needs to diverge |

Every generated deck's `.options reltol=...` line, and whether it is the
harness default or a manifest override, is recorded on the record's
**Environment** block (`Transient tolerance: reltol=... (harness default |
manifest override)`) — see the worked example below — so a later reader can
tell which convention produced a given number without cross-referencing this
repo's git history. Implemented in
[`sim/harness/runner.py`](harness/runner.py) (`DEFAULT_TRAN_RELTOL`,
`effective_reltol`, `compose_deck`) and
[`sim/harness/report.py`](harness/report.py) (`environment`, `render_record`).

## Decision record: Monte Carlo / local-mismatch convention

Every recorded result in this repo before issue #204 was a **global process
corner** claim (`tt`/`ff`/`ss`/`fs`/`sf`) — die-to-die and wafer-to-wafer
skew, applied uniformly to every device in the deck. That says nothing about
**within-die local mismatch** between two nominally-identical devices on the
same die at the same corner, which is the statistic that matters for a
matched pair or a small, precision-cancelled margin. The **Statistical
convention** field above has always reserved a place for that evidence
class; this section ratifies how the harness produces it.

**What the installed PDK ships** (read off `gf180mcuD`, open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, not assumed):

| Device class | Local (intra-die) mismatch model | Notes |
|---|---|---|
| `nfet_03v3` / `pfet_03v3` / `nfet_05v0` / `pfet_05v0` / `nfet_06v0` / `pfet_06v0` | **Yes** — `sm141064.ngspice`'s `.lib fets_mm` wrappers carry `delvto='mis_vth*sw_stat_mismatch'` and `mulu0='1-mis_k*sw_stat_mismatch'`, drawn per *instance* from `agauss(0, σ, 1)` with σ ∝ 1/√(W_eff·L_eff) | `fets_mm` is already pulled in by all five MOS corner sections, and this repo's netlists instantiate those subcircuit names directly, so no netlist edit is needed |
| MiM capacitors (`cap_mim_*`) | **No** — the `mc_c_cox_{1p0,1p5,2p0}fF` hooks exist but are hardcoded to `0` in every `mimcap_*` section, and are `.LIB`-scope (one value for all instances) rather than per-instance | Global ±10 % density skew *is* modelled, via `mimcap_ss`/`mimcap_ff` |
| Resistors | **No** — `.lib res_statistical` draws `agauss` sheet-rho deviations but gates them on `sw_stat_global`, not `sw_stat_mismatch` | Die-level skew only, already covered by `res_ff`/`res_ss` |
| `nfet_05v0` / `nfet_06v0` β mismatch | **No** — `par_k = 0.0000` for these two families only, so `mulu0` ≡ 1 | Threshold mismatch only for the thick-oxide nFETs; recorded as a medium-voltage model-fidelity finding per `CLAUDE.md` |

**Convention** (implemented in [`sim/harness/montecarlo.py`](harness/montecarlo.py),
`runner.compose_deck(..., mc=...)`, `runner.run_samples`):

- **One ngspice invocation is one sample.** ngspice evaluates `agauss` at
  netlist-parse time and draws independently per subcircuit instance, so the
  existing "one PVT point is one ngspice run" model carries over unchanged.
- **`sw_stat_global` stays 0.** The deterministic `.LIB` process corner is
  this harness's global-skew axis; letting the PDK *also* draw a random
  global skew would double-count it and make "mismatch at the `ss` corner"
  mean something else. Monte Carlo is therefore always run **on top of** the
  corner matrix, never instead of it.
- **Seeds are derived, not ad hoc.** `seed = base_seed + point_index ×
  10000 + sample`, pinned into the deck as `.options seed=<n>`; the base seed
  and sample count on the record regenerate the whole distribution.
- **A deterministic negative control is mandatory.** Sample index 0 is
  reserved for a `sw_stat_mismatch = 0` run, which must reproduce the plain
  (`mc=None`) harness deck for the same PVT point **bit-for-bit**, on every
  measurement, at two different seeds. Without it a "Monte Carlo" record
  cannot distinguish mismatch from a deck difference or solver noise.
- **Corner-ids stay inside the ratified grammar.** The sample token rides in
  the *process* field — `ss_mc0042_125c_vlogic3p30v-vdrv6p00v` — rather than
  adding a fourth field the evidence linter would reject.
- **Raw evidence is filtered, not dropped.** A campaign is thousands of runs;
  committing one `.log` per draw is unreadable and committing none is
  unauditable. The convention is a real `.log` for each cited run (the
  baseline, the zero-sigma control, and the worst-case draw at each PVT
  point) plus a flat `samples-<corner-id>.csv` sidecar under
  `corners/<record-id>/` carrying every draw's seed and parsed measurements.
  `corners/<record-id>/` deliberately does not forbid non-`.log` sidecars.
- **The Statistical convention field must state** N, the sigma level of the
  *underlying model* (the PDK's per-device draws are 1 σ, not a 3 σ corner
  pull), the base seed, and whether a reported worst case is an observed
  maximum or a fitted quantile.

First record under this convention:
`sim/gate-driver-indrv-mismatch/records/` (issue #204,
`spec/decision-records/0017-pdk-local-mismatch-model-coverage.md`).

## Append-only rule

`records/*.md` files are never edited or deleted after creation. A re-run or
a correction always creates a new record with a new `<record-id>`. If it
corrects or replaces a prior result, it references that prior record via
**Supersedes** rather than overwriting it. This applies even to typo fixes —
the append-only guarantee is what makes `sim/` usable as an evidence trail;
"fixing" an existing record in place would defeat that. Enforced in CI by
`sim/check_records.py` (see `.github/workflows/ci.yml`'s `lint` job).

## Worked example

`sim/smoke-mv-inverter/records/<record-id>.md` (see
[`sim/harness/README.md`](harness/README.md#smoke-mv-inverter) for what this
experiment proves):

```markdown
# Record 20260808-153000-1a7ef75

- **Record ID**: 20260808-153000-1a7ef75
- **Claim**: None — harness self-verification, not a spec claim. Proves the
  two-rail PVT plumbing (parameter substitution on both `vlogic` and `vdrv`,
  `.lib` corner sections reaching the thick-oxide 06v0 device family, `.temp`)
  actually takes effect, so later records against ratified spec lines can be
  trusted.
- **Netlist provenance**: schematic (`sim/smoke-mv-inverter/testbench/smoke_mv_inverter.spice`)
- **Corner matrix run**:
  - Process: tt, ff, ss, fs, sf
  - Temperature: −40 °C, 27 °C, 125 °C
  - Supply (vlogic, nominal 3.30 V): 2.97 V, 3.30 V, 3.63 V
  - Supply (vdrv, nominal 5.00 V): 4.50 V, 5.00 V, 5.50 V
  - 45 point grid (5 process corners x 3 temperatures x 3 tied two-rail
    supply points), 45 completed
  - Full PVT matrix per CLAUDE.md (−40/27/125 °C, ±10 % on every rail,
    process corners).
- **Statistical convention**: N/A (corner-matrix claim, not a distribution claim)
- **Result**: PASS at every point — see the full per-corner table in the
  record itself.
  - **Overall: PASS**
- **Links**:
  - Testbench: `sim/smoke-mv-inverter/testbench/smoke_mv_inverter.spice`, `sim/smoke-mv-inverter/testbench/tb.json`
  - Netlist snapshot: `sim/smoke-mv-inverter/netlist-snapshots/20260808-153000-1a7ef75.spice`
  - Raw logs: `sim/smoke-mv-inverter/corners/20260808-153000-1a7ef75/`
- **Timestamp / author**: 2026-08-08T15:30:00Z, agent-builder
- **Supersedes**: (none — first record for this claim)
```

A later post-layout extracted re-run of a spec-line claim would live under
its own experiment directory (e.g. `sim/output-stage-drive/`) with its own
`<record-id>`, `Netlist provenance: extracted (layout/... -> extracted
netlist)`, and a `Supersedes: <prior-record-id>` field carrying a
schematic-vs-extracted delta summary in its Result section — the same
supersession convention `sim/smoke-mv-inverter/` itself would use for a
correction re-run.

## Facets in this repo: cold-start invocation and PDK pin (issue #22 item 9)

Every experiment directory under `sim/` uses one of two entry points, and
every record it produces pins the exact PDK build it ran against — this is
the per-facet index the [T1 checklist](https://github.com/2AMLogic/gf180-gate-driver/issues/22)
"item 9" acceptance criterion asks for, confirming the convention already
documented above and in [`sim/harness/README.md`](harness/README.md) is
actually followed by every facet, not just described in the abstract.

| Facet (`sim/<slug>/`) | Cold-start invocation | Spec claim |
|---|---|---|
| `smoke-mv-inverter` | `python3 sim/run_corners.py smoke-mv-inverter` | none — harness self-test |
| `gate-driver-core-drive` | `python3 sim/run_corners.py gate-driver-core-drive` | `spec/gate-driver.md` §3, §2.3 |
| `gate-driver-core-drive-postlayout` | `python3 sim/run_corners.py gate-driver-core-drive-postlayout --dut layout/lvs/gate_driver_core.extracted.spice` (no-RC) or `--dut layout/lvs/gate_driver_core.extracted-rc.spice` (RC) | `spec/gate-driver.md` §3, §2.3 |
| `output-stage-drive` | `python3 sim/run_corners.py output-stage-drive` | `spec/gate-driver.md` §3 |
| `level-shifter-oxide-safety` | `python3 sim/run_corners.py level-shifter-oxide-safety` | `spec/gate-driver.md` §4, §2.3 |
| `device-mv-fet` | `PDK_ROOT=... PDK=gf180mcuD sim/device-mv-fet/run_device_mv_fet.py` (dedicated script — see its own module docstring; `python3 sim/run_corners.py device-mv-fet` runs only a small representative subset for `--list`/`--check-env` discovery) | `spec/gate-driver.md` §2.5 |
| `low-side-power-switch` | `PDK_ROOT=... PDK=gf180mcuD sim/low-side-power-switch/run_low_side_power_switch.py` (dedicated script, same convention as `device-mv-fet`; `python3 sim/run_corners.py low-side-power-switch` runs only a representative subset) | `spec/low-side-power-switch.md` §2.1 |
| `gate-driver-indrv-mismatch` | `PDK_ROOT=... PDK=gf180mcuD sim/gate-driver-indrv-mismatch/run_indrv_mismatch.py` (dedicated script, same convention as `device-mv-fet`; a **Monte Carlo local-mismatch** campaign layered on the corner matrix, not a grid — it has no `tb.json` of its own and is not discoverable via `run_corners.py`, because it reuses `sim/gate-driver-core-drive/`'s testbench verbatim) | `spec/gate-driver.md` §5 Exception 3, §2.3 |

All eight entries resolve the PDK the same way (`sim/harness/README.md`'s
`GF180_PDK_PATH` → `PDK_ROOT`/`PDK` → `sim/pdk.local.json` → `sim/pdk.json` →
built-in search-root order); `sim/pdk.json` commits this repo's default
variant (`gf180mcuD`), and `sim/env.sh` exports the resolved path/variant to
an interactive shell. That is the *prospective* pin (which variant a fresh
clone should install); the *retrospective* pin — which exact `open_pdks`
build actually produced a given number — is per-record, not per-facet:
every `records/<record-id>.md` file's **Environment** section states the
PDK path, variant and `open_pdks` git hash, the `ngspice` version, the
harness version, and the git commit the record was produced from (see the
worked example above, or any record under any facet listed here) — that is
what makes a given record reproducible, since the PDK a facet resolves at
run time can differ record to record as `open_pdks` itself advances. CI
never installs a PDK or mints a record (`.github/workflows/ci.yml`'s own
top-of-file comment; `sim/` results are minted by a human or agent, not a
CI robot, per `CLAUDE.md`'s append-only-evidence convention).
