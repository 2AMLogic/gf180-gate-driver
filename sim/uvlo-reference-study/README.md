# UVLO reference studies

Schematic-level studies of the UVLO reference named in decision record 0018
("Why no design fix is undertaken here"), on one harness and one set of ratified
bounds. Evidence only: `design/`, `layout/`, `verification/signoff/` and
`spec/gate-driver.md` are untouched by both studies.

Two candidates have been measured, both against the DR-0018 baseline:

| Candidate | Issue | Reference mechanism | Result |
|---|---|---|---|
| 3-diode stack | #412 (record 0023) | 3 diode-connected `nfet_06v0` in series: `N x Vgs` | **negative** — 2 of 15 corners, spread unchanged |
| `Vbe`/`dVbe` core | #457 (this study) | substrate PNPs `pnp_05p00x05p00`: junction `Vbe` + PTAT `dVbe` | **positive** — 15 of 15 corners, falling-trip spread 91 mV |
| same, adoption gates 3 + 4 | #556 (this study) | — | **gate 3 satisfied** (startup grid 165/165 units pass, `MKICK`-deleted control detected as failing); **gate 4 costed** (the 50 MOhm `Rfb` dominates; high-sheet flavour proposal below) |

Read the two sections below in that order; the second is the follow-up record
0023's Consequences section asks for ("a reference with weaker
process/temperature dependence").

| File | What |
|---|---|
| `uvlo_stacked_ref.spice` | #412 candidate. Flat fragment like `design/netlist/uvlo.spice`. |
| `uvlo_bandgap_ref.spice` | #457 candidate. Same shape; `Vbe`/`dVbe` reference. |
| `uvlo_bandgap_ref_nokick.spice` | #556 gate-3 negative control: the #457 candidate with exactly `XMKICK` deleted. |
| `klt/request-trip.json`, `klt/body-trip.spice` | #412 trip request/body. |
| `klt/request-bandgap-trip.json`, `klt/body-bandgap-trip.spice` | #457 trip request/body. Copies of the #412 pair; only the `netlist` key and the DUT `.include` differ. |
| `klt/gen_startup_requests.py` | #556 gate-3 generator: writes the twelve `request-startup-*.json` over `sim/harness/klt_request.py` (the issue #441 pattern — no third copy of the scaffolding). |
| `klt/body-startup-*.spice`, `klt/request-startup-*.json` | #556 gate-3 startup grid: twelve stimulus request/body pairs (five ramp rates, three stuck rails, brown-out, two dead-init points, one negative control). |
| `klt/design.ngspice` | DR-0018 PDK globals, shared unchanged by both. |
| `envelopes/20261106-453297f-klt-sim-uvlo-stacked-ref-trip.json` | #412 committed `klt sim` report (batch backend, 3 shards). |
| `envelopes/20261114-38154c7-klt-sim-uvlo-bandgap-ref-trip.json` | #457 committed `klt sim` report (batch backend, 3 shards). |
| `envelopes/20261121-0160c0d-klt-sim-uvlo-bandgap-startup.json` (+ `20261121-0160c0d-uvlo-bandgap-startup/`) | #556 gate-3 committed `klt sim --batch-set` evidence: one aggregate envelope over twelve member reports (batch backend, 12 jobs, all done exit 0 — the negative-control member's job exit 3 is its graded FAIL, by design). |

Both requests carry the same ramp (`tran 10n 40u`, a 0 -> 6 V -> 0 V triangle at
20 us per edge), the same 5 process x 3 temperature points, and the same
ratified bounds: falling trip 3.3-3.9 V, rising trip 3.6-4.2 V.

---

# Study 1: stacked-diode reference (issue #412)

Replace the single diode-connected `nfet_06v0` reference (divider gain about
5x) with a multi-diode stack, so the divider gain is near unity.

**Result: negative.** The 3-diode candidate does not improve the PVT spread. It
passes 2 of 15 corners, against 4 of 15 for the DR-0018 baseline, and its
worst-case rising trip is **5.110 V** (`ss/-40C`), above the 4.50 V low-line
floor. One corner (`fs/125C`) errors in ngspice.

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

---

# Study 2: `Vbe`/`dVbe` (bandgap-type) reference (issue #457)

The follow-up decision record 0023 names in its own Consequences section:
"A follow-up should evaluate a reference with weaker process/temperature
dependence before any schematic change is made." Study 1 showed the trip point
tracks `N x Vgs`, so the candidate here derives the reference from junction
physics instead — `Vbe` of a substrate PNP (CTAT) summed with a PTAT `dVbe`.

**Result: positive.** The `Vbe`/`dVbe` candidate passes **15 of 15 corners** on
both windows, with a falling-trip spread of **91 mV** (3.550-3.641 V) against
2.51 V for the DR-0018 baseline and 2.47 V for the 3-diode candidate. Its
worst-case rising trip is **3.988 V** (`ss/125C`), which **clears** the 4.50 V
low-line floor by 0.512 V — the failure Finding 2 of DR-0018 reported and
study 1 did not fix. No corner errors. DC supply current is 34.8 uA, within
0.3 uA of study 1's 34.5 uA and about 1.9x the DR-0018 baseline's 17.95 uA
(measured here for the first time; study 1 did not measure it).

This is a schematic-level measurement of a reference *mechanism*. It is not a
proposal to change `design/uvlo.sch`; see "What this does and does not settle".

## Where the mechanism came from

Per the issue's AC1 research question: the sibling `2AMLogic/gf180-bandgap`
core **cannot** be taken by reference at this block's supply range. All 42 of
its core MOS devices are `*_03v3` (`sim/dut/bandgap_top.spice`,
`sim/dut/bandgap_amp.spice`) and its ratified `spec/decision-records/0002-supply-voltage-scope.md`
reads "3.3V-only for wave 1 … No 5V-flavor work is undertaken in wave 1",
against `VDD_DRV`'s 4.5 / 5.0 / 5.5 V tolerance points here.

