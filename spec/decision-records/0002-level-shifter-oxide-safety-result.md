# 0002: Level-shifter oxide-safety verification result — §4's central claim fails a narrower, unaddressed case

- **Status**: Ratified
- **Date**: 2026-08-08
- **Decided by**: Builder agent, issue #7

## Context

`spec/gate-driver.md` §4 chose the cascode/clamped level-shifter topology
specifically to satisfy §2.3's 3.63 V thin-oxide DC gate-node ceiling "by
construction," and §5 leans on the same claim to declare overvoltage
protection handled structurally: "no thin-oxide node is designed to exceed
3.63 V" even momentarily. Issue #7 required a transient testbench across the
full PVT matrix to substantiate or refute that claim before it could stand as
verified rather than asserted.

`design/level_shifter.sch` (the schematic capturing §4's topology) and
`sim/level-shifter-oxide-safety/` (the testbench and evidence trail) were
built for this issue. The full mandated PVT matrix (5 process corners × 3
temperatures × the tied two-rail supply grid, 60 points) ran clean —
`sim/level-shifter-oxide-safety/records/20260808-051839-f3ec3e2.md` — no
convergence failures, no simulator errors, only two ngspice convergence aids
added to the testbench manifest (`gmin=1e-9`, `method=gear` — standard
robustness options for a circuit containing a fast positive-feedback latch
transition; see that record's Environment section and
`sim/level-shifter-oxide-safety/testbench/tb.json`).

## Decision

**The record's answer is a qualified fail, not a clean pass.** Two distinct
claims live inside §4/§5's language, and the evidence splits them:

1. **The cascode clamp itself works, robustly, across the whole matrix.**
   `vna_peak`/`vnb_peak` (the thin-oxide pull-down drain nodes the cascode
   devices are supposed to protect from the drive rail) stay between 1.88 V
   and 2.78 V at every one of the 60 points — comfortably under 3.63 V, and
   tracking `VDD_LOGIC` (not the drive rail) exactly as the cascode-bias
   derivation in `design/level-shifter-partition.md` predicts. §4's
   topology decision, evaluated on the domain-crossing problem it was
   chosen to solve, is verified correct.
2. **A separate, domain-internal node exceeds the ceiling at every corner
   where the logic rail sits at its own +10 % bound.** `vgate_thinox_max`
   (the worst of six thin-oxide gate-to-any-node measurements, including the
   pre-driver inverter's own output swing on its own 3.3 V rail) FAILS the
   3.63 V check at all 15 `vlogic3p63v` points — every process corner ×
   temperature combination, 3.65019 V to 3.66512 V, a consistent 20–35 mV
   excursion. It PASSES cleanly at every `vlogic2p97v` and `vlogic3p30v`
   point (max 3.33579 V). The excursion is a small transient overshoot on
   the pre-driver inverter's own output node above its own supply rail —
   plausibly a gate-drain (Miller) charge-injection kick from the pull-down
   transistors' drain transition coupling back onto their gate — and it is
   entirely internal to the 3.3 V logic domain. It has nothing to do with
   the drive rail, the cascode devices, or the domain crossing §4's decision
   record addresses. **No thin-oxide-to-thick-oxide clamp can fix it**,
   because the offending node never touches a thick-oxide device.

**No change to `spec/gate-driver.md`.** §4's topology decision is not
reversed by this finding — it remains the correct answer to the problem it
was chosen for, and the record above establishes exactly that with evidence.
The unqualified sentence in §5 ("no thin-oxide node is designed to exceed
3.63 V") is not yet true as stated; per this issue's own acceptance criteria,
that gap is recorded here rather than the bound being relaxed, the
measurement being narrowed, or the PDK's duty-cycle TDDB overshoot allowance
(§2.3, explicitly declined) being invoked to wave it through.

## Alternatives considered

- **Widen the cascode clamp's scope to cover the pre-driver inverter too** —
  rejected for this record: it would require a design change (e.g., a series
  gate resistor or a small clamp on `in`/`inb`) that issue #7 did not scope
  and that has not been verified. Recorded as follow-up work, not decided
  here.
- **Relax the 3.63 V bound, or invoke the PDK's TDDB duty-cycle overshoot
  allowance** — explicitly rejected. §2.3 already declines to rely on that
  allowance, and this issue's acceptance criteria forbid it as a way to make
  the result pass. The margin here (20–35 mV, ~1 %) is exactly the kind of
  "brief excursion" §2.3 describes the allowance as covering *if* this
  design chose to rely on it — it deliberately does not.
- **Treat the small margin as simulation noise and pass anyway** — rejected.
  The excursion is consistent in sign and magnitude across all 15 process ×
  temperature combinations at the affected supply point (never at the other
  two), which is the signature of a real, repeatable transient mechanism,
  not numerical noise. A single point exceeding the bound would warrant more
  scrutiny before concluding a real effect; fifteen-for-fifteen, with a
  monotonic corner-driven trend (worst at `ss_125c`, best at `ff_-40c`,
  consistent with device-speed intuition), does not.

## Consequences

- `design/level_shifter.sch`, `design/level_shifter.sym`,
  `design/netlist/level_shifter.spice`, and
  `design/level-shifter-partition.md` land as issue #7's deliverables. The
  cascode/clamped topology and its DNWELL partition are correct and are not
  blocked by this finding.
- The oxide-safety claim in `spec/gate-driver.md` §5 ("no thin-oxide node is
  designed to exceed 3.63 V") is **not yet substantiated** for the pre-driver
  inverter's own output node at the logic rail's +10 % corner. A follow-up
  issue is required to either add a mitigation (e.g., a small series gate
  resistor or an explicit clamp on the pre-driver output) and re-verify, or
  to formally narrow §5's claim to the domain-crossing case it was actually
  designed for — that decision is for the follow-up issue, not this record.
- Any future block reusing this pre-driver-inverter pattern at a rail
  already parked at its own absolute ceiling should expect the same class of
  small transient overshoot and budget margin for it, or verify it away,
  rather than assume a thin-oxide gate is safe merely because it never
  numerically exceeds its own nominal supply value.
- This record does not change `sim/level-shifter-oxide-safety/`'s use as
  ongoing evidence: a mitigation attempt gets its own new record-id via
  `--supersedes 20260808-051839-f3ec3e2`, per the append-only convention in
  `sim/README.md`.
