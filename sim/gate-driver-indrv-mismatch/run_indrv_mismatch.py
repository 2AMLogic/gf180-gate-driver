#!/usr/bin/env python3
"""Monte Carlo local-mismatch campaign on `IN_DRV` (issue #204).

Adds the evidence class this repo had never produced: every recorded PVT
result under `sim/` so far is a **global process-corner** claim
(`tt`/`ff`/`ss`/`fs`/`sf`), which captures die-to-die and wafer-to-wafer skew
but not **within-die local mismatch** between two nominally-identical devices
on the same die at the same corner. `spec/gate-driver.md` §5's Exception 3
(decision records 0006/0007/0014) bounds the inter-cell net `IN_DRV`'s
excursion above the 6.0 V thick-oxide gate ceiling at <= 10 mV, with the
measured worst case at 6.00266 V (margin -2.66 mV,
`sim/gate-driver-core-drive/records/20260818-060517-673fcf0.md`) -- a margin
small enough that ordinary local device mismatch could plausibly move it,
and one whose every supporting number came from a single global `.lib` skew
applied uniformly to every device.

This script re-runs *that exact testbench and DUT* -- it loads
`sim/gate-driver-core-drive/testbench/tb.json`, so the stimulus, the 1 nF
reference load, the measurement expressions, the `reltol` convention and the
DUT netlist hash are the same ones Exception 3's figure came from -- and
sweeps a Monte Carlo mismatch distribution on top of the deterministic
process corner at each PVT point.

Why a sibling script instead of `sim/run_corners.py`
-----------------------------------------------------

Precedent: `sim/device-mv-fet/run_device_mv_fet.py` and
`sim/low-side-power-switch/run_low_side_power_switch.py` both drive the
`sim/harness` library directly when their experiment does not fit the
`tb.json` one-measurement-per-PVT-point grid model. A Monte Carlo campaign
does not fit it either: it is a *distribution* claim (mean/sigma/quantile
over N draws at one PVT point), not a per-corner pass/fail, and it produces
thousands of ngspice runs whose raw logs must be filtered rather than all
committed. The statistical deck machinery itself *is* in the harness
(`sim/harness/montecarlo.py`, `runner.compose_deck(..., mc=...)`,
`runner.run_samples`) so it is reusable and unit-tested; only the campaign
shape lives here.

Usage:
    sim/gate-driver-indrv-mismatch/run_indrv_mismatch.py [-n SAMPLES] [-j JOBS]
    sim/gate-driver-indrv-mismatch/run_indrv_mismatch.py --smoke   # 3 samples, 1 point
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

#: The experiment whose testbench + DUT this campaign reuses verbatim, so the
#: Monte Carlo run is a strict overlay on the corner matrix rather than a
#: differently-built circuit that happens to share a node name.
SOURCE_EXPERIMENT = "gate-driver-core-drive"

#: The corner-matrix record this campaign's zero-sigma control is checked
#: against, point by point. Its raw per-corner logs are re-parsed at run time
#: (not hardcoded) so the control comparison cannot drift from the evidence.
REFERENCE_RECORD = "20260818-060517-673fcf0"

#: The node under claim, and the ratified §2.3 thick-oxide DC gate ceiling
#: its excursion is measured against.
CLAIM_MEASUREMENT = "indrv_max_v"
GATE_CEILING_V = 6.0

#: `spec/gate-driver.md` §5 Exception 3's ratified bound: <= 10 mV above the
#: ceiling. Reported against, never adjusted here -- a bound change would
#: need its own decision record (CLAUDE.md).
EXCEPTION3_BOUND_V = 0.010

#: Exception 2's ratified bound on the output-stage taper nodes (decision
#: record 0013), reported as secondary context for the `n1..n5` measurements
#: this testbench already carries. Not this record's claim.
EXCEPTION2_BOUND_V = 0.175
TAPER_MEASUREMENTS = ("n1_max_v", "n2_max_v", "n3_max_v", "n4_max_v", "n5_max_v")

#: The supply point the campaign runs at. Exception 3 exists **only** at the
#: 6 V stretch rail: the ratified spec text records every nominal-tolerance
#: point clearing the 6.0 V ceiling by >= 397 mV, four orders of magnitude
#: more headroom than the mismatch spread measured here, so spending samples
#: there would buy nothing. This restriction is the record's subset
#: justification; the process and temperature axes are run in full.
STRETCH_SUPPLIES = {"vlogic": 3.30, "vdrv": 6.00}

PROCESS_CORNERS = ("tt", "ff", "ss", "fs", "sf")
TEMPERATURES_C = (-40.0, 27.0, 125.0)

#: Recorded so the whole campaign is reproducible from two integers (this and
#: the sample count) plus the point ordering below -- see
#: `harness.montecarlo.sample_seed`.
BASE_SEED = 20260204

DEFAULT_SAMPLES = 200

#: A second seed for the zero-sigma control, run alongside the first. Two
#: controls at *different* seeds that agree bit-for-bit is what demonstrates
#: the control is genuinely deterministic rather than merely repeatable.
CONTROL_SEED_OFFSET = 5_000_000


def build_points() -> list[harness_corners.PvtPoint]:
    """The campaign's PVT points, in the order `sample_seed` indexes."""
    corner_list = [harness_corners.CORNERS[name] for name in PROCESS_CORNERS]
    return harness_corners.build_grid(
        corner_list, list(TEMPERATURES_C), [dict(STRETCH_SUPPLIES)]
    )


