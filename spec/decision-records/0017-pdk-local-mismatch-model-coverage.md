# 0017: gf180mcu local-mismatch model coverage, and what Monte Carlo evidence can and cannot say about Exception 3

- **Status**: Ratified
- **Date**: 2026-08-21
- **Decided by**: Builder agent, issue #204
- **Supersedes**: none. **Does not amend** `spec/gate-driver.md` §5 Exception 1,
  2 or 3, nor decision records 0003/0005/0006/0007/0013/0014/0015. Every
  ratified bound stands exactly as written. This record adds an evidence class
  and states its coverage limits; it changes no number.

## Context

Every recorded result under `sim/` before this record was a **global process
corner** claim (`tt`/`ff`/`ss`/`fs`/`sf`) — die-to-die and wafer-to-wafer skew,
applied uniformly to every device in the deck. That says nothing about
**within-die local mismatch** between two nominally-identical devices on the
same die at the same corner. `sim/README.md`'s record schema has always
reserved a **Statistical convention** field for that evidence class, and no
record had ever populated it: both records that mentioned Monte Carlo at all
(`sim/device-mv-fet/records/20260808-023237-61e0c25.md`,
`sim/low-side-power-switch/records/20260818-011754-03afe04.md`) say
"Statistical convention: N/A — this record is the corner matrix, not a Monte
Carlo/mismatch distribution claim."

Issue #204 raised this against the repo's **tightest-margin ratified claim**:
`spec/gate-driver.md` §5's Exception 3 (decision records 0006/0007/0014) bounds
the inter-cell net `IN_DRV`'s excursion above the 6.0 V thick-oxide gate
ceiling (§2.3) at **≤ 10 mV**, with the measured worst case at **6.00266 V
(margin −2.66 mV)** at `ss_125c_vlogic3p30v-vdrv6p00v`
(`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`). That figure
depends on the `XCCOMP` feedforward compensation capacitor — four series
`cap_mim_2f0_m4m5_noshield` devices in `design/level_shifter.sch`, decision
record 0014 — cancelling a gate-drive-feedthrough path to within a few
millivolts. A cancellation that precise is exactly the kind of margin local
device mismatch is supposed to be checked against, and it never had been.

Before any such campaign can be run, one question has to be answered from the
installed PDK rather than assumed: **does the open `gf180mcuD` PDK ship a
local-mismatch model at all, and for which devices?** That question — not the
resulting number — is what this record exists to settle, because the answer
bounds what every future mismatch record in this repo is allowed to claim.

## Finding: what `gf180mcuD` actually ships

Determined by reading the installed decks under
`libs.tech/ngspice/` of `gf180mcuD` @ open_pdks
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, and confirmed by running them —
not by assuming a foundry convention.

