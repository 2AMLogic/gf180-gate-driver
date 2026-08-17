# 0008: Low-side on-die power-NMOS characterization facet — scope decision and Ron·W baseline

- **Status**: Ratified (scope decision + baseline data only — see "Consequences" for what is explicitly deferred)
- **Date**: 2026-08-17
- **Decided by**: Builder agent, issue #178

## Context

Issue #178 identifies a framing gap: this repo's spec (`gate-driver.md` §1)
scopes a **high-voltage gate driver** — an external-FET pattern where the
switch itself lives off-die and the driver's job is to level-shift and
source/sink gate charge into it. A distinct, large class of mature-node
power questions is not that pattern at all: **direct low-side drive of a
small load (motor/solenoid/LED) from a single Li-ion cell**, where the
switch is an **on-die** thick-oxide 6 V NMOS, `Vgs` is the cell's own
3.6–5 V range (no level-shifting problem, no HV rail), and the deliverables
are different — `Ron·W` vs. `Vgs`/temperature, EM/bonding current limits per
channel, per-channel overcurrent-protection (OCP) + thermal-shutdown
structures, and flyback handling (body diode / junction diode / synchronous
PMOS) at ~5 V drain excursions.

The issue's own data point (ngspice on the PDK's shipped models, typical
corner, 2026-08-17): `nmos_6p0` at `Vgs` 5 V ≈ 2.25 Ω·mm; at `Vgs` 3.6 V
≈ 2.83 Ω·mm; at 125 °C ≈ 3.13 Ω·mm; `pmos_6p0` ≈ 6.5 Ω·mm. These are cited
as an existing spot-check by the issue filer, not sourced to a `sim/`
record in this repo — this decision record cross-checks them against actual
recorded evidence below rather than taking them at face value.

**This repo already has directly reusable evidence.** `sim/device-mv-fet`
(issue #5, record `20260808-023237-61e0c25`) already characterizes
`nfet_06v0`/`pfet_06v0` — the exact devices this facet needs — across the
full 15-point process×temperature PVT grid (`typical`/`ff`/`ss`/`fs`/`sf` ×
−40/27/125 °C), including an on-resistance table at three `Vgs` levels
(75/90/100 % of each family's Idsat bias). That record was produced to
substantiate `gate-driver.md` §2.5's device-flavor choice, not this facet —
but the raw per-corner logs it left behind (`sim/device-mv-fet/corners/
20260808-023237-61e0c25/*.log`, themselves part of that same append-only
record) already contain everything needed for a `Ron·W` baseline at no new
simulation cost. This record derives that baseline from those logs; §
"Ron·W baseline" below documents the extraction so it is reproducible from
the existing evidence.

## Decision

**1. Scope: the low-side on-die power-NMOS facet is in scope in this repo,
not a sibling row.** The device-characterization work this facet needs
(`nfet_06v0`/`pfet_06v0` `Ron`, `Vt`, `Ioff`, thermal behavior) is already
being produced here for the HV gate driver's output stage, and is exactly
the shared substrate CLAUDE.md's "the medium-voltage devices are the point"
framing is about. Forking the facet to a sibling repo would duplicate that
device-characterization investment for no benefit and would split one
device's evidence trail across two repos. `README.md` is updated to state
both facets explicitly:

- **(a) HV gate driver** — external-FET, 5–6 V drive rail, level-shifted
  from 3.3 V logic. Ratified spec: `spec/gate-driver.md`.
- **(b) Low-side on-die power-NMOS facet** (new, this record) — direct
  low-side drive of a small load from a single Li-ion cell at logic-level
  `Vgs` (3.6–5 V), on-die thick-oxide `nfet_06v0` switch, no HV rail, no
  level shifter. Spec content is a new, separate document
  (`spec/low-side-power-switch.md`, not yet written — see "Consequences"),
  not folded into `gate-driver.md`, since it is a different device use with
  different deliverables (per-channel OCP/thermal, EM/bonding, flyback),
  not an amendment to the HV driver's ratified decisions.

**2. Ron·W baseline (ratified now, derived from already-recorded evidence —
no new simulation run).** `sim/device-mv-fet/corners/20260808-023237-61e0c25/`
holds Id(Vds) output-characteristic sweeps for `nfet_06v0` (`n06`, W=10 µm)
and `pfet_06v0` (`p06`, W=10 µm) at `Vgs` = 75/90/100 % of `Vidsat` = 6.0 V,
i.e. 4.5 V / 5.4 V / 6.0 V, across all 15 process×temperature points. Ron is
that record's own near-origin-chord extraction (`Vds` ≈ 1 % of `vmax`);
this record only re-expresses it as `Ron·W` (Ω·mm) instead of bare Ω, and
tabulates the `typical`-corner temperature dependence and the full-grid
process-corner spread the source record's own tables collapsed into a
single min/max column.

### `nfet_06v0` (n06), W = 10 µm

| `Vgs` | `typical`, −40 °C | `typical`, 27 °C | `typical`, 125 °C | full grid (5 process × 3 temp) min .. max |
|---|---|---|---|---|
| 4.5 V (75 % Vidsat) | 1.8155 Ω·mm | 2.3658 Ω·mm | 3.2708 Ω·mm | 1.6198 .. 3.8618 Ω·mm |
| 5.4 V (90 % Vidsat) | 1.6296 Ω·mm | 2.1400 Ω·mm | 2.9825 Ω·mm | 1.4742 .. 3.4699 Ω·mm |
| 6.0 V (100 % Vidsat) | 1.5518 Ω·mm | 2.0470 Ω·mm | 2.8649 Ω·mm | 1.4147 .. 3.3054 Ω·mm |

### `pfet_06v0` (p06), W = 10 µm

| `Vgs` | `typical`, −40 °C | `typical`, 27 °C | `typical`, 125 °C | full grid (5 process × 3 temp) min .. max |
|---|---|---|---|---|
| 4.5 V (75 % Vidsat) | 5.9500 Ω·mm | 7.7171 Ω·mm | 10.0922 Ω·mm | 5.0967 .. 12.3316 Ω·mm |
| 5.4 V (90 % Vidsat) | 5.2677 Ω·mm | 6.7738 Ω·mm | 8.7242 Ω·mm | 4.5707 .. 10.5469 Ω·mm |
| 6.0 V (100 % Vidsat) | 4.9510 Ω·mm | 6.3273 Ω·mm | 8.0551 Ω·mm | 4.3239 .. 9.6861 Ω·mm |

**Cross-check against the issue's cited spot-check**: at `typical`/27 °C,
interpolating `n06` between the 4.5 V and 5.4 V points above puts `Ron·W` at
`Vgs` = 5 V at roughly 2.2 Ω·mm, and the 4.5 V point itself (2.3658 Ω·mm) is
the closest measured point to the issue's cited 3.6 V figure (2.83 Ω·mm) —
both broadly consistent with the issue's cited 2.25 Ω·mm / 2.83 Ω·mm
(same order of magnitude, same direction of `Vgs` dependence), but not an
exact match, because **this record's measured points (4.5/5.4/6.0 V) do not
land on the issue's cited points (3.6/5.0 V)** — see the gap noted in
"Consequences" below. `pfet_06v0`'s typical/27 °C/6.0 V point (6.3273 Ω·mm)
is close to the issue's cited 6.5 Ω·mm pmos figure. The temperature
dependence direction matches too: `typical`/125 °C `n06`/100 % is
2.8649 Ω·mm, close to the issue's cited "at 125 °C ≈ 3.13 Ω·mm" (again not
an exact match for the same reason — different `Vgs`, and the issue's
125 °C figure does not state which `Vgs` it was taken at).

## Alternatives considered

- **Recommend the low-side facet live in a sibling repo** — the issue's own
  first bullet raised this as an option. Rejected: the device
  characterization is shared (§ "Decision" above), and this repo already
  carries the `sim/device-mv-fet` evidence base the facet needs; splitting
  it would duplicate work already produced here for no benefit, and would
  fragment one device's evidence trail (`nfet_06v0`/`pfet_06v0`) across two
  repos' `sim/` directories, which is exactly what the append-only-evidence
  convention in `sim/README.md` is trying to keep contiguous per device.
- **Resolve all four of the issue's suggested acceptance-criteria items in
  this one record** — rejected as oversized for one decision record. This
  repo's own precedent (decision records 0002 through 0007) is one decision
  per record; the issue's remaining three items (full spec content
  including EM/current-density guidance and OCP/thermal-sense structures
  and flyback trade, a shared-shuttle test-structure plan, and multi-channel
  bond/ground/substrate-noise guidance) are each their own decision with
  their own evidence requirements and are better served as separate,
  independently reviewable records — see "Consequences" for the follow-on
  issues this record files for them.