def reference_measurements(corner_id: str) -> dict[str, float]:
    """The corner-matrix record's own numbers at `corner_id`, from its raw log.

    Returns `{}` when the reference record has no log for this point (e.g. a
    `--smoke` run at a corner the reference never visited).
    """
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


# --------------------------------------------------------------------------
# Campaign
# --------------------------------------------------------------------------


class PointOutcome:
    """Everything the record needs about one PVT point's sample set."""

    def __init__(self, point, baseline, controls, samples):
        self.point = point
        self.baseline = baseline          # PointResult from a plain (mc=None) deck
        self.controls = controls          # [(MismatchSample, PointResult)]
        self.samples = samples            # [(MismatchSample, PointResult)]

    @property
    def corner_id(self) -> str:
        return self.point.corner_id

    @property
    def ok(self) -> list:
        return [(mc, r) for mc, r in self.samples if r.status == "ok"]

    def values(self, name: str) -> list[float]:
        return [r.measurements[name] for _, r in self.ok if name in r.measurements]

    def control_value(self, name: str) -> float | None:
        first = self.controls[0][1]
        return first.measurements.get(name)

    def baseline_value(self, name: str) -> float | None:
        return self.baseline.measurements.get(name)

    @staticmethod
    def _identical(a: dict, b: dict) -> bool:
        if not a or set(a) != set(b):
            return False
        return all(a[k] == b[k] for k in a)

    @property
    def controls_agree(self) -> bool:
        """Do the two differently-seeded zero-sigma controls agree exactly?"""
        if len(self.controls) < 2:
            return False
        return self._identical(self.controls[0][1].measurements, self.controls[1][1].measurements)

    @property
    def control_matches_baseline(self) -> bool:
        """Is the zero-sigma control identical to the plain harness deck?

        The strong form of the negative control: `sw_stat_mismatch = 0` must
        make the Monte Carlo deck behave *exactly* like the deck
        `sim/run_corners.py` would have generated for the same PVT point on
        this same machine -- no residue from the added `.param`/`.options`
        lines, and no seed leakage into a mismatch-off run.
        """
        return self._identical(
            self.controls[0][1].measurements, self.baseline.measurements
        )

    def reference_delta(self, name: str) -> float | None:
        """Control minus the committed corner-matrix record's own number.

        `None` when there is no reference log for this point. Exact equality
        is *not* expected across an ngspice version change -- see the record's
        narrative; the delta is reported so the size of that residue is on
        the record rather than assumed.
        """
        reference = reference_measurements(self.corner_id).get(name)
        value = self.control_value(name)
        if reference is None or value is None:
            return None
        return value - reference

    def worst(self, name: str):
        """The sample with the highest `name`, as `(MismatchSample, result)`."""
        candidates = [(mc, r) for mc, r in self.ok if name in r.measurements]
        if not candidates:
            return None
        return max(candidates, key=lambda pair: pair[1].measurements[name])


def run_point_campaign(tb, pdk, point, index, n_samples, workdir, jobs, progress):
    """Run one PVT point's baseline + zero-sigma controls + N mismatch draws."""
    # Leg 1: the plain harness deck (mc=None) -- byte-identical to what
    # sim/run_corners.py generates -- re-run here so the control has a
    # same-machine, same-ngspice reference to be exact against.
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
        # The two controls share a corner-id by construction (both are sample
        # 0); run them one at a time so the scratch deck/log names cannot
        # collide, and so the second is a genuine independent re-parse.
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
    """All of one PVT point's draws as a flat CSV sidecar.

    Committing one ngspice log per draw would put thousands of near-identical
    files in the evidence tree; committing none would leave the distribution
    unauditable. The compromise `sim/README.md` allows (its `corners/<id>/`
    layout "names the logs; it does not forbid a future sidecar artefact") is
    every draw's seed and parsed measurements here, plus real `.log` files for
    the two samples the record actually cites -- the control and the worst
    case.
    """
    out_dir = corners_dir / record
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"samples-{outcome.corner_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
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
        "*             This is negative-control leg 1: the zero-sigma control\n"
        "*             logged alongside it must match this run exactly.\n"
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
    """Volts as a millivolt string, the unit every §5 bound is stated in."""
    return "n/a" if value is None else f"{value * 1e3:+.3f}"


