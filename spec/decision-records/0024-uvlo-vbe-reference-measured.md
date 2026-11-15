# 0024: UVLO `Vbe`/`dVbe` reference — measured, clears all 15 corners; adoption still gated

- **Status**: proposed
- **Date**: 2026-11-14
- **Decided by**: Builder agent, issue #457 (draft — **awaiting operator ratification**)
- **Extends**: decision record 0023 (UVLO stacked-diode reference), whose
  Consequences section asks for exactly this follow-up: "A follow-up should
  evaluate a reference with weaker process/temperature dependence before any
  schematic change is made." **Does not reopen or amend** 0001, 0018 or 0023,
  **does not close 0018 Finding 2**, does not declare T1 item 5 met, and
  **changes no bound** in `spec/gate-driver.md` or decision record 0001.

## Context

T1 item 5 is unmet because the UVLO trip spread is wide (0018 Finding 1:
falling trip 2.23-4.74 V against the ratified 3.3-3.9 V window; 4 of 15
corners pass), and 0018 Finding 2 shows `ss`/-40 C stays locked out at the
legitimate 4.50 V low-line rail. Record 0023 measured the fix 0018 named — a
3-diode `Vgs` stack — and found the spread unchanged (2 of 15), because the
trip point scales with the stack's `N x Vgs`.

Issue #457 measures the class of reference 0023's consequence asks for: one
whose reference voltage does not derive from `Vgs`. Evidence:
`sim/uvlo-reference-study/` (candidate netlist `uvlo_bandgap_ref.spice`, the
`klt sim` request, the committed 15-corner envelope
`envelopes/20261114-38154c7-klt-sim-uvlo-bandgap-ref-trip.json`, and a README
section with the per-corner table, the startup measurement and the stated
limitations). Same ramp, same 5 process x 3 temperature points and the same
ratified bounds as 0018 and 0023.

## Decision

**No design change is adopted by this record.** It records a positive
measurement and the conditions that still gate adoption.

Measured, 15 corners, schematic-only candidate — a `Vbe`/`dVbe` (CTAT + PTAT)
reference on `pnp_05p00x05p00` substrate PNPs with a `pfet_06v0` mirror and an
`nfet_06v0` loop amplifier, with 0018's comparator, buffer and `MPD` copied
device-for-device:

- **15 of 15** corners pass both windows (0023: 2 of 15; 0018 baseline: 4 of
  15). 0 fail, **0 error** — including `fs/125C`, which errored for the 3-diode
  candidate.
- Falling-trip spread **3.550-3.641 V (91 mV)**, against 2.33-4.80 V for 0023
  and 2.23-4.74 V for the baseline.
- Worst-case rising trip **3.988 V** (`ss/125C`) against the 4.50 V low-line
  floor: **clears it** by 0.512 V. No corner exceeds the floor. This is the
  0018 Finding 2 failure, and no prior candidate cleared it.
- Hysteresis 0.284-0.348 V at every corner (0023: 0.256-0.848 V).
- DC current from `VDD_DRV` at 5 V, tt, 27 C: **34.8 uA** (single local check),
  against 0023's 34.5 uA and the 0018 baseline's 17.95 uA (measured for the
  first time in this study). Two thirds of the 34.8 uA is 0018's *copied*
  comparator tail, whose gate now sits on the core's bias node; the
  `Vbe`/`dVbe` reference and its amplifier cost 7.9 uA of it.

So the mechanism 0023 identified as the cause of the spread is confirmed to be
the cause: replacing it, with the rest of the cell held fixed, collapses the
spread by a factor of 27 and clears the floor.

**Adoption into `design/uvlo.sch` is NOT ratified by this record**, and is
gated on all four of:

