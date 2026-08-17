# Low-side output-stage sizing derivation

Sizing record for `design/output_stage.sch` / `design/output_stage.sym`
(issue #6). Every width, finger/multiplicity count and taper ratio below is
traced to an input number with its source, per the issue's requirement.
Numbers are **design targets derived from PDK-published bounds and a
single-device sizing-support probe against the shipped model card**.

**Update, post-#5 landing**: issue #5's dedicated PVT-swept device
characterization ([`design/device-characterization.md`](device-characterization.md),
[`sim/device-mv-fet/records/20260808-023237-61e0c25.md`](../sim/device-mv-fet/records/20260808-023237-61e0c25.md))
has since landed and is cross-checked here rather than superseding §1.2's
probe outright: issue #5 measures each device's Idsat at *its own*
PDK-defined characterization bias only (`nfet_06v0`/`pfet_06v0` at
`|Vgs|=|Vds|=6.0V`; `nfet_05v0`/`pfet_05v0` at `5.0V`), while this cell's
`VDD_DRV` rail sweeps 4.5/5.0/5.5/6.0V (nominal ±10% plus the 6V stretch
point) applied to the *same* `nfet_06v0`/`pfet_06v0` devices — a bias-swept
question issue #5's fixed-bias record does not answer for this specific
device pair, so §1.2's own sizing-support probe remains the necessary input
for §1.3's worst-case current density, not merely a stand-in awaiting #5.
Where the two overlap (the `typical`/27°C, `nfet_06v0`-at-its-own-6.0V-bias
point), they agree directionally: issue #5 records 569.4 µA/µm for `n06`
Idsat at 6.0V/typical/27°C, higher than this probe's 440.2 µA/µm at
5.0V/typical/27°C (§1.2) — consistent with more gate overdrive at the higher
bias, the expected direction, and no red flag against the probe's own
methodology. §1.2's worst-case sizing point (`ss`/125°C/4.5V) has no direct
analogue in issue #5's record (fixed-bias, not swept to 4.5V), so it is not
independently re-derived here; §6's transient simulation is the actual
verification of the resulting design's current/timing margins in any case,
not either DC-operating-point estimate.

## 0. Interface and topology

Ports (per
[`spec/decision-records/0001-block-interface-and-uvlo-parameters.md`](../spec/decision-records/0001-block-interface-and-uvlo-parameters.md)
Decision 1, restricted to the drive-rail-domain pins this cell owns):

| Pin | Direction | Function |
|---|---|---|
| `IN_DRV` | in | Drive-rail-referenced logic input. **Not** the block's 3.3 V `IN` pin — per issue #6, "this cell's input is a drive-rail-referenced logic signal," produced by the level shifter (#7). Assumed rail-to-rail (0 to `VDD_DRV`). |
| `VDD_DRV` | in | 5 V nominal (±10 %) / 6 V stretch drive rail (spec §3). |
| `GND_DRV` | in | Drive-rail return. |
| `OUT` | out | Gate-drive output into the 1 nF reference load (spec §3). |

Topology: a 5-stage thick-oxide tapered pre-driver (stages 1–5) driving a
6th, final complementary push-pull stage into `OUT`. Every device is
`nfet_06v0`/`pfet_06v0` (spec §2.5) — no thin-oxide device appears anywhere
in this cell, satisfied trivially since the cell's input is already in the
drive-rail domain. 6 total inverting stages (even) → the cell is
**non-inverting**: `IN_DRV` high → `OUT` high.

## 1. Inputs and their sources

### 1.1 PDK-published `Idsat` bounds (spec §2.5's citations)

Per [PDK Electrical Specifications §2.0, Medium Voltage Devices
(6V)](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_2.html)
and [§3.0, Medium Voltage Devices
(5V)](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_3.html)
(re-fetched 2026-08-08):

| Bias point | Device | W/L tested | min | typ | max | units |
|---|---|---|---|---|---|---|
| `\|Vgs\|=\|Vds\|=6V` | NCH (NE2) | 10/0.7 | 480 | 570 | 660 | µA/µm |
| `\|Vgs\|=\|Vds\|=6V` | PCH (PE2) | 10/0.55 | 340 | 290 | 240 | µA/µm (magnitude) |
| `\|Vgs\|=\|Vds\|=5V` | NCH (NE2) | 10/0.6 | 400 | 500 | 600 | µA/µm |
| `\|Vgs\|=\|Vds\|=5V` | PCH (PE2) | 10/0.5 | 280 | 240 | 200 | µA/µm (magnitude) |

The `nfet_06v0`/`pfet_06v0` xschem subcircuits (`libs.tech/xschem/symbols/`)
default to `L=0.70u` (NMOS) / `L=0.55u` (PMOS) — exactly the 6 V table's
tested geometry, not the 5 V table's (0.6/0.5). This design keeps the
default `L` for every stage (see §2), so the 6 V table's `L` matches this
design's devices exactly; the 5 V table's slightly shorter `L` is used only
as a cross-check.

### 1.2 Sizing-support probe against the shipped model card

To size against this design's *actual* geometry (not just the closest
published table row) and across the *full* PVT matrix (the tables above are
single points, each already at their own worst/typ/best silicon spread, not
process-corner- or temperature-swept), a single-device DC operating-point
probe was run directly against the installed `sm141064.ngspice` model
(`nfet_06v0`/`pfet_06v0`, default `L`, `W=10 µm`, `Id` and BSIM4 `cgg` at
`Vgs=Vds=` each rail value) across all 5 `mos` corners × {−40, 27, 125} °C ×
{4.5, 5.0, 5.5, 6.0, 6.6} V. This is **not** issue #5's dedicated
characterization sweep (no PVT-swept record was minted under `sim/`) — it
is a one-off sizing input, reproducible with:

