#!/usr/bin/env python3
"""Pins the helpers shared by the standalone ``sim/*/run_*.py`` scripts.

    python3 sim/test_harness_script_helpers.py    # or: python3 -m unittest ...

Standard-library ``unittest`` only, and deliberately **PDK-free and
ngspice-free** (the convention ``sim/test_harness_checks.py``,
``sim/test_harness_runner.py`` and ``sim/test_harness_campaign.py`` set): the
only tests that touch ``ngspice`` put a two-line shell stub on ``PATH``, so the
suite runs on a bare runner with nothing but ``python3``.

Why this file is stdlib ``unittest`` (issue #429)
-------------------------------------------------

It was written pytest-style -- bare module-level ``def test_*``, the
``tmp_path``/``monkeypatch`` fixtures, ``pytest.raises`` -- which no runner in
this repo executes: the repo is stdlib-only by policy (``sim/harness/README.md``:
"stdlib only, no packages"; ``.github/workflows/ci.yml``: "python3 (stdlib) and
shellcheck"), so ``python3 -m unittest`` collected zero tests from it and CI
never named it. The twenty pins below guarded nothing for the eight dedupe
refactors (``687fa8d`` .. ``72b0e07``) that each hoisted a helper into
``harness/script_helpers.py`` and added its pin here. Converted in place and
wired into the PDK-free ``test`` job; step 5/5 of ``.github/scripts/lint.sh``
now fails any tracked ``test_*.py`` that CI does not run, so the same gap
cannot reopen silently.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM_DIR))

import mismatch_body_fixture as fixture  # noqa: E402

from harness import campaign  # noqa: E402
from harness import corners as harness_corners  # noqa: E402
from harness import script_helpers  # noqa: E402

LOG = """\
noise
Index   v(a)   v(b)
-----------------------
0       1.0    2.0
1       3.0    4.0
Index   i(x)
-----------------------
0       5e-3
"""


class _Pdk:
    design_include = "/pdk/design.ngspice"
    model_lib = "/pdk/sm141064.ngspice"


class _RelativePdk:
    design_include = "design.ngspice"
    model_lib = "sm141064.ngspice"


class _RecordingOutcome:
    """A `PointOutcome` stand-in that records which measurement was asked for."""

    def __init__(self):
        self.asked = []

    def values(self, name):
        self.asked.append(name)
        return [1.0, 3.0]


class _TempDirCase(unittest.TestCase):
    """Base: a throwaway directory (the pytest ``tmp_path`` fixture's job)."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp_path = Path(td.name)

    def patch(self, patcher):
        """Start `patcher` for the duration of the test (``monkeypatch``'s job)."""
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def stub_ngspice(self, body: str) -> Path:
        """Put a ``/bin/sh`` stub named ``ngspice`` first on ``PATH``."""
        stub = self.tmp_path / "bin" / "ngspice"
        stub.parent.mkdir()
        stub.write_text("#!/bin/sh\n" + body)
        stub.chmod(0o755)
        self.patch(
            mock.patch.dict(os.environ, {"PATH": f"{stub.parent}:/usr/bin:/bin"})
        )
        return self.tmp_path


class TestFormattingAndLogParsing(unittest.TestCase):
    def test_fmt_four_digits_and_none(self):
        self.assertEqual(script_helpers.fmt(1.23456789), "1.2346")
        self.assertEqual(script_helpers.fmt(1.23456789, 6), "1.234568")
        self.assertEqual(script_helpers.fmt(None), "n/a")

    def test_parse_dc_tables_and_column(self):
        tables = script_helpers.parse_dc_tables(LOG)
        self.assertEqual(
            tables,
            [
                (["v(a)", "v(b)"], [[1.0, 2.0], [3.0, 4.0]]),
                (["i(x)"], [[5e-3]]),
            ],
        )
        header, rows = tables[0]
        self.assertEqual(script_helpers.column(header, rows, "v(b)"), [2.0, 4.0])


class TestCornerShim(unittest.TestCase):
    def test_corner_shim_sections_temp_and_extra_lines(self):
        deck = script_helpers.corner_shim(
            _Pdk(),
            ["typical", "cap_typical"],
            27,
            script="run_x.py",
            extra_lines=[".options reltol=1e-4"],
        )
        self.assertEqual(
            deck.splitlines(),
            [
                "* Generated per corner point by run_x.py from",
                "* $PDK_ROOT/$PDK (via sim/harness/pdk.py) -- do not edit by hand, "
                "and do not commit.",
                '.include "/pdk/design.ngspice"',
                '.lib "/pdk/sm141064.ngspice" typical',
                '.lib "/pdk/sm141064.ngspice" cap_typical',
                ".temp 27",
                ".options reltol=1e-4",
            ],
        )
        self.assertTrue(deck.endswith("\n"))


class TestCampaignGlue(unittest.TestCase):
    def test_build_points_matches_inline_grid(self):
        names = list(harness_corners.CORNERS)[:2]
        temps = (-40.0, 125.0)
        supplies = {"vdd": 5.0}
        expected = harness_corners.build_grid(
            [harness_corners.CORNERS[n] for n in names], list(temps), [dict(supplies)]
        )
        got = script_helpers.build_points(names, temps, supplies)
        self.assertEqual(got, expected)
        self.assertEqual(len(got), len(names) * len(temps))

    def test_claim_sigma_summary_uses_named_measurement(self):
        direct = _RecordingOutcome()
        expected = campaign.point_sigma_summary([direct], lambda o: o.values("m"))
        via_helper = _RecordingOutcome()
        self.assertEqual(script_helpers.claim_sigma_summary([via_helper], "m"), expected)
        self.assertEqual(via_helper.asked, direct.asked)

    def test_claim_progress_detail_formats_measurement_or_falls_back(self):
        class Result:
            def __init__(self):
                self.measurements = {"m": 1.5}
                self.message = "no data"

        self.assertEqual(
            script_helpers.claim_progress_detail(Result(), "m"), campaign.fmt(1.5, 10)
        )
        self.assertEqual(script_helpers.claim_progress_detail(Result(), "other"), "no data")


class _WorstCaseOutcome:
    """A `PointOutcome` stand-in: canned draws and control value per name."""

    def __init__(self, values: dict, controls: dict | None = None):
        self._values = values
        self._controls = controls or {}

    def values(self, name):
        return self._values.get(name, [])

    def control_value(self, name):
        return self._controls.get(name)


class TestWorstAcrossPoints(unittest.TestCase):
    """`worst_across_points` -- the per-node worst case across a campaign.

    Was a byte-identical 14-line loop in the `indrv` and `taper` runners until
    issue #465 hoisted it here; the record rows it feeds are pinned
    byte-for-byte by the goldens in `sim/testdata/mismatch_record_body/`.
    """

    def test_reduces_max_over_every_outcome(self):
        outcomes = [
            _WorstCaseOutcome({"a": [1.0, 5.5]}, {"a": 4.0}),
            _WorstCaseOutcome({"a": [6.1, 2.0]}, {"a": 4.5}),
        ]
        (worst,) = script_helpers.worst_across_points(outcomes, ("a",), 6.0)
        self.assertEqual(worst.name, "a")
        self.assertEqual(worst.mc_worst, 6.1)
        self.assertEqual(worst.ctrl_worst, 4.5)
        self.assertAlmostEqual(worst.delta, 1.6)
        # Above the ceiling, so the margin is negative.
        self.assertAlmostEqual(worst.margin, -0.1)

    def test_name_with_no_converged_draw_is_omitted(self):
        # `b` has a control value but no draw anywhere: no worst case to report.
        outcomes = [_WorstCaseOutcome({"a": [1.0]}, {"a": 1.0, "b": 2.0})]
        got = script_helpers.worst_across_points(outcomes, ("a", "b"), 6.0)
        self.assertEqual([worst.name for worst in got], ["a"])

    def test_no_outcomes_yields_no_rows(self):
        self.assertEqual(script_helpers.worst_across_points([], ("a",), 6.0), [])

    def test_name_with_no_control_leaves_ctrl_worst_and_delta_none(self):
        (worst,) = script_helpers.worst_across_points(
            [_WorstCaseOutcome({"a": [5.0]})], ("a",), 6.0
        )
        self.assertIsNone(worst.ctrl_worst)
        self.assertIsNone(worst.delta)
        self.assertAlmostEqual(worst.margin, 1.0)

    def test_rows_follow_the_order_of_the_names_argument(self):
        outcomes = [_WorstCaseOutcome({"a": [1.0], "b": [2.0]})]
        got = script_helpers.worst_across_points(outcomes, ("b", "a"), 6.0)
        self.assertEqual([worst.name for worst in got], ["b", "a"])

    def test_field_order_is_the_one_the_record_rows_unpack(self):
        # Both runners unpack the row positionally, so the field order is part
        # of the contract, not an implementation detail.
        (row,) = script_helpers.worst_across_points(
            [_WorstCaseOutcome({"a": [5.0]}, {"a": 4.0})], ("a",), 6.0
        )
        name, ctrl_worst, mc_worst, delta, margin = row
        self.assertEqual((name, ctrl_worst, mc_worst), ("a", 4.0, 5.0))
        self.assertAlmostEqual(delta, 1.0)
        self.assertAlmostEqual(margin, 1.0)


class TestRatifiedSpecValues(unittest.TestCase):
    """The ratified values shared by the `indrv` and `taper` campaigns have
    exactly one home, and each runner reads it (issue #465, item 2).

    Identity, not equality, is the assertion: a literal retyped back into a
    runner would still compare equal today, and that is precisely the drift
    being guarded. Two independent literals mean a decision record moving the
    §2.3 ceiling or Exception 2's bound can reach one campaign and miss the
    other, leaving two append-only records disagreeing about the same ratified
    number with nothing in the tree flagging it.
    """

    def test_values_are_the_ratified_numbers(self):
        self.assertEqual(script_helpers.GATE_CEILING_V, 6.0)
        self.assertEqual(script_helpers.EXCEPTION2_BOUND_V, 0.175)
        self.assertEqual(
            script_helpers.TAPER_MEASUREMENTS,
            ("n1_max_v", "n2_max_v", "n3_max_v", "n4_max_v", "n5_max_v"),
        )

    def test_both_runners_read_the_shared_values(self):
        for key in ("indrv", "taper"):
            module = fixture.load_runner(key)
            for name in ("GATE_CEILING_V", "EXCEPTION2_BOUND_V", "TAPER_MEASUREMENTS"):
                with self.subTest(runner=key, constant=name):
                    self.assertIs(
                        getattr(module, name), getattr(script_helpers, name)
                    )


class TestRunNgspice(_TempDirCase):
    def test_run_ngspice_returns_combined_log(self):
        work = self.stub_ngspice("echo out; echo err >&2\n")
        self.assertEqual(
            script_helpers.run_ngspice(work, "d.spice", "typical @ 27 C"), "out\nerr\n"
        )

    def test_run_ngspice_raises_on_nonzero_exit(self):
        work = self.stub_ngspice("echo boom; exit 3\n")
        with self.assertRaisesRegex(
            RuntimeError, r"exited 3 for d\.spice \[ss @ 125 C\]"
        ):
            script_helpers.run_ngspice(work, "d.spice", "ss @ 125 C")

    def test_run_ngspice_raises_on_error_line(self):
        work = self.stub_ngspice("echo 'Error: no such model'\n")
        with self.assertRaisesRegex(
            RuntimeError, r"reported an error for d\.spice \[tt\]"
        ):
            script_helpers.run_ngspice(work, "d.spice", "tt")


class TestRunCornerDeck(_TempDirCase):
    def test_run_corner_deck_stages_wrapper_and_included_files(self):
        seen = {}

        def fake_run(work, deck_name, label):
            seen["deck_name"] = deck_name
            seen["label"] = label
            seen["files"] = {p.name: p.read_text() for p in work.iterdir()}
            return "log"

        self.patch(mock.patch.object(script_helpers, "run_ngspice", fake_run))
        deck = self.tmp_path / "dut.spice"
        deck.write_text("* dut\nR1 a b 1k")

        log = script_helpers.run_corner_deck(
            deck, _RelativePdk(), ["typical"], 27.0,
            script="run_x.py", control=".control\nrun\n.endc", label="tt @ 27 C",
            prefix="x-", extra_lines=[".options abstol=1e-12"],
        )
        self.assertEqual(log, "log")
        self.assertEqual(seen["deck_name"], "dut.spice")
        self.assertEqual(seen["label"], "tt @ 27 C")
        files = seen["files"]
        self.assertEqual(set(files), {"corner.spice", "control.spice", "dut.spice"})
        self.assertIn(".temp 27", files["corner.spice"])
        self.assertIn(".options abstol=1e-12", files["corner.spice"])
        self.assertEqual(files["control.spice"], ".control\nrun\n.endc")
        self.assertEqual(
            files["dut.spice"],
            '.include "corner.spice"\n* dut\nR1 a b 1k\n.include "control.spice"\n.end\n',
        )


class TestFirstCrossing(unittest.TestCase):
    def test_first_crossing_rising_interpolates(self):
        self.assertEqual(script_helpers.first_crossing([0, 1, 2], [0.0, 1.0, 3.0], 2.0), 1.5)

    def test_first_crossing_falling_interpolates(self):
        self.assertEqual(
            script_helpers.first_crossing([0, 1, 2], [3.0, 1.0, 0.0], 2.0, rising=False),
            0.5,
        )

    def test_first_crossing_direction_must_match(self):
        self.assertIsNone(script_helpers.first_crossing([0, 1, 2], [3.0, 1.0, 0.0], 2.0))
        self.assertIsNone(
            script_helpers.first_crossing([0, 1, 2], [0.0, 1.0, 3.0], 2.0, rising=False)
        )

    def test_first_crossing_skips_flat_segment_and_takes_first_crossing(self):
        xs, ys = [0, 1, 2, 3, 4], [1.0, 1.0, 1.0, 5.0, 0.0]
        self.assertEqual(script_helpers.first_crossing(xs, ys, 3.0), 2.5)

    def test_first_crossing_threshold_on_sample_and_none_when_absent(self):
        self.assertEqual(script_helpers.first_crossing([0, 1], [0.0, 2.0], 2.0), 1.0)
        self.assertIsNone(script_helpers.first_crossing([0, 1], [0.0, 2.0], 5.0))
        self.assertIsNone(script_helpers.first_crossing([], [], 1.0))

    def test_first_crossing_log_interpolates_in_log_y(self):
        # Geometric midpoint of 1e-6..1e-4 is 1e-5, halfway in x.
        got = script_helpers.first_crossing([0.0, 1.0], [1e-6, 1e-4], 1e-5, log=True)
        self.assertLess(abs(got - 0.5), 1e-12)
        self.assertNotEqual(
            script_helpers.first_crossing([0.0, 1.0], [1e-6, 1e-4], 1e-5), got
        )

    def test_first_crossing_log_nonpositive_bracket_returns_left_x(self):
        self.assertEqual(
            script_helpers.first_crossing([2.0, 3.0], [0.0, 1.0], 0.5, log=True), 2.0
        )


class TestRangeVerdict(unittest.TestCase):
    def test_range_verdict(self):
        rv = script_helpers.range_verdict
        self.assertEqual(rv(None, 0, 1), "ERROR (no crossing found)")
        self.assertEqual(rv(0.5, 0, 1), "PASS")
        self.assertEqual(rv(0, 0, 1), "PASS")
        self.assertEqual(rv(1, 0, 1), "PASS")
        self.assertEqual(rv(-0.1, 0, 1), "FAIL")
        self.assertEqual(rv(1.1, 0, 1), "FAIL")
        self.assertEqual(rv(5, None, 5), "PASS")
        self.assertEqual(rv(6, None, 5), "FAIL")
        self.assertEqual(rv(-1, 0, None), "FAIL")


class TestRonwMismatchErrorDisclosure(_TempDirCase):
    def test_ronw_mismatch_run_sample_discloses_ngspice_error(self):
        """A non-converged Monte Carlo draw is reported as ``"error"`` (with the
        shared runner's message), not raised -- the campaign must not abort."""
        self.stub_ngspice("echo 'Error: timestep too small'\n")

        sibling = str(SIM_DIR / "low-side-power-switch")
        sys.path.insert(0, sibling)
        self.addCleanup(lambda: sys.path.remove(sibling))

        spec = importlib.util.spec_from_file_location(
            "run_ronw_mismatch",
            SIM_DIR / "low-side-power-switch-ronw-mismatch" / "run_ronw_mismatch.py",
        )
        ronw = importlib.util.module_from_spec(spec)
        self.patch(mock.patch.dict(sys.modules, {spec.name: ronw}))
        spec.loader.exec_module(ronw)

        corner = harness_corners.CORNERS["tt"]
        status, log, flat = ronw._run_sample(_RelativePdk(), corner, 27.0, None)
        self.assertEqual(status, "error")
        self.assertIn("reported an error for", log)
        self.assertIn("tt @ 27.0 C", log)
        self.assertEqual(flat, {})


class TestReferenceMeasurements(_TempDirCase):
    def test_reference_measurements_parses_log_and_defaults_empty(self):
        log = self.tmp_path / "c1.log"
        log.write_text("m_peak_v = 1.25e+00\n")
        paths = {"c1": log}
        self.patch(
            mock.patch.object(
                script_helpers,
                "reference_log_path",
                lambda exp, rec, cid: paths.get(cid),
            )
        )
        self.assertEqual(
            script_helpers.reference_measurements("exp", "rec", "c1"), {"peak_v": 1.25}
        )
        self.assertEqual(script_helpers.reference_measurements("exp", "rec", "missing"), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