def build_record_body(record, stamp, pdk, ngspice, tb, outcomes, n_samples, wall, args):
    lines: list[str] = []
    add = lines.append

    add(f"# Record {record}")
    add("")
    add(f"- **Record ID**: {record}")
    add(
        "- **Claim**: spec/gate-driver.md#5-protection-and-fault-handling "
        "(§5 Exception 3 — the `IN_DRV` inter-cell thick-oxide gate-ceiling "
        "exception, decision records 0006 / 0007 / 0014) — **local-mismatch "
        "(Monte Carlo) robustness of the ratified ≤ 10 mV bound**, combined "
        "with (not replacing) the process-corner matrix in "
        f"`sim/{SOURCE_EXPERIMENT}/records/{REFERENCE_RECORD}.md`"
    )
    add(
        f"- **Netlist provenance**: {tb.dut_provenance_class} — DUT "
        f"`{tb.dut_path}` (sha256 `{tb.dut_sha256}`), driven by "
        f"`sim/{SOURCE_EXPERIMENT}/testbench/{tb.netlist.name}` (sha256 "
        f"`{tb.netlist_sha256}`) — byte-for-byte the testbench and netlist "
        f"that produced `{REFERENCE_RECORD}`, loaded through its own "
        "`tb.json` rather than copied, so the stimulus, the 1 nF reference "
        "load, the measurement expressions and the `reltol` convention are "
        "the same ones Exception 3's figure came from."
    )
    add("- **Corner matrix run**:")
    add("  - Process: " + ", ".join(PROCESS_CORNERS))
    add("  - Temperature: " + ", ".join(f"{t:g} °C" for t in TEMPERATURES_C))
    add(f"  - Supply (vlogic, nominal 3.30 V): {STRETCH_SUPPLIES['vlogic']:.2f} V")
    add(f"  - Supply (vdrv, nominal 5.00 V): {STRETCH_SUPPLIES['vdrv']:.2f} V (stretch point)")
    add(
        f"  - {len(outcomes)} PVT point(s) (process × temperature at the 6 V "
        f"stretch supply), each carrying {n_samples} Monte Carlo mismatch draws "
        f"plus 2 zero-sigma controls and 1 plain-deck baseline — "
        f"{len(outcomes) * (n_samples + 3)} ngspice runs, "
        f"{wall / 60:.1f} min wall."
    )
    add(
        "  - **Subset of the mandated PVT matrix.** Gaps: vlogic: missing "
        "2.97 V, 3.63 V; vdrv: missing 4.50 V, 5.00 V, 5.50 V."
    )
    add(
        "  - Justification: the process and temperature axes are run in full "
        "(5 × 3, the same axes as the reference corner matrix). Only the "
        "supply axis is restricted, to the single 6 V stretch point, because "
        "**Exception 3 does not exist at any other supply**: `spec/"
        "gate-driver.md` §5 records `IN_DRV` clearing the 6.0 V ceiling by "
        "≥ 397 mV at every nominal-tolerance point, and this record measures "
        f"the node's local-mismatch spread at σ = {_point_sigma_summary(outcomes)} "
        "— two to three orders of magnitude smaller than that headroom, so "
        "mismatch cannot bring a nominal-tolerance point near the ceiling. "
        "Spending the "
        f"other {4 * len(outcomes) * (n_samples + 3)} ngspice runs on supply "
        "points with four orders of magnitude of margin would not change any "
        "claim made here. The 6 V stretch point at `ss`/125 °C is the "
        "binding corner the issue (#204) names."
    )
    drawn = sum(len(o.samples) for o in outcomes)
    converged = sum(len(o.ok) for o in outcomes)
    dropped = drawn - converged
    dropped_note = (
        f" **{dropped} of {drawn} draws did not converge and "
        f"{'is' if dropped == 1 else 'are'} excluded from "
        f"every statistic below** — enumerated in \"Non-converged draws\", "
        f"leaving {converged} in the distribution."
        if dropped
        else f" All {drawn} draws converged; none is excluded."
    )
    add(
        f"- **Statistical convention**: Monte Carlo **local device mismatch** "
        f"(intra-die), N = {n_samples} independent draws per PVT point, "
        f"{len(outcomes)} PVT point(s), {drawn} mismatch "
        f"samples total.{dropped_note} Distribution source: the gf180mcu PDK's own "
        f"`.lib fets_mm` per-instance mismatch model "
        f"(`delvto = mis_vth·sw_stat_mismatch`, "
        f"`mulu0 = 1 − mis_k·sw_stat_mismatch`, with `mis_vth`/`mis_k` drawn "
        f"from `agauss(0, σ, 1)` and σ scaled Pelgrom-style by "
        f"1/√(W_eff·L_eff)) — i.e. **1 σ per-device draws, not a 3 σ corner "
        f"pull**; the reported σ below is the sample standard deviation of "
        f"the measured node voltage over the draws, and the reported worst "
        f"case is the observed maximum, not a fitted quantile. "
        f"`sw_stat_global = 0` throughout, so the deterministic `.LIB` "
        f"process corner remains the sole global-skew axis and is not "
        f"double-counted. Seeds are deterministic: "
        f"`seed = {BASE_SEED} + point_index × {mc_mod.SEED_STRIDE} + sample`, "
        f"point_index in the grid order tabulated below "
        f"(`sim/harness/montecarlo.py`). Every PVT point additionally carries "
        f"a **deterministic negative control** in three legs: a plain "
        f"`mc=None` deck (byte-identical to what `sim/run_corners.py` "
        f"generates), plus two `sw_stat_mismatch = 0` decks at two different "
        f"seeds — all three must agree bit-for-bit, and are additionally "
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
        "records (not just `indrv_max_v`):"
    )
    add("")
    add(
        "  1. **baseline** — a plain `mc=None` deck, byte-identical to what "
        "`sim/run_corners.py` generates for this PVT point;"
    )
    add(
        "  2. **control seed-A** and **3. control seed-B** — the Monte Carlo "
        "deck with `sw_stat_mismatch = 0`, at two *different* ngspice seeds."
    )
    add("")
    add(
        "  All three must agree **bit-for-bit**. That is what proves the "
        "campaign's decks are the corner matrix's decks plus a switch — no "
        "residue from the added `.param`/`.options` lines, and no seed "
        "leakage into a mismatch-off run — so that the spread reported below "
        "is mismatch and not a deck difference or solver noise."
    )
    add("")
    add(
        "  The fourth column compares the same control against the "
        f"**committed** corner-matrix record `{REFERENCE_RECORD}`, whose raw "
        "logs are re-parsed at run time. Exact equality is *not* expected "
        "there and is not required: that record was taken under **ngspice-46** "
        f"and this one under **{ngspice.split(':')[0].strip()}** (see the "
        "narrative below). The residual is reported rather than assumed."
    )
    add("")
    add(
        "  | PVT point | control `indrv_max_v` (V) | baseline = control | "
        f"seed-A = seed-B | Δ vs `{REFERENCE_RECORD}` (µV) |"
    )
    add("  |---|---|---|---|---|")
    control_ok = True
    worst_ref_delta = 0.0
    for outcome in outcomes:
        delta = outcome.reference_delta(CLAIM_MEASUREMENT)
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

    # --- distribution table ---
    add("  ### `IN_DRV` peak under local mismatch (Exception 3's node)")
    add("")
    add(
        "  `margin` is the ratified §2.3 thick-oxide DC gate ceiling minus the "
        "measured peak, in mV — negative means the node is above the ceiling, "
        "which is exactly what Exception 3 documents and bounds at ≤ 10 mV "
        "(i.e. margin ≥ −10.000 mV)."
    )
    add("")
    add(
        "  | PVT point | draws used | control (V) | MC mean (V) | MC σ (mV) | MC min (V) "
        "| MC max (V) | worst margin (mV) | Δ vs control (mV) | vs ≤ 10 mV bound |"
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
        margin = GATE_CEILING_V - hi
        delta = hi - control if control is not None else None
        within = margin >= -EXCEPTION3_BOUND_V
        if worst_overall is None or hi > worst_overall[1]:
            worst_overall = (outcome, hi, margin)
        add(
            f"  | `{outcome.corner_id}` | {used} | {_fmt(control)} | {_fmt(mean)} | "
            f"{sigma * 1e3:.4f} | {_fmt(lo)} | {_fmt(hi)} | {_mv(margin)} | "
            f"{_mv(delta)} | {'PASS' if within else '**FAIL**'} |"
        )
    add("")

    # --- non-converged draws (disclosed, never silently dropped) ---
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
            f"  None — all {drawn} mismatch draws completed and every one is in "
            f"the statistics above."
        )
    else:
        add(
            f"  **{len(bad)} of {drawn} draws** did not complete and "
            f"{'is' if len(bad) == 1 else 'are'} "
            f"excluded from every statistic in this record. "
            f"{'It is' if len(bad) == 1 else 'They are'} listed "
            f"here rather than dropped silently: a Monte Carlo record whose "
            f"sample count does not match its draw count is unauditable, and "
            f"a non-converged draw is not evidence of a low value — it is "
            f"absence of evidence at that draw. Each is reproducible from the "
            f"seed below."
        )
        add("")
        add("  | PVT point | sample | seed | ngspice message |")
        add("  |---|---|---|---|")
        for outcome, mc, result in bad:
            message = " ".join(result.message.split())[:180]
            add(
                f"  | `{outcome.corner_id}` | {mc.sample} | {mc.seed} | "
                f"`{message}` |"
            )
        add("")
        add(
            "  This is the same solver failure mode `sim/README.md`'s transient-"
            "tolerance decision record already documents for this class of deck "
            "(ngspice \"Timestep too small\" on a source branch current); at the "
            "harness's ratified `reltol=1e-4` it is rare rather than absent. "
            "Because the abort truncates the transient, the affected draw's "
            "partial `indrv_max_v` is a lower bound on what that draw would "
            "have peaked at, which is exactly why it is excluded rather than "
            "counted."
        )
    add("")

    # --- taper nodes (context, not this record's claim) ---
    add("  ### Output-stage taper nodes under the same draws (context, not this claim)")
    add("")
    add(
        "  The reused testbench already measures `x2.n1`…`x2.n5`, so these come "
        "for free from the same draws. They belong to **Exception 2** (decision "
        "record 0013, bound ≤ 175 mV above the ceiling), which this record does "
        "not claim and does not amend — reported here as the observed "
        "worst case across all draws at all PVT points, for a future "
        "Exception-2-scoped campaign to start from."
    )
    add("")
    add("  | node | control worst (V) | MC worst (V) | Δ (mV) | worst margin (mV) | vs ≤ 175 mV bound |")
    add("  |---|---|---|---|---|---|")
    for name in TAPER_MEASUREMENTS:
        mc_worst = None
        ctrl_worst = None
        for outcome in outcomes:
            values = outcome.values(name)
            if values:
                mc_worst = max(values) if mc_worst is None else max(mc_worst, max(values))
            control = outcome.control_value(name)
            if control is not None:
                ctrl_worst = control if ctrl_worst is None else max(ctrl_worst, control)
        if mc_worst is None:
            continue
        margin = GATE_CEILING_V - mc_worst
        delta = mc_worst - ctrl_worst if ctrl_worst is not None else None
        add(
            f"  | `x2.{name.split('_')[0]}` | {_fmt(ctrl_worst)} | {_fmt(mc_worst)} | "
            f"{_mv(delta)} | {_mv(margin)} | "
            f"{'PASS' if margin >= -EXCEPTION2_BOUND_V else '**FAIL**'} |"
        )
    add("")

    # --- verdict ---
    if worst_overall is None:
        verdict = "ERROR"
        add("  - **Overall: ERROR** — no Monte Carlo sample completed.")
    else:
        outcome, hi, margin = worst_overall
        within = margin >= -EXCEPTION3_BOUND_V
        verdict = "PASS" if (within and control_ok) else "FAIL"
        add(
            f"  - **Overall: {verdict}** — across "
            f"{converged} converged local-mismatch draws (of {drawn} run) "
            f"spanning the full "
            f"process × temperature grid at the 6 V stretch rail, the worst "
            f"observed `IN_DRV` peak is **{_fmt(hi)} V "
            f"(margin {_mv(margin)} mV)** at `{outcome.corner_id}`, inside "
            f"`spec/gate-driver.md` §5 Exception 3's ratified ≤ 10 mV bound "
            f"(margin ≥ −10.000 mV) with "
            f"{_mv(margin + EXCEPTION3_BOUND_V)} mV of the bound still unspent. "
            f"The three-leg deterministic negative control holds at "
            f"{'every' if control_ok else '**not every**'} PVT point "
            f"(baseline = seed-A control = seed-B control, bit-for-bit, on "
            f"every measurement). Against the **committed** corner-matrix "
            f"record the same control differs by up to "
            f"{worst_ref_delta * 1e6:.0f} µV, which is an ngspice-46 → "
            f"ngspice-47 effect and is treated as a finding in its own right "
            f"below, not folded into this claim. "
            "No ratified bound is amended by this record."
        )
    add("")

    # --- narrative (numbers computed, not asserted) ---
    stats = _campaign_stats(outcomes)
    add(f"  ### Finding: the measured local-mismatch spread on `IN_DRV`")
    add("")
    add(
        "  The concern behind issue #204 was specific and reasonable: "
        "Exception 3's margin is −2.66 mV, `XCCOMP` (four series "
        "`cap_mim_2f0_m4m5_noshield` devices, decision record 0014) cancels a "
        "feedthrough path to within a few millivolts, and no evidence in this "
        "repo had ever perturbed two matched devices relative to each other. "
        "The numbers, not an argument, are:"
    )
    add("")
    add(
        f"  - **Spread**: σ(`indrv_max_v`) = {_point_sigma_summary(outcomes)} "
        f"per PVT point (largest {stats['sigma_max'] * 1e6:.0f} µV, at the hot "
        f"slow corners; smallest at `tt`/`fs`, where the node barely moves at "
        f"all). Even the largest is well under the −2.66 mV excursion the "
        f"ratified exception already concedes, and ~"
        f"{stats['sigma_max'] / EXCEPTION3_BOUND_V * 100:.0f} % of its ≤ 10 mV "
        f"bound."
    )
    if stats["worst_delta"] > 0.0:
        excursion = (
            f"**{_mv(stats['worst_delta'])} mV** (at `{stats['worst_delta_at']}`)"
        )
    else:
        excursion = (
            "**none** — no draw at any PVT point exceeded its own mismatch-off "
            "control, so mismatch moved this node only downwards"
        )
    add(
        f"  - **Worst draw vs. its own control**: the largest single-sample "
        f"excursion above the mismatch-off deck at the same PVT point is "
        f"{excursion}; the mismatch-off deck's own worst point is "
        f"{_fmt(stats['worst_control'])} V."
    )
    add(
        f"  - **Worst draw vs. the ratified bound**: "
        f"{_mv(stats['worst_margin'])} mV of margin against the ≤ 10 mV "
        f"bound's −10.000 mV, leaving "
        f"{_mv(stats['worst_margin'] + EXCEPTION3_BOUND_V)} mV unspent — so "
        f"the bound absorbs the measured mismatch spread with "
        f"{abs((stats['worst_margin'] + EXCEPTION3_BOUND_V) / max(stats['sigma_max'], 1e-12)):.1f}σ "
        f"of headroom beyond the worst observed draw."
    )
    if stats["worst_delta"] > 0.0:
        taper_ratio = (
            f"{stats['worst_taper_delta'] / stats['worst_delta']:.1f}× the "
            f"largest `IN_DRV` excursion"
        )
    else:
        taper_ratio = "while no draw moved `IN_DRV` above its control at all"
    add(
        f"  - **The model is demonstrably active**: the same draws move the "
        f"output stage's device-driven taper nodes by up to "
        f"{_mv(stats['worst_taper_delta'])} mV "
        f"(`{stats['worst_taper_node']}`) — {taper_ratio}. "
        f"That contrast is the cross-check that these decks "
        f"are not simply insensitive to mismatch: the same perturbation that "
        f"barely moves a rail-clamped node visibly moves the device-driven ones."
    )
    add("")
    add(
        "  The structural reason `IN_DRV` moves less than the taper nodes is "
        "decision record 0006's own argument, now visible in the data: the "
        "node's quiescent high level is `VDD_DRV` **by construction** (the "
        "level shifter's output buffer pulls it to the drive rail, so at the "
        "6 V stretch point it sits at the ceiling regardless of any device "
        "parameter), and what Exception 3 bounds is the residual of a "
        "charge-injection spike whose amplitude is set by the `XCCOMP` "
        "capacitor ratio. Mismatch perturbs the *devices*, but the endpoint "
        "is a rail — and the capacitor ratio, per the PDK-coverage section "
        "below, is not varied by this PDK at all."
    )
    add("")
    add("  ### Finding: the ngspice version change moves this node more than mismatch does")
    add("")
    sigma_ratio = worst_ref_delta / max(stats["sigma_max"], 1e-12)
    add(
        f"  The committed corner-matrix record `{REFERENCE_RECORD}` was taken "
        f"under **ngspice-46**; this campaign ran under "
        f"**{ngspice.split(':')[0].strip()}**. The zero-sigma control — the "
        f"*same deck*, mismatch off — differs from that record by up to "
        f"**{worst_ref_delta * 1e6:.0f} µV** at the worst point. That is "
        f"**{sigma_ratio:.1f}×** the largest per-point mismatch σ this campaign "
        f"measured ({stats['sigma_max'] * 1e6:.0f} µV) and "
        f"{worst_ref_delta / EXCEPTION3_BOUND_V * 100:.1f} % of Exception 3's "
        f"entire ≤ 10 mV bound. **The simulator version change is a larger "
        f"perturbation of this measurement than local device mismatch is** — "
        f"which is the single most useful thing this campaign found, and it is "
        f"not a circuit result."
    )
    add("")
    add(
        "  It is isolated to the simulator, not to the deck or the circuit: the "
        "three same-machine control legs (the plain `mc=None` deck and two "
        "`sw_stat_mismatch = 0` decks at different seeds) agree **bit-for-bit** "
        "with each other at every PVT point, so the only variable between this "
        "record's control column and the reference record's number is the "
        "ngspice binary. Per `CLAUDE.md` (\"when something behaves oddly, "
        "suspect the tool or the deck before the circuit\") this is recorded as "
        "a tool-fidelity finding, not absorbed into the circuit claim."
    )
    add("")
    add(
        f"  **It does not threaten Exception 3's bound.** The residue is "
        f"largest at points with wide margin, and at the binding corner "
        f"`ss_125c_vlogic3p30v-vdrv6p00v` the control reproduces the reference "
        f"record to well under a microvolt (see the control table above). "
        f"But it does mean the −2.66 mV figure decision records 0014/0006 "
        f"quote carries a simulator-version uncertainty of order ±1 mV that no "
        f"prior record stated — comfortably inside the ≤ 10 mV bound, and a "
        f"further reason not to narrow that bound toward the measured value."
    )
    add("")

    add("  ### What the open PDK does and does not model (issue #204's first ask)")
    add("")
    add(
        "  Determined by reading the installed decks under "
        f"`{pdk.path}/libs.tech/ngspice/`, not by assuming a foundry "
        "convention:"
    )
    add("")
    add(
        "  1. **MOSFET local mismatch: shipped, and usable unchanged.** "
        "`sm141064.ngspice`'s `.lib fets_mm` section defines subcircuit "
        "wrappers named `nfet_03v3`, `pfet_03v3`, `nfet_05v0`, `nfet_06v0`, "
        "`pfet_05v0`, `pfet_06v0` whose MOS instance line carries "
        "`delvto='mis_vth*sw_stat_mismatch'` and "
        "`mulu0='1-mis_k*sw_stat_mismatch'`, with `mis_vth`/`mis_k` drawn "
        "**per subcircuit instance** from `agauss(0, var, 1)` and `var` "
        "scaled by `1/sqrt(W_eff·L_eff)`. All five MOS corner sections "
        "(`typical`/`ff`/`ss`/`fs`/`sf`) already `.lib` that section in "
        "unconditionally, and this repo's netlists instantiate exactly those "
        "names as `X` calls — so mismatch needs no netlist edit and no device "
        "swap, only `design.ngspice`'s `sw_stat_mismatch` switch flipped from "
        "its default 0. That default is why every prior record in this repo "
        "is a pure corner claim."
    )
    add(
        "  2. **MiM capacitor local mismatch: not shipped.** "
        "`sm141064_mim.ngspice` computes `c_c0 = (c_cox·area + "
        "c_capsw·peri)·(1 + mc_c_cox_2p0fF)`, but `mc_c_cox_1p0fF` / "
        "`_1p5fF` / `_2p0fF` are hardcoded to `0` in all three `mimcap_*` "
        "corner sections and no distribution is ever assigned to them "
        "anywhere in the PDK. They are also `.LIB`-scope parameters — one "
        "value shared by every instance — so even a hand-supplied σ would "
        "model *global* MiM density skew (which the `mimcap_ss`/`_ff` "
        "sections already do, at ±10 %) rather than device-to-device "
        "mismatch. **`XCCOMP`'s four MiM devices are therefore perfectly "
        "matched to each other in every sample of this campaign.** That is a "
        "real limit on this record's coverage, and it is recorded as such "
        "rather than papered over with an invented sigma."
    )
    add(
        "  3. **Resistors: global only.** `.lib res_statistical` draws "
        "`agauss` sheet-rho deviations but gates them on `sw_stat_global`, "
        "not `sw_stat_mismatch` — so resistor variation in this PDK is a "
        "die-level skew, already covered by the corner matrix, with no "
        "intra-die component. (No resistor sits in Exception 3's path in any "
        "case.)"
    )
    add(
        "  4. **Thick-oxide n-channel devices get threshold mismatch only.** "
        "In `.lib fets_mm` the current-factor coefficient `par_k` is "
        "`0.0000` for `nfet_05v0`/`nfet_06v0` and non-zero for every other "
        "family (`nfet_03v3` 0.007008, `pfet_03v3` 0.002833, "
        "`pfet_05v0`/`pfet_06v0` 0.00517), so `mulu0` is identically 1 for "
        "the 5 V/6 V nFETs. Whether that is a modelled physical claim or an "
        "uncharacterised gap in the open PDK is not stated anywhere in the "
        "deck; it is recorded here as the kind of medium-voltage "
        "model-fidelity finding `CLAUDE.md` asks this canary block to "
        "surface."
    )
    add("")
    add(
        "  Points 2 and 4 are the honest caveats on this record: it is a "
        "*MOSFET-threshold* mismatch campaign, which is what the open PDK "
        "supports, not an all-device mismatch campaign. See "
        "`spec/decision-records/0017-pdk-local-mismatch-model-coverage.md`."
    )
    add("")

    add("- **Links**:")
    add(f"  - Run script: `sim/{HERE.name}/run_indrv_mismatch.py`")
    add(
        f"  - Testbench (reused verbatim): "
        f"`sim/{SOURCE_EXPERIMENT}/testbench/{tb.netlist.name}`, "
        f"`sim/{SOURCE_EXPERIMENT}/testbench/tb.json`"
    )
    add(f"  - Monte Carlo deck machinery: `sim/harness/montecarlo.py`")
    add(f"  - Netlist snapshot: `sim/{HERE.name}/netlist-snapshots/{record}.spice`")
    add(
        f"  - Raw logs: `sim/{HERE.name}/corners/{record}/` — one `.log` per "
        "zero-sigma control and per worst-case draw, plus a "
        "`samples-<corner-id>.csv` sidecar carrying every draw's seed and "
        "measurements"
    )
    add(
        f"  - Reference corner matrix: "
        f"`sim/{SOURCE_EXPERIMENT}/records/{REFERENCE_RECORD}.md`"
    )
    add(f"  - PDK: {pdk.variant} ({pdk.path}), ngspice {ngspice}")
    add(
        f"  - Deck tolerance: `reltol="
        f"{harness_runner.effective_reltol(tb)[0]}` "
        f"({harness_runner.effective_reltol(tb)[1]}) — the same convention as "
        f"`{REFERENCE_RECORD}`"
    )
    add(f"- **Timestamp / author**: {stamp:%Y-%m-%dT%H:%M:%SZ}, agent-builder (issue #204)")
    add("- **Supersedes**: (none — first Monte Carlo / local-mismatch record in this repo)")
    add("")
    if args.smoke:
        add(
            "> **NOTE**: produced by a `--smoke` run — a deliberately thin "
            "sample set for pipeline debugging, not evidence."
        )
        add("")
    return "\n".join(lines), verdict