What *is* reusable is its reference mechanism and device choice: its core's
reference is three vertical substrate PNPs (`XQ1`/`XQ2`/`XQ3`, device
`pnp_05p00x05p00`, `m=1/4/1`), and both repos pin `gf180mcuD`, so the device is
available to this harness. This candidate borrows that — PNPs for the
reference, this block's own `*_06v0` devices for the mirror, amplifier and
comparator — and nothing else.

## Candidate

`uvlo_bandgap_ref.spice`. Comparator (`MTAIL`/`MINP`/`MINN`/`MLOADP`/`MLOADN`),
the two-inverter buffer and `MPD` are copied device-for-device from
`design/netlist/uvlo.spice`, so any movement in the result is attributable to
the reference. Two **connection** changes, of the same kind study 1 made to
`MTAIL`: `MINN`'s gate is the new reference node `nvref` and `MTAIL`'s gate is
the core's bias node `nib`, because the diode-connected-NMOS node `nref` that
both used no longer exists.

Replacing `Rref`/`MREF`:

- Two matched `pfet_06v0` mirror legs (`MP1`, `MP2`, `L=2u W=5u`, gates on
  `nfb`) feed leg A (`nvref` -> `Rsa` 275k -> `Q1`, `pnp_05p00x05p00` `m=1`) and
  leg B (`nvb` -> `Rsb` 275k -> `Rp` 27k -> `Q2`, same device at `m=8`).
- A loop amplifier (`nfet_06v0` input pair `MAMP1`/`MAMP2`, `pfet_06v0` mirror
  load `MALP1`/`MALP2`, tail `MATAIL` biased from `nib`) forces
  `V(nvref) = V(nvb)`. With equal mirror currents and an 8:1 emitter-area
  ratio that gives `I * Rp = Vbe1 - Vbe2 = (kT/q) * ln(8)`, so

      Vref = V(nvref) = Vbe1 + (Rsa/Rp) * (kT/q) * ln(8)

  — a CTAT term plus a PTAT term. `Rsa/Rp = 275k/27k = 10.19` is the
  first-order zero-TC ratio for this device: `dVbe/dT = (Vbe - Eg/q)/T -
  xti*(kT/q)/T = -1.83 mV/K` and `d(dVbe)/dT = ln(8)*k/q = +0.179 mV/K`.
  Measured at tt/27 C, 5 V, one `.op`: `Vref = 1.2264 V`, leg current
  `1.985 uA` in each of `MP1`/`MP2`, and `V(ne1) - V(ne2) = 53.9 mV` — i.e.
  `(kT/q)*ln(8)` as designed, within 0.4 mV.
- Putting the **same** `Rsa` in both legs is what raises the amplifier's input
  common mode from `Vbe` (0.70 V) to `Vref` (1.23 V) without changing the PTAT
  equation above. An `nfet_06v0` input pair cannot run at a 0.70 V common
  mode: the pair's measured `vth` at this operating point is **0.860 V**
  (`MAMP1`, `L=2u`), so at `Vbe` it would sit ~160 mV below threshold. At the
  1.23 V common mode it sits at `vgs = 0.873 V`, 13 mV of overdrive, carrying
  0.97 uA. This is the one structural departure from the sibling's 3.3 V cell,
  which does run its pair at `Vbe`.
- `XCC` (`cap_mim_2f0_m4m5_noshield`, 40u x 40u, 3.2 pF, `VDD_DRV` to `nfb`)
  compensates the loop. It is load-bearing: delete it and the same deck at the
  same sizing gives falling 3.071 V / rising 3.606 V at tt/27 C (the falling
  trip is then **outside** the 3.3 V floor), with `V(nvref)` wandering over
  1.131-1.193 V across the 15-25 us window instead of holding 1.22-1.24 V.
  This is the only non-ideal passive in either candidate, and it is the reason
  the request's `mimcap_*` corner sections now matter for this study.
- `Rdet`/`MSENSE`/`MKICK` are the startup circuit — see below.
- Divider re-valued for the 1.23 V reference instead of the baseline's single
  `Vgs` (measured `V(nref) = 0.756 V` at 5 V, tt, 27 C): `R1` 880k -> 960k,
  `R2` 200k -> 450k (gain 0.319 instead of 0.185), `Rfb` 16000k -> 50000k.

Sizing was by single-corner local `ngspice -b` probes at tt/27 C, the same way
study 1 sized its candidate: `Rsa`/`Rp` from the zero-TC ratio above, then
`R1` and `Rfb` to put the falling trip at the centre of 3.3-3.9 V and the
rising trip at the centre of 3.6-4.2 V. **The ratified bounds were not moved
and nothing was tuned per corner** — the 15-corner grid below was run once,
after the tt/27 C sizing was fixed and committed.

## Result (15 corners)

Both predecessors for reference: DR-0018 baseline falling 2.23-4.74 V, 4 of 15
corners pass (`sim/uvlo-trip-verification/klt/envelopes/20261028-d7a2b69-klt-sim-uvlo-trip.json`);
3-diode candidate falling 2.33-4.80 V, 2 of 15 (study 1 above).

