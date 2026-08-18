# 0012: Low-side power-switch facet — shuttle test-structure plan (wafer.space GF180MCU quarter slot)

- **Status**: Ratified (plan only — no schematic, layout, DRC/LVS, or `sim/`
  campaign; see "Consequences" for the follow-on this record files)
- **Date**: 2026-08-18
- **Decided by**: Builder agent, issue #180
- **Extends**: [`spec/low-side-power-switch.md`](../low-side-power-switch.md)
  §6 (the six open items this plan is the input for), and, by explicit
  extension of their segregation principle rather than their literal port
  list, [decision record
  0001](0001-block-interface-and-uvlo-parameters.md)'s `GND_LOGIC`/`GND_DRV`
  split and [decision record
  0009](0009-multichannel-bond-ground-substrate-guidance.md)'s multi-channel
  bond/ground/substrate guidance. Amends neither.

## Context

[Decision records 0010](0010-low-side-power-switch-spec-ronw-em-and-protection.md)
and [0011](0011-low-side-power-switch-flyback-handling.md) ratified
`spec/low-side-power-switch.md`, the low-side on-die power-NMOS facet's spec:
cell-referenced `Ron·W`, an EM/current-density budget at 1 A/channel, `Vtrip`
= 150 mV / 1–5 µs-blanking OCP and 150 °C/135 °C thermal-sense reference
structures, and a dedicated `diode_pd2nw_06v0` flyback clamp — entirely from
PDK documentation, PDK models, and `sim/` DC-op-point sweeps. None of it has
been built or measured on real silicon. §6 of that document lists six open
items and names this issue as their consumer:

1. The §4.1 OCP comparator and §4.2 thermal-sense structures have no
   schematic, no testbench, no corner run.
2. No UVLO threshold is ratified for this facet.
3. `diode_pd2nw_06v0` reverse leakage at cell-voltage reverse bias and
   125 °C is unmeasured.
4. Whether the ~6.1 V worst-case clamped drain excursion (§5.3) is governed
   by a rule other than `gate-driver.md` §2.3's gate ceiling, and what that
   rule's bound is, is unresolved.
5. Switching loss / gate-charge budget for the 23–91 mm device (§2.2) is
   unbounded — §2 is a DC on-resistance spec only.
6. Self-heating: §2.1's `Ron·W` table is from an isothermal model at a fixed
   `.temp`; the channel's own 0.1–0.2 W dissipation is not folded back into
   a self-consistent operating point.

**This record is the plan those six items get measured against**, per
`CLAUDE.md`'s "no claim without a testbench." It is a plan, not the
schematic/layout/DRC/LVS work itself — that is explicitly deferred to a
follow-on issue (see "Consequences"), the same split `gate-driver.core`'s own
layout closure (issues #182/#183) used against its own already-ratified spec.

### The target shuttle slot, confirmed at build time

The issue's original text named "e.g. a wafer.space quarter slot, next
submission window" as an example, not a commitment. Re-checked against
`wafer.space` directly (fetched 2026-08-18, all figures date-stamped because
pricing/deadlines are explicitly a moving target):

- **wafer.space's GF180MCU Run 3 is open now** and, per its own 1 Aug 2026
  announcement (`wafer.space/news/run3-announcement`), introduces a new
  **0.5×0.5 "quarter slot"** specifically pitched at "test structures, analog
  circuits, or compact digital designs" — **4.9 mm² of silicon**, **1,000
  dies for $2,000** ($2/die). This is a good match for a test-structure plan,
  not a coincidence to route around.
- **Precise geometry**, from `mithro.github.io/gf180mcu-project-template/`
  (page content generated 04 Jun 2026, fetched 2026-08-18 — the same 4.90 mm²
  figure corroborates the news post, so the geometry has not changed between
  the two dates even though the price point is new in Run 3): the standard
  (4-side pad ring) **0.5×0.5 quarter slot** —

  | | |
  |---|---|
  | Die size | 1.94 mm × 2.53 mm (4.90 mm²) |
  | Usable silicon (inside the 26 µm seal ring) | 1.88 mm × 2.48 mm (4.67 mm²) |
  | **Core area (inside the IO ring — the design area)** | **1.05 mm × 1.65 mm (1.73 mm²)** |
  | IO overhead | 65 % |
  | Total pads | **56** — 48 IO (38 bidir, 6 in, **4 analog**) + 8 power (4 `DVDD` + 4 `DVSS`) |

  A "2-side EXACT" quarter variant also exists (pads pinned to `slot_1x1`
  coordinates, larger core at 2.66 mm² but only 18 total pads). This plan
  targets the **standard 4-side quarter slot** because its 56-pad budget
  comfortably covers the pad list below with margin (§ "Pad budget"), while
  the 2-side variant's 18-pad budget would not — § "Pad budget" counts **18
  pads used here**, i.e. that variant's entire budget with zero margin, and
  that is before asking whether its 18 pads even break down into the 4
  analog + 8 power types this plan's pad list depends on.
- **Dates disagree between two wafer.space pages fetched the same day**,
  which is itself the "next submission window is a moving target" the issue
  warned about: the live countdown on `wafer.space`'s front page (fetched
  2026-08-18) shows a purchase deadline of **9 December 2026** and a
  submission deadline of **16 December 2026**; the 1 Aug 2026 announcement
  post states **15 December 2026** / **29 December 2026**. Neither is treated
  as authoritative here — **whoever executes the follow-on schematic/layout
  issue (see "Consequences") must re-confirm the live deadline against
  `wafer.space` before purchasing a slot**, not trust either figure quoted in
  this record.

