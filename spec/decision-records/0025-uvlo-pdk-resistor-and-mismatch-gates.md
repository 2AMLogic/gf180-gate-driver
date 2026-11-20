# 0025: UVLO `Vbe`/`dVbe` reference — PDK-resistor gate passes, local-mismatch gate fails

- **Status**: proposed
- **Date**: 2026-11-20
- **Decided by**: Builder agent, issue #555 (draft — **awaiting operator ratification**)
- **Extends**: decision record 0024 (UVLO `Vbe`/`dVbe` reference, measured),
  which adopted nothing and named four adoption gates. This record measures
  gate 2 (PDK resistors, `res_*` sections live) and gate 1 (local-mismatch
  Monte Carlo combined with the corners). **Does not reopen or amend** 0001,
  0018, 0023 or 0024, **does not close 0018 Finding 2**, does not declare T1
  item 5 met, and **changes no bound** in `spec/gate-driver.md` or decision
  record 0001. Gates 3 (startup signoff) and 4 (layout cost) belong to #556.

## Context

DR-0024's Consequences section says: "The next UVLO work is a
mismatch/Monte Carlo run on this candidate, not another topology search." Its
gate 1 rationale: the loop amplifier's input-pair offset is multiplied by
`Rsa/Rp = 10.19` into `Vref`, so ~10 mV of offset is ~8 % of the trip point —
"the measurement most likely to overturn the result above." Its gate 2
rationale: both candidates and `design/netlist/uvlo.spice` use ideal `R`
elements, so resistor process spread was never exercised and the PTAT gain is
a resistor ratio. Issue #555 measures both gates on the same harness, ramp,
corner grid and ratified bounds as 0018/0023/0024. Evidence:
`sim/uvlo-reference-study/` (candidate variant `uvlo_bandgap_ref_pdk_r.spice`,
the `klt sim`/`klt yield-campaign` requests, five committed envelopes under
`envelopes/`, and a study-3 README section with the per-corner tables and the
stated model coverage).

## Decision

**No design change is adopted by this record.** It records one satisfied gate
and one failed gate, and the numbers that a design iteration must answer to.
A failing gate is the valid outcome of #555; the response it points to is a
design iteration, never a wider trip window.

**Gate 2 (PDK resistors): satisfied.** With all seven ideal `R` elements
replaced by PDK poly devices (`ppolyf_u` for `Rsa`/`Rsb`/`Rp`/`R1`/`R2`;
`ppolyf_u_2k_6p0` — the 6.0 V-area high-sheet-rho flavor — for the
impractically large `Rdet` 20 MOhm and `Rfb` 50 MOhm) and the `res_*` corner
sections live for the first time:

- **15 of 15** corners pass both ratified windows; 0 fail, 0 error.
- Falling-trip spread **3.471-3.506 V (35 mV)** — tighter than 0024's
  nominal 91 mV; the load-bearing ratios (`Rsa/Rp`, `R1/R2`) track in one
  device flavor, and the absolute value shifts `Vbe` only logarithmically.
- Worst-case rising trip **4.138 V (`ss/-40C`)** against the 4.50 V low-line
  floor: **clears it** by 0.363 V (0024: 0.512 V). Margin to the 4.2 V
  ceiling narrows to 0.062 V at that corner.
- Hysteresis 0.428-0.661 V (0024: 0.284-0.348 V): the devices' own
  temperature coefficients and modelled `fox_sub` parasitics against the
  20 us ramp. The 0024 "not a static property" caveat applies a fortiori.

**Gate 1 (local mismatch): NOT satisfied.** `klt yield-campaign` on the batch
backend, `n = 1000` per corner x 15 corners (15,000 samples, seed 20261120,
`seed_scope: "point"`, `sw_stat_global = 0`, `mismatch_scale: 1`,
`window_scope: "per_corner"` with `k_sigma: 3`), plus a detected known-bad
control (`mismatch_scale: 2.5`, independently seeded) and an exact determinism
control (`mismatch_scale: 0`: per-corner sigma exactly 0, means reproduce the
gate-2 nominals to ten digits):

- Per-corner trip sigma is **0.476-0.570 V**; the 3-sigma windows **fail all
  15 corners on both windows**. Pooled yield against the ratified windows:
  **falling 43.1 %** (95 % CI 42.3-43.9), **rising 45.4 %** (CI 44.6-46.2);
  `sigma_to_spec` 0.48 / 0.22. `sample_size.verdict: sufficient` on both.
