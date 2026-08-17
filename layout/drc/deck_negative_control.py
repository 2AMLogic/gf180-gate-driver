#!/usr/bin/env python3
"""Prove the committed ``status: clean`` DRC verdict is not vacuous.

A clean DRC report is only evidence if the deck it was produced with would
have *flagged* something. This script produces that control: it draws a
deliberately illegal fixture with ``klt draw`` -- two Metal1 rectangles
0.05 um apart, against gf180mcu's 0.23 um ``metal1.space.1`` minimum -- runs
the **same** ``layout/drc/run_drc.py`` entry point and the **same**
``gf180mcu`` deck the block's own report was produced with, and asserts the
expected rule fires.

``klt draw`` is the documented way to build such a fixture (``docs/cli/draw.md``:
"so a DRC flow's negative case (a known-bad fixture that must come back
flagged) can be produced with klt alone"); it applies no rule checking, so the
illegal geometry survives to the checker.

The fixture GDS is written under ``layout/build/`` (git-ignored generator
scratch, ``layout/README.md``) and is byte-reproducible from this script, so
nothing binary needs committing to reproduce the control. The **report** is
committed, under ``layout/drc/reports/deck-negative-control/``, alongside the
block's own reports and under the same append-only rule.

Usage (from the repo root)::

    python3 layout/drc/deck_negative_control.py

Exit codes: 0 the deck flagged the fixture as expected, 1 it did not (or a
tool/PDK prerequisite is missing) -- a 1 invalidates the sibling
``status: clean`` report until explained, which is the whole point.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = REPO_ROOT / "layout" / "build"
FIXTURE_GDS = BUILD_DIR / "drc-negative-control.gds"
RUN_DRC = REPO_ROOT / "layout" / "drc" / "run_drc.py"
FIXTURE_NAME = "deck-negative-control"

#: Metal1 (34/0), two rectangles 0.05 um apart. gf180mcu's metal1.space.1
#: minimum is 0.23 um, so exactly one spacing violation must be reported.
FIXTURE_SHAPES = {
    "shapes": [
        {"layer": [34, 0], "rect_um": [0, 0, 1, 1]},
        {"layer": [34, 0], "rect_um": [1.05, 0, 2.05, 1]},
    ]
}
EXPECTED_RULE = "metal1.space.1"


def main() -> int:
    if shutil.which("klt") is None:
        print(
            "error: 'klt' not found on PATH. Install with:\n"
            "  uv tool install git+https://github.com/2AMLogic/klayout-tools\n"
            "(see layout/README.md)",
            file=sys.stderr,
        )
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    draw = subprocess.run(
        [
            "klt", "draw",
            "--params", json.dumps(FIXTURE_SHAPES),
            "--cell-name", "drc_negative_control",
            "-o", str(FIXTURE_GDS),
            "--format", "json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if draw.returncode != 0:
        print(draw.stdout, draw.stderr, file=sys.stderr)
        print("error: could not draw the negative-control fixture", file=sys.stderr)
        return 1

    drc = subprocess.run(
        [sys.executable, str(RUN_DRC), str(FIXTURE_GDS), "--fixture", FIXTURE_NAME],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print(drc.stdout, end="")
    if drc.returncode != 0:
        print(drc.stderr, file=sys.stderr)
        return 1

    report_line = next(
        line for line in drc.stdout.splitlines() if line.startswith("report (json)")
    )
    report_path = REPO_ROOT / report_line.split(":", 1)[1].strip()
    payload = json.loads(report_path.read_text())

    failures = []
    if payload["status"] != "violations":
        failures.append(f"expected status 'violations', got {payload['status']!r}")
    if payload["rule_counts"].get(EXPECTED_RULE) != 1:
        failures.append(
            f"expected exactly one {EXPECTED_RULE} violation, got "
            f"{payload['rule_counts']!r}"
        )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(
            "The gf180mcu deck did not flag a fixture it must flag -- a "
            "'status: clean' report produced with this deck is not evidence "
            "until this is explained.",
            file=sys.stderr,
        )
        return 1

    print(
        f"ok: the gf180mcu deck flagged the known-bad fixture "
        f"({EXPECTED_RULE} x1) -- 'status: clean' on the block is a real verdict"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
