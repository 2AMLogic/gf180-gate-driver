# UVLO stacked-diode reference study (issue #412)

Schematic-level study of the fix named in decision record 0018 ("Why no design
fix is undertaken here"): replace the single diode-connected `nfet_06v0`
reference (divider gain about 5x) with a multi-diode stack, so the divider gain
is near unity. Evidence only: `design/`, `layout/`, `verification/signoff/` and
`spec/gate-driver.md` are untouched.

**Result: negative.** The 3-diode candidate does not improve the PVT spread. It
passes 2 of 15 corners, against 4 of 15 for the DR-0018 baseline, and its
worst-case rising trip is **5.110 V** (`ss/-40C`), above the 4.50 V low-line
floor. One corner (`fs/125C`) errors in ngspice.

| File | What |
|---|---|
| `uvlo_stacked_ref.spice` | Candidate. Flat fragment like `design/netlist/uvlo.spice`. |
| `klt/request-trip.json`, `klt/body-trip.spice`, `klt/design.ngspice` | Copies of the DR-0018 trip request/body/PDK globals. Same 15 process x temperature points, ramp and bounds. Only the DUT `.include` differs. |
| `envelopes/20261106-453297f-klt-sim-uvlo-stacked-ref-trip.json` | Committed `klt sim` report (batch backend, 3 shards). |

## Candidate

Comparator, buffer and `MPD` devices are copied unchanged from
`design/netlist/uvlo.spice`. Changes:

- `MREF` becomes a stack of **N = 3** diode-connected `nfet_06v0` (each
  `L=0.7u W=10u`, bulk on `GND_DRV`, so the upper devices see body effect). The
  comparator reference input (`MINN` gate) is the top of the stack.
- `MTAIL`'s gate moves to the bottom tap (`nref1`, one Vgs). Left on the top of
  the stack it would see about 3 V and draw far more tail current. This is a
  connection change, not a device change; it is a deliberate deviation from
  "copy unchanged".
- `Rref` 800k -> 300k, `R1` 880k -> 150k, `R2` 200k -> 450k (divider gain 0.75
  instead of 0.185), `Rfb` 16000k -> 4000k (hysteresis about 0.30 V at tt/27 C).

Sizing was by single-corner `klt sim --backend local` probes at tt/27 C
(N = 4: stack never crosses the divider, because body effect puts it near
`VDD_DRV`; N = 3 with `Rfb` 800k/2000k/4000k/6000k gave 1.05/0.49/0.30/0.24 V
hysteresis). The sizing target was tt/27 C only; no corner-aware search was
done, so a different N/`Rref`/divider point is not excluded by this study.

## Result (15 corners)

DR-0018 baseline for reference: falling 2.23-4.74 V, 4 of 15 corners pass
(`sim/uvlo-trip-verification/klt/envelopes/20261028-d7a2b69-klt-sim-uvlo-trip.json`).

| Corner | Falling (V) | Rising (V) | Hysteresis (V) | Baseline falling / rising (V) | Status |
|---|---|---|---|---|---|
| `tt/-40C` | 4.069 | 4.350 | 0.281 | 4.005 / 4.333 | fail |
| `tt/27C` | 3.708 | 4.011 | 0.303 | 3.606 / 3.931 | pass |
| `tt/125C` | 3.149 | 3.494 | 0.346 | 3.017 / 3.341 | fail |
| `ff/-40C` | 3.342 | 3.598 | 0.256 | 3.260 / 3.542 | fail |
| `ff/27C` | 2.953 | 3.234 | 0.281 | 2.849 / 3.126 | fail |
| `ff/125C` | 2.330 | 2.664 | 0.334 | 2.231 / 2.503 | fail |
| `ss/-40C` | 4.798 | 5.110 | 0.312 | 4.737 / 5.115 | fail |
| `ss/27C` | 4.454 | 4.790 | 0.336 | 4.352 / 4.726 | fail |
| `ss/125C` | 3.933 | 4.308 | 0.375 | 3.786 / 4.162 | fail |
| `fs/-40C` | 2.892 | 3.692 | 0.800 | 3.468 / 3.775 | fail |
| `fs/27C` | 2.364 | 3.212 | 0.848 | 3.060 / 3.365 | fail |
| `fs/125C` | — | — | — | 2.449 / 2.757 | **error** (`ngspice_fatal`, measurement out of interval) |
| `sf/-40C` | 4.629 | 4.901 | 0.272 | 4.526 / 4.876 | fail |
| `sf/27C` | 4.300 | 4.576 | 0.276 | 4.137 / 4.481 | fail |
| `sf/125C` | 3.798 | 4.086 | 0.288 | 3.566 / 3.906 | pass |

(Baseline values are from the committed DR-0018-era envelope; the baseline
corner `fs/-40C` passes there, the candidate's does not.)

Counts against the ratified windows:

- Falling in 3.3-3.9 V: **3 of 15** (`tt/27C`, `ff/-40C`, `sf/125C`).
- Rising in 3.6-4.2 V: **3 of 15** (`tt/27C`, `fs/-40C`, `sf/125C`).
- Both windows (row passes): **2 of 15** (`tt/27C`, `sf/125C`). 12 fail, 1 errors.
- Falling-trip spread 2.33-4.80 V; baseline 2.23-4.74 V.
- **Worst-case rising trip 5.110 V (`ss/-40C`) vs the 4.50 V floor: does not
  clear it** (worse than the floor by 0.61 V). Rising trip exceeds 4.50 V at
  `ss/-40C`, `ss/27C`, `sf/-40C` and `sf/27C`.

## Reading

The trip point tracks N x Vgs(process, temperature) with a gain near one, so
the fractional spread of the reference is carried straight through; lowering
the divider gain removes the 5x multiplier on the *divider* but not the
absolute dependence of the threshold on the stack's Vgs, and body effect on
the upper devices adds process/temperature sensitivity. The hypothesis in
DR-0018 that the divider gain is the cause of the spread is not supported by
this measurement. The `fs` corners also show hysteresis of 0.8 V, i.e. the
comparator does not stay balanced there at the multi-Vgs common-mode level.

## Supply current

DC current drawn from `VDD_DRV` at 5 V, tt, 27 C, one `.op` (`vsup#branch`,
UVLO in the "ok" state): **34.5 uA**. This was a single local ngspice check, not
a `klt sim` corner, and the baseline was not measured here.

## Reproduce

```bash
cd sim/uvlo-reference-study/klt
klt sim --backend batch --hosts 3 \
  --report-out ../envelopes/<date>-<sha>-klt-sim-uvlo-stacked-ref-trip.json \
  --format json request-trip.json
```

The committed envelope was produced with klt `0.9.2.dev47+g581de87616d8`
against runner `0.9.0` (job ids under `environment.remote.fleet`).
