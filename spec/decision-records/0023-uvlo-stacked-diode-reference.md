# 0023: UVLO stacked-diode reference — measured, does not support adoption as sized

- **Status**: proposed
- **Date**: 2026-11-06
- **Decided by**: Builder agent, issue #412 (draft — **awaiting operator ratification**)
- **Extends**: decision record 0018 (UVLO comparator PVT measurement), whose
  "Why no design fix is undertaken here" section names this fix. **Does not
  reopen or amend** 0001 or 0018, **does not close 0018 Finding 2**, and
  **changes no bound** in `spec/gate-driver.md` or decision record 0001.

## Context

T1 item 5 is unmet because the UVLO trip spread is wide (0018 Finding 1:
falling trip 2.23-4.74 V against 3.3-3.9 V; 4 of 15 corners pass). 0018 named a
reference built from a multi-diode stack, giving a divider gain near unity
instead of about 5x, as the fix. Issue #412 measures that on a schematic-only
candidate. Evidence: `sim/uvlo-reference-study/` (candidate netlist,
`klt sim` request, committed 15-corner envelope, README with per-corner table).

## Decision

No design change is adopted by this record. It reports the measurement and
recommends **against** adopting the 3-diode stacked reference as sized:

- 15 corners, same ramp and bounds as 0018: **2 of 15** pass both windows
  (baseline 4 of 15); 3 of 15 fall in 3.3-3.9 V falling; 3 of 15 in 3.6-4.2 V
  rising; 1 corner (`fs/125C`) errors.
- Falling-trip spread 2.33-4.80 V (baseline 2.23-4.74 V): unchanged.
- Worst-case rising trip **5.110 V** (`ss/-40C`) against the 4.50 V floor: not
  met.
- DC current from `VDD_DRV` at 5 V, tt, 27 C: 34.5 uA (single local check).

The 0018 hypothesis that divider gain is the cause of the spread is therefore
not supported at this sizing: the trip point scales with the stack's
N x Vgs, which carries the process and temperature variation (plus body effect
on the upper devices) through unchanged.

## Alternatives considered

- **Other N / `Rref` / divider points** — only tt/27 C was used for sizing
  (N = 4 never crosses the divider; N = 3 was used), so a better point is not
  excluded, but the measured spread mechanism makes a large improvement from
  re-sizing alone unlikely.
- **A reference that does not track Vgs (bandgap-type)** — outside this
  study; it belongs in its own decision record.
- **Retuning the existing divider** — 0018 already shows this cannot fix the
  spread.

## Consequences

- 0018 Finding 2 and T1 item 5 remain open. Nothing in `design/`, `layout/` or
  `verification/signoff/` changes; items 1-4 and 11 are not re-opened.
- A follow-up should evaluate a reference with weaker process/temperature
  dependence before any schematic change is made.
- The `fs` corners show 0.8 V hysteresis and one ngspice error at the
  multi-Vgs common-mode level; these are results of this candidate, not
  investigated further.
