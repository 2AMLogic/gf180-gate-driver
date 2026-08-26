# Chipalooza Challenge #5 (GF180MCU / Wafer.Space) — high-voltage gate driver proposal

Submission target: Open Circuit Design's Chipalooza Challenge #5
(GF180MCU test chip fabricated through Wafer.Space), same 3.3 V digital /
5.0 V analog structure as Challenge #3 unless that challenge's own rules
page states otherwise. This repository has not observed a published,
dated submission deadline for Challenge #5 as of this document's writing —
none is asserted here; the operator submitting this proposal should confirm
the current deadline and gated-review schedule directly against the
challenge's own rules page before emailing it.

**Source repository**: `2AMLogic/gf180-gate-driver` (public, Apache-2.0 —
see §7). Every number in §4 is transcribed from this repository's own
append-only `sim/` evidence, with a dated citation to the record it came
from — nothing here is asserted without a re-runnable testbench, per
`CLAUDE.md`'s "no claim without a testbench."

This document is written to be emailed verbatim as the block's public
proposal. It contains no personal or institutional identifiers; a designer
CV and a test-equipment list, if needed, are separate attachments the
submitting operator supplies outside this repository.

**Scope note**: this repository scopes two distinct facets on the same
gf180mcu medium-voltage devices
([decision record 0008](../../spec/decision-records/0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md)).
This proposal covers **facet (a) only** — the ratified high-voltage gate
driver (`spec/gate-driver.md`). Facet (b) (an on-die low-side power-NMOS
driver) has its own ratified spec but no schematic/layout work started, and
is explicitly out of scope for this proposal, per
[issue #219](https://github.com/2AMLogic/gf180-gate-driver/issues/219) and
decision record 0008.

---

## 1. Type of IP block

A single-channel, low-side, high-voltage MOSFET/IGBT gate driver: 3.3 V
logic input, level-shifted through a cascode/clamped topology to a 5 V
nominal (6 V stretch) drive rail that sources and sinks gate charge into an
external, off-die power switch, with undervoltage lockout (UVLO) on the
drive rail.

---

## 2. I/O list, including test ports

### 2.1 Rails: this block's drive rail is a native fit for the Challenge's 5.0 V analog rail

Per [decision record 0001](../../spec/decision-records/0001-block-interface-and-uvlo-parameters.md)
Decision 1, the ratified core cell (`design/gate_driver_core.sch`) exposes
exactly six pins: `VDD_LOGIC`, `GND_LOGIC` (3.3 V logic domain), `IN` (3.3 V
logic control input), and `VDD_DRV`, `GND_DRV`, `OUT` (5 V nominal / 6 V
stretch drive domain). This design exists specifically to exercise
gf180mcu's medium-voltage (`nfet_06v0`/`pfet_06v0`) device flavors
(`CLAUDE.md`: "The medium-voltage devices are the point"), so the drive
domain is proposed to draw `VDD_DRV`/`GND_DRV` directly from the Challenge's
5.0 V analog supply rail, and the logic domain to draw `VDD_LOGIC`/
`GND_LOGIC` from the Challenge's 3.3 V digital rail — no internal regulator
or level-shift-from-a-single-rail scheme is needed or built. §4 reports
every measured row across the analog rail's full 3.3–5.0 V envelope, not
just its 5.0 V nominal point, because the output stage's drive strength is
materially rail-dependent (§4's own findings) and the challenge's own brief
asks for output-stage characterization across that range.

### 2.2 Pad table, mapped to the Challenge #5 slot budget

| Signal | Dir | Challenge slot | Count used | Notes |
|---|---|---|---|---|
| `VDD_LOGIC`, `GND_LOGIC` | supply | 3.3 V digital rail | — (rail, not a slot line item) | Logic supply/return for the pre-driver and level-shifter's thin-oxide side (decision record 0001 Decision 1) |
| `VDD_DRV`, `GND_DRV` | supply | 5.0 V analog rail (proposed, §2.1) | — (rail, not a slot line item) | Drive-rail supply/return; `GND_DRV` and `GND_LOGIC` are the **same electrical node by design** but must be **physically separated at the pad ring** — `OUT`'s high-di/dt switching return must not share a bond wire with the `IN` comparator's reference path (decision record 0001 Decision 1). `GND_DRV`'s return path should be co-located, low-impedance, with `OUT`'s own dedicated pad below |
| `IN` | in | digital control input (budget ≤ 24) | 1 of 24 | Non-inverting logic control input (decision record 0001 Decision 3): `IN` high drives `OUT`/the external switch on. Ratiometric levels `VIH ≥ 0.7×VDD_LOGIC`, `VIL ≤ 0.3×VDD_LOGIC` (decision record 0001 Decision 2) |
| `OUT` | out, dedicated | dedicated pad (budget ≤ 4) | 1 of 4 | Gate-drive output into the 1 nF reference load (spec §3); measured peak source/sink current spans 0.187–1.422 A across the full Challenge #5 PVT/rail grid (§4) — **needs a low-resistance, dedicated path; a shared-mux switch's added series resistance would directly erode drive strength and rise/fall time** |
| `UVLO_N` (**proposed, new — not in the ratified port list**) | out, digital test output (budget ≤ 12) | 1 of 12 | **Not part of decision record 0001's ratified six-pin port list.** `design/uvlo.sch`'s internal comparator/lockout state (`x3.lockout`, internal to `design/gate_driver_core.sch`) is not brought to a top-level pin today — the only externally observable consequence of UVLO lockout is `OUT` being forced low, indistinguishable from a normal `IN`-low cycle without also knowing `VDD_DRV`. Since decision record 0018 documents an **open, unresolved false-trip finding** (§4) that packaged-part characterization needs to observe directly, this proposal recommends adding a dedicated lockout-status test pad (working name `UVLO_N`; **exact polarity and any level-shifting/buffering needed to bring the drive-rail-referenced `x3.lockout` node to a clean digital test level are undecided** — a schematic-design detail, not settled by this document), mapped to one of the Challenge's digital test output slots. **This is a package-level test-pad addition proposed for the tape-out, not a change already made to the ratified core-cell schematic** — see §6 open items; it would need its own follow-up issue (new schematic net, DRC/LVS re-verification) if adopted |

**Totals against the Challenge #5 budget**: 0 of 1 bandgap-referenced bias
voltage, 0 of ≤ 2 bandgap-referenced current sources (this block has **no
bandgap** — decision record 0001 Decision 5 states this explicitly: the
UVLO reference is a diode-connected `nfet_06v0` `Vt` reference, chosen
*because* no bandgap exists in this block, not a bandgap-derived voltage),
1 of ≤ 24 digital control inputs, 1 of ≤ 12 digital test outputs (the
proposed `UVLO_N`), **1 of ≤ 4 dedicated pads**, **0 of ≤ 4 shared
(multiplexed) analog lines**. Every category fits inside budget with wide
headroom — 23 of 24 digital-control-input slots, 11 of 12 digital-test-
output slots, 3 of 4 dedicated-pad slots, and the entire shared-analog-line
and bandgap-current-source allocations are left unused by this block.

### 2.3 What's dropped, multiplexed, substituted, or new relative to this repo's own port list

- **Nothing this block's ratified core cell brings off-chip is dropped.**
  `VDD_LOGIC`/`GND_LOGIC`/`IN`/`VDD_DRV`/`GND_DRV`/`OUT` is exactly decision
  record 0001 Decision 1's port list — nothing is cut to fit the slot
  budget, since the budget has ample headroom (§2.2).
- **`UVLO_N` is new**, not a substitution or a drop — see §2.2's own note
  and §6. It is proposed specifically because bench validation of decision
  record 0018's open false-trip finding needs a direct lockout-state
  observation; simulation could infer it from `OUT`'s behavior only because
  the testbench also controls `IN` and `VDD_DRV` independently, which a
  bench measurement of the packaged part cannot always do at the same
  resolution.
- **No pins are shared/multiplexed.** `OUT` is the one signal with a hard
  low-resistance requirement (§2.2) and is kept dedicated rather than routed
  through the Challenge's shared analog mux.
- **No internal control signals are exposed.** `IN_DRV` (the level shifter's
  drive-rail-referenced output feeding the output stage), the level
  shifter's internal `inb` node, and the output stage's internal taper
  nodes `n1`…`n5` are all internal to `design/gate_driver_core.sch` and are
  not proposed as any of the Challenge's pins — some of them are the very
  nodes §4's oxide-safety exceptions are about, and none of them has a test
  pad in this proposal (see §6, "gate-oxide-margin bench-visibility gap").
- **SPI control is not applicable to this block.** The Challenge #5 budget
  documents SPI control in the harness for blocks that need configuration
  registers; this block is a fixed-function driver with a single control
  input and no internal mode/configuration state (decision record 0001
  Decision 3 explicitly deferred a separate `EN`/mode pin as having "no
  consumer this increment"), so no SPI-addressable register exists or is
  proposed.

---

## 3. Functional description

`IN` (3.3 V logic, non-inverting) drives a cascode/clamped level shifter
(`design/level_shifter.sch`) that crosses from the 3.3 V logic domain to the
5 V nominal / 6 V stretch drive domain without any thin-oxide (3.3 V) node
ever being designed to exceed its 3.63 V DC gate-oxide ceiling — thick-oxide
(`nfet_06v0`/`pfet_06v0`) cascode devices clamp the thin-oxide pull-down
drains, chosen specifically over a plain cross-coupled latch to satisfy
`spec/gate-driver.md` §2.3's oxide-breakdown constraint by construction
(§4). The level-shifted signal (`IN_DRV`) drives a tapered push-pull output
stage (`design/output_stage.sch`, entirely thick-oxide) that sources and
sinks gate charge into `OUT`, targeting a 1 nF reference load (a
gate-capacitance stand-in for a mid-size discrete power MOSFET/IGBT,
`spec/gate-driver.md` §3) with a ≥ 0.5 A nominal / 1 A stretch peak-current
target and a < 50 ns nominal / < 25 ns stretch propagation-delay budget. A
third sub-cell, `uvlo` (`design/uvlo.sch`, added by issue #220), monitors
`VDD_DRV` only (not `VDD_LOGIC`) via a resistive divider compared against a
diode-connected `nfet_06v0` `Vt` reference — there is no bandgap in this
block — and forces `OUT` low, independent of `IN`, whenever `VDD_DRV` is
below the release threshold (decision record 0001 Decisions 4–5). This is a
**low-side-only** configuration: a half-bridge / high-side variant, dead-
time/shoot-through control, and thermal shutdown are all explicitly
deferred to a follow-on spec revision (`spec/gate-driver.md` §1, §5).

The complete block — `level_shifter` + `output_stage` + `uvlo` — is drawn at
transistor level in `layout/gate_driver_core.gds`, DRC-clean (0 violations)
and LVS-matched (2044/2044 devices, 295/295 nets, one benign topology-only
warning unrelated to any device/net mismatch) against the schematic
(`layout/README.md`, decision record 0019). Post-layout, extracted-netlist
PVT re-verification of the complete block (with and without RC interconnect
parasitics) is complete (issue #222, decision record 0019) and is the
governing evidence for §4 below wherever it exists, per this proposal's own
citation convention (§4.0).

---

## 4. Target specification at the Challenge #5 rails

### 4.0 Citation convention

Every row cites a specific, dated `sim/` record. Per this issue's own
instruction, **post-layout (`sim/gate-driver-core-drive-with-uvlo-
postlayout/`, issue #222) records are the governing evidence wherever they
exist**, with the schematic-level record (`sim/gate-driver-core-drive-with-
uvlo/`, issue #220) cited alongside for context; where no post-layout
equivalent exists (UVLO's own trip-voltage/hysteresis/response-time facet —
decision record 0019 Finding 6 explains why: `uvlo` has no independently-
extractable GDS sub-cell), the schematic-level record is the only evidence
and is cited as such, not silently substituted. **Governing post-layout
figures below use the RC-parasitic-extracted netlist**
(`layout/lvs/gate_driver_core.extracted-rc.spice`, the more realistic of the
two post-layout variants), with the parasitic-free extracted variant cited
alongside for corroboration, matching decision record 0019's own reporting
convention.

**What "at the Challenge #5 rails" means here**: `VDD_LOGIC` swept 2.97 /
3.30 / 3.63 V (3.3 V ± 10 %) tied to `VDD_DRV` swept 3.30 / 4.15 / 5.00 V,
across all 5 process corners × 3 temperatures (−40/27/125 °C) — the same
45-point grid `sim/gate-driver-core-drive-with-uvlo(-postlayout)/` already
runs as an explicit "Challenge #5 rails" variant, per `sim/README.md`'s
two-rail tied-supply grid convention. This is **not** `spec/gate-driver.md`
§3's own ratified PVT grid (`VDD_DRV` 4.5/5.0/5.5 V ± 6 V stretch) — where a
row's only evidence is at the spec grid, that is stated explicitly.

| Parameter | Target | Measured (Challenge #5 grid, 3.3–5.0 V envelope) | Verdict | Source (dated) |
|---|---|---|---|---|
| Peak source current, `OUT` | ≥ 0.5 A (target defined at the 5 V nominal rail, `spec/gate-driver.md` §3) | Full envelope: 0.187 A (`ss_125c`, `vdrv`=3.30 V) – 1.422 A (`ff_-40c`, `vdrv`=5.00 V). **At `vdrv`=5.00 V specifically: 0.715–1.422 A, all 15 process×temp points clear the target** (min 43 % margin, `ss_125c`). At `vdrv`=4.15 V: 3 of 15 points (all `ss`) fall short, worst 0.358 A. At `vdrv`=3.30 V: 13 of 15 points fall short, worst 0.187 A | **MET at 5.0 V** (the rail the target was derived for); **UNMET at 3.30–4.15 V** — expected, since §3's ≥ 0.5 A target was never derived for a rail below 4.5 V | `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-074240-a7dcce1.md` (post-layout, RC-extracted, issue #222); corroborated, no-RC, `20260826-074206-a7dcce1.md`; schematic context `sim/gate-driver-core-drive-with-uvlo/records/20260826-013219-6299c36.md` (issue #220) |
| Peak sink current, `OUT` | ≥ 0.5 A (same basis as above) | Full envelope: 0.215 A (`ss_125c`, `vdrv`=3.30 V) – 1.273 A (`ff_-40c`, `vdrv`=5.00 V). **At `vdrv`=5.00 V: 0.668–1.273 A, all 15 points clear the target** (min 34 % margin, `ss_125c`) | **MET at 5.0 V**; **UNMET at 3.30–4.15 V**, same basis as source current | Same records as above |
| Propagation delay, `tpdlh`/`tpdhl` | < 50 ns nominal | Full envelope: `tpdlh` 8.82–21.43 ns, `tpdhl` 6.26–14.88 ns — **every one of the 45 points clears the 50 ns target**, worst-case margin ≥ 57 % | **MET**, full 3.3–5.0 V envelope, no exceptions | `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-074240-a7dcce1.md` (RC, governing) |
| Rise/fall into 1 nF reference load, 10–90 % | < 50 ns | Full envelope: `trise` 0.73–10.57 ns, `tfall` 0.54–8.00 ns — **every point clears the target**, worst-case margin ≥ 79 % | **MET**, full envelope | Same record |
| UVLO trip voltage & hysteresis | Design target (decision record 0001 Decision 4): falling typ 3.6 V (band 3.3–3.9 V), rising typ 3.9 V (band 3.6–4.2 V), hysteresis typ 0.3 V | Measured, full 15-corner grid: falling **2.231–4.737 V**, rising **2.503–5.115 V**, hysteresis **0.273–0.378 V** — roughly 3× wider than decision record 0001's originally-budgeted band, root-caused to the reference divider's ~5× amplification of the diode reference's own process *and temperature* spread (decision record 0018 Finding 1) | **UNMET** against decision record 0001's original design-target band — decision record 0001's numbers are **superseded** by these measured ranges, not narrowed to fit | `sim/uvlo-trip-verification/records/20260826-013053-6299c36.md` (schematic-only; no post-layout equivalent exists — decision record 0019 Finding 6, `uvlo` has no independently-extractable GDS sub-cell) |
| UVLO lockout response time (`VDD_DRV` crossing falling threshold → `OUT` low) | < 500 ns | 95.0–238.0 ns across all 15 corners, worst case `ss_-40c` | **MET**, ≥ 52 % margin at the worst corner | Same record, decision record 0018 Finding 4 |
| UVLO guaranteed-off (`VDD_DRV` < 3.3 V forces lockout) | Lockout at `VDD_DRV` < 3.3 V | Confirmed with margin down to `VDD_DRV` = 2.0 V, all 15 process×temp points, full block | **MET**, with margin | `sim/gate-driver-core-drive-with-uvlo/records/20260826-013206-6299c36.md` (issue #220) |
| **UVLO false-trip risk** — release above `spec/gate-driver.md` §3's −10 % low-line floor (4.50 V) | Guaranteed-on above 4.2 V (decision record 0001 Decision 4's literal claim) | `ss_-40c` remains locked out up to a measured 5.115 V rising threshold — **above the drive rail's own −10 % low-line floor** — corroborated directly in the full-block context (both spec-rail and Challenge #5-rail grids) at the schematic level and, independently, post-layout | **UNMET — open, unresolved safety finding**, not a bounded exception. Carried forward unchanged, not narrowed or waved through | Decision record 0018 Finding 2 (schematic); decision record 0019 Finding 2 (post-layout corroboration, same two corners `ss_-40c`/`sf_-40c` at `vdrv`4.50 V), Finding 4 (Challenge #5-rail grid shows the same pattern reproduced, `26/45` and `29/45` overall PASS points respectively, `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-074206-a7dcce1.md` / `-074240-a7dcce1.md`) |
| Oxide safety — domain-crossing cascode clamp (thin-oxide nodes protected from the drive rail) | No thin-oxide node designed to exceed 3.63 V DC | `vna_peak`/`vnb_peak` (cascode-protected thin-oxide drains) stay 1.88–2.78 V across the full sweep this evidence covers | **MET** at the corners measured — **caveat: this evidence's own `vdrv` sweep is 4.50–6.00 V** (`sim/level-shifter-oxide-safety/`), not re-run at the Challenge #5 envelope's low end (3.30/4.15 V); not re-verified at those two points (§6 open item) | `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`; decision record 0002 |
| Oxide safety — Exception 1 (pre-driver inverter output `inb` overshoots its own `VDD_LOGIC` rail) | Bounded ≤ 40 mV above `VDD_LOGIC`, only at the `vlogic`=3.63 V (+10 %) corner | Measured 20.34–35.33 mV at harness default tolerance, worst case 3.66533 V; re-solved to convergence, 20.17–35.67 mV | **MET** (bounded exception, not a design defect) — **applies at the Challenge #5 rails**, since `vlogic`=3.63 V is present in that grid's high tied-supply point (`vdrv`=5.00 V) and the overshoot mechanism is internal to the logic domain, independent of `vdrv` | `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`; decision records 0003, 0015 |
| Oxide safety — Exceptions 2/3 (output-stage taper nodes `n1`…`n5`; inter-cell node `IN_DRV`) | Bounded ≤ 175 mV / ≤ 10 mV above the 6.0 V thick-oxide ceiling, only at the **6 V stretch rail** | 6.0 V stretch rail is outside the Challenge #5 envelope (max 5.0 V); the Challenge #5 postlayout grid's own `n1`…`n5` measurements top out at 5.021–5.061 V (worst case `n5`, no-RC variant), well inside the 6.0 V ceiling at every one of the 45 points | **N/A / does not apply at the Challenge #5 rails** — both exceptions are structurally confined to the 6 V stretch corner this proposal's rail range never reaches | `sim/gate-driver-core-drive-with-uvlo-postlayout/records/20260826-074240-a7dcce1.md` (RC, spread table, `n1_max_v`…`n5_max_v` ≤ 5.04 V) and `20260826-074206-a7dcce1.md` (no-RC, `n5_max_v` = 5.06136 V, the grid's overall worst case); decision records 0005, 0006, 0013 (bound definitions) |
| Stretch-rail sink-current shortfall (`ss_125c`/`sf_125c` at 6 V stretch) | Bounded ≥ 0.85 A at 2 named corners, 6 V stretch rail only | Same reasoning as the row above — the 6 V stretch rail is outside the Challenge #5 envelope | **N/A at the Challenge #5 rails** | Decision record 0016 (bound definition; not re-evidenced here since it does not apply to this proposal's rail range) |
| Layout signoff | DRC + LVS clean (`spec/gate-driver.md` §3) | DRC: `status: clean`, 0 violations. LVS: `status: match`, 2044/2044 devices, 295/295 nets, 25/25 pins, one benign warning-only topology finding unrelated to any device/net mismatch | **MET** | `layout/README.md` ("Status: DRC-clean and LVS-match" section); `layout/drc/reports/gate_driver_core/20260826-044706-fdf17d9.drc.json`; `layout/lvs/reports/gate_driver_core/20260826-062806-a7dcce1.lvs.json`; decision record 0019 |

None of the rows above had any evidence at a Challenge-#5-rail point to
report as "unmet" that wasn't already reported that way in this repository's
own decision records before this proposal was written — every UNMET or
N/A verdict traces to an existing, previously-ratified finding (decision
records 0016, 0018) or to a straightforward consequence of this rail range
not reaching the 6 V stretch corner those bounded exceptions are scoped to.
No spec row is relaxed, narrowed, or silently dropped to make it pass, per
`CLAUDE.md`.

---

## 5. Bench test plan (packaged part, on a daughterboard + test board)

All measurements below use only the pads in §2.2 — `IN` (digital control
input), `OUT` (dedicated pad), and the proposed `UVLO_N` (digital test
output); none require the Challenge's shared analog mux lines, which this
block does not use.

1. **Bring-up / DC sanity.** Apply `VDD_LOGIC` (3.3 V from the digital
   rail) and `VDD_DRV` (from the analog rail, initially at its 5.0 V nominal
   point). Tie `GND_LOGIC` and `GND_DRV` together at a single star point
   close to the device, per decision record 0001 Decision 1's explicit
   testbench requirement — do not leave them floating relative to each
   other. Confirm `OUT` sits low with `IN` low and no `uvlo`-forced lockout
   asserted (`UVLO_N` released) at nominal supply.
2. **Functional / polarity check.** Toggle `IN` at a low, non-switching-
   stress rate into a bench 1 nF (or a representative discrete power
   MOSFET/IGBT) gate load, and confirm `OUT` tracks `IN` non-inverting
   (decision record 0001 Decision 3) across the available `VDD_DRV` range on
   the daughterboard.
3. **Drive-strength / dynamic characterization.** Drive `IN` at the target
   switching rate into the reference load, and measure `OUT`'s peak
   source/sink current (a current probe or a known-resistance shunt in the
   `OUT`/load path) and propagation delay/rise/fall (an oscilloscope
   comparing `IN` and `OUT` edges). Sweep `VDD_DRV` across 3.3–5.0 V and
   temperature (an environmental chamber or a temperature-controlled
   probe/socket) and compare against §4's PVT grid — in particular, confirm
   the ≥ 0.5 A target is met at the 5.0 V rail point and observe the
   expected shortfall at the low end, matching §4's simulated pattern rather
   than treating it as a bench-only surprise.
4. **UVLO trip / hysteresis / response-time characterization.** Sweep
   `VDD_DRV` down and back up slowly through the trip band (a programmable
   supply with a slow ramp, or a manual step sweep) while monitoring `OUT`
   and the proposed `UVLO_N` test pad with `IN` held high. Record the
   falling and rising trip voltages and hysteresis, and compare against
   §4's measured 2.231–4.737 V / 2.503–5.115 V simulated range. **Sample
   across multiple die/lots specifically to probe the false-trip risk
   §4 documents as open** — the affected process corner (slow-NMOS/slow-
   PMOS, cold) is a statistical sampling question on packaged silicon, not
   something a single-die bench characterization can select directly; a
   negative result on one die does not clear the open finding.
5. **UVLO response-time measurement.** With `VDD_DRV` stepped rapidly
   across the falling threshold (a fast supply step or a switch-selected
   two-rail source), measure the delay from the step to `OUT` reaching a
   safe-low level and to `UVLO_N` asserting, and compare against the
   < 500 ns target and the 95–238 ns simulated range.
6. **Repeat across the daughterboard's available supply/temperature range**
   to compare directly against §4's simulated PVT grid, and note any
   deviation as a genuine silicon finding requiring a new, dated `sim/`
   record and (if it narrows a margin) a new decision record, per this
   repository's own evidence-trail convention — not folded silently into
   this document.
7. **Gate-oxide-margin bench-visibility gap, noted for completeness.** The
   internal nodes §4's three oxide-safety exceptions are about (`inb`,
   `n1`…`n5`, `IN_DRV`) have no test pad in this proposal and cannot be
   directly probed on packaged silicon; this bench plan cannot independently
   confirm those bounds by direct measurement, only indirectly (functional
   pass/fail and, if ever pursued, accelerated-life/reliability testing,
   both out of scope for this bench plan).

---

## 6. Open items before this proposal's evidence trail is considered complete

1. **UVLO false-trip risk (§4) is an open, unresolved safety finding, not a
   bounded exception.** At the `ss`/−40 °C process/temperature corner, the
   block can remain locked out at legitimate, in-spec operating points on
   both the ratified spec grid and the Challenge #5 grid. Closing it needs a
   reference-topology redesign (e.g. a lower-gain reference stack or an
   actual bandgap) that decision record 0018 explicitly defers as "a
   materially different circuit from decision record 0001 Decision 5's
   specified topology," not something this proposal, or the issue that
   produced it, can resolve. **This is disclosed here, not concealed**, per
   `CLAUDE.md`'s "agents do not relax the ratified spec to make results
   pass."
2. **A separate, un-excepted nominal-rail drive-strength miss exists at the
   spec grid (not the Challenge #5 grid)**: `ss_-40c_vlogic2p97v-vdrv4p50v`
   falls just under the ≥ 0.5 A source-current target (decision record
   0019 Finding 5), inherited unchanged from issue #220's own schematic and
   not yet covered by any bounded exception. Filed as issue #226; not yet
   resolved. This point is outside the Challenge #5 grid's own `vdrv` sweep
   (3.30/4.15/5.00 V vs. the spec grid's 4.50/5.00/5.50 V), so it is noted
   here rather than in §4's table, but is relevant context for a reviewer
   comparing this design's overall drive-strength maturity.
3. **The domain-crossing cascode-clamp oxide-safety evidence (§4) has not
   been re-run at the Challenge #5 envelope's low end.** `sim/level-shifter-
   oxide-safety/`'s `vdrv` sweep is 4.50–6.00 V; it has never measured
   `vna_peak`/`vnb_peak` at `vdrv` = 3.30 V or 4.15 V. Nothing in the
   existing evidence suggests a problem at the low end (the clamp's
   mechanism does not obviously depend on the low end being reached), but
   this proposal states the gap rather than assuming the result carries
   over unverified.
4. **`UVLO_N` (§2.2) is a proposed, not yet designed, test pad.** Adopting
   it before tape-out needs a new schematic net from `x3`'s internal
   lockout signal to a new top-level pin, plus DRC/LVS re-verification of
   the resulting layout change — tracked here as the item to file a
   follow-up issue for if this proposal is accepted, not implied to already
   exist.
5. **Half-bridge / high-side configuration, dead-time control, and thermal
   shutdown remain deferred** (`spec/gate-driver.md` §1, §5) — this
   proposal is for the single-channel, low-side configuration only, exactly
   as ratified.

None of the above items block *submitting* this proposal — consistent with
this program's stated goal for Chipalooza proposals, the aim is to state the
design honestly at its current maturity with every claim traceable to a
dated `sim/` record, not to have already closed every open item by the
submission date.

---

## 7. Licensing and EDA flow

- **License**: this entire repository — spec, decision records, schematics,
  testbenches, and every evidence record cited above — is licensed
  [Apache-2.0](../../LICENSE), satisfying the Challenge's requirement for a
  standard open license with all modifiable sources public.
- **Flow**: fully open-source. Schematic capture and netlisting via
  [xschem](https://xschem.sourceforge.io/); simulation via
  [ngspice](https://ngspice.sourceforge.io/) (ngspice-46 for the evidence
  cited above); layout, DRC, LVS, and parasitic extraction via
  [KLayout](https://www.klayout.de/) driven by
  [klayout-tools](https://github.com/2AMLogic/klayout-tools) (`klt`, version
  0.3.0 for the current layout signoff); the gf180mcu PDK (`gf180mcuD`
  variant, `open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`)
  resolved via the standard `PDK_ROOT`/`PDK` environment convention this
  repository uses throughout (`sim/env.sh`), interoperable with an
  IIC-OSIC-TOOLS/ciel-based flow though not itself built on top of either.
  Every cited `sim/` record's `## Environment` section states the exact
  pinned toolchain versions that produced it, so any reviewer can re-run the
  cited evidence from a clean checkout (`python3 sim/run_corners.py
  <experiment-slug>`, documented in `sim/README.md` and
  `sim/harness/README.md`).
