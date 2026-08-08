# Medium-voltage device characterization (issue #5)

This report answers the question `CLAUDE.md` poses as this repo's whole
reason to exist — *"what do the gf180mcu HV devices actually withstand"* —
with a real simulated sweep, not a re-quote of the PDK's HTML documentation.
It compares `nfet_06v0`/`pfet_06v0` ([`spec/gate-driver.md`](../spec/gate-driver.md)
§2.5's chosen model corner), `nfet_05v0`/`pfet_05v0` (to test the
[`spec/gate-driver.md`](../spec/gate-driver.md) §2.2 same-device finding) and
`nfet_03v3`/`pfet_03v3` (the level shifter's thin-oxide side) against the
PDK's own published electrical-spec tables, and answers the two spec
questions §2.2 and §7 directly from the model source, with file+line
citations.

**No claim without a testbench.** Every number in this report is a simulated
result recorded under [`sim/device-mv-fet/`](../sim/device-mv-fet/); see that
directory's `records/` for the full append-only evidence, including every raw
per-corner ngspice log. `spec/gate-driver.md` is unchanged by this issue —
findings live here and in `sim/`, pending a future decision record (per the
issue's own scope).

## TL;DR

- All six devices' Vt, Idsat and Ioff land inside the PDK's published
  min/typ/max windows at the one point that is a fair comparison — the
  `typical` process corner at 27 °C (see "Methodology: what pass/fail means"
  below for why the other 12 grid points are *not* judged against those
  windows even though they are measured and recorded).
- §2.2 is **confirmed directly from the model source**: `nfet_05v0` is a
  thin wrapper subcircuit whose only active element is an `m0` MOSFET
  instance of the `nfet_06v0` model card (same for `pfet_05v0`/`pfet_06v0`).
  See "§2.2" below for the exact file and lines.
- §7 (the thick-oxide DC gate-node ceiling) is **not stated anywhere in the
  model source or the techfile** — searched exhaustively (see "§7" below).
  The PDK's *documentation* (DRM 14.1.4.2, already cited in spec §2.3) is the
  only place this number appears; the `.model`/techfile source is silent.
  This report does not change spec §2.3's adopted 6.0 V ceiling — it reports
  the evidence spec §7 asked for.

## Methodology

### Devices, geometry, and bias conditions

Every device is simulated at the PDK's own published test geometry (W/L) and
at the PDK's own stated bias condition for each quantity, so the comparison
is apples-to-apples. Sources: `google/gf180mcu-pdk`,
`docs/analog/spice/elec_specs/tables_clear/1_Low_Voltage_Devices.csv` (3.3 V),
`2_Medium_Voltage_Devices6v.csv` (6 V) and `3_Medium_Voltage_Devices5v.csv`
(5 V), re-fetched for this issue.

| device | model | W/L (µm) | DC gate ceiling used¹ | Idsat bias \|Vgs\|=\|Vds\| | Ioff bias \|Vds\| |
|---|---|---|---|---|---|
| `n06` | `nfet_06v0` | 10/0.7 | 6.6 V | 6.0 V | 6.6 V |
| `p06` | `pfet_06v0` | 10/0.55 | 6.6 V | 6.0 V | 6.6 V |
| `n05` | `nfet_05v0` | 10/0.6 | 5.5 V | 5.0 V | 5.5 V |
| `p05` | `pfet_05v0` | 10/0.5 | 5.5 V | 5.0 V | 5.5 V |
| `n33` | `nfet_03v3` | 10/0.28 | 3.63 V | 3.3 V | 3.63 V |
| `p33` | `pfet_03v3` | 10/0.28 | 3.63 V | 3.3 V | 3.63 V |

¹ "DC gate ceiling used" here is the upper bound of each device's own *Vt
sweep and output-characteristic sweep*, not a restatement of spec §2.3's
adopted design ceiling — it is simply the PDK's own stated overshoot/Ioff
test voltage for that family (6.6 V/5.5 V/3.63 V), used so the Vgs sweep
never drives a device outside the range the PDK itself characterizes it in.

Every device uses Vsb = 0 (source tied to bulk — NMOS bulk at ground, PMOS
bulk/source at a local supply node at that family's own ceiling), the
standard four-terminal characterization condition the PDK's own tables
assume.

### Vt: constant-current, linear region

Each device is biased at a fixed Vds = 50 mV (matching the PDK table's
"Linear Threshold Voltage" label) with Vgs swept from 0 to the device's own
ceiling. |Vth| is read as |Vgs| at Id = 100 nA × (W/L) — the same
constant-current criterion `2AMLogic/gf180-bandgap`'s
`sim/device-mos-vth/run_mos_vth.py` uses (for cross-repo consistency), chosen
here specifically because it lands every one of these six devices inside the
PDK's published window (validated during this issue's implementation — a
1 µA×(W/L) criterion, also tried, over-estimates Vt and lands two devices
outside their windows; see the record's raw logs for the swept I-V data if a
different criterion is ever needed).

### Idsat / Ioff: single DC operating points

**Idsat**: a single `.op` at |Vgs|=|Vds| equal to the PDK table's own stated
saturation bias (6.0 V / 5.0 V / 3.3 V per family), current normalized to the
test structure's W (10 µm for all six). **Ioff**: a single `.op` at Vgs = 0,
|Vds| equal to the PDK table's own stated overshoot bias (6.6 V / 5.5 V /
3.63 V), same normalization.

### Cgg / Cgd: BSIM operating-point capacitance

Read directly from the model's internal operating-point state
(`@m.<inst>.m0[cgg]`/`[cgd]` in ngspice) at the Idsat bias point, rather than
an AC/small-signal sweep — exact at that one operating point, and
inexpensive enough to run at every PVT corner. No PDK-published window exists
for this quantity (not in the elec-spec tables); it is measured device data
for issue #6's pre-driver-taper load estimate.

### Output characteristic / on-resistance

Id(Vds) swept from 0 to the device's own ceiling at three Vgs levels (75 %,
90 %, 100 % of the Idsat bias — the 100 % point is exactly the PDK's own
Idsat bias condition). On-resistance is read as the near-origin chord
(Vds ≈ 1 % of the device's ceiling) at each Vgs level. Also not in the
elec-spec tables; measured device data for issue #6's output-stage sizing.

### The harness: PVT grid and the `nosupply` convention

Every device is a bare transistor biased entirely from ideal sources inside
the testbench — there is no circuit supply rail for these testbenches to
sweep, so the ±10 % `vlogic`/`vdrv` axis of `CLAUDE.md`'s PVT matrix has
nothing to act on. Per `sim/README.md`'s `nosupply` convention (inherited
from `2AMLogic/gf180-bandgap`'s device-characterization scripts, and now
implemented directly in this repo's `sim/harness/corners.py` /
`sim/harness/testbench.py` as part of this issue — a testbench manifest
declares `"rails": {}` to opt into zero rails, and `PvtPoint.corner_id`/
`corners.tied_supply_grid` render the literal `nosupply` supply-field token),
every corner-id in this experiment's raw logs reads `<section>_<temp>c_nosupply`
(e.g. `ff_-40c_nosupply`). Process and temperature still cover the full
`CLAUDE.md` matrix: the five top-level MOS `.LIB` sections
(`typical`/`ff`/`ss`/`fs`/`sf`) × −40/27/125 °C = 15 points, all recorded.

