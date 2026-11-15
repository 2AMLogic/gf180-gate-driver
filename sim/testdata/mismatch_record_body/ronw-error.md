verdict=ERROR
anomalies=[]
# Record 20260102-030405-abcdef0

- **Record ID**: 20260102-030405-abcdef0
- **Claim**: `spec/low-side-power-switch.md#21-ronw-vs-vgs-and-temperature-ratified` -- **local-mismatch (Monte Carlo) robustness of the ratified `nfet_06v0` `Ron·W` table**, primarily its worst-case design point (`Vgs` = 3.6 V, grid-worst = **4.5719 Ω·mm**, the number §2.2's switch-sizing table is computed from), combined with (not replacing) the process-corner matrix in `sim/low-side-power-switch/records/20260818-011754-03afe04.md`. `pfet_06v0` (not the switch — §5's synchronous-PMOS flyback option) and the `fb_vf` diode measurements the reused testbench also carries are reported as incidental context only, per the same convention `sim/gate-driver-indrv-mismatch`'s record uses for its own incidental taper-node data — this record does not claim them.
- **Netlist provenance**: schematic-level device testbench (`sim/low-side-power-switch/testbench/tb_low_side_power_switch.spice`) -- loaded verbatim (not copied), the identical deck `sim/low-side-power-switch/run_low_side_power_switch.py` used to produce `20260818-011754-03afe04`. PDK device models instantiated directly; no `design/` schematic, no extracted layout.
- **Corner matrix run**:
  - Process: tt, ff, ss, fs, sf
  - Temperature: -40 °C, 27 °C, 125 °C
  - Supply: **not applicable** -- every DUT is a bare transistor or diode biased from ideal sources, same `nosupply` convention as the reference record; the cell-referenced `Vgs` axis (3.6/4.2/5.0 V) is swept as an explicit gate-bias point, not a supply tolerance.
  - 4 PVT point(s) (full 5 process × 3 temperature grid, no narrowing), each carrying 5 Monte Carlo mismatch draws plus 2 zero-sigma controls and 1 plain-deck baseline -- 32 ngspice runs, 2.0 min wall.
