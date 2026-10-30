"""Helpers shared by the standalone ``sim/*/run_*.py`` experiment scripts.

These scripts drive ngspice directly rather than through ``runner``, and each
used to carry its own byte-identical copy of these functions. ``fmt`` keeps
4 digits (``campaign.fmt`` defaults to 6) so recorded evidence formatting does
not change.
"""

from __future__ import annotations

import math
import re
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

from . import campaign
from . import corners as harness_corners
from . import report as harness_report

SIM_DIR = Path(__file__).resolve().parent.parent


def fmt(value, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def parse_dc_tables(log: str) -> list[tuple[list[str], list[list[float]]]]:
    """Every ``Index <cols...>`` table in a control-block's printed output,
    in the order the ``print`` commands that produced them were issued."""
    lines = log.splitlines()
    tables: list[tuple[list[str], list[list[float]]]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("Index"):
            header = lines[i].split()[1:]
            rows: list[list[float]] = []
            j = i + 2  # skip the header and the '---' rule line
            while j < len(lines):
                parts = lines[j].split()
                if not parts or not parts[0].isdigit():
                    break
                try:
                    values = [float(p) for p in parts[1:]]
                except ValueError:
                    break
                if len(values) == len(header):
                    rows.append(values)
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


def column(header: list[str], rows: list[list[float]], name: str) -> list[float]:
    idx = header.index(name)
    return [row[idx] for row in rows]


def first_crossing(
    xs: list[float],
    ys: list[float],
    thresh: float,
    *,
    rising: bool = True,
    log: bool = False,
) -> float | None:
    """First x where `ys` crosses `thresh`, linearly interpolated between the
    bracketing samples; `None` when it never does. `rising` selects an upward
    (``y0 < thresh <= y1``) or downward (``y0 > thresh >= y1``) crossing.
    `log` interpolates in log(y) (rising only) so an exponential knee is not
    read with a straight-line secant across a decade; a non-positive or flat
    bracket falls back to the segment's left x."""
    for i in range(1, len(ys)):
        y0, y1 = ys[i - 1], ys[i]
        if not (y0 < thresh <= y1 if rising else y0 > thresh >= y1):
            continue
        x0, x1 = xs[i - 1], xs[i]
        if log:
            if y0 <= 0 or y1 <= y0:
                return x0
            frac = (math.log(thresh) - math.log(y0)) / (math.log(y1) - math.log(y0))
            return x0 + (x1 - x0) * frac
        return x0 if y1 == y0 else x0 + (x1 - x0) * (thresh - y0) / (y1 - y0)
    return None


def range_verdict(value: float | None, lo: float | None, hi: float | None) -> str:
    """``PASS``/``FAIL`` for `value` inside the inclusive [lo, hi] (either
    bound may be `None`); ``ERROR (no crossing found)`` when `value` is `None`."""
    if value is None:
        return "ERROR (no crossing found)"
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return "FAIL"
    return "PASS"


def corner_shim(
    pdk,
    sections: Iterable[str],
    temp_c: float,
    *,
    script: str,
    extra_lines: Iterable[str] = (),
) -> str:
    """The per-corner-point ``corner.spice`` deck: PDK include, one ``.lib``
    per model section, ``.temp``, then any caller-supplied ``extra_lines``
    (e.g. ``.options`` or Monte Carlo ``deck_lines()``). ``script`` names the
    caller in the header comment."""
    lines = [
        f"* Generated per corner point by {script} from",
        "* $PDK_ROOT/$PDK (via sim/harness/pdk.py) -- do not edit by hand, "
        "and do not commit.",
        f'.include "{pdk.design_include}"',
    ]
    lines += [f'.lib "{pdk.model_lib}" {section}' for section in sections]
    lines.append(f".temp {temp_c:g}")
    lines.extend(extra_lines)
    return "\n".join(lines) + "\n"


_NGSPICE_ERROR_RE = re.compile(r"^\s*(Error|ERROR|fatal)", re.MULTILINE)


def run_ngspice(work: Path, deck_name: str, label: str) -> str:
    """Run ``ngspice -b deck_name`` in `work` and return stdout+stderr.

    Raises `RuntimeError` on a non-zero exit or an ``Error``/``ERROR``/``fatal``
    line in the log; `label` (e.g. ``"typical @ 27 C"``) names the corner point
    in the message."""
    proc = subprocess.run(
        ["ngspice", "-b", deck_name],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )
    log = proc.stdout + proc.stderr
    if proc.returncode != 0:
        raise RuntimeError(
            f"ngspice exited {proc.returncode} for {deck_name} [{label}]\n{log}"
        )
    if _NGSPICE_ERROR_RE.search(log):
        raise RuntimeError(
            f"ngspice reported an error for {deck_name} [{label}]:\n{log}"
        )
    return log


def run_corner_deck(
    deck: Path,
    pdk,
    sections: Iterable[str],
    temp_c: float,
    *,
    script: str,
    control: str,
    label: str,
    prefix: str,
    extra_lines: Iterable[str] = (),
) -> str:
    """Stage and run `deck` at one corner point; return the ngspice log.

    In a fresh temp dir (named with `prefix`) writes ``corner.spice``
    (`corner_shim`), ``control.spice`` (`control`, the caller's ``.control``
    block) and a wrapper deck that ``.include``s both around `deck`'s text,
    then calls `run_ngspice` (raises `RuntimeError` as it does; `label` names
    the point)."""
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        work = Path(tmp)
        (work / "corner.spice").write_text(
            corner_shim(pdk, sections, temp_c, script=script, extra_lines=extra_lines),
            encoding="utf-8",
        )
        (work / "control.spice").write_text(control, encoding="utf-8")
        (work / deck.name).write_text(
            '.include "corner.spice"\n'
            + deck.read_text(encoding="utf-8")
            + '\n.include "control.spice"\n.end\n',
            encoding="utf-8",
        )
        return run_ngspice(work, deck.name, label)


def build_points(
    process_corners, temperatures_c, supplies: dict
) -> list[harness_corners.PvtPoint]:
    """A mismatch campaign's PVT points, in the order `sample_seed` indexes."""
    corner_list = [harness_corners.CORNERS[name] for name in process_corners]
    return harness_corners.build_grid(
        corner_list, list(temperatures_c), [dict(supplies)]
    )


def claim_sigma_summary(outcomes, measurement: str) -> str:
    """`campaign.point_sigma_summary` over one named claim measurement."""
    return campaign.point_sigma_summary(
        outcomes, lambda outcome: outcome.values(measurement)
    )


def reference_log_path(
    source_experiment: str, reference_record: str, corner_id: str
) -> Path | None:
    """The reference record's raw log for `corner_id`, or `None` when it has
    none (e.g. a `--smoke` run at a corner the reference never visited)."""
    log = (
        SIM_DIR
        / source_experiment
        / harness_report.CORNERS_DIR
        / reference_record
        / f"{corner_id}.log"
    )
    return log if log.is_file() else None


def delta_vs_reference(value: float | None, reference: float | None) -> float | None:
    """Control minus reference; `None` when either is missing."""
    if reference is None or value is None:
        return None
    return value - reference
