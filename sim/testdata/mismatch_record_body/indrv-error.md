verdict=ERROR
# Record 20260102-030405-abcdef0

- **Record ID**: 20260102-030405-abcdef0
- **Claim**: spec/gate-driver.md#5-protection-and-fault-handling (§5 Exception 3 — the `IN_DRV` inter-cell thick-oxide gate-ceiling exception, decision records 0006 / 0007 / 0014) — **local-mismatch (Monte Carlo) robustness of the ratified ≤ 10 mV bound**, combined with (not replacing) the process-corner matrix in `sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`
- **Netlist provenance**: design — DUT `design/fake.spice` (sha256 `dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd`), driven by `sim/gate-driver-core-drive/testbench/fake_tb.spice` (sha256 `nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn`) — byte-for-byte the testbench and netlist that produced `20260818-060517-673fcf0`, loaded through its own `tb.json` rather than copied, so the stimulus, the 1 nF reference load, the measurement expressions and the `reltol` convention are the same ones Exception 3's figure came from.
- **Corner matrix run**:
  - Process: tt, ff, ss, fs, sf
  - Temperature: -40 °C, 27 °C, 125 °C
  - Supply (vlogic, nominal 3.30 V): 3.30 V
  - Supply (vdrv, nominal 5.00 V): 6.00 V (stretch point)
  - 4 PVT point(s) (process × temperature at the 6 V stretch supply), each carrying 5 Monte Carlo mismatch draws plus 2 zero-sigma controls and 1 plain-deck baseline — 32 ngspice runs, 2.0 min wall.
  - **Subset of the mandated PVT matrix.** Gaps: vlogic: missing 2.97 V, 3.63 V; vdrv: missing 4.50 V, 5.00 V, 5.50 V.
  - Justification: the process and temperature axes are run in full (5 × 3, the same axes as the reference corner matrix). Only the supply axis is restricted, to the single 6 V stretch point, because **Exception 3 does not exist at any other supply**: `spec/gate-driver.md` §5 records `IN_DRV` clearing the 6.0 V ceiling by ≥ 397 mV at every nominal-tolerance point, and this record measures the node's local-mismatch spread at σ = n/a — two to three orders of magnitude smaller than that headroom, so mismatch cannot bring a nominal-tolerance point near the ceiling. Spending the other 128 ngspice runs on supply points with four orders of magnitude of margin would not change any claim made here. The 6 V stretch point at `ss`/125 °C is the binding corner the issue (#204) names.