| Corner | Falling (V) | Rising (V) | Hysteresis (V) | 3-diode falling / rising (V) | Baseline falling / rising (V) | Status |
|---|---|---|---|---|---|---|
| `tt/-40C` | 3.590 | 3.897 | 0.308 | 4.069 / 4.350 | 4.005 / 4.333 | pass |
| `tt/27C` | 3.593 | 3.905 | 0.312 | 3.708 / 4.011 | 3.606 / 3.931 | pass |
| `tt/125C` | 3.588 | 3.903 | 0.315 | 3.149 / 3.494 | 3.017 / 3.341 | pass |
| `ff/-40C` | 3.563 | 3.848 | 0.285 | 3.342 / 3.598 | 3.260 / 3.542 | pass |
| `ff/27C` | 3.562 | 3.848 | 0.286 | 2.953 / 3.234 | 2.849 / 3.126 | pass |
| `ff/125C` | 3.550 | 3.834 | 0.284 | 2.330 / 2.664 | 2.231 / 2.503 | pass |
| `ss/-40C` | 3.622 | 3.956 | 0.334 | 4.798 / 5.110 | 4.737 / 5.115 | pass |
| `ss/27C` | 3.634 | 3.975 | 0.341 | 4.454 / 4.790 | 4.352 / 4.726 | pass |
| `ss/125C` | 3.641 | 3.988 | 0.348 | 3.933 / 4.308 | 3.786 / 4.162 | pass |
| `fs/-40C` | 3.584 | 3.882 | 0.299 | 2.892 / 3.692 | 3.468 / 3.775 | pass |
| `fs/27C` | 3.586 | 3.890 | 0.303 | 2.364 / 3.212 | 3.060 / 3.365 | pass |
| `fs/125C` | 3.581 | 3.887 | 0.305 | — / — (**error**) | 2.449 / 2.757 | pass |
| `sf/-40C` | 3.596 | 3.914 | 0.318 | 4.629 / 4.901 | 4.526 / 4.876 | pass |
| `sf/27C` | 3.601 | 3.924 | 0.323 | 4.300 / 4.576 | 4.137 / 4.481 | pass |
| `sf/125C` | 3.597 | 3.923 | 0.327 | 3.798 / 4.086 | 3.566 / 3.906 | pass |

Counts against the ratified windows:

- Falling in 3.3-3.9 V: **15 of 15**.
- Rising in 3.6-4.2 V: **15 of 15**.
- Both windows (row passes): **15 of 15**. 0 fail, **0 error** — including
  `fs/125C`, the corner that errored (`ngspice_fatal`, measurement out of
  interval) for the 3-diode candidate. The envelope's `errored` and
  `inconclusive` counts are both 0 and `diagnostic_counts.by_code` is empty, so
  no corner was dropped.
- Falling-trip spread **3.550-3.641 V (91 mV)**; 3-diode 2.33-4.80 V
  (2.47 V), baseline 2.23-4.74 V (2.51 V). A 27x reduction against the
  baseline.
- **Worst-case rising trip 3.988 V (`ss/125C`) vs the 4.50 V floor: clears it**
  with 0.512 V of margin. No corner's rising trip exceeds 4.50 V. The 3-diode
  candidate exceeded it at four corners and the baseline at three.
- Hysteresis 0.284-0.348 V across all 15 corners, against 0.256-0.848 V for the
  3-diode candidate (whose `fs` corners reached 0.8 V).

## Reading

`Vbe` is set by `Is` and `Eg` rather than by `Vt`, and the PDK's `bjt_ss`/`bjt_ff`
sections move `Is` by only 0.65x/1.35x — which, through `Vbe = (kT/q) ln(I/Is)`,
is +11 mV / -8 mV of `Vbe`, against the hundreds of millivolts of `Vt` spread
the two `Vgs`-derived references carry. Summing a PTAT `dVbe` at the zero-TC
ratio then removes the first-order temperature term as well. So the result is
what the mechanism predicts, and it is the mechanism — not a sizing choice —
that record 0023 identified as the problem and this study changes.

The residual 91 mV of spread is **not** in the reference. Over the five
single-corner local ramp probes (`tt/27C`, `ss/-40C`, `ff/125C`, `fs/125C`,
`sf/-40C`), the min/max of `V(nvref)` across the whole 15-25 us window — which
includes the switching transient itself, so it is an upper bound on the
reference's variation rather than a settled spread — is 1.215-1.239 V, about
2%. On the tt/27 C ramp `V(nvref)` moves only 2 mV between `VDD_DRV` = 3.0 V
and 6.0 V. The trip ordering that remains
(`ss` highest, `ff` lowest) is the sign of the **comparator's** offset, which
is still `Vt`-dependent, divided by the 0.319 divider gain. If this reference
is ever taken toward a design change, the comparator offset — not the
reference — is the next thing to attack.

## Startup and the zero-current state

A `Vbe`/`dVbe` core has a degenerate zero-current operating point that the
3-diode candidate did not: `I = 0` also satisfies `V(nvref) = V(nvb)`. This is
safety-relevant for a UVLO, so it was measured rather than assumed.
`Rdet`/`MSENSE`/`MKICK` break it: with the core dead, `nvref` is low, `MSENSE`
is off, `Rdet` pulls `ndet` to `VDD_DRV`, and `MKICK` pulls the mirror gate
`nfb` to `GND_DRV`, forcing current into the legs.

Measured at 27 C with the core initialised dead
(`.ic v(nfb)=VDD v(nvref)=0 v(nvb)=0 v(nib)=0 …`, `tran … uic`, 200 us at a
fixed `VDD_DRV`), with and without `MKICK` present:

| `VDD_DRV` | `MKICK` | settled `V(nvref)` | settled `lockout` | `I(VDD_DRV)` |
|---|---|---|---|---|
| 5 V | present | 1.226 V | low (released — correct, 5 V is above trip) | 34.7 uA |
| 5 V | deleted | **0.373 V** | low | 3.6 uA |
| 3 V | present | 1.226 V | **high (locked out — correct)** | 59.6 uA |
| 3 V | deleted | **0.249 V** | **low (released — WRONG)** | 2.2 uA |
| 2 V | present | 1.225 V | **high (locked out — correct)** | 30.7 uA |
| 2 V | deleted | **0.117 V** | **low (released — WRONG)** | 1.4 uA |

(`I(VDD_DRV)` in that table includes the testbench's 100k `rpu` on `OUT`, which
is why the locked-out 3 V rows draw *more* than the released 5 V rows: with
`lockout` high, `MPD` pulls `OUT` low and `rpu` carries about 30 uA.)

Two things to state plainly:

1. **With the startup circuit, the core starts at every corner measured.** All
   15 envelope corners ramp from `VDD_DRV = 0`, so every one of them exercises
   startup, and all 15 produced both trip measurements. The five local
   single-corner probes settle `Vref` to 1.215-1.239 V. No zero-current
   latch-up was observed.
