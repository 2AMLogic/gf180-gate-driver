# sim/harness — the PVT corner runner

Reproducible ngspice simulation against the gf180mcu PDK, ported from
`2AMLogic/gf180-bandgap` (per `CLAUDE.md`) and adapted for this repo's
**two-rail** design. This document covers **how to run** the harness and
**how to write a testbench**.

The *output* of a run — directory layout, record-id format, the summary
record field set, the two-rail corner-id grammar, and the append-only rule —
is defined by [`sim/README.md`](../README.md), not here. That convention is
authoritative; this harness exists to produce records that conform to it.

```
sim/
  run_corners.py            CLI entry point (stdlib python3, no venv)
  check_records.py          evidence-record format + append-only checker
  env.sh                    `source sim/env.sh` to export the same PDK to your shell
  pdk.json                  committed PDK defaults (variant, extra search roots)
  harness/                  the runner itself (this directory)
  .work/                    generated ngspice decks (git-ignored, disposable)

  <experiment-slug>/        one per claim under test -- see sim/README.md
    testbench/              tb.json + netlist fragment      <- you write these
    netlist-snapshots/      frozen netlist per record       <- the harness writes these
    corners/<record-id>/    raw <corner-id>.log per PVT point
    records/<record-id>.md  append-only summary record
```

## Quick start

```bash
python3 sim/run_corners.py --check-env       # is ngspice + the PDK present?
python3 sim/run_corners.py --list            # experiments, corners, corner sets, rails
python3 sim/run_corners.py smoke-mv-inverter  # run the full PVT grid, mint a record
python3 sim/check_records.py                 # lint every evidence record
```

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| `ngspice` | simulation | `brew install ngspice` / `apt-get install ngspice` |
| gf180mcu PDK | device models | `pip install volare && volare enable --pdk gf180mcu <hash>` |
| `xschem` | schematic capture (optional for simulation) | `brew install xschem` / distro package |
| python3 ≥ 3.9 | the harness | stdlib only, no packages |

The harness never hardcodes a PDK path. It resolves one, in order:

1. `GF180_PDK_PATH` — the *variant* directory, e.g. `~/.volare/gf180mcuD`
   (the one containing `libs.tech/`).
2. `PDK_ROOT` (+ `PDK`, default `gf180mcuD`) — the open_pdks / OpenLane convention.
3. `sim/pdk.local.json` — machine-local, git-ignored.
4. `sim/pdk.json` — committed defaults.
5. Built-in search roots: `~/.volare`, `~/.ciel`, `/usr/share/pdk`,
   `/usr/local/share/pdk`, `~/share/pdk`, `/opt/pdk`.

If nothing is found the runner exits 3 with install instructions rather than
producing a misleading result. `sim/run_corners.py --print-env` emits the
resolved paths as shell exports; `source sim/env.sh` applies them so that an
interactive ngspice or xschem session uses the identical PDK.

## The PVT grid

`CLAUDE.md` requires PVT corners on every recorded result. The defaults are
baked into `corners.py` and are what a testbench gets unless its manifest says
otherwise:

- **Temperature**: −40, 27, 125 °C
- **Voltage**: two rails, each nominal ±10 % (spec/gate-driver.md §3):
  - `vlogic` — 3.3 V logic rail → 2.97 / 3.30 / 3.63 V
  - `vdrv` — 5 V drive rail → 4.50 / 5.00 / 5.50 V
- **Process**: see below

gf180mcu has no single global corner switch — each device family carries its
own `.lib` section in `sm141064.ngspice`, so a named corner here is a bundle of
six sections (MOS, resistor, BJT, diode, MOS cap, MIM cap):

| Corner | Meaning |
|---|---|
| `tt` | everything typical |
| `ff` / `ss` | every device family fast / slow |
| `fs` / `sf` | fast-N/slow-P and slow-N/fast-P, passives typical |
| `res_ff` / `res_ss` | resistor sheet rho skewed, rest typical |
| `bjt_ff` / `bjt_ss` | BJT skewed, rest typical |

