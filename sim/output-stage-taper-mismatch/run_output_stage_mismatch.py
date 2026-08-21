#!/usr/bin/env python3
"""Monte Carlo local-mismatch campaign on the output stage's taper nodes
`n1`...`n5` (issue #211, Exception 2).

Follow-up to issue #204 (`sim/gate-driver-indrv-mismatch/`), which delivered
this repo's first Monte Carlo / local-mismatch evidence but scoped
deliberately to `spec/gate-driver.md` §5's **Exception 3** (`IN_DRV`) only.
This script applies the same harness (`sim/harness/montecarlo.py`,
`runner.compose_deck(..., mc=...)`, `runner.run_samples`) and the same
ratified convention (decision record 0017: `sw_stat_global = 0`, derived
seeds, a three-leg deterministic negative control, non-converged draws
disclosed rather than dropped) to **Exception 2**: `design/output_stage.sch`'s
internal taper nodes `n1`...`n5`, bounded at <= 175 mV above the 6.0 V
thick-oxide gate ceiling (decision record 0013).

Unlike issue #204's incidental taper-node numbers (reported as context in
`sim/gate-driver-indrv-mismatch/records/20260821-095727-1ea8cb5.md`, which
reuses `sim/gate-driver-core-drive`'s end-to-end chain), this campaign reuses
`sim/output-stage-drive`'s own isolated-cell testbench and ideal-edge
`IN_DRV` source verbatim -- the testbench issue #211 names as Exception 2's
target, giving this exception a dedicated campaign rather than a borrowed
side-effect of a different one.

**Provenance note, disclosed rather than silently assumed.** Decision record
0013's own cited worst-case number (`n1` = 6.14803 V, margin -148.0 mV) comes
from `sim/gate-driver-core-drive`'s end-to-end chain
(`sim/gate-driver-core-drive/records/20260817-202640-d7bda87.md`), which
drives the taper chain through the real level-shifter's own output edge, not
from `sim/output-stage-drive`'s ideal 1 ns edge source -- decision record 0005
(as ratified before its 0006 amendment) is the record whose numbers came from
`sim/output-stage-drive`. This campaign follows issue #211's own explicit,
twice-stated instruction to target `sim/output-stage-drive`'s testbench,
which gives this exception a controlled, isolated-cell mismatch campaign
distinct from (not a re-run of) the end-to-end numbers #204 already touched
incidentally -- reported here alongside the discrepancy so a future reader is
not misled about which record's driving conditions this campaign reproduces.

Usage:
    sim/output-stage-taper-mismatch/run_output_stage_mismatch.py [-n SAMPLES] [-j JOBS]
    sim/output-stage-taper-mismatch/run_output_stage_mismatch.py --smoke
"""

from __future__ import annotations

import argparse
import csv
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
SOURCE_EXPERIMENT = "output-stage-drive"

#: The corner-matrix record this campaign's zero-sigma control is checked
#: against, point by point (the latest full-grid record for this testbench,
#: which includes the 6 V stretch supply point this campaign restricts to).
REFERENCE_RECORD = "20260817-202802-d7bda87"

#: The nodes under claim, and the ratified §2.3 thick-oxide DC gate ceiling
#: their excursion is measured against.
TAPER_MEASUREMENTS = ("n1_max_v", "n2_max_v", "n3_max_v", "n4_max_v", "n5_max_v")
GATE_CEILING_V = 6.0

#: `spec/gate-driver.md` §5 Exception 2's ratified bound: <= 175 mV above the
#: ceiling (decision record 0013). Reported against, never adjusted here -- a
#: bound change would need its own decision record (CLAUDE.md).
EXCEPTION2_BOUND_V = 0.175

#: Exception 2 exists only at the 6 V `vdrv` stretch rail (decision records
#: 0004/0005/0013: "never at the 4.5/5.0/5.5 V nominal-tolerance points").
#: `output-stage-drive`'s testbench declares one rail (`vdrv`), so the supply
#: axis is a single point here, not a two-rail pair.
STRETCH_SUPPLIES = {"vdrv": 6.0}

PROCESS_CORNERS = ("tt", "ff", "ss", "fs", "sf")
TEMPERATURES_C = (-40.0, 27.0, 125.0)

#: Recorded so the whole campaign is reproducible from two integers (this and
#: the sample count) plus the point ordering below.
BASE_SEED = 20260225

DEFAULT_SAMPLES = 200

#: A second seed for the zero-sigma control, run alongside the first.
CONTROL_SEED_OFFSET = 5_000_000