## Decision

### 1. Channel count: **one**, not two

A literal, production-scale channel does not fit this slot, and that is not
a layout-stage discovery — it follows from numbers already ratified.
`spec/low-side-power-switch.md` §3.2 ratifies that a single channel's 1 A
supply bus alone needs **≥ 667 µm of drawn MetalTop (`tm11k`)** — or, for the
intermediate metals that are the actual per-layer worst case, **1493 µm** —
distributed across the whole device array (§3.2's own point 2: "the via
array must be drawn over the whole device array, not concentrated at a bus
tap"). The quarter slot's core area is **1.05 mm × 1.65 mm**, i.e. its short
dimension is **1050 µm**. A `tm11k` bus at the full-1 A EM-compliant width
already consumes **64 %** of that short dimension for supply routing alone,
and the intermediate-metal figure (1493 µm) **exceeds the entire short
dimension** — before the switch device itself, the OCP/thermal circuitry,
any flyback structure, probe/Kelvin routing, or a second channel are laid
down at all. A full-current (~1 A), full-width (45.7 mm at the §2.2
reference `Ron` budget) production-representative channel is therefore not a
choice this plan can make differently at layout time — it is arithmetically
incompatible with this slot, on numbers already in the ratified spec.

**This plan therefore does not attempt a production-scale channel.** It uses
a deliberately reduced-scale representative channel (§2 below) whose own
EM-mandated bus width is a small fraction of the core's short dimension, and
whose job is to validate structure *behavior* (trip points, self-heating
trend, diode/PMOS forward characteristics, leakage) rather than to be a 1:1
stand-in for the production part. At that reduced scale, a first-order
estimate (§ "Area budget" below) suggests the raw silicon for a *second*
reduced-scale channel would likely also fit the remaining core area and pad
budget — but this plan still chooses **one** channel for this round, for a
reason distinct from raw area: this is the facet's first-ever silicon
(`spec/low-side-power-switch.md` inherits `README.md`'s maturity ladder, and
per decision record 0008/issue #178, no measured result exists yet for
either on-die facet). The plan prioritizes **depth of instrumentation on one
channel** — dedicated Kelvin sense on every node, external trim access on
both comparators, a probe-accessible blanking timer, a shared flyback
comparison structure — over breadth (a second channel duplicating the same
measurement), and holds the area/pad headroom a single channel leaves
unused as a margin against layout-stage costs (guard-ring area, DRC spacing,
routing overhead) this plan cannot price precisely without doing the layout
work that is explicitly out of scope here (see "Scope clarification" in
issue #180). A second channel — for channel-to-channel mismatch, not for
more current — is the natural next round once this round's actual layout
area is known, not something this record rules out permanently.

### 2. The test channel: `nfet_06v0`, `W` = 1 mm, with per-channel OCP and thermal sense

**Sizing.** `W` = 1 mm is chosen deliberately, not rounded from a larger
number: at that width, §2.1's `Ron·W` table (Ω·mm) reads directly as Ω with
no unit conversion, and — checked against the EM argument above — even its
worst-case trip current (below) keeps the structure's own EM-mandated bus
width to ~65 µm, a small fraction of the core's 1050 µm short dimension.

| condition | `Ron·W` (§2.1, Ω·mm) | `Ron` at `W` = 1 mm (Ω) | trip current at `Vtrip` = 150 mV |
|---|---|---|---|
| grid-worst (`Vgs` 3.6 V, full-grid max) | 4.5719 | 4.5719 | **32.8 mA** |
| `tt`, 27 °C, `Vgs` 4.2 V | 2.4758 | 2.4758 | **60.6 mA** |
| grid-best (`Vgs` 5.0 V, full-grid min) | 1.5287 | 1.5287 | **98.1 mA** |

At the top of that range (98.1 mA), the structure's own EM-mandated `tm11k`
bus at 125 °C (1.50 mA/µm, §3.1) is 98.1/1.50 ≈ **65 µm** — 6 % of the core's
short dimension, leaving headroom for the analog circuitry, the flyback
structure, and probe routing this same channel needs.

**Per-channel instrumentation, with dedicated probe access to the trip
points themselves** (not just pass/fail inference of correct operation),
per issue #180's acceptance criteria:

- **OCP (§4.1)**: an `Ron`-sense comparator against the switch drain, gated
  by leading-edge blanking. **Blanking is pinned to 2 µs** — new information
  this plan adds within the ratified 1–5 µs range, not a restatement.
  Rationale: `gate-driver.md` §3's propagation-delay target (<50 ns) bounds
  the switch's own turn-on transient to well under 1 µs even with generous
  margin for probe/Kelvin routing parasitics on a test die, and facet (b)'s
  own §4 protection-scope table gives the reason to pick the *fast* end of
  the ratified range rather than the slow end: the switch is on-die, so "a
  fault that would have destroyed an external FET destroys this die
  instead" — faster fault response is worth more here than it would be for
  an external-FET design. The shuttle's own external trim access (below)
  lets 2 µs be checked against the bench's actual load-turn-on transient
  before this pin is carried into a production design, rather than only
  after.
- **Thermal sense (§4.2)**: a diode-connected vertical PNP inside the
  switch's own array, biased at a fixed current, `Vbe` compared against a
  reference; target trip 150 °C / release 135 °C, unchanged from §4.2 (this
  record does not revisit that choice, per Implementation Guidance).

**Probe access** (both structures get an external reference-override input
so the *trip point itself*, not just correct on/off behavior around some
assumed threshold, can be swept and measured):

| Net | Pad type | Purpose |
|---|---|---|
| `VDD_DRV` | `DVDD` ×2 | Cell-rail supply |
| `GND_DRV` | `DVSS` ×2 | Switch source / switching-current return |
| `GND_SENSE` | `DVSS` ×1 | Quiet return for the OCP/thermal comparators — new, see § "Consistency check" |
| `GATE` | general IO (in) | External gate drive for the test channel |
| `DRAIN_FORCE` | general IO (bidir) | Power-level drain node; forced-current path for `Ron`/OCP/flyback sweeps |
| `DRAIN_SENSE` | **analog** | Kelvin sense on drain — 4-point `Ron`/`Vtrip` measurement |
| `SOURCE_SENSE` | general IO (bidir) | Kelvin sense on source |
| `OCP_VTRIM` | **analog** | External override of the OCP comparator's `Vtrip` reference — sweeps the trip point directly |
| `OCP_OUT` | general IO (bidir) | OCP comparator digital trip output |
| `THERM_VTRIM` | **analog** | External override of the thermal comparator's reference — sweeps shutdown/release thresholds directly |
| `THERM_VBE` | **analog** | Direct sense of the diode-connected PNP's `Vbe` |
| `THERM_OUT` | general IO (bidir) | Thermal comparator digital output (shutdown/release) |
| `THERM_IBIAS` | general IO (bidir) | External force-current option for the PNP bias, independent of the on-die bias generator |

The four dedicated **analog** pads the quarter slot provides are used
exactly for the four most sense-critical nodes (`DRAIN_SENSE`,
`OCP_VTRIM`, `THERM_VTRIM`, `THERM_VBE`) — the only pad category this plan
fully consumes (§ "Pad budget").

### 3. Flyback: all three variants, as two structures (not three)

`spec/low-side-power-switch.md` §5.2 chose option (b) — a dedicated
`diode_pd2nw_06v0` clamp — for production, but options (a) and (c) share the
**same physical device**: a `pfet_06v0` whose drain-to-nwell body diode *is*
option (a) when its gate is left floating/off, and *is* option (c) when its
gate is actively driven on. One structure with an accessible gate pad
therefore measures both, rather than needing two.

- **Structure A's own drain clamp already instantiates option (b)** — no
  separate structure is needed for it; `DRAIN_SENSE` and `VDD_DRV` already
  give Kelvin access to its forward drop (forcing current backward through
  `DRAIN_FORCE` with the switch held off) and its reverse leakage (forcing
  the switch on and reverse-biasing the diode at the cell voltage, at
  elevated ambient — see § "Traceability", item 3).
- **One shared `pfet_06v0` structure measures options (a) and (c)**, with
  `FLY_FORCE` / `FLY_SENSE` (Kelvin) and `FLY_GATE` (floating/off = option
  a; driven on = option c). These are **three additional general-IO pads**
  — they do not share §2's pads, because the flyback structure must be
  measurable independently of (and concurrently with) the switch channel it
  is being compared against, and all four analog pads are already committed
  to §2's sense-critical nodes. They are counted as general IO in
  § "Pad budget".

**Sizing, at a chosen comparison current of `I_test` = 100 mA (0.1 A)** —
chosen to exactly match the *lowest already-recorded* point in
`sim/low-side-power-switch/records/20260818-011754-03afe04.md` (the 0.1 A
row of decision record 0011's table), so the shuttle measurement is
directly checkable against existing simulation evidence at the same nominal
current, not just the same current-density convention:

- **Structure A's diode**: `≥ 10⁴ µm²/A × 0.1 A = 1000 µm²` junction area,
  per §5.2's ratified sizing rule. This is a **different area** than the
  existing sim record's fixed 10⁴ µm²-reference device (which swept current
  0.1–1.0 A through one fixed-size diode) — at 100 mA, this structure's
  current density (10⁻⁴ A/µm²) matches the sim record's **1 A** point, not
  its 0.1 A point, so this is genuinely new evidence about how area scaling
  (not just current scaling) affects the real forward drop, not a repeat of
  an existing measurement.
- **Shared flyback PFET**: sized to *match* the diode's forward drop at
  `I_test`, using the `tt`/27 °C/0.1 A diode figure from decision record
  0011 (0.8816 V) and the grid-worst `pfet_06v0` `Ron·W` at `|Vgs|` = 3.6 V
  (15.2279 Ω·mm, §2.1): `Ron_target = 0.8816 V / 0.1 A = 8.816 Ω`, so
  `W = 15.2279 / 8.816 ≈ 1.7 mm`. This is the *same* trade-off §5.2 already
  priced at production scale (17 mm to merely match, 152 mm to meaningfully
  beat it) — 10× smaller because `I_test` is 10× smaller than 1 A — so the
  shuttle confirms the trade-off's **direction and magnitude on real
  silicon** at a size that actually fits, rather than attempting to build a
  PMOS large enough to *beat* the diode, which even at this reduced current
  would already cost more width than this plan budgets for the entire
  structure.

### Traceability — which of the six open items this shuttle round retires

| # | Item | Retired by | Status this round |
|---|---|---|---|
| 1 | OCP + thermal-sense structures have no schematic/testbench/corner run | Structure A (§2) | **Retired** — both structures get a schematic, dedicated probe access, and a real measurement; see § "PVT-grid honesty" for what "corner run" can and cannot mean from a shuttle sample. |
| 2 | No facet UVLO threshold ratified | — | **Not retired this round.** `spec/low-side-power-switch.md` §4 explicitly leaves the *parameters* unratified, not just unmeasured — there is nothing to build a test structure against yet. A UVLO-parameter decision record (analogous to decision record 0001 Decision 4, but for facet (b)'s single-domain cell rail) must land first; that comparator's own shuttle structure is a later round's plan, not this one's. |
| 3 | `diode_pd2nw_06v0` reverse leakage at cell-voltage reverse bias, 125 °C | Structure A's embedded diode (§3) | **Retired** — forced-off, reverse-biased leakage measured directly at a thermal-chamber 125 °C setpoint, on the same physical clamp Structure A already carries. |
| 4 | Governing rule for the ~6.1 V clamped drain excursion | Structure A (magnitude only) | **Partially retired.** The shuttle *measures* the real clamped drain voltage under the diode flyback path (confirming or correcting the ~6.04–6.1 V figure §5.3 derived from simulation alone) — that is new, real evidence. It does **not** retire the other half of item 4: identifying *which* reliability/DRM rule governs a drain (not gate-oxide) bias at that level is a documentation-research task, not a measurement one, and is explicitly left open here. Confirming no long-term degradation at that bias would additionally need an accelerated-life/HTOL-style stress test, which is out of scope for a single shuttle measurement pass. |
| 5 | Switching loss / gate-charge budget unbounded | Structure A, board-level double-pulse test (not a new on-die structure) | **Partially retired**, and explicitly not silently dropped, per issue #180's own instruction. `GATE`, `DRAIN_SENSE`, and `SOURCE_SENSE` already give everything a board-level double-pulse gate-charge test needs — no additional on-die structure. Gate charge `Qg` scales approximately linearly with device width and transfers reasonably from this 1 mm test channel to a width-scaled production estimate. **Switching *energy* (`Eon`/`Eoff`) at the real production scale does not transfer the same way** — realistic `dI/dt` into a genuinely ~1 A inductive load exceeds both this 1 mm structure's own safe operating area and what this plan's bench probe setup is sized to deliver this round, so the production-scale loss figure stays an extrapolation from a measured `Qg`, not a direct measurement, this round. |
| 6 | Self-heating not folded into a self-consistent operating point | Structure A, forced-power sweep | **Partially retired.** Sweeping `Vds` at fixed `Vgs` on Structure A's switch (beyond the small-signal `Ron`-extraction regime) forces a range of dissipation levels through the *actual fabricated array geometry*, and cross-referencing the resulting `Ron` shift against §2.1's already-known `Ron(T)` PVT dependence extracts an effective thermal resistance `R_th` for that specific layout — a real measurement, not an isothermal simulation. It does **not** directly measure the production channel's self-consistent operating point: at 1 mm this structure dissipates far less than the production channel's own 0.1–0.2 W, so the full-scale self-consistent point is reached by applying this round's measured `R_th` (scaled by the metal/via density already known from §3) to the production geometry, not by a 1:1 silicon measurement. |

### PVT-grid honesty

The wafer.space quarter slot's **1,000-die yield per slot purchase** (§
"Context") is a genuinely large sample — large enough for real
device-to-device mismatch statistics and, since temperature is
externally controllable (thermal chamber/hotplate, −40…125 °C, the exact
axis `spec/low-side-power-switch.md` §2.1 and `CLAUDE.md` already mandate),
large enough to sweep the **temperature axis** of the ratified grid with
real silicon, on many samples, not one. **It does not, and cannot from one
slot purchase, validate the process-corner axis** (`tt`/`ff`/`ss`/`fs`/`sf`):
all 1,000 dies come from the same reticle exposure on the same wafer lot,
so they share whatever single process-corner draw that lot landed on — not
a chosen corner, and not the five corners §2.1/§5.2's simulated grid
covers. **What this shuttle round validates**: whichever corner this lot
actually lands on, across the full temperature range, with real
device-to-device spread data. **What stays simulation-only**: the other
four process corners, and therefore any claim about the *width* of the
process-corner spread itself (the "3.0× worst-to-best" figure in §2.1) —
that figure is not something one lot's silicon can confirm or refute on its
own, and this plan does not claim it will.

### Area budget

**Known, not estimated**: the target slot's core area (1.73 mm²) and pad
budget (56 total — see § "Pad budget" below), both cited to `wafer.space`
above.

**First-order, not layout-verified** — flagged explicitly as such, the same
way `spec/low-side-power-switch.md` §2.2/§3 give ratified budgets and rules
rather than final layout numbers before layout exists: at `I_test` ≤
100 mA, none of this plan's structures need the EM-driven metal strapping
that dominates the *production* channel's footprint (§3's 1493 µm figure) —
the 1 mm switch and 1.7 mm flyback PFET's own EM-mandated bus widths are
each ~65 µm (§2), a small fraction of the core's 1050 µm short dimension.
The likely area cost driver at this reduced scale is therefore the **analog
comparator/reference circuitry and its guard-ring/substrate-tap overhead**
(§ "Consistency check" below), not the power devices themselves — and this
plan does not have a layout to measure that against. This is stated as an
open input to the follow-on schematic/layout issue (§ "Consequences"), not
papered over with an invented number.

### Pad budget

**18 of 56 pads used** (4 of 4 analog, 9 of 44 general IO, 5 of 8 power) —
counted from the tables in §2 and §3:

| Category | Pads | Of budget | Which |
|---|---|---|---|
| Power (`DVDD`/`DVSS`) | 5 | 5 of 8 | `VDD_DRV` ×2 (`DVDD`), `GND_DRV` ×2 + `GND_SENSE` ×1 (`DVSS`) |
| Analog | 4 | **4 of 4** | `DRAIN_SENSE`, `OCP_VTRIM`, `THERM_VTRIM`, `THERM_VBE` |
| General IO | 9 | 9 of 44 | §2: `GATE`, `DRAIN_FORCE`, `SOURCE_SENSE`, `OCP_OUT`, `THERM_OUT`, `THERM_IBIAS`; §3: `FLY_FORCE`, `FLY_SENSE`, `FLY_GATE` |
| **Total** | **18** | **18 of 56** | |

(The 44-pad general-IO budget is the slot table's 48 IO pads minus its 4
dedicated analog pads: 38 bidir + 6 in.)

**Pad count is not the binding constraint on channel count or structure
count** — area is (§1) — but the four dedicated
analog pads are the one category this plan fully consumes, which is worth
carrying forward: a future second channel would need to either share the
existing analog pads' sensitive nodes through an on-die mux, or accept that
its own most-sensitive nodes route through general-purpose IO pads instead
of the analog-specific ones.

### Consistency check against decision records 0001 and 0009

**Decision record 0001's `GND_LOGIC`/`GND_DRV` split does not transfer
literally** — facet (b) has no separate 3.3 V logic domain the way facet
(a) does (`spec/low-side-power-switch.md` §1: "the cell rail itself" is the
gate drive), so there is no `GND_LOGIC` pin to reuse, and facet (b) has no
ratified port list of its own to check this test chip's pad list against.
**The segregation *principle* does transfer**, and this plan applies it for
the first time to facet (b): the OCP and thermal-sense comparators are
exactly the category of "sensitive, low-level reference circuit that must
be kept off a high-dI/dt switching return" that motivated 0001's split and
0009's per-channel extension of it. `GND_SENSE` (§2's pad table) is that
application — a dedicated, physically separate `DVSS` pad for the
comparators' reference return, distinct from `GND_DRV`'s switching-current
return — new guidance this plan is adding for facet (b), not a restatement
of 0001/0009's facet-(a)-specific numbers.

