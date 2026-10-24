verdict=FAIL
# Record 20260102-030405-abcdef0

- **Record ID**: 20260102-030405-abcdef0
- **Claim**: spec/gate-driver.md#5-protection-and-fault-handling (§5 Exception 1 -- the level shifter's pre-driver inverter output `inb`, decision records 0003/0015) -- **local-mismatch (Monte Carlo) robustness of the ratified ≤ 40 mV bound**, combined with (not replacing) the process-corner matrix in `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`
- **Netlist provenance**: design -- DUT `design/fake.spice` (sha256 `dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd`), driven by `sim/level-shifter-oxide-safety/testbench/fake_tb.spice` (sha256 `nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn`) -- byte-for-byte the testbench and netlist that produced `20260818-071216-5260603`, loaded through its own `tb.json` rather than copied. One measurement key is added at compose time beyond the manifest's own set: `vinb_max_v` aliases `mq6` -- an already-computed `meas tran` result this testbench's own `tb.json` `analyses` list already defines (`dq6 = |v(inb)-v(gnd_logic)|`, `meas tran mq6 max dq6`) -- so no new SPICE expression, netlist edit, or `tb.json` change is involved; see the module docstring.
- **Corner matrix run**:
  - Process: tt, ff, ss, fs, sf
  - Temperature: -40 °C, 27 °C, 125 °C
  - Supply (vlogic, nominal 3.30 V): 3.63 V (+10 % tolerance point)
  - Supply (vdrv, nominal 5.00 V): 5.50 V (tied +10 % point)
  - 4 PVT point(s) (process × temperature at the vlogic3p63v-vdrv5p50v tied supply point), each carrying 5 Monte Carlo mismatch draws plus 2 zero-sigma controls and 1 plain-deck baseline -- 32 ngspice runs, 2.0 min wall.
  - **Subset of the mandated PVT matrix.** Gaps: vlogic: missing 2.97 V, 3.30 V; vdrv: missing 4.50 V, 5.00 V, 6.00 V.
  - Justification: the process and temperature axes are run in full (5 × 3, the same axes as the reference corner matrix). Only the supply axis is restricted, to the single tied `vlogic3p63v-vdrv5p50v` point, because **Exception 1 does not exist at any other supply**: decision record 0003 records `inb` clearing its own `VDD_LOGIC` rail at every other tolerance point (max 3.336 V at `vlogic3p30v`, well inside the rail), only overshooting at the `vlogic3p63v` corner. Spending the other 64 ngspice runs on supply points with no exception to characterize would not change any claim made here.