`design.ngspice` defines two global switches, documented in its own comment
table: `sw_stat_global` (die-to-die / global skew) and `sw_stat_mismatch`
(intra-die mismatch, described there as "especially critical for analog
matching applications"). **Both default to `0`.** That default is the direct
reason every prior record in this repo is a pure corner claim: the harness has
always generated decks with statistical modelling entirely switched off, and
nothing in the decks announced that.

| Device class | Local (intra-die) mismatch shipped? | Mechanism / evidence |
|---|---|---|
| `nfet_03v3`, `pfet_03v3`, `nfet_05v0`, `pfet_05v0`, `nfet_06v0`, `pfet_06v0` | **Yes** | `sm141064.ngspice` `.lib fets_mm` wraps each in a subcircuit whose MOS line carries `delvto='mis_vth*sw_stat_mismatch'` and `mulu0='1-mis_k*sw_stat_mismatch'`, with `mis_vth`/`mis_k` drawn **per subcircuit instance** from `agauss(0, σ, 1)` and σ scaled Pelgrom-style by `1/√(W_eff·L_eff)`. All five MOS corner sections (`typical`/`ff`/`ss`/`fs`/`sf`) already `.lib` that section in unconditionally. |
| MiM capacitors (`cap_mim_*`) | **No** | `sm141064_mim.ngspice` computes `c_c0 = (c_cox·area + c_capsw·peri)·(1 + mc_c_cox_2p0fF)`, but `mc_c_cox_1p0fF`/`_1p5fF`/`_2p0fF` are hardcoded to `0` in all three `mimcap_typical`/`_ss`/`_ff` sections. A distribution is assigned to them only in `.lib mimcap_statistical`, gated on `sw_stat_global` — and they are `.LIB`-scope parameters, i.e. **one value shared by every instance**, so even that is global density skew, not device-to-device mismatch. |
| Resistors | **No** | `.lib res_statistical` draws `agauss` sheet-rho deviations but gates them on `sw_stat_global`, not `sw_stat_mismatch`. Die-level skew only, already covered by `res_ff`/`res_ss`. |
| β (current-factor) mismatch on `nfet_05v0` / `nfet_06v0` | **No** | In `.lib fets_mm` the coefficient `par_k` is `0.0000` for these two families and non-zero for every other (`nfet_03v3` 0.007008, `pfet_03v3` 0.002833, `pfet_05v0`/`pfet_06v0` 0.00517), so `mulu0 ≡ 1`. The thick-oxide nFETs get **threshold mismatch only**. |

Two further medium-voltage model-fidelity observations, recorded per
`CLAUDE.md`'s instruction that this block surface exactly this class of finding:

- **`.LIB statistical` has a dead branch for `nfet_06v0`.** It defines global MC
  parameters `nfet_06v0_vsat`/`_vth0`/`_xl`/`_xw`/`_tox` as `agauss` expressions,
  but its own include list then pulls `.lib 'sm141064.ngspice' nfet_06v0_t` —
  the *typical* model card — where `pfet_06v0` gets `pfet_06v0_stat` and the
  3.3 V families get `nfet_03v3_stat`/`pfet_03v3_stat`. **No `nfet_06v0_stat`
  section exists anywhere in the file.** So the thick-oxide n-channel device's
  global statistical parameters are computed and never consumed. This does not
  affect this repo's evidence (we pin `sw_stat_global = 0` and take global skew
  from the deterministic `.LIB` corner — see the Decision below), but it means a
  `sw_stat_global = 1` campaign on this PDK would silently under-vary
  `nfet_06v0`, and anyone attempting one should know that first.
- **`.options seed=<expr>` is rejected by ngspice-47** ("unknown option seed")
  when the value is a `.param` expression; only a literal integer is accepted.
  The harness therefore formats the seed as a literal.

**Empirically confirmed** on this install, ngspice-47, two nominally identical
`nfet_06v0` instances at identical bias: `sw_stat_mismatch = 0` gives bit-identical
drain currents regardless of seed; `sw_stat_mismatch = 1` gives *different*
currents per instance, reproducible bit-for-bit at the same seed and different at
a different seed. The per-instance draw is real, not a single global perturbation.

## Decision

