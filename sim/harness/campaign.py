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

import csv
import statistics
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import montecarlo as mc_mod
from . import report
from . import runner as harness_runner
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


__all__ = [
    "CONTROL_SEED_OFFSET",
    "PointOutcome",
    "baseline_log_header",
    "fmt",
    "log_header",
    "mv",
    "point_sigma_summary",
    "run_device_point_campaign",
    "run_point_campaign",
    "write_log",
    "write_sample_csv",
]