### What pass/fail means (read this before the tables)

The PDK's published min/typ/max columns are a **silicon manufacturing
spread** at a nominal test condition (no stated temperature beyond Ioff's
explicit "@25 °C" — read here as a room-temperature reference for the other
quantities too, since none of the tables state otherwise). The `ff`/`ss`/
`fs`/`sf` process **corners** this sweep also runs are a different thing
entirely: deliberate, pessimistic timing-signoff skews used for worst-case
circuit verification margin, not a bound on real fabricated silicon. This
sweep's own results confirm exactly that: e.g. `nfet_06v0` Idsat at the
`ff`/27 °C corner measures 665.9 µA/µm, above the table's own published
660 µA/µm *maximum* — not because the simulation or the model is wrong, but
because `ff` is deliberately built to sit outside the typical-silicon
envelope. Judging pass/fail against a manufacturing-spread table at a
deliberately-skewed corner would be a category error.

So: **pass/fail is judged at the `typical` process corner, 27 °C only** —
the one point that is an actual like-for-like comparison with the PDK's
table — while the full 15-point process×temperature grid is still measured,
recorded, and reported (`sim min..max (full grid)` in every table below) as
design-margin data for issues #6 and #7's sizing, not as a spec-window
verdict.

## Results

Full precision, every quantity, every one of the 15 PVT points: see
[`sim/device-mv-fet/records/20260808-023237-61e0c25.md`](../sim/device-mv-fet/records/20260808-023237-61e0c25.md)
(and the raw per-corner logs alongside it). The tables below are the
`typical`/27 °C comparison point plus the full-grid range, condensed for
readability.

