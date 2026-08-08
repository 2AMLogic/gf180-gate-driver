# design — schematics and netlists

Schematic capture is xschem; simulation is ngspice via the corner runner in
[`../sim/`](../sim/README.md).

```
design/
  xschemrc     repo xschem config: resolves the PDK, adds repo symbol libraries
  symbols/     repo-local .sym files (created when the first one exists)
  netlist/     xschem-generated .spice netlists (created on first netlist)
```

**Hierarchical schematic-cell symbols must live next to their `.sch`, not in
`symbols/`.** xschem auto-descends into a child schematic only when the
referencing symbol is found at the *same relative path* as a same-named
`.sch` file (e.g. `design/gate_driver_core.sym` next to
`design/gate_driver_core.sch`, both referenced bare as
`{gate_driver_core.sym}`). A symbol placed under
`design/symbols/gate_driver_core.sym` cannot find `design/gate_driver_core.sch`
next to it and instead netlists as an empty subcircuit — no error, just
missing devices, which is easy to miss. `design/symbols/` remains the right
place for symbols that are *not* schematic-derived (e.g. hand-authored device
symbols with no matching `.sch`).

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
result. The runner does not care whether a fragment was generated or typed by
hand.

## Two-rail devices

This is a two-rail design (spec/gate-driver.md §3): 3.3 V logic in
(`nfet_03v3`/`pfet_03v3`, thin-oxide) driving a 5 V/6 V output stage
(`nfet_06v0`/`pfet_06v0`, thick-oxide, per spec §2.5). Per DRM 7.2, both
flavors must not share a DNWELL — keep 3.3 V and 5 V/6 V devices in separate
DNWELL regions (or keep the 3.3 V side outside any DNWELL) from schematic
capture onward, not as a layout-time surprise (spec §2.4).
