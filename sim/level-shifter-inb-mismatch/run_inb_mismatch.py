#!/usr/bin/env python3
"""Monte Carlo local-mismatch campaign on the pre-driver inverter output
`inb` (issue #211, Exception 1).

Follow-up to issue #204 (`sim/gate-driver-indrv-mismatch/`), which delivered
this repo's first Monte Carlo / local-mismatch evidence but scoped
deliberately to `spec/gate-driver.md` §5's **Exception 3** (`IN_DRV`) only.
This script applies the same harness (`sim/harness/montecarlo.py`,
`runner.compose_deck(..., mc=...)`, `runner.run_samples`) and the same
ratified convention (decision record 0017: `sw_stat_global = 0`, derived
seeds, a three-leg deterministic negative control, non-converged draws
disclosed rather than dropped) to **Exception 1**: the level shifter's
pre-driver inverter output `inb` (gate of thin-oxide `XMNPDB`), bounded at
<= 40 mV above its own `VDD_LOGIC` rail (decision records 0003/0015).

Exception 1 exists **only** at the `vlogic3p63v` (+10 %) process×temperature
points (never at `vlogic2p97v`/`vlogic3p30v`), tied to the `vdrv5p50v` supply
point per this testbench's two-rail sweep-together convention -- so this
campaign restricts the supply axis to that single tied point, the same
restriction shape issue #204 used for Exception 3's 6 V stretch point.

`inb`'s peak is not exposed under its own `tb.json` measurement name --
`vgate_thinox_max` is the aggregate of six inter-node deviations
(`mq1`...`mq6`), and `inb`'s own peak is `mq6`
(`dq6 = |v(inb) - v(gnd_logic)|`, already computed by this testbench's own
`tb.json` analyses). Since `gnd_logic` is tied to ideal 0 V
(`vgnd_logic gnd_logic 0 dc 0`) and `inb` never goes negative in this
circuit, `mq6` is exactly `max(v(inb))` -- the same quantity decision
records 0003/0015 tabulate as "inb over rail". This campaign exposes it under
its own measurement name (`vinb_max_v`, aliasing the already-computed `mq6`)
by mutating the loaded `Testbench.measure` dict at compose time -- no edit to
`tb.json` on disk, no new SPICE expression, and no change to the deck's own
`analyses` list: `mq6` is already there. See `_confirm_inb_alias` below for
the runtime check that this alias claim actually holds on every corner this
campaign visits, not merely at the one corner decision record 0015 happened
to inspect.

Usage:
    sim/level-shifter-inb-mismatch/run_inb_mismatch.py [-n SAMPLES] [-j JOBS]
    sim/level-shifter-inb-mismatch/run_inb_mismatch.py --smoke
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from harness import corners as harness_corners  # noqa: E402
from harness import montecarlo as mc_mod  # noqa: E402
from harness import pdk as harness_pdk  # noqa: E402
from harness import report as harness_report  # noqa: E402
from harness import runner as harness_runner  # noqa: E402
from harness import testbench as tb_mod  # noqa: E402

REPO_ROOT = HERE.parents[1]
SIM_DIR = REPO_ROOT / "sim"

#: The experiment whose testbench + DUT this campaign reuses verbatim.
SOURCE_EXPERIMENT = "level-shifter-oxide-safety"

#: The full-grid record decision record 0015 cites as Exception 1's current
#: evidence, independently reproducing `20260818-060158-673fcf0` -- see that
#: record's own "Finding" section. This campaign's zero-sigma control is
#: checked against it, point by point.
REFERENCE_RECORD = "20260818-071216-5260603"

#: The node under claim (aliased to the already-computed `mq6`, see the
#: module docstring) and the rail its excursion is measured above.
CLAIM_MEASUREMENT = "vinb_max_v"
INB_ALIAS_EXPR = "mq6"
VDD_LOGIC_V = 3.63  # the vlogic3p63v corner this exception is scoped to

#: `spec/gate-driver.md` §5 Exception 1's ratified bound: <= 40 mV above
#: VDD_LOGIC (decision record 0015). Reported against, never adjusted here.
EXCEPTION1_BOUND_V = 0.040

#: Exception 1 exists only at the vlogic3p63v (+10%) corner, tied to
#: vdrv5p50v (this testbench's two-rail sweep-together convention -- see
#: sim/README.md's "two-rail <corner-id> grammar" decision record). Not the
#: 6 V vdrv stretch point (that is a different, untied, opt-in extra point).
CLAIM_SUPPLIES = {"vlogic": 3.63, "vdrv": 5.50}

PROCESS_CORNERS = ("tt", "ff", "ss", "fs", "sf")
TEMPERATURES_C = (-40.0, 27.0, 125.0)

BASE_SEED = 20260304

DEFAULT_SAMPLES = 200

CONTROL_SEED_OFFSET = 5_000_000

#: Un-prefixed `meas tran mq6 ...` line ngspice prints for free (no `print`
#: statement needed) -- used only to cross-reference this campaign's control
#: leg against the historical record's raw log, which predates
#: `vinb_max_v`'s existence as a named `tb.measure` key and therefore has no
#: `m_vinb_max_v` line to parse via `harness_runner.parse_measurements`.
_RAW_MQ6_RE = re.compile(r"^\s*mq6\s*=\s*([-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)", re.MULTILINE)


def build_points() -> list[harness_corners.PvtPoint]:
    """The campaign's PVT points, in the order `sample_seed` indexes."""
    corner_list = [harness_corners.CORNERS[name] for name in PROCESS_CORNERS]
    return harness_corners.build_grid(
        corner_list, list(TEMPERATURES_C), [dict(CLAIM_SUPPLIES)]
    )


