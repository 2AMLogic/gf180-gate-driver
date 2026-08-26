# `uvlo` — comparator/reference sizing and tuning history

- **Cell**: [`design/uvlo.sch`](uvlo.sch) / [`design/uvlo.sym`](uvlo.sym)
- **Spec constraint**: [`spec/gate-driver.md` §5](../spec/gate-driver.md),
  ratified numeric targets in
  [`spec/decision-records/0001-block-interface-and-uvlo-parameters.md`](../spec/decision-records/0001-block-interface-and-uvlo-parameters.md)
  Decisions 4–5.
- **Scope**: schematic-level sizing derivation and the manual tuning
  iterations used to arrive at the committed component values — not a
  layout deliverable (issue #220 is schematic + pre-layout PVT verification;
  layout is #221). Measured PVT results are recorded in
  [`sim/uvlo-trip-verification/records/`](../sim/uvlo-trip-verification/records/)
  and analyzed in
  [`spec/decision-records/0018-uvlo-comparator-pvt-measurement.md`](../spec/decision-records/0018-uvlo-comparator-pvt-measurement.md) —
  this document is the design rationale, that record is the evidence.

## Domain — single DNWELL group, no partition table needed

Unlike `level_shifter` (which spans the 3.3 V/5–6 V boundary and therefore
needs [`design/level-shifter-partition.md`](level-shifter-partition.md)'s
device-by-device DNWELL table), `uvlo` is entirely inside the drive-rail
domain: every device is `nfet_06v0`/`pfet_06v0`, there is no `VDD_LOGIC`/
`GND_LOGIC` pin at all (decision record 0001 Decision 5: "only `VDD_DRV` is
monitored"), and every bulk ties to either `VDD_DRV` (PMOS) or `GND_DRV`
(NMOS) — no thin-oxide device, so DRM 7.2's "3.3 V and 5 V/6 V not in the
same DNWELL" rule has nothing to violate here; the whole cell co-locates
with `level_shifter`/`output_stage`'s own `DNWELL_DRV` group.

## Topology (decision record 0001 Decision 5's literal choice)

A resistive divider off `VDD_DRV` compared against a diode-connected
`nfet_06v0` `Vt` reference:

```
Reference:  VDD_DRV --[Rref]-- nref --[MREF diode-connected]-- GND_DRV
Divider:    VDD_DRV --[R1]-- ndiv --[R2]-- GND_DRV
Hysteresis: uvlo_ok --[Rfb]-- ndiv   (positive feedback, see below)
Comparator: 5T differential pair (MTAIL/MINP/MINN/MLOADP/MLOADN),
            gates on ndiv (+) / nref (-), single-ended output ncompn
Buffer:     ncompn -> INV1 -> lockout -> INV2 -> uvlo_ok
Output:     MPD (nfet_06v0, W=10u m=800), gate=lockout, drain=OUT,
            source=GND_DRV -- the active-low pulldown
```

No bandgap exists in this block (decision record 0001 Decision 5's own
stated tradeoff), so the reference is necessarily a device-`Vt`-based level,
not a temperature/process-stable voltage — this is the root cause of the
wide measured PVT spread analyzed in decision record 0018, not a sizing
mistake in what follows.

## Hysteresis derivation (resistive positive feedback)

`Rfb` connects the buffered digital output `uvlo_ok` (swings ~0V..`VDD_DRV`)
back onto the divider tap `ndiv`, alongside `R1`/`R2`. This produces two
different effective divider networks depending on which state the
comparator is currently in — the standard resistive-Schmitt-trigger
technique:

- **Currently locked out** (`uvlo_ok` ≈ 0V, in parallel with `R2`'s path to
  `GND_DRV`): effective bottom resistance is `R2 || Rfb` (slightly less than
  `R2`), top is `R1`. This network is active while `VDD_DRV` is rising, so
  it determines the **rising** (release) threshold:
  `V_rising = V_ref * (R1 + R2||Rfb) / (R2||Rfb)`.
- **Currently released** (`uvlo_ok` ≈ `VDD_DRV`, in parallel with `R1`'s
  path to `VDD_DRV`): effective top resistance is `R1 || Rfb` (slightly less
  than `R1`), bottom is `R2`. Active while `VDD_DRV` is falling, so it
  determines the **falling** (lockout) threshold:
  `V_falling = V_ref * (R1||Rfb + R2) / R2`.

Since `R1||Rfb < R1`, `V_falling < V_rising` by construction — the correct
hysteresis direction (decision record 0001 Decision 4: falling typ 3.6 V <
rising typ 3.9 V).

## Component values and the tuning iterations that produced them

`MREF` (`nfet_06v0`, `W=10u L=0.7u`, diode-connected) biased through
`Rref=800k` from `VDD_DRV` measures `V_ref ≈ 0.73–0.76 V` at `tt`/27 °C
across `VDD_DRV` = 3.6–5.5 V (a DC sweep of the reference branch alone,
`nfet_06v0`'s published linear-region `VT0` is 0.61/0.73/0.85 min/typ/max —
see `design/device-characterization.md` — consistent with this being close
to, but not exactly, a pure threshold voltage since `MREF` carries a real
bias current, not the PDK table's zero-current linear-`Vt` test condition).

Starting from `V_ref ≈ 0.75 V` and decision record 0001 Decision 4's typ
targets (falling 3.6 V, rising 3.9 V), a first-pass hand solve of the two
equations above (picking `R2 = 200k` as a convenient anchor) gave
`R1 ≈ 840k`, `Rfb ≈ 11 M` — simulated (transient triangle-wave ramp, see
below) at `tt`/27 °C: falling 3.40 V, rising 3.80 V, hysteresis 393 mV.
Falling/rising were both ~200 mV low and hysteresis ~90 mV wide of target,
so `R1` was raised to `880k` (raises both thresholds together, by
`ΔV ≈ V_ref/R2 * ΔR1`) and `Rfb` raised to `16 M` (weakens the feedback,
narrowing hysteresis) — re-simulated: falling 3.606 V, rising 3.930 V,
hysteresis 324 mV, matching decision record 0001's typ targets (3.6 V /
3.9 V / 300 mV) closely. These are the committed values:

| Component | Value | Role |
|---|---|---|
| `Rref` | 800k | Biases `MREF`'s reference current |
| `MREF` | `nfet_06v0` W=10u L=0.7u, diode-connected | `Vt` reference |
| `R1` | 880k | Divider top (VDD_DRV → ndiv) |
| `R2` | 200k | Divider bottom (ndiv → GND_DRV) |
| `Rfb` | 16000k (16 M) | Positive-feedback hysteresis resistor |
| `MTAIL` | `nfet_06v0` W=20u L=0.7u | Tail current mirror (mirrors `MREF`'s bias) |
| `MINP`/`MINN` | `nfet_06v0` W=15u L=0.7u each | Differential pair (bulk tied to `GND_DRV`, not their own source/tail node — see below) |
| `MLOADP`/`MLOADN` | `pfet_06v0` W=15u L=0.55u each | Current-mirror load |
| `MPINV1`/`MNINV1` | `pfet_06v0` W=10u / `nfet_06v0` W=5u | Buffer stage 1 (ncompn → lockout) |
| `MPINV2`/`MNINV2` | `pfet_06v0` W=20u / `nfet_06v0` W=10u | Buffer stage 2 (lockout → uvlo_ok, drives `Rfb`) |
| `MPD` | `nfet_06v0` W=10u L=0.7u **m=800** | OUT pulldown |

**Why `MINP`/`MINN`'s bulk ties to `GND_DRV`, not `ntail`**: an earlier draft
tied the differential pair's bulk to their own source (`ntail`, the tail
node) — a mistake caught by `layout/lvs/test_make_reference.py`'s
`test_nfet_bodies_all_tie_to_the_merged_ground_net` (issue #220's own CI
run): gf180mcu is a bulk process with one shared p-substrate per NMOS
(confirmed by every other NMOS in this repo tying to `gnd_logic`/`gnd_drv`,
never to its own source unless that source already *is* ground), so tying
body to the tail node — which sits at a real, current-dependent bias above
ground — is a body-effect error, not a valid "diode-tie" simplification. The
committed schematic ties both to `GND_DRV`, matching every other grounded
NMOS in this design.

**Why `MPD` is `W=10u m=800`**: `output_stage`'s own final push-pull stage
(`design/output_stage.sch`'s `MP6`, `pfet_06v0 W=10u m=500`, effective
5000 µm) is the strongest device `MPD` might need to override — `MPD`'s
`m=800` (effective 8000 µm) gives comfortable margin so the pulldown's `Ron`
dominates even when `output_stage` is actively trying to drive `OUT` high.

## Why a transient triangle-wave ramp, not a `.dc` sweep, for verification

`design/uvlo.sch`'s comparator is a regenerative (Schmitt-trigger-style)
positive-feedback circuit by design — that is what creates the hysteresis
above. A raw `.dc` sweep asks ngspice to find a *single* nonlinear operating
point at each swept value via Newton continuation from the previous point;
near the circuit's actual flip point that continuation becomes numerically
close to singular and required repeated gmin-stepping recovery at nearly
every point in the transition region during this issue's own tuning
iterations — observed directly to take several minutes (or longer) per
corner, and once required manually aborting the run. A slow transient
triangle-wave ramp of `VDD_DRV` (0 V → 6 V over 20 µs, then back down over
another 20 µs — many orders of magnitude slower than the comparator's own
bandwidth, so quasi-static in every sense that matters for a trip-voltage
measurement) sidesteps this entirely and is what
`sim/uvlo-trip-verification/run_uvlo_trip.py` uses — see that script's
module docstring for the full account, and
`spec/decision-records/0018-uvlo-comparator-pvt-measurement.md` for the
measured PVT results this tuning produced.
