# low-side on-die power switch — facet (b) specification

**Status: Ratified 2026-08-18.** Ratifying decision records:
[0010](decision-records/0010-low-side-power-switch-spec-ronw-em-and-protection.md)
(this document, the `Ron·W` baseline, the EM budget, and the protection
structures) and
[0011](decision-records/0011-low-side-power-switch-flyback-handling.md)
(§5, flyback handling).

This is the spec document for the **second** facet scoped into this repo by
[decision record 0008](decision-records/0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md):
direct low-side drive of a small load (motor / solenoid / LED) straight from
a single Li-ion cell, where the switch is an **on-die** thick-oxide
`nfet_06v0`, `Vgs` is the cell's own 3.6–5.0 V range, and there is no HV
rail and no level shifter.

It does **not** amend [`gate-driver.md`](gate-driver.md) — see §7. Changing
any decision recorded here requires a new decision record, not a silent edit
(`CLAUDE.md`: "Spec changes go through `spec/` with a decision record; agents
do not relax the ratified spec to make results pass").

Every PDK claim below is cited to a specific page of the `gf180mcu-pdk`
documentation or to a specific file in the installed PDK, re-fetched and
re-checked on 2026-08-18 for this ratification. Every electrical number is
cited to an append-only record under `sim/`. Where nothing has been measured
yet, this document says so instead of inferring — see §6.

## 1. Scope of this facet

| | |
|---|---|
| Configuration | **Low-side switch, on-die.** Load returns to the cell's positive terminal; the switch's source is the die's power ground. |
| Supply | A **single Li-ion cell**, directly: 5.0 V (fresh) … 4.2 V (nominal) … 3.6 V (end of discharge). No boost, no charge pump, no separate drive rail. |
| Gate drive | The cell rail itself. `Vgs` = the cell voltage, so the switch's `Ron` moves with the state of charge — this is the defining constraint of the facet and the reason §2's table is indexed on `Vgs` rather than on a single nominal drive. |
| Target current | **~1 A per channel**, continuous, unidirectional. |
| Switch device | `nfet_06v0` (thick-oxide 6 V NMOS). Same device family `gate-driver.md` §2.5 selects, for the reasons recorded there. |
| Protection | Per-channel overcurrent (OCP) and a thermal sense — §4. |
| Flyback | An on-die recirculation path from the switch drain back to the cell rail — §5. |
| **Not** in scope here | High-side / half-bridge operation, level shifting from a lower logic domain (that is facet (a), `gate-driver.md`), the shuttle test-structure plan ([#180](https://github.com/2AMLogic/gf180-gate-driver/issues/180)), and multi-channel bond-wire / ground-return / substrate-noise guidance ([#181](https://github.com/2AMLogic/gf180-gate-driver/issues/181)). |

## 2. On-resistance

### 2.1 `Ron·W` vs. `Vgs` and temperature (ratified)

Measured in `sim/low-side-power-switch/records/20260818-011754-03afe04.md`
across the full 15-point process × temperature PVT grid (`tt`/`ff`/`ss`/`fs`/`sf`
× −40/27/125 °C), on the PDK elec-spec tables' own test geometry
(W/L = 10/0.7 µm), `Vsb` = 0, `Ron` read as the near-origin chord of Id(Vds)
at `Vds` = 66 mV.

**`nfet_06v0` — the switch.** All figures Ω·mm.

| `Vgs` (cell state) | `tt`, −40 °C | `tt`, 27 °C | `tt`, 125 °C | full grid min .. max |
|---|---|---|---|---|
| 5.0 V (fresh cell) | 1.6996 | 2.2246 | 3.0903 | 1.5287 .. 3.6176 |
| 4.2 V (nominal) | 1.9053 | 2.4758 | 3.4115 | 1.6907 .. 4.0510 |
| 3.6 V (end of discharge) | 2.1525 | 2.7796 | 3.7996 | 1.8855 .. 4.5719 |

**`pfet_06v0` — not the switch.** Measured at the same cell-referenced
`|Vgs|` because §5's synchronous-PMOS option would hang a PMOS off the same
cell rail. W/L = 10/0.55 µm.

| `|Vgs|` | `tt`, −40 °C | `tt`, 27 °C | `tt`, 125 °C | full grid min .. max |
|---|---|---|---|---|
| 5.0 V | 5.5326 | 7.1427 | 9.2656 | 4.7759 .. 11.2493 |
| 4.2 V | 6.2636 | 8.1438 | 10.6955 | 5.3358 .. 13.1291 |
| 3.6 V | 7.1086 | 9.2773 | 12.2617 | 5.9721 .. 15.2279 |

**Worst-case design point for this facet: 4.5719 Ω·mm** — `nfet_06v0` at
`Vgs` = 3.6 V, across the whole process × temperature grid. That is
**3.0×** the best-case point (1.5287 Ω·mm at `Vgs` = 5.0 V), and the spread
is not optional margin: the cell really does traverse 5.0 → 3.6 V in normal
use, and the die really is specified to −40…125 °C. Every downstream number
in this document that depends on `Ron` carries that 3:1 window explicitly
rather than quoting a typical value.

### 2.2 Switch sizing (ratified rule, not a fixed width)

`W = Ron·W / Ron_budget`. This document ratifies the **rule and the table it
is applied to**, not a single width, because the width follows from a
conduction-loss budget a specific product sets:

| `Ron` budget | drop / loss at 1 A | W at `tt`/27 °C/4.2 V | W at the grid-worst point (3.6 V) |
|---|---|---|---|
| 0.05 Ω | 50 mV / 50 mW | 49.5 mm | 91.4 mm |
| 0.10 Ω | 100 mV / 100 mW | 24.8 mm | 45.7 mm |
| 0.20 Ω | 200 mV / 200 mW | 12.4 mm | 22.9 mm |

**A 1 A on-die low-side switch in this process is area-dominated, and that
is the facet's headline result.** Even the loosest row above needs ~23 mm of
gate width to hold 0.2 Ω at end of discharge and 125 °C. §3's worked example
uses the middle row (0.10 Ω, W ≈ 45.7 mm worst case) as the reference
channel, and the rest of this document is consistent with it.

### 2.3 Relationship to decision record 0008's stopgap baseline

Decision record 0008 ratified a `Ron·W` baseline for this facet by
re-expressing `sim/device-mv-fet`'s already-recorded on-resistance table,
which is measured at the PDK elec-spec convention of 75/90/100 % of `Vidsat`
= 4.5 / 5.4 / 6.0 V — bias points the facet never operates at. 0008 itself
flagged this as a stopgap and filed the purpose-built measurement as
[#179](https://github.com/2AMLogic/gf180-gate-driver/issues/179).

**§2.1's table supersedes 0008's table as this facet's design baseline.**
0008's numbers are *not* withdrawn as evidence — they remain valid
measurements of the same devices at the bias points they were taken at, and
`sim/` is append-only. The two reconcile: the new 5.0 V figure lands inside
0008's 5.4 V…4.5 V bracket at all three `tt` temperatures, and the new
`tt`/27 °C figures at `Vgs` = 5.0 V and 3.6 V (2.2246 / 2.7796 Ω·mm) land
within 1.5 % / 1.8 % of the 2.25 / 2.83 Ω·mm spot-check
[#178](https://github.com/2AMLogic/gf180-gate-driver/issues/178) cited and
0008 could only check by interpolation. Full cross-check table in the record
itself.

## 3. Metal, via and contact current-density budget at 1 A/channel

### 3.1 What the PDK actually rules

PDK Design Manual [§14.2 Electro-migration](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html)
(re-fetched 2026-08-18). The rules are set to meet
*T*₀.₁ > 100 000 hours at 85 °C junction temperature, where *T*₀.₁ is the
time to 0.1 % cumulative failures under a log-normal distribution. **The
1 A/channel target here is steady DC, so every number below is the DRM's
*unidirectional* column** ("the steady value of direct current or the time
average value of current always pulsed in the same direction"); the
bidirectional column does not apply to a low-side switch's supply path.

DRM Table 14.3 — maximum line current density per drawn width (mA/µm):

| conductor | 85 °C | 110 °C | 125 °C |
|---|---|---|---|
| Metal 1 … MetalTop−1 | 2.09 | 1.00 | 0.67 |
| MetalTop, 6 kÅ | 3.30 | 1.60 | 1.07 |
| MetalTop, 9 kÅ | 3.77 | 1.80 | 1.21 |
| **MetalTop, 11 kÅ (`tm11k`)** | **4.50** | **2.20** | **1.50** |
| **MetalTop, 30 kÅ (`tm30k`)** | **16.52** | **8.01** | **5.37** |

DRM Table 14.4 — maximum current per contact/via (mA):

| structure | 85 °C | 110 °C | 125 °C |
|---|---|---|---|
| COMP contact | 0.58 | 0.28 | 0.18 |
| Via1 … Via5 (0.26 µm) | 0.58 | 0.28 | 0.18 |

**These are the numbers this facet is budgeted against, at 125 °C** — the
top of `CLAUDE.md`'s mandated temperature range, and the last row the DRM
tabulates. DRM §14.2.2's temperature-scaling formula is stated only for
temperatures *below* 110 °C, so it cannot be used to extrapolate above
125 °C: **there is no published EM allowance above 125 °C at all**, which is
independently why §4 puts the thermal-shutdown trip where it does.

### 3.2 Ratified per-channel budget (1 A, 125 °C, unidirectional)

Drawn width / count required to carry one channel's 1 A:

| conductor | drawn width or count for 1 A @ 125 °C | @ 110 °C | @ 85 °C |
|---|---|---|---|
| Metal 1 … MetalTop−1 | 1493 µm | 1000 µm | 479 µm |
| MetalTop `tm11k` | **667 µm** | 455 µm | 222 µm |
| MetalTop `tm30k` | **186 µm** | 125 µm | 61 µm |
| COMP contacts | 5556 | 3572 | 1725 |
| Vias, **per via level** | 5556 | 3572 | 1725 |

Ratified consequences:

1. **The intermediate metals, not the top metal, are the per-layer worst
   case** (1493 µm at 125 °C). A single-layer 1 A bus on Metal1–Metal5 is
   not practical; the channel's current must be collected as a *distributed*
   strap over the device array and taken up to MetalTop, not routed as one
   wire. This is compatible by construction with §2.2's geometry — the
   reference channel is ~45.7 mm of gate width, so 1493 µm of accumulated
   intermediate-metal width is ~3 % of the device's own folded extent.
2. **Contacts and vias are not the binding constraint at this device size,
   but they are not free either.** 5556 vias per level, at Via1's
   array pitch (0.26 µm size, `V1.2b` 0.36 µm array spacing → 0.62 µm), is
   ~3.4 mm of single-row via, against a device ~45.7 mm wide. 5556 COMP
   contacts at `CO.1` 0.22 µm / `CO.2b` 0.28 µm array spacing → 0.50 µm
   pitch is ~2.8 mm of contacted diffusion edge, ~6 % of the device's gate
   width. Both fit — but **the via array must be drawn over the whole device
   array**, not concentrated at a bus tap, or the local per-via limit is
   violated even though the global count is satisfied.
3. **`tm30k` is worth 3.6× `tm11k` in EM-limited bus width** (5.37 vs.
   1.50 mA/µm at 125 °C) for 2.7× the metal thickness. It is also
   geometrically coarser: min width `MT30.1a` 1.8 µm and min space `MT30.2`
   1.8 µm, rising to `MT30.1b` 2.2 µm minimum width for a line longer than
   1000 µm — versus `MT.1` 0.44 µm / `MT.2a` 0.46 µm for the 9 kÅ/11 kÅ
   option. (DRC rule names as coded in the installed PDK's own KLayout deck,
   `libs.tech/klayout/drc/rule_decks/metaltop.drc` and `metaltop_30k.drc`,
   open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.)
4. **At its EM-limited width, the choice of top-metal option barely changes
   the bus IR drop — it changes the area.** The PDK's own sheet resistances
   (`libs.tech/ngspice/sm141064.ngspice`: `rsh_tm11k` = 0.040 Ω/□ typ,
   ±0.009; `rsh_tm30k` = 0.0095 Ω/□ typ, +0.0045/−0.0035) over a 500 µm bus
   run give 0.040 × 500/667 = **30 mΩ** for `tm11k` and
   0.0095 × 500/186 = **26 mΩ** for `tm30k`. That is not a rounding error
   against §2.2's 100 mΩ reference budget: **the supply routing eats a
   quarter to a third of the channel's whole `Ron` budget**, and it must be
   accounted in the budget rather than added to it afterwards.

### 3.3 Ratified guidance

- Route the channel's 1 A on **MetalTop**, sized from the 125 °C
  unidirectional row (667 µm `tm11k` / 186 µm `tm30k`), and treat the bus
  resistance as part of the §2.2 `Ron` budget, not as an addition to it.
- **`tm30k` is the preferred option where the shuttle offers it**, on area
  alone (186 µm vs. 667 µm of drawn width per ampere). `tm11k` is
  acceptable; `tm9k` and 6 kÅ are not recommended for a 1 A channel (1.21
  and 1.07 mA/µm at 125 °C — worse than `tm11k` for no area saving in the
  routing channel).
- The metal-stack option is a **shuttle-level choice, not a per-block one**
  — it is fixed for the whole reticle. This document therefore ratifies a
  budget for both options rather than one; which one a submission actually
  gets is [#180](https://github.com/2AMLogic/gf180-gate-driver/issues/180)'s
  problem.
- Bond-wire and package current limits are deliberately **not** ratified
  here — that is [#181](https://github.com/2AMLogic/gf180-gate-driver/issues/181)'s
  scope. The on-die budget above stops at the pad.

## 4. Protection scope

Same shape as [`gate-driver.md` §5](gate-driver.md), and read the same way:
a status per feature with the reason, not a circuit.

| Feature | Status this facet | Rationale |
|---|---|---|
| Per-channel overcurrent protection (OCP) | **In scope** | A shorted load puts the cell's full short-circuit current through a device sized for 1 A. Unlike facet (a), the switch is *on-die*, so a fault that would have destroyed an external FET destroys this die instead — OCP is the difference between a recoverable fault and a dead part. |
| Thermal sense + shutdown | **In scope** | §3 establishes that there is **no published EM allowance above 125 °C**, and §2.2 that the channel dissipates 0.1–0.2 W continuously with a 3:1 PVT window on top. Deferring thermal shutdown, as `gate-driver.md` §5 does for facet (a), is not defensible here: facet (a) drives a 1 nF gate, this facet drives 1 A into a load. |
| Undervoltage lockout (UVLO) | **In scope, inherited framing only** | `Vgs` *is* the cell voltage, so a collapsing cell directly degrades `Ron` (§2.1: at `tt`/27 °C, 3.6 V is 1.25× the 5.0 V figure, and it keeps climbing below 3.6 V, outside the measured range) rather than merely weakening a drive rail. Parameters are not ratified here — decision record 0001's UVLO parameters are specified against facet (a)'s 5 V drive rail and do not transfer. A per-facet UVLO threshold is an open item (§6). |
| Dead-time / shoot-through control | **Deferred** | There is exactly one switch per channel and (per §5) no actively driven high-side device, so there is nothing to sequence against. This is the same reasoning `gate-driver.md` §5 gives, and it is re-evaluated the moment §5's synchronous-PMOS option is revisited. |
| Overvoltage / gate-oxide protection | **In scope, structural** | `Vgs` never exceeds the cell voltage (5.0 V max) and the drain is clamped by §5's flyback path to roughly the cell voltage plus a junction drop, so no node is exposed to the 6.0 V thick-oxide DC ceiling of `gate-driver.md` §2.3 in normal operation. Unlike facet (a) this needs no exception: there is no rail above the device rating anywhere in the channel. The *fault* case (§5's clamp missing or open) is not covered by this argument and is an open item (§6). |

### 4.1 OCP reference structure

**Structure**: `Ron`-sense (drain-voltage sense) across the power NMOS
itself. A comparator takes the switch drain node against a reference
threshold `Vtrip`, is enabled only while the gate drive is asserted, and is
gated by a leading-edge blanking interval so the load's own turn-on
transient does not trip it. One comparator per channel.

**Target trip point**: `Vtrip` = 150 mV, blanking 1–5 µs (both to be pinned
by [#180](https://github.com/2AMLogic/gf180-gate-driver/issues/180)'s test
structures, which is what a blanking number needs to be measured against).

**The consequence §2.1's data forces, stated as spec**: a fixed-threshold
`Ron`-sense OCP inherits `Ron`'s whole 3:1 PVT window. With the §2.2
reference channel (W = 45.7 mm) and `Vtrip` = 150 mV, the trip current is

| condition | `Ron` | trip current at `Vtrip` = 150 mV |
|---|---|---|
| grid-worst (`Vgs` 3.6 V, 125 °C, slow corner) | 100 mΩ | **1.5 A** |
| `tt`, 27 °C, `Vgs` 4.2 V | 54 mΩ | **2.8 A** |
| grid-best (`Vgs` 5.0 V, −40 °C, fast corner) | 33 mΩ | **4.5 A** |

This OCP is therefore ratified as a **die-protection threshold, not a
precision current limit**, and the 1.5–4.5 A window is the specified
behaviour rather than an error budget to be closed later. A design that
needs a precision limit must use a ratioed sense-FET instead (a small mirror
device sharing gate and drain with the power switch, its source taken into a
sense element), which cancels `Ron`'s PVT dependence to first order because
both devices skew together — deliberately **not** ratified for this
increment, because it adds a matched-device and offset-accuracy problem to a
facet whose first job is characterizing the power device.

### 4.2 Thermal-sense reference structure

**Structure**: a diode-connected vertical PNP from the PDK's own BJT set
(`pnp_10p00x10p00` or `pnp_05p00x05p00`, `sm141064.ngspice`), biased at a
fixed current, its `Vbe` compared against a reference; ≈ −1.6…−2 mV/°C.
Placed **inside** the power device's array rather than at the die edge or
next to the bias block, because the whole point is to see the switch's own
junction temperature and not the average die temperature. One sense element
per channel, or per adjacent channel pair.

**Target trip point**: shutdown at Tj = 150 °C, release at 135 °C (15 °C
hysteresis). Rationale, both halves cited:

- **Above 125 °C** so it cannot false-trip anywhere inside the operating
  range the PDK itself assumes designers target — DRM
  [§14.1.1](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_1.html):
  "Circuit designers typically design their circuit for operation between
  −40 deg C to 125 deg C".
- **Not far above 125 °C**, because DRM Table 14.3/14.4 stop at 125 °C and
  §14.2.2's scaling formula is stated only below 110 °C — above 125 °C this
  facet's §3 metal budget has no published backing at all. Shutting down at
  150 °C bounds the excursion into that unspecified region to 25 °C rather
  than leaving it open-ended.

The PDK's BJT models carry their own corner sections (`bjt_typical` /
`bjt_ff` / `bjt_ss`, already in `sim/harness/corners.py`'s bundles and in the
`full` corner set), so the trip point's process spread is a corner axis the
harness can sweep directly when this structure is designed. It has **not**
been swept yet (§6).

## 5. Flyback handling

### 5.1 The path that has to exist

With the load between the cell's positive terminal and the switch drain, and
the switch's source at ground, turning the switch off against an inductive
load drives the drain **up**, above the cell rail. The switch's own
drain-to-bulk junction is reverse-biased in that direction and does not
conduct, so **the low-side NMOS has no usable body diode for this
transition** — the recirculation path must be a separate element from the
drain node back to the cell rail. Absent one, the drain rises until
something breaks down, which for a device sized per §2.2 means the switch
itself.

Three ways to build that path were considered. All three are the *same*
P+/N-well junction physics where a junction is involved, which is why one
measurement covers two of them.

### 5.2 Decision record

| | |
|---|---|
| Options considered | **(a)** the body diode of an unpowered high-side `pfet_06v0` placed drain-to-cell-rail; **(b)** a dedicated `diode_pd2nw_06v0` junction diode, drain-to-cell-rail, drawn and sized explicitly; **(c)** a synchronous high-side `pfet_06v0`, actively gate-driven on during the off interval so recirculation goes through the channel. |
| Evidence | `sim/low-side-power-switch/records/20260818-011754-03afe04.md`. `diode_pd2nw_06v0` forward drop at a fixed 10⁴ µm² reference area: **0.9742 V at 1 A** (`tt`/27 °C), full-grid **0.8687 … 1.0418 V**; 0.9230 V at 0.3 A and 0.8816 V at 0.1 A, i.e. a 10× larger diode buys only ~93 mV because the junction is far above the model's own high-injection knee. `pfet_06v0` `Ron·W` at cell-referenced `|Vgs|`: 5.9721…15.2279 Ω·mm at 3.6 V (§2.1). |
| Trade-offs | Options (a) and (b) are the **identical junction** — a PMOS's drain-to-nwell diode and `diode_pd2nw_06v0` are the same P+/N-well structure — so they do not differ in drop, only in whether the conducting area is a designed parameter or a side effect of the PMOS's channel sizing. Both cost ≈ 0.87…1.04 V, i.e. ≈ 0.9 W at 1 A while recirculating, essentially independent of how large the diode is drawn. Option (c) is the only one that can beat that, and §2.1's measured PMOS `Ron·W` prices it: merely *matching* the diode's ~0.9 V costs W ≈ 15.2279/0.9 ≈ **17 mm** worst case, and getting a worthwhile 0.1 V costs W ≈ **152 mm** — over 3× the entire low-side switch (§2.2). On top of the area, (c) requires a gate drive referenced to the cell rail above the switching node, i.e. exactly the floating/level-shifted high-side drive problem this facet's §1 scope excludes and facet (a) exists to study, plus dead-time control between the two devices, which `gate-driver.md` §5 deferred for the same "one channel, nothing to sequence against" reason. |
| Chosen | **(b) — a dedicated `diode_pd2nw_06v0` from the switch drain to the cell rail**, drawn at ≥ 10⁴ µm² of junction area per ampere of recirculation current, on its own EM budget per §3 (the flyback path carries the same 1 A the switch does, so it needs the same width/via allowance, not a token strap). |
| Rationale | (a) is rejected not because it performs worse — it is the same junction — but because it makes the recirculation area an *implicit* consequence of a channel width chosen for something else, and because with (c) rejected there is no high-side PMOS in the design for its body diode to belong to. Drawing the junction explicitly costs nothing and makes the current path visible to DRC, to LVS, and to a reader. (c) is rejected for this increment on measured area cost plus two whole subsystems (high-side floating drive, dead time) that this facet's scope excludes; it is the natural revisit if a future increment already carries a high-side drive for other reasons, at which point (b)'s diode becomes that PMOS's body diode and the two options converge. |

### 5.3 Ratified consequences

- The drain node is clamped at roughly **cell voltage + 0.87…1.04 V**, i.e.
  **≈ 6.04 V** at a fresh 5.0 V cell and the worst-case grid forward drop
  (5.0 + 1.0418). That is at the
  6.0 V thick-oxide DC ceiling of `gate-driver.md` §2.3, **not comfortably
  below it** — the drain of a device whose gate ceiling is 6.0 V. This is
  the tightest margin in the facet and is called out as an open item (§6)
  rather than waved through: it is a drain/junction bias, not a gate-oxide
  bias, so §2.3's ceiling is not the governing rule, but the governing rule
  has not been established here.
- The diode is reverse-biased at the cell voltage whenever the switch is on.
  `diode_pd2nw_06v0`'s model gives `bv` = 10.5 V, so 5.0 V reverse is
  well inside breakdown. Its reverse **leakage** at that bias and 125 °C
  adds directly to the channel's on-state current and has **not** been
  measured (§6).
- An on-die clamp does not remove the need for an external freewheel path
  for a genuinely energetic inductive load: ~0.9 W of recirculation
  dissipation lands on the same die as a 0.1–0.2 W switch and a thermal
  shutdown at 150 °C (§4.2). Sizing that trade is a system-level question
  this document does not settle.

## 6. Verification status and open items

Substantiated by an append-only `sim/` record:

- §2.1's `Ron·W` tables, both devices, full 15-point grid —
  `sim/low-side-power-switch/records/20260818-011754-03afe04.md`.
- §5's diode forward drop at 0.1/0.3/1.0 A, full 15-point grid — same
  record.

Cited to PDK documentation or the installed PDK, not simulated here:

- §3's entire EM budget (DRM §14.2 Tables 14.3/14.4, DRC rule decks, model
  sheet resistances). Arithmetic on those rules is shown inline so it is
  checkable; nothing in §3 is an independent derivation.

**Not yet substantiated — no claim is made:**

1. The §4.1 OCP comparator and §4.2 thermal-sense structures exist here as
   reference structures and target trip points only. No schematic, no
   testbench, no corner run.
2. The §4 UVLO threshold for this facet.
3. `diode_pd2nw_06v0` reverse leakage at cell-voltage reverse bias and
   125 °C (§5.3), which is an on-state loss term for the channel.
4. Whether the ~6.1 V worst-case clamped drain excursion of §5.3 is governed
   by a rule other than `gate-driver.md` §2.3's gate ceiling, and what that
   rule's bound is.
5. Switching loss and the gate-charge budget for a 23–91 mm device driven
   from the cell rail. §2 is a DC on-resistance spec; nothing here bounds
   the turn-on/turn-off transition.
6. Self-heating. Every number in §2 is from an isothermal model at a fixed
   `.temp`; the 0.1–0.2 W the channel actually dissipates raises its own
   junction temperature, which raises `Ron`, which raises the dissipation.
   §2.1's 125 °C column is an *ambient* corner, not a self-consistent
   operating point.

Items 1–6 are the input to
[#180](https://github.com/2AMLogic/gf180-gate-driver/issues/180)'s
test-structure plan. Per `CLAUDE.md` ("no claim without a testbench"), they
are open questions, not soft targets.

## 7. Relationship to `spec/gate-driver.md`

`gate-driver.md` is **unchanged** by this document, and this document does
not inherit from it. They are two facets of one shared device base
(decision record 0008), not two revisions of one spec:

| | `gate-driver.md` (facet a) | this document (facet b) |
|---|---|---|
| Switch | off-die, external | **on-die** `nfet_06v0` |
| Domains | 3.3 V logic → 5–6 V drive rail | one domain, the cell |
| Central problem | level shifting across domains | `Ron`·area and heat at 1 A |
| Load | 1 nF reference gate | a real ~1 A load |
| Thermal shutdown | deferred (§5) | **in scope** (§4) |

Where both documents touch the same PDK fact — the thick-oxide device
choice, the 6.0 V DC gate ceiling of `gate-driver.md` §2.3, the ±10 % supply
convention — `gate-driver.md`'s ratified statement stands and this document
cites it rather than restating it. The one place the two could be read as
conflicting is protection scope: `gate-driver.md` §5 defers thermal
shutdown, §4 above puts it in scope. That is not an amendment to
`gate-driver.md`; it is a different block with a different reason, and
`gate-driver.md` §5's own rationale ("Revisit if PVT/measured-silicon
results show a real thermal risk at the target drive currents") is scoped to
its own drive currents, not this facet's.
