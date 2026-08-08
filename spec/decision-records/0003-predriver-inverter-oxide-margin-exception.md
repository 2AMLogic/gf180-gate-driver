# 0003: Pre-driver-inverter oxide margin — §5's claim narrowed to a documented exception

- **Status**: Ratified
- **Date**: 2026-08-08
- **Decided by**: Builder agent, issue #13
- **Supersedes**: none. **Extends** decision record 0002 (does not reopen or
  contradict it — 0002's own "Consequences" section explicitly deferred this
  exact choice to a follow-up issue; this record is that follow-up).

## Context

Decision record 0002 (issue #7) found that `design/level_shifter.sch`'s
cascode/clamped topology (`spec/gate-driver.md` §4) is verified correct for
the problem it was chosen to solve — every thin-oxide node exposed to the
5 V/6 V drive rail (`na`/`nb`, the cascode-protected pull-down drains) stays
1.88–2.78 V across the full 60-point PVT matrix, comfortably under the
3.63 V ceiling. But a second, unrelated node — the pre-driver inverter's own
output (`inb`, gate of thin-oxide `XMNPDB`) — transiently overshoots its own
`VDD_LOGIC` rail by 20–35 mV at all 15 process×temperature points where the
logic rail sits at its own `vlogic3p63v` (+10 %) bound (evidence:
`sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`). This
leaves `spec/gate-driver.md` §5's blanket claim ("no thin-oxide node is
designed to exceed 3.63 V" even momentarily) not true as stated for this
cell, and issue #13 was filed to resolve the gap one of two ways: mitigate
the circuit and re-verify, or formally narrow the claim.

## Investigation: mitigation was attempted and rejected

Before choosing to narrow the claim, three passive mitigation shapes
suggested by issue #13 ("a small series gate resistor... or an explicit
clamp") were tried against the single worst-case point from the existing
record (`ss_125c_vlogic3p63v-vdrv5p50v`, baseline `vgate_thinox_max` =
3.66512 V, the worst of the 15 failing corners). This was exploratory,
single-corner testing to inform this decision — **not** a full-PVT run, and
not a new evidence record under `sim/README.md`'s convention (nothing here
is shipped in the design, so nothing here carries that record's
substantiation burden; contrast with the Decision below, which changes
nothing in `design/level_shifter.sch`).