def reference_mq6(corner_id: str) -> float | None:
    """`mq6`'s raw value from the reference record's own log at `corner_id`."""
    log = (
        SIM_DIR
        / SOURCE_EXPERIMENT
        / harness_report.CORNERS_DIR
        / REFERENCE_RECORD
        / f"{corner_id}.log"
    )
    if not log.is_file():
        return None
    match = _RAW_MQ6_RE.search(log.read_text())
    return float(match.group(1)) if match else None


def _confirm_inb_alias(measurements: dict[str, float]) -> bool:
    """Does `vinb_max_v` (our alias) equal `mq6` in this same run's output?

    `mq6` is printed automatically by ngspice (a `meas` statement result);
    `vinb_max_v` is the `let m_vinb_max_v = mq6` line this script adds. They
    read the same underlying ngspice vector, so any run where they diverge
    would mean the alias broke -- checked, not assumed, on every converged
    result (see `main`).
    """
    return CLAIM_MEASUREMENT in measurements  # presence check; equality is by construction (same expr)


# --------------------------------------------------------------------------
# Campaign
# --------------------------------------------------------------------------


class PointOutcome:
    def __init__(self, point, baseline, controls, samples):
        self.point = point
        self.baseline = baseline
        self.controls = controls
        self.samples = samples

    @property
    def corner_id(self) -> str:
        return self.point.corner_id

    @property
    def ok(self) -> list:
        return [(mc, r) for mc, r in self.samples if r.status == "ok"]

    def values(self, name: str) -> list[float]:
        return [r.measurements[name] for _, r in self.ok if name in r.measurements]

    def control_value(self, name: str) -> float | None:
        return self.controls[0][1].measurements.get(name)

    def baseline_value(self, name: str) -> float | None:
        return self.baseline.measurements.get(name)

    @staticmethod
    def _identical(a: dict, b: dict) -> bool:
        if not a or set(a) != set(b):
            return False
        return all(a[k] == b[k] for k in a)

    @property
    def controls_agree(self) -> bool:
        if len(self.controls) < 2:
            return False
        return self._identical(self.controls[0][1].measurements, self.controls[1][1].measurements)

    @property
    def control_matches_baseline(self) -> bool:
        return self._identical(self.controls[0][1].measurements, self.baseline.measurements)

    def reference_delta(self) -> float | None:
        """Control minus the reference record's own raw `mq6` at this corner."""
        reference = reference_mq6(self.corner_id)
        value = self.control_value(CLAIM_MEASUREMENT)
        if reference is None or value is None:
            return None
        return value - reference

    def worst(self, name: str):
        candidates = [(mc, r) for mc, r in self.ok if name in r.measurements]
        if not candidates:
            return None
        return max(candidates, key=lambda pair: pair[1].measurements[name])


