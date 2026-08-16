# layout — `gate_driver_core` physical layout

First physical layout for the block. It is **generated, not hand-drawn**:
`gate_driver_core.gds` is the byte-reproducible output of running
[`gen_gate_driver_core.py`](gen_gate_driver_core.py) against
[`../design/netlist/gate_driver_core.spice`](../design/netlist/gate_driver_core.spice)
and the gf180mcu PDK, with every polygon produced by `klt`
([klayout-tools](https://github.com/2AMLogic/klayout-tools), this repo's stated
layout tooling).

```
layout/
  gate_driver_core.gds              the layout database (top cell: gate_driver_core)
  gate_driver_core.provenance.json  what it was built from, and by what
  gate_driver_core.checks.json      the checks below, as run on the committed GDS
  gen_gate_driver_core.py           the generator
  check_gate_driver_core.py         the checker
  build/                            generator scratch (gitignored)
```

## Status: geometrically complete, not signed off

| | |
|---|---|
| Device list matches the schematic | yes — 24 netlist devices → 959 transistors, verified |
| Gate/source/drain connectivity matches | yes — verified device-by-device against the netlist |
| 3.3 V and 5 V/6 V devices in separate DNWELL regions | yes — verified geometrically (DRM 7.2) |
| DRC-clean | **no — never run** (issue #105) |
| LVS-clean | **no — never run** (issue #105) |
| Bulk/body terminals tied | **no — no well or substrate taps drawn** (issue #105) |

This is the checkpoint issue #104 asked for: a geometrically complete layout
that matches the schematic's devices and connectivity. DRC/LVS closure and
post-layout verification are issue #105's scope; nothing here should be read
as a signoff claim.

## Regenerating

```bash
python3 layout/gen_gate_driver_core.py     # rewrites gate_driver_core.gds + provenance
python3 layout/check_gate_driver_core.py --report layout/gate_driver_core.checks.json
```

The generator needs `klt` on `PATH` and a resolvable gf180mcu install (it uses
`klt pdk find`'s resolver — the same one `sim/env.sh` reports). It links
nothing itself: it is standard-library Python that shells out to `klt`.
Re-running it on the same inputs reproduces the GDS **byte for byte**, so
`gate_driver_core.provenance.json`'s `sha256` is a checkable claim, not a
decoration.

To look at it:

```bash
klayout layout/gate_driver_core.gds       # or: klt render layout/gate_driver_core.gds
klt stats layout/gate_driver_core.gds --per-layer
klt cells layout/gate_driver_core.gds
```

## How it is built

1. **Flatten.** The two sub-cells `level_shifter` (`x1`) and `output_stage`
   (`x2`) are flattened into one device list carrying top-level net names.
   Internal sub-cell nets keep an `x1_`/`x2_` prefix (`x1_nca`, `x2_n3`, …).
2. **Devices — `klt gen mos_array`, once per netlist device.** A device with
   `m=M` is drawn as a single unit device folded into `M` parallel gate
   fingers (`finger_topology: "parallel"`), which is exactly what `m=M` means
   in SPICE: `M` transistors of width `W` sharing one source, drain and gate
   strap. `klt extract` reads them back as `M` parallel transistors, so the
   layout's transistor count equals the netlist's (959) rather than 24.
3. **Wiring + markers — `klt draw`, once.** One flat cell carrying the Metal2
   net rails, the Metal1 stubs and gate routes, the Via1 stack between them,
   the net-name labels, and the voltage-domain marker geometry.
4. **Composition — `klt gen-compose`** with `placement.strategy: "explicit"`,
   merging the 24 device cells and the wiring cell into one
   `gate_driver_core` top cell at the origins step 2 computed.

### Floorplan

Every device is a left-aligned horizontal strip; strips stack upward in
netlist order — the four thin-oxide 3.3 V devices first, then a 20 µm domain
gap, then the twenty thick-oxide 5 V/6 V devices. `mos_array` puts a strip's
source pad on its left edge, its drain pad on its right edge and its gate pad
on its top edge, which gives a router-free orthogonal wiring scheme:

- net rails run **vertically on Metal2**, in a channel left of the strips
  (sources and gates) and a channel right of them (drains);
- a **Metal1** stub runs horizontally out of each pad to its rail and drops a
  **Via1**; a gate route leaves the top of its strip and crosses the empty
  channel above it to the left rail;
- each net's left and right rail are tied by one horizontal **Metal1** jumper
  in a cross-over band above the whole stack.

Metal1 stubs therefore pass *under* unrelated Metal2 rails with no via, which
is what keeps the scheme short-free without a router. The result is
553 × 494 µm — dominated by `x2_XMP6`/`x2_XMN6`, the 500- and 220-finger final
output devices.

### Two-rail / DNWELL partition

Per [`../spec/gate-driver.md` §2.4](../spec/gate-driver.md) (DRM 7.2) and the
device table in
[`../design/level-shifter-partition.md`](../design/level-shifter-partition.md):

- the twenty `*_06v0` thick-oxide devices sit inside one `DNWELL` (12/0)
  region — `DNWELL_DRV` — with `Dualgate` (55/0) over the same group and an
  `LVPWELL` (204/0) patch under each thick-oxide nfet;
- the four `*_03v3` thin-oxide devices sit **entirely outside any DNWELL**,
  which is §2.4's second allowed option and the one the partition table
  already committed to.

No DNWELL is shared between the two flavors, and there is exactly one DNWELL
polygon in the design.

## Checks

`check_gate_driver_core.py` runs three checks against the *committed* GDS via
`klt` — it never reads the generator's internal state, so it audits the stream
rather than replaying how it was made. Its output is committed as
`gate_driver_core.checks.json`.

| Check | What it does |
|---|---|
| `devices` | `klt extract --deck gf180mcu`, then compare every extracted transistor against the flattened netlist: a device with `m=M` must appear as `M` transistors of the same W/L whose gate net and unordered source/drain pair match. Passing means 959/959 with no missing and no unexpected device. |
| `dnwell_partition` | `klt components` with `DNWELL` declared *both* as a conductor and as the via joining it to `Comp`, so every active region a DNWELL polygon overlaps lands in the DNWELL's own component. Asserts exactly 20 active regions inside (the 5 V/6 V devices) and 4 outside (the 3.3 V devices). |
| `voltage_domain` | `klt layers --flattened` for the marker layers, plus the `voltage_domain_warnings` block `klt extract` returns — see the deck caveat below. |

This is a device-count/connectivity check, **not** LVS. `klt lvs` belongs to
issue #105.

## Known gaps (all deferred to #105, none accidental)

- **Not DRC-clean, not LVS-clean.** `klt drc` has never been run on this
  stream. Expect real violations: the wiring scheme was built for topological
  correctness, not spacing compliance, and `klt gen`'s own DRC-safe defaults
  only cover geometry inside a device cell.
- **No body ties, no guard ring.** Bulk terminals are unconnected: no well or
  substrate taps are drawn, and `DNWELL_DRV` has no PCOMP guard ring (DRM 7.2
  requires one). A closed tap ring has to be cut for every signal crossing the
  domain boundary, which is a routing plan rather than a marker rectangle —
  that work belongs with DRC/LVS closure. `klt extract` reports the drawn
  consequence directly: 660 PMOS bodies on anonymous nets.
- **klt's gf180mcu deck does not model `Dualgate` scoping.** Every thick-oxide
  device in this layout extracts against the **3.3 V** model
  (`nfet_03v3`/`pfet_03v3`) and is DRC-checked against 3.3 V thresholds, even
  though it is drawn entirely inside `Dualgate` — klt reports this itself in
  `voltage_domain_warnings`, and its gf180mcu deck documents it as a known
  gap. The checker therefore compares device *flavor* (n/p) and W/L, never the
  extracted model name, and records klt's warning in the report so the gap is
  visible rather than silently absorbed. This is the canary's medium-voltage
  friction showing up exactly where CLAUDE.md predicts it would; filed
  upstream per the friction protocol.
- **`klt gen`'s MOS generators cannot draw a voltage-domain / thick-oxide
  marker themselves**, so `Dualgate`/`DNWELL`/`LVPWELL` had to be drawn by
  `klt draw` alongside the generated device cells rather than requested as a
  generator param — also filed upstream.
- **Device aspect ratios are whatever `m` folds into a single row.** The
  500-finger `x2_XMP6` is 486 µm wide and 13 µm tall. Electrically it is what
  the netlist asks for; as a floorplan it is a first cut.