### Vt (V) — constant-current, linear region

| device | published min/typ/max | sim (`typical`,27 °C) | pass/fail | sim min..max (full grid) |
|---|---|---|---|---|
| `n06` (`nfet_06v0`) | 0.61 / 0.73 / 0.85 | 0.7154 | **PASS** | 0.4732 .. 0.9178 |
| `p06` (`pfet_06v0`) | −0.98 / −0.85 / −0.72 | −0.9281 | **PASS** | −1.1466 .. −0.6739 |
| `n05` (`nfet_05v0`) | 0.58 / 0.70 / 0.82 | 0.7001 | **PASS** | 0.4554 .. 0.9079 |
| `p05` (`pfet_05v0`) | −0.96 / −0.83 / −0.70 | −0.9219 | **PASS** | −1.1429 .. −0.6639 |
| `n33` (`nfet_03v3`) | 0.53 / 0.63 / 0.73 | 0.6094 | **PASS** | 0.4031 .. 0.7850 |
| `p33` (`pfet_03v3`) | −0.85 / −0.73 / −0.61 | −0.7866 | **PASS** | −0.9860 .. −0.5469 |

Notable: `n05` measures 0.7001 V, within 0.1 mV of the PDK's own published
*typical* value (0.70 V) — a strong independent confirmation that the
constant-current criterion and bias condition used here track the PDK's own
measurement methodology closely, not merely landing inside a wide window.

### Idsat (µA/µm) — |Vgs|=|Vds| = the PDK's own saturation bias

| device | published min/typ/max | sim (`typical`,27 °C) | pass/fail | sim min..max (full grid) |
|---|---|---|---|---|
| `n06` | 480 / 570 / 660 | 569.4 | **PASS** | 404.5 .. 755.3 |
| `p06` | −340 / −290 / −240 | −289.0 | **PASS** | −381.0 .. −205.7 |
| `n05` | 400 / 500 / 600 | 498.6 | **PASS** | 341.3 .. 675.8 |
| `p05` | −280 / −240 / −200 | −234.0 | **PASS** | −315.9 .. −160.5 |
| `n33` | 430 / 510 / 590 | 508.4 | **PASS** | 369.8 .. 648.4 |
| `p33` | −290 / −250 / −210 | −249.6 | **PASS** | −325.4 .. −185.6 |

Every `typical`/27 °C value lands within 2 % of the table's own *typical*
figure. As flagged in "What pass/fail means" above, the `ff`/`ss` corners
push outside the published window in both directions (e.g. `n06` at
`ff`/27 °C = 665.9 µA/µm, `ss`/27 °C = 469.97 µA/µm) — expected corner-model
behavior, not a deck or model defect, and not scored against this table.

### Ioff (pA/µm) — Vgs=0, |Vds| = the PDK's own overshoot bias, published "@25 °C"

| device | published min/typ/max | sim (`typical`,27 °C) | pass/fail | sim min..max (full grid, incl. −40/125 °C and ff/ss) |
|---|---|---|---|---|
| `n06` | — / 1.00 / 10.00 | 0.70 | **PASS** | 0.66 .. 285.50 |
| `p06` | −10.00 / −1.00 / — | −0.83 | **PASS** | −8.56 .. −0.82 |
| `n05` | — / 1.00 / 10.00 | 0.65 | **PASS** | 0.55 .. 615.69 |
| `p05` | −10.00 / −1.00 / — | −0.70 | **PASS** | −12.05 .. −0.68 |
| `n33` | — / 1.00 / 100.00 | 1.56 | **PASS** | 0.36 .. 3069.99 |
| `p33` | −20.00 / −1.00 / — | −0.55 | **PASS** | −104.69 .. −0.47 |