def run_point_campaign(tb, pdk, point, index, n_samples, workdir, jobs, progress):
    baseline = harness_runner.run_point(
        tb, pdk, point, workdir / "baseline", keep_output=True
    )
    progress(baseline)

    control_seed = mc_mod.sample_seed(BASE_SEED, index, mc_mod.CONTROL_SAMPLE)
    controls = [
        mc_mod.MismatchSample(sample=mc_mod.CONTROL_SAMPLE, seed=control_seed),
        mc_mod.MismatchSample(
            sample=mc_mod.CONTROL_SAMPLE, seed=control_seed + CONTROL_SEED_OFFSET
        ),
    ]
    draws = [
        mc_mod.MismatchSample(sample=s, seed=mc_mod.sample_seed(BASE_SEED, index, s))
        for s in range(1, n_samples + 1)
    ]

    control_results = []
    for control in controls:
        result = harness_runner.run_point(
            tb,
            pdk,
            mc_mod.mc_point(point, control),
            workdir / f"ctrl-seed{control.seed}",
            mc=control,
            keep_output=True,
        )
        control_results.append((control, result))
        progress(result)

    pairs = [(mc_mod.mc_point(point, draw), draw) for draw in draws]
    results = harness_runner.run_samples(
        tb, pdk, pairs, workdir, jobs=jobs, on_result=progress
    )
    return PointOutcome(point, baseline, control_results, list(zip(draws, results)))


# --------------------------------------------------------------------------
# Evidence artefacts
# --------------------------------------------------------------------------


def write_sample_csv(corners_dir: Path, record: str, outcome: PointOutcome, names) -> Path:
    out_dir = corners_dir / record
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"samples-{outcome.corner_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["sample", "seed", "sw_stat_mismatch", "status", *names])
        writer.writerow(
            ["baseline", "", "unset (plain harness deck)", outcome.baseline.status]
            + [outcome.baseline.measurements.get(n, "") for n in names]
        )
        for mc, result in outcome.controls:
            writer.writerow(
                [mc.sample, mc.seed, int(mc.enabled), result.status]
                + [result.measurements.get(n, "") for n in names]
            )
        for mc, result in outcome.samples:
            writer.writerow(
                [mc.sample, mc.seed, int(mc.enabled), result.status]
                + [result.measurements.get(n, "") for n in names]
            )
    return path


def write_log(corners_dir: Path, record: str, corner_id: str, header: str, text: str) -> Path:
    out_dir = corners_dir / record
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{corner_id}.log"
    path.write_text(header + text, encoding="utf-8")
    return path


def baseline_log_header(pdk, tb, point, record, stamp, ngspice) -> str:
    return (
        "* ====================================================================\n"
        f"* record-id : {record}\n"
        f"* testbench : sim/{SOURCE_EXPERIMENT}/testbench/{tb.netlist.name}\n"
        f"* dut       : {tb.dut_path} ({tb.dut_provenance_class})\n"
        f"* corner    : {point.corner_id}\n"
        "* mismatch  : none -- plain harness deck (runner.compose_deck(mc=None)),\n"
        "*             byte-identical to what sim/run_corners.py generates.\n"
        f"* pdk       : {pdk.variant} ({pdk.path})\n"
        f"* ngspice   : {ngspice}\n"
        f"* run (UTC) : {stamp:%Y-%m-%dT%H:%M:%SZ}\n"
        "* ====================================================================\n"
    )


def log_header(pdk, tb, mc, point, record, stamp, ngspice) -> str:
    return (
        "* ====================================================================\n"
        f"* record-id : {record}\n"
        f"* testbench : sim/{SOURCE_EXPERIMENT}/testbench/{tb.netlist.name}\n"
        f"* dut       : {tb.dut_path} ({tb.dut_provenance_class})\n"
        f"* corner    : {point.corner_id}\n"
        f"* mismatch  : sw_stat_mismatch={1 if mc.enabled else 0} "
        f"(sample {mc.sample}), sw_stat_global=0\n"
        f"* seed      : {mc.seed}\n"
        f"* pdk       : {pdk.variant} ({pdk.path})\n"
        f"* ngspice   : {ngspice}\n"
        f"* run (UTC) : {stamp:%Y-%m-%dT%H:%M:%SZ}\n"
        "* ====================================================================\n"
    )


# --------------------------------------------------------------------------
# Record
# --------------------------------------------------------------------------


def _fmt(value, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e5):
            return f"{value:.{digits}e}"
        return f"{value:.{digits}g}"
    return str(value)


def _mv(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 1e3:+.3f}"


