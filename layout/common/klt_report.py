"""Shared ``klt`` invocation for ``layout/`` signoff runners.

The DRC/ERC/LVS/PEX runners and negative controls all repeat the same
skeleton: run ``klt <tool> ...`` (as ``--format json``, and for the
human-readable record also ``--format text``) and check klt's exit-code
contract (some non-zero codes are successful runs, e.g. "violations found").
Keeping it here means a runner cannot drift from its siblings (e.g. ignore the
resolved ``klt`` binary).

Every run -- single-format or both legs of a report -- is checked by the one
:func:`_raise_if_bad` below, so there is a single definition of "klt failed"
in the repo (issue #472).

This module deliberately **writes nothing**. Where the bytes go -- the artifact
store or the committed ``reports/`` tree -- is each caller's decision
(``signoff_store``, issue #348, ``layout/README.md`` "Stored vs committed
signoff outputs"), so the helper returns the json and text payloads and the
caller stages / stores / commits them.

Usage from an entry point::

    REPO_ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

    import klt_report  # noqa: E402

    report = klt_report.run_klt_report(
        REPO_ROOT, [klt, "drc", str(gds_rel), "--deck", deck], ok_codes=(0, 3),
    )
    (stage / f"{record_id}.drc.txt").write_text(report.text)
    payload = report.payload
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple


class KltRunError(Exception):
    """``klt`` exited with a code outside the tool's success contract.

    The failure block has already been printed to stderr. The exception's
    argument is the klt subcommand (``argv[1]``), not the failing leg -- the
    stderr block names the leg.
    """


class KltReport(NamedTuple):
    """One klt run in both formats: raw json, raw text, and the parsed json."""

    json: str
    text: str
    payload: dict


def _raise_if_bad(
    argv: Sequence[str],
    proc: subprocess.CompletedProcess[str],
    ok_codes: Sequence[int],
    *,
    leg: str = "",
) -> None:
    """Print klt's failure block and raise on an exit outside ``ok_codes``.

    The single definition of "klt failed" for this module: both entry points
    call it, so neither the message nor the raise can drift (issue #472).
    ``leg`` names which format failed for a multi-format run
    (``"--format text"``); it is empty for a single-format :func:`run_klt`,
    which has only one leg to name.
    """
    if proc.returncode in ok_codes:
        return
    label = str(argv[1])
    print(proc.stdout, file=sys.stdout)
    print(proc.stderr, file=sys.stderr)
    failed = f"klt {label} {leg}".rstrip()
    print(f"error: {failed} failed (exit {proc.returncode})", file=sys.stderr)
    raise KltRunError(label)


def run_klt(
    cwd: Path, argv: Sequence[str], *, ok_codes: Sequence[int] = (0,)
) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` from ``cwd``; print a failure block and raise on a bad exit."""
    proc = subprocess.run(
        list(argv), cwd=cwd, capture_output=True, text=True, check=False
    )
    _raise_if_bad(argv, proc, ok_codes)
    return proc


def run_klt_report(
    cwd: Path, argv: Sequence[str], *, ok_codes: Sequence[int] = (0,)
) -> KltReport:
    """Run ``argv`` as json then text; return both outputs and the parsed payload.

    ``argv`` is the full command without ``--format`` (``[klt, "drc", ...]``).
    Both formats are run before either exit code is checked, and **both** are
    then checked against ``ok_codes`` -- json first, so a json failure reports
    the same block it always has. A leg outside ``ok_codes`` prints that leg's
    failure block and raises :class:`KltRunError`.

    The text leg is checked because its stdout is what callers write into
    append-only signoff evidence: a failed render must not reach a record that
    ``signoff_store``'s fail-closed contract would otherwise protect
    (issue #472).
    """
    json_proc = subprocess.run(
        [*argv, "--format", "json"], cwd=cwd, capture_output=True, text=True, check=False
    )
    text_proc = subprocess.run(
        [*argv, "--format", "text"], cwd=cwd, capture_output=True, text=True, check=False
    )
    _raise_if_bad(argv, json_proc, ok_codes, leg="--format json")
    _raise_if_bad(argv, text_proc, ok_codes, leg="--format text")
    return KltReport(
        json=json_proc.stdout,
        text=text_proc.stdout,
        payload=json.loads(json_proc.stdout),
    )