- **Run a new sim/ campaign at the issue's exact cited `Vgs` points (3.6 V,
  5.0 V) before ratifying any baseline** — rejected for *this* record:
  the existing `sim/device-mv-fet` evidence already gives a same-order-of-
  magnitude, same-direction baseline (§ "Decision" above) sufficient to
  ratify the scope decision and hand off a starting point; a purpose-built
  sweep at the cell-referenced `Vgs` points the facet actually cares about
  (3.6/4.2/5.0 V, not the PDK elec-spec table's 75/90/100 %-of-Idsat
  convention `sim/device-mv-fet` uses) is real, separate work — filed as a
  follow-on issue rather than done inline here, to keep this record scoped
  to the framing decision it is actually deciding.

## Consequences

- `README.md` gains a paragraph stating both facets are in scope in this
  repo (§ "Decision" above).
- `spec/gate-driver.md` is **unchanged** — its scope (§1: HV, low-side-only,
  external-FET driver) is not amended by this record; the new facet gets
  its own spec document instead of being squeezed into the HV driver's
  ratified decisions.
- `spec/README.md` gains an index entry for this record.
- This record ratifies a **scope decision and a baseline data point**, not
  the full low-side facet spec. The remaining pieces of issue #178's
  suggested acceptance criteria are explicitly deferred to follow-on issues
  rather than silently dropped:
  - A purpose-built `sim/` campaign at the facet's actual `Vgs` operating
    points (3.6/4.2/5.0 V, single-cell range) and a full
    `spec/low-side-power-switch.md` covering `Ron·W` there, EM/current-
    density guidance for the tm11k/tm30k top-metal options, and
    per-channel OCP-comparator + thermal-sense reference structures and
    flyback options (body diode / junction diode / synchronous PMOS) with
    their area/loss trade.
  - A test-structure plan sized for a shared shuttle slot (e.g. wafer.space
    quarter slot, next submission window per the issue), covering one or
    two channels plus protection plus three flyback variants.
  - Multi-channel guidance: what N channels of ~1 A low-side drive imply
    for bond wires, ground return, and substrate noise into co-integrated
    analog.
  Each is filed as its own issue referencing this record, per this record's
  "Alternatives considered" note on why they are not resolved inline here.
- No existing `sim/` record is edited or superseded — the `Ron·W` table
  above is a re-expression of `sim/device-mv-fet/records/
  20260808-023237-61e0c25.md`'s already-recorded on-resistance data
  (append-only rule preserved; nothing in `sim/device-mv-fet/` changes).
