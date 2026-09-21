#!/usr/bin/env python3
"""Reproducible, append-only ``klt erc`` invocation for ``layout/``.

Runs ``klt erc <gds> <spec> --deck gf180mcu`` (both ``--format json`` and
``--format text``) and writes the output under
``layout/erc/reports/<fixture>/<record-id>.erc.{json,txt}``.

``<record-id>`` is ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``, matching the
convention ``sim/README.md`` documents for ``sim/`` evidence (shared
implementation: ``layout/common/report_id.py``). This script never overwrites
an existing report -- CLAUDE.md: "``sim/`` results are append-only
evidence", and this repo applies the same rule to ``layout/`` reports (see
``layout/README.md``).

``--deck`` is load-bearing for this spec (issue #238): the curved-deck
device-marker subtraction it enables is what keeps the uvlo bias strings'
drawn ``ppolyf_u`` bodies from reading as wires in the device-blind
connectivity graph. ``--deck`` requires a klayout-tools build that has it
(klayout-tools#2217); the runner accepts ``--klt <path>`` so a report can be
produced from a specific install without touching the PATH pin, and every
committed report's ``provenance.klt_version`` records the exact build that
produced it.

klt erc exit codes are NOT pass/fail (docs/cli/erc.md: "Gate on `status`,
not the exit code"): 0 (clean/clean_partial), 3 (violations), and 4
(antenna `not_checked`) are all successful runs and all record a report;
only exit 1/2 (failed to run / usage) are errors.

Usage (from the repo root):

    python3 layout/erc/run_erc.py layout/gate_driver_core.gds

    # explicit fixture / spec / deck / klt, if ever needed:
    python3 layout/erc/run_erc.py <path/to.gds> --fixture <name> \\
        --spec layout/erc-supply-spec.json --deck gf180mcu --klt /path/to/klt
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

import report_id  # noqa: E402

REPORTS_ROOT = Path(__file__).resolve().parent / "reports"
DEFAULT_SPEC = REPO_ROOT / "layout" / "erc-supply-spec.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gds", type=Path, help="path to the GDS/OASIS file to check")
    parser.add_argument(
        "--fixture",
        help="report subdirectory name (default: the GDS file's stem)",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=DEFAULT_SPEC,
        help="klt erc spec file (default: layout/erc-supply-spec.json)",
    )
    parser.add_argument("--deck", default="gf180mcu", help="curated deck (default: gf180mcu)")
    parser.add_argument(
        "--klt",
        help="path to the klt binary (default: 'klt' on PATH)",
    )
    args = parser.parse_args()

    klt = args.klt or shutil.which("klt")
    if klt is None:
        print(
            "error: 'klt' not found on PATH. Install with:\n"
            "  uv tool install git+https://github.com/2AMLogic/klayout-tools\n"
            "(no PyPI release yet -- see layout/README.md)",
            file=sys.stderr,
        )
        return 1

    gds_path = args.gds
    if not gds_path.is_absolute():
        gds_path = (Path.cwd() / gds_path).resolve()
    if not gds_path.exists():
        print(f"error: {gds_path} does not exist", file=sys.stderr)
        return 1

    spec_path = args.spec
    if not spec_path.is_absolute():
        spec_path = (Path.cwd() / spec_path).resolve()
    if not spec_path.exists():
        print(f"error: {spec_path} does not exist", file=sys.stderr)
        return 1

    fixture = args.fixture or gds_path.stem
    reports_dir = REPORTS_ROOT / fixture
    reports_dir.mkdir(parents=True, exist_ok=True)

    when = _dt.datetime.now(_dt.timezone.utc)
    record_id = report_id.record_id(reports_dir, when, report_id.short_sha(REPO_ROOT))

    # Relative paths from the repo root, so the committed report's "file"
    # and "spec" fields are reproducible regardless of invocation cwd.
    gds_rel = gds_path.relative_to(REPO_ROOT)
    spec_rel = spec_path.relative_to(REPO_ROOT)

    common = [klt, "erc", str(gds_rel), str(spec_rel), "--deck", args.deck]
    json_proc = subprocess.run(
        [*common, "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    text_proc = subprocess.run(
        [*common, "--format", "text"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # exit 0 (clean), 3 (violations found) and 4 (antenna not_checked) are
    # all successful runs per klt erc's documented exit-code contract; only
    # exit 1/2 are errors.
    if json_proc.returncode not in (0, 3, 4):
        print(json_proc.stdout, file=sys.stdout)
        print(json_proc.stderr, file=sys.stderr)
        print(f"error: klt erc failed (exit {json_proc.returncode})", file=sys.stderr)
        return 1

    json_path = reports_dir / f"{record_id}.erc.json"
    text_path = reports_dir / f"{record_id}.erc.txt"
    json_path.write_text(json_proc.stdout)
    text_path.write_text(text_proc.stdout)

    payload = json.loads(json_proc.stdout)
    print(f"record id        : {record_id}")
    print(f"fixture          : {fixture}")
    print(f"klt              : {payload['provenance']['klt_version']}")
    print(f"erc_status       : {payload['erc_status']}")
    print(f"status (antenna) : {payload['status']}")
    print(f"erc_finding_count : {payload['erc_finding_count']}")
    print(f"report (json)    : {json_path.relative_to(REPO_ROOT)}")
    print(f"report (text)    : {text_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
