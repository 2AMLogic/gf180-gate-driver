# 0010: `spec/low-side-power-switch.md` — cell-referenced `Ron·W` baseline, EM budget, and protection structures

- **Status**: Ratified
- **Date**: 2026-08-18
- **Decided by**: Builder agent, issue #179

## Context

[Decision record 0008](0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md)
scoped the low-side on-die power-NMOS facet into this repo and ratified a
**stopgap** `Ron·W` baseline by re-expressing `sim/device-mv-fet`'s existing
on-resistance table. That table is measured at the PDK elec-spec convention
of 75/90/100 % of `Vidsat` — 4.5 / 5.4 / 6.0 V — which is not where this
facet operates: a single Li-ion cell presents 5.0 V fresh, 4.2 V nominal and
3.6 V at end of discharge, and the cell rail *is* the gate drive. 0008 said
so itself, deferred the purpose-built measurement and the facet's whole spec
document to issue #179, and left `spec/low-side-power-switch.md` unwritten.

Three of the four things #179 asks for are decided here; the fourth (flyback
handling) is its own record, [0011](0011-low-side-power-switch-flyback-handling.md).
That split is deliberate — see "Alternatives considered".

## Decision

**1. `spec/low-side-power-switch.md` is created and ratified** as the facet's
spec document, separate from `gate-driver.md` exactly as 0008 said it would
be. It does not amend `gate-driver.md`; §7 of the new document states the
relationship, including the one place the two documents could be misread as
conflicting (thermal shutdown: deferred for facet (a), in scope for facet
(b)).

**2. The cell-referenced `Ron·W` table replaces 0008's stopgap baseline as
this facet's design baseline.** Measured across the full 15-point process ×
temperature grid in
`sim/low-side-power-switch/records/20260818-011754-03afe04.md`, method- and
geometry-identical to `sim/device-mv-fet` so the two are directly
comparable. `nfet_06v0`, Ω·mm:

| `Vgs` | `tt`, −40 °C | `tt`, 27 °C | `tt`, 125 °C | full grid min .. max |
|---|---|---|---|---|
| 5.0 V | 1.6996 | 2.2246 | 3.0903 | 1.5287 .. 3.6176 |
| 4.2 V | 1.9053 | 2.4758 | 3.4115 | 1.6907 .. 4.0510 |
| 3.6 V | 2.1525 | 2.7796 | 3.7996 | 1.8855 .. 4.5719 |

**Design point: 4.5719 Ω·mm** (grid-worst, `Vgs` = 3.6 V), which is 3.0× the
grid-best point. "Replaces as design baseline" is not "withdraws as
evidence": 0008's numbers remain valid measurements at the bias points they
were taken at, and `sim/` is append-only — nothing under `sim/device-mv-fet/`
is touched.

The new measurement reconciles with the old: the 5.0 V figure lands inside
0008's 5.4 V…4.5 V bracket at all three `tt` temperatures, and the `tt`/27 °C
5.0 V and 3.6 V figures (2.2246 / 2.7796 Ω·mm) land within 1.5 % / 1.8 % of
the 2.25 / 2.83 Ω·mm spot-check issue #178 cited and 0008 could only check by
interpolation. Issue #179's test plan required this cross-check before
ratifying; it passes, so no investigation was needed.

**3. The EM/current-density budget is ratified from the PDK's own rules**
(DRM §14.2 Tables 14.3 and 14.4), at 125 °C and in the *unidirectional*
column, since a 1 A low-side channel is steady DC. Per ampere per channel:
1493 µm of Metal1…MetalTop−1, **667 µm of `tm11k`** or **186 µm of `tm30k`**,
and 5556 contacts / 5556 vias per via level. `tm30k` is the preferred
top-metal option where a shuttle offers it, on area alone.

**4. Per-channel OCP and thermal sense are in scope, with reference
structures and target trip points** at the level of detail `gate-driver.md`
§5's protection-scope table uses — an `Ron`-sense comparator with `Vtrip`
= 150 mV and 1–5 µs blanking, and a diode-connected vertical PNP
(`pnp_10p00x10p00`) thermal sense tripping at Tj = 150 °C with 15 °C
hysteresis, placed inside the power device's array. Neither is designed
here; both are specified.

## Alternatives considered