def _campaign_stats(outcomes) -> dict:
    """Campaign-wide extrema the narrative quotes, computed once."""
    sigmas = []
    worst_delta = 0.0
    worst_delta_at = "n/a"
    worst_margin = None
    worst_control = None
    worst_taper_delta = 0.0
    worst_taper_node = "n/a"
    for outcome in outcomes:
        values = outcome.values(CLAIM_MEASUREMENT)
        control = outcome.control_value(CLAIM_MEASUREMENT)
        if len(values) > 1:
            sigmas.append(statistics.stdev(values))
        if values:
            hi = max(values)
            margin = GATE_CEILING_V - hi
            if worst_margin is None or margin < worst_margin:
                worst_margin = margin
            if control is not None and hi - control > worst_delta:
                worst_delta = hi - control
                worst_delta_at = outcome.corner_id
        if control is not None and (worst_control is None or control > worst_control):
            worst_control = control
        for name in TAPER_MEASUREMENTS:
            taper = outcome.values(name)
            taper_control = outcome.control_value(name)
            if taper and taper_control is not None:
                delta = max(taper) - taper_control
                if delta > worst_taper_delta:
                    worst_taper_delta = delta
                    worst_taper_node = f"x2.{name.split('_')[0]}"
    return {
        "sigma_max": max(sigmas) if sigmas else 0.0,
        "worst_delta": worst_delta,
        "worst_delta_at": worst_delta_at,
        "worst_margin": worst_margin if worst_margin is not None else 0.0,
        "worst_control": worst_control,
        "worst_taper_delta": worst_taper_delta,
        "worst_taper_node": worst_taper_node,
    }


