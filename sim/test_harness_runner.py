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

Why ``ComposeDeckReltolDefaultTests`` exists (issue #156)
-----------------------------------------------------------

With no ``maxstep`` argument on ``tran`` and ngspice's own factory-default
``reltol`` (1e-3), local-truncation-error control is free to take timesteps
wide enough to straddle -- and skip the true peak of -- a sub-nanosecond
capacitive-coupling spike. Every recorded spec §2.3 gate-ceiling number so
far (decision records 0003-0006) is the peak of exactly that kind of spike,
so the harness-default deck was measuring a lower bound on the excursion,
not an upper one. ``compose_deck`` now appends a harness-wide
``.options reltol=1e-4`` default unless a testbench's own manifest already
opts into a ``reltol`` value (``sim/harness/README.md``'s
``"options": ["reltol=..."]`` syntax) -- a tighter ``reltol=1e-5`` was tried
first but rejected after a full 60-point PVT grid run aborted
("timestep too small") on 7 points it did not on a single-point test; these
tests pin the ``1e-4`` default staying in place, and that a manifest
override is honored rather than double-set.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR))

from harness import report  # noqa: E402
from harness.corners import CORNERS, PvtPoint, Rail  # noqa: E402
from harness.pdk import Pdk  # noqa: E402
from harness.runner import (  # noqa: E402
    DEFAULT_TRAN_RELTOL,
    RELTOL_SOURCE_DEFAULT,
    RELTOL_SOURCE_MANIFEST,
    PointResult,
    compose_deck,
    effective_reltol,
)
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


class ComposeDeckReltolDefaultTests(unittest.TestCase):
    """The generated deck must default to the tightened transient tolerance."""

    def test_deck_gets_the_harness_default_reltol(self):
        deck = compose_deck(_TB, _PDK, _POINT)
        self.assertIn(f".options reltol={DEFAULT_TRAN_RELTOL}", deck.splitlines())

    def test_reltol_line_sits_before_the_dut_include(self):
        # Guards against a future refactor moving the default reltol .options
        # line after .include of the testbench/DUT, where it would still
        # apply (ngspice options are deck-global) but would misleadingly read
        # as testbench-specific rather than harness-wide. dut_sha256 reads
        # the DUT file's bytes, so it must exist on disk for this call.
        with tempfile.TemporaryDirectory() as tmp:
            dut = Path(tmp) / "fake_dut.spice"
            dut.write_text("* fake dut\n")
            tb = replace(_TB, dut=dut)
            deck_lines = compose_deck(tb, _PDK, _POINT).splitlines()
        reltol_idx = deck_lines.index(f".options reltol={DEFAULT_TRAN_RELTOL}")
        dut_idx = next(
            i for i, line in enumerate(deck_lines) if line.startswith(".include") and "fake_dut" in line
        )
        self.assertLess(reltol_idx, dut_idx)

    def test_manifest_reltol_override_is_honored_not_double_set(self):
        # A testbench that opts into its own reltol (sim/harness/README.md's
        # "options": ["reltol=..."] syntax) must see exactly that value in
        # the deck, with no harness-default line appended alongside it --
        # ngspice takes the *last* .options reltol= line, so a naive
        # unconditional append would silently overrule a deliberate choice.
        tb = replace(_TB, options=("reltol=1e-6",))
        deck_lines = compose_deck(tb, _PDK, _POINT).splitlines()
        reltol_lines = [line for line in deck_lines if "reltol" in line]
        self.assertEqual(reltol_lines, [".options reltol=1e-6"])

    def test_manifest_reltol_override_tolerates_whitespace_and_case(self):
        tb = replace(_TB, options=("RELTOL = 2e-6",))
        deck_lines = compose_deck(tb, _PDK, _POINT).splitlines()
        reltol_lines = [line for line in deck_lines if "reltol" in line.lower()]
        self.assertEqual(reltol_lines, [".options RELTOL = 2e-6"])

    def test_effective_reltol_reports_the_default_with_no_manifest_override(self):
        self.assertEqual(effective_reltol(_TB), (DEFAULT_TRAN_RELTOL, RELTOL_SOURCE_DEFAULT))

    def test_effective_reltol_reports_the_manifest_override(self):
        tb = replace(_TB, options=("reltol=3e-6",))
        self.assertEqual(effective_reltol(tb), ("3e-6", RELTOL_SOURCE_MANIFEST))

    def test_manifest_pinning_the_default_value_still_reads_as_an_override(self):
        # The source is a property of *where the value came from*, not of the
        # value itself: a manifest that deliberately pins the same string the
        # harness default currently happens to use is still an override. A
        # value comparison against DEFAULT_TRAN_RELTOL would mislabel it, and
        # would silently change every such manifest's label the day the
        # default moves.
        tb = replace(_TB, options=(f"reltol={DEFAULT_TRAN_RELTOL}",))
        self.assertEqual(effective_reltol(tb), (DEFAULT_TRAN_RELTOL, RELTOL_SOURCE_MANIFEST))