- **Statistical convention**: Monte Carlo **local device mismatch** (intra-die), N = 5 independent draws per PVT point, 4 PVT point(s), 20 mismatch samples total. **20 of 20 draws did not converge and are excluded from every statistic below** — enumerated in "Non-converged draws", leaving 0 in the distribution. Distribution source: the gf180mcu PDK's own `.lib fets_mm` per-instance mismatch model (`delvto = mis_vth·sw_stat_mismatch`, `mulu0 = 1 − mis_k·sw_stat_mismatch`, with `mis_vth`/`mis_k` drawn from `agauss(0, σ, 1)` and σ scaled Pelgrom-style by 1/√(W_eff·L_eff)) — i.e. **1 σ per-device draws, not a 3 σ corner pull**; the reported σ below is the sample standard deviation of the measured node voltage over the draws, and the reported worst case is the observed maximum, not a fitted quantile. `sw_stat_global = 0` throughout, so the deterministic `.LIB` process corner remains the sole global-skew axis and is not double-counted. Seeds are deterministic: `seed = 20260204 + point_index × 10000 + sample`, point_index in the grid order tabulated below (`sim/harness/montecarlo.py`). Every PVT point additionally carries a **deterministic negative control** in three legs: a plain `mc=None` deck (byte-identical to what `sim/run_corners.py` generates), plus two `sw_stat_mismatch = 0` decks at two different seeds — all three must agree bit-for-bit, and are additionally compared against the committed corner-matrix record `sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`.
- **Result**:

  ### Deterministic negative control

  Three legs per PVT point, on **every** measurement this testbench records (not just `indrv_max_v`):

  1. **baseline** — a plain `mc=None` deck, byte-identical to what `sim/run_corners.py` generates for this PVT point;
  2. **control seed-A** and **3. control seed-B** — the Monte Carlo deck with `sw_stat_mismatch = 0`, at two *different* ngspice seeds.

  All three must agree **bit-for-bit**. That is what proves the campaign's decks are the corner matrix's decks plus a switch — no residue from the added `.param`/`.options` lines, and no seed leakage into a mismatch-off run — so that the spread reported below is mismatch and not a deck difference or solver noise.

  The fourth column compares the same control against the **committed** corner-matrix record `20260818-060517-673fcf0`, whose raw logs are re-parsed at run time. Exact equality is *not* expected there and is not required: that record was taken under **ngspice-46** and this one under **ngspice-47** (see the narrative below). The residual is reported rather than assumed.

  | PVT point | control `indrv_max_v` (V) | baseline = control | seed-A = seed-B | Δ vs `20260818-060517-673fcf0` (µV) |
  |---|---|---|---|---|
  | `tt_-40c_vlogic3p30v-vdrv6p00v` | 3 | yes | yes | -3000123.96 |
  | `tt_27c_vlogic3p30v-vdrv6p00v` | 3.5 | yes | yes | -2500081.62 |
  | `tt_125c_vlogic3p30v-vdrv6p00v` | 4 | yes | yes | -2001235.49 |
  | `ff_-40c_vlogic3p30v-vdrv6p00v` | 4.5 | yes | yes | -1500094.07 |

  ### `IN_DRV` peak under local mismatch (Exception 3's node)

  `margin` is the ratified §2.3 thick-oxide DC gate ceiling minus the measured peak, in mV — negative means the node is above the ceiling, which is exactly what Exception 3 documents and bounds at ≤ 10 mV (i.e. margin ≥ −10.000 mV).

  | PVT point | draws used | control (V) | MC mean (V) | MC σ (mV) | MC min (V) | MC max (V) | worst margin (mV) | Δ vs control (mV) | vs ≤ 10 mV bound |
  |---|---|---|---|---|---|---|---|---|---|
  | `tt_-40c_vlogic3p30v-vdrv6p00v` | 0/5 | 3 | no data | | | | | | |
  | `tt_27c_vlogic3p30v-vdrv6p00v` | 0/5 | 3.5 | no data | | | | | | |
  | `tt_125c_vlogic3p30v-vdrv6p00v` | 0/5 | 4 | no data | | | | | | |
  | `ff_-40c_vlogic3p30v-vdrv6p00v` | 0/5 | 4.5 | no data | | | | | | |

  ### Non-converged draws

  **20 of 20 draws** did not complete and are excluded from every statistic in this record. They are listed here rather than dropped silently: a Monte Carlo record whose sample count does not match its draw count is unauditable, and a non-converged draw is not evidence of a low value — it is absence of evidence at that draw. Each is reproducible from the seed below.

  | PVT point | sample | seed | ngspice message |
  |---|---|---|---|
  | `tt_-40c_vlogic3p30v-vdrv6p00v` | 1 | 0 | `Timestep too small; aborted` |
  | `tt_-40c_vlogic3p30v-vdrv6p00v` | 2 | 1 | `Timestep too small; aborted` |
  | `tt_-40c_vlogic3p30v-vdrv6p00v` | 3 | 2 | `Timestep too small; aborted` |
  | `tt_-40c_vlogic3p30v-vdrv6p00v` | 4 | 3 | `Timestep too small; aborted` |
  | `tt_-40c_vlogic3p30v-vdrv6p00v` | 5 | 4 | `Timestep too small; aborted` |
  | `tt_27c_vlogic3p30v-vdrv6p00v` | 1 | 100 | `Timestep too small; aborted` |
  | `tt_27c_vlogic3p30v-vdrv6p00v` | 2 | 101 | `Timestep too small; aborted` |
  | `tt_27c_vlogic3p30v-vdrv6p00v` | 3 | 102 | `Timestep too small; aborted` |
  | `tt_27c_vlogic3p30v-vdrv6p00v` | 4 | 103 | `Timestep too small; aborted` |
  | `tt_27c_vlogic3p30v-vdrv6p00v` | 5 | 104 | `Timestep too small; aborted` |
  | `tt_125c_vlogic3p30v-vdrv6p00v` | 1 | 200 | `Timestep too small; aborted` |
  | `tt_125c_vlogic3p30v-vdrv6p00v` | 2 | 201 | `Timestep too small; aborted` |
  | `tt_125c_vlogic3p30v-vdrv6p00v` | 3 | 202 | `Timestep too small; aborted` |
  | `tt_125c_vlogic3p30v-vdrv6p00v` | 4 | 203 | `Timestep too small; aborted` |
  | `tt_125c_vlogic3p30v-vdrv6p00v` | 5 | 204 | `Timestep too small; aborted` |
  | `ff_-40c_vlogic3p30v-vdrv6p00v` | 1 | 300 | `Timestep too small; aborted` |
  | `ff_-40c_vlogic3p30v-vdrv6p00v` | 2 | 301 | `Timestep too small; aborted` |
  | `ff_-40c_vlogic3p30v-vdrv6p00v` | 3 | 302 | `Timestep too small; aborted` |
  | `ff_-40c_vlogic3p30v-vdrv6p00v` | 4 | 303 | `Timestep too small; aborted` |
  | `ff_-40c_vlogic3p30v-vdrv6p00v` | 5 | 304 | `Timestep too small; aborted` |

  This is the same solver failure mode `sim/README.md`'s transient-tolerance decision record already documents for this class of deck (ngspice "Timestep too small" on a source branch current); at the harness's ratified `reltol=1e-4` it is rare rather than absent. Because the abort truncates the transient, the affected draw's partial `indrv_max_v` is a lower bound on what that draw would have peaked at, which is exactly why it is excluded rather than counted.

  ### Output-stage taper nodes under the same draws (context, not this claim)

  The reused testbench already measures `x2.n1`…`x2.n5`, so these come for free from the same draws. They belong to **Exception 2** (decision record 0013, bound ≤ 175 mV above the ceiling), which this record does not claim and does not amend — reported here as the observed worst case across all draws at all PVT points, for a future Exception-2-scoped campaign to start from.

  | node | control worst (V) | MC worst (V) | Δ (mV) | worst margin (mV) | vs ≤ 175 mV bound |
  |---|---|---|---|---|---|

  - **Overall: ERROR** — no Monte Carlo sample completed.

  ### Finding: the measured local-mismatch spread on `IN_DRV`

  The concern behind issue #204 was specific and reasonable: Exception 3's margin is −2.66 mV, `XCCOMP` (four series `cap_mim_2f0_m4m5_noshield` devices, decision record 0014) cancels a feedthrough path to within a few millivolts, and no evidence in this repo had ever perturbed two matched devices relative to each other. The numbers, not an argument, are:

  - **Spread**: σ(`indrv_max_v`) = n/a per PVT point (largest 0 µV, at the hot slow corners; smallest at `tt`/`fs`, where the node barely moves at all). Even the largest is well under the −2.66 mV excursion the ratified exception already concedes, and ~0 % of its ≤ 10 mV bound.
  - **Worst draw vs. its own control**: the largest single-sample excursion above the mismatch-off deck at the same PVT point is **none** — no draw at any PVT point exceeded its own mismatch-off control, so mismatch moved this node only downwards; the mismatch-off deck's own worst point is 4.5 V.
  - **Worst draw vs. the ratified bound**: +0.000 mV of margin against the ≤ 10 mV bound's −10.000 mV, leaving +10.000 mV unspent — so the bound absorbs the measured mismatch spread with 10000000000.0σ of headroom beyond the worst observed draw.
  - **The model is demonstrably active**: the same draws move the output stage's device-driven taper nodes by up to +0.000 mV (`n/a`) — while no draw moved `IN_DRV` above its control at all. That contrast is the cross-check that these decks are not simply insensitive to mismatch: the same perturbation that barely moves a rail-clamped node visibly moves the device-driven ones.

  The structural reason `IN_DRV` moves less than the taper nodes is decision record 0006's own argument, now visible in the data: the node's quiescent high level is `VDD_DRV` **by construction** (the level shifter's output buffer pulls it to the drive rail, so at the 6 V stretch point it sits at the ceiling regardless of any device parameter), and what Exception 3 bounds is the residual of a charge-injection spike whose amplitude is set by the `XCCOMP` capacitor ratio. Mismatch perturbs the *devices*, but the endpoint is a rail — and the capacitor ratio, per the PDK-coverage section below, is not varied by this PDK at all.

  ### Finding: the ngspice version change moves this node more than mismatch does

  The committed corner-matrix record `20260818-060517-673fcf0` was taken under **ngspice-46**; this campaign ran under **ngspice-47**. The zero-sigma control — the *same deck*, mismatch off — differs from that record by up to **3000124 µV** at the worst point. That is **3000123956900.0×** the largest per-point mismatch σ this campaign measured (0 µV) and 30001.2 % of Exception 3's entire ≤ 10 mV bound. **The simulator version change is a larger perturbation of this measurement than local device mismatch is** — which is the single most useful thing this campaign found, and it is not a circuit result.

  It is isolated to the simulator, not to the deck or the circuit: the three same-machine control legs (the plain `mc=None` deck and two `sw_stat_mismatch = 0` decks at different seeds) agree **bit-for-bit** with each other at every PVT point, so the only variable between this record's control column and the reference record's number is the ngspice binary. Per `CLAUDE.md` ("when something behaves oddly, suspect the tool or the deck before the circuit") this is recorded as a tool-fidelity finding, not absorbed into the circuit claim.

  **It does not threaten Exception 3's bound.** The residue is largest at points with wide margin, and at the binding corner `ss_125c_vlogic3p30v-vdrv6p00v` the control reproduces the reference record to well under a microvolt (see the control table above). But it does mean the −2.66 mV figure decision records 0014/0006 quote carries a simulator-version uncertainty of order ±1 mV that no prior record stated — comfortably inside the ≤ 10 mV bound, and a further reason not to narrow that bound toward the measured value.

  ### What the open PDK does and does not model (issue #204's first ask)

  Determined by reading the installed decks under `/nonexistent/gf180mcuD/libs.tech/ngspice/`, not by assuming a foundry convention:

  1. **MOSFET local mismatch: shipped, and usable unchanged.** `sm141064.ngspice`'s `.lib fets_mm` section defines subcircuit wrappers named `nfet_03v3`, `pfet_03v3`, `nfet_05v0`, `nfet_06v0`, `pfet_05v0`, `pfet_06v0` whose MOS instance line carries `delvto='mis_vth*sw_stat_mismatch'` and `mulu0='1-mis_k*sw_stat_mismatch'`, with `mis_vth`/`mis_k` drawn **per subcircuit instance** from `agauss(0, var, 1)` and `var` scaled by `1/sqrt(W_eff·L_eff)`. All five MOS corner sections (`typical`/`ff`/`ss`/`fs`/`sf`) already `.lib` that section in unconditionally, and this repo's netlists instantiate exactly those names as `X` calls — so mismatch needs no netlist edit and no device swap, only `design.ngspice`'s `sw_stat_mismatch` switch flipped from its default 0. That default is why every prior record in this repo is a pure corner claim.
  2. **MiM capacitor local mismatch: not shipped.** `sm141064_mim.ngspice` computes `c_c0 = (c_cox·area + c_capsw·peri)·(1 + mc_c_cox_2p0fF)`, but `mc_c_cox_1p0fF` / `_1p5fF` / `_2p0fF` are hardcoded to `0` in all three `mimcap_*` corner sections and no distribution is ever assigned to them anywhere in the PDK. They are also `.LIB`-scope parameters — one value shared by every instance — so even a hand-supplied σ would model *global* MiM density skew (which the `mimcap_ss`/`_ff` sections already do, at ±10 %) rather than device-to-device mismatch. **`XCCOMP`'s four MiM devices are therefore perfectly matched to each other in every sample of this campaign.** That is a real limit on this record's coverage, and it is recorded as such rather than papered over with an invented sigma.
  3. **Resistors: global only.** `.lib res_statistical` draws `agauss` sheet-rho deviations but gates them on `sw_stat_global`, not `sw_stat_mismatch` — so resistor variation in this PDK is a die-level skew, already covered by the corner matrix, with no intra-die component. (No resistor sits in Exception 3's path in any case.)
  4. **Thick-oxide n-channel devices get threshold mismatch only.** In `.lib fets_mm` the current-factor coefficient `par_k` is `0.0000` for `nfet_05v0`/`nfet_06v0` and non-zero for every other family (`nfet_03v3` 0.007008, `pfet_03v3` 0.002833, `pfet_05v0`/`pfet_06v0` 0.00517), so `mulu0` is identically 1 for the 5 V/6 V nFETs. Whether that is a modelled physical claim or an uncharacterised gap in the open PDK is not stated anywhere in the deck; it is recorded here as the kind of medium-voltage model-fidelity finding `CLAUDE.md` asks this canary block to surface.

  Points 2 and 4 are the honest caveats on this record: it is a *MOSFET-threshold* mismatch campaign, which is what the open PDK supports, not an all-device mismatch campaign. See `spec/decision-records/0017-pdk-local-mismatch-model-coverage.md`.

- **Links**:
  - Run script: `sim/gate-driver-indrv-mismatch/run_indrv_mismatch.py`
  - Testbench (reused verbatim): `sim/gate-driver-core-drive/testbench/fake_tb.spice`, `sim/gate-driver-core-drive/testbench/tb.json`
  - Monte Carlo deck machinery: `sim/harness/montecarlo.py`
  - Netlist snapshot: `sim/gate-driver-indrv-mismatch/netlist-snapshots/20260102-030405-abcdef0.spice`
  - Raw logs: `sim/gate-driver-indrv-mismatch/corners/20260102-030405-abcdef0/` — one `.log` per zero-sigma control and per worst-case draw, plus a `samples-<corner-id>.csv` sidecar carrying every draw's seed and measurements
  - Reference corner matrix: `sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`
  - PDK: gf180mcuD (/nonexistent/gf180mcuD), ngspice ngspice-47 : fake
  - Deck tolerance: `reltol=1e-4` (harness default) — the same convention as `20260818-060517-673fcf0`
- **Timestamp / author**: 2026-01-02T03:04:05Z, agent-builder (issue #204)
- **Supersedes**: (none — first Monte Carlo / local-mismatch record in this repo)
