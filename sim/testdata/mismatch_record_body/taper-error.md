verdict=ERROR
# Record 20260102-030405-abcdef0

- **Record ID**: 20260102-030405-abcdef0
- **Claim**: spec/gate-driver.md#5-protection-and-fault-handling (§5 Exception 2 -- the output stage's internal taper nodes `n1`...`n5`, decision record 0013) -- **local-mismatch (Monte Carlo) robustness of the ratified ≤ 175 mV bound**, combined with (not replacing) the process-corner matrix in `sim/output-stage-drive/records/20260817-202802-d7bda87.md`
- **Netlist provenance**: design -- DUT `design/fake.spice` (sha256 `dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd`), driven by `sim/output-stage-drive/testbench/fake_tb.spice` (sha256 `nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn`) -- byte-for-byte the testbench and netlist that produced `20260817-202802-d7bda87`, loaded through its own `tb.json` rather than copied. **Provenance caveat** (disclosed, not silently assumed): this testbench drives `IN_DRV` from an ideal 1 ns-edge source with no level shifter present, which is the same driving condition decision record 0005's *original* number used, not the end-to-end real level-shifter edge decision record 0006's amendment (and decision record 0013's own cited worst case) later measured under `sim/gate-driver-core-drive/`. This campaign follows issue #211's own explicit instruction to target this testbench; see the module docstring for the full discrepancy note.
- **Corner matrix run**:
  - Process: tt, ff, ss, fs, sf
  - Temperature: -40 °C, 27 °C, 125 °C
  - Supply (vdrv, nominal 5.00 V): 6.00 V (6 V stretch point)
  - 4 PVT point(s) (process × temperature at the 6 V stretch supply), each carrying 5 Monte Carlo mismatch draws plus 2 zero-sigma controls and 1 plain-deck baseline -- 32 ngspice runs, 2.0 min wall.
  - **Subset of the mandated PVT matrix.** Gaps: vdrv: missing 4.50 V, 5.00 V, 5.50 V.
  - Justification: the process and temperature axes are run in full (5 × 3, the same axes as the reference corner matrix). Only the supply axis is restricted, to the single 6 V stretch point, because **Exception 2 does not exist at any other supply**: decision records 0004/0005/0013 record the taper nodes clearing the 6.0 V ceiling at every nominal-tolerance point (4.5/5.0/5.5 V), only exceeding it at the 6 V stretch rail. Spending the other 96 ngspice runs on supply points with no exception to characterize would not change any claim made here.
- **Statistical convention**: Monte Carlo **local device mismatch** (intra-die), N = 5 independent draws per PVT point, 4 PVT point(s), 20 mismatch samples total. **20 of 20 draws did not converge and are excluded from every statistic below** -- enumerated in "Non-converged draws", leaving 0 in the distribution. Distribution source: the gf180mcu PDK's own `.lib fets_mm` per-instance mismatch model (`delvto = mis_vth·sw_stat_mismatch`, `mulu0 = 1 − mis_k·sw_stat_mismatch`, with `mis_vth`/`mis_k` drawn from `agauss(0, σ, 1)` and σ scaled Pelgrom-style by 1/√(W_eff·L_eff)) -- i.e. **1 σ per-device draws, not a 3 σ corner pull**; the reported σ below is the sample standard deviation of the measured worst-taper-node voltage over the draws, and the reported worst case is the observed maximum, not a fitted quantile. `nfet_06v0`/`pfet_06v0` -- the only device families in `design/output_stage.sch` (spec §2.5) -- carry threshold mismatch only (`par_k = 0.0000`, no β mismatch), per decision record 0017. `sw_stat_global = 0` throughout, so the deterministic `.LIB` process corner remains the sole global-skew axis and is not double-counted. Seeds are deterministic: `seed = 20260225 + point_index × 10000 + sample`, point_index in the grid order tabulated below (`sim/harness/montecarlo.py`). Every PVT point additionally carries a **deterministic negative control** in three legs: a plain `mc=None` deck (byte-identical to what `sim/run_corners.py` generates), plus two `sw_stat_mismatch = 0` decks at two different seeds -- all three must agree bit-for-bit, and are additionally compared against the committed corner-matrix record `sim/output-stage-drive/records/20260817-202802-d7bda87.md`.
- **Result**:

  ### Deterministic negative control

  Three legs per PVT point, on **every** measurement this testbench records (not just `n1`...`n5`): a plain `mc=None` deck, plus the Monte Carlo deck with `sw_stat_mismatch = 0` at two different seeds. All three must agree **bit-for-bit** -- that is what proves the campaign's decks are the corner matrix's decks plus a switch.

  | PVT point | control worst node | control worst (V) | baseline = control | seed-A = seed-B | Δ vs its own node in `20260817-202802-d7bda87` (µV) |
  |---|---|---|---|---|---|
  | `tt_-40c_vdrv6p00v` | `n5_max_v` | 3.006 | yes | yes | -3045656.02 |
  | `tt_27c_vdrv6p00v` | `n5_max_v` | 3.506 | yes | yes | -2544699.17 |
  | `tt_125c_vdrv6p00v` | `n5_max_v` | 4.006 | yes | yes | -2040700.77 |
  | `ff_-40c_vdrv6p00v` | `n5_max_v` | 4.506 | yes | yes | -1536904.72 |

  ### Worst taper node (`n1`...`n5`) under local mismatch

  `margin` is the ratified §2.3 thick-oxide DC gate ceiling minus the measured peak, in mV -- negative means the node is above the ceiling, which is exactly what Exception 2 documents and bounds at ≤ 175 mV (i.e. margin ≥ −175.000 mV).

  | PVT point | draws used | control node | control (V) | MC mean (V) | MC σ (mV) | MC max (V) | binding node | worst margin (mV) | Δ vs control (mV) | vs ≤ 175 mV bound |
  |---|---|---|---|---|---|---|---|---|---|---|
  | `tt_-40c_vdrv6p00v` | 0/5 | `n5_max_v` | 3.006 | no data | | | | | | |
  | `tt_27c_vdrv6p00v` | 0/5 | `n5_max_v` | 3.506 | no data | | | | | | |
  | `tt_125c_vdrv6p00v` | 0/5 | `n5_max_v` | 4.006 | no data | | | | | | |
  | `ff_-40c_vdrv6p00v` | 0/5 | `n5_max_v` | 4.506 | no data | | | | | | |

  ### Per-node worst case across all draws and PVT points

  | node | control worst (V) | MC worst (V) | Δ (mV) | worst margin (mV) |
  |---|---|---|---|---|

  ### Non-converged draws

  **20 of 20 draws** did not complete and are excluded from every statistic in this record, listed here rather than dropped silently. Each is reproducible from the seed below.

  | PVT point | sample | seed | ngspice message |
  |---|---|---|---|
  | `tt_-40c_vdrv6p00v` | 1 | 0 | `Timestep too small; aborted` |
  | `tt_-40c_vdrv6p00v` | 2 | 1 | `Timestep too small; aborted` |
  | `tt_-40c_vdrv6p00v` | 3 | 2 | `Timestep too small; aborted` |
  | `tt_-40c_vdrv6p00v` | 4 | 3 | `Timestep too small; aborted` |
  | `tt_-40c_vdrv6p00v` | 5 | 4 | `Timestep too small; aborted` |
  | `tt_27c_vdrv6p00v` | 1 | 100 | `Timestep too small; aborted` |
  | `tt_27c_vdrv6p00v` | 2 | 101 | `Timestep too small; aborted` |
  | `tt_27c_vdrv6p00v` | 3 | 102 | `Timestep too small; aborted` |
  | `tt_27c_vdrv6p00v` | 4 | 103 | `Timestep too small; aborted` |
  | `tt_27c_vdrv6p00v` | 5 | 104 | `Timestep too small; aborted` |
  | `tt_125c_vdrv6p00v` | 1 | 200 | `Timestep too small; aborted` |
  | `tt_125c_vdrv6p00v` | 2 | 201 | `Timestep too small; aborted` |
  | `tt_125c_vdrv6p00v` | 3 | 202 | `Timestep too small; aborted` |
  | `tt_125c_vdrv6p00v` | 4 | 203 | `Timestep too small; aborted` |
  | `tt_125c_vdrv6p00v` | 5 | 204 | `Timestep too small; aborted` |
  | `ff_-40c_vdrv6p00v` | 1 | 300 | `Timestep too small; aborted` |
  | `ff_-40c_vdrv6p00v` | 2 | 301 | `Timestep too small; aborted` |
  | `ff_-40c_vdrv6p00v` | 3 | 302 | `Timestep too small; aborted` |
  | `ff_-40c_vdrv6p00v` | 4 | 303 | `Timestep too small; aborted` |
  | `ff_-40c_vdrv6p00v` | 5 | 304 | `Timestep too small; aborted` |

  This is the same solver failure mode `sim/README.md`'s transient-tolerance decision record already documents for this class of deck (ngspice "Timestep too small" on a source branch current); at the harness's ratified `reltol=1e-4` it is rare rather than absent. Because the abort truncates the transient, the affected draw's partial node measurement is a lower bound on what that draw would have peaked at, which is exactly why it is excluded rather than counted.

  - **Overall: ERROR** -- no Monte Carlo sample completed.

  ### Finding: is the ~27 mV of headroom decision record 0013 left unspent?

  Decision record 0013 sized Exception 2's ≤ 175 mV bound with ~27 mV of headroom above its cited −148.0 mV worst case, explicitly because no deck-fidelity or mismatch sweep had been run against `n1`'s own binding corner at the time. This campaign is that sweep's mismatch half (a deck-fidelity `reltol`/`maxstep` sweep, the other half decision record 0013 names as a future follow-up, is out of scope for issue #211).

  - **Spread**: σ(worst taper node) = n/a per PVT point.
  - **Provenance caveat carried forward**: this campaign's own driving condition (ideal 1 ns `IN_DRV` edge, no level shifter) is milder than the end-to-end chain decision record 0013 actually bounds against (real level-shifter edge, worse by ~46 mV at the deterministic corner per decision record 0013's own table). This record's local-mismatch spread is therefore evidence about *how much mismatch moves this node*, not a replacement for an end-to-end mismatch campaign against `sim/gate-driver-core-drive`'s chain -- which issue #204's own incidental data already partially covers and is not re-run here (out of scope for issue #211: Exception 3 / `IN_DRV` is #204's own claim).

  ### What the open PDK does and does not model

  This cell (`design/output_stage.sch`, spec §2.5) is entirely `nfet_06v0`/`pfet_06v0` -- both families carry per-instance threshold mismatch (`delvto`) in `sm141064.ngspice`'s `.lib fets_mm`, but `nfet_06v0` gets **no** β mismatch (`par_k = 0.0000`); `pfet_06v0` does (`par_k = 0.00517`). No resistor or MiM capacitor sits in this cell's taper chain, so the resistor/MiM mismatch gaps `spec/decision-records/0017-pdk-local-mismatch-model-coverage.md` records do not limit this campaign's coverage the way they limit Exception 3's `XCCOMP` caveat. This is therefore a full-coverage mismatch campaign for the device families this cell actually uses, modulo the `nfet_06v0` β-mismatch gap noted above.

- **Links**:
  - Run script: `sim/output-stage-taper-mismatch/run_output_stage_mismatch.py`
  - Testbench (reused verbatim): `sim/output-stage-drive/testbench/fake_tb.spice`, `sim/output-stage-drive/testbench/tb.json`
  - Monte Carlo deck machinery: `sim/harness/montecarlo.py`
  - Netlist snapshot: `sim/output-stage-taper-mismatch/netlist-snapshots/20260102-030405-abcdef0.spice`
  - Raw logs: `sim/output-stage-taper-mismatch/corners/20260102-030405-abcdef0/` -- one `.log` per zero-sigma control and per worst-case draw, plus a `samples-<corner-id>.csv` sidecar carrying every draw's seed and measurements
  - Reference corner matrix: `sim/output-stage-drive/records/20260817-202802-d7bda87.md`
  - PDK: gf180mcuD (/nonexistent/gf180mcuD), ngspice ngspice-47 : fake
  - Deck tolerance: `reltol=1e-4` (harness default) -- the same convention as `20260817-202802-d7bda87`
- **Timestamp / author**: 2026-01-02T03:04:05Z, agent-builder (issue #211)
- **Supersedes**: (none -- first Monte Carlo / local-mismatch record for this claim)