**Confirmed against the installed gf180mcuD `sm141064.ngspice`**
(open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`, checked 2026-08-08):
the generic `typical`/`ff`/`ss`/`fs`/`sf` `.LIB` sections already bundle the
thick-oxide `nfet_06v0`/`pfet_06v0` corner-parameter overlay alongside the
3.3 V devices — the same five corner names sweep both this repo's rails'
device families, no new corner vocabulary needed for the drive rail. See
`corners.py`'s module docstring for detail.

Corner sets: `tt` (1), `mos` (5, the default), `full` (9 — use this for
anything whose accuracy rides on resistors or BJTs).

Each point becomes one `<corner-id>` — `<process>_<temp>c_<supply>`, the
naming `sim/README.md` ratifies — and one raw log under
`corners/<record-id>/`.

### Two rails, swept together

Unlike gf180-bandgap's single `vdd`, this design has two independent named
rails (`corners.Rail`). They are **tied together** rather than
full-factorially cross-producted: point 0 is both rails at their low value,
point 1 is both at nominal, point 2 is both at their high value — see
`corners.tied_supply_grid` and the decision record in `sim/README.md`. A
`corner-id` names both rails explicitly, e.g. `tt_27c_vlogic3p30v-vdrv5p00v`.

A rail's optional `extra_v` stretch point (e.g. `vdrv`'s 6 V stretch target,
spec §3) is **not** part of the default grid — a testbench opts in with
`"stretch": true` in its manifest (`corners.stretch_points`), so the mandated
±10 % matrix is never silently widened for every experiment. A point sitting
at one of those `extra_v` voltages is what the `checks` block calls a
*stretch point*, and it can be held to a stricter bound than the rest of the
grid — see [Corner-scoped bounds](#corner-scoped-bounds-nominal-vs-stretch)
below.

Override any axis from the command line:

```bash
python3 sim/run_corners.py smoke-mv-inverter --corner-set full -j 8
python3 sim/run_corners.py smoke-mv-inverter --corners tt res_ss --temps -40 125
```

`-j` parallelizes across PVT points at the harness level (one ngspice
subprocess per point), so the generated deck's `.control` block always pins
`set num_threads=1` — see the note on the control block under
[Writing a testbench](#writing-a-testbench) below — to stop each ngspice
process from *also* fanning out across OpenMP threads underneath the
harness's own parallelism.

There is no `--supply`/`--supply-tol` override (unlike gf180-bandgap): with
two independently-named rails there is no single scalar left to override from
the command line the way the source harness's one `vdd` was. Change a rail's
nominal voltage or tolerance in the testbench manifest's `rails` map instead.

**Subsets need a reason.** `sim/README.md` requires every record's *Corner
matrix run* field to be the full mandated matrix "unless the record states why
a subset was used". The runner enforces that: if the grid you asked for is
missing a mandated temperature, a mandated voltage on either rail, or has
fewer than three process corners, it refuses to write a record unless you
supply `--subset-reason '<why>'` (which is copied verbatim into the record),
or pass `--no-write` because you are only debugging.

```bash
# debugging: runs, records nothing
python3 sim/run_corners.py smoke-mv-inverter --corners tt --temps 27 --no-write

# a deliberate, justified subset: runs and records, with the reason on the record
python3 sim/run_corners.py smoke-mv-inverter --corners tt --temps 27 \
    --subset-reason "nominal-only debug sweep; distribution claim, see Statistical convention"
```

## Writing a testbench

Create `sim/<experiment-slug>/testbench/` with a manifest and a netlist
fragment. The slug is the experiment directory from `sim/README.md`: one per
distinct claim under test, kebab-case.

`tb.json`:

```json
{
  "name": "my-experiment",
  "description": "one line, shows up in --list and in the record",
  "claim": "spec/gate-driver.md#drive-strength-and-reference-load",
  "netlist": "my_tb.spice",
  "dut": "sim/dut/gate_driver_top.spice",
  "rails": {
    "vlogic": {"nominal_v": 3.3, "tolerance": 0.1},
    "vdrv": {"nominal_v": 5.0, "tolerance": 0.1, "extra_v": [6.0]}
  },
  "temperatures_c": [-40, 27, 125],
  "corners": ["full"],
  "stretch": false,
  "analyses": ["op"],
  "params": {"iload": "10u"},
  "options": ["reltol=1e-6"],
  "measure": {"vout": "v(vout)", "iq_ua": "-i(vsup)*1e6"},
  "checks": {"vout": {"min": 4.9, "max": 5.1, "max_spread_pct": 2.0}}
}
```

`options` is a list of literal `.options ...` lines, appended to the deck
verbatim. **Every generated deck already gets `.options reltol=1e-4`** by
default (`runner.DEFAULT_TRAN_RELTOL`) — the harness-wide transient-tolerance
convention `sim/README.md`'s "Decision record: transient tolerance
convention" ratifies (issue #156): ngspice's own factory-default `reltol`
(1e-3) under-resolves the narrow capacitive-coupling spikes every §2.3
gate-ceiling record measures, and a tighter `reltol=1e-5` was tried and
rejected -- it aborts ("timestep too small") on some points of this repo's
full PVT grid, even though it looked safe on a single worst-case point.
Declare `"options": ["reltol=..."]` in a manifest only to *override* that
default with a different value for this testbench specifically, as in the
example above (`reltol=1e-6`); the harness detects the override
(case/whitespace-insensitive match on `reltol=`) and does not also append
its own default line.

`rails` is optional — omit it to get this repo's two default rails
(`vlogic` 3.3 V, `vdrv` 5 V, both ±10 %, `vdrv` carrying the 6 V stretch
point). A rail's `name` becomes both the corner-id token and the ngspice
`.param` prefix the generated deck exposes, so it must be lowercase
alphanumeric/underscore.

A manifest may instead declare **`"rails": {}`** — explicitly empty, not
omitted — to opt a device-level testbench (a bare transistor/resistor/diode
driven entirely from ideal sources, no circuit supply rail to sweep) out of
the two-rail axis entirely. `corners.tied_supply_grid` then resolves to a
single no-supply point and every corner-id in that experiment renders the
literal `nosupply` supply field (`sim/README.md`'s `nosupply` convention,
inherited from `2AMLogic/gf180-bandgap`'s device-characterization scripts —
see `sim/device-mv-fet/testbench/tb.json` for a worked example). Omitting
`rails` entirely is different from declaring it empty: the former gets this
repo's two default rails, the latter gets none.

`claim` is the default for the record's **Claim** field — the ratified spec
line this experiment substantiates. `--claim` overrides it per run.

`dut` (optional) names the **device under test**: a second fragment holding
nothing but subcircuit definitions, `.include`d ahead of the testbench. That
indirection is what lets several testbenches share one netlist, and what lets
the *same* testbench re-run unedited against a different one:

```bash
python3 sim/run_corners.py output-stage --dut layout/netlist/gate_driver_top_extracted.spice
```

The DUT path, its sha256 and its provenance class (`schematic` /
`frozen schematic` / `extracted`, derived from the path) land in the record's
**Netlist provenance** field, and its contents are copied into that record's
frozen `netlist-snapshots/<record-id>.spice` — so a record identifies the
exact circuit it measured, not just the stimulus around it. A DUT file may
not carry `.end`, `.control`, `.endc`, `.temp` or `.lib`; it *may* carry
`.include`, which an extracted netlist needs.

`subset_reason` (optional) pre-declares why this experiment's grid is a
deliberate subset of the mandated PVT matrix — for a testbench that sweeps an
axis internally, say. `--subset-reason` still overrides it, and either way the
text is copied verbatim onto the record, which is where `sim/README.md` wants
the justification to live.

The netlist is a **fragment**, not a complete deck. It must not contain
`.include`, `.lib`, `.temp`, `.control`, `.endc` or `.end` — the harness owns
all of those, which is what lets one netlist sweep the whole grid unedited.
The loader rejects fragments that break this rule instead of silently pinning
every corner to 27 °C. The harness hands the fragment, per declared rail:

`compose_deck()`'s `.control` block also always pins `set num_threads=1`,
alongside `set numdgt=10` / `set noaskquit`. This isn't a numerical-accuracy
knob — it stops each ngspice subprocess from fanning out across OpenMP
threads on its own. A locally built, OpenMP-enabled ngspice reads its own
`spinit` (or a `.spiceinit`) for a default thread count — some hosts ship one
with `set num_threads=8` — which is pure oversubscription once `-j` is
already running several PVT points in parallel: on an affected host, one
point went from ~0.17 CPU-s to ~8.5 CPU-min, and a 60-point sweep from ~5 s to
hours, for byte-identical measurements. The harness is what decides the
sweep's parallelism, so it is also what pins each ngspice invocation to a
single thread underneath it, independent of host `spinit` configuration.

| Parameter | Value |
|---|---|
| `<rail>_val` | that rail's supply for this PVT point (nominal, +tol or -tol) |
| `<rail>_nom` | that rail's nominal supply, for ratio measurements |
| `temp_c` | temperature for this PVT point (also applied via `.temp`) |

e.g. `vlogic_val`, `vlogic_nom`, `vdrv_val`, `vdrv_nom` for this repo's
default two rails.

Each `measure` entry becomes `let m_<name> = <expr>` followed by `print` inside
the control block, so the expression must reduce to a **scalar**: fine for
`op`; for `tran`/`ac` reduce with `maximum()`, `mean()`, `v(out)[0]`, etc.

`checks` are evaluated after the sweep:

| Key | Applies to | Meaning |
|---|---|---|
| `min` / `max` | every point | hard limit; failure names the offending corner-id |
| `stretch` | stretch points only | `{"min": …, "max": …}` override — see below |
| `max_spread_pct` | the grid | `(max−min)/\|mean\|` must stay under the limit |
| `min_spread_pct` | the grid | must *exceed* it — asserts the sweep really moved |
| `description` | — | free text, copied onto the record |

Any other key is a load error: a misspelled bound (`"maximum"`) would
otherwise leave the measurement unchecked while the record still said PASS.

`min_spread_pct` is a harness-integrity check: if `.temp` or a `.lib` section
silently failed to apply, a strongly PVT-sensitive measurement would come back
flat, and this catches that instead of reporting a suspiciously perfect result.

### Corner-scoped bounds (nominal vs stretch)

`spec/gate-driver.md` §3 states two tiers for the same parameter — a target
and a **stretch** target:

| Parameter | Target | Stretch |
|---|---|---|
| Peak source/sink current | ≥ 0.5 A | 1 A |
| Propagation delay | < 50 ns | < 25 ns |
| Rise/fall into reference load | < 50 ns | — |

A check states both by adding a `stretch` object next to its nominal
`min`/`max`:

```json
"checks": {
  "ipeak_sink_a": {"min": 0.5, "stretch": {"min": 1.0}},
  "tpdlh_s":      {"max": 50e-9, "stretch": {"max": 25e-9}},
  "trise_s":      {"max": 50e-9}
}
```

- At a **stretch point** — any point whose supply sits at one of a rail's
  `extra_v` values, e.g. `vdrv` at 6 V (`report.is_stretch_point`) — the
  `stretch` bound is evaluated **instead of** the nominal one. It replaces
  that side of the bound, it does not stack with it, so one point never
  reports two failures for the same measurement.
- At every **other** point the nominal `min`/`max` applies, exactly as
  before. A check with no `stretch` key is unchanged everywhere.
- A `stretch` object may override just **one side**; the omitted side falls
  back to the nominal value (so `{"min": 0.5, "max": 6.6, "stretch":
  {"min": 5.4}}` still enforces `max` 6.6 at the stretch point).
- A parameter whose spec row has **no** stretch target (`—`, like rise/fall
  above) simply declares no `stretch` key and keeps its nominal bound at the
  stretch corner too. Do not invent a stretch bound the spec does not state —
  and equally, do not leave the loose nominal bound standing in for one it
  does.
- `stretch` may only scope the per-point `min`/`max`. The two `*_spread_pct`
  keys are properties of the whole grid, so scoping one to a single corner
  is meaningless and is rejected at load time.
- Declaring a `stretch` bound on a testbench that never *runs* a stretch
  point (`"stretch": false`, or no rail with an `extra_v`) is a load error
  too: the stricter bound could never fire, so the record would read as if
  the tighter target were enforced while every point was judged against the
  looser one. That silent-loose-bound failure is exactly what this feature
  exists to prevent (issue #125).

The record reports which tier each verdict came from: the limits column
reads `min=0.5, stretch min=1`, and a failure at a stretch point is tagged
`ipeak_sink_a min [stretch]=1 (got 0.875334)`.

`sim/test_harness_checks.py` pins this behavior (stdlib `unittest`, no PDK):

```bash
python3 sim/test_harness_checks.py     # npm run test:harness
```

## What a run writes

One run mints one `<record-id>` (`<YYYYMMDD>-<HHMMSS>-<short-git-sha>`) and
writes, under `sim/<experiment-slug>/`:

| Path | Contents |
|---|---|
| `records/<record-id>.md` | the append-only summary record (the nine fields from `sim/README.md`, plus an Environment section with PDK / ngspice / harness / git provenance and the per-corner model sections) |
| `netlist-snapshots/<record-id>.spice` | verbatim frozen copy of the testbench fragment, with its sha256 |
| `corners/<record-id>/<corner-id>.log` | raw ngspice output, one file per PVT point |

Nothing is ever overwritten: the runner refuses to write over an existing
record or snapshot, and mints a later record-id if one is somehow already
taken. Corrections and re-runs get a new record-id and reference the prior one
with `--supersedes <record-id>`. Do not edit or delete anything under
`records/`, `netlist-snapshots/` or `corners/` — see the append-only rule in
`sim/README.md`.

A run taken against a dirty working tree says so in the record's **Netlist
provenance** field and is not citable as a clean-tree result.

Exit codes: `0` pass · `1` a check failed · `2` a simulation failed or did not
converge · `3` environment problem (no ngspice, no PDK, bad manifest,
unjustified PVT subset).

Generated decks land in `sim/.work/<experiment-slug>/<record-id>/` and are
git-ignored, so a failing corner can be reproduced by hand with
`ngspice -b sim/.work/<slug>/<record-id>/<corner-id>.spice`.

## Monte Carlo / local mismatch

`harness/montecarlo.py` adds a **local device mismatch** mode to deck
composition. The ratified convention it implements — what the PDK does and
does not model, why `sw_stat_global` stays off, and the mandatory
deterministic negative control — is in
[`sim/README.md`](../README.md#decision-record-monte-carlo--local-mismatch-convention)
and `spec/decision-records/0017-pdk-local-mismatch-model-coverage.md`. This
section is just the API.

```python
from harness.montecarlo import MismatchSample, mc_point, sample_seed
from harness.runner import run_samples

seed = sample_seed(base_seed=20260204, point_index=7, sample=42)
mc = MismatchSample(sample=42, seed=seed)          # sample=0 is the control
results = run_samples(tb, pdk, [(mc_point(point, mc), mc)], workdir, jobs=8)
```

- `compose_deck(tb, pdk, point, mc=...)` appends `.param sw_stat_global=0`,
  `.param sw_stat_mismatch={0,1}` and a literal `.options seed=<n>` **after**
  the corner `.lib` sections — the PDK's `design.ngspice` sets both switches to
  `0` ahead of them, and ngspice takes the last `.param` definition of a name,
  so an override emitted earlier would be silently undone and every "Monte
  Carlo" run would quietly be a nominal run. There is a regression test for
  exactly that ordering.
- `mc=None` (every non-Monte-Carlo run) leaves the deck byte-identical to what
  the harness produced before this mode existed.
- `mc_point(point, mc)` re-labels the point's *process* field with an
  `mc<NNNN>` token (`ss_mc0042_125c_vlogic3p30v-vdrv6p00v`) so each sample gets
  a unique, grammar-legal corner-id, while carrying the corner's actual `.lib`
  sections through untouched.
- `run_samples(...)` is the Monte Carlo counterpart of `run_grid`: it returns
  every run's raw ngspice text on the result and keeps logs in the scratch
  workdir, so a campaign can commit only the runs its record actually cites
  instead of one log file per draw.

`sim/gate-driver-indrv-mismatch/run_indrv_mismatch.py` is the first campaign
built on this, and the reference for the shape of one.

## smoke-mv-inverter

`sim/smoke-mv-inverter/` is the harness acceptance test, not a circuit
deliverable and not a spec claim. Two independent branches, each proving a
different part of the plumbing:

1. an ideal resistor divider off `vlogic` — must read exactly 0.5·vlogic at
   every point, proving `vlogic_val` parameter substitution and measurement
   parsing;
2. a thick-oxide (`nfet_06v0`/`pfet_06v0`) CMOS inverter powered from `vdrv`,
   plus a diode-connected `nfet_06v0` forced at a fixed current — the
   inverter's output tracks `vdrv_val` (proving the drive-rail plumbing on
   the actual thick-oxide device family spec §2.5 commits this design to),
   and the diode-connected device's Vgs is both corner- and
   temperature-sensitive (proving `.lib`/`.temp` actually reach the 06v0
   device, not just the 03v3 one).

Both branches run at every point of the tied two-rail PVT grid (see "Two
rails, swept together" above), so one record demonstrates the harness sweeping
both rails together across the full mandated matrix.

## xschem

`design/xschemrc` resolves the PDK the same way the harness does and sources
the PDK's own xschemrc, so gf180mcu symbols and this repo's `design/`,
`design/symbols/` and every `sim/<experiment-slug>/testbench/` are all on the
library path:

```bash
source sim/env.sh
cd design && xschem
```

Schematic netlists are written to `design/netlist/`. To simulate a schematic,
strip it to a fragment (or netlist a testbench schematic without its
`.control`/`.end` block) and point a `tb.json` at it — the corner runner is
agnostic about whether the fragment was typed or generated.

Note: xschem itself is not required to run any of the above; the corner runner
only needs ngspice and the PDK.