2. **`MKICK` is load-bearing, and its failure direction is the unsafe one.**
   When the core is left dead, `nvref` sits *below* the divider tap, so the
   comparator reads "supply is fine" and `lockout` stays low — the UVLO
   releases `OUT` at 2 V and 3 V. That is the opposite of the fail-safe
   direction. Any design that adopts this reference must treat the startup
   path as a signoff item, not an implementation detail; a single open in
   `MKICK`'s path disables the UVLO silently. The `Vgs`-stack references do not
   have this failure mode, which is the one respect in which they are safer.

## Supply current

DC current drawn from `VDD_DRV` at 5 V, tt, 27 C, one `.op` (`vsup#branch`,
UVLO in the "ok" state): **34.8 uA** — against 34.5 uA for the 3-diode
candidate, measured the same way. Measured breakdown from the same `.op`:

| Branch | Current | Note |
|---|---|---|
| `MTAIL` (comparator tail) | 23.07 uA | copied device `W=20u L=0.7u`, gate now on `nib` = 0.811 V |
| `MP1` + `MP2` + `MP3` (mirror legs) | 5.95 uA | the reference core proper |
| `MATAIL` (loop-amp tail) | 1.94 uA | |
| `R1`/`R2` divider | 3.52 uA | |
| `Rdet` | 0.25 uA | startup detector pull-up |
| `Rfb` | 0.07 uA | |
| **total** | **34.81 uA** | `vsup#branch` reads 34.84 uA |

For comparison, `design/netlist/uvlo.spice` itself — the DR-0018 baseline — was
measured the same way for this study and draws **17.95 uA** at 5 V, tt, 27 C
(`V(nref) = 0.756 V`). Study 1 did not measure the baseline, so this is the
first number for it; both candidates are about 1.9x the baseline.

So two thirds of the cell's current is the **copied comparator's** tail, not the
new reference: the `Vbe`/`dVbe` core and its amplifier together cost 7.9 uA. The
comparator tail is this large because `MTAIL` was copied unchanged at
`W=20u L=0.7u` and is now biased from `nib` rather than from the deleted `nref`
node; re-sizing it is a free lever for anything built on this, but re-sizing a
copied device would have broken the attribution this study depends on. Like
study 1's, this is a single local ngspice check, not a `klt sim` corner, and no
`Iq` bound for this cell is ratified — the number is reported, not targeted.

## Limitations of this measurement

Stated so a reader does not have to infer them:

- **`fs` and `sf` do not spread the BJT.** `request-bandgap-trip.json` inherits
  the #412 `corners` block unchanged (AC2), and only `tt`, `ff` and `ss` select
  a matching `bjt_typical`/`bjt_ff`/`bjt_ss` section; `fs` and `sf` both select
  `bjt_typical`. So 9 of the 15 points carry BJT process spread and 6 do not.
  Since the reference is now a BJT, the honest reading of "15 of 15" is: MOS
  spread is covered at all 15 points, BJT spread at 9.
- **Resistors are ideal `R` elements**, as in `design/netlist/uvlo.spice` and
  `uvlo_stacked_ref.spice`. The `res_*` corner sections therefore do not spread
  them. For this candidate the PTAT gain depends on the `Rsa/Rp` **ratio**,
  which tracks in a real poly resistor, but the absolute value sets `I` and so
  shifts `Vbe` logarithmically, and `R1`/`R2`'s ratio sets the divider gain
  directly. A candidate taken further should re-measure with `ppolyf_u`
  devices and the `res_*` sections live.
- **No mismatch and no Monte Carlo.** `klt/design.ngspice` sets
  `sw_stat_global=0` and `sw_stat_mismatch=0`, so these are nominal-corner
  runs. For this candidate that matters more than for study 1: the loop
  amplifier's input-pair offset is multiplied by `Rsa/Rp` = 10.19 on its way
  into `Vref`, so a 10 mV random offset is ~100 mV of `Vref` error, which is
  ~8% of the trip point. **Mismatch, not process corners, is the next
  measurement this candidate needs** — and it is the one that could still
  overturn the positive result above.
- **The 3-terminal `pnp_05p00x05p00` is a vertical substrate PNP**, so its
  collector is the substrate. Both its base and collector are tied to
  `GND_DRV`. In a block whose point is the 5 V/6 V devices, substrate current
  injection into a shared well is not modelled by this deck.
- **The measured hysteresis is not all `Rfb`.** With `Rfb` set to 100 GOhm (i.e.
  effectively removed) the same deck at the same sizing still shows 0.245 V of
  hysteresis at tt/27 C (falling 3.639 V, rising 3.884 V), against 0.312 V with
  `Rfb` = 50 MOhm. The residue is because the measurement probes `lockout`,
  which drives `MPD`'s
  ~15 pF gate (`W=10u m=800`), and the 20 us ramp is not slow enough for that
  transition to be instantaneous. The same artefact is present in the baseline
  and the 3-diode harness — the three columns above are comparable — but no
  hysteresis number from this harness should be read as a static property.
- **`klt` reports `06v0` as an `unmoved_devices` entry for `ff`/`ss`/`fs`/`sf`**
  in `environment.corner_coverage` (also true of the committed #412 envelope,
  where it went unremarked). **This is a false positive and the 15-corner grid
  above does skew the 6 V devices.** Verified two ways. (1) The installed deck:
  all five top-level sections set distinct `.param nfet_06v0_vth0` values
  (`typical` 0, `ff` -0.1298, `ss` +0.1193, `fs` `-0.1298*0.75`, `sf`
  `0.1193*0.75`), plus `nfet_06v0_vsat`/`tox` and `pfet_06v0_dvth0`, which the
  commonly-named `nfet_06v0_t`/`pfet_06v0_t` sub-libs then consume — so the
  skew is carried by `.param` override, not by sub-lib name, which is what the
  coverage classifier compares. (2) Committed evidence in this repo: the
  DR-0018 baseline UVLO is built entirely from `*_06v0` devices and ideal
  resistors, and its falling trip reads 2.849 V at `ff/27C`, 3.606 V at
  `tt/27C` and 4.352 V at `ss/27C` — which is impossible if the 6 V devices did
  not move. Filed upstream as `2AMLogic/klayout-tools#5663`, because the field
  reads as "your corner sweep did not move the devices you care about" on
  exactly this block's device flavor, and `klt signoff` consumes the same
  coverage block.

