#!/usr/bin/env python3
"""Regression tests for the harness's spec-check evaluation.

    python3 sim/test_harness_checks.py     # or: python3 -m unittest ...

Standard-library ``unittest`` only, and deliberately **PDK-free and
ngspice-free**: everything under test here is pure bound arithmetic over
already-collected measurements, so this suite runs on a bare runner (the
``test`` job in ``.github/workflows/ci.yml``) with nothing but ``python3``.
It follows ``sim/check_records.py``'s import convention -- put ``sim/`` on
``sys.path`` and import the ``harness`` package -- rather than requiring the
repo to be installed.

Why this file exists (issue #125)
---------------------------------

``spec/gate-driver.md`` §3 states two tiers for the same parameter:

    | Peak source/sink current | >= 0.5 A | 1 A stretch  |
    | Propagation delay        |  < 50 ns | < 25 ns      |

but ``report.evaluate_checks`` used to apply a single static ``min``/``max``
across the whole PVT grid. A testbench that opts into the 6 V ``vdrv``
stretch point (``"stretch": true``, ``extra_v``) therefore judged its
stretch corners against the *looser* nominal bound, and a point that misses
the stretch target was recorded PASS -- a failure mode that is invisible in
the record, because a loose check that passes looks exactly like a tight
check that passes.

The bug class is "a bound silently weaker than the one the record appears to
claim", so every test here pins an *observable* discrimination: the same
measured value must be judged differently at a stretch point than at a
nominal one, and the failure must name which bound it was judged against.
``test_recorded_6v_sink_currents_now_fail_the_stretch_target`` is the
regression proper -- it replays two real measurements from the committed
record ``sim/output-stage-drive/records/20260812-064304-03699ea.md`` that
were recorded PASS under the old single-bound behavior and must now fail.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR))

from harness import report, testbench as tb_mod  # noqa: E402
from harness.corners import CORNERS, PvtPoint, Rail  # noqa: E402
from harness.runner import PointResult  # noqa: E402

#: The rail set the tests exercise: this repo's 5 V drive rail carrying
#: spec §3's 6 V stretch target as its opt-in ``extra_v`` point.
VDRV = Rail("vdrv", 5.0, 0.10, extra_v=(6.0,))
#: A second rail with no stretch point of its own, to prove a stretch bound
#: keys off ``extra_v`` and not merely off "some rail moved".
VLOGIC = Rail("vlogic", 3.3, 0.10)


def point(vdrv_v: float, temp_c: float = 125.0, corner: str = "ss") -> PvtPoint:
    return PvtPoint(corner=CORNERS[corner], temp_c=temp_c, supplies={"vdrv": vdrv_v})


def result(vdrv_v: float, measurements: dict, **kwargs) -> PointResult:
    return PointResult(point=point(vdrv_v, **kwargs), status="ok", measurements=measurements)


class IsStretchPointTests(unittest.TestCase):
    """Which grid points count as stretch points at all."""

    def test_extra_v_point_is_a_stretch_point(self):
        self.assertTrue(report.is_stretch_point(point(6.0), (VDRV,)))

    def test_nominal_and_tolerance_points_are_not(self):
        for volts in (4.5, 5.0, 5.5):
            with self.subTest(vdrv=volts):
                self.assertFalse(report.is_stretch_point(point(volts), (VDRV,)))

    def test_rail_without_extra_v_never_yields_a_stretch_point(self):
        # Same 6 V reading, but no rail declares 6 V as a stretch target:
        # nothing about the *value* makes a point a stretch point, only the
        # manifest's own opt-in extra_v.
        self.assertFalse(report.is_stretch_point(point(6.0), (Rail("vdrv", 5.0, 0.10),)))

    def test_unrelated_rail_is_ignored(self):
        pvt = PvtPoint(corner=CORNERS["tt"], temp_c=27.0, supplies={"vlogic": 3.3})
        self.assertFalse(report.is_stretch_point(pvt, (VDRV, VLOGIC)))

    def test_float_round_tripping_still_matches(self):
        # extra_v survives json -> float -> round(..., 6); the match must not
        # hinge on exact binary equality.
        self.assertTrue(report.is_stretch_point(point(round(6.0 * (1.0), 6)), (VDRV,)))


class NominalOnlyChecksTests(unittest.TestCase):
    """A check with no ``stretch`` key must behave exactly as it always did."""

    CHECKS = {"ipeak_sink_a": {"min": 0.5}}

    def test_passes_everywhere_when_above_the_nominal_bound(self):
        results = [result(v, {"ipeak_sink_a": 0.88}) for v in (4.5, 5.0, 5.5, 6.0)]
        failures = report.evaluate_checks(self.CHECKS, results, {}, (VDRV,))
        self.assertEqual(failures, [])

    def test_fails_at_a_stretch_point_too_when_below_the_nominal_bound(self):
        failures = report.evaluate_checks(
            self.CHECKS, [result(6.0, {"ipeak_sink_a": 0.4})], {}, (VDRV,)
        )
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["bound"], "nominal")
        self.assertEqual(failures[0]["limit"], 0.5)

    def test_measurement_absent_from_a_point_is_skipped(self):
        failures = report.evaluate_checks(self.CHECKS, [result(6.0, {})], {}, (VDRV,))
        self.assertEqual(failures, [])

    def test_non_ok_point_is_skipped(self):
        errored = PointResult(point=point(6.0), status="error", measurements={"ipeak_sink_a": 0.0})
        self.assertEqual(report.evaluate_checks(self.CHECKS, [errored], {}, (VDRV,)), [])


class StretchOverrideTests(unittest.TestCase):
    """The corner-scoped override: stricter bound at the stretch point only."""

    #: spec §3's peak-current row, as a testbench now states it.
    CURRENT = {"ipeak_sink_a": {"min": 0.5, "stretch": {"min": 1.0}}}
    #: spec §3's propagation-delay row.
    DELAY = {"tpdlh_s": {"max": 50e-9, "stretch": {"max": 25e-9}}}

    def test_same_value_passes_nominal_and_fails_stretch(self):
        """The discrimination this whole feature exists for."""
        value = {"ipeak_sink_a": 0.88}  # >= 0.5 A nominal, < 1 A stretch
        nominal_points = [result(v, value) for v in (4.5, 5.0, 5.5)]
        self.assertEqual(report.evaluate_checks(self.CURRENT, nominal_points, {}, (VDRV,)), [])

        failures = report.evaluate_checks(self.CURRENT, [result(6.0, value)], {}, (VDRV,))
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["measurement"], "ipeak_sink_a")
        self.assertEqual(failures[0]["kind"], "min")
        self.assertEqual(failures[0]["bound"], "stretch")
        self.assertEqual(failures[0]["limit"], 1.0)
        self.assertEqual(failures[0]["value"], 0.88)
        self.assertEqual(failures[0]["at"], "ss_125c_vdrv6p00v")

    def test_stretch_point_meeting_the_stretch_bound_passes(self):
        failures = report.evaluate_checks(
            self.CURRENT, [result(6.0, {"ipeak_sink_a": 1.24})], {}, (VDRV,)
        )
        self.assertEqual(failures, [])

    def test_stretch_point_below_both_bounds_reports_the_stretch_limit(self):
        # Not two failures for one measurement at one point: the stretch bound
        # replaces the nominal one there, it does not stack with it.
        failures = report.evaluate_checks(
            self.CURRENT, [result(6.0, {"ipeak_sink_a": 0.2})], {}, (VDRV,)
        )
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["limit"], 1.0)

    def test_max_side_override(self):
        value = {"tpdlh_s": 30e-9}  # < 50 ns nominal, > 25 ns stretch
        self.assertEqual(report.evaluate_checks(self.DELAY, [result(5.0, value)], {}, (VDRV,)), [])
        failures = report.evaluate_checks(self.DELAY, [result(6.0, value)], {}, (VDRV,))
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["kind"], "max")
        self.assertEqual(failures[0]["bound"], "stretch")
        self.assertEqual(failures[0]["limit"], 25e-9)

    def test_omitted_side_falls_back_to_the_nominal_bound(self):
        checks = {"vout_max_v": {"min": 0.0, "max": 6.6, "stretch": {"min": 5.4}}}
        # At the stretch point the tightened min applies and the nominal max
        # is still enforced (it was not repeated in the override).
        failures = report.evaluate_checks(
            checks, [result(6.0, {"vout_max_v": 7.0})], {}, (VDRV,)
        )
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["kind"], "max")
        self.assertEqual(failures[0]["limit"], 6.6)

        failures = report.evaluate_checks(
            checks, [result(6.0, {"vout_max_v": 5.0})], {}, (VDRV,)
        )
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["kind"], "min")
        self.assertEqual(failures[0]["limit"], 5.4)

    def test_stretch_only_bound_leaves_nominal_points_unchecked(self):
        checks = {"ipeak_sink_a": {"stretch": {"min": 1.0}}}
        self.assertEqual(
            report.evaluate_checks(checks, [result(5.0, {"ipeak_sink_a": 0.1})], {}, (VDRV,)), []
        )
        self.assertEqual(
            len(report.evaluate_checks(checks, [result(6.0, {"ipeak_sink_a": 0.1})], {}, (VDRV,))),
            1,
        )

    def test_grid_spread_checks_are_unaffected(self):
        checks = {"ipeak_sink_a": {"min": 0.5, "stretch": {"min": 1.0}, "max_spread_pct": 10.0}}
        summary = {"ipeak_sink_a": {"n": 2, "spread_pct": 42.0}}
        failures = report.evaluate_checks(
            checks, [result(5.0, {"ipeak_sink_a": 1.5})], summary, (VDRV,)
        )
        self.assertEqual([f["kind"] for f in failures], ["max_spread_pct"])
        self.assertEqual(failures[0]["at"], "grid")

    def test_rails_argument_is_required(self):
        # Defaulting it would make every point look non-stretch, which is the
        # silent-loose-bound bug this feature closes. Keep it un-defaultable.
        with self.assertRaises(TypeError):
            report.evaluate_checks(self.CURRENT, [], {})  # type: ignore[call-arg]


class RecordedDataRegressionTests(unittest.TestCase):
    """Real measurements from a committed record, re-judged.

    ``sim/output-stage-drive/records/20260812-064304-03699ea.md`` recorded
    every point PASS. Two of its 6 V stretch points read below spec §3's 1 A
    stretch sink-current target and were passed by the 0.5 A nominal bound.
    """

    #: corner-id -> measured ipeak_sink_a, read off that record.
    RECORDED_6V_SINK = {
        ("ss", 125.0): 0.875334,
        ("sf", 125.0): 0.935921,
        ("tt", 27.0): 1.24179,
        ("ff", -40.0): 1.63609,
    }

    def setUp(self):
        self.tb = tb_mod.load(REPO_ROOT / "sim" / "output-stage-drive")

    def test_manifest_states_both_spec_tiers(self):
        checks = self.tb.checks
        for name in ("ipeak_source_a", "ipeak_sink_a"):
            self.assertEqual(checks[name]["min"], 0.5, name)
            self.assertEqual(checks[name]["stretch"]["min"], 1.0, name)
        for name in ("tpdlh_s", "tpdhl_s"):
            self.assertEqual(checks[name]["max"], 50e-9, name)
            self.assertEqual(checks[name]["stretch"]["max"], 25e-9, name)
        # spec §3's Rise/fall row has no stretch target ("—"), so trise/tfall
        # must NOT carry an invented one -- the nominal 50 ns bound applies
        # at the stretch corner too.
        for name in ("trise_s", "tfall_s"):
            self.assertEqual(checks[name]["max"], 50e-9, name)
            self.assertNotIn("stretch", checks[name], name)

    def test_recorded_6v_sink_currents_now_fail_the_stretch_target(self):
        results = [
            result(6.0, {"ipeak_sink_a": value}, temp_c=temp, corner=corner)
            for (corner, temp), value in self.RECORDED_6V_SINK.items()
        ]
        failures = report.evaluate_checks(self.tb.checks, results, {}, self.tb.rails)
        failed_at = {f["at"] for f in failures if f["measurement"] == "ipeak_sink_a"}
        self.assertEqual(failed_at, {"ss_125c_vdrv6p00v", "sf_125c_vdrv6p00v"})
        for failure in failures:
            self.assertEqual(failure["bound"], "stretch")
            self.assertEqual(failure["limit"], 1.0)

    def test_the_same_readings_pass_the_nominal_bound_at_a_non_stretch_point(self):
        # The old behavior, now confined to where it belongs: 0.875 A is a
        # legitimate PASS at 5.0 V and only at 5.0 V.
        results = [
            result(5.0, {"ipeak_sink_a": value}, temp_c=temp, corner=corner)
            for (corner, temp), value in self.RECORDED_6V_SINK.items()
        ]
        self.assertEqual(report.evaluate_checks(self.tb.checks, results, {}, self.tb.rails), [])


class ManifestValidationTests(unittest.TestCase):
    """A stretch bound that could never fire is a load error, not a no-op."""

    BASE = {
        "name": "unit-test",
        "netlist": "tb.spice",
        "rails": {"vdrv": {"nominal_v": 5.0, "tolerance": 0.1, "extra_v": [6.0]}},
        "stretch": True,
        "measure": {"ipeak_sink_a": "-minimum(i(vimeas))"},
        "checks": {"ipeak_sink_a": {"min": 0.5, "stretch": {"min": 1.0}}},
    }

    def load(self, **overrides):
        manifest = dict(self.BASE)
        manifest.update(overrides)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "tb.spice").write_text("* fragment\nR1 a 0 1k\n")
            (directory / "tb.json").write_text(json.dumps(manifest))
            return tb_mod.load(directory)

    def test_valid_manifest_loads(self):
        tb = self.load()
        self.assertEqual(tb.checks["ipeak_sink_a"]["stretch"], {"min": 1.0})

    def test_stretch_bound_without_an_opted_in_stretch_grid_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.load(stretch=False)
        self.assertIn("never runs a stretch point", str(caught.exception))

    def test_stretch_bound_without_a_rail_extra_v_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.load(rails={"vdrv": {"nominal_v": 5.0, "tolerance": 0.1}})
        self.assertIn("extra_v", str(caught.exception))

    def test_misspelled_check_key_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.load(checks={"ipeak_sink_a": {"minimum": 0.5}})
        self.assertIn("unknown key", str(caught.exception))

    def test_misspelled_stretch_key_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.load(checks={"ipeak_sink_a": {"min": 0.5, "stretch": {"minimum": 1.0}}})
        self.assertIn("unknown key", str(caught.exception))

    def test_spread_check_may_not_be_scoped_to_the_stretch_corner(self):
        with self.assertRaises(ValueError):
            self.load(
                checks={"ipeak_sink_a": {"min": 0.5, "stretch": {"max_spread_pct": 1.0}}}
            )

    def test_empty_or_non_object_stretch_is_rejected(self):
        for bad in ({}, 1.0, "1.0", [1.0]):
            with self.subTest(stretch=bad):
                with self.assertRaises(ValueError):
                    self.load(checks={"ipeak_sink_a": {"min": 0.5, "stretch": bad}})

    def test_every_committed_manifest_still_loads(self):
        for directory in tb_mod.discover(REPO_ROOT / "sim"):
            with self.subTest(experiment=directory.name):
                tb_mod.load(directory)


class RecordRenderingTests(unittest.TestCase):
    """The record must say which bound each point was judged against."""

    def record_fragment(self, value: float, vdrv_v: float) -> str:
        checks = {"ipeak_sink_a": {"min": 0.5, "stretch": {"min": 1.0}}}
        results = [result(vdrv_v, {"ipeak_sink_a": value})]
        summary = report.summarize(results, ["ipeak_sink_a"])
        failures = report.evaluate_checks(checks, results, summary, (VDRV,))
        record = {
            "measure": {"ipeak_sink_a": "-minimum(i(vimeas))"},
            "checks": {"spec": checks, "passed": not failures, "failures": failures},
            "summary": summary,
            "points": [r.as_dict() for r in results],
            "status": "fail" if failures else "pass",
        }
        return "\n".join(report._result_lines(record))

    def test_stretch_failure_is_tagged_and_limits_column_shows_both_tiers(self):
        text = self.record_fragment(0.88, 6.0)
        self.assertIn("FAIL", text)
        self.assertIn("min [stretch]=1", text)
        self.assertIn("min=0.5, stretch min=1", text)

    def test_same_value_renders_pass_at_a_nominal_point(self):
        text = self.record_fragment(0.88, 5.0)
        self.assertIn("| PASS |", text)
        self.assertNotIn("FAIL", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
