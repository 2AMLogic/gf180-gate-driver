#!/usr/bin/env python3
"""Reproducible, append-only ``klt extract --parasitics`` run for ``layout/``.

Distinct from ``run_lvs.py``'s own (non-parasitic) extraction: that one
exists to compare against the LVS reference; this one exists to feed
``mk_extracted_dut.py``, which turns its report into a simulatable post-layout
DUT netlist for ``sim/`` (issue #105's post-layout-verification requirement).
Kept as a separate command/report series rather than folded into
``run_lvs.py`` because the two extractions serve different consumers and
``--parasitics`` measurably changes the extraction's output shape
(``docs/cli/extract.md``: "byte-identical to a schematic-equivalent
extraction" when omitted).

Writes ``layout/lvs/reports/<block>/<record-id>.pex-extract.json`` --
never overwritten, same append-only convention as ``run_drc.py``/``run_lvs.py``
(``sim/README.md``, CLAUDE.md).

Usage (from the repo root)::

    python3 layout/lvs/run_pex_extract.py layout/gate_driver_core.gds
"""

from __future__ import annotations

import argparse
import datetime as _dt
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "layout" / "common"))

import report_id  # noqa: E402

REPORTS_ROOT = Path(__file__).resolve().parent / "reports"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gds", type=Path, help="path to the GDS/OASIS file")
    parser.add_argument("--block", help="report subdirectory (default: the GDS stem)")
    parser.add_argument("--deck", default="gf180mcu", help="extraction deck")
    parser.add_argument("--top", default=None, help="top cell (default: the GDS stem)")
    args = parser.parse_args()

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

    record_id = report_id.record_id(
        reports_dir, _dt.datetime.now(_dt.timezone.utc), report_id.short_sha(REPO_ROOT)
    )
    gds_rel = gds_path.relative_to(REPO_ROOT)
    scratch_spice = reports_dir / f"{record_id}.pex-extract.spice"

    proc = subprocess.run(
        [
            "klt", "extract", str(gds_rel),
            "--deck", args.deck,
            "--top", top,
            "--parasitics",
            "--format", "json",
            "-o", str(scratch_spice),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr, file=sys.stderr)
        print(f"error: klt extract --parasitics failed (exit {proc.returncode})", file=sys.stderr)
        return 1

    json_path = reports_dir / f"{record_id}.pex-extract.json"
    json_path.write_text(proc.stdout)
    # The raw klt SPICE writer's own output is a scratch intermediate --
    # mk_extracted_dut.py rebuilds a simulatable netlist directly from the
    # JSON (see that script's docstring), so this file is not committed
    # evidence in its own right; drop it rather than leave an unused
    # near-duplicate of the committed .json report next to it.
    scratch_spice.unlink(missing_ok=True)

    print(f"record id : {record_id}")
    print(f"block     : {block}")
    print(f"report    : {json_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