**1. Local-mismatch (Monte Carlo) evidence is ratified as a recognised evidence
class in this repo, layered on top of the corner matrix and never replacing it.**
The convention is written into `sim/README.md` ("Decision record: Monte Carlo /
local-mismatch convention") and implemented in `sim/harness/montecarlo.py` +
`runner.compose_deck(..., mc=...)` / `runner.run_samples`. Its load-bearing rules:

- One ngspice invocation is one sample (`agauss` is evaluated at parse time and
  drawn per subcircuit instance).
- **`sw_stat_global` is pinned to `0`.** The deterministic `.LIB` process corner
  *is* this harness's global-skew axis; letting the PDK also draw a random global
  skew would double-count it and make "mismatch at the `ss` corner" mean
  something else. Monte Carlo therefore always runs **on top of** the mandated
  PVT matrix, per `CLAUDE.md`'s "PVT corners on every recorded result".
- Seeds are derived, not ad hoc: `seed = base_seed + point_index·10000 + sample`,
  pinned as a literal `.options seed=<n>`, so a record's whole distribution is
  reproducible from two recorded integers.
- **A deterministic negative control is mandatory.** Sample index 0 is reserved
  for a `sw_stat_mismatch = 0` run which must reproduce the plain harness deck
  for the same PVT point **bit-for-bit on every measurement, at two different
  seeds**. Without it, a "Monte Carlo" record cannot distinguish mismatch from a
  deck difference or solver noise.
- The **Statistical convention** field must state N, the sigma level of the
  underlying model (the PDK's per-device draws are 1 σ, *not* a 3 σ corner pull),
  the base seed, and whether a reported worst case is an observed maximum or a
  fitted quantile.

**2. Every mismatch record in this repo must state the coverage limits above.**
Specifically: a gf180mcu mismatch campaign is a **MOSFET-threshold** mismatch
campaign (plus β mismatch on every family except `nfet_05v0`/`nfet_06v0`). MiM
capacitors and resistors are **not** perturbed device-to-device, because the open
PDK ships no such distribution. A record claiming broader coverage than that is
claiming something the PDK does not model.

**3. No sigma is ever invented for a device the PDK does not characterise.**
In particular, `XCCOMP`'s four MiM devices are perfectly matched to each other in
every sample of any campaign run under this convention. That is a real, stated
limit on Exception 3's mismatch evidence — not a gap to be papered over with a
hand-picked capacitor sigma. Closing it requires a characterised MiM mismatch
model (foundry data this open PDK does not ship), not a modelling assumption.

**4. Exception 3's ratified ≤ 10 mV bound is unchanged.** The first campaign
under this convention (`sim/gate-driver-indrv-mismatch/`, issue #204) runs the
full 5 × 3 process × temperature grid at the 6 V stretch rail — the only supply
where Exception 3 exists at all, since §5 records `IN_DRV` clearing the ceiling
by ≥ 397 mV at every nominal-tolerance point — and finds the bound met with
margin to spare. The bound is neither narrowed nor relaxed by that result:
narrowing it on mismatch evidence that structurally excludes the `XCCOMP`
capacitor ratio would overstate what was verified.

## Alternatives considered

- **Assign a hand-picked σ to the MiM capacitors so `XCCOMP`'s ratio varies
  too.** Rejected outright. It is the single most load-bearing unmodelled term
  for Exception 3 specifically, which makes it the most tempting to invent and
  the most damaging to invent: a fabricated distribution would produce a
  scientific-looking number with no foundry basis, and `CLAUDE.md`'s
  "verification is the product" is worth nothing if the distribution behind a
  statistical claim is made up. The gap is recorded instead.
- **Run with `sw_stat_global = 1` (the PDK's own "most realistic" default
  setting) instead of the deterministic `.LIB` corners.** Rejected: it would
  double-count global skew against the corner matrix `CLAUDE.md` mandates on
  every record, it would make results incomparable with every existing record in
  `sim/`, and — per the dead-branch finding above — it would silently
  under-vary `nfet_06v0`, the dominant device family in this block.
- **Extend `sim/run_corners.py` with a Monte Carlo mode rather than adding a
  sibling script.** Partially rejected: the *deck* machinery does belong in the
  shared harness (and is there, in `sim/harness/montecarlo.py`, so any facet can
  use it), but the campaign driver does not. A campaign is a distribution claim
  over thousands of runs at one PVT point, not the `tb.json` grid model's
  one-measurement-per-point pass/fail, and its raw logs must be filtered rather
  than all committed. `sim/device-mv-fet/run_device_mv_fet.py` and
  `sim/low-side-power-switch/run_low_side_power_switch.py` are the existing
  precedent for a facet that drives the harness library directly.
- **Declare the question unanswerable on an open PDK and record only the gap**
  (issue #204's own anticipated third outcome). Rejected on the facts: the MOSFET
  mismatch model *is* shipped and *does* work. Only the MiM/resistor half of the
  question is a genuine gap, and it is recorded as one.

## Consequences

- `sim/README.md`'s **Statistical convention** field is populated by a real
  record for the first time; records that are not distribution claims continue to
  say "N/A", and now have a convention to point at when they do.
- **Exception 3 now has mismatch evidence, with a stated blind spot.** Anyone
  citing it should cite the blind spot too: `IN_DRV`'s mismatch spread was
  measured with the `XCCOMP` capacitor stack perfectly matched, because the PDK
  models no MiM mismatch. The excursion Exception 3 bounds is the residual of a
  capacitive cancellation, so the unmodelled term is not an incidental one.
- **Exceptions 1 and 2 do not have mismatch evidence.** The first campaign
  reports the `n1`…`n5` taper nodes (Exception 2, decision record 0013) as
  incidental context only, because the reused testbench already measures them —
  that is not an Exception-2-scoped campaign and must not be cited as one.
  Exception 1 (`inb`, decision records 0003/0015) is measured by a different
  facet (`sim/level-shifter-oxide-safety/`) and has had no mismatch run at all.
  Both are open follow-ups.
- **A future PDK update could invalidate the coverage table above.** It is
  pinned to open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`. If a later
  build ships a MiM mismatch distribution, or an `nfet_06v0_stat` section, the
  first campaign re-run against it should re-derive the table rather than
  inherit it, and supersede this record if the answer changed.
- **The `nfet_06v0` β-mismatch and dead-`_stat`-branch findings are model
  observations, not defects this repo can fix.** They are recorded here because
  `CLAUDE.md` makes surfacing medium-voltage model-fidelity gaps this block's
  job; they belong upstream (open_pdks / GlobalFoundries PDK) if anywhere.