**Decision record 0009's per-channel `GND_DRV_n` and bond-wire sizing
degenerate cleanly at N = 1** (0009's own stated behavior): with one
channel, `GND_DRV_1` is `GND_DRV`, consistent with this plan's pad table.
**0009's ≥2 mil-of-bonded-diameter-per-amp rule is not binding at this
plan's reduced test currents**: the highest current any structure here
carries is Structure A's OCP trip current, ≤ 98.1 mA — a single standard
1 mil bond wire, even at 0009's own conservative 0.5 A/mil derated point,
already clears that with ~5× margin. This is recorded so it is not mistaken
for evidence that 0009's rule is loose in general — it is a consequence of
this shuttle's deliberately reduced test current (§1), not a re-evaluation
of 0009's production-scale (~1 A) sizing point, which remains unchanged.

## Alternatives considered

- **Build a production-scale (1 A, ~45.7 mm) channel on the shuttle** —
  rejected on the arithmetic in §1: the EM-mandated supply bus alone (1493
  µm intermediate-metal, or 667 µm `tm11k`) does not fit inside the quarter
  slot's 1050 µm core short dimension. Not a layout-stage judgment call.
- **Buy a larger slot (0.5×1, 1×0.5, or 1×1) to fit a production-scale
  channel** — rejected for *this* record. It would resolve §1's area
  arithmetic, but escalates cost (a full 1×1 slot's own die is over 4×
  the quarter slot's area) for a first-round facet with no measured silicon
  at all yet, and is a budget/scope decision this plan does not have
  standing to make silently — if a future round needs it, that is its own
  decision record, made with this round's actual results in hand.
- **Two reduced-scale channels instead of one** — considered and rejected
  for this round; see §1's full reasoning (pad/area headroom likely
  supports it, but instrumentation depth on one channel is prioritized for
  the facet's first silicon round, and the actual layout area this plan's
  circuitry needs is not yet known).
- **Three separate flyback structures (one per variant)** — rejected once
  the physical-device identity between options (a) and (c) was recognized
  (§3): they are the same `pfet_06v0` in two gate-bias conditions, so one
  structure with an accessible gate pad measures both, saving area and
  pads without losing any comparison the issue's acceptance criteria asks
  for.
- **Size the shuttle's flyback PFET to actually beat the diode's drop, not
  just match it** — rejected. §5.2 already prices that at ~152 mm at
  production scale (over 3× the entire switch); at this shuttle's 10×
  smaller test current the same trade-off scales to ~15.2 mm, which this
  slot's 1.73 mm² core cannot absorb alongside everything else this plan
  needs. Matching (not beating) the diode is the size this plan can afford
  and still get a real, apples-to-apples comparison.
- **Leave the OCP blanking time unpinned, deferring it to the layout
  issue** — rejected. `spec/low-side-power-switch.md` §4.1 explicitly says
  pinning the value is this plan's job ("to be pinned by #180's test
  structures, which is what a blanking number needs to be measured
  against"); deferring it again would just move the same open question one
  issue further down the chain without resolving it.
- **A precision, ratioed-sense-FET OCP instead of the ratified `Ron`-sense
  comparator** — not reconsidered here; decision record 0010 already
  rejected it for this facet's first increment, and this plan builds the
  structure §4.1 already specifies rather than re-opening that choice.

## Consequences

- `spec/low-side-power-switch.md` §6 gains a forward reference to this
  record, the same way its §2.3 already cross-references decision record
  0008.
- `README.md`'s "Two facets, one shared device base" section stops
  describing the shared-shuttle test-structure plan as deferred to issue
  #180 and points at this record instead, mirroring how decision record
  0009 landing updated the equivalent multi-channel-guidance line (commit
  `3327220`).
- `spec/README.md` gains an index entry for this record, per this
  directory's own convention (every prior decision record does this in its
  own "Consequences").
- **A follow-on issue is required** for the actual schematic capture,
  layout, and DRC/LVS closure of the structures this plan names — that work
  is explicitly out of scope for this record (issue #180's own "Scope
  clarification"), the same split `gate-driver.core`'s layout closure
  (issues #182/#183) used against its own already-ratified spec. That issue
  must re-confirm wafer.space's live purchase/submission deadlines before
  any slot purchase, per the date discrepancy noted in "Context".
- Item 2 (UVLO threshold) stays a genuinely open item after this round —
  not silently dropped, but explicitly requiring its own decision record
  (parameters, analogous to decision record 0001 Decision 4 but scoped to
  facet (b)'s single-domain cell rail) before any UVLO test structure can
  be planned.
- Items 4 and 5 are only **partially** retired by this round (§
  "Traceability") — the governing-rule half of item 4 and the
  production-scale switching-energy half of item 5 remain open after this
  shuttle's results land, and should not be read as closed once this plan's
  structures are measured.
- No `sim/` record or ratified spec parameter is edited or superseded by
  this record. It is a plan for future evidence, not evidence itself.
