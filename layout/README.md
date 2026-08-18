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
  ground_rail_negative_control.py   known-good/known-bad control for the
                                    ground_rail_isolation check (#132)
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
| LVS-clean | yes — `status: match`, 959/959 devices, 17/17 nets, 17/17 pins, **1 warning-only finding below (unrelated to body ties)** |
| Bulk/body terminals tied | **yes, both flavors (#132)** — every one of the 959 drawn transistors has a real, drawn, contacted body tie to the schematic's own net (`VDD_LOGIC`/`VDD_DRV` for the 660 PMOS, `GND_LOGIC`/`GND_DRV` for the 299 NMOS). `klt lvs`'s `device.body_unverified` finding — 959 mismatches before this issue — is **gone entirely**, not just reduced (see [Known gaps](#known-gaps) for the one real, permanent side effect: the two grounds extract as one merged net) |
| Post-layout simulation | yes — two full PVT-grid records on the LVS-verified extracted netlist (with and without interconnect RC), `sim/gate-driver-core-drive-postlayout/`. Both records' overall verdict is `FAIL` on **inherited** misses the schematic-side record already carries — [enumerated below](#post-layout-simulation), not summarised away |

Both verdicts are real (each has a committed negative control, below) but
neither is a tapeout signoff: the deck does not carry rules for this layout's
well/marker layers, and the DRC deck cannot check the guard ring's own
geometry (only its *presence*, drawn to satisfy DN.3 by inspection). Read
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
   the net-name labels, the voltage-domain marker geometry, every PMOS
   device's well-tie tap, and the PCOMP guard ring (#132 — see
   "[Body ties and guard ring](#body-ties-and-guard-ring-132)" below).
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

### Body ties and guard ring (#132)

`Interconnect.body_ties()`/`Interconnect.guard_ring()` in
[`gen_gate_driver_core.py`](gen_gate_driver_core.py) draw the substrate/well
tap and PCOMP guard-ring geometry this issue tracks. Every one of the 959
drawn transistors gets its own tap, and the guard ring is closed and
grounded. What each one does, and the one real (not a layout gap) limitation
that remains, follows from reading `klayout-tools`' own
`extract.py`/`decks/gf180mcu.py` rather than assuming:

- **PMOS well ties — real, per-device, and verified.** Every PMOS device gets
  its own Comp+Nplus+Contact+Metal1 tap, positioned just outside its own
  bbox, inside a redundant Nwell rectangle sized to merge with `klt gen
  mos_array`'s own internal well once flattened, and wired to the device's
  own `VDD_LOGIC`/`VDD_DRV` rail. The Nplus layer is not decorative: gf180mcu's
  curated deck has no distinct tap mask, so a bare Comp+Contact+Metal shape
  inside Nwell is geometrically indistinguishable from ordinary PMOS
  source/drain diffusion and is **not** derived into a tap at all — confirmed
  empirically (a first pass of this generator without the Nplus layer still
  extracted every PMOS body onto its own anonymous net, unchanged). Adding it
  invokes the deck's `tap_nplus` derivation (klayout-tools issue #1084):
  `tap_nplus & active & nwell` reads as a genuine well tie. Since every PMOS
  device's Nwell island is geometrically independent (11 separate, non-
  touching islands — no well-merge geometry across devices), each ties to its
  *own* device's real body net with no cross-device or cross-domain merge
  risk. Confirmed against a real `klt extract` run: `unbiased_pmos_body_nets`
  drops from 660 entries to zero.