| Mitigation tried | Range swept | Best result | Outcome |
|---|---|---|---|
| Series gate-isolation resistor between the pre-driver's output and `XMNPDB`'s gate (splitting the shared `inb` node into a driven side and an isolated gate side) | 100 Ω – 5000 Ω | 1000 Ω → 3.6636 V (only ~1.5 mV better than baseline) | Non-monotonic and weak: worse again above ~2 kΩ (5 kΩ → 3.6665 V, *worse* than doing nothing). The kick is not dominated by this resistance. |
| Decoupling (bypass) capacitor added at the shared `inb`/gate node | 5 fF – 5 pF | 5 pF → 3.6319 V | Monotonic but only asymptotic: even 5 pF (≈250× a typical thin-oxide gate cap at this device size, ≈25× the `sim/level-shifter-oxide-safety/testbench/`'s assumed downstream #6 pre-driver load cap) still leaves 1.9 mV of margin *missing*, while pushing `t_plh_ns` from 0.99 ns to 7.87 ns — an 8× propagation-delay increase. Numerically still inside §3's 25 ns/50 ns budget, but a component change of that magnitude to close 2 mV of a 35 mV gap is not a "small" fix by any reasonable reading of the issue's own framing. |
| Keeper resistor from the shared node to `VDD_LOGIC` (reinforcing the pull-up through the transition) | 20 Ω – 10 kΩ | 10 kΩ → 3.6637 V (functional) | Any resistance low enough to move the peak meaningfully (≤ 1 kΩ) breaks correct switching: it fights the same NMOS pull-down the inverter needs to turn `XMNPDB` off, and `t_plh`/`t_phl` measurements stop resolving (functional regression, not merely a delay cost). |

**Why passive shaping cannot close this gap, not just "these three
attempts didn't."** The existing record itself shows why: at the affected
corner, `inb` sits held at *exactly* `VDD_LOGIC` (3.63000 V, matching the
independent `mq1`–`mq4` measurements against the same rail) through the
quiescent phase immediately preceding the overshoot. Any nonzero charge
coupled onto that node from `nb`'s much larger, faster transition
(the Miller path through `XMNPDB`'s own `Cgd`) necessarily pushes the
transient peak to `VDD_LOGIC + ε` for some `ε > 0` — passive R/C shaping can
only drive `ε` toward zero asymptotically (as the 5 pF capacitor result
shows: closer, never crossing), not eliminate it, because eliminating it
requires either zero coupling capacitance (not available for a real gate
terminal next to a switching drain) or an active clamp with an essentially
zero forward-conduction onset. An active clamp is a real option in the
abstract, but it is a nontrivial addition — its own device, its own PVT
verification, and its own oxide-safety question for the clamp device
itself — disproportionate to closing a 20–35 mV (≤1 %) gap on a node that
never leaves the 3.3 V logic domain, and well past what issue #13 scoped as
"a small series gate resistor... or an explicit clamp." It is recorded here
as a legitimate, larger-scope follow-up, not ruled out permanently.

## Decision

**§5's oxide-safety claim is narrowed to the case §4 was designed for — the
domain-crossing case (thin-oxide nodes exposed to the 5 V/6 V drive rail) —
and the pre-driver inverter's own output is recorded as a distinct,
bounded, measured exception**, not folded into the general claim and not
covered by the PDK's duty-cycle TDDB overshoot allowance (`spec/gate-driver.md`
§2.3, explicitly declined — this record does not invoke it either).

`spec/gate-driver.md` §5's "Overvoltage / gate-oxide protection" row is
updated from an unqualified "no thin-oxide node is designed to exceed
3.63 V" to state:

- The domain-crossing claim (every thin-oxide node the cascode/clamped
  topology in §4 protects from the 5 V/6 V drive rail) holds, verified,
  across the full PVT matrix (decision record 0002).
- One documented, bounded exception exists: the pre-driver inverter's own
  output (`inb`, gate of thin-oxide `XMNPDB`, internal to the 3.3 V logic
  domain and never touching the drive rail) transiently overshoots its own
  `VDD_LOGIC` rail by 20–35 mV, **only** at the `vlogic3p63v` (+10 %) PVT
  corner (never at `vlogic2p97v`/`vlogic3p30v`, max there 3.336 V), measured
  worst case 3.65019 V (`ff_-40c`) to 3.66512 V (`ss_125c`) across all 15
  affected process×temperature points —
  `sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`.

`design/level_shifter.sch` is **unchanged** by this record — the cascode
clamp remains verified correct (decision record 0002) and is not touched;
no new `sim/level-shifter-oxide-safety/` evidence record is required (per
issue #13's own Test Plan: "If option 2... is chosen instead: no new PVT
run is required") since nothing in the design or its evidence trail changes.

## Alternatives considered

- **Mitigate with a series gate resistor or decoupling capacitor (issue
  #13's option 1)** — investigated in detail above; rejected. No passive
  shaping tried closes the gap without either remaining strictly inside the
  fail region (resistor) or requiring component values well outside "small"
  while still not fully clearing the ceiling (capacitor), or breaking
  function outright (keeper).
- **Add an active clamp device** — considered; deferred, not rejected
  outright. A real option, but disproportionate in verification burden (its
  own PVT sweep, its own oxide-safety question) to a ≤1 % margin on a node
  that never leaves the 3.3 V domain. Left as an explicit, larger-scope
  follow-up if a future block reusing this pattern needs a tighter margin
  than this record documents.
- **Relax the 3.63 V bound, or invoke the PDK's TDDB duty-cycle overshoot
  allowance** — explicitly forbidden by issue #13 and by `CLAUDE.md`
  ("agents do not relax the ratified spec to make results pass"); not
  considered further.
- **Leave §5's claim as currently worded (do nothing)** — rejected: the
  claim is false as currently stated for this cell (decision record 0002's
  own finding), which is the exact gap issue #13 exists to close.

## Consequences

- `spec/gate-driver.md` §5's "Overvoltage / gate-oxide protection" row is
  updated to the narrowed, documented-exception wording above. The 3.63 V
  ceiling itself (§2.3) is unchanged; no PDK allowance is invoked.
- `design/level_shifter.sch`, `design/netlist/level_shifter.spice`, and
  `sim/level-shifter-oxide-safety/records/20260808-052057-5fbdb2d.md`
  (decision record 0002's evidence) are unchanged and remain the
  authoritative, sole evidence trail for this cell — this record adds no
  new `sim/` record, per issue #13's Test Plan for the option chosen here.
- **Carried forward from decision record 0002**: any future block reusing
  this pre-driver-inverter pattern at a rail already parked at its own
  absolute ceiling should expect the same class of small transient
  overshoot and budget margin for it (or add the active-clamp follow-up
  noted above), rather than assume a thin-oxide gate is safe merely because
  it never numerically exceeds its own nominal supply value.
- If a future revision of this cell (or a reused instance in another block)
  needs the pre-driver-inverter node to also clear 3.63 V with margin — not
  just document why it currently doesn't — that is new design work (most
  plausibly the active-clamp option above) requiring its own decision
  record and full-PVT evidence record, not a silent edit to this one.
