# 0011: Low-side power switch — flyback handling is a dedicated on-die `diode_pd2nw_06v0` clamp

- **Status**: Ratified
- **Date**: 2026-08-18
- **Decided by**: Builder agent, issue #179

## Context

`spec/low-side-power-switch.md` (ratified by
[decision record 0010](0010-low-side-power-switch-spec-ronw-em-and-protection.md))
specifies an on-die low-side `nfet_06v0` switching ~1 A from a single Li-ion
cell. With the load between the cell's positive terminal and the switch
drain, turning the switch off against an inductive load drives the drain
**up**, above the cell rail — and the switch's own drain-to-bulk junction is
reverse-biased in that direction, so **the low-side NMOS has no usable body
diode for this transition**. A separate recirculation element from the drain
node back to the cell rail is mandatory; without one the drain rises until
something breaks down, which for a device sized per that document's §2.2
means the switch itself.

[Decision record 0008](0008-low-side-power-nmos-facet-scope-and-ronw-baseline.md)
named the three candidate elements (body diode / junction diode /
synchronous PMOS) and deferred choosing between them to issue #179. This
record chooses, on measured evidence rather than on the usual textbook
ordering.

Evidence: `sim/low-side-power-switch/records/20260818-011754-03afe04.md`,
full 15-point process × temperature grid.

## Decision

**A dedicated `diode_pd2nw_06v0` junction diode from the switch drain to the
cell rail**, drawn at **≥ 10⁴ µm² of junction area per ampere** of
recirculation current, carried on its own EM budget per
`spec/low-side-power-switch.md` §3 — the flyback path carries the same 1 A
the switch does, so it gets the same drawn-width and via allowance, not a
token strap.

Measured behaviour of that clamp, at the 10⁴ µm² reference area:

| forward current | `tt`, −40 °C | `tt`, 27 °C | `tt`, 125 °C | full grid min .. max |
|---|---|---|---|---|
| 0.1 A | 0.9624 V | 0.8816 V | 0.7566 V | 0.7516 .. 0.9658 V |
| 0.3 A | 0.9952 V | 0.9230 V | 0.8105 V | 0.8050 .. 0.9990 V |
| 1.0 A | 1.0367 V | 0.9742 V | 0.8759 V | 0.8687 .. 1.0418 V |

So the drain is clamped at cell voltage + 0.87…1.04 V, and the clamp
dissipates ≈ 0.87…1.04 W while recirculating 1 A.

## Alternatives considered

- **The body diode of an unpowered high-side `pfet_06v0` placed
  drain-to-cell-rail** — rejected, but *not* on performance. A PMOS's
  drain-to-nwell diode and `diode_pd2nw_06v0` are the **same P+/N-well
  junction**, which is exactly why one sweep in the record above measures
  both options; they cannot differ in forward drop at equal area. They
  differ in whether the conducting area is a designed parameter or a side
  effect of a channel width chosen for something else. Rejected because
  (i) implicit is worse than explicit for a path that has to carry the full
  channel current and be checked against §3's EM budget, and (ii) with the
  synchronous option below rejected, there is no high-side PMOS in the
  design for a body diode to belong to. Drawing the junction explicitly
  costs nothing.
- **A synchronous high-side `pfet_06v0`, actively gate-driven on during the
  off interval** — rejected on measured area cost plus scope. It is the only
  option that can beat a junction drop, and the measured `pfet_06v0` `Ron·W`
  at cell-referenced `|Vgs|` prices it: 5.9721…15.2279 Ω·mm at 3.6 V, so a
  PMOS that merely *matches* the diode's ~0.9 V at 1 A still costs
  15.2279/0.9 ≈ **17 mm** of width worst case, and one that gives a
  worthwhile 0.1 V costs ≈ **152 mm** — over 3× the entire low-side switch
  (45.7 mm at the same budget). On top of the area it requires a gate drive
  referenced to the cell rail above a switching node — the floating,
  level-shifted high-side drive problem `spec/low-side-power-switch.md` §1
  excludes from this facet and facet (a) exists to study — plus dead-time
  control between the two devices, which `gate-driver.md` §5 deferred for
  the same "one channel, nothing to sequence against" reason. Three
  subsystems for ~0.8 W.
- **Size the junction diode much larger to cut the drop** — rejected as
  ineffective, and this is a measured result rather than an assumption. The
  same record shows 0.9742 V at 1 A, 0.9230 V at 0.3 A and 0.8816 V at
  0.1 A through the *same* area, i.e. a 10× larger diode buys only ~93 mV,
  because at these currents the junction is far above the PDK model's own
  high-injection knee (`ik` = 253800, ≈ 2.5 mA at the reference area). There
  is no area at which an on-die P+/N-well clamp becomes a low-drop element;
  ≥ 10⁴ µm²/A is chosen as the point past which further area stops paying.
- **No on-die clamp; require an external freewheel diode across the load** —
  rejected as the *sole* provision. An external diode is the right answer
  for a genuinely energetic inductive load and is not forbidden by this
  record, but relying on it alone leaves the die unprotected against a
  missing, open or slow external part, in a facet whose defining hazard is
  that the switch is on-die. The on-die clamp is ratified as the floor, not
  as a claim that external freewheeling is unnecessary.

## Consequences

- The switch drain is clamped at **≈ 6.04 V worst case** (fresh 5.0 V cell +
  the 1.0418 V grid-worst forward drop). That is *at* the 6.0 V thick-oxide
  DC ceiling of `gate-driver.md` §2.3 — the tightest margin anywhere in this
  facet. It is a drain/junction bias rather than a gate-oxide bias, so
  §2.3's ceiling is not the governing rule; but **the governing rule has not
  been established**, and that is recorded as an open item
  (`spec/low-side-power-switch.md` §6, item 4) rather than waved through.
  Anyone tempted to relax it should note `gate-driver.md`'s own history of
  narrow ceiling exceptions (decision records 0003, 0005, 0006, 0007).
- ≈ 0.9 W of recirculation dissipation lands on the same die as a
  0.1–0.2 W switch and a 150 °C thermal shutdown. The duty cycle at which
  that becomes the dominant thermal term is a system-level question this
  record does not settle, and it is now a first-class input to
  [#180](https://github.com/2AMLogic/gf180-gate-driver/issues/180)'s
  test-structure plan.
- The clamp is reverse-biased at the cell voltage whenever the switch is on.
  `diode_pd2nw_06v0`'s model gives `bv` = 10.5 V, so 5.0 V reverse is well
  inside breakdown — but its reverse **leakage** at that bias and 125 °C is
  **unmeasured** and adds directly to the channel's on-state current
  (`spec/low-side-power-switch.md` §6, item 3). This record's sweep is
  forward-bias only.
- Dead-time / shoot-through control stays deferred, and this record is the
  reason it can be: with no actively driven high-side device there is
  nothing to sequence against. If a future increment revisits the
  synchronous-PMOS option — most plausibly because it already carries a
  high-side drive for other reasons — that deferral has to be revisited in
  the same breath, and this record's diode becomes that PMOS's body diode,
  at which point options (a) and the chosen option converge.
- No `sim/` record is edited or superseded. The diode measurement is new
  evidence in a new experiment directory; nothing under `sim/device-mv-fet/`
  changes.
