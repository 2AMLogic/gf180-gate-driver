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

One thing here is not Monte Carlo at all: `run_device_main` (issue #450), the
command-line driver shared by the *device-characterization* runners
(`sim/device-mv-fet`, `sim/low-side-power-switch`,
`sim/uvlo-trip-verification`). It lives beside `run_mismatch_main` for the
same reason that one does -- a runner's driver is evidence plumbing, and this
module is where the layout `sim/README.md` ratifies has exactly one
implementation -- so what this file really holds is "the run shape of a
recorded experiment", of which the mismatch campaign is one shape and a
PVT-grid device sweep is the other.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from collections.abc import Callable, Iterable, Sequence
from typing import Any, NamedTuple
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


def _point_seed_plan(
    base_seed: int, index: int, n_samples: int, control_seed_offset: int
) -> tuple[list[mc_mod.MismatchSample], list[mc_mod.MismatchSample]]:
    """The seeds one PVT point's campaign legs run at, as ``(controls, draws)``.

    The seed policy both drivers below share (decision record 0017): the two
    zero-sigma controls sit at ``sample_seed(base_seed, index,
    CONTROL_SAMPLE)`` and that plus ``control_seed_offset`` -- different
    seeds agreeing bit-for-bit is what shows the control is deterministic,
    not merely repeatable -- and draw ``s`` (1..``n_samples``) sits at
    ``sample_seed(base_seed, index, s)``. Deriving it in one place (issue
    #578) is what lets a record reproduce any draw it cites without knowing
    which execution layer ran the point.
    """
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
    return controls, draws


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

    controls, draws = _point_seed_plan(
        base_seed, index, n_samples, control_seed_offset
    )

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

    controls, draws = _point_seed_plan(
        base_seed, index, n_samples, control_seed_offset
    )

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
# Run envelope
# --------------------------------------------------------------------------


class RunContext(NamedTuple):
    """What :func:`start_run` mints before a campaign loop starts.

    `args` is the parsed `-n/-j/--smoke/--no-write` namespace, or `None`
    for a driver without a CLI (the device-characterization runners take no
    flags). `git` / `record` / `stamp` are the provenance triple every
    record body and log banner needs.
    """

    args: argparse.Namespace | None
    pdk: Pdk
    ngspice: str
    git: dict
    record: str
    stamp: datetime


def disclose_dirty_tree(git: dict, record: str) -> None:
    """The dirty-input-tree disclosure every recorded run prints (#541).

    One copy of the warning: `start_run` prints it for the envelope's
    drivers, and `harness/cli.py` (`run_corners.py`) — which keeps its own
    head because its `--no-write` is offline debugging and must keep
    skipping the evidence preflight — calls this so a dirty tree has the
    same answer at every recorded-run entry point.
    """
    if git["dirty"]:
        print(
            "warning: input tree (design/testbench/harness/docs) is dirty; "
            f"record {record} will not be reproducible from commit "
            f"{git['short']} alone"
        )


def start_run(
    argv: Sequence[str] | None = None,
    *,
    parse_cli: bool = True,
    description: str | None = None,
    here: Path,
    repo_root: Path,
    default_samples: int | None = None,
) -> RunContext:
    """The shared head of a recorded run's `main()` (issue #483).

    Parses the `-n/-j/--smoke/--no-write` flags every recorded run takes
    (`parse_cli=False` skips this -- the device-characterization drivers
    have no CLI), discovers the PDK and ngspice, runs the evidence-store
    preflight unless `--no-write`, mints the record id from the tree's git
    provenance, parses its stamp, and discloses a dirty input tree. The
    campaign loop, its banner and the record body stay the caller's; the
    tail is :func:`finish_run` / :func:`commit_run`.

    The dirty-tree disclosure used to have three divergent answers: ronw
    warned from its private `main()`, `run_device_main` warned from its own
    copy, and `run_mismatch_main` never -- even though all of them read
    `report.git_provenance()`. It lives here, so every recorded run using
    the envelope says so in the same words. Emitting it everywhere is the
    behaviour-preserving superset; whether the record *body* should also
    carry `report.render_record`'s in-record disclosure is a separate call,
    deliberately left to a follow-up.
    """
    if parse_cli:
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
    else:
        args = None

    pdk = harness_pdk.find_pdk()
    ngspice = harness_runner.ngspice_version()

    if args is None or not args.no_write:
        evidence_store.preflight_or_exit(repo_root)
    git = report.git_provenance(repo_root)
    record = report.allocate_record_id(repo_root, here / report.RECORDS_DIR, git=git)
    stamp = datetime.strptime(record[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)

    disclose_dirty_tree(git, record)

    return RunContext(
        args=args, pdk=pdk, ngspice=ngspice, git=git, record=record, stamp=stamp
    )


def commit_run(
    *, stage: Path, repo_root: Path, here: Path, record: str, body: str
) -> tuple[Path, Path]:
    """The closing commit block shared by every recorded run.

    Hands the staged evidence to :func:`evidence_store.commit_run_or_exit`
    and returns the committed record's path and the manifest it produced.
    """
    path = here / report.RECORDS_DIR / f"{record}.md"
    manifest = evidence_store.commit_run_or_exit(
        stage, repo_root=repo_root, bench=here.name, rid=record,
        record_text=body, record_path=path,
    )
    return path, manifest


def finish_run(
    *,
    stage: Path,
    repo_root: Path,
    here: Path,
    record: str,
    body: str,
    verdict: str,
    anomalies: Sequence[str] = (),
) -> int:
    """The closing tail of a recorded run's `main()`: commit, then report.

    Commits via :func:`commit_run`, prints the `record` / `manifest` /
    `staged` / `status` block, then the optional `anomalies` list --
    disclosed-but-not-fatal findings a run wants on the console (issue
    #483: ronw was the only runner with that channel, as a private fork of
    this block). Returns `0` iff the verdict is `PASS`.
    """
    path, manifest = commit_run(
        stage=stage, repo_root=repo_root, here=here, record=record, body=body
    )
    print(f"record    : {path}")
    print(f"manifest  : {manifest}")
    print(f"staged    : {stage}")
    print(f"status    : {verdict}")
    if anomalies:
        print(f"anomalies : {len(anomalies)}")
        for line in anomalies:
            print(f"  - {line}")
    return 0 if verdict == "PASS" else 1


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

    The `-n/-j/--smoke/--no-write` parsing, the PDK/ngspice discovery, the
    evidence-store preflight, the record-id minting and its stamp, the
    dirty-tree disclosure, and the closing commit + report block are the
    shared run envelope (:func:`start_run` / :func:`finish_run`, issue
    #483). The per-campaign parts are hooks:

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
    run = start_run(
        argv,
        description=description,
        here=here,
        repo_root=repo_root,
        default_samples=default_samples,
    )
    args = run.args
    pdk = run.pdk
    ngspice = run.ngspice
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

    workdir = sim_dir / ".work" / here.name / run.record
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
    print(f"record id  : {run.record}")
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
        run.record, run.stamp, pdk, ngspice, tb, outcomes, n_samples, wall, args
    )

    if args.no_write:
        print()
        print(body)
        print("evidence  : not recorded (--no-write)")
        return 0

    stage = evidence_store.stage_dir(repo_root, here.name, run.record)
    corners_dir = stage / report.CORNERS_DIR
    for outcome in outcomes:
        write_outcome_logs(
            corners_dir, run.record, outcome, pdk, tb, run.stamp, ngspice,
            source_experiment=source_experiment,
            worst=worst_sample(outcome),
            baseline_note_lines=baseline_note_lines,
        )

    report.write_netlist_snapshot(tb, here, run.record, out_dir=stage / report.SNAPSHOT_DIR)
    return finish_run(
        stage=stage, repo_root=repo_root, here=here, record=run.record,
        body=body, verdict=verdict,
    )


def run_device_main(
    *,
    here: Path,
    repo_root: Path,
    deck: Path,
    process_corners: Sequence[Any],
    temperatures_c: Sequence[float],
    run_point: Callable[[Pdk, Any, float], tuple[str, str, dict]],
    build_record_body: Callable[..., tuple[str, Any]],
    summarize: Callable[[Any], Sequence[str]],
    corner_key: Callable[[Any], str] = lambda corner: corner,
    progress_detail: Callable[[str, dict], str] = lambda cid, extracted: "ok",
) -> int:
    """The `main()` shared by the device-characterization runners.

    The device-family counterpart of :func:`run_mismatch_main` (issue #450).
    `sim/device-mv-fet`, `sim/low-side-power-switch` and
    `sim/uvlo-trip-verification` each carried a near-identical copy of this
    skeleton: PDK/ngspice discovery, the evidence-store preflight, minting a
    record-id, the process-corner x temperature loop with its corner log,
    freezing the deck as the record's netlist snapshot, and committing the
    run. Those parts live here; what genuinely varies is passed in.

    * `process_corners` / `temperatures_c` -- the two grid axes, traversed
      corner-outer and temperature-inner. That is the order every committed
      record was written in, so it is the order kept here.
    * `run_point(pdk, corner, temp_c) -> (corner_id, log, extracted)` -- runs
      one grid point and parses it. A runner that drives *several* decks per
      point concatenates their logs inside its own `run_point`
      (`run_uvlo_trip.py` does) rather than teaching the driver about it; the
      `log` it returns is the bytes that land in the corner log.
    * `corner_key(corner)` -- the corner's name, used both as the `results`
      key and as the log banner's `corner` field. The default suits a runner
      whose axis is already a `.LIB` section name; a runner iterating
      :class:`corners.Corner` objects passes `lambda c: c.name`.
    * `progress_detail(corner_id, extracted)` -- the text after `<cid>: ` on
      a progress line; the default is the bare `ok` two of the three print.
    * `build_record_body(record, stamp, pdk, ngspice, results)` -- the
      runner's own record markdown, plus whatever summary object it wants
      handed back to `summarize`.
    * `summarize(summary)` -- the closing lines printed after the manifest.

    A dirty input tree is disclosed for **every** recorded run via
    :func:`start_run` (issue #483). Before #450 only
    `run_low_side_power_switch.py` said so, even though all of them read
    `git_provenance()`; #450 gave this driver its own copy, and the shared
    envelope is where that decision now lives for the mismatch campaigns
    too. Whether the record *body* should also carry
    :func:`report.render_record`'s in-record disclosure is a separate call,
    deliberately left to a follow-up.
    """
    run = start_run(here=here, repo_root=repo_root, parse_cli=False)
    pdk = run.pdk
    ngspice = run.ngspice
    stage = evidence_store.stage_dir(repo_root, here.name, run.record)

    print(f"record {run.record}: {len(process_corners) * len(temperatures_c)} corner points")
    results: dict[tuple[str, float], dict] = {}
    for corner in process_corners:
        for temp in temperatures_c:
            cid, log, extracted = run_point(pdk, corner, temp)
            name = corner_key(corner)
            report.write_corner_log(
                stage / report.CORNERS_DIR,
                run.record,
                cid,
                report.device_log_header(pdk, deck, name, temp, run.record, run.stamp, ngspice),
                log,
            )
            results[(name, temp)] = extracted
            print(f"  {cid}: {progress_detail(cid, extracted)}")

    report.write_device_netlist_snapshot(stage / report.SNAPSHOT_DIR, run.record, deck)
    body, summary = build_record_body(run.record, run.stamp, pdk, ngspice, results)
    path, manifest = commit_run(
        stage=stage, repo_root=repo_root, here=here, record=run.record, body=body,
    )
    print(f"wrote {path} (evidence manifest {manifest})")
    for line in summarize(summary):
        print(line)
    return 0

# --------------------------------------------------------------------------
# Record formatting
# --------------------------------------------------------------------------


def sigfig(value, digits: int = 6) -> str:
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


def convention_head(
    n_samples: int,
    n_points: int,
    drawn: int,
    dropped_note: str,
    dash: str,
) -> str:
    """The opening of every mismatch record's `Statistical convention` bullet:
    the Monte Carlo framing and the gf180mcu `.lib fets_mm` per-instance
    mismatch model it draws from, through the 1 σ (not a 3 σ corner pull)
    clause. That model description is a PDK fact, not an experiment fact, so
    it is shared; the per-experiment prose that follows -- which device
    families carry β mismatch, which node's σ is reported -- stays with the
    runner, as does the `convention_tail` that closes the bullet."""
    return (
        f"- **Statistical convention**: Monte Carlo **local device mismatch** "
        f"(intra-die), N = {n_samples} independent draws per PVT point, "
        f"{n_points} PVT point(s), {drawn} mismatch samples "
        f"total.{dropped_note} Distribution source: the gf180mcu PDK's own "
        f"`.lib fets_mm` per-instance mismatch model "
        f"(`delvto = mis_vth·sw_stat_mismatch`, "
        f"`mulu0 = 1 − mis_k·sw_stat_mismatch`, with `mis_vth`/`mis_k` drawn "
        f"from `agauss(0, σ, 1)` and σ scaled Pelgrom-style by "
        f"1/√(W_eff·L_eff)) {dash} i.e. **1 σ per-device draws, not a "
        f"3 σ corner pull**;"
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


def control_table_rows(
    outcomes,
    probe,
    *,
    value_fmt=None,
    delta_fmt: str = "+.2f",
) -> tuple[list[str], bool, float | None, int]:
    """Rows of the deterministic-negative-control table.

    `probe(outcome)` returns `(node, value, delta)`: the node name (or `None`
    for a single-node claim, which drops that column), the control value and
    its delta against the reference record. `value_fmt(value)` renders the
    control cell (default `sigfig(value, 10)`) and `delta_fmt` is the format spec
    applied to the delta once scaled to micro-units -- a campaign whose unit
    needs different precision passes its own rather than keeping a private
    copy of this loop.

    Returns `(rows, control_ok, worst_ref_delta, compared)`.
    `worst_ref_delta` is `None` -- never `0.0` -- when **no** point had a
    reference to compare against, so a caller can never print a residual for a
    cross-check that did not run (#442); `compared` is how many of `outcomes`
    actually had one, so a partial cross-check can be disclosed too.
    """
    if value_fmt is None:
        def value_fmt(value):
            return sigfig(value, 10)

    rows = []
    control_ok = True
    worst_ref_delta: float | None = None
    compared = 0
    for outcome in outcomes:
        node, value, delta = probe(outcome)
        agree = outcome.controls_agree
        matches_baseline = outcome.control_matches_baseline
        control_ok = control_ok and agree and matches_baseline
        if delta is not None:
            compared += 1
            worst_ref_delta = (
                abs(delta) if worst_ref_delta is None
                else max(worst_ref_delta, abs(delta))
            )
        node_cell = "" if node is None else f"`{node}` | "
        rows.append(
            f"  | `{outcome.corner_id}` | {node_cell}{value_fmt(value)} "
            f"| {'yes' if matches_baseline else '**NO**'} "
            f"| {'yes' if agree else '**NO**'} "
            f"| {'n/a' if delta is None else format(delta * 1e6, delta_fmt)} |"
        )
    return rows, control_ok, worst_ref_delta, compared


def reference_coverage_note(
    reference_record: str, compared: int, total: int, dash: str
) -> str:
    """Disclosure for a reference cross-check that did not cover every point.

    `""` when all `total` points were compared (the record's own prose already
    states the residual). Otherwise a sentence -- leading space included, so it
    appends to that prose -- saying how much of the cross-check did not run, so
    no record implies a comparison it never made (#442).
    """
    missing = total - compared
    if total <= 0 or missing <= 0:
        return ""
    these = "point" if missing == 1 else "points"
    if compared == 0:
        all_points = "point" if total == 1 else "points"
        return (
            f" The cross-check against the committed corner-matrix record "
            f"`{reference_record}` was **not performed**: no reference log was "
            f"found for any of the {total} PVT {all_points}, so no residual "
            f"was measured {dash} the `n/a` entries above are skipped "
            f"comparisons, not zero residuals."
        )
    return (
        f" That residual covers {compared} of {total} PVT points only: "
        f"{missing} {these} had no reference log in `{reference_record}` and "
        f"{'was' if missing == 1 else 'were'} not cross-checked."
    )


def reference_anomaly(reference_record: str, compared: int, total: int) -> str | None:
    """The anomaly a skipped reference cross-check raises, or `None`.

    A campaign that could not compare every point against its committed
    reference has not run the check it advertises, so the record must not read
    PASS on it (#442).
    """
    missing = total - compared
    if total <= 0 or missing <= 0:
        return None
    these = "point" if missing == 1 else "points"
    return (
        f"reference cross-check against `{reference_record}` did not run at "
        f"{missing} of {total} PVT {these} (no committed reference log found)"
    )


def non_converged_section(
    outcomes, drawn: int, dash: str, explanation: str, closing: str
) -> list[str]:
    """The `Non-converged draws` section, disclosing every excluded draw.

    `explanation` follows "excluded from every statistic in this record" and
    may use `{it_is}` for "It is"/"They are"; `closing` is the paragraph
    after the table. Both are claim-specific wording. An empty `closing`
    emits no closing paragraph and no extra blank line.
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
        lines += ["", closing] if closing else [""]
    lines.append("")
    return lines


def verdict_for(within: bool, control_ok: bool, reference_ok: bool = True) -> str:
    """PASS iff the bound holds, the negative control held everywhere, and the
    committed-reference cross-check actually ran at every point.

    `reference_ok` defaults to `True` for a campaign that makes no such
    cross-check; one that does passes the result of
    `reference_anomaly(...) is None` so a skipped comparison cannot be read as
    a clean one (#442).
    """
    return "PASS" if (within and control_ok and reference_ok) else "FAIL"


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
    "RunContext",
    "baseline_log_header",
    "control_table_rows",
    "convention_head",
    "convention_tail",
    "dropped_note",
    "error_verdict_line",
    "sigfig",
    "links_lines",
    "log_header",
    "mv",
    "non_converged_section",
    "point_sigma_summary",
    "pvt_axes_lines",
    "reference_anomaly",
    "reference_coverage_note",
    "commit_run",
    "finish_run",
    "run_device_main",
    "run_device_point_campaign",
    "run_mismatch_main",
    "run_point_campaign",
    "start_run",
    "trailer_lines",
    "verdict_for",
    "write_log",
    "write_outcome_logs",
    "write_sample_csv",
]