- **Statistical convention**: Monte Carlo **local device mismatch** (intra-die), N = 5 independent draws per PVT point, 4 PVT point(s), 20 mismatch samples total. All 20 draws converged; none is excluded. Distribution source: the gf180mcu PDK's own `.lib fets_mm` per-instance mismatch model (`delvto = mis_vth·sw_stat_mismatch`, `mulu0 = 1 − mis_k·sw_stat_mismatch`, with `mis_vth`/`mis_k` drawn from `agauss(0, σ, 1)` and σ scaled Pelgrom-style by 1/√(W_eff·L_eff)) -- i.e. **1 σ per-device draws, not a 3 σ corner pull**; `nfet_03v3`/`pfet_03v3` (the pre-driver inverter's own thin-oxide devices) carry both threshold *and* β mismatch (`par_k` 0.007008 / 0.002833) per decision record 0017 -- the fuller mismatch model this repo's thick-oxide 5 V/6 V families do not all get. The reported σ below is the sample standard deviation of `inb`'s measured peak over the draws, and the reported worst case is the observed maximum, not a fitted quantile. `sw_stat_global = 0` throughout, so the deterministic `.LIB` process corner remains the sole global-skew axis and is not double-counted. Seeds are deterministic: `seed = 20260304 + point_index × 10000 + sample`, point_index in the grid order tabulated below (`sim/harness/montecarlo.py`). Every PVT point additionally carries a **deterministic negative control** in three legs: a plain `mc=None` deck (byte-identical to what `sim/run_corners.py` generates), plus two `sw_stat_mismatch = 0` decks at two different seeds -- all three must agree bit-for-bit, and are additionally compared against the committed corner-matrix record `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`'s own raw `mq6` value at each corner.
- **Result**:

  ### Deterministic negative control

  Three legs per PVT point, on **every** measurement this testbench records (not just `inb`): a plain `mc=None` deck, plus the Monte Carlo deck with `sw_stat_mismatch = 0` at two different seeds -- all three must agree **bit-for-bit**. The fourth column compares the same control against the reference record's own raw `mq6` value, re-parsed from its committed log at run time.

  | PVT point | control `vinb_max_v` (V) | baseline = control | seed-A = seed-B | Δ vs `20260818-071216-5260603` `mq6` (µV) |
  |---|---|---|---|---|
  | `tt_-40c_vlogic3p63v-vdrv5p50v` | 3.001 | yes | yes | -652790.00 |
  | `tt_27c_vlogic3p63v-vdrv5p50v` | 3.501 | yes | yes | -156310.00 |
  | `tt_125c_vlogic3p63v-vdrv5p50v` | 4.001 | yes | yes | +341040.00 |
  | `ff_-40c_vlogic3p63v-vdrv5p50v` | 4.501 | yes | yes | +850660.00 |

  ### `inb` peak under local mismatch (Exception 1's node)

  `over_rail` is the measured peak minus `VDD_LOGIC` (3.63 V at this corner), in mV -- Exception 1 bounds this at ≤ 40 mV.

  | PVT point | draws used | control (V) | MC mean (V) | MC σ (mV) | MC min (V) | MC max (V) | worst over_rail (mV) | Δ vs control (mV) | vs ≤ 40 mV bound |
  |---|---|---|---|---|---|---|---|---|---|
  | `tt_-40c_vlogic3p63v-vdrv5p50v` | 5/5 | 3.001 | 3.011 | 15.8114 | 2.991 | 3.031 | -599.000 | +30.000 | PASS |
  | `tt_27c_vlogic3p63v-vdrv5p50v` | 5/5 | 3.501 | 3.521 | 31.6228 | 3.481 | 3.561 | -69.000 | +60.000 | PASS |
  | `tt_125c_vlogic3p63v-vdrv5p50v` | 5/5 | 4.001 | 4.031 | 47.4342 | 3.971 | 4.091 | +461.000 | +90.000 | **FAIL** |
  | `ff_-40c_vlogic3p63v-vdrv5p50v` | 5/5 | 4.501 | 4.541 | 63.2456 | 4.461 | 4.621 | +991.000 | +120.000 | **FAIL** |

  ### Non-converged draws

  None -- all 20 mismatch draws completed and every one is in the statistics above.

  - **Overall: FAIL** -- across 20 converged local-mismatch draws (of 20 run) spanning the full process × temperature grid at the `vlogic3p63v-vdrv5p50v` tied point, the worst observed `inb` peak is **4.621 V (+991.000 mV over `VDD_LOGIC`)** at `ff_-40c_vlogic3p63v-vdrv5p50v`, inside `spec/gate-driver.md` §5 Exception 1's ratified ≤ 40 mV bound with -951.000 mV of the bound still unspent. The three-leg deterministic negative control holds at every PVT point (baseline = seed-A control = seed-B control, bit-for-bit, on every measurement). Against the **committed** corner-matrix record's own raw `mq6` value the same control differs by up to 850660 µV. No ratified bound is amended by this record.

  ### Finding: Exception 1's ~4.3 mV of headroom under local mismatch

  Decision record 0015 sized Exception 1's ≤ 40 mV bound with only ~4.3 mV of headroom above its converged 35.67 mV worst case -- proportionally the tightest of the block's three §5 exceptions -- specifically because that record's own deck-fidelity sweep, not a device-mismatch sweep, was the only refinement it had tested against. This campaign is the local-mismatch half of the question decision record 0015 left open.

  - **Spread**: σ(`inb` peak) = 15811–63246 µV per PVT point.
  - **Worst draw vs. the ratified bound**: -951.000 mV of the ≤ 40 mV bound still unspent at the worst observed draw (+991.000 mV over rail).
  - **The pre-driver inverter's own devices carry the fuller mismatch model this repo's other two exceptions do not**: `nfet_03v3`/`pfet_03v3` get both threshold *and* β mismatch (decision record 0017), unlike the thick-oxide `nfet_05v0`/`nfet_06v0` families Exceptions 2 and 3 depend on, which get threshold mismatch only. If any of this block's three exceptions were going to show a mismatch-driven surprise, this is the one with the richest underlying PDK model to show it -- and the measured spread above is the answer, not an argument.

- **Links**:
  - Run script: `sim/level-shifter-inb-mismatch/run_inb_mismatch.py`
  - Testbench (reused verbatim): `sim/level-shifter-oxide-safety/testbench/fake_tb.spice`, `sim/level-shifter-oxide-safety/testbench/tb.json`
  - Monte Carlo deck machinery: `sim/harness/montecarlo.py`
  - Netlist snapshot: `sim/level-shifter-inb-mismatch/netlist-snapshots/20260102-030405-abcdef0.spice`
  - Raw logs: `sim/level-shifter-inb-mismatch/corners/20260102-030405-abcdef0/` -- one `.log` per zero-sigma control and per worst-case draw, plus a `samples-<corner-id>.csv` sidecar carrying every draw's seed and measurements
  - Reference corner matrix: `sim/level-shifter-oxide-safety/records/20260818-071216-5260603.md`
  - PDK: gf180mcuD (/nonexistent/gf180mcuD), ngspice ngspice-47 : fake
  - Deck tolerance: `reltol=1e-4` (harness default) -- the same convention as `20260818-071216-5260603`
- **Timestamp / author**: 2026-01-02T03:04:05Z, agent-builder (issue #211)
- **Supersedes**: (none -- first Monte Carlo / local-mismatch record for this claim)
