# design — schematics and netlists

Schematic capture is xschem; simulation is ngspice via the corner runner in
[`../sim/`](../sim/README.md).

```
design/
  xschemrc              repo xschem config: resolves the PDK, adds repo symbol libraries
  gate_driver_core.sch  TOP cell: instantiates level_shifter + output_stage + uvlo
  gate_driver_core.sym  its hierarchical symbol (must sit here, see below)
  level_shifter.sch     sub-cell (spec §4), + level_shifter.sym
  output_stage.sch      sub-cell (spec §3), + output_stage.sym
  uvlo.sch              sub-cell (spec §5, decision record 0001 Decisions 4-5), + uvlo.sym
  symbols/              repo-local .sym files that are NOT schematic-derived
  netlist/              xschem-generated .spice netlists
```

## Cell hierarchy

`gate_driver_core` is the top cell: it instantiates `level_shifter` (`x1`),
`output_stage` (`x2`) and `uvlo` (`x3`, issue #220) and wires them per
`spec/gate-driver.md` and `spec/decision-records/0001` Decision 1's port list —

```
IN ─▶ x1 level_shifter ─▶ IN_DRV ─▶ x2 output_stage ─▶ OUT
      (VDD/GND_LOGIC + VDD/GND_DRV)   (VDD/GND_DRV)

x3 uvlo (VDD_DRV, GND_DRV, OUT) -- monitors VDD_DRV only, actively pulls
OUT low (independent of IN/IN_DRV) whenever VDD_DRV is below the release
threshold (decision record 0001 Decision 5)
```

`IN_DRV` is the only signal net between `x1`/`x2`; `VDD_DRV`/`GND_DRV` are
shared across all three sub-cells, and `VDD_LOGIC`/`GND_LOGIC`/`IN` reach the
level shifter only. `x1`/`x2` are non-inverting (the level shifter's
2-inverter drive-rail output buffer; the output stage's 6-stage chain), so
the block is non-inverting per decision record 0001, Decision 3, independent
of UVLO's own OUT-override. Measured PVT numbers for `x3`'s trip
thresholds/hysteresis/response time diverge substantially from decision
record 0001 Decision 4's targets at temperature/process extremes — see
`spec/decision-records/0018-uvlo-comparator-pvt-measurement.md` and
`design/uvlo-comparator-sizing.md` before assuming the typ numbers hold at
every corner.

**Hierarchical schematic-cell symbols must live next to their `.sch`, not in
`symbols/`.** xschem auto-descends into a child schematic only when the
referencing symbol is found at the *same relative path* as a same-named
`.sch` file — hence `design/gate_driver_core.sym` next to
`design/gate_driver_core.sch`, both referenced bare as
`{gate_driver_core.sym}`, and likewise for `level_shifter` / `output_stage`. A
symbol placed under `design/symbols/gate_driver_core.sym` cannot find
`design/gate_driver_core.sch` next to it and instead netlists as an empty
subcircuit — no error, just missing devices, which is easy to miss.
`design/symbols/` remains the right place for symbols that are *not*
schematic-derived (e.g. hand-authored device symbols with no matching `.sch`).

Generate a cell's symbol from its own `.sch` rather than drawing pin geometry by
hand, then hand-add only a provenance comment block:

```bash
cd design && awk -f "$(dirname "$(command -v xschem)")/../share/xschem/make_sym.awk" \
  300 gate_driver_core.sch
```

Note that `make_sym.awk` emits pins grouped by direction, so the resulting
`.subckt` port **order** is the symbol's pin order, not the order the `ipin`/
`opin` instances appear in the schematic (for `gate_driver_core` that is
`VDD_LOGIC GND_LOGIC IN OUT VDD_DRV GND_DRV`). Connect by name, and read the
port order off the committed netlist rather than assuming the spec table's
order.

## Running xschem

```bash
source sim/env.sh     # exports PDK_ROOT / PDK / XSCHEM_USER_LIBRARY_PATH
cd design && xschem   # xschem reads ./xschemrc from the working directory
```

`design/xschemrc` finds the gf180mcu install by the same rules as the harness
(`GF180_PDK_PATH`, then `PDK_ROOT`+`PDK`, then the usual prefixes — see
`sim/README.md`), sources the PDK's own xschemrc so the gf180mcu device symbols
are on the library path, and adds `design/`, `design/symbols/` and every
`sim/<experiment-slug>/testbench/`. Netlists are written to `design/netlist/`
so they are reviewable in git rather than landing in a scratch directory.

## Getting a schematic into the corner runner

The corner runner consumes netlist *fragments*: devices and sources only, no
`.include`, `.lib`, `.temp`, `.control` or `.end` (the harness supplies those
per PVT point). Netlist the schematic from xschem, strip any simulator
directives, and point a `sim/<experiment-slug>/testbench/tb.json` at the
result. xschem also prepends a `** sch_path: <absolute path>` comment line
naming the local schematic file on disk — strip that too before committing,
since it leaks a machine/worktree-local path that is meaningless (and
sometimes misleading) outside the environment that generated it. A
**hierarchical** netlist leaks two more per expanded child cell, `** sym_path:`
and a second `** sch_path:`, so strip on line *content*, not line number. The
runner does not care whether a fragment was generated or typed by hand.

Netlist a cell (from the repo root, after `source sim/env.sh`) with:

```bash
xschem --rcfile design/xschemrc -x -q -n -s -o design/netlist design/<cell>.sch
grep -v -e '^\*\* sch_path:' -e '^\*\* sym_path:' -e '^\.end$' \
  design/netlist/<cell>.spice > /tmp/nl && mv /tmp/nl design/netlist/<cell>.spice
```

then re-add the cell's hand-written header comment block (each committed
netlist under `design/netlist/` carries one describing its ports and how to
regenerate it). Everything below that header is generated — do not hand-edit
device lines; change the schematic and re-run.

## Two-rail devices

This is a two-rail design (spec/gate-driver.md §3): 3.3 V logic in
(`nfet_03v3`/`pfet_03v3`, thin-oxide) driving a 5 V/6 V output stage
(`nfet_06v0`/`pfet_06v0`, thick-oxide, per spec §2.5). Per DRM 7.2, both
flavors must not share a DNWELL — keep 3.3 V and 5 V/6 V devices in separate
DNWELL regions (or keep the 3.3 V side outside any DNWELL) from schematic
capture onward, not as a layout-time surprise (spec §2.4).
