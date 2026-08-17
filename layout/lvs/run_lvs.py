#!/usr/bin/env python3
"""Reproducible, append-only ``klt extract`` + ``klt lvs`` run for ``layout/``.

The LVS half of the flow ``layout/drc/run_drc.py`` starts. Given a GDS it:

1. regenerates the reference netlist (``layout/lvs/make_reference.py``) so a
   stale, hand-edited reference can never quietly pass;
2. runs ``klt extract --deck gf180mcu`` and keeps the extracted netlist;
3. runs ``klt lvs`` against the reference (engine: ``klayout``, the only
   comparator this deck ships that needs no external binary);
4. writes all artefacts under ``layout/lvs/reports/<block>/<record-id>.*``.

``<record-id>`` is ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``, the same
convention ``sim/README.md`` documents for ``sim/`` evidence and
``layout/drc/run_drc.py`` uses for DRC reports. **Reports are never
overwritten** -- CLAUDE.md: "``sim/`` results are append-only evidence", and
this repo applies the same rule to ``layout/`` reports.

Ported and adapted from ``2AMLogic/gf180-bandgap``'s ``layout/lvs/run_lvs.py``
(CLAUDE.md: "Harness bootstrap: copy the sim-harness pattern from
2AMLogic/gf180-bandgap rather than reinventing it") -- this repo's single
top cell has no analog to that repo's ``--engine netgen`` cross-check need
yet, so the engine selector is dropped rather than carried unused.

Usage (from the repo root)::

    python3 layout/lvs/run_lvs.py layout/gate_driver_core.gds
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

import report_id  # noqa: E402

REPORTS_ROOT = Path(__file__).resolve().parent / "reports"
REFERENCE = Path(__file__).resolve().parent / "gate_driver_core.ref.spice"
MAKE_REFERENCE = Path(__file__).resolve().parent / "make_reference.py"


def _build_request(*, gds_path: Path, reports_dir: Path, reference: Path, deck: str, top: str) -> dict:
    """Build the ``klt lvs`` request document.

    `klt lvs` resolves every relative path inside a request document against
    the **request file's own directory**, not the process cwd -- the request
    lives under ``layout/lvs/reports/<block>/``, so repo-root-relative paths
    would resolve to nonexistent files. Emit paths relative to the request
    directory instead -- machine-independent (unlike absolute paths), so the
    committed request document stays reproducible on any checkout.
    """
    return {
        "layout": {
            "file": os.path.relpath(gds_path, reports_dir),
            "deck": deck,
            "top": top,
        },
        "reference": {
            "netlist": os.path.relpath(reference.resolve(), reports_dir),
            "top": top,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gds", type=Path, help="path to the GDS/OASIS file")
    parser.add_argument("--block", help="report subdirectory (default: the GDS stem)")
    parser.add_argument("--deck", default="gf180mcu", help="extraction deck")
    parser.add_argument("--top", default=None, help="top cell (default: the GDS stem)")
    parser.add_argument(
        "--reference",
        type=Path,
        default=REFERENCE,
        help="reference netlist (regenerated before the run)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    klt = shutil.which("klt")
    if klt is None:
        print(
            "error: 'klt' not found on PATH. Install with:\n"
            "  uv tool install git+https://github.com/2AMLogic/klayout-tools\n"
            "(see layout/README.md)",
            file=sys.stderr,
        )
        return 1

    gds_path = args.gds if args.gds.is_absolute() else (Path.cwd() / args.gds).resolve()
    if not gds_path.exists():
        print(f"error: {gds_path} does not exist", file=sys.stderr)
        return 1

    block = args.block or gds_path.stem
    top = args.top or gds_path.stem
    reports_dir = REPORTS_ROOT / block
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Regenerate the reference so it can never be stale relative to the
    #    schematic netlist or the layout generator's own device parsing.
    regen = subprocess.run(
        [sys.executable, str(MAKE_REFERENCE), "-o", str(args.reference)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if regen.returncode != 0:
        print(regen.stdout, regen.stderr, file=sys.stderr)
        print("error: could not regenerate the reference netlist", file=sys.stderr)
        return 1

    record_id = report_id.record_id(
        reports_dir, _dt.datetime.now(_dt.timezone.utc), report_id.short_sha(REPO_ROOT)
    )
    gds_rel = gds_path.relative_to(REPO_ROOT)
    extracted = reports_dir / f"{record_id}.extracted.spice"

    # 2. Extract.
    extract_proc = subprocess.run(
        [
            klt, "extract", str(gds_rel),
            "--deck", args.deck,
            "--top", top,
            "--format", "json",
            "-o", str(extracted),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if extract_proc.returncode != 0:
        print(extract_proc.stdout, extract_proc.stderr, file=sys.stderr)
        print(f"error: klt extract failed (exit {extract_proc.returncode})", file=sys.stderr)
        return 1
    (reports_dir / f"{record_id}.extract.json").write_text(extract_proc.stdout)

    # 3. Compare.
    request = _build_request(
        gds_path=gds_path,
        reports_dir=reports_dir,
        reference=args.reference,
        deck=args.deck,
        top=top,
    )
    request_path = reports_dir / f"{record_id}.lvs-request.json"
    request_path.write_text(json.dumps(request, indent=2) + "\n")
    request_arg = str(request_path.relative_to(REPO_ROOT))

    lvs_json = subprocess.run(
        [klt, "lvs", request_arg, "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # exit 0 (match) and exit 3 (mismatch) are both successful runs.
    if lvs_json.returncode not in (0, 3):
        print(
            f"{lvs_json.stdout}{lvs_json.stderr}\n"
            f"error: klt lvs failed (exit {lvs_json.returncode})",
            file=sys.stderr,
        )
        return 1
    lvs_text = subprocess.run(
        [klt, "lvs", request_arg, "--format", "text"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    (reports_dir / f"{record_id}.lvs.json").write_text(lvs_json.stdout)
    (reports_dir / f"{record_id}.lvs.txt").write_text(lvs_text.stdout)

    extract_payload = json.loads(extract_proc.stdout)
    lvs_payload = json.loads(lvs_json.stdout)
    print(f"record id        : {record_id}")
    print(f"block            : {block}")
    print(f"extracted devices: {extract_payload['device_count']} {extract_payload['device_counts']}")
    print(f"lvs status       : {lvs_payload['status']}")
    print(f"mismatch_count   : {lvs_payload['mismatch_count']}")
    print(f"devices matched  : {lvs_payload['counts']['devices']['matched']} / "
          f"{lvs_payload['counts']['devices']['reference']}")
    print(f"nets matched     : {lvs_payload['counts']['nets']['matched']} / "
          f"{lvs_payload['counts']['nets']['reference']}")
    print(f"report (json)    : {(reports_dir / f'{record_id}.lvs.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
