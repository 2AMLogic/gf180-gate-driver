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
  ratified spec value.
- **Links** — paths to the testbench file(s), the frozen netlist snapshot,
  and the raw per-corner logs used to produce this record.
- **Timestamp / author** — when the record was created and who (human or
  agent) created it.
- **Supersedes** (optional) — the prior `<record-id>` this record supersedes,
  for corrections or for a post-layout extracted re-run that reports a
  schematic-vs-extracted delta against the schematic-level record.

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
