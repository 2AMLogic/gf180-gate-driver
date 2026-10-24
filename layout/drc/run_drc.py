#!/usr/bin/env python3
"""Reproducible, append-only ``klt drc`` invocation for ``layout/``.

Runs ``klt drc <gds> --deck gf180mcu`` (both ``--format json`` and
``--format text``) and writes the output under
``layout/drc/reports/<fixture>/<record-id>.drc.json``; the text twin goes to the
artifact store (``layout/common/signoff_store.py``, issue #348) and only its
manifest is committed. Fails closed if it cannot be stored.

``<record-id>`` is ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``, matching the
convention ``sim/README.md`` documents for ``sim/`` evidence. This script
never overwrites an existing report -- CLAUDE.md: "``sim/`` results are
append-only evidence", and this repo applies the same rule to ``layout/``
DRC reports (see ``layout/README.md``). On a same-second collision it
advances the timestamp by one second rather than clobbering.

Ported from ``2AMLogic/gf180-bandgap``'s ``layout/drc/run_drc.py`` (CLAUDE.md:
"Harness bootstrap: copy the sim-harness pattern from 2AMLogic/gf180-bandgap
rather than reinventing it").

Requires ``klt`` on ``PATH`` -- see ``layout/README.md`` for the pinned
install.

Usage (from the repo root):

    python3 layout/drc/run_drc.py layout/gate_driver_core.gds

    # explicit fixture name / deck, if ever needed:
    python3 layout/drc/run_drc.py <path/to.gds> --fixture <name> --deck gf180mcu
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

import klt_env  # noqa: E402
import signoff_store  # noqa: E402

REPORTS_ROOT = Path(__file__).resolve().parent / "reports"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gds", type=Path, help="path to the GDS/OASIS file to check")
    parser.add_argument(
        "--fixture",
        help="report subdirectory name (default: the GDS file's stem)",
    )
    parser.add_argument("--deck", default="gf180mcu", help="DRC deck (default: gf180mcu)")
    parser.add_argument(
        "--store-envelope",
        action="store_true",
        help="store the json envelope too instead of committing it (negative controls)",
    )
    args = parser.parse_args()

    klt = klt_env.require_klt()
    signoff_store.preflight_or_exit(REPO_ROOT)

    gds_path = klt_env.resolve_existing(args.gds)

    fixture = args.fixture or gds_path.stem
    reports_dir = REPORTS_ROOT / fixture
    bench = f"layout-drc-{fixture}"
    record_id = signoff_store.new_record_id(REPO_ROOT, bench, reports_dir)

    # Relative path from the repo root, so the committed report's "file"
    # field is reproducible regardless of invocation cwd.
    gds_rel = gds_path.relative_to(REPO_ROOT)

    json_proc = subprocess.run(
        [klt, "drc", str(gds_rel), "--deck", args.deck, "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    text_proc = subprocess.run(
        [klt, "drc", str(gds_rel), "--deck", args.deck, "--format", "text"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # exit 0 (clean) and exit 3 (violations found) are both successful runs
    # per klt drc's documented exit-code contract; only exit 1/2 are errors.
    if json_proc.returncode not in (0, 3):
        print(json_proc.stdout, file=sys.stdout)
        print(json_proc.stderr, file=sys.stderr)
        print(f"error: klt drc failed (exit {json_proc.returncode})", file=sys.stderr)
        return 1

    # The text twin is stored. The json envelope is what the tier report cites
    # from the tree, so it is committed -- but only after the store succeeded.
    stage = signoff_store.stage_dir(REPO_ROOT, bench, record_id)
    (stage / f"{record_id}.drc.txt").write_text(text_proc.stdout)
    json_path = (stage if args.store_envelope else reports_dir) / f"{record_id}.drc.json"
    if args.store_envelope:
        json_path.write_text(json_proc.stdout)
    manifest = signoff_store.store_or_exit(
        stage, repo_root=REPO_ROOT, bench=bench, rid=record_id,
        name_prefix=str(reports_dir.relative_to(REPO_ROOT)),
    )
    if not args.store_envelope:
        reports_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json_proc.stdout)

    payload = json.loads(json_proc.stdout)
    print(f"record id      : {record_id}")
    print(f"fixture        : {fixture}")
    print(f"status         : {payload['status']}")
    print(f"violation_count: {payload['violation_count']}")
    print(f"report (json)  : {json_path.relative_to(REPO_ROOT)}")
    print(f"manifest       : {manifest.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
