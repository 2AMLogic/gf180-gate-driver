#!/usr/bin/env python3
"""Prove ``check_gate_driver_core.py``'s ``ground_rail_isolation`` PASS is real.

That check is, since issue #132, the **only** automated signal that would catch
an accidental short between ``GND_LOGIC`` and ``GND_DRV`` in the drawn
interconnect:

* ``klt extract`` (and therefore ``klt lvs``) reports the two rails as one
  merged net regardless of the drawn metal, because gf180mcu's curated deck
  ties every NMOS body to one hardcoded substrate global -- klayout-tools #1128;
* the ``devices`` check normalizes the same merge away (``_canon_net``);
* DRC does not cover it either: two same-layer shapes on *different* nets that
  overlap merge into one polygon, so no spacing rule fires.

So a PASS from it is only evidence if the same invocation would have *failed*
on a layout that really is shorted. This script produces that control, in the
same shape ``layout/drc/deck_negative_control.py`` uses for the DRC deck:
``klt draw`` a two-rail fixture (``klt draw`` applies no rule checking, so
deliberately bad geometry survives to the checker), then run the **same**
:func:`check_gate_driver_core.routed_metal_components` layer stack and the
**same** :func:`check_gate_driver_core.ground_rail_isolation_verdict` ruling
the block's own report was produced with -- not a re-typed copy of either.

Two fixtures, run as a pair, so both directions are pinned:

``isolated``
    two labeled Metal2 rails, nothing joining them -> must PASS.
``shorted``
    byte-identical plus one Metal1 bar and two Via1 cuts bridging the rails
    -- exactly the failure mode DRC cannot see, since the bridge is legal
    geometry on its own -> must FAIL, naming both rails.

The fixture GDS files are written under ``layout/build/`` (git-ignored
generator scratch, ``layout/README.md``) and are byte-reproducible from this
script, so nothing binary needs committing. Needs ``klt`` but **no PDK**:
``klt components`` runs no deck.

Usage (from the repo root)::

    python3 layout/ground_rail_negative_control.py

Exit codes: 0 both control fixtures ruled as they must, 1 either did not (or
``klt`` is missing) -- a 1 invalidates the sibling ``ground_rail_isolation``
PASS until explained, which is the whole point.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_gate_driver_core import (  # noqa: E402  (path set above)
    ground_rail_isolation_verdict,
    routed_metal_components,
)
from gen_gate_driver_core import (  # noqa: E402  (path set above)
    GenError,
    L_METAL1,
    L_METAL2,
    L_METAL2_LABEL,
    L_VIA1,
    REPO_ROOT,
)

BUILD_DIR = os.path.join(REPO_ROOT, "layout", "build")
CELL = "ground_rail_negative_control"
NETS = ["GND_DRV", "GND_LOGIC"]

#: Two Metal2 rails 2 um apart, each carrying its own name on the Metal2 text
#: layer -- the same two-rail arrangement the block draws, in miniature.
_ISOLATED_SHAPES = [
    {"layer": list(L_METAL2), "rect_um": [0.0, 0.0, 1.0, 20.0]},
    {"layer": list(L_METAL2), "rect_um": [3.0, 0.0, 4.0, 20.0]},
]
_LABELS = [
    {"layer": list(L_METAL2_LABEL), "text": "GND_LOGIC", "at_um": [0.5, 1.0]},
    {"layer": list(L_METAL2_LABEL), "text": "GND_DRV", "at_um": [3.5, 1.0]},
]
#: The short: a Metal1 bar spanning both rails, contacted to each with a Via1.
#: Every shape here is individually legal -- this is the case that reaches the
#: checker clean from DRC and merged from LVS.
_BRIDGE_SHAPES = [
    {"layer": list(L_METAL1), "rect_um": [0.0, 9.5, 4.0, 10.5]},
    {"layer": list(L_VIA1), "rect_um": [0.2, 9.8, 0.8, 10.2]},
    {"layer": list(L_VIA1), "rect_um": [3.2, 9.8, 3.8, 10.2]},
]


def _draw(name: str, shapes: list[dict]) -> str:
    """``klt draw`` one fixture into ``layout/build/`` and return its path."""
    os.makedirs(BUILD_DIR, exist_ok=True)
    gds = os.path.join(BUILD_DIR, f"ground-rail-{name}.gds")
    proc = subprocess.run(
        [
            "klt", "draw",
            "--params", json.dumps({"shapes": shapes, "labels": _LABELS}),
            "--cell-name", CELL,
            "-o", gds,
            "--format", "json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr, file=sys.stderr)
        raise GenError(f"could not draw the '{name}' control fixture")
    return gds


def _verdict(name: str, shapes: list[dict]) -> dict:
    return ground_rail_isolation_verdict(
        routed_metal_components(_draw(name, shapes), top=CELL), NETS
    )


def main() -> int:
    if shutil.which("klt") is None:
        print(
            "error: 'klt' not found on PATH. Install with:\n"
            "  uv tool install git+https://github.com/2AMLogic/klayout-tools\n"
            "(see layout/README.md)",
            file=sys.stderr,
        )
        return 1

    try:
        isolated = _verdict("isolated", _ISOLATED_SHAPES)
        shorted = _verdict("shorted", _ISOLATED_SHAPES + _BRIDGE_SHAPES)
    except GenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    failures: list[str] = []
    if not isolated["passed"]:
        failures.append(
            "the 'isolated' fixture (two separate rails) was reported as "
            f"shorted: {isolated['failures']}"
        )
    if isolated["component_count"] != 2:
        failures.append(
            f"expected 2 components in the 'isolated' fixture, got "
            f"{isolated['component_count']}"
        )
    if shorted["passed"]:
        failures.append(
            "the 'shorted' fixture (both rails bridged on Metal1 through Via1) "
            "was reported as clean -- the check cannot see a real short, so the "
            "block's own PASS means nothing"
        )
    else:
        message = " ".join(shorted["failures"])
        for net in NETS:
            if net not in message:
                failures.append(f"the 'shorted' verdict does not name {net}: {message}")

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        print(
            "ground_rail_isolation did not rule as it must on a known-good/"
            "known-bad pair -- the block's own PASS is not evidence until this "
            "is explained.",
            file=sys.stderr,
        )
        return 1

    print(
        "ok: ground_rail_isolation passed the isolated fixture (2 components) "
        "and failed the bridged one, naming both rails -- the block's own PASS "
        "is a real verdict"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