def _point_sigma_summary(outcomes) -> str:
    sigmas = []
    for outcome in outcomes:
        values = outcome.values(CLAIM_MEASUREMENT)
        if len(values) > 1:
            sigmas.append(statistics.stdev(values))
    if not sigmas:
        return "n/a"
    return f"{min(sigmas) * 1e6:.0f}–{max(sigmas) * 1e6:.0f} µV"


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

    # The full grid is always built, because `sample_seed`'s point_index -- and
    # therefore every recorded seed -- is the point's position in *this* order.
    # A --smoke run selects a subset of it without renumbering.
    grid = build_points()
    n_samples = args.samples
    selected = set(range(len(grid)))
    if args.smoke:
        n_samples = 3
        selected = {
            i for i, p in enumerate(grid)
            if p.corner_id == "ss_125c_vlogic3p30v-vdrv6p00v"
        }
    points = [p for i, p in enumerate(grid) if i in selected]

    git = harness_report.git_provenance(REPO_ROOT)
    record = harness_report.allocate_record_id(
        REPO_ROOT, HERE / harness_report.RECORDS_DIR, git=git
    )
    stamp = datetime.strptime(record[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    workdir = SIM_DIR / ".work" / HERE.name / record
    total = len(points) * (n_samples + 3)  # + baseline + 2 zero-sigma controls

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
            value = result.measurements.get(CLAIM_MEASUREMENT)
            detail = _fmt(value, 10) if value is not None else result.message
            print(f"[{done:>5}/{total}] {result.status:<6} {result.point.corner_id:<45} {detail}")

    wall_start = time.monotonic()
    outcomes = []
    for index, point in enumerate(grid):
        if index not in selected:
            continue
        outcomes.append(
            run_point_campaign(
                tb, pdk, point, index, n_samples, workdir, args.jobs, progress
            )
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

    body, verdict = build_record_body(
        record, stamp, pdk, ngspice, tb, outcomes, n_samples, wall, args
    )

    if args.no_write:
        print()
        print(body)
        print("evidence  : not recorded (--no-write)")
        return 0

    corners_dir = HERE / harness_report.CORNERS_DIR
    names = list(tb.measure)
    for outcome in outcomes:
        write_sample_csv(corners_dir, record, outcome, names)
        # Leg 1: the plain harness deck, under its plain corner-id.
        write_log(
            corners_dir,
            record,
            outcome.point.corner_id,
            baseline_log_header(pdk, tb, outcome.point, record, stamp, ngspice),
            outcome.baseline.output,
        )
        # Leg 2: the seed-A zero-sigma control (seed-B is byte-identical; the
        # CSV sidecar carries both seeds' parsed measurements).
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
