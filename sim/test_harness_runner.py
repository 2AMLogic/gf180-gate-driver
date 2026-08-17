#!/usr/bin/env python3
"""Regression tests for ``sim/harness/runner.py``'s deck composition.

    python3 sim/test_harness_runner.py     # or: python3 -m unittest ...

Standard-library ``unittest`` only, and deliberately **PDK-free and
ngspice-free**, matching ``sim/test_harness_checks.py``'s convention: put
``sim/`` on ``sys.path`` and import the ``harness`` package rather than
requiring the repo to be installed. ``compose_deck()`` is a pure function --
it takes a ``Testbench``/``Pdk``/``PvtPoint`` and returns a deck string, with
no ngspice invocation and no PDK install required (``Pdk.design_include`` and
``Pdk.model_lib`` are plain path properties; neither is read from disk by
``compose_deck`` itself) -- so this suite runs under the CI ``test`` job with
nothing but ``python3``, same as ``sim/test_harness_checks.py``.

Why this file exists (issue #146)
----------------------------------

A locally built, OpenMP-enabled ngspice reads its own ``spinit`` (or a
``.spiceinit``) for a default thread count. On a host whose ``spinit``
carries ``set num_threads=8``, every PVT point run through
``sim/run_corners.py -j N`` becomes pure oversubscription -- N harness
processes each *also* fanning out across 8 OpenMP threads on the same box --
measured at ~2000x slower for byte-identical measurements. The fix pins
``set num_threads=1`` in the generated deck's ``.control`` block so a run's
speed is independent of host ``spinit`` configuration; this test is the
regression guard that keeps it there.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR))

from harness.corners import CORNERS, PvtPoint, Rail  # noqa: E402
from harness.pdk import Pdk  # noqa: E402
from harness.runner import compose_deck  # noqa: E402
from harness.testbench import Testbench  # noqa: E402

#: A minimal single-rail testbench -- enough to exercise every branch of
#: compose_deck() that doesn't require a real PDK checkout or netlist file
#: on disk (compose_deck only interpolates tb.netlist as a path string, it
#: never reads it).
_TB = Testbench(
    directory=SIM_DIR / "fake-experiment" / "testbench",
    name="fake-experiment",
    netlist=SIM_DIR / "fake-experiment" / "testbench" / "fake_tb.spice",
    rails=(Rail("vdrv", 5.0, 0.10),),
    analyses=("op",),
    measure={"vout": "v(vout)"},
)

#: A Pdk pointing at a nonexistent path -- fine, since Pdk.version() checks
#: Path.is_file() and falls back to "unknown" rather than raising, and
#: compose_deck only ever formats design_include/model_lib as path strings.
_PDK = Pdk(path=Path("/nonexistent/gf180mcuD"), variant="gf180mcuD", source="test")

_POINT = PvtPoint(corner=CORNERS["tt"], temp_c=27.0, supplies={"vdrv": 5.0})


class ComposeDeckThreadPinTests(unittest.TestCase):
    """The generated ``.control`` block must pin ngspice to one thread."""

    def test_deck_pins_num_threads_to_one(self):
        deck = compose_deck(_TB, _PDK, _POINT)
        self.assertIn("set num_threads=1", deck.splitlines())

    def test_num_threads_line_sits_in_the_control_block(self):
        # Guards against a future refactor accidentally emitting the line
        # outside .control/.endc, where ngspice would not apply it.
        deck_lines = compose_deck(_TB, _PDK, _POINT).splitlines()
        control_start = deck_lines.index(".control")
        control_end = deck_lines.index(".endc")
        self.assertIn("set num_threads=1", deck_lines[control_start:control_end])

    def test_alongside_the_existing_numdgt_and_noaskquit_pins(self):
        # compose_deck's own docstring/README describe num_threads=1 as
        # living "alongside" the pre-existing accuracy/prompt pins -- assert
        # all three survive together rather than one silently regressing.
        deck_lines = compose_deck(_TB, _PDK, _POINT).splitlines()
        for expected in ("set numdgt=10", "set noaskquit", "set num_threads=1"):
            with self.subTest(expected=expected):
                self.assertIn(expected, deck_lines)


if __name__ == "__main__":
    unittest.main()
