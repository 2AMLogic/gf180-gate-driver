"""Deck composition and ngspice execution for one PVT point.

Ported from `2AMLogic/gf180-bandgap` (sim/harness/runner.py); ``compose_deck``
is adapted to emit one ``<rail>_val``/``<rail>_nom`` parameter pair per rail
declared on the testbench (this repo's two rails by default -- ``vlogic``,
``vdrv``) instead of the source harness's single ``vdd_val``/``vdd_nom``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .corners import PvtPoint
from .montecarlo import MismatchSample
from .pdk import Pdk
from .testbench import Testbench

NGSPICE = "ngspice"
DEFAULT_TIMEOUT_S = 300

# `print` output for a length-1 vector: "m_vout = 6.9043645202e-01"
_MEAS_RE = re.compile(r"^\s*m_(\w+)\s*=\s*([-+]?[0-9.]+(?:[eE][-+]?[0-9]+)?)\s*$")
_ERROR_RE = re.compile(r"^\s*(?:Error|ERROR|Fatal|fatal error|doAnalyses:)", re.MULTILINE)

#: Default ngspice ``reltol`` for every generated deck (issue #156).
#:
#: ngspice's own factory default (``reltol=1e-3``) leaves local-truncation-
#: error control free to take timesteps wide enough to straddle -- and skip
#: over the peak of -- a sub-nanosecond capacitive-coupling spike. Every
#: recorded spec Sec.2.3 gate-ceiling number so far is the peak of exactly
#: that kind of spike (decision records 0003-0006), so the harness-default
#: deck was measuring a LOWER bound on the true excursion, not an upper one
#: -- the opposite of what a conservative reliability bound needs.
#:
#: ``1e-4`` recovers nearly all of the ~25% outward peak movement a tighter
#: setting would on this repo's worst-case recorded point
#: (`sim/gate-driver-core-drive`'s `ss_125c_vlogic3p30v-vdrv6p00v`, node
#: IN_DRV: 6.14569 V @ reltol=1e-4 vs. a 6.11823 V harness-default baseline
#: and 6.14801 V @ reltol=1e-5), needs no per-testbench ``tran`` edit, and --
#: unlike ``reltol=1e-5`` -- never hits ngspice's "timestep too small" abort
#: anywhere across the mandated 60-point PVT grid. ``1e-5`` looked safe on
#: that single worst-case point but was rejected after a full-grid run
#: aborted on 7 of 60 points ("Timestep too small ... trouble with node
#: vimeas#branch/vgnd_logic#branch") -- a different failure mode than the
#: sub-5 ps ``maxstep`` abort the issue's own single-point table found, and
#: one that single-point testing alone would not have caught. See
#: ``sim/README.md``'s "Transient tolerance convention" section for the full
#: comparison table and rationale.
DEFAULT_TRAN_RELTOL = "1e-4"

#: Matches an existing ``reltol=...`` (any case, any whitespace around ``=``)
#: inside a manifest ``options`` entry, so a testbench that already opts into
#: its own value is not double-set by :data:`DEFAULT_TRAN_RELTOL` below it --
#: ngspice takes the *last* ``.options reltol=`` line in a deck, so a naive
#: unconditional append would silently overrule a deliberate manifest choice.
_RELTOL_OPTION_RE = re.compile(r"(?i)\breltol\s*=")


#: How a record's ``reltol`` came to be: the harness-wide default, or a value
#: the testbench's own manifest opted into. Recorded explicitly on every
#: record's Environment block rather than re-derived by comparing the value
#: against :data:`DEFAULT_TRAN_RELTOL` -- a manifest that deliberately pins
#: the same string as the current default is still an *override*, and would
#: be mislabelled by a value comparison (and would silently change meaning
#: the day the default moves).
RELTOL_SOURCE_DEFAULT = "harness default"
RELTOL_SOURCE_MANIFEST = "manifest override"


def reltol_is_manifest_override(tb: Testbench) -> bool:
    """Whether ``tb``'s manifest opts into its own ``reltol``.

    Single source of truth for the three places that must agree: whether
    :func:`compose_deck` appends the harness default, what
    :func:`effective_reltol` reports, and which source string
    ``report.py`` writes onto the record.
    """
    return any(_RELTOL_OPTION_RE.search(option) for option in tb.options)


def effective_reltol(tb: Testbench) -> tuple[str, str]:
    """The ``reltol`` this testbench's decks run at, and where it came from.

    A manifest may opt into its own value via ``"options": ["reltol=..."]``
    (``sim/harness/README.md`` documents the syntax); otherwise every deck
    gets the harness-wide :data:`DEFAULT_TRAN_RELTOL`. Returns
    ``(value, source)`` where ``source`` is :data:`RELTOL_SOURCE_DEFAULT` or
    :data:`RELTOL_SOURCE_MANIFEST`; ``report.py`` records both on the
    record's Environment block, per issue #156's "record the tolerance
    settings" ask.
    """
    for option in tb.options:
        if _RELTOL_OPTION_RE.search(option):
            return option.split("=", 1)[1].strip(), RELTOL_SOURCE_MANIFEST
    return DEFAULT_TRAN_RELTOL, RELTOL_SOURCE_DEFAULT


class NgspiceMissing(RuntimeError):
    pass


def ngspice_version() -> str:
    exe = shutil.which(NGSPICE)
    if not exe:
        raise NgspiceMissing(
            "ngspice not found on PATH.\n"
            "  macOS:  brew install ngspice\n"
            "  Debian: apt-get install ngspice"
        )
    out = subprocess.run(
        [exe, "--version"], capture_output=True, text=True, check=False
    ).stdout
    for line in out.splitlines():
        if "ngspice-" in line:
            return line.strip().lstrip("* ").strip()
    return out.strip().splitlines()[0] if out.strip() else "unknown"


def compose_deck(
    tb: Testbench, pdk: Pdk, point: PvtPoint, mc: MismatchSample | None = None
) -> str:
    """Build the complete, self-contained ngspice deck for one PVT point.

    ``mc`` -- when given -- adds this repo's Monte Carlo / local-mismatch
    block (``sim/harness/montecarlo.py``): the gf180mcu ``sw_stat_mismatch``
    switch plus a pinned ngspice seed, emitted *after* the corner ``.lib``
    sections so it overrides ``design.ngspice``'s defaults. With ``mc=None``
    (every non-Monte-Carlo run) the deck is byte-identical to what this
    function produced before Monte Carlo support existed.
    """
    lines: list[str] = [
        f"* {tb.name} @ {point.corner_id} -- GENERATED by sim/harness, do not edit",
        f"* corner={point.corner.name} ({point.corner.description})",
        f"* temp={point.temp_c} C  pdk={pdk.variant}@{pdk.version}",
        "",
        "* ---- PVT parameters -------------------------------------------------",
    ]
    for rail in tb.rails:
        val = point.supplies.get(rail.name, rail.nominal_v)
        lines.append(f".param {rail.name}_val={val!r}")
        lines.append(f".param {rail.name}_nom={rail.nominal_v!r}")
    lines.append(f".param temp_c={point.temp_c!r}")
    for key, value in tb.params.items():
        lines.append(f".param {key}={value}")

    lines += [
        "",
        "* ---- gf180mcu models ------------------------------------------------",
        f'.include "{pdk.design_include}"',
    ]
    for section in point.corner.sections:
        lines.append(f'.lib "{pdk.model_lib}" {section}')

    if mc is not None:
        # After the .lib block on purpose: design.ngspice (included above)
        # sets both statistical switches to 0, and ngspice takes the last
        # .param definition of a name.
        lines += mc.deck_lines()

    lines += [
        "",
        f".temp {point.temp_c!r}",
    ]
    for option in tb.options:
        lines.append(f".options {option}")
    if not reltol_is_manifest_override(tb):
        # Harness-wide transient-tolerance default -- see DEFAULT_TRAN_RELTOL
        # above and sim/README.md's "Transient tolerance convention".
        lines.append(f".options reltol={DEFAULT_TRAN_RELTOL}")

    if tb.dut is not None:
        lines += [
            "",
            "* ---- device under test ----------------------------------------------",
            f"* provenance: {tb.dut_provenance_class}  sha256 {tb.dut_sha256}",
            f'.include "{tb.dut}"',
        ]

    lines += [
        "",
        "* ---- testbench ------------------------------------------------------",
        f'.include "{tb.netlist}"',
        "",
        "* ---- measurement ----------------------------------------------------",
        ".control",
        "set numdgt=10",
        "set noaskquit",
        "set num_threads=1",
    ]
    lines += [f"  {analysis}" for analysis in tb.analyses]
    for name, expr in tb.measure.items():
        lines.append(f"  let m_{name} = {expr}")
    for name in tb.measure:
        lines.append(f"  print m_{name}")
    lines += [".endc", ".end", ""]
    return "\n".join(lines)


@dataclass
class PointResult:
    point: PvtPoint
    status: str                                   # "ok" | "failed" | "error"
    measurements: dict[str, float] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    seconds: float = 0.0
    message: str = ""
    #: Raw ngspice output, populated only when ``run_point(keep_output=True)``
    #: asked for it. Never serialized into a record -- ``as_dict`` omits it --
    #: because the raw text belongs in ``corners/<record-id>/<corner-id>.log``,
    #: not inline in the record.
    output: str = field(default="", compare=False, repr=False)

    def as_dict(self) -> dict:
        record = self.point.as_dict()
        record.update(
            {
                "status": self.status,
                "measurements": self.measurements,
                "seconds": round(self.seconds, 3),
            }
        )
        if self.missing:
            record["missing_measurements"] = self.missing
        if self.message:
            record["message"] = self.message
        return record


def parse_measurements(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for line in text.splitlines():
        match = _MEAS_RE.match(line)
        if match:
            try:
                found[match.group(1)] = float(match.group(2))
            except ValueError:  # pragma: no cover - regex already constrains this
                continue
    return found


def run_point(
    tb: Testbench,
    pdk: Pdk,
    point: PvtPoint,
    workdir: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    log_dir: Path | None = None,
    mc: MismatchSample | None = None,
    keep_output: bool = False,
) -> PointResult:
    """Simulate one PVT point. Never raises for simulation failure.

    ``workdir`` holds the generated deck (scratch, disposable). ``log_dir``
    -- when given -- is where the raw ngspice output lands as
    ``<corner-id>.log``; that is the ``sim/<slug>/corners/<record-id>/``
    directory from ``sim/README.md``. It defaults to ``workdir`` so a
    throwaway run does not touch the evidence tree.

    ``mc`` selects a Monte Carlo / local-mismatch draw (see
    :func:`compose_deck`); pass the matching ``point`` from
    ``montecarlo.mc_point`` so the deck, the log filename and the recorded
    corner-id all agree. ``keep_output`` additionally carries the raw ngspice
    text back on the result, which a Monte Carlo campaign needs so it can
    write only the *interesting* samples' logs into the evidence tree instead
    of one file per draw.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    log_dir = workdir if log_dir is None else log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    deck_path = workdir / f"{point.corner_id}.spice"
    log_path = log_dir / f"{point.corner_id}.log"
    deck_path.write_text(compose_deck(tb, pdk, point, mc=mc))

    started = time.monotonic()
    try:
        proc = subprocess.run(
            [NGSPICE, "-b", str(deck_path)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=workdir,
            check=False,
        )
        output = proc.stdout + "\n" + proc.stderr
        returncode = proc.returncode
    except FileNotFoundError as exc:
        raise NgspiceMissing(str(exc)) from exc
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        log_path.write_text(f"TIMEOUT after {timeout_s}s\n")
        return PointResult(
            point=point,
            status="error",
            seconds=elapsed,
            message=f"ngspice timed out after {timeout_s}s",
        )
    elapsed = time.monotonic() - started
    log_path.write_text(output)

    measurements = parse_measurements(output)
    missing = [name for name in tb.measure if name not in measurements]

    if missing:
        errors = "; ".join(_ERROR_RE.findall(output)[:3])
        first_error = next(
            (line.strip() for line in output.splitlines() if _ERROR_RE.match(line)), ""
        )
        return PointResult(
            point=point,
            status="failed",
            measurements=measurements,
            missing=missing,
            seconds=elapsed,
            message=first_error or errors or f"ngspice exit {returncode}, no measurements parsed",
            output=output if keep_output else "",
        )

    return PointResult(
        point=point,
        status="ok",
        measurements=measurements,
        seconds=elapsed,
        output=output if keep_output else "",
    )


def run_grid(
    tb: Testbench,
    pdk: Pdk,
    points: list[PvtPoint],
    workdir: Path,
    jobs: int = 1,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    on_result=None,
    log_dir: Path | None = None,
) -> list[PointResult]:
    """Run every PVT point; results come back in grid order regardless of jobs."""
    results: list[PointResult | None] = [None] * len(points)

    def _one(index_point):
        index, point = index_point
        result = run_point(tb, pdk, point, workdir, timeout_s=timeout_s, log_dir=log_dir)
        results[index] = result
        if on_result is not None:
            on_result(result)
        return result

    if jobs <= 1:
        for item in enumerate(points):
            _one(item)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(_one, enumerate(points)))

    return [r for r in results if r is not None]


