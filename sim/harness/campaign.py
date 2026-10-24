"""Shared machinery for the Monte Carlo local-mismatch campaigns.

`sim/README.md`'s "Monte Carlo / local-mismatch convention" (decision record
0017) fixes the *shape* of every mismatch campaign in this repo: one plain
`mc=None` baseline plus two differently-seeded `sw_stat_mismatch = 0`
controls per PVT point, N derived-seed draws on top of the deterministic
`.LIB` process corner, non-converged draws disclosed rather than dropped, and
a `samples-<corner-id>.csv` sidecar carrying every draw's seed and parsed
measurements alongside real `.log` files for the two samples a record cites.

That shape is identical across campaigns; only the *claim* differs. This
module holds the shape -- the campaign driver, the `PointOutcome` accessors
every record's tables need, and the evidence writers/formatters -- so the
per-exception scripts under `sim/*-mismatch/` carry only what is genuinely
theirs (which measurement is under claim, which reference record the control
is checked against, and the record's narrative text).

Before issue #258 each campaign script carried its own byte-identical copy of
all of it. The convention it follows is the same one `report.py`'s
`device_*` helpers already establish for the device-characterization side of
the tree: shared evidence plumbing lives in the harness package, so the
layout `sim/README.md` ratifies has exactly one implementation.

Nothing here composes or runs a deck itself -- that is still
`runner.compose_deck` / `runner.run_point` / `runner.run_samples`, with
`montecarlo.py` owning the sampling model. This module is the campaign layer
above them. `run_point_campaign` assumes that `Testbench`/`runner.run_point`
execution layer; `run_device_point_campaign` is the identical skeleton for a
campaign whose execution layer is a bare device-level deck instead (issue
#276 -- see its own docstring).
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import evidence_store
from . import montecarlo as mc_mod
from . import pdk as harness_pdk
from . import report
from . import runner as harness_runner
from . import testbench as tb_mod
from .corners import PvtPoint
from .pdk import Pdk
from .testbench import Testbench

#: Offset of the second zero-sigma control's seed from the first. Two
#: controls at *different* seeds that agree bit-for-bit is what demonstrates
#: the control is genuinely deterministic rather than merely repeatable.
CONTROL_SEED_OFFSET = 5_000_000


# --------------------------------------------------------------------------
# Campaign
# --------------------------------------------------------------------------


class PointOutcome:
    """Everything a record needs about one PVT point's sample set.

    Campaign scripts subclass this to add their own claim-specific
    accessors (a `reference_delta` against their own reference record, a
    "worst node of a set" reduction, ...); everything common to every
    campaign's tables is here.
    """

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
        return self._identical(self.controls[0][1].measurements, self.baseline.measurements)

    def worst(self, name: str):
        """The sample with the highest `name`, as `(MismatchSample, result)`."""
        candidates = [(mc, r) for mc, r in self.ok if name in r.measurements]
        if not candidates:
            return None
        return max(candidates, key=lambda pair: pair[1].measurements[name])


def run_point_campaign(
    tb: Testbench,
    pdk: Pdk,
    point: PvtPoint,
    index: int,
    n_samples: int,
    workdir: Path,
    jobs: int,
    progress,
    *,
    base_seed: int,
    outcome_cls: type[PointOutcome] = PointOutcome,
    control_seed_offset: int = CONTROL_SEED_OFFSET,
) -> PointOutcome:
    """Run one PVT point's baseline + zero-sigma controls + N mismatch draws.

    `index` is the point's position in the campaign's *full* grid, because
    `montecarlo.sample_seed` derives every recorded seed from it -- a
    `--smoke` subset must therefore select from the full grid rather than
    renumber it. `outcome_cls` lets a campaign carry its own
    :class:`PointOutcome` subclass through unchanged.
    """
    # Leg 1: the plain harness deck (mc=None) -- byte-identical to what
    # sim/run_corners.py generates -- re-run here so the control has a
    # same-machine, same-ngspice reference to be exact against.
    baseline = harness_runner.run_point(
        tb, pdk, point, workdir / "baseline", keep_output=True
    )
    progress(baseline)

    control_seed = mc_mod.sample_seed(base_seed, index, mc_mod.CONTROL_SAMPLE)
    controls = [
        mc_mod.MismatchSample(sample=mc_mod.CONTROL_SAMPLE, seed=control_seed),
        mc_mod.MismatchSample(
            sample=mc_mod.CONTROL_SAMPLE, seed=control_seed + control_seed_offset
        ),
    ]
    draws = [
        mc_mod.MismatchSample(sample=s, seed=mc_mod.sample_seed(base_seed, index, s))
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
    return outcome_cls(point, baseline, control_results, list(zip(draws, results)))


def run_device_point_campaign(
    point,
    index: int,
    n_samples: int,
    jobs: int,
    progress,
    run_sample: Callable[[mc_mod.MismatchSample | None], harness_runner.PointResult],
    *,
    base_seed: int,
    outcome_cls: type[PointOutcome] = PointOutcome,
    control_seed_offset: int = CONTROL_SEED_OFFSET,
) -> PointOutcome:
    """The device-level counterpart of :func:`run_point_campaign`.

    Same skeleton -- one plain baseline, two differently-seeded zero-sigma
    controls, N derived-seed draws, `jobs`-wide parallel over the draws --
    and the identical seed policy (`base_seed`, `index`,
    `control_seed_offset`), but for a campaign whose sample-execution layer
    is a bare DC-sweep-and-interpolate deck driven straight off this
    package's library (`pdk.py`/`corners.py`/`montecarlo.py`) rather than a
    `Testbench`-composed transient
    (`sim/low-side-power-switch-ronw-mismatch/run_ronw_mismatch.py` is the
    first such campaign, issue #276). That execution layer does not fit
    `runner.run_point`/`run_samples` -- both assume a `tb.json`-loaded
    `Testbench` -- so it is the one thing parameterized here: `run_sample(mc)`
    runs exactly one ngspice invocation for `point` (`mc=None` selects the
    plain baseline leg; otherwise `mc` selects a control or a mismatch draw)
    and returns a `PointResult`. `point` itself only needs a `.corner_id` --
    this function never reads any of its other fields -- so a `PvtPoint` and
    a device-level equivalent (no supply rail) both work unchanged.
    """
    baseline = run_sample(None)
    progress(baseline)

    control_seed = mc_mod.sample_seed(base_seed, index, mc_mod.CONTROL_SAMPLE)
    controls = [
        mc_mod.MismatchSample(sample=mc_mod.CONTROL_SAMPLE, seed=control_seed),
        mc_mod.MismatchSample(
            sample=mc_mod.CONTROL_SAMPLE, seed=control_seed + control_seed_offset
        ),
    ]
    draws = [
        mc_mod.MismatchSample(sample=s, seed=mc_mod.sample_seed(base_seed, index, s))
        for s in range(1, n_samples + 1)
    ]

    control_results = []
    for control in controls:
        # Same reasoning as run_point_campaign: one at a time, so a bad run
        # cannot collide with the other's scratch state.
        result = run_sample(control)
        control_results.append((control, result))
        progress(result)

    def _do(mc: mc_mod.MismatchSample):
        result = run_sample(mc)
        progress(result)
        return (mc, result)

    if jobs > 1:
        # ThreadPoolExecutor.map returns results in input order (not
        # completion order), so the draw list stays index-aligned with its
        # seeds regardless of how the threads actually interleave -- the same
        # determinism guarantee run_samples gives the Testbench-based path.
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            sample_results = list(pool.map(_do, draws))
    else:
        sample_results = [_do(mc) for mc in draws]

    return outcome_cls(point, baseline, control_results, sample_results)


# --------------------------------------------------------------------------
# Evidence artefacts
# --------------------------------------------------------------------------


def write_sample_csv(
    corners_dir: Path, record: str, outcome: PointOutcome, names: Iterable[str]
) -> Path:
    """All of one PVT point's draws as a flat CSV sidecar.

    Committing one ngspice log per draw would put thousands of near-identical
    files in the evidence tree; committing none would leave the distribution
    unauditable. The compromise `sim/README.md` allows (its `corners/<id>/`
    layout "names the logs; it does not forbid a future sidecar artefact") is
    every draw's seed and parsed measurements here, plus real `.log` files for
    the two samples the record actually cites -- the control and the worst
    case.
    """
    names = list(names)
    out_dir = corners_dir / record
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"samples-{outcome.corner_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        # lineterminator: csv.writer defaults to CRLF, and newline="" passes it
        # through verbatim -- so the sidecar on disk would differ from the LF
        # blob git stores, and every `git add` of a fresh run would warn. These
        # are committed evidence; on-disk and committed bytes must be the same.
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


def write_log(
    corners_dir: Path, record: str, corner_id: str, header: str, text: str
) -> Path:
    """Write ``corners/<record-id>/<corner-id>.log`` -- raw ngspice output."""
    return report.write_corner_log(corners_dir, record, corner_id, header, text)


def baseline_log_header(
    pdk: Pdk,
    tb: Testbench,
    point: PvtPoint,
    record: str,
    stamp,
    ngspice: str,
    *,
    source_experiment: str,
    extra_note_lines: Sequence[str] = (),
) -> str:
    """Provenance banner for negative-control leg 1 (the plain `mc=None` deck).

    `extra_note_lines` are appended to the `mismatch` block's continuation
    lines, for a campaign that wants to say more about what the leg is for.
    """
    notes = "".join(f"*             {line}\n" for line in extra_note_lines)
    return (
        "* ====================================================================\n"
        f"* record-id : {record}\n"
        f"* testbench : sim/{source_experiment}/testbench/{tb.netlist.name}\n"
        f"* dut       : {tb.dut_path} ({tb.dut_provenance_class})\n"
        f"* corner    : {point.corner_id}\n"
        "* mismatch  : none -- plain harness deck (runner.compose_deck(mc=None)),\n"
        "*             byte-identical to what sim/run_corners.py generates.\n"
        f"{notes}"
        f"* pdk       : {pdk.variant} ({pdk.path})\n"
        f"* ngspice   : {ngspice}\n"
        f"* run (UTC) : {stamp:%Y-%m-%dT%H:%M:%SZ}\n"
        "* ====================================================================\n"
    )


def log_header(
    pdk: Pdk,
    tb: Testbench,
    mc: mc_mod.MismatchSample,
    point: PvtPoint,
    record: str,
    stamp,
    ngspice: str,
    *,
    source_experiment: str,
) -> str:
    """Provenance banner for one Monte Carlo draw's (or control's) log."""
    return (
        "* ====================================================================\n"
        f"* record-id : {record}\n"
        f"* testbench : sim/{source_experiment}/testbench/{tb.netlist.name}\n"
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


def write_outcome_logs(
    corners_dir: Path,
    record: str,
    outcome: PointOutcome,
    pdk: Pdk,
    tb: Testbench,
    stamp,
    ngspice: str,
    *,
    source_experiment: str,
    worst: tuple[mc_mod.MismatchSample, harness_runner.PointResult] | None,
    baseline_note_lines: Sequence[str] = (),
) -> None:
    """Write one PVT point's sample CSV and raw logs.

    Writes the CSV sidecar, the plain-deck baseline log, the seed-A zero-sigma
    control log (seed-B is byte-identical; the CSV carries both seeds), and the
    log of `worst` -- the `(MismatchSample, result)` draw the campaign singles
    out, or `None` for no such draw.
    """
    write_sample_csv(corners_dir, record, outcome, list(tb.measure))
    write_log(
        corners_dir,
        record,
        outcome.point.corner_id,
        baseline_log_header(
            pdk, tb, outcome.point, record, stamp, ngspice,
            source_experiment=source_experiment,
            extra_note_lines=baseline_note_lines,
        ),
        outcome.baseline.output,
    )
    draws = list(outcome.controls[:1])
    if worst is not None:
        draws.append(worst)
    for mc, result in draws:
        mc_pt = mc_mod.mc_point(outcome.point, mc)
        write_log(
            corners_dir,
            record,
            mc_pt.corner_id,
            log_header(
                pdk, tb, mc, mc_pt, record, stamp, ngspice,
                source_experiment=source_experiment,
            ),
            result.output,
        )


# --------------------------------------------------------------------------
# Command-line driver
# --------------------------------------------------------------------------


def run_mismatch_main(
    argv,
    *,
    description: str,
    here: Path,
    repo_root: Path,
    sim_dir: Path,
    source_experiment: str,
    default_samples: int,
    base_seed: int,
    outcome_cls: type[PointOutcome],
    build_points: Callable[[], Sequence[PvtPoint]],
    build_record_body: Callable[..., tuple[str, str]],
    smoke_corner_id: str,
    progress_detail: Callable[[harness_runner.PointResult], str],
    corner_width: int,
    worst_sample: Callable[
        [PointOutcome], tuple[mc_mod.MismatchSample, harness_runner.PointResult] | None
    ],
    baseline_note_lines: Sequence[str] = (),
    testbench_note: str = "",
    prepare_testbench: Callable[[Testbench], None] | None = None,
    check_result: Callable[[harness_runner.PointResult], bool] | None = None,
    check_failure_message: str = "",
) -> int:
    """The `main()` shared by the testbench-driven mismatch campaigns.

    Parses `-n/-j/--smoke/--no-write`, loads the PDK/ngspice/testbench, runs the
    campaign over the PVT grid, and writes the record, netlist snapshot and raw
    logs. The per-campaign parts are hooks:

    * `smoke_corner_id` -- the one grid point a `--smoke` run keeps.
    * `progress_detail` / `corner_width` -- the trailing text and the corner
      column width of a progress line.
    * `worst_sample` -- the `(MismatchSample, result)` draw whose raw log is
      written for each point, or `None`.
    * `prepare_testbench` -- an in-memory edit of the loaded testbench.
    * `check_result` -- called on every converged result; if it ever returns
      false the run prints `check_failure_message` and exits 2 unrecorded.

    The full grid is always built, because `sample_seed`'s point_index -- and
    therefore every recorded seed -- is the point's position in *this* order. A
    `--smoke` run selects a subset of it without renumbering.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-n", "--samples", type=int, default=default_samples,
        help=f"Monte Carlo draws per PVT point (default {default_samples})",
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
    tb = tb_mod.load(sim_dir / source_experiment)
    if prepare_testbench is not None:
        prepare_testbench(tb)

    grid = build_points()
    n_samples = args.samples
    selected = set(range(len(grid)))
    if args.smoke:
        n_samples = 3
        selected = {i for i, p in enumerate(grid) if p.corner_id == smoke_corner_id}
    points = [p for i, p in enumerate(grid) if i in selected]

    if not args.no_write:
        evidence_store.preflight_or_exit(repo_root)
    git = report.git_provenance(repo_root)
    record = report.allocate_record_id(repo_root, here / report.RECORDS_DIR, git=git)
    stamp = datetime.strptime(record[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    workdir = sim_dir / ".work" / here.name / record
    total = len(points) * (n_samples + 3)  # + baseline + 2 zero-sigma controls

    print(f"experiment : {here.name}")
    print(f"testbench  : sim/{source_experiment} (reused verbatim{testbench_note})")
    print(f"dut        : {tb.dut_path}  sha256 {tb.dut_sha256[:12]}")
    print(f"pdk        : {pdk.variant} @ {pdk.version}")
    print(f"ngspice    : {ngspice}")
    print(
        f"points     : {len(points)} PVT x ({n_samples} draws + 1 baseline "
        f"+ 2 controls) = {total} runs"
    )
    print(f"base seed  : {base_seed}  (stride {mc_mod.SEED_STRIDE})")
    print(f"record id  : {record}")
    print()

    done = 0
    check_ok = True

    def progress(result):
        nonlocal done, check_ok
        done += 1
        if check_result is not None and result.status == "ok" and not check_result(result):
            check_ok = False
        if result.status != "ok" or done % 25 == 0 or done == total:
            detail = progress_detail(result)
            print(
                f"[{done:>5}/{total}] {result.status:<6} "
                f"{result.point.corner_id:<{corner_width}} {detail}"
            )

    wall_start = time.monotonic()
    outcomes = []
    for index, point in enumerate(grid):
        if index not in selected:
            continue
        outcomes.append(
            run_point_campaign(
                tb, pdk, point, index, n_samples, workdir, args.jobs, progress,
                base_seed=base_seed,
                outcome_cls=outcome_cls,
            )
        )
    wall = time.monotonic() - wall_start

    if not check_ok:
        print(check_failure_message)
        return 2

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

    stage = evidence_store.stage_dir(repo_root, here.name, record)
    corners_dir = stage / report.CORNERS_DIR
    for outcome in outcomes:
        write_outcome_logs(
            corners_dir, record, outcome, pdk, tb, stamp, ngspice,
            source_experiment=source_experiment,
            worst=worst_sample(outcome),
            baseline_note_lines=baseline_note_lines,
        )

    report.write_netlist_snapshot(tb, here, record, out_dir=stage / report.SNAPSHOT_DIR)
    path = here / report.RECORDS_DIR / f"{record}.md"
    manifest = evidence_store.commit_run_or_exit(
        stage, repo_root=repo_root, bench=here.name, rid=record,
        record_text=body, record_path=path,
    )
    print(f"record    : {path}")
    print(f"manifest  : {manifest}")
    print(f"staged    : {stage}")
    print(f"status    : {verdict}")
    return 0 if verdict == "PASS" else 1


# --------------------------------------------------------------------------
# Record formatting
# --------------------------------------------------------------------------


def fmt(value, digits: int = 6) -> str:
    """A measurement for a record table: `n/a`, or `digits` significant figures."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e5):
            return f"{value:.{digits}e}"
        return f"{value:.{digits}g}"
    return str(value)


def mv(value: float | None) -> str:
    """Volts as a millivolt string, the unit every §5 bound is stated in."""
    return "n/a" if value is None else f"{value * 1e3:+.3f}"


def point_sigma_summary(
    outcomes: Iterable[PointOutcome],
    values_of: Callable[[PointOutcome], list[float]],
) -> str:
    """The per-PVT-point sample-sigma range, in µV, as a record-ready string.

    `values_of` extracts the distribution a campaign reports sigma on -- one
    named measurement for a single-node claim, or a per-draw reduction over
    several nodes for a multi-node one.
    """
    sigmas = []
    for outcome in outcomes:
        values = values_of(outcome)
        if len(values) > 1:
            sigmas.append(statistics.stdev(values))
    if not sigmas:
        return "n/a"
    return f"{min(sigmas) * 1e6:.0f}–{max(sigmas) * 1e6:.0f} µV"


def pvt_axes_lines(process_corners, temperatures_c) -> list[str]:
    """The `Process:` / `Temperature:` lines of a record's corner-matrix block."""
    return [
        "  - Process: " + ", ".join(process_corners),
        "  - Temperature: " + ", ".join(f"{t:g} °C" for t in temperatures_c),
    ]


def dropped_note(drawn: int, converged: int, dash: str) -> str:
    """The sentence a record's statistical-convention paragraph uses to say
    how many draws were excluded (or that none were)."""
    dropped = drawn - converged
    if not dropped:
        return f" All {drawn} draws converged; none is excluded."
    return (
        f" **{dropped} of {drawn} draws did not converge and "
        f"{'is' if dropped == 1 else 'are'} excluded from "
        f"every statistic below** {dash} enumerated in \"Non-converged draws\", "
        f"leaving {converged} in the distribution."
    )


def convention_tail(
    base_seed: int,
    source_experiment: str,
    reference_record: str,
    dash: str,
    reference_suffix: str = ".",
) -> str:
    """The seed convention and negative-control description that closes every
    mismatch record's `Statistical convention` bullet, from `sw_stat_global`
    onwards. `reference_suffix` completes the final sentence."""
    return (
        f"`sw_stat_global = 0` throughout, so the deterministic `.LIB` "
        f"process corner remains the sole global-skew axis and is not "
        f"double-counted. Seeds are deterministic: "
        f"`seed = {base_seed} + point_index × {mc_mod.SEED_STRIDE} + sample`, "
        f"point_index in the grid order tabulated below "
        f"(`sim/harness/montecarlo.py`). Every PVT point additionally carries "
        f"a **deterministic negative control** in three legs: a plain "
        f"`mc=None` deck (byte-identical to what `sim/run_corners.py` "
        f"generates), plus two `sw_stat_mismatch = 0` decks at two different "
        f"seeds {dash} all three must agree bit-for-bit, and are additionally "
        f"compared against the committed corner-matrix record "
        f"`sim/{source_experiment}/records/{reference_record}.md`{reference_suffix}"
    )


def control_table_rows(outcomes, probe) -> tuple[list[str], bool, float]:
    """Rows of the deterministic-negative-control table.

    `probe(outcome)` returns `(node, value, delta)`: the node name (or `None`
    for a single-node claim, which drops that column), the control value and
    its delta against the reference record. Returns `(rows, control_ok,
    worst_ref_delta)`, the last two feeding the verdict.
    """
    rows = []
    control_ok = True
    worst_ref_delta = 0.0
    for outcome in outcomes:
        node, value, delta = probe(outcome)
        agree = outcome.controls_agree
        matches_baseline = outcome.control_matches_baseline
        control_ok = control_ok and agree and matches_baseline
        if delta is not None:
            worst_ref_delta = max(worst_ref_delta, abs(delta))
        node_cell = "" if node is None else f"`{node}` | "
        rows.append(
            f"  | `{outcome.corner_id}` | {node_cell}{fmt(value, 10)} "
            f"| {'yes' if matches_baseline else '**NO**'} "
            f"| {'yes' if agree else '**NO**'} "
            f"| {'n/a' if delta is None else f'{delta * 1e6:+.2f}'} |"
        )
    return rows, control_ok, worst_ref_delta


def non_converged_section(
    outcomes, drawn: int, dash: str, explanation: str, closing: str
) -> list[str]:
    """The `Non-converged draws` section, disclosing every excluded draw.

    `explanation` follows "excluded from every statistic in this record" and
    may use `{it_is}` for "It is"/"They are"; `closing` is the paragraph
    after the table. Both are claim-specific wording.
    """
    lines = ["  ### Non-converged draws", ""]
    bad = [
        (outcome, mc, result)
        for outcome in outcomes
        for mc, result in outcome.samples
        if result.status != "ok"
    ]
    if not bad:
        lines.append(
            f"  None {dash} all {drawn} mismatch draws completed and every one is in "
            f"the statistics above."
        )
    else:
        lines.append(
            f"  **{len(bad)} of {drawn} draws** did not complete and "
            f"{'is' if len(bad) == 1 else 'are'} "
            f"excluded from every statistic in this record"
            + explanation.format(it_is="It is" if len(bad) == 1 else "They are")
        )
        lines += ["", "  | PVT point | sample | seed | ngspice message |", "  |---|---|---|---|"]
        for outcome, mc, result in bad:
            message = " ".join(result.message.split())[:180]
            lines.append(f"  | `{outcome.corner_id}` | {mc.sample} | {mc.seed} | `{message}` |")
        lines += ["", closing]
    lines.append("")
    return lines


def verdict_for(within: bool, control_ok: bool) -> str:
    """PASS iff the bound holds and the negative control held everywhere."""
    return "PASS" if (within and control_ok) else "FAIL"


def error_verdict_line(dash: str) -> str:
    return f"  - **Overall: ERROR** {dash} no Monte Carlo sample completed."


def links_lines(
    *,
    record: str,
    script_dir: str,
    script_name: str,
    source_experiment: str,
    reference_record: str,
    tb,
    pdk,
    ngspice: str,
    dash: str,
) -> list[str]:
    """The `Links` block, identical across mismatch records but for the dash."""
    reltol, reltol_source = harness_runner.effective_reltol(tb)
    return [
        "- **Links**:",
        f"  - Run script: `sim/{script_dir}/{script_name}`",
        f"  - Testbench (reused verbatim): "
        f"`sim/{source_experiment}/testbench/{tb.netlist.name}`, "
        f"`sim/{source_experiment}/testbench/tb.json`",
        "  - Monte Carlo deck machinery: `sim/harness/montecarlo.py`",
        f"  - Netlist snapshot: `sim/{script_dir}/netlist-snapshots/{record}.spice`",
        f"  - Raw logs: `sim/{script_dir}/corners/{record}/` {dash} one `.log` per "
        "zero-sigma control and per worst-case draw, plus a "
        "`samples-<corner-id>.csv` sidecar carrying every draw's seed and "
        "measurements",
        f"  - Reference corner matrix: `sim/{source_experiment}/records/{reference_record}.md`",
        f"  - PDK: {pdk.variant} ({pdk.path}), ngspice {ngspice}",
        f"  - Deck tolerance: `reltol={reltol}` ({reltol_source}) {dash} the same "
        f"convention as `{reference_record}`",
    ]


def trailer_lines(stamp, issue: int, supersedes: str, smoke: bool, dash: str) -> list[str]:
    """Timestamp/author, supersedes, and the `--smoke` disclaimer."""
    lines = [
        f"- **Timestamp / author**: {stamp:%Y-%m-%dT%H:%M:%SZ}, agent-builder (issue #{issue})",
        f"- **Supersedes**: {supersedes}",
        "",
    ]
    if smoke:
        lines += [
            f"> **NOTE**: produced by a `--smoke` run {dash} a deliberately thin "
            "sample set for pipeline debugging, not evidence.",
            "",
        ]
    return lines


__all__ = [
    "CONTROL_SEED_OFFSET",
    "PointOutcome",
    "baseline_log_header",
    "control_table_rows",
    "convention_tail",
    "dropped_note",
    "error_verdict_line",
    "fmt",
    "links_lines",
    "log_header",
    "mv",
    "non_converged_section",
    "point_sigma_summary",
    "pvt_axes_lines",
    "run_device_point_campaign",
    "run_mismatch_main",
    "run_point_campaign",
    "trailer_lines",
    "verdict_for",
    "write_log",
    "write_outcome_logs",
    "write_sample_csv",
]
