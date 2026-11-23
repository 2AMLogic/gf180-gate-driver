# 0026: UVLO `Vbe`/`dVbe` reference — startup path verified and layout cost estimated (0024 gates 3 and 4)

- **Status**: proposed
- **Date**: 2026-11-21
- **Decided by**: Builder agent, issue #556 (draft — **awaiting operator
  ratification**)
- **Extends**: decision record 0024 (UVLO `Vbe`/`dVbe` reference, measured),
  closing its adoption gates 3 and 4. **Does not reopen or amend** 0001,
  0018, 0023 or 0024, does not ratify 0024, **does not adopt the reference
  into `design/uvlo.sch`**, and **changes no bound** in `spec/gate-driver.md`
  or decision record 0001. Gate 1 (mismatch) and gate 2 (PDK resistors)
  belong to the sibling issue #555 / record 0025 (PR #564, open at the time
  of writing) and are only referenced, not re-measured here.

## Context

Record 0024 measured a `Vbe`/`dVbe` UVLO reference candidate that passes 15
of 15 corners and gates its adoption on four items. Gates 3 and 4 are this
record's scope. Gate 3 is a safety matter: a `Vbe`/`dVbe` core has a
degenerate zero-current state, and 0024's hand measurement (27 C, `MKICK`
deleted, core initialised dead) showed the failure direction is the unsafe
one — `lockout` stays low and the UVLO releases `OUT` at 2 V. Gate 4 is a
cost matter: the candidate adds nine substrate PNPs, a 3.2 pF MIM cap and a
50 MOhm feedback resistor to a block whose present UVLO is drawn.

Evidence: `sim/uvlo-reference-study/` — the committed plan and per-corner
tables in `README.md` ("Gate 3: startup path", "Gate 4: layout cost"), the
twelve generator-produced requests under `klt/` (pinned byte-for-byte by
`sim/test_gen_requests.py`), the negative-control DUT
`uvlo_bandgap_ref_nokick.spice`, and the committed `klt sim` batch-set
evidence `envelopes/20261121-0160c0d-klt-sim-uvlo-bandgap-startup.json` over
twelve member reports.

## Decision

**No design change is adopted by this record.** It records the two gates'
outcomes.

**Gate 3 (startup path): satisfied**, on the committed plan's criterion —
`lockout` asserted and `OUT` unreleased whenever `VDD_DRV` is below the
ratified falling-trip window's 3.3 V floor (DR-0001 Decision 4, nothing
relaxed) — measured at all 15 process x temperature points on every stimulus
of the plan:

- Power-on ramps 0 -> 6 V at 200 us, 20 us, 2 us, 200 ns per edge and the
  1 ns edge of `body-response.spice`: release level 3.741-3.988 V (graded
  >= 3.3 V, >= 0.44 V margin; the 20 us values reproduce 0024's committed
  rising trips exactly), power-up assert at 1.501-1.613 V, settled core
  alive (1.2156-1.2392 V) with correct released end state; cold-start from
  the 1 ns step 0.62-13.34 us (slowest `ff/-40C`).
- Stuck rails 2.0 V and 3.0 V (below the window): settled `lockout` at the
  rail, `OUT` <= 20.7 uV, core alive — the 15-corner dynamic form of 0024's
  table. 5.0 V: correctly released.
- Brown-out 6 -> 1.5 V in 1 ns (partial discharge below the core's
  regulation headroom), hold, re-ramp: `OUT` <= 24.2 uV through the hold,
  re-ramp release 3.815-3.967 V.
- Dead-initialised core (`.ic nfb` = rail + `uic`, 0024's adverse initial
  condition, expressed natively via `options.initial_conditions`): restarts
  in 0.14-1.01 us at all 15 corners and then meets the same grades.
- **Deterministic negative control**: the `MKICK`-deleted dead-initialised
  2.0 V case at tt/27 C — 0024's own measurement — run through the *same*
  checks **fails all three** (`nvref` 0.198 V, `lockout` 2.7e-6 V, `OUT`
  1.99983 V): the committed checks detect the known-bad circuit.

165 of 165 `MKICK`-present units pass; the control fails by design. Stated
limits: the pre-assert power-up interval (every UVLO has one; bounded per
corner by the reported `assert_v`, 1.501-1.613 V) is not graded, and `fs`/
`sf` select `bjt_typical`, so BJT process spread is exercised at 9 of the 15
points — carried as a limit of this gate, not closed. **Condition attached:
`MKICK` (a single W=2u L=2u nfet) is a safety element; a single open in its
path silently disables the UVLO.** Any adoption must carry this grid and its
control as a regression; the fail-safe default 0024 suggests (hold `lockout`
high until the core is confirmed alive) is recommended only if `MKICK`
reliability cannot be argued at layout time.