- **Statistical convention**: Monte Carlo **local device mismatch** (intra-die), N = 5 independent draws per PVT point, 4 PVT point(s), 20 mismatch samples total. **20 of 20 draws did not converge and are excluded from every statistic below** -- enumerated in "Non-converged draws", leaving 0 in the distribution. Distribution source: the gf180mcu PDK's own `.lib fets_mm` per-instance mismatch model (`delvto = mis_vth·sw_stat_mismatch`, `mulu0 = 1 − mis_k·sw_stat_mismatch`, `mis_vth`/`mis_k` drawn from `agauss(0, σ, 1)`, σ scaled Pelgrom-style by 1/√(W_eff·L_eff)) -- **1 σ per-device draws, not a 3 σ corner pull**; reported σ is the sample standard deviation over the draws, reported worst case is the observed maximum, not a fitted quantile. `sw_stat_global = 0` throughout -- the deterministic `.LIB` process corner remains the sole global-skew axis. Seeds: `seed = 20260821 + point_index × 10000 + sample`, point_index in the grid order tabulated below. Every PVT point carries a **deterministic negative control** in three legs: a plain mismatch-off deck, plus two `sw_stat_mismatch = 0` decks at two different seeds -- all three must agree bit-for-bit, and are additionally compared against the committed corner-matrix record `20260818-011754-03afe04`.
- **Result**:

  ### Deterministic negative control

  Three legs per PVT point, on `ronw_n06_3.6` (the primary claim measurement; the sidecar CSVs carry all measurements). All three must agree **bit-for-bit** -- that is what proves the campaign's decks are the corner matrix's decks plus a switch, so the spread reported below is mismatch and not a deck difference or solver noise. The fourth column compares the same control against the **committed** record `20260818-011754-03afe04`, re-parsed from its raw logs at run time; both this campaign and that record ran under the same ngspice version (see Environment below), so exact equality *is* expected there, unlike the ngspice-46/ngspice-47 cross-version residue decision record 0017 documents for a different facet.

  | PVT point | control `ronw_n06_3.6` (Ω·mm) | baseline = control | seed-A = seed-B | Δ vs `20260818-011754-03afe04` (µΩ·mm) |
  |---|---|---|---|---|
  | `tt_-40c_nosupply` | 2.000000 | yes | yes | -152541.888 |
  | `tt_27c_nosupply` | 2.100000 | yes | yes | -679584.709 |
  | `tt_125c_nosupply` | 2.200000 | yes | yes | -1599566.330 |
  | `ff_-40c_nosupply` | 2.300000 | yes | yes | +414521.124 |

  ### `nfet_06v0` `Ron·W` at `Vgs` = 3.6 V under local mismatch (the switch, worst-case design row)

  **Why this table has no per-row PASS/FAIL against the ratified window.** 4.5719 Ω·mm (§2.1's grid-worst figure) is itself a single deterministic sample -- one seed, mismatch off -- at `ss_125c_nosupply`, not an independently-set margin the way Exceptions 1–3's ≤ 40/175/10 mV bounds are. Local mismatch is a roughly zero-mean perturbation layered on top of that same sample, so **about half of any PVT point's draws are expected to exceed its own deterministic value by construction** -- that is not a spec violation, it is what a symmetric distribution centered on a single prior sample does. The question that actually matters for §2.1/§2.2 is *how large* that excursion is, not whether it is exactly zero. `excursion` below is (MC max − this PVT point's own deterministic control), always ≥ 0 by definition of max; `excursion % window` expresses it against the ratified window's own 2.6864 Ω·mm width.

  | PVT point | draws used | control (Ω·mm) | MC mean (Ω·mm) | MC σ (mΩ·mm) | MC max (Ω·mm) | excursion (mΩ·mm) | excursion, % of window |
  |---|---|---|---|---|---|---|---|
  | `tt_-40c_nosupply` | 0/5 | 2.0000 | no data | | | | |
  | `tt_27c_nosupply` | 0/5 | 2.1000 | no data | | | | |
  | `tt_125c_nosupply` | 0/5 | 2.2000 | no data | | | | |
  | `ff_-40c_nosupply` | 0/5 | 2.3000 | no data | | | | |

  ### Non-converged draws

  **20 of 20 draws** did not complete and are excluded from every statistic in this record. Listed here rather than dropped silently, per decision record 0017's convention -- each is reproducible from the seed below.

  | PVT point | sample | seed | ngspice message |
  |---|---|---|---|
  | `tt_-40c_nosupply` | 1 | 0 | `aborted` |
  | `tt_-40c_nosupply` | 2 | 1 | `aborted` |
  | `tt_-40c_nosupply` | 3 | 2 | `aborted` |
  | `tt_-40c_nosupply` | 4 | 3 | `aborted` |
  | `tt_-40c_nosupply` | 5 | 4 | `aborted` |
  | `tt_27c_nosupply` | 1 | 100 | `aborted` |
  | `tt_27c_nosupply` | 2 | 101 | `aborted` |
  | `tt_27c_nosupply` | 3 | 102 | `aborted` |
  | `tt_27c_nosupply` | 4 | 103 | `aborted` |
  | `tt_27c_nosupply` | 5 | 104 | `aborted` |
  | `tt_125c_nosupply` | 1 | 200 | `aborted` |
  | `tt_125c_nosupply` | 2 | 201 | `aborted` |
  | `tt_125c_nosupply` | 3 | 202 | `aborted` |
  | `tt_125c_nosupply` | 4 | 203 | `aborted` |
  | `tt_125c_nosupply` | 5 | 204 | `aborted` |
  | `ff_-40c_nosupply` | 1 | 300 | `aborted` |
  | `ff_-40c_nosupply` | 2 | 301 | `aborted` |
  | `ff_-40c_nosupply` | 3 | 302 | `aborted` |
  | `ff_-40c_nosupply` | 4 | 303 | `aborted` |
  | `ff_-40c_nosupply` | 5 | 304 | `aborted` |


  ### `nfet_06v0` `Ron·W` at the other two `Vgs` points (context, not the primary claim)

  Aggregated worst case across all PVT points and all draws, checked against each row's own ratified window (§2.1) for completeness, but the primary claim above is the `Vgs` = 3.6 V row -- the worst-case design point §2.2's sizing table actually uses.
  Same `excursion` convention as the primary table: MC worst minus that PVT point's own deterministic control, aggregated here to the single largest excursion observed at any PVT point (not a full 15-row breakdown, since these rows are context, not the claim).

  | `Vgs` | ratified window (Ω·mm) | window width (Ω·mm) | worst excursion (mΩ·mm) | excursion, % of window |
  |---|---|---|---|---|
  | 5 V | 1.5287 .. 3.6176 | 2.0889 | no data | |
  | 4.2 V | 1.6907 .. 4.0510 | 2.3603 | no data | |

  ### `pfet_06v0` `Ron·W` (context, not the switch -- §5's rejected synchronous-PMOS option)

  | `|Vgs|` | ratified window (Ω·mm) | window width (Ω·mm) | worst excursion (mΩ·mm) | excursion, % of window |
  |---|---|---|---|---|
  | 5 V | 4.7759 .. 11.2493 | 6.4734 | no data | |
  | 4.2 V | 5.3358 .. 13.1291 | 7.7933 | no data | |
  | 3.6 V | 5.9721 .. 15.2279 | 9.2558 | no data | |

  - **Overall: ERROR** -- no Monte Carlo sample completed.

  ### Finding: does the ratified 3:1 grid-wide window already absorb local mismatch?

  This is the question issue #216 poses, and **this campaign cannot answer it**: no Monte Carlo draw converged at any PVT point, so there is no measured local-mismatch excursion to put against the ratified window (§2.1: 1.8855 .. 4.5719 Ω·mm at the `Vgs` = 3.6 V row, the worst-case design row, **2.6864 Ω·mm wide**). Per-PVT-point mismatch σ on this row is n/a. Every failed draw is listed in the non-converged-draws table above, each reproducible from its seed; this record is evidence that the campaign ran and what it did, not evidence about the window.

  **Conclusion for issue #216's acceptance criteria**: none drawn. With zero converged draws this campaign neither supports nor contradicts the proposition that the ratified window absorbs local mismatch. No revision to `spec/low-side-power-switch.md` §2.1's table or §2.2's sizing rule is warranted by this record -- and none is ruled out by it either; the question stays open until a campaign converges.

  ### What the open PDK does and does not model (per decision record 0017)

  This campaign inherits decision record 0017's coverage findings unchanged (re-verified, not re-derived, against the same `open_pdks` pin): `nfet_06v0`/`pfet_06v0` get **threshold mismatch only** (`par_k = 0` for both families in `.lib fets_mm`, so `mulu0 ≡ 1` -- no β mismatch), and MiM capacitors/resistors are not perturbed device-to-device at all (this testbench instantiates neither, so that gap does not limit this specific record the way it limits Exception 3's `XCCOMP` caveat). `diode_pd2nw_06v0` -- instantiated by the reused testbench for §5's flyback context, not measured by this record -- is **not** one of the `.lib fets_mm` mismatch-carrying families either; its forward drop is drawn identically at every sample, a limit worth stating even though this record does not claim its Vf figures.

- **Links**:
  - Run script: `sim/low-side-power-switch-ronw-mismatch/run_ronw_mismatch.py`
  - Testbench (reused verbatim): `sim/low-side-power-switch/testbench/tb_low_side_power_switch.spice`
  - Monte Carlo deck machinery: `sim/harness/montecarlo.py`
  - Netlist snapshot: `sim/low-side-power-switch-ronw-mismatch/netlist-snapshots/20260102-030405-abcdef0.spice`
  - Raw logs: `sim/low-side-power-switch-ronw-mismatch/corners/20260102-030405-abcdef0/` -- one `.log` per baseline, zero-sigma control and worst-case draw, plus a `samples-<corner-id>.csv` sidecar carrying every draw's seed and parsed measurements
  - Reference corner matrix: `sim/low-side-power-switch/records/20260818-011754-03afe04.md`
  - PDK: gf180mcuD (/nonexistent/gf180mcuD), ngspice ngspice-47 : fake
- **Timestamp / author**: 2026-01-02T03:04:05Z, agent-builder (issue #216)
- **Supersedes**: (none -- first Monte Carlo / local-mismatch record for `spec/low-side-power-switch.md`)
