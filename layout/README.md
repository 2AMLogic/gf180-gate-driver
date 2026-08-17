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
  common/report_id.py               shared <record-id> minting for the run scripts
  drc/                              klt drc runner + committed reports (#105)
  lvs/                              klt extract/lvs runner, reference netlist,
                                    extracted DUT netlists, committed reports (#105)
```

## Status: DRC-clean and LVS-match, within a stated deck scope

| | |
|---|---|
| Device list matches the schematic | yes — 24 netlist devices → 959 transistors, verified |
| Gate/source/drain connectivity matches | yes — verified device-by-device against the netlist |
| 3.3 V and 5 V/6 V devices in separate DNWELL regions | yes — verified geometrically (DRM 7.2) |
| DRC-clean | yes — `status: clean`, 0 violations, **within the deck scope below** |
| LVS-clean | yes — `status: match`, 959/959 devices, 30/30 nets, 19/19 pins, **3 warnings-only findings below** |
| Bulk/body terminals tied | **no — no well or substrate taps drawn**; this is what the LVS `device.body_unverified` warnings are |
| Post-layout simulation | yes — full 60-point PVT grid on the extracted netlist, `sim/gate-driver-core-drive-postlayout/`; **no interconnect parasitics in the simulated DUT** |

Both verdicts are real (each has a committed negative control, below) but
neither is a tapeout signoff: the deck does not carry rules for this layout's
well/marker layers, and the layout has no body ties for LVS to verify. Read
"[What the DRC verdict covers](#what-the-drc-verdict-covers)" and "[What the
LVS verdict covers](#what-the-lvs-verdict-covers)" before quoting either.

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
decoration. That cuts both ways: a change to the generator source must leave
`provenance.generator.sha256` matching `sha256sum layout/gen_gate_driver_core.py`,
even when the stream itself is unchanged — otherwise the record names a
generator that is no longer in the tree.

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
   `W=W nf=N m=M` is drawn as a single unit device folded into `N*M` parallel
   gate fingers of width `W/N` each (`finger_topology: "parallel"`), which is
   exactly what those parameters mean in SPICE: `M` copies of one `W`-wide
   transistor whose width is itself split across `N` fingers, all sharing one
   source, drain and gate strap. `klt extract` reads them back as `N*M`
   parallel transistors, so the layout's transistor count equals the
   netlist's (959) rather than 24, and the total drawn width is `W*M`
   whatever `N` is.

   Both halves of that handoff are load-bearing and both are confirmed rather
   than assumed (issue #129): SPICE's `W` is a *total* width split across `nf`
   fingers (gf180mcu's model cards pass `w=w nf=nf` into the BSIM core and
   size their drift resistors on `w/nf`; this netlist's own `ad`/`ps`
   expressions use `W/nf`), while `klt gen mos_array`'s `w_um` is the
   *per-finger* width — a `"parallel"` unit device is "one folded transistor
   of width `fingers * w_um`" ([`docs/cli/gen.md`][klt-gen]). Every device in
   the committed netlist has `nf=1`, so this is `M` fingers of width `W` and
   the committed GDS is unaffected;
   [`test_gen_gate_driver_core.py`](test_gen_gate_driver_core.py) pins the
   `nf>1` arithmetic against hand-computed values so a future netlist edit
   that folds a device cannot silently draw an `N`×-too-wide transistor.

[klt-gen]: https://github.com/2AMLogic/klayout-tools/blob/main/docs/cli/gen.md
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
| `devices` | `klt extract --deck gf180mcu`, then compare every extracted transistor against the flattened netlist: a device with `nf=N m=M` must appear as `N*M` transistors of width `W/N` and the same L, whose gate net and unordered source/drain pair match. Passing means 959/959 with no missing and no unexpected device. |
| `dnwell_partition` | `klt components` with `DNWELL` declared *both* as a conductor and as the via joining it to `Comp`, so every active region a DNWELL polygon overlaps lands in the DNWELL's own component. Asserts exactly 20 active regions inside (the 5 V/6 V devices) and 4 outside (the 3.3 V devices). |
| `voltage_domain` | `klt layers --flattened` for the marker layers, plus the `voltage_domain_warnings` block `klt extract` returns — see the deck caveat below. |

This is a device-count/connectivity check, **not** LVS — it compares the
extraction against a device list derived from the netlist by the generator's
own parser. The independent comparison is
[`klt lvs`](#lvs-klt-extract--klt-lvs) below.

### Generator unit tests

```bash
python3 layout/test_gen_gate_driver_core.py        # or: npm run test:layout
```

`check_gate_driver_core.py` imports `parse_netlist` from the generator, so it
derives its *expected* device list from the same interpretation the generator
drew from: a misreading of `W`/`nf`/`m` would be common-mode and the `devices`
check would pass on a wrong layout (issue #129).
[`test_gen_gate_driver_core.py`](test_gen_gate_driver_core.py) is the
independent half — hand-computed expectations for that arithmetic, with no
number derived by calling the helpers under test. It is stdlib-only and needs
neither `klt` nor the PDK, so it runs on every PR in CI's `test` job.

## Signoff checks: DRC, LVS, post-layout simulation (#105)

Both runners live next to the layout, mint an append-only
`<YYYYMMDD>-<HHMMSS>-<short-git-sha>` record id (the same convention
[`sim/README.md`](../sim/README.md) defines for simulation evidence), and
**never overwrite an existing report** — a re-run mints a new one.

```bash
python3 layout/drc/run_drc.py layout/gate_driver_core.gds        # -> layout/drc/reports/
python3 layout/lvs/run_lvs.py layout/gate_driver_core.gds        # -> layout/lvs/reports/
python3 layout/lvs/run_pex_extract.py layout/gate_driver_core.gds  # parasitic extraction

# the two controls that make the verdicts above mean something:
python3 layout/drc/deck_negative_control.py
python3 layout/lvs/lvs_negative_control.py
```

### DRC (`klt drc`)

Latest report: [`layout/drc/reports/gate_driver_core/20260817-093625-de81c7b.drc.json`](drc/reports/gate_driver_core/20260817-093625-de81c7b.drc.json)
— `status: clean`, `violation_count: 0`, deck `gf180mcu`
`sha256:e2726af8…`, run against the stream whose content hash
(`sha256:8cdb7cb6…`) is the committed
`gate_driver_core.provenance.json`'s. Re-running `klt drc` on the committed
GDS reproduces that report byte for byte.

#### What the DRC verdict covers

`klt drc`'s own report enumerates its scope, and this is the part to read
before quoting "DRC clean":

| Field in the report | Value here | What it means |
|---|---|---|
| `coverage.deck_scope` | 10 DRM sections (Nwell, Comp, Poly2, Contact, Metaln, Vian, MetalTop, MIM option B, DRC_BJT, bond pad) | the deck is a **curated subset** of the gf180mcu DRM, not the whole manual |
| `coverage.layers_checked` | 7 (21/0, 22/0, 30/0, 33/0, 34/0, 35/0, 36/0) | the deck layers this stream actually uses |
| `coverage.layers_in_stream_without_rules` | **4 — 12/0 `DNWELL`, 36/10, 55/0 `Dualgate`, 204/0 `LVPWELL`** | this layout's well and voltage-domain marker layers carry **no rules at all** in this deck. The DNWELL/LVPWELL spacing and enclosure rules of DRM 7.2, and the guard-ring requirement, are **not** checked by this verdict |
| `coverage.rules_skipped` | 23 (metal3…metaltop, via2…via4, MIM, pad, BJT) | rules for layers this two-metal layout does not draw |
| `coverage.voltage_domain_warnings` | 1 | the deck applies **3.3 V thresholds to thick-oxide geometry** — see the `Dualgate` gap below. Every 5 V/6 V device here is checked against `DF.1a` 0.22 µm rather than `DF.1a_MV` 0.30 µm, `DF.3a` 0.28 rather than 0.36, `DF.6` 0.24 rather than 0.40, `PL.5a/PL.5b` 0.10 rather than 0.30 |

So: **clean against the rules this deck ships, with the medium-voltage
thresholds and the well/marker-layer rules outside it.** That is the honest
scope, and it is exactly the friction CLAUDE.md predicts for the first block
to use the 5 V/6 V flavors.

#### Is `clean` a real verdict?

`layout/drc/deck_negative_control.py` answers that without trusting the
result: it draws two Metal1 rectangles 0.05 µm apart with `klt draw` (which
applies no rule checking) and runs the **same** deck through the **same**
`run_drc.py`. The deck flags it — `metal1.space.1 × 1`, committed as
[`layout/drc/reports/deck-negative-control/`](drc/reports/deck-negative-control/).
A deck that returns `clean` for everything would fail that control.

### LVS (`klt extract` + `klt lvs`)

Latest report: [`layout/lvs/reports/gate_driver_core/20260817-093733-de81c7b.lvs.json`](lvs/reports/gate_driver_core/20260817-093733-de81c7b.lvs.json)
— engine **`klayout`** (klayout 0.30.10), `status: match`:

| | layout | reference | matched |
|---|---|---|---|
| devices | 959 | 959 | **959** |
| nets | 30 | 30 | **30** |
| pins | 19 | 19 | **19** |

The reference netlist ([`lvs/gate_driver_core.ref.spice`](lvs/gate_driver_core.ref.spice))
is **generated, never hand-edited** — `lvs/make_reference.py` derives it from
`design/netlist/gate_driver_core.spice` and applies four mechanical transforms
that the extraction deck's own capabilities force (finger expansion, generic
`nfet`/`pfet` device class, NMOS body → the deck's synthesized `vsubs`, PMOS
body → one anonymous net per drawn well island). `run_lvs.py` regenerates it
before every run, so a stale reference cannot quietly pass, and
`lvs/test_make_reference.py` pins each transform's structural facts in CI
without needing `klt` or the PDK.

#### What the LVS verdict covers

`mismatch_count: 3`, **all severity `warning`, none of them a real
topology difference** — listed here rather than dropped:

| Category | Side | Finding |
|---|---|---|
| `device.body_unverified` | layout | 299 NMOS body terminals were compared against the deck-synthesized `vsubs` substrate net, **not a real schematic net** — no drawn substrate-tap geometry resolves them |
| `device.body_unverified` | layout | 660 PMOS body terminals were compared against an anonymous, deck-synthesized well net — this deck has no distinct well-tap layer |
| `topology` | layout | a device class with no counterpart on the other side, **and no devices of that class extracted either** — klt states in the finding itself that this is not a real topology mismatch (it is one of the deck's unused classes: BJT, MIM cap, resistor, diodes) |

Both `device.body_unverified` findings are the drawn consequence of the "no
body ties, no guard ring" gap below: **`match` here means drain/gate/source
connectivity and device sizing match the schematic; it does not mean body
bias is verified**, because there is no tap geometry to verify it against.

#### Is `match` a real verdict?

`layout/lvs/lvs_negative_control.py` deletes exactly **one** of the 959
reference device cards and re-runs the identical comparison: the verdict
flips to `status: mismatch` with a `device.unmatched` error and 958 reference
devices. Committed as
[`layout/lvs/reports/negative-control/`](lvs/reports/negative-control/). A
comparator that pattern-matched a summary rather than comparing device by
device would not catch a 959-vs-958 delta.

### Post-layout simulation

The LVS-extracted netlist is turned into a simulatable DUT by
[`lvs/mk_extracted_dut.py`](lvs/mk_extracted_dut.py), whose module docstring
and generated file header list every transform (T1…T6) and every
back-annotation (BA1…BA3) applied to the extractor's own output. Two DUTs are
built from the same layout:

| File | Built from | Contents | Used for |
|---|---|---|---|
| [`lvs/gate_driver_core.extracted.spice`](lvs/gate_driver_core.extracted.spice) | the LVS extraction, `--combine` | 42 cards, parallel-identical fingers folded back to `m=<n>`; drawn W/L and measured AS/AD/PS/PD; **no interconnect parasitics** | the full PVT grid |
| [`lvs/gate_driver_core.extracted-rc.spice`](lvs/gate_driver_core.extracted-rc.spice) | `klt extract --parasitics` | 959 discrete fingers + 2877 R / 18 C per-net ground stars | a documented corner subset (the finger-level netlist is far too slow for the whole grid) |

The campaign, its per-corner results, and the schematic-vs-extracted delta
live in [`sim/gate-driver-core-drive-postlayout/`](../sim/gate-driver-core-drive-postlayout/)
as ordinary append-only `sim/` evidence. The first record —
[`20260817-152820-6a5739c`](../sim/gate-driver-core-drive-postlayout/records/20260817-152820-6a5739c.md),
the **full 60-point PVT grid** (5 process corners x -40/27/125 C x three tied
+-10 % supply points plus the 6 V stretch point) — re-runs the same spec suite
the schematic-side record covers, at every one of the same 60 corner-ids, and
lands within **1.8 % on every drive row** and **<= 79 mV on every thick-oxide
gate node**. Both of its harness-check misses are the same inherited -50 mV
undershoot sanity band, on the same node and corner family, that the
schematic-side record already misses; the record's own sections 1-3 explain
each one rather than leaving the one-word verdict to speak.

## Known gaps

- **DRC is clean within a deck scope, not against the full DRM.** The deck
  ships no rules for `DNWELL`/`LVPWELL`/`Dualgate` and applies 3.3 V
  thresholds to thick-oxide geometry — see the coverage table above. DRM 7.2's
  well spacing/enclosure rules and the guard-ring requirement are unchecked by
  any automated verdict in this repo.
- **No body ties, no guard ring.** Bulk terminals are unconnected: no well or
  substrate taps are drawn, and `DNWELL_DRV` has no PCOMP guard ring (DRM 7.2
  requires one). A closed tap ring has to be cut for every signal crossing the
  domain boundary, which is a routing plan rather than a marker rectangle.
  `klt extract` reports the drawn consequence directly (660 PMOS bodies on
  anonymous nets), `klt lvs` reports it as its two `device.body_unverified`
  warnings, and the post-layout DUT has to **assert** the intended body bias
  (BA1/BA2) rather than measure it. Drawing the taps is a layout change, not a
  verification one, so it is not in #105's scope; it is the next thing this
  layout needs.
- **klt's gf180mcu deck does not model `Dualgate` scoping.** Every thick-oxide
  device in this layout extracts against the **3.3 V** model
  (`nfet_03v3`/`pfet_03v3`) and is DRC-checked against 3.3 V thresholds, even
  though it is drawn entirely inside `Dualgate` — klt reports this itself in
  `voltage_domain_warnings`, and its gf180mcu deck documents it as a known
  gap. The checker therefore compares device *flavor* (n/p) and W/L, never the
  extracted model name, and records klt's warning in the report so the gap is
  visible rather than silently absorbed. This is the canary's medium-voltage
  friction showing up exactly where CLAUDE.md predicts it would; filed
  upstream per the friction protocol and still open as klayout-tools
  [#1089](https://github.com/2AMLogic/klayout-tools/issues/1089).

  It has a measured downstream consequence, not just a warning:
  `klt extract --pdk gf180mcuD` binds **every** device in this layout to
  `nfet_03v3`/`pfet_03v3` — all 299 NMOS and all 660 PMOS, including the 955
  thick-oxide fingers drawn inside `Dualgate`. A netlist bound that way would
  simulate 5 V/6 V devices on 3.3 V model cards, so the post-layout DUT
  ([`lvs/mk_extracted_dut.py`](lvs/mk_extracted_dut.py), T2) deliberately does
  **not** use `--pdk`: it re-binds by drawn L, which disjoint-identifies
  flavor in this netlist (0.28 µm thin-oxide, 0.70 µm 6 V nfet, 0.55 µm 6 V
  pfet). The two body-terminal gaps behind BA1/BA2 and behind
  `make_reference.py`'s transforms 3/4 are likewise upstream-tracked
  ([#281](https://github.com/2AMLogic/klayout-tools/issues/281),
  [#555](https://github.com/2AMLogic/klayout-tools/issues/555),
  [#490](https://github.com/2AMLogic/klayout-tools/issues/490)).
- **`klt gen`'s MOS generators cannot draw a voltage-domain / thick-oxide
  marker themselves** (klayout-tools
  [#1054](https://github.com/2AMLogic/klayout-tools/issues/1054)), so
  `Dualgate`/`DNWELL`/`LVPWELL` are drawn by `klt draw` and aligned over the
  generated device cells' reported bounding boxes — which is exactly the
  workaround that issue names. Two more klt gaps shaped this flow and are
  tracked upstream: `gen-compose`'s router is two-pin only, so a shared supply
  rail or any fanout node is unroutable
  ([#1073](https://github.com/2AMLogic/klayout-tools/issues/1073)) — hence the
  hand-built interconnect cell — and a `klt draw` response is not accepted as
  a `gen-compose` block without hand-synthesising a `generator_report`
  ([#1059](https://github.com/2AMLogic/klayout-tools/issues/1059)), which is
  what `gen_gate_driver_core.py` does for the interconnect cell.
- **Device aspect ratios are whatever `m` folds into a single row.** The
  500-finger `x2_XMP6` is 486 µm wide and 13 µm tall. Electrically it is what
  the netlist asks for; as a floorplan it is a first cut.