**Gate 4 (layout cost): the estimate exists and is recorded** — the gate as
written in 0024 — with one finding that changes the implementation path:
drawn as base `ppolyf_u` (350 ohm/sq, 0.42 um width), the candidate's
additions total ~75.4k um2, ~2.2x the present UVLO's ~34.0k um2 footprint
(~5.2 % of the 1.443 mm2 block outline), and the 50 MOhm `Rfb` alone is 67 %
of that (50.4k um2, larger than the whole present UVLO). The proposal that
follows (analysis only, no layout edit, no area target changed): draw `Rfb`
and `Rdet` in the high-sheet 6.0 V-area flavour `ppolyf_u_2k_6p0`
(2000 ohm/sq typ), which drops the additions to **~17.2k um2 — about half
the present UVLO** while keeping every ohm identical; the sibling gate-2
re-measurement (#555 / PR #564) already passes 15 of 15 corners with exactly
that flavour drawn for `Rfb`/`Rdet`, so the measured trip and hysteresis
behaviour survives. Trade stated in the README: +/-20 % family spread moves
only the hysteresis width (typical-value quantity, no ratified worst-case
bound; `Rfb` sets no trip window), with high-sheet poly's worse
matching/voltage-derating accepted because `Rfb`/`Rdet` set no precision
quantity.

So of 0024's four gates: 3 **satisfied** (this record), 4 **satisfied as an
estimate** with the high-sheet-flavour implementation path named, 2
satisfied (#555, record 0025), and 1 **not satisfied** — the mismatch gate,
per record 0025. **Adoption remains
blocked by gate 1**, and the fix it points to (offset cancellation or a
lower `Rsa/Rp` in the loop amplifier) is unchanged by this record.

## Alternatives considered

- **Run the grid as local ngspice loops** — rejected: committed evidence is
  `klt sim` on the batch fleet only (`--batch-set`, 12 jobs, all `done`);
  nothing was hand-launched locally for the evidence.
- **Hand-copy the trip request JSON for the twelve stimuli** — rejected:
  `klt/gen_startup_requests.py` generates all twelve over
  `sim/harness/klt_request.py` (issue #441), pinned byte-for-byte by
  `sim/test_gen_requests.py`.
- **Grade the brown-out hold on `lockout`** — rejected: at the 1.5 V park
  the inverters' own high level leaves no margin over the 1.5 V measurement
  level; `OUT` <= 0.5 V (the response row's low proxy) is the honest
  discriminator, and the control confirms it cannot miss (2.0 V on release).
- **Grade the pre-assert power-up interval** — rejected: no UVLO can drive
  `lockout` high before its chain has supply (the DR-0018 baseline included);
  the plan bounds it with the reported `assert_v` instead.
- **Accept the 10 us settle window's `ff/-40C` failure** — rejected: it was
  a window artifact (the same corner settles at 1.216 V by 18-20 us under
  the 200 ns stimulus), so the window was widened to 40 us and the grid
  re-run; the discarded first run is disclosed in the README.
- **File a `klt` capability gap** — not needed: `.ic`/`uic` start states
  (`options.initial_conditions`, klayout-tools #3881), the expected-fail
  control, and the ramp-rate fan-out (`--batch-set`) are all native; no gap
  was hit.
- **Relax the 3.3 V floor or any ratified window** — rejected; the criterion
  is keyed to DR-0001 Decision 4 unchanged.

## Consequences

- 0024's gate 3 and gate 4 are answered; **gate 1 remains the sole blocker**
  to adopting the reference, and the startup grid is now a reusable
  regression: twelve committed requests plus a control that any design
  change to the startup circuit must re-run.
- The startup path becomes a signoff item **conditional on `MKICK` being
  treated as a safety element** — the one respect in which the `Vgs`-stack
  references remain safer (no degenerate state, no single-point kicker).
  A future design change may harden this (fail-safe default); this record
  does not require it.
- The layout cost of adopting the reference is no longer unknown: with the
  proposed `ppolyf_u_2k_6p0` flavour for the two rail-spanning resistors the
  candidate adds ~17.2k um2 (half the present UVLO, 1.2 % of the block
  outline), of which the nine PNPs are 617 um2. No area target in
  `spec/gate-driver.md` is touched.
- `sim/test_gen_requests.py` now pins a fourth generator; the three existing
  generators' pinned bytes are unchanged.
- Nothing in `design/`, `layout/`, `verification/signoff/`,
  `spec/gate-driver.md` or any ratified record changes; T1 item 5 remains
  open pending the gate-1 outcome.