def run_samples(
    tb: Testbench,
    pdk: Pdk,
    samples: list[tuple[PvtPoint, MismatchSample]],
    workdir: Path,
    jobs: int = 1,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    on_result=None,
) -> list[PointResult]:
    """Run a list of ``(point, mismatch-sample)`` pairs; results in input order.

    The Monte Carlo counterpart of :func:`run_grid`. Two deliberate
    differences, both because a campaign is hundreds to thousands of runs
    rather than tens:

    * every run's raw ngspice text comes back on the result
      (``keep_output=True``) instead of being written straight into the
      evidence tree, so the caller can commit only the samples a record
      actually cites (the control and the worst case) rather than one
      committed log file per draw;
    * logs therefore go to the scratch ``workdir``, never to
      ``corners/<record-id>/``.

    Pass ``point`` already re-labelled by ``montecarlo.mc_point`` so its
    ``corner_id`` (and hence the scratch deck/log filenames) is unique per
    sample.
    """
    results: list[PointResult | None] = [None] * len(samples)

    def _one(item):
        index, (point, mc) = item
        result = run_point(
            tb,
            pdk,
            point,
            workdir,
            timeout_s=timeout_s,
            log_dir=None,
            mc=mc,
            keep_output=True,
        )
        results[index] = result
        if on_result is not None:
            on_result(result)
        return result

    if jobs <= 1:
        for item in enumerate(samples):
            _one(item)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(_one, enumerate(samples)))

    return [r for r in results if r is not None]