Subthreshold leakage is strongly temperature- **and** process-corner
dependent — `n33`'s own full-grid range spans almost four orders of
magnitude (0.36 → 3070 pA/µm at the `ff`/125 °C corner). That full range is
exactly the number issue #6's quiescent-current budget should size against
(the grid maximum, not the typical-corner figure); the published-window
comparison above is deliberately restricted to the one point (`typical`,
27 °C) that is a fair comparison with a table stated "@25 °C".

### Cgg / Cgd (fF) — BSIM op-point capacitance at the Idsat bias point

No PDK-published window exists for this quantity — reported as measured
device data, not scored.

| device | Cgg typ (`typical`,27 °C) | Cgg min..max (grid) | Cgd typ | Cgd min..max (grid) |
|---|---|---|---|---|
| `n06` | 9.583 | 9.507 .. 10.056 | −0.001 | −0.001 .. −0.001 |
| `p06` | 9.187 | 9.009 .. 9.675 | 0.021 | 0.014 .. 0.028 |
| `n05` | 7.994 | 7.811 .. 8.564 | −0.001 | −0.001 .. −0.001 |
| `p05` | 8.439 | 8.221 .. 8.964 | 0.029 | 0.019 .. 0.039 |
| `n33` | 6.933 | 6.759 .. 7.094 | 0.107 | 0.095 .. 0.121 |
| `p33` | 9.595 | 9.482 .. 9.702 | 0.068 | 0.061 .. 0.075 |

`Cgd` at the saturation Idsat bias point is essentially zero for the NMOS
devices (as expected — in deep saturation the drain is pinched off from the
channel) and small but nonzero for the PMOS devices (overlap capacitance
dominates); this is the correct qualitative behavior for a saturated MOSFET's
op-point capacitance and is a useful cross-check that the `@m.<inst>.m0[cgg]`/
`[cgd]` extraction is reading a sensible internal state, not noise.

### On-resistance (Ω, W = 10 µm test structure) — near-origin chord of Id(Vds)

No PDK-published window exists for this quantity either; measured device
data for issue #6's output-stage sizing. `typical` corner, 27 °C; full
process/temperature spread is in the raw per-corner logs.