- **Keep 0008's stopgap `Ron·W` numbers and write the spec around them** —
  rejected. The whole reason #179 exists is that 4.5/5.4/6.0 V is not where
  this facet operates, and the difference is not academic: the design point
  moves from 0008's 3.8618 Ω·mm (its worst 4.5 V grid figure) to 4.5719 Ω·mm,
  an 18 % larger switch for the same `Ron` budget, because the real
  end-of-discharge gate drive is 0.9 V lower than the lowest point 0008 could
  reach.
- **Fold this facet into `gate-driver.md` as a new section** — rejected,
  and already rejected by 0008 for the same reason: different device use,
  different deliverables, different protection scope. Folding it in would
  force `gate-driver.md`'s §5 to hold two contradictory thermal-shutdown
  rows.
- **One comprehensive decision record for all four of #179's deliverables**
  (0008's own bundling precedent) — rejected. The flyback decision is the
  only one of the four with a genuine multi-option trade and its own
  measured evidence deciding between the options; bundling it would bury a
  reviewable choice inside a ratification. Splitting it out follows this
  repo's more common one-decision-per-record pattern (0002–0007) for the
  part that actually is one decision, while keeping the "here is the facet's
  spec document and its numbers" ratification together, since its three
  parts are not independently adoptable — the EM budget is expressed per
  ampere through a channel whose width comes from the `Ron·W` table, and the
  OCP trip window is derived from that same table's spread.
- **Split further, one record per topic (`Ron·W`, EM, protection)** —
  rejected as over-fragmentation for exactly that reason: a reviewer cannot
  usefully evaluate the OCP trip window without the `Ron·W` table in front
  of them, since the window *is* the table's spread.
- **Derive metal current-density limits from first principles rather than
  citing the DRM** — rejected; 0008's own pattern is citing PDK
  documentation, and an EM limit derived independently would be an invented
  reliability claim. The only arithmetic done here is dividing 1 A by the
  DRM's published mA/µm, shown inline so it is checkable.
- **Ratify a precision current-limit OCP (ratioed sense-FET)** — rejected
  for this increment. It cancels `Ron`'s PVT dependence to first order, but
  it adds a device-matching and comparator-offset accuracy problem to a
  facet whose first job is characterizing the power device itself. The
  `Ron`-sense structure is ratified instead **with its 1.5–4.5 A trip window
  stated as the specified behaviour**, rather than quoting a single trip
  current the data does not support.
- **Defer thermal shutdown, mirroring `gate-driver.md` §5** — rejected. That
  deferral's stated rationale is that a single-channel canary driving a 1 nF
  gate has no real thermal risk. This facet drives 1 A continuously and, per
  the DRM, has **no published EM allowance above 125 °C** — the risk is the
  reason the feature exists.

## Consequences

- `spec/low-side-power-switch.md` exists and is the authority for facet (b);
  `spec/README.md` indexes it and this record.
- `README.md`'s "Two facets" section stops describing facet (b)'s spec
  content as deferred to #179 and points at the document instead.
- Anything that was sizing this facet's switch from 0008's table gets an
  18 % larger device at the same `Ron` budget. Nothing in the repo was, since
  no schematic for this facet exists yet — the cost is paid now rather than
  after a layout.
- The 1 A channel is confirmed **area-dominated**: 45.7 mm of gate width for
  0.10 Ω worst case, and a supply bus that eats 26–30 mΩ of that same 100 mΩ
  budget. Any future floorplan for this facet starts from that, not from a
  transistor-count estimate.
- `sim/low-side-power-switch/` joins the experiment set: discoverable via
  `python3 sim/run_corners.py --list`, with a `tb.json` that also runs a
  representative op-point subset through the generic CLI. Unlike every other
  experiment here it selects `corners.py`'s **full per-device-family section
  bundles** rather than a bare MOS `.LIB` section, because its deck contains
  a diode whose model lives under the diode family's own sections; that is
  why its corner-ids read `tt`/`ff`/`ss`/`fs`/`sf` where
  `sim/device-mv-fet`'s read `typical`/`ff`/…, and it is recorded in the
  record itself so a later reader does not mistake it for a narrowed grid.
- Six things are ratified as **open**, not as soft targets (new document
  §6): the OCP and thermal structures have no schematic or testbench, the
  facet's UVLO threshold is unset, the flyback diode's reverse leakage is
  unmeasured, the governing rule for the clamped drain excursion is
  unestablished, switching loss and gate charge for a 23–91 mm device are
  unbounded, and every `Ron` figure here is isothermal — self-heating is not
  modelled. These are #180's input.
- Decision record 0001's UVLO parameters are explicitly **not** inherited by
  this facet; they are specified against facet (a)'s 5 V drive rail.