```
.lib "<pdk>/libs.tech/ngspice/sm141064.ngspice" <corner>
.temp <T>
vgn ng 0 dc <V>
vdn nd 0 dc <V>
xn nd ng 0 0 nfet_06v0 w=10u l=0.7u
.op
.control
run
print @m.xn.m0[id]
print @m.xn.m0[cgg]
.endc
```

At the typical corner / 27 °C / 5 V bias, this probe measured `Id` = 440.2
µA/µm (NMOS) and 213.3 µA/µm (PMOS) — inside the §1.1 5 V table's
min/max window (400–600 and 200–280 µA/µm respectively), close to its
lower half (consistent with the probe's slightly longer `L`, 0.7/0.55 µm
vs. the table's 0.6/0.5 µm). This cross-check gives confidence the probe
reproduces the PDK's own published behavior before using it for the finer
PVT-swept sizing basis below. This probe has since been cross-checked
against issue #5's dedicated, PVT-swept, `sim/`-recorded device
characterization — see the "Update, post-#5 landing" note at the top of
this document.

### 1.3 Worst-case current density used for final-stage sizing

The design target requires peak source/sink current ≥ 0.5 A "at every PVT
point" (issue #6 acceptance criteria), which includes the nominal rail's
−10 % floor (4.5 V, per spec §3 / decision record 0001 Decision 4's
derivation: 5 V × 0.9). Sizing therefore uses the **worst-case (minimum)**
current density found across the probe grid at `V ≤ 5.5 V` (the nominal
±10 % range — the 6 V stretch point is checked separately in §4, not used
to relax nominal sizing):

| Corner | Temp | `VDD_DRV` | `Id_n` (µA/µm) | `Id_p` (µA/µm) |
|---|---|---|---|---|
| `ss` | 125 °C | 4.5 V | **263.95** (worst-case NMOS) | **119.21** (worst-case PMOS) |
| `ss` | 125 °C | 5.5 V | 356.7 (for comparison — better than 4.5 V) | 138.7 (for comparison — better than 4.5 V) |

Both devices' worst-case current density over the nominal ±10 % range occur
at the same point, `ss` / 125 °C / 4.5 V (the slow-process, high-temperature,
low-rail corner, as expected for a current-density minimum) — sizing against
that single shared worst point, rather than each device's own separately
worst corner, is what lets both the source and sink paths clear 0.5 A
simultaneously at every PVT point, not just at their individually-easiest
corner.

(Full grid captured in this one-off sizing-support probe, per §1.2 — not
itself a `sim/`-recorded evidence artifact; §6's transient testbench is the
actual PVT-swept evidence for this cell's own behavior.) The worst-case
point over the nominal ±10 % range is **`ss` / 125 °C / 4.5 V** for both
devices:

- NMOS: **263.95 µA/µm**
- PMOS: **119.21 µA/µm**

Ratio (PMOS/NMOS current density) = 119.21 / 263.95 = **0.4517**, i.e. the
PMOS/NMOS **width** ratio needed for equal drive current is the reciprocal,
**2.214** — this is the "measured mobility asymmetry" the issue asks the
PMOS/NMOS width ratio to follow, evaluated at the same worst-case corner
used for the width targets themselves (not a separate typical-corner
number), so that source and sink both clear 0.5 A at the *same* worst
point rather than one of them being sized against an easier corner.

### 1.4 Gate capacitance (taper sizing input)

From the same probe, `@m.<dev>.m0[cgg]` at the **typical corner, 27 °C,
5 V** (used for nominal-case taper/delay sizing — process-corner cap spread
is ≈ ±5.5 % across the probe grid, ss slowest/highest-cap to ff
fastest/lowest-cap, folded into the delay margin check in §3, not into the
taper ratio itself):

- NMOS: `cgg` = 9.585×10⁻¹⁵ F per 10 µm instance → **0.9585 fF/µm**
- PMOS: `cgg` = 9.227×10⁻¹⁵ F per 10 µm instance → **0.9227 fF/µm**

## 2. Final-stage sizing (from §1.3's current target)

```
W_n,min = 0.5 A / 263.95 µA/µm = 1894.7 µm
W_p,min = 0.5 A / 119.21 µA/µm = 4194.6 µm
```

Chosen, with ~16–19 % margin over the bare minimum (covers the delta
between this hand DC-bias estimate and the real transient/finite-edge-rate
behavior verified in §6, and the sizing-support probe's status as a
supplementary, bias-swept input cross-checked against issue #5 per §1.2's
"Update, post-#5 landing" note):

| Device | Chosen W | Realization | Worst-case (ss/125°C/4.5V) current | Margin over 0.5A |
|---|---|---|---|---|
| `MN6` (final NMOS) | 2200 µm | `W=10u m=220` (unit cell under the model's `wmax=100.001u` bin limit) | 580.7 mA | +16.1% |
| `MP6` (final PMOS) | 5000 µm | `W=10u m=500` | 596.0 mA | +19.2% |

`L` is left at the subcircuit default (`0.70u` NMOS / `0.55u` PMOS, §1.1) —
no `L` scaling is used anywhere in this cell; every width change is
expressed via `m` (SPICE parallel-instance multiplicity) with a 10 µm unit
cell, keeping every individual device instance's `W` at or under the
`nfet_06v0`/`pfet_06v0` `.model` validity bound (`wmax=100.001u`) even
though the *stage* total width is in the hundreds to low thousands of µm.

Realized `Wp/Wn` = 5000/2200 = **2.27**, close to the §1.3 mobility-derived
target of 2.214 (the ~2.5% difference comes from rounding each stage's
`m` to an integer multiplier of the 10 µm unit cell).

## 3. Pre-driver taper sizing (from §1.4's gate-capacitance input)

**Method**: classic geometric tapered-buffer sizing (`f = (C_L/C_in)^(1/N)`,
`N` = number of stage-to-stage intervals), using `f ≈ 4` as a starting
target (the standard VLSI-text default balancing delay against area) and
`C_in` fixed at a small unit inverter (`Wn=2 µm`, `Wp=4.4 µm`, ratio ≈ 2.2
per §1.3).

```
C_in  = 0.9585 fF/µm * 2 µm + 0.9227 fF/µm * 4.4 µm = 5.977 fF
C_L   = 0.9585 fF/µm * 2200 µm + 0.9227 fF/µm * 5000 µm = 6722.2 fF   (final stage's own gate cap, §2)
ratio = C_L / C_in = 1124.7
N     = round(ln(1124.7) / ln(4)) = round(5.07) = 5 intervals -> 6 stages total
f     = 1124.7^(1/5) = 4.076
```

Stage-by-stage widths (`Wn` scaled by `f`, `Wp` kept at the same ratio to
`Wn`), rounded to a 10 µm unit cell with integer `m` from stage 4 onward
(stages 1–3 stay under the `wmax` bound with a single instance, `m=1`):

| Stage | `Wn` (µm) | NMOS realization | `Wp` (µm) | PMOS realization | `Wp/Wn` |
|---|---|---|---|---|---|
| 1 (unit) | 2.0 | `W=2u m=1` | 4.4 | `W=4.4u m=1` | 2.20 |
| 2 | 8.0 | `W=8u m=1` | 18.0 | `W=18u m=1` | 2.25 |
| 3 | 33.0 | `W=33u m=1` | 73.0 | `W=73u m=1` | 2.21 |
| 4 | 140 | `W=10u m=14` | 300 | `W=10u m=30` | 2.14 |
| 5 | 550 | `W=10u m=55` | 1220 | `W=10u m=122` | 2.22 |
| 6 (final) | 2200 | `W=10u m=220` | 5000 | `W=10u m=500` | 2.27 |

Stage-to-stage width ratios realized: 4.00, 4.13, 4.24, 3.93, 4.00 — all
close to the target `f=4.076`, confirming the rounded, `wmax`-respecting
widths did not distort the taper (largest deviation stage 4→5, +3.6%).
`L` is the subcircuit default at every stage (§2). Every net between stages
(`n1`…`n5`) is the shared gate/drain node of that stage's complementary
pair, wired in `design/output_stage.sch` via coincident xschem `lab_pin`
markers at each device pin (see the schematic's header comment).

### 3.1 Hand-estimated delay (sanity check against §6's transient result)

Per-stage intrinsic delay for a geometrically tapered chain (parasitic
resistance/capacitance products cancel the absolute stage size, leaving
only `f`, `V`, and the per-µm `Idsat`/`Cgg` ratio):

```
tau_stage,NMOS-limited = 0.69 * Vdd * f * Ceff_per_Wn_unit / Idsat_n_per_um
Ceff_per_Wn_unit = Cgg_n_per_um + 2.2 * Cgg_p_per_um = 0.9585 + 2.2*0.9227 = 2.988 fF per um-of-Wn
tau_stage,NMOS  = 0.69 * 5 * 4.076 * 2.988e-15 / 440.15e-6 = 95.4 ps  (typical corner, 5V nominal)
tau_stage,PMOS  = 0.69 * 5 * 4.076 * 2.988e-15 / (2.2 * 213.33e-6) = 89.5 ps
```

5 intervals → taper delay ≈ 5 × ~92 ps ≈ **0.46 ns** (typical corner).
Final-stage output delay into the 1 nF load (`0.69 * R_on * C_L`, typical
corner): `R_on,n = 5V/(440.15µA/µm * 2200µm) = 5.16 Ω` →
`tau ≈ 0.69*5.16*1nF = 3.56 ns`; `R_on,p = 5V/(213.33µA/µm*5000µm)=4.69 Ω`
→ `tau ≈ 3.24 ns`. **Total hand-estimated propagation delay ≈ 3.7–4.0 ns**
at the typical corner / 5 V nominal — this is a sanity check only; §5's
transient simulation is the verified number.

## 4. §2.3 gate-ceiling analysis (pass/fail, before running the sim)

This cell has **no cascode or clamp** — it is a plain rail-to-rail
complementary push-pull chain referenced only to `VDD_DRV`/`GND_DRV` (the
issue explicitly scopes this cell to "a thick-oxide complementary push-pull
final stage plus the pre-driver taper," not a clamped topology — clamping
is §4 of the ratified spec's level-shifter topology, a different cell,
#7). Every node in this cell (`n1`…`n5`, `OUT`, `IN_DRV`) is driven only by
sources within `[GND_DRV, VDD_DRV]` through a network with **no
inductance** (only MOSFET channels and gate/junction capacitance) — for
such a network, no node can ever exceed the convex hull of its driving
sources (a standard RC-network bound; confirmed empirically in §5 via
`vout_max_v`/`vout_min_v` checks). Therefore the worst-case `|Vgs|` (or
`|Vgd|`/`|Vgb|`) **any** device in this cell ever sees is bounded above by
exactly `VDD_DRV − GND_DRV = VDD_DRV` (achieved when a device is fully on:
gate at one rail, source/drain/bulk at the other).

| Rail point | `VDD_DRV` | Worst-case `\|Vgs\|` | Margin to 6.0V ceiling (spec §2.3) |
|---|---|---|---|
| Nominal −10% | 4.50 V | 4.50 V | **+1.50 V** |
| Nominal | 5.00 V | 5.00 V | **+1.00 V** |
| Nominal +10% | 5.50 V | 5.50 V | **+0.50 V** |
| 6 V stretch | 6.00 V | 6.00 V | **0.00 V** |

**Analytical finding**: at the 6 V stretch rail, this topology's worst-case
`|Vgs|` reaches **exactly** the adopted 6.0 V ceiling by this quasi-static
bound — not exceeding it, but with **zero**, not positive, margin. This is
not a sizing defect fixable by choosing different widths; it is
topological, inherent to *any* non-cascoded rail-to-rail thick-oxide
push-pull stage swinging the full 6 V stretch rail. It is also, not
coincidentally, exactly the PDK's own characterization bias point for the
`nfet_06v0`/`pfet_06v0` 6V0 corner (elec_specs_2.html tests `Idsat` at
`|Vgs|=|Vds|=6V` — see §1.1) — operating this device flavor at `Vgs=6V` is
its intended, characterized full-scale operating point, not an excursion
beyond it.

**Measured finding (§6): worse than the analytical bound, not equal to
it.** The §6 transient simulation shows this quasi-static bound does not
hold exactly — a gate-capacitance/Miller-coupling transient pushes the
worst internal taper node (`n5`) to 6.0538 V at `ss_27c_vdrv6p00v`, **53.8
mV past** the ceiling, at every one of the 15 PVT points on the 6 V stretch
rail. See §6 for the full result and
[decision record 0004](../spec/decision-records/0004-output-stage-gate-ceiling-result.md)
for the ratified analysis.

Per issue #6's explicit instruction ("If a §3 target proves unreachable, do
not relax it — record the shortfall in the sim record and open a
decision-record issue instead"), this shortfall is **not** resolved here.
Decision record 0004 records it as measured and defers the resolution
(accept a documented exception for this specific device flavor at its
native characterization point, per the precedent in decision record 0003,
or require a cascode/clamp on this cell's final stage) to a follow-up
issue, not decided unilaterally here.

**Update, post-#24 resolution**: issue #24 investigated a clamp/cascode
mitigation and found it disproportionate — this node drives the cell's
largest, most delay-critical devices (§2 above), so an added device is
expected to cost more of the already-tight 6 V-stretch delay budget (§5/§6)
than the analogous, rejected clamp attempt in decision record 0003 cost
that (lower-stakes) case, to close a smaller gap. [Decision record
0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md)
formally narrows `spec/gate-driver.md` §5's overvoltage-protection claim
with a second documented, bounded exception instead — §2.3's 6.0 V ceiling
number itself is unchanged, and this cell's design/evidence trail is
unchanged (no new `sim/output-stage-drive/` record required).

## 5. Propagation-delay budget split (issue #6's explicit ask)

Total propagation-delay budget from spec §3: **< 50 ns nominal, < 25 ns
stretch**, measured (per the ratified spec's own framing) end-to-end from
the block's `IN` pin to `OUT`. That path is `IN` → level shifter (#7,
cascode/clamped, crossing the 3.3V/drive-rail domain) → **this cell**
(`IN_DRV` → `OUT`).

**Budget allocated to this cell**: **≤ 20 ns of the 50 ns nominal budget**,
**≤ 10 ns of the 25 ns stretch budget** — leaving ≥ 30 ns / ≥ 15 ns for the
level shifter (#7) and any interconnect. This split is a **design
allocation, not a verified split** (issue #7 has not landed and cannot
confirm its own share yet); it is chosen because a cascode/clamped level
shifter crossing two voltage domains is expected to be the slower element
(conservative biasing to hold every thin-oxide node under 3.63 V, per spec
§4), while this cell's own hand estimate (§3.1, ~4 ns typical) suggests
substantial headroom inside a 20 ns allocation even accounting for
worst-case PVT slowdown.

**Achieved** (this cell only, `tpdlh`/`tpdhl` from the §6 transient
record, idealized 1 ns `IN_DRV` edge — see the record's own caveat on this
assumption): see §6's table. If §6's worst-case measured delay exceeds this
cell's 20 ns/10 ns allocation, that is reported as a shortfall against the
*allocation* (not the ratified spec's own 50 ns/25 ns number, which this
cell alone cannot fail short of the level shifter also landing) in the
record.

## 6. Verification — see `sim/output-stage-drive/`

PVT-corner transient simulation results (rise/fall time, peak
source/sink current, propagation delay, cross-conduction current, energy
per edge, worst-case node voltages) are recorded in
`sim/output-stage-drive/records/`, per `sim/README.md`'s append-only
evidence convention. Full 60-point PVT grid (5 process corners × 3
temperatures × 4 tied-supply points, including the 6 V stretch rail), see
[`sim/output-stage-drive/records/20260812-064304-03699ea.md`](../sim/output-stage-drive/records/20260812-064304-03699ea.md)
for the complete per-corner table.

**Drive strength (§3, acceptance criteria)** — met at every PVT point:

| Measurement | Worst case | Value | Target |
|---|---|---|---|
| Peak source current | `ss_125c_vdrv4p50v` | 0.5877 A | ≥ 0.5 A |
| Peak sink current | `ss_125c_vdrv4p50v` | 0.5737 A | ≥ 0.5 A |
| 10–90 % rise time | `ss_125c_vdrv4p50v` | 8.36 ns | < 50 ns |
| 10–90 % fall time | `ss_125c_vdrv4p50v` | 7.53 ns | < 50 ns |

**Propagation delay (§5 budget)** — met against this cell's own allocation
at every point, including the 6 V stretch corners:

| Rail | Worst `tpdlh`/`tpdhl` | Corner | Allocation |
|---|---|---|---|
| Nominal ±10 % (4.5/5.0/5.5 V) | 5.78 ns / 5.88 ns | `ss_125c_vdrv4p50v` | ≤ 20 ns |
| 6 V stretch | 4.56 ns / 5.01 ns | `ss_125c_vdrv6p00v` | ≤ 10 ns |

**Cross-conduction / energy per edge (§7, no spec limit)**:

| Measurement | Worst case | Value |
|---|---|---|
| Peak shoot-through, rising edge | `ff_-40c_vdrv6p00v` | 0.319 A |
| Peak shoot-through, falling edge | `tt_-40c_vdrv6p00v` | 0.0229 A |
| Energy per edge | `ss_125c_vdrv6p00v` | 18.6 nJ |

**§2.3 gate-ceiling (§4's analytical bound) — FAILS the positive-margin
acceptance criterion, confirmed by transient simulation.** §4's quasi-static
convex-hull argument bounds worst-case `|Vgs|` at exactly `VDD_DRV`, with
zero margin at the 6 V stretch rail. The measured transient result is
worse than that analytical bound, not merely equal to it: **every one of
the 15 PVT points at the 6 V stretch rail** (all 5 process corners × all 3
temperatures — a consistent, corner-tracking pattern, not simulation noise)
shows at least one internal taper node (`n1`…`n5`) transiently exceeding
6.0 V:

| Node | Global worst case | Corner | Margin to 6.0 V ceiling |
|---|---|---|---|
| `n5` | 6.0538 V | `ss_27c_vdrv6p00v` | **−53.8 mV** |
| `n4` | 6.0526 V | `ss_125c_vdrv6p00v` | **−52.6 mV** |
| `n3` | 6.0518 V | `ss_125c_vdrv6p00v` | −51.8 mV |
| `n1` | 6.0407 V | `ss_125c_vdrv6p00v` | −40.7 mV |
| `n2` | 6.0334 V | `ss_125c_vdrv6p00v` | −33.4 mV |

No node exceeds 6.0 V at the 4.5/5.0/5.5 V nominal-tolerance rail points —
the excursion is confined to the 6 V stretch corners, consistent with §4's
own topological explanation (a gate-capacitance/Miller-coupling transient on
top of the quasi-static bound) rather than a sizing defect. This mirrors the
same excursion shape already ratified in
[decision record 0002](../spec/decision-records/0002-level-shifter-oxide-safety-result.md)/[0003](../spec/decision-records/0003-predriver-inverter-oxide-margin-exception.md)
for the level shifter's pre-driver inverter.

Per issue #6's explicit instruction, this shortfall is not resolved by
relaxing the target here. It is recorded in
[decision record 0004](../spec/decision-records/0004-output-stage-gate-ceiling-result.md),
which defers the resolution (mitigate with a clamp/cascode, or formally
narrow the §2.3 claim for this cell) to a follow-up issue.

**Resolved by issue #24**:
[decision record 0005](../spec/decision-records/0005-output-stage-gate-ceiling-exception.md)
formally narrows `spec/gate-driver.md` §5's overvoltage-protection claim
with a second documented, bounded exception for this cell's internal taper
nodes (`n1`…`n5`), scoped to exactly this measured excursion (6 V stretch
rail only, ≤ 53.8 mV, all 15 process×temperature points) — a clamp/cascode
mitigation was investigated and rejected as disproportionate (this node
drives the cell's largest, most delay-critical devices, unlike the
lower-stakes analogous case in decision record 0003). §2.3's 6.0 V ceiling
number itself is unchanged, and this record (§6) remains the unmodified,
authoritative evidence trail for this cell — no new PVT run was required.
Per [decision record 0006](../spec/decision-records/0006-indrv-inter-cell-gate-ceiling-exception.md),
the end-to-end campaign has amended the exception's quantification: under the
real level-shifter edge, the worst case is n1 = 6.10232 V (margin −102.3 mV)
at `sf_-40c_vlogic3p30v-vdrv6p00v`, not n5 = 6.0538 V (−53.8 mV) measured here
with an ideal 1 ns edge; this record's own idealized-edge results remain the
authoritative baseline for `sim/output-stage-drive/`.

## 7. Cross-conduction / shoot-through (captured, no spec limit)

Per issue #6 ("Also report... the peak cross-conduction (shoot-through)
current within the taper during a transition, and the energy per edge...
the number a future half-bridge revision and any thermal-shutdown
reconsideration will need"), `sim/output-stage-drive/testbench/tb.json`
measures the peak current on whichever rail (`VDD_DRV` or `GND_DRV`)
should be idle during a given output transition — a small draw there,
during that specific transition, is cross-conduction rather than the
intended charge/discharge current (see the testbench's own comments and
the record for the measured values and the reasoning that isolates it this
way without adding measurement-only devices to the production netlist).
"Energy per edge" is the supply-referred switching energy
(`integ(V_DD_DRV * I_sup)`) over the transient run, divided by the two
edges it contains — an approximation that folds in both legitimate
load-charging energy and cross-conduction loss, not decomposed further; see
§6/the record for the measured value and this caveat repeated in context.