## What this does and does not settle

- It settles record 0023's open question: a reference that does not derive from
  `Vgs` **does** collapse the UVLO trip spread on this harness, from 2.5 V to
  91 mV, and it clears the 4.50 V low-line floor that DR-0018 Finding 2
  reported.
- It does **not** settle whether `design/uvlo.sch` should change. That needs a
  mismatch/Monte Carlo result (see Limitations), a real-resistor re-measurement,
  a startup-path signoff plan for the unsafe failure direction above, and a
  layout cost estimate for the PNPs, the MIM cap and the 50 MOhm `Rfb`. None of
  those is in this issue's scope, and `design/`, `spec/`, `layout/` and
  `verification/signoff/` are untouched by this PR.
- T1 item 5 is **not** declared passing by this study. It records what a
  compliant reference would have to be.

## Reproduce

```bash
cd sim/uvlo-reference-study/klt
klt sim --backend batch --hosts 3 --wait-for-capacity 600 \
  --report-out ../envelopes/<date>-<sha>-klt-sim-uvlo-bandgap-ref-trip.json \
  --format json request-bandgap-trip.json
```

The committed envelope was produced with klt `0.9.2.dev1022+g2a9c52b27ce7`
against runner `0.9.0` (`runner_compatibility: match`), ngspice `47`, PDK
`gf180mcuD` / `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
(`models_lib_sha256 f6f4a96e…`), on three `c7i.4xlarge` spot shards — job ids
`klt-sim-684ba22165fe`, `klt-sim-a2ff758c8e9b`, `klt-sim-7f06c66bda66` under
`environment.remote.fleet`, all `state=done exit_code=0`.

Note that `klt` resolves `gf180mcuD` from `~/.ciel` while `sim/env.sh` /
`sim/run_corners.py` resolve it from `~/.volare` (a different `open_pdks`
build); the envelope records the ambiguity in `provenance.pdk.ambiguous_sources`.
The tt/27 C sizing probes were re-run against both installs and give identical
trips to ten digits, so nothing here depends on which one is read.

---

# Gate 3: startup path (issue #556)

Decision record 0024 gates adoption of the `Vbe`/`dVbe` candidate on, among
other things, "a signoff plan for the startup path", because the core has a
degenerate zero-current operating point whose failure direction is the unsafe
one: measured at 27 C with the kicker deleted and the core initialised dead,
`lockout` stays **low** — the UVLO releases `OUT` at 2 V and 3 V (the table in
"Startup and the zero-current state" above). That measurement was six local
ngspice rows at 27 C. This section is the committed plan and the committed
fleet evidence for it; the result is recorded in decision record
`spec/decision-records/0026-uvlo-vbe-reference-startup-and-layout-cost.md`.

## The plan

**Pass criterion, tied to the ratified windows of decision record 0001
Decision 4** (falling trip 3.3-3.9 V, rising trip 3.6-4.2 V; neither window is
moved): `lockout` must be asserted, and `OUT` unreleased, whenever `VDD_DRV`
is below the falling-trip window's **3.3 V floor**, on every stimulus and at
every one of the 15 process x temperature points. Operationally, graded by
`klt sim` limits on three quantities:

1. **Release level** — on every power-on ramp and re-ramp, the release
   decision (the `lockout` node falling through the harness's fixed 1.5 V
   absolute level, the same literal the trip requests use) must occur at
   `VDD_DRV` >= 3.3 V. A UVLO that never asserts during a ramp releases only
   at the rail the ramp parks at, so on the fast ramps (below) the same
   safety property is graded on the settled end state instead.
2. **Settled output state below the window** — on every stimulus that parks
   below 3.3 V, settled `lockout` >= 1.5 V and `OUT` <= 0.5 V (the response
   row's own low proxy, `OUT_LOW_V` in `sim/uvlo-trip-verification/klt/
   gen_requests.py`).
3. **Core alive** — settled `V(nvref)` >= 1.1 V against the measured 15-corner
   settled range 1.216-1.241 V (> 100 mV margin); the dead core reads
   0.117-0.373 V (record 0024), so the floor separates the two states by more
   than a factor of three.

**Stated, not graded:** the pre-assert power-up interval. From cold, `lockout`
is a digital-chain output that cannot be driven high before the chain has
supply; every UVLO has an interval at rail startup where `lockout` reads low
trivially (the DR-0018 baseline included — its reference node also starts at
0 V with its tail off). The plan bounds it per corner by reporting `assert_v`
(the rail level at which `lockout` first rises through 1.5 V on the slow
ramps) instead of grading it: measured 1.501-1.613 V, far below the 3.3 V
floor, so the comparator decides "locked out" while the rail is still below
the window on every corner. The hazard the criterion targets is a *persisting*
wrongful release — the 0024 failure — and that is what items 1-3 grade.

**Conditions that must be shown to start** (each a request/body pair under
`klt/`, all 15 corners unless stated, `MKICK` present unless stated):

| Stimulus | Body/request | What it shows |
|---|---|---|
| 0 -> 6 V ramp, 200 us per edge | `ramp-slow` | quasi-static startup; graded on release + assert crossings |
| 0 -> 6 V ramp, 20 us per edge | `ramp-harness` | the trip envelopes' own ramp rate; same grades |
| 0 -> 6 V ramp, 2 us per edge | `ramp-fast` | core settles while the rail crosses the window |
| 0 -> 6 V ramp, 200 ns per edge | `ramp-vfast` | comparator cannot assert inside the ramp; settled grades |
| 0 -> 6 V step, 1 ns edge | `ramp-1ns` | `body-response.spice`'s own edge rate from cold; settled grades + reported `t_alive` |
| 0 -> 2.0 V ramp, hold | `hold-2v0` | stuck below the window at 0024's failure level |
| 0 -> 3.0 V ramp, hold | `hold-3v0` | 0024's middle row |
| 0 -> 5.0 V ramp, hold | `hold-5v0` | normal rail: released with core alive |
| 6 V -> 1.5 V in 1 ns, hold, re-ramp | `brownout` | partial discharge below the core's regulation headroom, then recovery |
| fixed 2.0 V, dead-init (`.ic nfb=2.0` + `uic`) | `deadinit-2v0` | 0024's adverse initial condition; restart + output grades |
| fixed 5.0 V, dead-init (`.ic nfb=5.0` + `uic`) | `deadinit-5v0` | 0024's 5 V probe; restart grade |
| same as `deadinit-2v0`, `XMKICK` deleted | `deadinit-2v0-nokick` | **negative control**, tt/27 C only: must FAIL the same checks |

The dead-initialised runs are expressed natively through
`options.initial_conditions` (`{match: {}, values: {nfb: <rail>}}`, rendered
by `klt` as a file-scope `.ic` card plus `uic`, klayout-tools #3881) — the
DUT netlists are not edited to force a start state. The `MKICK`-deleted
control uses a separate DUT copy, `uvlo_bandgap_ref_nokick.spice`, whose only
delta from the candidate is the deleted `XMKICK` instance; it carries the
same measurements and limits as `deadinit-2v0`.

**BJT-corner coverage, stated limit (inherited, not closed here):** the
requests inherit the #412 corners block (AC2 of study 2), so `fs` and `sf`
select `bjt_typical` — BJT process spread is exercised at 9 of the 15 points,
MOS spread at all 15. For gate 3 this limits the `assert_v`/`t_alive`
 absolutes (a spread BJT moves `Vbe`, hence the start level and time); it
does not affect the direction of any graded check, all of which are bounded
by margins (>= 0.44 V on the release level, >= 0.5 V on the settled states)
far larger than the +11/-8 mV of `Vbe` the `bjt_ff`/`bjt_ss` sections carry.
Carried as a limit of this gate's result rather than re-cornered.

## Result

All 165 units of the eleven `MKICK`-present members **pass** at every corner;
the negative control **fails** its three graded checks. Committed evidence:
`envelopes/20261121-0160c0d-klt-sim-uvlo-bandgap-startup.json` over the twelve
member reports in `envelopes/20261121-0160c0d-uvlo-bandgap-startup/` (batch
backend, 12 jobs, all `done`/exit 0 except the control member, whose exit 3
*is* its graded FAIL).

Release and assert levels on the slow ramps (release graded >= 3.3 V;
`assert_v` reported), and the cold-start time constant from the 1 ns step:

| Corner | 200 us: release | 200 us: assert | 20 us: release | 20 us: assert | 1 ns: `t_alive` |
|---|---|---|---|---|---|
| `tt/-40C` | 3.799 | 1.501 | 3.897 | 1.511 | 0.62 us |
| `tt/27C` | 3.805 | 1.501 | 3.905 | 1.513 | 0.68 us |
| `tt/125C` | 3.801 | 1.502 | 3.903 | 1.516 | 0.71 us |
| `ff/-40C` | 3.758 | 1.501 | 3.848 | 1.507 | **13.34 us** |
| `ff/27C` | 3.756 | 1.501 | 3.848 | 1.509 | 2.24 us |
| `ff/125C` | 3.741 | 1.501 | 3.834 | 1.511 | 1.23 us |
| `ss/-40C` | 3.849 | 1.502 | 3.956 | 1.548 | 0.64 us |
| `ss/27C` | 3.866 | 1.502 | 3.975 | 1.534 | 0.65 us |
| `ss/125C` | 3.877 | 1.502 | 3.988 | 1.526 | 0.70 us |
| `fs/-40C` | 3.793 | 1.501 | 3.882 | 1.514 | 0.66 us |
| `fs/27C` | 3.799 | 1.502 | 3.890 | 1.517 | 1.16 us |
| `fs/125C` | 3.794 | 1.613 | 3.887 | 1.520 | 0.81 us |
| `sf/-40C` | 3.806 | 1.501 | 3.914 | 1.509 | 0.62 us |
| `sf/27C` | 3.814 | 1.501 | 3.924 | 1.511 | 0.64 us |
| `sf/125C` | 3.811 | 1.501 | 3.923 | 1.513 | 0.69 us |

- Release level (graded): 3.741-3.988 V — every corner >= 3.3 V with >=
  0.44 V of margin. The 20 us values reproduce study 2's committed rising
  trips exactly (e.g. `ff/-40C` 3.848 vs 3.848, `ss/125C` 3.988 vs 3.988) —
  the release-on-startup *is* the rising trip, cross-validated.
- Assert level (reported): 1.501-1.613 V — the UVLO asserts while the rail is
  still below 1.7 V at every corner, bounding the pre-assert interval.
- Fast ramps (2 us, 200 ns, 1 ns): settled `V(nvref)` 1.2156-1.2392 V and
  settled `lockout` low (released — correct at the 6 V park) at all 45 units.
  Cold-start time from the 1 ns step: 0.62-13.34 us, slowest at `ff/-40C`.
- Stuck rails, below the window (2.0 V and 3.0 V): settled `lockout` holds
  the rail exactly (min 2.000 V / 2.9996 V over the settled window; graded
  >= 1.5 V), `OUT` <= 20.7 uV (graded <= 0.5 V), core alive 1.216-1.241 V —
  the dynamic, 15-corner form of 0024's 2 V and 3 V rows.
- Stuck 5.0 V rail: `lockout` never leaves low (max 3.1e-8 V) with the core
  alive — released, which is correct above every corner's rising trip.
- Brown-out (6 -> 1.5 V in 1 ns, hold 50 us, re-ramp): `OUT` <= 24.2 uV
  through the hold (graded <= 0.5 V), re-ramp release 3.815-3.967 V (graded
  >= 3.3 V), core alive again after the re-ramp. At the 1.5 V park
  `lockout` sits at the rail (reported `hold_lockout_min` 1.4999...-1.5 V)
  — exactly why the graded discriminator there is `OUT`, not `lockout`: at a
  1.5 V rail the inverters' own high level leaves no margin over the 1.5 V
  measurement level, while a wrongful release pulls `OUT` to the rail
  (the control shows 2.0 V) and cannot miss the 0.5 V bound.
- Dead-initialised core (`.ic nfb` = rail + `uic`): restarts in 0.35-1.01 us
  at 2.0 V and 0.14-0.55 us at 5.0 V, then satisfies the same settled grades
  as the power-on cases at all 15 corners — 0024's adverse initial condition
  is cleared by `MKICK` everywhere, not just at 27 C.

**Negative control (deterministic, from 0024):** the `MKICK`-deleted,
dead-initialised 2.0 V case at tt/27 C — the exact condition 0024 measured by
hand — run through the *same* measurements and limits as the passing
`deadinit-2v0` member. It **fails all three graded checks**:
`nvref_settled` = 0.198 V (< 1.1), `lockout_min` = 2.7e-6 V (< 1.5),
`out_max` = 1.99983 V (> 0.5 — `OUT` pulled to the rail), with `t_alive`
reported `not_reached`. The committed checks detect the known-bad circuit.

**One disclosed re-run:** the 1 ns member was first submitted with a 10 us
settle window and graded `ff/-40C` at `nvref` = 0.62 V — mid-startup, not a
start failure (the 200 ns member shows the same corner settled at 1.216 V by
18-20 us). The window was widened to 40 us and the whole twelve-member grid
re-run; the committed envelope is the re-run, and the first run's envelope
was discarded uncommitted. The widen is recorded in the body's own header.

**No `klt` capability gap was hit.** The plan needed exactly the three things
the issue anticipated might be missing, and all are native: dead-initialised
`.ic`/`uic` (`options.initial_conditions`, klayout-tools #3881), an
expected-fail negative control (ordinary limits on a known-bad DUT copy), and
a ramp-rate sweep (one request per rate, fanned out with `--batch-set`). No
local ngspice grid was run for the committed evidence, and no request JSON
was hand-copied — all twelve are generator output pinned byte-for-byte by
`sim/test_gen_requests.py`.

## Reading

With `MKICK` present, the core starts under every adverse condition the plan
covers: all 15 corners, ramp rates from quasi-static to a 1 ns cold step, a
1 ns deep brown-out to below the core's regulation headroom, and 0024's
dead initial condition. The unsafe direction 0024 measured is real but
entirely carried by `MKICK`: delete it and the same checks fail loudly on a
dead core that releases `OUT` at 2 V. So gate 3's answer is: **the startup
path is signable, on the condition that `MKICK` (a single minimum-size
nfet, `W=2u L=2u`) is treated as a safety element** — a single open in its
path silently disables the UVLO. A design change that adopts this reference
should carry this grid (and the control) as a regression and should consider
the fail-safe default 0024 suggests (hold `lockout` high until the core is
confirmed alive) if `MKICK` reliability cannot be argued at layout time;
that hardening is not required by the measured grid and is not proposed here.

---

# Gate 4: layout cost (issue #556)

Drawn-area estimate for the candidate's additions over the present UVLO, per
device class. Sources: PDK GDS `libs.ref/gf180mcu_fd_pr/gds/
pnp_05p00x05p00.gds` (bbox 8.28 x 8.28 um, measured at dbu 1 nm); the
candidate netlist's own `c_width`/`c_length`; `layout/gen_gate_driver_core.py`'s
resistor constants (350 ohm/sq `ppolyf_u`, 0.42 um unit width, `res_array`
fold: units <= 80 um, 8 per row, 0.5 um unit spacing); the added MOS cells
drawn by `klt gen mos_array` at the same params shape the layout generator
uses; and the committed `layout/gate_driver_core.provenance.json` /
`klt stats layout/gate_driver_core.gds` for the present-day comparison.

| Added class | Count | Unit size | Unit area | Total |
|---|---|---|---|---|
| `pnp_05p00x05p00` (Q1 m=1, Q2 m=8) | 9 | 8.28 x 8.28 um | 68.6 um2 | **617 um2** |
| `cap_mim_2f0_m4m5_noshield` (`XCC`) | 1 | 40 x 40 um | 1600 um2 | **1600 um2** |
| small-signal MOS (MP1-3, MNIB, MAMP1/2, MALP1/2, MATAIL, MSENSE, MKICK) | 11 | W2-10 um, L=2 um | 31.8-75.0 um2 | **595 um2** |

The eleven MOS cells, drawn (`klt gen mos_array`, `gf180mcuD`): pfet W5 L2
48.5 um2 x5, nfet W5 L2 48.0 um2 x2, nfet W10 L2 75.0 um2 x3, nfet W2 L2
(MKICK) 31.8 um2. The candidate also *deletes* the baseline's `MREF`
(-51.9 um2, from the committed provenance).

Resistors, as base `ppolyf_u` (350 ohm/sq) at the layout generator's 0.42 um
unit width — strip length = R * w / rho, strip area = length * w, and a
folded-block estimate at the fold overhead the committed GDS itself realises
(the 16 MOhm `Rfb` block draws 16057 um2 for 8064 um2 of poly, 1.99x; the
800k `Rref` 2.04x — so ~2.0x throughout):

| Resistor | Value | Poly length | Units (<= 80 um) | Strip area | Block est. (~2x) |
|---|---|---|---|---|---|
| `Rsa` | 275 k | 330 um | 5 x 66 um | 138.6 um2 | 277 um2 |
| `Rsb` | 275 k | 330 um | 5 x 66 um | 138.6 um2 | 277 um2 |
| `Rp` | 27 k | 32.4 um | 1 | 13.6 um2 | 27 um2 |
| `R1` | 960 k | 1152 um | 16 x 72 um | 483.8 um2 | 968 um2 |
| `R2` | 450 k | 540 um | 9 x 60 um | 226.8 um2 | 454 um2 |
| `Rdet` | 20 M | 24000 um | 300 x 80 um | 10080 um2 | **20160 um2** |
| `Rfb` | 50 M | 60000 um | 750 x 80 um | 25200 um2 | **50400 um2** |

**Totals against the present UVLO and the block outline:**

| | Area |
|---|---|
| candidate additions, resistors (blocks) | ~72.6k um2 |
| candidate additions, PNP + MIM + MOS | ~2.8k um2 |
| **candidate additions, total** | **~75.4k um2** |
| present UVLO (sum of committed blocks: `MPD` 15315 + ten small devices 679 + four resistor blocks 17995) | ~34.0k um2 |
| block outline (`klt stats layout/gate_driver_core.gds` bbox 1774.46 x 813.18 um) | 1442.6k um2 |

So the candidate as measured would add **~2.2x the present UVLO's entire
footprint** (~5.2 % of the block outline), and **the 50 MOhm `Rfb` alone
(50.4k um2) is 67 % of that — larger than the whole present UVLO**. Together
the two rail-spanning megaohm resistors (`Rfb` + `Rdet`) are ~94 %. Everything
else — nine PNPs, the MIM cap, eleven MOS, five precision resistors — fits in
~4.9k um2, less than a third of the present UVLO.

## What limits the 50 MOhm, and the smaller-area proposal

The value is set by the hysteresis sizing on the 1.23 V reference at the
divider's ~3.5 uA operating point; the limit is the **sheet resistance
available**: base `ppolyf_u` at 350 ohm/sq makes 50 MOhm 143k squares, i.e.
60 mm of 0.42 um poly (the issue's own arithmetic). Lowering the value
instead would need a proportionally larger divider current (more Iq) or less
hysteresis — both change measured behaviour and are out of scope here.

**Proposal (analysis only, no layout edit): draw `Rfb` and `Rdet` in the
high-sheet flavour `ppolyf_u_2k_6p0`** (2000 ohm/sq typ, 1600/2400 ff/ss —
the same +/-20 % family spread as base `ppolyf_u`; the high-Rs flavour
qualified for the 6.0 V area, which matters because both resistors span the
full `VDD_DRV` rail). At the same 0.42 um width that drops `Rfb` to 10.5 mm /
4.4k um2 strip (~8.8k um2 block) and `Rdet` to 4.2 mm / 1.8k um2 strip
(~3.5k um2 block): the candidate's additions fall to **~17.2k um2 — about
half the present UVLO and 1.2 % of the block outline.** The trade, stated:

- *Behaviour kept:* the ohms are solved by geometry, so the measured
  hysteresis is unchanged by construction — and this is not hypothetical:
  the sibling gate-2 re-measurement (PR #564, record 0025, open at the time
  of writing) already runs the full 15-corner trip grid with `Rfb`/`Rdet`
  drawn as `ppolyf_u_2k_6p0` and passes 15/15 with a 35 mV falling spread.
  That measurement draws them at `r_width=1u` (24.0 mm for `Rfb`), chosen so
  the *ratio*-critical resistors share one exact width; at 0.42 um the same
  devices halve again, but the width tolerance of a non-ratio resistor is
  the implementer's call, not this estimate's.
- *Family spread:* +/-20 % on `Rfb` moves the `Rfb`-component of the
  hysteresis by +/-20 %. Hysteresis carries a typical value only in DR-0001
  Decision 4 (no ratified worst-case bound), and `Rfb` does not move either
  trip window (the `R1`/`R2` divider does), so no ratified quantity shifts.
- *Residual:* high-sheet poly generally matches and voltage-derates worse
  than base poly. `Rfb`/`Rdet` set no precision quantity here (hysteresis
  width and a kick-gate bias), which is why the trade is acceptable — but a
  layout that takes this should re-measure hysteresis over the `res_*`
  corners with the flavour live, exactly the way PR #564 did for the trips.

The PNPs are a non-issue: nine 8.28 um cells (617 um2) is 0.8 % of the
candidate's cost — "medium-voltage devices are the point" of this block, and
the first `pnp_05p00x05p00` fleet evidence on the 5 V rail is study 2's, not
a layout risk.

## Reproduce (gates 3 and 4)

```bash
cd sim/uvlo-reference-study/klt
python3 gen_startup_requests.py        # regenerates the twelve requests
klt sim --backend batch --wait-for-capacity 600 --max-in-flight 4 \
  --batch-set request-startup-ramp-slow.json request-startup-ramp-harness.json \
  request-startup-ramp-fast.json request-startup-ramp-vfast.json \
  request-startup-ramp-1ns.json request-startup-hold-2v0.json \
  request-startup-hold-3v0.json request-startup-hold-5v0.json \
  request-startup-brownout.json request-startup-deadinit-2v0.json \
  request-startup-deadinit-5v0.json request-startup-deadinit-2v0-nokick.json \
  --report-out ../envelopes/<date>-<sha>-klt-sim-uvlo-bandgap-startup.json \
  -o ../envelopes/<date>-<sha>-uvlo-bandgap-startup/ --format json
```

The committed envelope was produced with klt `0.9.3.dev2575+g6bd18bbc8637`
against runner `0.9.0` (`runner_compatibility: match`), ngspice `47`, PDK
`gf180mcuD` / `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`
(`models_lib_sha256 f6f4a96e…` — the same install and ambiguity the 0024
trip envelope records), 12 batch jobs, all `state=done`. The aggregate
envelope's `status: fail` is the negative-control member's graded FAIL — the
designed outcome; every `MKICK`-present member reports `pass`. The gate-4
tables re-derive from the PDK GDS, `klt gen mos_array`, and the committed
layout provenance as cited inline.