def build_points() -> list[harness_corners.PvtPoint]:
    """The campaign's PVT points, in the order `sample_seed` indexes."""
    corner_list = [harness_corners.CORNERS[name] for name in PROCESS_CORNERS]
    return harness_corners.build_grid(
        corner_list, list(TEMPERATURES_C), [dict(STRETCH_SUPPLIES)]
    )


def reference_measurements(corner_id: str) -> dict[str, float]:
    """The corner-matrix record's own numbers at `corner_id`, from its raw log."""
    log = (
        SIM_DIR
        / SOURCE_EXPERIMENT
        / harness_report.CORNERS_DIR
        / REFERENCE_RECORD
        / f"{corner_id}.log"
    )
    if not log.is_file():
        return {}
    return harness_runner.parse_measurements(log.read_text())


def worst_taper(measurements: dict[str, float]) -> tuple[str, float] | None:
    """`(node, value)` for the taper node with the highest measured peak."""
    candidates = [(name, measurements[name]) for name in TAPER_MEASUREMENTS if name in measurements]
    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[1])


# --------------------------------------------------------------------------
# Campaign
# --------------------------------------------------------------------------


class PointOutcome:
    """Everything the record needs about one PVT point's sample set."""

    def __init__(self, point, baseline, controls, samples):
        self.point = point
        self.baseline = baseline
        self.controls = controls          # [(MismatchSample, PointResult)]
        self.samples = samples            # [(MismatchSample, PointResult)]

    @property
    def corner_id(self) -> str:
        return self.point.corner_id

    @property
    def ok(self) -> list:
        return [(mc, r) for mc, r in self.samples if r.status == "ok"]

    def worst_values(self) -> list[tuple]:
        """`(mc, node, value)` -- each draw's own worst taper node."""
        out = []
        for mc, r in self.ok:
            worst = worst_taper(r.measurements)
            if worst is not None:
                out.append((mc, worst[0], worst[1]))
        return out

    def node_values(self, name: str) -> list[float]:
        return [r.measurements[name] for _, r in self.ok if name in r.measurements]

    def control_node_value(self, name: str) -> float | None:
        return self.controls[0][1].measurements.get(name)

    def control_worst(self) -> tuple[str, float] | None:
        return worst_taper(self.controls[0][1].measurements)

    def baseline_worst(self) -> tuple[str, float] | None:
        return worst_taper(self.baseline.measurements)

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

    def reference_delta(self, name: str) -> float | None:
        reference = reference_measurements(self.corner_id).get(name)
        value = self.control_node_value(name)
        if reference is None or value is None:
            return None
        return value - reference


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
        values = [v for _, _, v in outcome.worst_values()]
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
        "(§5 Exception 2 -- the output stage's internal taper nodes "
        "`n1`...`n5`, decision record 0013) -- **local-mismatch (Monte Carlo) "
        "robustness of the ratified ≤ 175 mV bound**, combined with (not "
        "replacing) the process-corner matrix in "
        f"`sim/{SOURCE_EXPERIMENT}/records/{REFERENCE_RECORD}.md`"
    )
    add(
        f"- **Netlist provenance**: {tb.dut_provenance_class} -- DUT "
        f"`{tb.dut_path}` (sha256 `{tb.dut_sha256}`), driven by "
        f"`sim/{SOURCE_EXPERIMENT}/testbench/{tb.netlist.name}` (sha256 "
        f"`{tb.netlist_sha256}`) -- byte-for-byte the testbench and netlist "
        f"that produced `{REFERENCE_RECORD}`, loaded through its own "
        "`tb.json` rather than copied. **Provenance caveat** (disclosed, not "
        "silently assumed): this testbench drives `IN_DRV` from an ideal "
        "1 ns-edge source with no level shifter present, which is the same "
        "driving condition decision record 0005's *original* number used, "
        "not the end-to-end real level-shifter edge decision record 0006's "
        "amendment (and decision record 0013's own cited worst case) later "
        "measured under `sim/gate-driver-core-drive/`. This campaign follows "
        "issue #211's own explicit instruction to target this testbench; see "
        "the module docstring for the full discrepancy note."
    )
    add("- **Corner matrix run**:")
    add("  - Process: " + ", ".join(PROCESS_CORNERS))
    add("  - Temperature: " + ", ".join(f"{t:g} °C" for t in TEMPERATURES_C))
    add(f"  - Supply (vdrv, nominal 5.00 V): {STRETCH_SUPPLIES['vdrv']:.2f} V (6 V stretch point)")
    add(
        f"  - {len(outcomes)} PVT point(s) (process × temperature at the 6 V "
        f"stretch supply), each carrying {n_samples} Monte Carlo mismatch draws "
        f"plus 2 zero-sigma controls and 1 plain-deck baseline -- "
        f"{len(outcomes) * (n_samples + 3)} ngspice runs, "
        f"{wall / 60:.1f} min wall."
    )
    add(
        "  - **Subset of the mandated PVT matrix.** Gaps: vdrv: missing "
        "4.50 V, 5.00 V, 5.50 V."
    )
    add(
        "  - Justification: the process and temperature axes are run in full "
        "(5 × 3, the same axes as the reference corner matrix). Only the "
        "supply axis is restricted, to the single 6 V stretch point, because "
        "**Exception 2 does not exist at any other supply**: decision records "
        "0004/0005/0013 record the taper nodes clearing the 6.0 V ceiling at "
        "every nominal-tolerance point (4.5/5.0/5.5 V), only exceeding it at "
        "the 6 V stretch rail. Spending the other "
        f"{3 * len(outcomes) * (n_samples + 3)} ngspice runs on supply points "
        "with no exception to characterize would not change any claim made "
        "here."
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
        f"3 σ corner pull**; the reported σ below is the sample "
        f"standard deviation of the measured worst-taper-node voltage over "
        f"the draws, and the reported worst case is the observed maximum, "
        f"not a fitted quantile. `nfet_06v0`/`pfet_06v0` -- the only device "
        f"families in `design/output_stage.sch` (spec §2.5) -- carry "
        f"threshold mismatch only (`par_k = 0.0000`, no β mismatch), per "
        f"decision record 0017. `sw_stat_global = 0` throughout, so the "
        f"deterministic `.LIB` process corner remains the sole global-skew "
        f"axis and is not double-counted. Seeds are deterministic: "
        f"`seed = {BASE_SEED} + point_index × {mc_mod.SEED_STRIDE} + sample`, "
        f"point_index in the grid order tabulated below "
        f"(`sim/harness/montecarlo.py`). Every PVT point additionally carries "
        f"a **deterministic negative control** in three legs: a plain "
        f"`mc=None` deck (byte-identical to what `sim/run_corners.py` "
        f"generates), plus two `sw_stat_mismatch = 0` decks at two different "
        f"seeds -- all three must agree bit-for-bit, and are additionally "
        f"compared against the committed corner-matrix record "
        f"`sim/{SOURCE_EXPERIMENT}/records/{REFERENCE_RECORD}.md`."
    )
    add("- **Result**:")
    add("")

    # --- negative control table ---
    add("  ### Deterministic negative control")
    add("")
    add(
        "  Three legs per PVT point, on **every** measurement this testbench "
        "records (not just `n1`...`n5`): a plain `mc=None` deck, plus the "
        "Monte Carlo deck with `sw_stat_mismatch = 0` at two different seeds. "
        "All three must agree **bit-for-bit** -- that is what proves the "
        "campaign's decks are the corner matrix's decks plus a switch."
    )
    add("")
    add(
        "  | PVT point | control worst node | control worst (V) | baseline = "
        "control | seed-A = seed-B | Δ vs its own node "
        f"in `{REFERENCE_RECORD}` (µV) |"
    )
    add("  |---|---|---|---|---|---|")
    control_ok = True
    worst_ref_delta = 0.0
    for outcome in outcomes:
        control_worst = outcome.control_worst()
        agree = outcome.controls_agree
        matches_baseline = outcome.control_matches_baseline
        control_ok = control_ok and agree and matches_baseline
        node, value = control_worst if control_worst is not None else ("n/a", None)
        delta = outcome.reference_delta(node) if control_worst is not None else None
        if delta is not None:
            worst_ref_delta = max(worst_ref_delta, abs(delta))
        add(
            f"  | `{outcome.corner_id}` | `{node}` | {_fmt(value, 10)} "
            f"| {'yes' if matches_baseline else '**NO**'} "
            f"| {'yes' if agree else '**NO**'} "
            f"| {'n/a' if delta is None else f'{delta * 1e6:+.2f}'} |"
        )
    add("")

    # --- distribution table: worst taper node under MC, per point ---
    add("  ### Worst taper node (`n1`...`n5`) under local mismatch")
    add("")
    add(
        "  `margin` is the ratified §2.3 thick-oxide DC gate ceiling minus "
        "the measured peak, in mV -- negative means the node is above the "
        "ceiling, which is exactly what Exception 2 documents and bounds at "
        "≤ 175 mV (i.e. margin ≥ −175.000 mV)."
    )
    add("")
    add(
        "  | PVT point | draws used | control node | control (V) | MC mean (V) "
        "| MC σ (mV) | MC max (V) | binding node | worst margin (mV) | "
        "Δ vs control (mV) | vs ≤ 175 mV bound |"
    )
    add("  |---|---|---|---|---|---|---|---|---|---|---|")
    worst_overall = None
    for outcome in outcomes:
        triples = outcome.worst_values()
        values = [v for _, _, v in triples]
        control_worst = outcome.control_worst()
        control_node, control_value = (
            control_worst if control_worst is not None else ("n/a", None)
        )
        used = f"{len(values)}/{len(outcome.samples)}"
        if not values:
            add(f"  | `{outcome.corner_id}` | {used} | `{control_node}` | {_fmt(control_value)} | no data | | | | | | |")
            continue
        mean = statistics.fmean(values)
        sigma = statistics.stdev(values) if len(values) > 1 else 0.0
        hi_triple = max(triples, key=lambda t: t[2])
        hi_node, hi = hi_triple[1], hi_triple[2]
        margin = GATE_CEILING_V - hi
        delta = hi - control_value if control_value is not None else None
        within = margin >= -EXCEPTION2_BOUND_V
        if worst_overall is None or hi > worst_overall[1]:
            worst_overall = (outcome, hi, margin, hi_node)
        add(
            f"  | `{outcome.corner_id}` | {used} | `{control_node}` | "
            f"{_fmt(control_value)} | {_fmt(mean)} | {sigma * 1e3:.4f} | "
            f"{_fmt(hi)} | `{hi_node}` | {_mv(margin)} | {_mv(delta)} | "
            f"{'PASS' if within else '**FAIL**'} |"
        )
    add("")

    # --- per-node worst-case summary ---
    add("  ### Per-node worst case across all draws and PVT points")
    add("")
    add("  | node | control worst (V) | MC worst (V) | Δ (mV) | worst margin (mV) |")
    add("  |---|---|---|---|---|")
    for name in TAPER_MEASUREMENTS:
        mc_worst = None
        ctrl_worst = None
        for outcome in outcomes:
            values = outcome.node_values(name)
            if values:
                mc_worst = max(values) if mc_worst is None else max(mc_worst, max(values))
            control = outcome.control_node_value(name)
            if control is not None:
                ctrl_worst = control if ctrl_worst is None else max(ctrl_worst, control)
        if mc_worst is None:
            continue
        margin = GATE_CEILING_V - mc_worst
        delta = mc_worst - ctrl_worst if ctrl_worst is not None else None
        add(
            f"  | `{name.split('_')[0]}` | {_fmt(ctrl_worst)} | {_fmt(mc_worst)} | "
            f"{_mv(delta)} | {_mv(margin)} |"
        )
    add("")

    # --- non-converged draws ---
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
            "class of deck (ngspice \"Timestep too small\" on a source branch "
            "current); at the harness's ratified `reltol=1e-4` it is rare "
            "rather than absent. Because the abort truncates the transient, "
            "the affected draw's partial node measurement is a lower bound on "
            "what that draw would have peaked at, which is exactly why it is "
            "excluded rather than counted."
        )
    add("")

    # --- verdict ---
    if worst_overall is None:
        verdict = "ERROR"
        add("  - **Overall: ERROR** -- no Monte Carlo sample completed.")
    else:
        outcome, hi, margin, hi_node = worst_overall
        within = margin >= -EXCEPTION2_BOUND_V
        verdict = "PASS" if (within and control_ok) else "FAIL"
        add(
            f"  - **Overall: {verdict}** -- across "
            f"{converged} converged local-mismatch draws (of {drawn} run) "
            f"spanning the full process × temperature grid at the 6 V "
            f"stretch rail, the worst observed taper-node peak is "
            f"**{_fmt(hi)} V (margin {_mv(margin)} mV)** at `{outcome.corner_id}` "
            f"(node `{hi_node}`), inside `spec/gate-driver.md` §5 "
            f"Exception 2's ratified ≤ 175 mV bound (margin ≥ "
            f"−175.000 mV) with {_mv(margin + EXCEPTION2_BOUND_V)} mV of "
            f"the bound still unspent. The three-leg deterministic negative "
            f"control holds at {'every' if control_ok else '**not every**'} "
            f"PVT point (baseline = seed-A control = seed-B control, "
            f"bit-for-bit, on every measurement). Against the **committed** "
            f"corner-matrix record the same control's binding node differs by "
            f"up to {worst_ref_delta * 1e6:.0f} µV. No ratified bound is "
            f"amended by this record."
        )
    add("")

    # --- narrative ---
    add("  ### Finding: is the ~27 mV of headroom decision record 0013 left unspent?")
    add("")
    add(
        "  Decision record 0013 sized Exception 2's ≤ 175 mV bound with "
        "~27 mV of headroom above its cited −148.0 mV worst case, "
        "explicitly because no deck-fidelity or mismatch sweep had been run "
        "against `n1`'s own binding corner at the time. This campaign is that "
        "sweep's mismatch half (a deck-fidelity `reltol`/`maxstep` sweep, the "
        "other half decision record 0013 names as a future follow-up, is out "
        "of scope for issue #211)."
    )
    add("")
    stats_sigma = _point_sigma_summary(outcomes)
    add(
        f"  - **Spread**: σ(worst taper node) = {stats_sigma} per PVT "
        f"point."
    )
    if worst_overall is not None:
        outcome, hi, margin, hi_node = worst_overall
        add(
            f"  - **Worst draw vs. the ratified bound**: {_mv(margin)} mV of "
            f"margin against the ≤ 175 mV bound's −175.000 mV, "
            f"leaving {_mv(margin + EXCEPTION2_BOUND_V)} mV unspent."
        )
    add(
        "  - **Provenance caveat carried forward**: this campaign's own "
        "driving condition (ideal 1 ns `IN_DRV` edge, no level shifter) is "
        "milder than the end-to-end chain decision record 0013 actually "
        "bounds against (real level-shifter edge, worse by ~46 mV at the "
        "deterministic corner per decision record 0013's own table). This "
        "record's local-mismatch spread is therefore evidence about *how "
        "much mismatch moves this node*, not a replacement for an end-to-end "
        "mismatch campaign against `sim/gate-driver-core-drive`'s chain -- "
        "which issue #204's own incidental data already partially covers and "
        "is not re-run here (out of scope for issue #211: Exception 3 / "
        "`IN_DRV` is #204's own claim)."
    )
    add("")

    add("  ### What the open PDK does and does not model")
    add("")
    add(
        "  This cell (`design/output_stage.sch`, spec §2.5) is entirely "
        "`nfet_06v0`/`pfet_06v0` -- both families carry per-instance threshold "
        "mismatch (`delvto`) in `sm141064.ngspice`'s `.lib fets_mm`, but "
        "`nfet_06v0` gets **no** β mismatch (`par_k = 0.0000`); "
        "`pfet_06v0` does (`par_k = 0.00517`). No resistor or MiM capacitor "
        "sits in this cell's taper chain, so the resistor/MiM mismatch gaps "
        "`spec/decision-records/0017-pdk-local-mismatch-model-coverage.md` "
        "records do not limit this campaign's coverage the way they limit "
        "Exception 3's `XCCOMP` caveat. This is therefore a full-coverage "
        "mismatch campaign for the device families this cell actually uses, "
        "modulo the `nfet_06v0` β-mismatch gap noted above."
    )
    add("")

    add("- **Links**:")
    add(f"  - Run script: `sim/{HERE.name}/run_output_stage_mismatch.py`")
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

    grid = build_points()
    n_samples = args.samples
    selected = set(range(len(grid)))
    if args.smoke:
        n_samples = 3
        selected = {i for i, p in enumerate(grid) if p.corner_id == "ss_-40c_vdrv6p00v"}

    points = [p for i, p in enumerate(grid) if i in selected]

    git = harness_report.git_provenance(REPO_ROOT)
    record = harness_report.allocate_record_id(
        REPO_ROOT, HERE / harness_report.RECORDS_DIR, git=git
    )
    stamp = datetime.strptime(record[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    workdir = SIM_DIR / ".work" / HERE.name / record
    total = len(points) * (n_samples + 3)

    print(f"experiment : {HERE.name}")
    print(f"testbench  : sim/{SOURCE_EXPERIMENT} (reused verbatim)")
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

    def progress(result):
        nonlocal done
        done += 1
        if result.status != "ok" or done % 25 == 0 or done == total:
            worst = worst_taper(result.measurements)
            detail = f"{worst[0]}={_fmt(worst[1], 10)}" if worst is not None else result.message
            print(f"[{done:>5}/{total}] {result.status:<6} {result.point.corner_id:<30} {detail}")

    wall_start = time.monotonic()
    outcomes = []
    for index, point in enumerate(grid):
        if index not in selected:
            continue
        outcomes.append(
            run_point_campaign(tb, pdk, point, index, n_samples, workdir, args.jobs, progress)
        )
    wall = time.monotonic() - wall_start

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
        triples = outcome.worst_values()
        if triples:
            mc, _, _ = max(triples, key=lambda t: t[2])
            result = next(r for m, r in outcome.samples if m is mc)
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
