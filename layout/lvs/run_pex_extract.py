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

Stores ``layout/lvs/reports/<block>/<record-id>.pex-extract.json`` in the
artifact store (``layout/common/signoff_store.py``, issue #348); git keeps only
the manifest. Nothing here is committed bytes, so an extraction a DUT header
or CI step consumes must be *promoted* deliberately: copy the printed staged
file into ``layout/lvs/reports/<block>/`` under the same name and commit it
(``layout/README.md``, "Stored vs committed signoff outputs"). Never
overwritten, same append-only convention as ``run_drc.py``/``run_lvs.py``.

Usage (from the repo root)::

    python3 layout/lvs/run_pex_extract.py layout/gate_driver_core.gds
"""

from __future__ import annotations

import argparse
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
    parser.add_argument("gds", type=Path, help="path to the GDS/OASIS file")
    parser.add_argument("--block", help="report subdirectory (default: the GDS stem)")
    parser.add_argument("--deck", default="gf180mcu", help="extraction deck")
    parser.add_argument("--top", default=None, help="top cell (default: the GDS stem)")
    args = parser.parse_args()

    klt = klt_env.require_klt()
    signoff_store.preflight_or_exit(REPO_ROOT)

    gds_path = klt_env.resolve_existing(args.gds)

    block = args.block or gds_path.stem
    top = args.top or gds_path.stem
    reports_dir = REPORTS_ROOT / block
    bench = f"layout-pex-{block}"
    record_id = signoff_store.new_record_id(REPO_ROOT, bench, reports_dir)
    stage = signoff_store.stage_dir(REPO_ROOT, bench, record_id)
    gds_rel = gds_path.relative_to(REPO_ROOT)
    scratch_spice = stage / f"{record_id}.pex-extract.spice"

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

    json_path = stage / f"{record_id}.pex-extract.json"
    json_path.write_text(proc.stdout)
    # The raw klt SPICE writer's own output is a scratch intermediate --
    # mk_extracted_dut.py rebuilds a simulatable netlist directly from the
    # JSON (see that script's docstring), so this file is not committed
    # evidence in its own right; drop it rather than leave an unused
    # near-duplicate of the committed .json report next to it.
    scratch_spice.unlink(missing_ok=True)
    manifest = signoff_store.store_or_exit(
        stage, repo_root=REPO_ROOT, bench=bench, rid=record_id,
        name_prefix=str(reports_dir.relative_to(REPO_ROOT)),
    )

    print(f"record id : {record_id}")
    print(f"block     : {block}")
    print(f"staged    : {json_path.relative_to(REPO_ROOT)}")
    print(f"manifest  : {manifest.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