class RecordEnvironmentReltolTests(unittest.TestCase):
    """The record's Environment block must say which reltol convention ran.

    issue #156's "Suggested work" asks the harness to record the transient
    tolerance settings on each record, so a later reader can tell which
    convention produced a given number without cross-referencing this repo's
    git history. Unlike ``_TB`` above (whose files never need to exist --
    ``compose_deck`` only interpolates paths), ``report.build_record`` reads
    the testbench's netlist/manifest bytes for their sha256 provenance, so
    this class needs real files on disk.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        directory = Path(self._tmp.name) / "testbench"
        directory.mkdir()
        netlist = directory / "fake_tb.spice"
        netlist.write_text("* fake netlist fragment\n")
        (directory / "tb.json").write_text('{"netlist": "fake_tb.spice", "measure": {"vout": "v(vout)"}}\n')
        self.tb = Testbench(
            directory=directory,
            name="fake-experiment",
            netlist=netlist,
            rails=(Rail("vdrv", 5.0, 0.10),),
            analyses=("op",),
            measure={"vout": "v(vout)"},
        )

    def _record(self, tb: Testbench) -> dict:
        result = PointResult(point=_POINT, status="ok", measurements={"vout": 5.0})
        return report.build_record(
            tb=tb,
            pdk=_PDK,
            points=[_POINT],
            results=[result],
            ngspice="ngspice-47 : Circuit level simulation program",
            repo_root=REPO_ROOT,
            record_id="19700101-000000-0000000",
            started_utc="1970-01-01T00:00:00+00:00",
            wall_seconds=1.0,
            git={"commit": "0" * 40, "short": "0000000", "branch": "test", "dirty": False},
        )

    def test_harness_default_reltol_is_reported(self):
        record = self._record(self.tb)
        self.assertEqual(record["environment"]["tran_reltol"], DEFAULT_TRAN_RELTOL)
        self.assertEqual(record["environment"]["tran_reltol_source"], RELTOL_SOURCE_DEFAULT)
        text = report.render_record(record, "fake-experiment")
        self.assertIn(
            f"Transient tolerance: reltol={DEFAULT_TRAN_RELTOL} (harness default)", text
        )

    def test_manifest_override_reltol_is_reported(self):
        tb = replace(self.tb, options=("reltol=1e-6",))
        record = self._record(tb)
        self.assertEqual(record["environment"]["tran_reltol"], "1e-6")
        self.assertEqual(record["environment"]["tran_reltol_source"], RELTOL_SOURCE_MANIFEST)
        text = report.render_record(record, "fake-experiment")
        self.assertIn("Transient tolerance: reltol=1e-6 (manifest override)", text)

    def test_manifest_pinning_the_default_value_is_recorded_as_an_override(self):
        # Judge's review of PR #165: the source must not be inferred by
        # string-comparing the value against DEFAULT_TRAN_RELTOL -- a
        # manifest that explicitly pins the default's current value is an
        # override, and the record must say so.
        tb = replace(self.tb, options=(f"reltol={DEFAULT_TRAN_RELTOL}",))
        record = self._record(tb)
        self.assertEqual(record["environment"]["tran_reltol"], DEFAULT_TRAN_RELTOL)
        self.assertEqual(record["environment"]["tran_reltol_source"], RELTOL_SOURCE_MANIFEST)
        text = report.render_record(record, "fake-experiment")
        self.assertIn(
            f"Transient tolerance: reltol={DEFAULT_TRAN_RELTOL} (manifest override)", text
        )


if __name__ == "__main__":
    unittest.main()