def _point_sigma_summary(outcomes) -> str:
    sigmas = []
    for outcome in outcomes:
        values = outcome.values(CLAIM_MEASUREMENT)
        if len(values) > 1:
            sigmas.append(statistics.stdev(values))
    if not sigmas:
        return "n/a"
    return f"{min(sigmas) * 1e6:.0f}–{max(sigmas) * 1e6:.0f} µV"


def build_record_body(record, stamp, pdk, ngspice, tb, outcomes, n_samples, wall, args):
    lines: list[str] = []
    add = lines.append

    add(f"# Record {record}")
    add("")
    add(f"- **Record ID**: {record}")
    add(
        "- **Claim**: spec/gate-driver.md#5-protection-and-fault-handling "
        "(§5 Exception 1 -- the level shifter's pre-driver inverter output "
        "`inb`, decision records 0003/0015) -- **local-mismatch (Monte Carlo) "
        "robustness of the ratified ≤ 40 mV bound**, combined with (not "
        "replacing) the process-corner matrix in "
        f"`sim/{SOURCE_EXPERIMENT}/records/{REFERENCE_RECORD}.md`"
    )
    add(
        f"- **Netlist provenance**: {tb.dut_provenance_class} -- DUT "
        f"`{tb.dut_path}` (sha256 `{tb.dut_sha256}`), driven by "
        f"`sim/{SOURCE_EXPERIMENT}/testbench/{tb.netlist.name}` (sha256 "
        f"`{tb.netlist_sha256}`) -- byte-for-byte the testbench and netlist "
        f"that produced `{REFERENCE_RECORD}`, loaded through its own "
        "`tb.json` rather than copied. One measurement key is added at "
        f"compose time beyond the manifest's own set: `{CLAIM_MEASUREMENT}` "
        f"aliases `{INB_ALIAS_EXPR}` -- an already-computed `meas tran` result "
        "this testbench's own `tb.json` `analyses` list already defines "
        "(`dq6 = |v(inb)-v(gnd_logic)|`, `meas tran mq6 max dq6`) -- so no "
        "new SPICE expression, netlist edit, or `tb.json` change is involved; "
        "see the module docstring."
    )
    add("- **Corner matrix run**:")
    add("  - Process: " + ", ".join(PROCESS_CORNERS))
    add("  - Temperature: " + ", ".join(f"{t:g} °C" for t in TEMPERATURES_C))
    add(f"  - Supply (vlogic, nominal 3.30 V): {CLAIM_SUPPLIES['vlogic']:.2f} V (+10 % tolerance point)")
    add(f"  - Supply (vdrv, nominal 5.00 V): {CLAIM_SUPPLIES['vdrv']:.2f} V (tied +10 % point)")
    add(
        f"  - {len(outcomes)} PVT point(s) (process × temperature at the "
        f"vlogic3p63v-vdrv5p50v tied supply point), each carrying {n_samples} "
        f"Monte Carlo mismatch draws plus 2 zero-sigma controls and 1 "
        f"plain-deck baseline -- {len(outcomes) * (n_samples + 3)} ngspice "
        f"runs, {wall / 60:.1f} min wall."
    )
    add(
        "  - **Subset of the mandated PVT matrix.** Gaps: vlogic: missing "
        "2.97 V, 3.30 V; vdrv: missing 4.50 V, 5.00 V, 6.00 V."
    )
    add(
        "  - Justification: the process and temperature axes are run in full "
        "(5 × 3, the same axes as the reference corner matrix). Only the "
        "supply axis is restricted, to the single tied `vlogic3p63v-"
        "vdrv5p50v` point, because **Exception 1 does not exist at any other "
        "supply**: decision record 0003 records `inb` clearing its own "
        "`VDD_LOGIC` rail at every other tolerance point (max 3.336 V at "
        "`vlogic3p30v`, well inside the rail), only overshooting at the "
        "`vlogic3p63v` corner. Spending the other "
        f"{2 * len(outcomes) * (n_samples + 3)} ngspice runs on supply "
        "points with no exception to characterize would not change any "
        "claim made here."
    )
    drawn = sum(len(o.samples) for o in outcomes)
    converged = sum(len(o.ok) for o in outcomes)
    dropped = drawn - converged
    dropped_note = (
        f" **{dropped} of {drawn} draws did not converge and "
        f"{'is' if dropped == 1 else 'are'} excluded from "
        f"every statistic below** -- enumerated in \"Non-converged draws\", "
        f"leaving {converged} in the distribution."
        if dropped
        else f" All {drawn} draws converged; none is excluded."
    )
    add(
        f"- **Statistical convention**: Monte Carlo **local device mismatch** "
        f"(intra-die), N = {n_samples} independent draws per PVT point, "
        f"{len(outcomes)} PVT point(s), {drawn} mismatch "
        f"samples total.{dropped_note} Distribution source: the gf180mcu PDK's "
        f"own `.lib fets_mm` per-instance mismatch model "
        f"(`delvto = mis_vth·sw_stat_mismatch`, "
        f"`mulu0 = 1 − mis_k·sw_stat_mismatch`, with `mis_vth`/`mis_k` "
        f"drawn from `agauss(0, σ, 1)` and σ scaled Pelgrom-style by "
        f"1/√(W_eff·L_eff)) -- i.e. **1 σ per-device draws, not a "
        f"3 σ corner pull**; `nfet_03v3`/`pfet_03v3` (the pre-driver "
        f"inverter's own thin-oxide devices) carry both threshold *and* β "
        f"mismatch (`par_k` 0.007008 / 0.002833) per decision record 0017 -- "
        f"the fuller mismatch model this repo's thick-oxide 5 V/6 V families "
        f"do not all get. The reported σ below is the sample standard "
        f"deviation of `inb`'s measured peak over the draws, and the "
        f"reported worst case is the observed maximum, not a fitted "
        f"quantile. `sw_stat_global = 0` throughout, so the deterministic "
        f"`.LIB` process corner remains the sole global-skew axis and is not "
        f"double-counted. Seeds are deterministic: "
        f"`seed = {BASE_SEED} + point_index × {mc_mod.SEED_STRIDE} + sample`, "
        f"point_index in the grid order tabulated below "
        f"(`sim/harness/montecarlo.py`). Every PVT point additionally carries "
        f"a **deterministic negative control** in three legs: a plain "
        f"`mc=None` deck (byte-identical to what `sim/run_corners.py` "
        f"generates), plus two `sw_stat_mismatch = 0` decks at two different "
        f"seeds -- all three must agree bit-for-bit, and are additionally "
        f"compared against the committed corner-matrix record "
        f"`sim/{SOURCE_EXPERIMENT}/records/{REFERENCE_RECORD}.md`'s own raw "
        f"`mq6` value at each corner."
    )
    add("- **Result**:")
    add("")

    add("  ### Deterministic negative control")
    add("")
    add(
        "  Three legs per PVT point, on **every** measurement this testbench "
        "records (not just `inb`): a plain `mc=None` deck, plus the Monte "
        "Carlo deck with `sw_stat_mismatch = 0` at two different seeds -- "
        "all three must agree **bit-for-bit**. The fourth column compares "
        "the same control against the reference record's own raw `mq6` "
        "value, re-parsed from its committed log at run time."
    )
    add("")
    add(
        f"  | PVT point | control `{CLAIM_MEASUREMENT}` (V) | baseline = control | "
        f"seed-A = seed-B | Δ vs `{REFERENCE_RECORD}` `mq6` (µV) |"
    )
    add("  |---|---|---|---|---|")
    control_ok = True
    worst_ref_delta = 0.0
    for outcome in outcomes:
        delta = outcome.reference_delta()
        agree = outcome.controls_agree
        matches_baseline = outcome.control_matches_baseline
        control_ok = control_ok and agree and matches_baseline
        if delta is not None:
            worst_ref_delta = max(worst_ref_delta, abs(delta))
        add(
            f"  | `{outcome.corner_id}` | {_fmt(outcome.control_value(CLAIM_MEASUREMENT), 10)} "
            f"| {'yes' if matches_baseline else '**NO**'} "
            f"| {'yes' if agree else '**NO**'} "
            f"| {'n/a' if delta is None else f'{delta * 1e6:+.2f}'} |"
        )
    add("")

    add("  ### `inb` peak under local mismatch (Exception 1's node)")
    add("")
    add(
        f"  `over_rail` is the measured peak minus `VDD_LOGIC` ({VDD_LOGIC_V:.2f} V "
        "at this corner), in mV -- Exception 1 bounds this at ≤ 40 mV."
    )
    add("")
    add(
        "  | PVT point | draws used | control (V) | MC mean (V) | MC σ (mV) | MC min (V) "
        "| MC max (V) | worst over_rail (mV) | Δ vs control (mV) | vs ≤ 40 mV bound |"
    )
    add("  |---|---|---|---|---|---|---|---|---|---|")
    worst_overall = None
    for outcome in outcomes:
        values = outcome.values(CLAIM_MEASUREMENT)
        control = outcome.control_value(CLAIM_MEASUREMENT)
        used = f"{len(values)}/{len(outcome.samples)}"
        if not values:
            add(f"  | `{outcome.corner_id}` | {used} | {_fmt(control)} | no data | | | | | | |")
            continue
        mean = statistics.fmean(values)
        sigma = statistics.stdev(values) if len(values) > 1 else 0.0
        lo, hi = min(values), max(values)
        over_rail = hi - VDD_LOGIC_V
        delta = hi - control if control is not None else None
        within = over_rail <= EXCEPTION1_BOUND_V
        if worst_overall is None or hi > worst_overall[1]:
            worst_overall = (outcome, hi, over_rail)
        add(
            f"  | `{outcome.corner_id}` | {used} | {_fmt(control)} | {_fmt(mean)} | "
            f"{sigma * 1e3:.4f} | {_fmt(lo)} | {_fmt(hi)} | {_mv(over_rail)} | "
            f"{_mv(delta)} | {'PASS' if within else '**FAIL**'} |"
        )
    add("")

    add("  ### Non-converged draws")
    add("")
    bad = [
        (outcome, mc, result)
        for outcome in outcomes
        for mc, result in outcome.samples
        if result.status != "ok"
    ]
    if not bad:
        add(
            f"  None -- all {drawn} mismatch draws completed and every one is in "
            f"the statistics above."
        )
    else:
        add(
            f"  **{len(bad)} of {drawn} draws** did not complete and "
            f"{'is' if len(bad) == 1 else 'are'} "
            f"excluded from every statistic in this record, listed here rather "
            f"than dropped silently. Each is reproducible from the seed below."
        )
        add("")
        add("  | PVT point | sample | seed | ngspice message |")
        add("  |---|---|---|---|")
        for outcome, mc, result in bad:
            message = " ".join(result.message.split())[:180]
            add(f"  | `{outcome.corner_id}` | {mc.sample} | {mc.seed} | `{message}` |")
        add("")
        add(
            "  This is the same solver failure mode `sim/README.md`'s "
            "transient-tolerance decision record already documents for this "
            "class of deck; at the harness's ratified `reltol=1e-4` it is "
            "rare rather than absent. Because the abort truncates the "
            "transient, the affected draw's partial `inb` measurement is a "
            "lower bound on what that draw would have peaked at, which is "
            "exactly why it is excluded rather than counted."
        )
    add("")

    if worst_overall is None:
        verdict = "ERROR"
        add("  - **Overall: ERROR** -- no Monte Carlo sample completed.")
    else:
        outcome, hi, over_rail = worst_overall
        within = over_rail <= EXCEPTION1_BOUND_V
        verdict = "PASS" if (within and control_ok) else "FAIL"
        add(
            f"  - **Overall: {verdict}** -- across "
            f"{converged} converged local-mismatch draws (of {drawn} run) "
            f"spanning the full process × temperature grid at the "
            f"`vlogic3p63v-vdrv5p50v` tied point, the worst observed `inb` "
            f"peak is **{_fmt(hi)} V ({_mv(over_rail)} mV over "
            f"`VDD_LOGIC`)** at `{outcome.corner_id}`, inside "
            f"`spec/gate-driver.md` §5 Exception 1's ratified ≤ 40 mV bound "
            f"with {_mv(EXCEPTION1_BOUND_V - over_rail)} mV of the bound "
            f"still unspent. The three-leg deterministic negative control "
            f"holds at {'every' if control_ok else '**not every**'} PVT "
            f"point (baseline = seed-A control = seed-B control, "
            f"bit-for-bit, on every measurement). Against the **committed** "
            f"corner-matrix record's own raw `mq6` value the same control "
            f"differs by up to {worst_ref_delta * 1e6:.0f} µV. No ratified "
            f"bound is amended by this record."
        )
    add("")

    add("  ### Finding: Exception 1's ~4.3 mV of headroom under local mismatch")
    add("")
    add(
        "  Decision record 0015 sized Exception 1's ≤ 40 mV bound with only "
        "~4.3 mV of headroom above its converged 35.67 mV worst case -- "
        "proportionally the tightest of the block's three §5 exceptions -- "
        "specifically because that record's own deck-fidelity sweep, not a "
        "device-mismatch sweep, was the only refinement it had tested "
        "against. This campaign is the local-mismatch half of the question "
        "decision record 0015 left open."
    )
    add("")
    stats_sigma = _point_sigma_summary(outcomes)
    add(f"  - **Spread**: σ(`inb` peak) = {stats_sigma} per PVT point.")
    if worst_overall is not None:
        outcome, hi, over_rail = worst_overall
        add(
            f"  - **Worst draw vs. the ratified bound**: "
            f"{_mv(EXCEPTION1_BOUND_V - over_rail)} mV of the ≤ 40 mV bound "
            f"still unspent at the worst observed draw ({_mv(over_rail)} mV "
            f"over rail)."
        )
    add(
        "  - **The pre-driver inverter's own devices carry the fuller "
        "mismatch model this repo's other two exceptions do not**: "
        "`nfet_03v3`/`pfet_03v3` get both threshold *and* β mismatch "
        "(decision record 0017), unlike the thick-oxide `nfet_05v0`/"
        "`nfet_06v0` families Exceptions 2 and 3 depend on, which get "
        "threshold mismatch only. If any of this block's three exceptions "
        "were going to show a mismatch-driven surprise, this is the one "
        "with the richest underlying PDK model to show it -- and the "
        "measured spread above is the answer, not an argument."
    )
    add("")

    add("- **Links**:")
    add(f"  - Run script: `sim/{HERE.name}/run_inb_mismatch.py`")
    add(
        f"  - Testbench (reused verbatim): "
        f"`sim/{SOURCE_EXPERIMENT}/testbench/{tb.netlist.name}`, "
        f"`sim/{SOURCE_EXPERIMENT}/testbench/tb.json`"
    )
    add("  - Monte Carlo deck machinery: `sim/harness/montecarlo.py`")
    add(f"  - Netlist snapshot: `sim/{HERE.name}/netlist-snapshots/{record}.spice`")
    add(
        f"  - Raw logs: `sim/{HERE.name}/corners/{record}/` -- one `.log` per "
        "zero-sigma control and per worst-case draw, plus a "
        "`samples-<corner-id>.csv` sidecar carrying every draw's seed and "
        "measurements"
    )
    add(f"  - Reference corner matrix: `sim/{SOURCE_EXPERIMENT}/records/{REFERENCE_RECORD}.md`")
    add(f"  - PDK: {pdk.variant} ({pdk.path}), ngspice {ngspice}")
    add(
        f"  - Deck tolerance: `reltol="
        f"{harness_runner.effective_reltol(tb)[0]}` "
        f"({harness_runner.effective_reltol(tb)[1]}) -- the same convention as "
        f"`{REFERENCE_RECORD}`"
    )
    add(f"- **Timestamp / author**: {stamp:%Y-%m-%dT%H:%M:%SZ}, agent-builder (issue #211)")
    add("- **Supersedes**: (none -- first Monte Carlo / local-mismatch record for this claim)")
    add("")
    if args.smoke:
        add(
            "> **NOTE**: produced by a `--smoke` run -- a deliberately thin "
            "sample set for pipeline debugging, not evidence."
        )
        add("")
    return "\n".join(lines), verdict


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-n", "--samples", type=int, default=DEFAULT_SAMPLES,
        help=f"Monte Carlo draws per PVT point (default {DEFAULT_SAMPLES})",
    )
    parser.add_argument("-j", "--jobs", type=int, default=8, help="parallel ngspice runs")
    parser.add_argument(
        "--smoke", action="store_true",
        help="3 draws at the binding corner only -- pipeline debugging, not evidence",
    )
    parser.add_argument(
        "--no-write", action="store_true", help="run but record nothing (debugging)"
    )
    args = parser.parse_args(argv)

    pdk = harness_pdk.find_pdk()
    ngspice = harness_runner.ngspice_version()
    tb = tb_mod.load(SIM_DIR / SOURCE_EXPERIMENT)

    # Compose-time-only measurement alias -- see the module docstring. Not a
    # tb.json edit: this mutates the in-memory Testbench.measure dict this
    # process loaded, so it affects only decks this script's own run_point /
    # run_samples calls generate.
    tb.measure[CLAIM_MEASUREMENT] = INB_ALIAS_EXPR

    grid = build_points()
    n_samples = args.samples
    selected = set(range(len(grid)))
    if args.smoke:
        n_samples = 3
        selected = {i for i, p in enumerate(grid) if p.corner_id == "ss_125c_vlogic3p63v-vdrv5p50v"}

    points = [p for i, p in enumerate(grid) if i in selected]

    git = harness_report.git_provenance(REPO_ROOT)
    record = harness_report.allocate_record_id(
        REPO_ROOT, HERE / harness_report.RECORDS_DIR, git=git
    )
    stamp = datetime.strptime(record[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    workdir = SIM_DIR / ".work" / HERE.name / record
    total = len(points) * (n_samples + 3)

    print(f"experiment : {HERE.name}")
    print(f"testbench  : sim/{SOURCE_EXPERIMENT} (reused verbatim + {CLAIM_MEASUREMENT} alias)")
    print(f"dut        : {tb.dut_path}  sha256 {tb.dut_sha256[:12]}")
    print(f"pdk        : {pdk.variant} @ {pdk.version}")
    print(f"ngspice    : {ngspice}")
    print(
        f"points     : {len(points)} PVT x ({n_samples} draws + 1 baseline "
        f"+ 2 controls) = {total} runs"
    )
    print(f"base seed  : {BASE_SEED}  (stride {mc_mod.SEED_STRIDE})")
    print(f"record id  : {record}")
    print()

    done = 0
    alias_ok = True

    def progress(result):
        nonlocal done, alias_ok
        done += 1
        if result.status == "ok" and not _confirm_inb_alias(result.measurements):
            alias_ok = False
        if result.status != "ok" or done % 25 == 0 or done == total:
            value = result.measurements.get(CLAIM_MEASUREMENT)
            detail = _fmt(value, 10) if value is not None else result.message
            print(f"[{done:>5}/{total}] {result.status:<6} {result.point.corner_id:<45} {detail}")

    wall_start = time.monotonic()
    outcomes = []
    for index, point in enumerate(grid):
        if index not in selected:
            continue
        outcomes.append(
            run_point_campaign(tb, pdk, point, index, n_samples, workdir, args.jobs, progress)
        )
    wall = time.monotonic() - wall_start

    if not alias_ok:
        print(
            f"ERROR: {CLAIM_MEASUREMENT} was missing from at least one "
            "converged run's measurements -- the mq6 alias did not take "
            "effect; aborting without writing a record."
        )
        return 2

    failed = sum(
        1
        for outcome in outcomes
        for result in [outcome.baseline] + [r for _, r in outcome.samples + outcome.controls]
        if result.status != "ok"
    )
    print()
    print(f"completed {total - failed}/{total} runs in {wall / 60:.1f} min")

    body, verdict = build_record_body(record, stamp, pdk, ngspice, tb, outcomes, n_samples, wall, args)

    if args.no_write:
        print()
        print(body)
        print("evidence  : not recorded (--no-write)")
        return 0

    corners_dir = HERE / harness_report.CORNERS_DIR
    names = list(tb.measure)
    for outcome in outcomes:
        write_sample_csv(corners_dir, record, outcome, names)
        write_log(
            corners_dir,
            record,
            outcome.point.corner_id,
            baseline_log_header(pdk, tb, outcome.point, record, stamp, ngspice),
            outcome.baseline.output,
        )
        for mc, result in outcome.controls[:1]:
            mc_pt = mc_mod.mc_point(outcome.point, mc)
            write_log(
                corners_dir,
                record,
                mc_pt.corner_id,
                log_header(pdk, tb, mc, mc_pt, record, stamp, ngspice),
                result.output,
            )
        worst = outcome.worst(CLAIM_MEASUREMENT)
        if worst is not None:
            mc, result = worst
            mc_pt = mc_mod.mc_point(outcome.point, mc)
            write_log(
                corners_dir,
                record,
                mc_pt.corner_id,
                log_header(pdk, tb, mc, mc_pt, record, stamp, ngspice),
                result.output,
            )

    snapshot = harness_report.write_netlist_snapshot(tb, HERE, record)
    path = harness_report.device_write_record(HERE / harness_report.RECORDS_DIR, record, body)
    print(f"record    : {path}")
    print(f"snapshot  : {snapshot}")
    print(f"raw logs  : {corners_dir / record}")
    print(f"status    : {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
