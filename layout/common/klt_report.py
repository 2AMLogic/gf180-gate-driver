"""Shared ``klt`` invocation + append-only report writing for ``layout/``.

The DRC/ERC/LVS/PEX runners and negative controls all repeat the same
skeleton: run ``klt <tool> ...`` (as ``--format json``, and for the
human-readable record also ``--format text``), check klt's exit-code contract
(some non-zero codes are successful runs, e.g. "violations found"), and write
the output under ``<reports_dir>/<record-id>.<suffix>.{json,txt}``. Keeping it
here means a runner cannot drift from its siblings (e.g. ignore the resolved
``klt`` binary).

Usage from an entry point::

    REPO_ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

    import klt_report  # noqa: E402

    payload = klt_report.run_klt_report(
        REPO_ROOT, [klt, "drc", str(gds_rel), "--deck", deck],
        ok_codes=(0, 3), reports_dir=reports_dir, record_id=record_id,
        suffix="drc",
    )
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from collections.abc import Sequence


class KltRunError(Exception):
    """``klt`` exited with a code outside the tool's success contract.

    The failure block has already been printed to stderr.
    """


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
    cwd: Path,
    argv: Sequence[str],
    *,
    ok_codes: Sequence[int],
    reports_dir: Path,
    record_id: str,
    suffix: str,
) -> dict:
    """Run ``argv`` as json then text; write both reports; return the JSON payload.

    ``argv`` is the full command without ``--format`` (``[klt, "drc", ...]``).
    Both formats are run before the exit code is checked, and nothing is
    written when the json run fails.
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

    (reports_dir / f"{record_id}.{suffix}.json").write_text(json_proc.stdout)
    (reports_dir / f"{record_id}.{suffix}.txt").write_text(text_proc.stdout)
    return json.loads(json_proc.stdout)