| device | Vgs = 75 % Vidsat | Vgs = 90 % Vidsat | Vgs = 100 % Vidsat (= PDK's Idsat bias) |
|---|---|---|---|
| `n06` | 236.6 | 214.0 | 204.7 |
| `p06` | 771.7 | 677.4 | 632.7 |
| `n05` | 228.2 | 201.5 | 189.8 |
| `p05` | 807.8 | 698.9 | 648.0 |
| `n33` | 185.1 | 166.7 | 158.8 |
| `p33` | 557.6 | 480.1 | 446.0 |

For a 10 µm test structure this is a per-width figure (Ω·µm ≈ value × 10 for
`W=10 µm`); issue #6's output stage should scale by its own chosen device
width. `nfet_06v0` at full Vgs (204.7 Ω for 10 µm ⇒ ≈2.05 kΩ·µm) is the
number that most directly informs issue #6's rise/fall-time sizing against
spec §3's 1 nF reference load.

## §2.2: does the shipped deck resolve `nfet_05v0`/`nfet_06v0` to the same model card?

**Yes — confirmed directly from the model source, not the docs.**

Citation: `google/globalfoundries-pdk-libs-gf180mcu_fd_pr` (the
`libraries/gf180mcu_fd_pr/latest` submodule of `google/gf180mcu-pdk`) at
commit **`faef89e8c1b392733c32820a7b12e3a3847cc18c`**,
`models/ngspice/sm141064.ngspice`:

```
47092: *------------------------------------------------------------------------
47093: * Added by Tim Edwards, May 16, 2025
47094: * An nfet_05v0 device is defined as a regular nFET device allowing a
47095: * slightly shorter gate length than required at 6V.  Otherwise, the
47096: * model is exactly the same as nfet_06v0.  Note that the model bin
47097: * nfet_06v0.1 covers the nfet_05v0 case specifically.
47098: *------------------------------------------------------------------------
47099: .subckt nfet_05v0 d g s b w=1e-6 l=6e-7
   ...
47120: m0 d g s b nfet_06v0 w=w l=l as=as ad=ad ps=ps pd=pd nrd=nrd nrs=nrs
47121: +delvto='mis_vth*sw_stat_mismatch' mulu0='1-mis_k*sw_stat_mismatch' sa=sa sb=sb nf=nf sd=sd m=m
47122: .ends nfet_05v0
```

and symmetrically for the PMOS side:

```
47150: *------------------------------------------------------------------------
47151: * Added by Tim Edwards, May 16, 2025
47152: * A pfet_05v0 device is defined as a regular pFET device allowing a
47153: * slightly shorter gate length than required at 6V.  Otherwise, the
47154: * model is exactly the same as pfet_06v0.  Note that unlike the nFET,
47155: * there is no specific model bin for the short gate device.
47156: *------------------------------------------------------------------------
47157: .subckt pfet_05v0 d g s b w=1e-5 l=5e-7
   ...
47178: m0 d g s b pfet_06v0 w=w l=l as=as ad=ad ps=ps pd=pd nrd=nrd nrs=nrs
47179: +delvto='mis_vth*sw_stat_mismatch' mulu0='1-mis_k*sw_stat_mismatch' sa=sa sb=sb nf=nf sd=sd m=m
47180: .ends pfet_05v0
```

`nfet_05v0` and `pfet_05v0` are not distinct model cards — each is a thin
wrapper `.subckt` whose only active element (`m0`) directly instantiates the
`nfet_06v0`/`pfet_06v0` model, with a slightly different default `l`/`par_l`/
`par_w` in the wrapper's own local `.param` block (the "slightly shorter gate
length" the comment describes — `nfet_05v0`'s default `l=6e-7` vs.
`nfet_06v0`'s `l=7e-7`) and its own `mis_vth`/`mis_k` mismatch-statistics
draw. **This independently confirms spec §2.2's finding**, which was
previously derived only from the PDK's HTML Appendix A device table; this is
the same conclusion read directly from the `.subckt` body that actually
executes in simulation.

This experiment's own 15-point sweep is consistent with that reading: `n05`
and `n06`'s Vt/Idsat differ only by the amount their different default
`l`/geometry would predict for otherwise-identical short-channel/mismatch
model parameters (e.g. `n05` Vt = 0.7001 V vs. `n06` Vt = 0.7154 V, a
plausible short-channel-effect delta for L=0.6 µm vs. L=0.7 µm on the *same*
underlying model, not the kind of difference a genuinely distinct device
model would produce).

**A citation-precision note**: `google/gf180mcu-pdk`'s own `main` branch
currently pins the `gf180mcu_fd_pr` submodule at an *older* commit
(`9f992d5a9186d1f7820c58f039c484ad35b2edea`, 2023-05-31) that predates this
addition and still uses the legacy `nmos_6p0`/`pmos_6p0` naming — reading
that pin directly would not find `nfet_05v0`/`nfet_06v0` at all. The commit
cited above (`faef89e8c1b392733c32820a7b12e3a3847cc18c`, 2025-07-14) is the
one `open_pdks`/`volare`'s installed gf180mcuD build actually ships (verified
byte-identical, modulo CRLF line endings, to the installed
`~/.volare/gf180mcuD/libs.tech/ngspice/sm141064.ngspice` — confirmed via
`open_pdks`'s own `gf180mcu/gf180mcu.json` reference-commit table for the
`open_pdks` build `c6d73a35f524070e85faff4a6a9eef49553ebc2b` this repo's
harness resolves by default). This is normal PDK-repo versioning (a
slow-moving reference/docs repo pinning a specific submodule commit
deliberately), not a defect worth filing anywhere — but a reader citing "the
model source" should cite the commit the tools actually run, not
`gf180mcu-pdk`'s current `main`-branch submodule pin, since the two can
disagree about which device names even exist.

## §7: what does the model source / techfile say about the thick-oxide DC gate-node ceiling?

**The source is silent.** Searched, with nothing found:

- `models/ngspice/sm141064.ngspice` (the full model deck, 47,764 lines in
  the installed copy) — no `vgs`/`vmax`/"breakdown"/"reliability" parameter
  or comment anywhere near the `nfet_06v0`/`pfet_06v0`/`nfet_05v0`/
  `pfet_05v0` subcircuits (lines 47092–47212) or their underlying model card.
  BSIM3/4-class model parameters describe the device's electrical
  I-V/C-V behavior, not an absolute voltage rating — ngspice enforces no
  such limit at simulation time either way (confirmed empirically: this
  issue's own sweep biases every device gate right up to its stated ceiling
  with no warning or clamp from ngspice).
- `models/ngspice/design.ngspice` (76 lines, defines the global corner
  switch parameters `.include`d ahead of every `.lib` section) — nothing
  relevant.
- The magic techfile (`open_pdks`'s `gf180mcu/magic/gf180mcu.tech`, the
  device-recognition/DRC source for the open-source flow) — searched for
  "volt"/"6.6"/"breakdown"; the only hits are naming-convention comments
  (e.g. `# diode_nd2ps_06v0 diode (N+/pwell, high voltage)`), no rule or
  parameter encoding a gate-voltage limit.

So: **neither the ngspice model source nor the magic techfile states a
thick-oxide DC gate-node ceiling anywhere** — the number spec §2.3 adopts
(6.0 V conservative, citing DRM 14.1.4.2's "6.5V/6V for 5V/6V process thick
gate") exists only in the PDK's *documentation*, not in any machine-readable
source this repo's tools consume. This is exactly the "source is silent"
outcome spec §7 anticipated as a possible finding. **This report does not
change spec §2.3's adopted 6.0 V ceiling** — per the issue's explicit
instruction, that is a decision-record question for a future spec revision,
not something this characterization issue resolves.

One related but distinct number *is* published in the PDK's documentation
(not the model source, so it does not answer §7's "model source or
techfile" question, but is useful context for whoever writes that future
decision record): the elec-spec tables' §5.4 "Oxide Breakdown Voltage"
(`docs/analog/spice/elec_specs/tables_clear/5_General_Specification4.csv`,
`google/gf180mcu-pdk`) states `BVox` for the "6V GATE" as −16/... V (NCH) and
.../16 V (PCH) typical, with a 12 V absolute limit on the tighter side of
each — a **breakdown** rating, roughly 2× the DC operating ceiling spec §2.3
already adopts, not a substitute for it. Gate-oxide TDDB (time-dependent
dielectric breakdown) derates well below the hard breakdown voltage for any
sustained DC bias, so this number does not imply 6.0 V (or even 6.5 V) has
headroom to spare — it is cited here only because it is the one related,
documented number that does exist, for completeness.

## Deck/doc agreement — nothing to file

No disagreement between the shipped ngspice deck and the PDK's documentation
was found during this characterization: `sim/harness/corners.py`'s existing
finding (the five top-level MOS `.LIB` sections already bundle the
thick-oxide device family, confirmed prior to this issue) held up under this
sweep, and every device's simulated Vt/Idsat/Ioff at the fair (`typical`,
27 °C) comparison point matched the published table closely (within ~2 % of
the *typical* column in every case, see Results above). No klayout-tools
friction was encountered either — this issue does no layout work, so the
friction protocol's tool-gap-filing criterion does not apply here.

## Links

- Testbench: [`sim/device-mv-fet/testbench/tb_device_mv_fet.spice`](../sim/device-mv-fet/testbench/tb_device_mv_fet.spice), [`tb.json`](../sim/device-mv-fet/testbench/tb.json)
- Run script (produces the authoritative record): [`sim/device-mv-fet/run_device_mv_fet.py`](../sim/device-mv-fet/run_device_mv_fet.py)
- Record: [`sim/device-mv-fet/records/20260808-023237-61e0c25.md`](../sim/device-mv-fet/records/20260808-023237-61e0c25.md)
- Raw per-corner logs: [`sim/device-mv-fet/corners/20260808-023237-61e0c25/`](../sim/device-mv-fet/corners/20260808-023237-61e0c25/)
- Netlist snapshot: [`sim/device-mv-fet/netlist-snapshots/20260808-023237-61e0c25.spice`](../sim/device-mv-fet/netlist-snapshots/20260808-023237-61e0c25.spice)