- **Worst-case rising trip including mismatch at 3 sigma: 5.848 V
  (`ss/-40C`, mean 4.245 + 3 x 0.534)** — 1.35 V past the 4.50 V floor; even
  at mean + 1 sigma that corner exceeds the floor, i.e. roughly a third of
  units there stay locked out at the legitimate low-line rail: 0018 Finding
  2's failure mode, resurrected by mismatch. Sample extremes 1.477-5.999 V;
  the 6 V ramp ceiling clips the worst draws (30 nominal / 2,019 control
  samples errored and are counted as errored, not dropped).
- Model coverage, quoting the envelope's `family_mismatch`: MOS and BJT
  (`fets_mm`, `bjt_mc`) `active: true` — per DR-0017 the 6 V flavours carry
  threshold mismatch only (`par_k = 0`); resistors and MIM capacitors
  `active: false` (the hooks ship disabled in the vendored deck,
  klayout-tools #355 / #2898). **Unmeasured residual:** `Rsa`/`Rp` and
  `R1`/`R2` ratio matching cannot be exercised on this PDK, and adding it can
  only widen the spread — gate 1 is not satisfied, and not even on its full
  input space.

Referred back through the loop, ~0.51-0.54 V of trip sigma is ~**15 mV** of
input-referred loop-amplifier offset (1 mV of offset is ~35 mV of trip at
`Rsa/Rp` = 10.19 and divider gain 0.319) — 0024's flagged amplification,
measured rather than estimated. Of 0024's two named follow-ups, the numbers
point primarily at **offset cancellation in the loop amplifier**: to hold a
3-sigma window inside the 0.30 V falling half-window at today's ratio needs
input-referred sigma <= ~2.8 mV (a ~5x reduction — larger input pair, or
chopping/auto-zero), whereas lowering `Rsa/Rp` to ~2 alone — giving up the
zero-TC ratio — still leaves ~0.41 V of 3-sigma window and fails. The
response to this record is that design iteration, scoped in a new issue; the
ratified trip windows do not move.

## Alternatives considered

- **Adopt the PDK-resistor variant on gate 2's strength** — rejected: gate 1
  fails by more than a factor of 10 in sigma-to-spec; 0024 conditions
  adoption on all four gates.
- **Widen the ratified trip windows to admit the mismatch spread** — rejected:
  the windows are ratified in `spec/gate-driver.md` and agents do not relax
  the ratified spec to make results pass (CLAUDE.md); the 4.50 V low-line
  floor is a system requirement.
- **Treat the failing campaign as a tool/PDK artifact** — rejected: the
  determinism control reproduces the nominal exactly with mismatch off, the
  independently seeded 2.5x control is detected with its sigma scaled up, and
  the sigma magnitude is consistent with 0024's own offset-amplification
  estimate.
- **Re-run as another topology search** — rejected: 0024's Consequences
  explicitly redirect to this measurement, and gate 2 shows the mechanism is
  not the problem; the offset multiplication is.

## Consequences

- The #457 candidate **cannot be adopted as sized**. Any future UVLO
  reference proposal must either cancel the loop amplifier's offset or
  re-architect the ratio, and must re-run this same campaign (spec, controls
  and all) — `klt/campaign-bandgap-pdk-r.json` is the reusable pattern.
- 0018 Finding 2 and T1 item 5 **remain open**; nothing in `design/`,
  `layout/`, `verification/signoff/` or `spec/gate-driver.md` changes, and
  `tier-report.json` is not regenerated.
- Gate 2's positive result stands on its own: `ppolyf_u` ratio tracking is
  now measured on this block (35 mV falling-trip spread with `res_*` live),
  and `pnp_05p00x05p00` plus the 6.0 V-area `ppolyf_u_2k_6p0` are now
  exercised devices for future 5 V-rail blocks on this PDK.
- Harness gaps remain recorded, none blocking: gf180mcu resistors/MIM caps
  have no local-mismatch model (klayout-tools #355, #2898), `fs`/`sf` select
  `bjt_typical` (BJT process spread at 9 of 15 points), and the trip
  measurement's hysteresis is ramp-rate-dependent. The measured resistor
  geometry is a schematic-level choice; its layout cost is gate 4 (#556).
- The gate-1 campaign demonstrates the repo can now run seeded, controlled
  Monte Carlo through `klt` on the batch backend (yield-native via
  `klayout-tools[yield]`), replacing the hand-rolled `sim/*-mismatch`
  scripts for future campaigns.
