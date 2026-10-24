"""Shared ``klt`` invocation for ``layout/`` signoff runners.

The DRC/ERC/LVS/PEX runners and negative controls all repeat the same
skeleton: run ``klt <tool> ...`` (as ``--format json``, and for the
human-readable record also ``--format text``) and check klt's exit-code
contract (some non-zero codes are successful runs, e.g. "violations found").
Keeping it here means a runner cannot drift from its siblings (e.g. ignore the
resolved ``klt`` binary).

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

    The failure block has already been printed to stderr.
    """


class KltReport(NamedTuple):
    """One klt run in both formats: raw json, raw text, and the parsed json."""

    json: str
    text: str
    payload: dict


def run_klt(
    cwd: Path, argv: Sequence[str], ok_codes: Sequence[int] = (0,)
) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` from ``cwd``; print a failure block and raise on a bad exit."""
    proc = subprocess.run(
        list(argv), cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode not in ok_codes:
        label = str(argv[1])
        print(proc.stdout, file=sys.stdout)
        print(proc.stderr, file=sys.stderr)
        print(f"error: klt {label} failed (exit {proc.returncode})", file=sys.stderr)
        raise KltRunError(label)
    return proc


def run_klt_report(
    cwd: Path, argv: Sequence[str], *, ok_codes: Sequence[int]
) -> KltReport:
    """Run ``argv`` as json then text; return both outputs and the parsed payload.

    ``argv`` is the full command without ``--format`` (``[klt, "drc", ...]``).
    Both formats are run before the exit code is checked; a json run outside
    ``ok_codes`` prints the failure block and raises :class:`KltRunError`.
    """
    json_proc = subprocess.run(
        [*argv, "--format", "json"], cwd=cwd, capture_output=True, text=True, check=False
    )
    text_proc = subprocess.run(
        [*argv, "--format", "text"], cwd=cwd, capture_output=True, text=True, check=False
    )
    if json_proc.returncode not in ok_codes:
        print(json_proc.stdout, file=sys.stdout)
        print(json_proc.stderr, file=sys.stderr)
        print(
            f"error: klt {argv[1]} failed (exit {json_proc.returncode})", file=sys.stderr
        )
        raise KltRunError(argv[1])
    return KltReport(
        json=json_proc.stdout,
        text=text_proc.stdout,
        payload=json.loads(json_proc.stdout),
    )