- **NMOS substrate ties — real, per-device, and drawn for both domains.**
  Every NMOS device gets its own Comp+Pplus+Contact+Metal1 tap, wired to its
  own group's ground rail (`GND_LOGIC` for the four 3.3 V devices,
  `GND_DRV` for the twenty 5 V/6 V devices, whose taps land inside their own
  `LVPWELL` patch). `klt`'s gf180mcu deck still ties *every* NMOS body, in
  every layout, to one hardcoded global identity
  (`ExtractionDeck.substrate_net`, via KLayout's `connect_global`) regardless
  of which DNWELL/LVPWELL region a device's diffusion sits in — confirmed by
  reading `extract.py` directly, filed upstream as a generic tool gap
  (klayout-tools [#1128](https://github.com/2AMLogic/klayout-tools/issues/1128),
  per CLAUDE.md's friction protocol) — so a real tap drawn anywhere merges
  *every* NMOS body (both domains) onto that one identity, and `GND_LOGIC`
  merges with `GND_DRV` in `klt`'s own extracted netlist as a result (a
  synthesized joined label, `GND_DRV|GND_LOGIC`). That merge turned out to be
  survivable rather than disqualifying: `spec/decision-records/0001`
  Decision 1 already ratifies `GND_LOGIC`/`GND_DRV` as **one** electrical
  reference node (option (c), genuinely isolated grounds, was considered and
  rejected), and once real taps exist for *both* domains, the deck's global
  identity stops being an anonymous placeholder — it is directly, physically
  wired to real labeled metal, so `klt extract` names the merged node after
  that real metal instead of its own synthesized `vsubs` fallback. The net
  effect: `klt lvs`'s `device.body_unverified` finding is **fully resolved**
  for NMOS too, not merely downgraded — a real `klt lvs` run against this
  geometry reports **zero** `device.body_unverified` mismatches, on either
  flavor. See "[What the LVS verdict covers](#what-the-lvs-verdict-covers)"
  for the counts, and `lvs/make_reference.py`'s transforms 3 and 5 for how
  the reference models the merge (and `layout/lvs/mk_extracted_dut.py`'s T4
  for how the merge is un-done again for simulation, so the testbench still
  has a net literally named `GND_LOGIC`/`GND_DRV` to drive).

  This merge is the *extractor's* model, not this layout's own routing: the
  two ground rails are drawn as separate Metal2 nets and stay separate in the
  drawn interconnect end to end, which
  `check_gate_driver_core.py`'s [`ground_rail_isolation`](#why-ground_rail_isolation-exists-132)
  check verifies independently of the extractor's substrate-identity model —
  `klt components` over Metal1/Via1/Metal2 only, net names off the Metal2 text
  layer, no deck globals. That check is the *only* remaining automated signal
  that would catch a real short between the two domains (`klt lvs` cannot,
  because of this very merge; DRC cannot, because two overlapping same-layer
  shapes raise no spacing violation), so it carries its own known-good/
  known-bad control — `ground_rail_negative_control.py` — exactly like the
  DRC and LVS verdicts do.
- **PCOMP guard ring — closed, and contacted on two of its four strokes.** A
  closed rectangular Comp+Pplus ring around `DNWELL_DRV`, offset far enough
  out to leave a real, non-touching gap from both `DNWELL_DRV`'s own marker
  and every well-tie tap (so neither `klt drc` nor
  `check_gate_driver_core.py`'s `dnwell_partition` check folds it into either
  side's component count), and pushed further north than that margin alone
  would place it when the 5 V/6 V group's own bbox sits flush against the
  whole device stack's top edge — clearing `jumpers()`'s own Metal1 band
  (every net's cross-over jumper, drawn above the stack) rather than
  threading a contact row through the narrow gaps between individual jumper
  bars (DN.3 sets no *maximum* ring-to-DNWELL distance, so this is always a
  safe direction to move). The **north and south strokes carry a contact
  row** on a regular pitch, strapped on Metal1 to the 3.3 V group's own
  `GND_LOGIC` rail — this block's substrate reference, since the 3.3 V
  devices sit directly on native substrate outside every DNWELL. The **east
  and west strokes carry no contacts**: every 5 V/6 V device's source, gate
  and drain stub leaves the domain horizontally on Metal1 and crosses those
  two strokes, so a Metal1 strap along them would short all of them
  together. Comp and Metal1 do not interact without a Contact bridging them,
  so the crossings themselves are harmless — the strokes are tied through
  the ring's own continuous p+ diffusion instead of through metal, which
  keeps the ring closed (DN.3) and grounded, at a higher tie resistance on
  the two vertical strokes than a fully-strapped ring would have.
  Distributing contacts along them needs a Metal2 crossover per stub, i.e. a
  routing-channel redesign — recorded as a residual gap below rather than
  bolted on here.

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

`check_gate_driver_core.py` runs four checks against the *committed* GDS via
`klt` — it never reads the generator's internal state, so it audits the stream
rather than replaying how it was made. Its output is committed as
`gate_driver_core.checks.json`.

| Check | What it does |
|---|---|
| `devices` | `klt extract --deck gf180mcu`, then compare every extracted transistor against the flattened netlist: a device with `nf=N m=M` must appear as `N*M` transistors of width `W/N` and the same L, whose gate net and unordered source/drain pair match. Passing means 959/959 with no missing and no unexpected device. |
| `dnwell_partition` | `klt components` with `DNWELL` declared *both* as a conductor and as the via joining it to `Comp`, so every active region a DNWELL polygon overlaps lands in the DNWELL's own component. Asserts exactly 40 active regions inside (20 5 V/6 V devices + 20 of their own body-tie taps, issue #132) and 12 outside (4 3.3 V devices + 4 of their own taps + 4 guard-ring strokes). |
| `ground_rail_isolation` | `klt components` over the **routed metal only** — Metal1 (34/0) and Metal2 (36/0) as conductors, Via1 (35/0) as the sole bridge, net names from the Metal2 text layer (36/10). No deck, no device recognition, no substrate global. Asserts no component carries two distinct net names, every routed net resolves to exactly one component, and `GND_LOGIC`/`GND_DRV` land in different components — 18 nets, 18 components. See [why this check exists](#why-ground_rail_isolation-exists-132). |
| `voltage_domain` | `klt layers --flattened` for the marker layers, plus the `voltage_domain_warnings` block `klt extract` returns — see the deck caveat below. |

#### Why `ground_rail_isolation` exists (#132)

Drawing real substrate ties for *both* grounds removed the only two automated
signals that used to distinguish them, at the same time:

* `klt extract` — and therefore `klt lvs` — now reports `GND_LOGIC` and
  `GND_DRV` as one merged net no matter what the metal does, because
  gf180mcu's curated deck ties every NMOS body to one hardcoded substrate
  global ([klayout-tools #1128](https://github.com/2AMLogic/klayout-tools/issues/1128),
  and [Known gaps](#known-gaps));
* the `devices` check normalises that same merge away (`_canon_net`) so it can
  still compare against the schematic.

DRC does not cover the gap either: two same-layer shapes on **different** nets
that overlap merge into one polygon, so no spacing rule fires — the failure is
invisible to a spacing check by construction. `ground_rail_isolation` is
therefore the only thing left that would catch a genuine short between the two
domains in the drawn interconnect, and it rules on the drawn metal rather than
on the extractor's model of the substrate. Its ruling is stated over *all*
nets, not just the two grounds, so an `OUT`/`VDD_DRV` short fails it the same
way.

Its PASS has a committed negative control, like the DRC and LVS verdicts:

```bash
python3 layout/ground_rail_negative_control.py    # needs klt, no PDK
```

[`ground_rail_negative_control.py`](ground_rail_negative_control.py) `klt
draw`s a two-rail fixture in two variants — isolated, and bridged by a Metal1
bar through two Via1 cuts (every shape individually legal, i.e. exactly the
case DRC cannot see) — and runs the **same** layer stack and the **same**
verdict function the block's own report was produced with. It must pass the
first and fail the second, naming both rails. The verdict function itself is
pure (response dict in, check record out), so its failing directions are also
pinned in CI by
[`test_gen_gate_driver_core.py`](test_gen_gate_driver_core.py) against
synthetic `klt components` responses — those cases cannot be produced from the
committed, correct GDS.

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

Latest report: [`layout/drc/reports/gate_driver_core/20260817-232501-dc66e49.drc.json`](drc/reports/gate_driver_core/20260817-232501-dc66e49.drc.json)
— `status: clean`, `violation_count: 0`, deck `gf180mcu`, run against the
stream whose content hash is the committed `gate_driver_core.provenance.json`'s
(issue #132: every device's own body-tie tap plus a closed, contacted PCOMP
guard ring, still DRC-clean). Re-running `klt drc` on the committed GDS
reproduces that report byte for byte.

#### What the DRC verdict covers

`klt drc`'s own report enumerates its scope, and this is the part to read
before quoting "DRC clean":

| Field in the report | Value here | What it means |
|---|---|---|
| `coverage.deck_scope` | 10 DRM sections (Nwell, Comp, Poly2, Contact, Metaln, Vian, MetalTop, MIM option B, DRC_BJT, bond pad) | the deck is a **curated subset** of the gf180mcu DRM, not the whole manual |
| `coverage.layers_checked` | 8 (21/0, 22/0, 30/0, 33/0, 34/0, 35/0, 36/0, 55/0) | the deck layers this stream actually uses. `55/0` (`Dualgate`) newly participates here relative to earlier reports — an interim `klt`/deck update now scopes `DF.1a`/`DF.3a` to it (see `coverage.voltage_domain_warnings` below), not a consequence of this issue's own geometry |
| `coverage.layers_in_stream_without_rules` | **5 — 12/0 `DNWELL`, 31/0 `Pplus`, 32/0 `Nplus`, 36/10, 204/0 `LVPWELL`** | `31/0`/`32/0` are new here: issue #132's per-device body-tie taps draw them (`Pplus` for every NMOS substrate/LVPWELL tie and the guard ring, `Nplus` for every PMOS well tie — gf180mcu's `tap_nplus`/`tap_pplus` derivation, klayout-tools #1084), and this curated *DRC* deck checks no rule against either (only the *extraction* deck reads them). The DNWELL/LVPWELL spacing and enclosure rules of DRM 7.2, and the guard-ring's own geometry, remain **not** checked by this verdict — the guard ring this issue draws is real, closed, contacted geometry, not a DRC-verified one |
| `coverage.rules_skipped` | 23 (metal3…metaltop, via2…via4, MIM, pad, BJT) | rules for layers this two-metal layout does not draw |
| `coverage.voltage_domain_warnings` | 1 | the deck models `DF.1a`/`DF.3a` COMP width/space as `_LV`/`_MV` pairs scoped to the `Dualgate` marker, but **every other rule still applies 3.3 V thresholds to thick-oxide geometry** — see the `Dualgate` gap below |

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

Latest report: [`layout/lvs/reports/gate_driver_core/20260817-232502-dc66e49.lvs.json`](lvs/reports/gate_driver_core/20260817-232502-dc66e49.lvs.json)
— engine **`klayout`** (klayout 0.30.10), `status: match`:

| | layout | reference | matched |
|---|---|---|---|
| devices | 959 | 959 | **959** |
| nets | 17 | 17 | **17** |
| pins | 17 | 17 | **17** |

Net count drops from 30 (pre-#132) to 17: the 11 anonymous per-instance PMOS
well nets are gone, folded into the real `VDD_LOGIC`/`VDD_DRV` pins their
devices' bodies actually belong to, and `GND_LOGIC`/`GND_DRV` collapse from
two nets to one (both issue #132's body-tie taps — see below for why the
ground merge happens and why it is not a routing problem).

The reference netlist ([`lvs/gate_driver_core.ref.spice`](lvs/gate_driver_core.ref.spice))
is **generated, never hand-edited** — `lvs/make_reference.py` derives it from
`design/netlist/gate_driver_core.spice` and applies five mechanical
transforms that the extraction deck's own capabilities force (finger
expansion, generic `nfet`/`pfet` device class, NMOS body → the schematic's
own `GND_LOGIC`/`GND_DRV` assignment, PMOS body → the schematic's own
`VDD_LOGIC`/`VDD_DRV` assignment, and — issue #132's own discovery —
`GND_LOGIC`/`GND_DRV` merging into one net on *every* terminal they appear
on, not just body). `run_lvs.py` regenerates it before every run, so a stale
reference cannot quietly pass, and `lvs/test_make_reference.py` pins each
transform's structural facts in CI without needing `klt` or the PDK.

#### What the LVS verdict covers

`mismatch_count: 1`, **severity `warning`, not a real topology
difference** — listed here rather than dropped:

| Category | Side | Finding |
|---|---|---|
| `topology` | layout | a device class with no counterpart on the other side, **and no devices of that class extracted either** — klt states in the finding itself that this is not a real topology mismatch (it is one of the deck's unused classes: BJT, MIM cap, resistor, diodes). Pre-existing, unrelated to body ties — present in every report this repo has committed for this design |

The `device.body_unverified` finding this table used to carry — 660 PMOS
bodies, then, after a first pass of this issue's own geometry, 299 NMOS
bodies — is **gone entirely** as of issue #132: `match` here now means
drain/gate/source connectivity, device sizing, *and* body bias for every one
of the 959 transistors all match the schematic. See
"[Body ties and guard ring](#body-ties-and-guard-ring-132)" above for why
drawing a real NMOS substrate tie for both grounds resolves this rather than
merely downgrading it, and what it costs (`GND_LOGIC`/`GND_DRV` extract as
one net).

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
| [`lvs/gate_driver_core.extracted-rc.spice`](lvs/gate_driver_core.extracted-rc.spice) | `klt extract --parasitics` | 959 discrete fingers + 2877 R / 17 C per-net ground stars, **including both ground rails** — the merged `GND_DRV\|GND_LOGIC` net's star is emitted with each leg's hub rebound to that leg's *own* device's rail (297 ground-rail legs, issue [#184](https://github.com/2AMLogic/gf180-gate-driver/issues/184)), and its one measured capacitance placed between the two real rails; **still no net-to-net coupling** | its own full PVT grid, run via `--dut` |

Both DUTs still back-annotate every body terminal (BA1/BA2) rather than
reading it off the extractor's own merged `GND_DRV|GND_LOGIC` net directly —
issue #132 made that assertion *redundant with what real extraction now
measures* rather than a fabrication filling an unmeasurable gap
(`mk_extracted_dut.py`'s T4), but it stays a rebind so the testbench still has
nets literally named `GND_LOGIC`/`GND_DRV` to drive (`sim/gate-driver-core-
drive-postlayout/testbench/gate_driver_core_tb.spice` instantiates both, tied
by a small resistor, modeling decision record 0001's "one electrical node").
T4's rebind is no longer only a body-terminal concern, either: since real
tap geometry merges the two grounds at the extraction level (see "[Body ties
and guard ring](#body-ties-and-guard-ring-132)" above), an *ordinary* d/s
connection to a ground rail lands on that same merged identity too, and gets
rebound the same way — per that terminal's own device's real domain (the
same (class, L) fact T4's body rebind already uses), never to one fixed
name. A fixed-name rebind was tried and measured wrong: it silently rerouted
a large fraction of the design's real `GND_DRV` connections (e.g. the output
stage's pull-down stack) through the testbench's tie resistor instead of
straight to the load capacitor's own return node, regressing `n1_min_v`
undershoot broadly.

The campaign, its per-corner results, and the schematic-vs-extracted delta
live in [`sim/gate-driver-core-drive-postlayout/`](../sim/gate-driver-core-drive-postlayout/)
as ordinary append-only `sim/` evidence, re-run against issue #132's now-LVS-
verified extraction (parasitic-free:
[`20260818-002620-ac84870`](../sim/gate-driver-core-drive-postlayout/records/20260818-002620-ac84870.md);
RC: [`20260818-002635-ac84870`](../sim/gate-driver-core-drive-postlayout/records/20260818-002635-ac84870.md)
— both the full 60-point PVT grid, superseding the pre-#132 pair).

**Read these numbers against two already-tracked, pre-existing gaps, not
against #132's own geometry** — neither is something this issue's own body-
tie/guard-ring work introduces or is in scope to fix:

1. **The layout does not yet draw decision record 0007's `IN_DRV`
   compensation capacitor** (`x1_XCCOMP*` — `gen_gate_driver_core.py`'s own
   startup warning names them every run; tracked as issue
   [#166](https://github.com/2AMLogic/gf180-gate-driver/issues/166), whose
   scope changed with issue #192 / [decision record
   0014](../spec/decision-records/0014-xccomp-mim-density-and-series-stack.md):
   it now draws **four** series `cap_mim_2f0_m4m5_noshield` devices at the
   DRM MIMTM.8a minimum 5.0 µm × 5.0 µm, rather than one
   `cap_mim_1f0_m4m5_noshield` that `gf180mcuD` cannot build, extract or LVS
   at all. The committed `gate_driver_core.gds` and its
   `gate_driver_core.provenance.json` predate that change and still name the
   single old device). The
   *schematic*-side record with that capacitor drawn
   (`sim/gate-driver-core-drive/records/20260817-201007-ce8027d.md`) shows
   only the two pre-existing `ipeak_sink_a` stretch misses and no
   `n1_min_v` undershoot anywhere in the grid; the extracted netlist, missing
   the capacitor, does not get that benefit yet.
2. **A harness transient-tolerance refinement (issue #156, landed after the
   pre-#132 postlayout evidence was recorded) moved every §2.3 gate-ceiling
   and undershoot measurement outward** by tens of mV, on both the schematic
   and the layout side alike — tracked for its spec-margin consequences as
   issue [#163](https://github.com/2AMLogic/gf180-gate-driver/issues/163),
   whose own postlayout citation already measured `n1_max_v` moving
   `6.10229 V -> 6.13027 V` on this same extracted (no-RC) netlist; this
   pass's own `20260818-002620-ac84870` record reproduces that exact number.

**What #132 itself changed, isolated from both of the above**: a control run
of the *byte-identical pre-#132* extracted netlist through today's harness
(same environment, same missing capacitor) reproduces the *exact same* set
of 30 `(corner, check)` failures as the post-#132 record — confirmed
per-corner, not just by count. Issue #132's own geometry work introduces
**zero new simulation regressions**; every miss in the current records is
inherited from #166 and #163, not from the taps/guard-ring this issue draws.

| | Parasitic-free (`ac84870`, no-RC) | RC (`ac84870`) |
|---|---|---|
| Overall | `FAIL` — 30/60 points | `FAIL` — 2/60 points |
| `ipeak_sink_a` short of the **1 A stretch** target, `ss_125c`/`sf_125c` 6 V | 0.881 A / 0.932 A | 0.882 A / 0.929 A |
| `n1_min_v` past the inherited **−50 mV undershoot** band | 29 points, worst −59.9 mV | **0 points**, worst −6.8 mV |
| Worst gate-ceiling excursion, taper (`n1_max_v`) | 6.13027 V | 6.00978 V |
| Worst gate-ceiling excursion, `indrv_max_v` | 6.13874 V | 6.01412 V |

The RC record's own pattern is unchanged from the original #105 finding:
**the extracted per-net capacitance damps exactly the ringing that drives the
undershoot band** (0 points fail `n1_min_v` under RC vs. 29 without it), and
layout still costs this block delay, not drive — `ipeak_sink_a` is
essentially identical with and without RC. The two `ipeak_sink_a` stretch
misses are the same pre-existing, narrative-documented shortfall the
schematic-side record already carries (decision record 0007's own summary:
"the only two harness-check misses are the same ... pre-existing
`ipeak_sink_a` 1 A stretch-target shortfall the baseline record already
carried").

These records are a real re-verification of the LVS-closed extraction (issue
#105's original item-3 acceptance criterion, deferred pending #132), not a
tapeout signoff and not a re-litigation of `spec/gate-driver.md` §5's ratified
exceptions — that re-litigation is #163's scope, and drawing the missing
compensation capacitor so postlayout evidence can benefit from decision
record 0007 the way the schematic side already does is #166's (and #164's).

## Known gaps

- **DRC is clean within a deck scope, not against the full DRM.** The deck
  ships no rules for `DNWELL`/`LVPWELL`, and every rule but `DF.1a`/`DF.3a`
  still applies 3.3 V thresholds to thick-oxide geometry — see the coverage
  table above. DRM 7.2's well spacing/enclosure rules, and the guard ring's
  own geometry, are unchecked by any automated verdict in this repo (the
  guard ring #132 draws satisfies the *presence* requirement, not a DRC rule
  this deck can check).
- **Every body terminal ties to a real net, but the deck's own NMOS model
  merges the two grounds into one net (issue #132).** Every PMOS body ties to
  the schematic's own `VDD_LOGIC`/`VDD_DRV` via a real per-device well tap,
  and every NMOS body ties to the schematic's own `GND_LOGIC`/`GND_DRV` via a
  real per-device substrate/LVPWELL tap (`Interconnect.body_ties()`) — `klt
  lvs` reports **zero** `device.body_unverified` mismatches, closing the
  finding that used to cover all 959 bodies (660 PMOS, then 299 NMOS after a
  first pass of this issue's own geometry). The one real, permanent
  consequence: `klt`'s gf180mcu deck ties *every* NMOS body, in every layout,
  to one hardcoded global identity regardless of DNWELL/LVPWELL enclosure
  (read directly from `extract.py`'s `connect_global` handling, not inferred
  from a warning message), so once real taps exist for *both* domains, `klt
  extract` also merges every ordinary terminal wired to either ground rail
  into one net (`GND_DRV|GND_LOGIC` in its own raw output). That merge is the
  *extractor's* model, not this layout's own routing — `GND_LOGIC` and
  `GND_DRV` are drawn and stay as two separate Metal2 nets end to end, which
  `check_gate_driver_core.py`'s
  [`ground_rail_isolation`](#why-ground_rail_isolation-exists-132) check (added
  by this same issue, precisely because the merge takes `klt lvs` out of the
  picture for this one property) verifies independently of the extractor's
  substrate model, with its own known-good/known-bad control — and it is also
  the electrical fact `spec/decision-records/0001`
  Decision 1 already ratifies (one electrical reference node, split into two
  pins only at the pad ring). Filed upstream as the underlying tool
  limitation: klayout-tools
  [#1128](https://github.com/2AMLogic/klayout-tools/issues/1128). See
  "[Body ties and guard ring](#body-ties-and-guard-ring-132)" above for the
  full mechanism, and "[Post-layout simulation](#post-layout-simulation)"
  below for the re-run evidence against the now-fully-verified extracted
  netlist. The post-layout DUT still **rebinds** (rather than reads directly)
  every body terminal to `GND_LOGIC`/`GND_DRV`/`VDD_LOGIC`/`VDD_DRV`
  (`mk_extracted_dut.py`'s T4/BA1/BA2) — not because the assertion is
  unmeasured any more (it now matches real extraction on both flavors), but
  because the testbench needs a net literally named `GND_LOGIC`/`GND_DRV` to
  drive, and the deck's own raw merged label is not one.
- **The RC DUT's ground rails are no longer ideal — the residual is how the
  merged net's one lumped capacitance is placed (issue
  [#184](https://github.com/2AMLogic/gf180-gate-driver/issues/184), closed).**
  Because the deck reports the two grounds as one merged net (previous gap),
  `mk_extracted_dut.py`'s T5 used to skip that net's parasitic star outright,
  leaving both rails as ideal zero-ohm nodes — 297 R legs and the
  `GND_DRV`↔`GND_LOGIC` cap short of the pre-#132 RC DUT, and **optimistic,
  not conservative**, for exactly the ground-bounce/undershoot checks the RC
  record makes. T5 now emits that star with each leg's **hub rebound
  per-device** — leg → R → that leg's *own* device's real `GND_LOGIC`/
  `GND_DRV`, by the same disjoint (class, L) binning as T4/BA1 — which
  reproduces the pre-#132 topology exactly (each rail's own `hub_net` *was*
  that rail's node): 294 legs on `GND_DRV`, 3 on `GND_LOGIC`, 2877 R total,
  and no node anywhere standing in for the merged identity. A shared or
  fixed-name hub is known wrong and is pinned against in CI
  (`lvs/test_mk_extracted_dut.py`) — see `MERGED_GROUND_RAW`'s docstring.
  What is left is an approximation, not a hole: the deck reports **one**
  measured ground capacitance for metal spanning both rails and resolves no
  per-domain split, so it is emitted whole between the two real rails (where
  the pre-#132 `GND_DRV` star's own cap landed) rather than apportioned by
  assertion — 17 C, versus pre-#132's 18, whose extra card was a degenerate
  `GND_LOGIC`-to-itself cap. Measured effect on the RC record, full 60-point
  grid: undershoot deepens on most corners, as restoring rail IR drop should
  (`indrv_min_v` and `n3_min_v` on 60/60 corners, `n5_min_v` on 59/60), the
  worst `n1_min_v` moves −0.00681 V → −0.00680 V (a second-order improvement
  at that one corner; 39/60 corners deepen), and the verdict is unchanged —
  same two failing corners, both on `ipeak_sink_a`'s stretch target. The
  deepest undershoot anywhere on the grid is `n5_min_v` at −0.0205 V against
  the −0.05 V limit (2.4x margin, was −0.0204 V).
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
  pfet). The body-terminal handling behind BA1/BA2 and behind
  `make_reference.py`'s transforms 3/4/5 traces back to the same family of
  upstream deck gaps ([#281](https://github.com/2AMLogic/klayout-tools/issues/281),
  [#555](https://github.com/2AMLogic/klayout-tools/issues/555),
  [#490](https://github.com/2AMLogic/klayout-tools/issues/490), and #1128
  above for the NMOS-substrate-specific one issue #132 investigated).
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
