#!/usr/bin/env python3
"""Prove the committed ``status: match`` LVS verdict is not vacuous.

The sibling of ``layout/drc/deck_negative_control.py``, for the LVS half of
the flow. A netlist comparison that reports ``match`` is only evidence if the
same comparison would report ``mismatch`` against a reference that genuinely
disagrees with the layout. This script builds that disagreement mechanically
-- it deletes **one** device card from the generated reference netlist,
leaving everything else byte-identical -- re-runs the same ``klt lvs`` engine
against the same extracted layout, and asserts the comparator notices.

That single-device perturbation is deliberately the smallest one available:
if `klt lvs` catches a 959-vs-958 device delta, it is comparing device by
device rather than pattern-matching a summary.

The perturbed reference is written under ``layout/build/`` (git-ignored
generator scratch, ``layout/README.md``); the **report** is committed under
``layout/lvs/reports/negative-control/``, under the same append-only rule as
the block's own reports.

Usage (from the repo root)::

    python3 layout/lvs/lvs_negative_control.py

Exit codes: 0 the comparator flagged the perturbed reference as expected,
1 it did not (or a tool/PDK prerequisite is missing) -- a 1 invalidates the
sibling ``status: match`` report until explained.
"""

from __future__ import annotations

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

BUILD_DIR = REPO_ROOT / "layout" / "build"
REFERENCE = REPO_ROOT / "layout" / "lvs" / "gate_driver_core.ref.spice"
PERTURBED = BUILD_DIR / "gate_driver_core.ref.one-device-short.spice"
REPORTS_DIR = REPO_ROOT / "layout" / "lvs" / "reports" / "negative-control"
GDS = REPO_ROOT / "layout" / "gate_driver_core.gds"
TOP = "gate_driver_core"
DECK = "gf180mcu"

#: The one device card removed from the reference. Any single card would do;
#: naming it explicitly keeps the control reproducible rather than dependent
#: on file order.
DROPPED_DEVICE = "Mx2_XMN6_0"


def main() -> int:
    if shutil.which("klt") is None:
        print(
            "error: 'klt' not found on PATH. Install with:\n"
            "  uv tool install git+https://github.com/2AMLogic/klayout-tools\n"
            "(see layout/README.md)",
            file=sys.stderr,
        )
        return 1
    if not REFERENCE.exists():
        print(
            f"error: {REFERENCE} does not exist -- run "
            "layout/lvs/make_reference.py first",
            file=sys.stderr,
        )
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    kept, dropped = [], 0
    for line in REFERENCE.read_text().splitlines():
        if line.split(" ", 1)[0] == DROPPED_DEVICE:
            dropped += 1
            continue
        kept.append(line)
    if dropped != 1:
        print(
            f"error: expected exactly one {DROPPED_DEVICE} card in "
            f"{REFERENCE.name}, found {dropped} -- update DROPPED_DEVICE",
            file=sys.stderr,
        )
        return 1
    PERTURBED.write_text("\n".join(kept) + "\n")

    record_id = report_id.record_id(
        REPORTS_DIR, _dt.datetime.now(_dt.timezone.utc), report_id.short_sha(REPO_ROOT)
    )
    request = {
        "layout": {
            "file": os.path.relpath(GDS, REPORTS_DIR),
            "deck": DECK,
            "top": TOP,
        },
        "reference": {
            "netlist": os.path.relpath(PERTURBED, REPORTS_DIR),
            "top": TOP,
        },
    }
    request_path = REPORTS_DIR / f"{record_id}.lvs-request.json"
    request_path.write_text(json.dumps(request, indent=2) + "\n")
    request_arg = str(request_path.relative_to(REPO_ROOT))

    proc = subprocess.run(
        ["klt", "lvs", request_arg, "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # exit 0 (match) and exit 3 (mismatch) are both successful runs.
    if proc.returncode not in (0, 3):
        print(proc.stdout, proc.stderr, file=sys.stderr)
        print(f"error: klt lvs failed (exit {proc.returncode})", file=sys.stderr)
        return 1
    text = subprocess.run(
        ["klt", "lvs", request_arg, "--format", "text"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    (REPORTS_DIR / f"{record_id}.lvs.json").write_text(proc.stdout)
    (REPORTS_DIR / f"{record_id}.lvs.txt").write_text(text.stdout)

    payload = json.loads(proc.stdout)
    print(f"record id      : {record_id}")
    print(f"dropped device : {DROPPED_DEVICE} (1 of 959 reference cards)")
    print(f"status         : {payload['status']}")
    print(f"mismatch_count : {payload['mismatch_count']}")
    print(f"report (json)  : {(REPORTS_DIR / f'{record_id}.lvs.json').relative_to(REPO_ROOT)}")

    failures = []
    if payload["status"] != "mismatch":
        failures.append(f"expected status 'mismatch', got {payload['status']!r}")
    if payload["category_counts"].get("device.unmatched", 0) < 1:
        failures.append(
            "expected at least one 'device.unmatched' finding, got "
            f"{payload['category_counts']!r}"
        )
    if payload["counts"]["devices"]["reference"] != 958:
        failures.append(
            "expected 958 reference devices after the drop, got "
            f"{payload['counts']['devices']['reference']}"
        )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(
            "The comparator did not notice a missing device -- a "
            "'status: match' report produced this way is not evidence until "
            "this is explained.",
            file=sys.stderr,
        )
        return 1

    print(
        "ok: dropping one of 959 reference devices flips the verdict to "
        "'mismatch' with a device.unmatched finding -- 'status: match' on the "
        "block is a real verdict"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