1. A mismatch / Monte Carlo result. The runs above are nominal corners
   (`sw_stat_global=0`, `sw_stat_mismatch=0`). The loop amplifier's input-pair
   offset is multiplied by `Rsa/Rp = 10.19` on its way into `Vref`, so ~10 mV of
   random offset is ~100 mV of reference error, i.e. ~8 % of the trip point.
   This is the measurement most likely to overturn the result above.
2. A re-measurement with PDK resistor devices (`ppolyf_u`) and the `res_*`
   corner sections live. Both candidates and `design/netlist/uvlo.spice` use
   ideal `R` elements, so resistor process spread is not exercised, and this
   candidate's PTAT gain is a resistor *ratio*.
3. A signoff plan for the startup path. A `Vbe`/`dVbe` core has a degenerate
   zero-current state; measured at 27 C with the startup kicker deleted and the
   core initialised dead, the core stays dead and `lockout` stays **low** — the
   UVLO releases `OUT` at 2 V and at 3 V. The failure direction is the unsafe
   one, which the `Vgs`-stack references do not have.
4. A layout cost estimate for the PNPs, the 3.2 pF MIM compensation capacitor
   and the 50 MOhm feedback resistor.

## Alternatives considered

- **Take the sibling `2AMLogic/gf180-bandgap` core by reference** — rejected,
  and this answers #457's AC1 research question. All 42 of its core MOS devices
  are `*_03v3` and its ratified DR-0002 scopes it to 3.3 V +/-10 %, against
  `VDD_DRV`'s 4.5/5.0/5.5 V here. Its reference *mechanism* and device choice
  (`pnp_05p00x05p00`) are reusable and were reused; its cell is not.
- **Power a 3.3 V-flavour reference from `VDD_LOGIC`** — rejected for this
  study: `uvlo` has exactly three ports (`.subckt uvlo VDD_DRV OUT GND_DRV`),
  so this needs a new port on `design/uvlo.sch` / `uvlo.sym`, which #457 puts
  out of scope.
- **Re-size the 3-diode stack (other `N` / `Rref` / divider point)** —
  rejected: 0023 measured the mechanism, not only one sizing.
- **Retune the existing divider** — rejected: 0018 already shows this cannot
  fix the spread.
- **Adopt this candidate now and amend `design/uvlo.sch`** — rejected: the four
  gates above are unmeasured, and #457 is scoped to evidence only.

## Consequences

- 0018 Finding 2 and T1 item 5 **remain open**. Nothing in `design/`,
  `layout/`, `verification/signoff/` or `spec/gate-driver.md` changes; items
  1-4 and 11 are not re-opened. What changes is that the open gap now has a
  measured candidate mechanism behind it instead of an untested hypothesis.
- The next UVLO work is a mismatch/Monte Carlo run on this candidate, not
  another topology search. If gate 1 fails, the reference needs either a
  lower `Rsa/Rp` with a different compensation scheme, or offset cancellation
  in the loop amplifier — and the negative result should be recorded the same
  way 0023 was.
- Adopting this reference would make the UVLO's **startup path** a signoff
  item in its own right; the block does not have one today, because neither
  the baseline nor the 0023 candidate has a degenerate operating state.
- This block now has a measured `pnp_05p00x05p00` reference on the 5 V rail.
  Per CLAUDE.md ("Not a CAN transceiver"), that is a data point for what the
  gf180mcu HV devices can be built on, but it says nothing about device
  withstand voltage, which remains unmeasured.
- Two harness limitations recorded in
  `sim/uvlo-reference-study/README.md` apply to this record's numbers and to
  0023's: `fs` and `sf` select `bjt_typical`, so BJT process spread is
  exercised at 9 of the 15 points and not at 6; and the measured hysteresis
  includes a ramp-rate-dependent component from probing `lockout`, which
  drives `MPD`'s ~15 pF gate, so no hysteresis number from this harness is a
  static property. A `klt` coverage-report false positive on the 6 V device
  flavour is filed as `2AMLogic/klayout-tools#5663`; it does not affect these
  results, which do skew the 6 V devices.
