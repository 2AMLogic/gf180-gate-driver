#!/usr/bin/env python3
"""Regression tests for ``sim/harness/campaign.py``.

    python3 sim/test_harness_campaign.py    # or: python3 -m unittest ...

Standard-library ``unittest`` only, and deliberately **PDK-free and
ngspice-free** (the convention ``sim/test_harness_checks.py`` and
``sim/test_harness_runner.py`` set): the campaign driver's only contact with
ngspice is through ``runner.run_point`` / ``runner.run_samples``, which these
tests stub, so the suite runs on a bare runner with nothing but ``python3``.

Why this file exists (issue #258)
---------------------------------

Three mismatch campaigns (``sim/gate-driver-indrv-mismatch``,
``sim/level-shifter-inb-mismatch``, ``sim/output-stage-taper-mismatch``) each
carried their own byte-identical copy of the campaign driver, the
``PointOutcome`` accessors and the evidence writers; ``harness/campaign.py``
is the single shared implementation they now call.

Those writers emit **committed evidence** -- ``sim/`` is append-only per
CLAUDE.md -- so the thing worth pinning is not "it runs" but the exact bytes:
a silently reformatted log banner or CSV sidecar would land in the evidence
tree looking like a new measurement rather than a formatting change. Every
assertion here is therefore on literal output, and on the leg structure
(1 plain baseline + 2 differently-seeded zero-sigma controls + N derived-seed
draws) that decision record 0017 ratifies.
"""

from __future__ import annotations

import datetime as _dt
import sys
import tempfile
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM_DIR))

from harness import campaign  # noqa: E402
from harness import runner as harness_runner  # noqa: E402
from harness.corners import CORNERS, PvtPoint, Rail  # noqa: E402
from harness.montecarlo import CONTROL_SAMPLE, MismatchSample, sample_seed  # noqa: E402
from harness.pdk import Pdk  # noqa: E402
from harness.runner import PointResult  # noqa: E402
from harness.testbench import Testbench  # noqa: E402

_TB = Testbench(
    directory=SIM_DIR / "fake-experiment" / "testbench",
    name="fake-experiment",
    netlist=SIM_DIR / "fake-experiment" / "testbench" / "fake_tb.spice",
    rails=(Rail("vdrv", 5.0, 0.10),),
    analyses=("tran 10p 100n",),
    measure={"vout": "v(vout)"},
)

_PDK = Pdk(path=Path("/nonexistent/gf180mcuD"), variant="gf180mcuD", source="test")

_POINT = PvtPoint(corner=CORNERS["tt"], temp_c=27.0, supplies={"vdrv": 5.0})

_STAMP = _dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc)

_BASE_SEED = 20260101


def _result(point, value, status="ok", output="raw\n") -> PointResult:
    return PointResult(
        point=point,
        status=status,
        measurements={"vout": value} if status == "ok" else {},
        seconds=0.0,
        message="" if status == "ok" else "aborted",
        output=output,
    )


def _outcome(values, control=5.0, baseline=5.0, statuses=None) -> campaign.PointOutcome:
    """A `PointOutcome` over synthetic draws, without running anything."""
    statuses = statuses or ["ok"] * len(values)
    controls = [
        (MismatchSample(sample=CONTROL_SAMPLE, seed=1), _result(_POINT, control)),
        (MismatchSample(sample=CONTROL_SAMPLE, seed=2), _result(_POINT, control)),
    ]
    samples = [
        (MismatchSample(sample=i + 1, seed=100 + i), _result(_POINT, v, status))
        for i, (v, status) in enumerate(zip(values, statuses))
    ]
    return campaign.PointOutcome(_POINT, _result(_POINT, baseline), controls, samples)


class StubRunner:
    """Replaces ``runner.run_point``/``run_samples`` for the driver tests."""

    def __init__(self):
        self.point_calls = []
        self.sample_calls = []

    def run_point(self, tb, pdk, point, workdir, mc=None, keep_output=False, **kwargs):
        self.point_calls.append((point, mc, workdir, keep_output))
        return _result(point, 5.0 + 0.001 * len(self.point_calls))

    def run_samples(self, tb, pdk, samples, workdir, jobs=1, on_result=None, **kwargs):
        self.sample_calls.append((samples, jobs))
        results = []
        for index, (point, mc) in enumerate(samples):
            result = _result(point, 5.0 + 0.01 * index)
            results.append(result)
            if on_result is not None:
                on_result(result)
        return results


class RunPointCampaignTests(unittest.TestCase):
    """The ratified three-leg negative control + derived-seed draw structure."""

    def setUp(self):
        self.stub = StubRunner()
        self._saved = (harness_runner.run_point, harness_runner.run_samples)
        harness_runner.run_point = self.stub.run_point
        harness_runner.run_samples = self.stub.run_samples
        self.addCleanup(self._restore)

    def _restore(self):
        harness_runner.run_point, harness_runner.run_samples = self._saved

    def _run(self, index=3, n_samples=4, outcome_cls=campaign.PointOutcome):
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            outcome = campaign.run_point_campaign(
                _TB, _PDK, _POINT, index, n_samples, Path(tmp), 1, seen.append,
                base_seed=_BASE_SEED,
                outcome_cls=outcome_cls,
            )
        return outcome, seen

    def test_one_baseline_and_two_controls_run_as_single_points(self):
        self._run()
        # Leg 1 is the plain deck (mc=None); legs 2 and 3 are the zero-sigma
        # controls -- all three go through run_point, never run_samples.
        self.assertEqual(len(self.stub.point_calls), 3)
        self.assertIsNone(self.stub.point_calls[0][1])
        self.assertEqual(
            [call[1].sample for call in self.stub.point_calls[1:]],
            [CONTROL_SAMPLE, CONTROL_SAMPLE],
        )

    def test_the_two_controls_carry_different_seeds(self):
        # Two controls at the *same* seed would only show repeatability;
        # decision record 0017 wants determinism, so the seeds must differ.
        self._run()
        seeds = [call[1].seed for call in self.stub.point_calls[1:]]
        expected = sample_seed(_BASE_SEED, 3, CONTROL_SAMPLE)
        self.assertEqual(seeds, [expected, expected + campaign.CONTROL_SEED_OFFSET])

    def test_every_run_keeps_its_raw_output(self):
        # The campaign writes only the cited samples' logs, so it needs the
        # raw text back on the result rather than on disk per draw.
        self._run()
        self.assertTrue(all(call[3] for call in self.stub.point_calls))

    def test_draw_seeds_are_derived_from_base_seed_and_point_index(self):
        self._run(index=3, n_samples=4)
        (samples, _jobs) = self.stub.sample_calls[0]
        self.assertEqual([mc.sample for _, mc in samples], [1, 2, 3, 4])
        self.assertEqual(
            [mc.seed for _, mc in samples],
            [sample_seed(_BASE_SEED, 3, s) for s in (1, 2, 3, 4)],
        )

    def test_progress_is_called_once_per_run(self):
        _outcome_obj, seen = self._run(n_samples=4)
        self.assertEqual(len(seen), 3 + 4)

    def test_outcome_cls_is_honored(self):
        class Custom(campaign.PointOutcome):
            pass

        outcome, _seen = self._run(outcome_cls=Custom)
        self.assertIsInstance(outcome, Custom)


class RunDevicePointCampaignTests(unittest.TestCase):
    """The device-level driver (issue #276): the identical three-leg
    negative-control + derived-seed draw skeleton as `RunPointCampaignTests`
    above, but parameterized over a "run one sample" callable instead of
    `runner.run_point`/`run_samples` -- the shape
    `sim/low-side-power-switch-ronw-mismatch/run_ronw_mismatch.py` now
    reuses instead of carrying its own copy."""

    @staticmethod
    def _stub_run_sample(mc):
        """Deterministic in `mc` alone (no shared mutable state), so this is
        safe to call concurrently from the `jobs > 1` thread-pool path."""
        seed = 0 if mc is None else mc.seed
        return _result(_POINT, 5.0 + seed * 1e-6)

    def _run(self, index=3, n_samples=4, jobs=1, outcome_cls=campaign.PointOutcome):
        seen = []
        outcome = campaign.run_device_point_campaign(
            _POINT, index, n_samples, jobs, seen.append, self._stub_run_sample,
            base_seed=_BASE_SEED,
            outcome_cls=outcome_cls,
        )
        return outcome, seen

    def test_the_two_controls_carry_different_seeds(self):
        # Two controls at the *same* seed would only show repeatability;
        # decision record 0017 wants determinism, so the seeds must differ.
        outcome, _seen = self._run(index=3)
        seeds = [mc.seed for mc, _r in outcome.controls]
        expected = sample_seed(_BASE_SEED, 3, CONTROL_SAMPLE)
        self.assertEqual(seeds, [expected, expected + campaign.CONTROL_SEED_OFFSET])

    def test_draw_seeds_are_derived_from_base_seed_and_point_index(self):
        outcome, _seen = self._run(index=3, n_samples=4)
        self.assertEqual([mc.sample for mc, _r in outcome.samples], [1, 2, 3, 4])
        self.assertEqual(
            [mc.seed for mc, _r in outcome.samples],
            [sample_seed(_BASE_SEED, 3, s) for s in (1, 2, 3, 4)],
        )

    def test_baseline_is_run_with_mc_none(self):
        outcome, _seen = self._run()
        self.assertEqual(outcome.baseline.measurements["vout"], 5.0)

    def test_progress_is_called_once_per_run(self):
        _outcome, seen = self._run(n_samples=4)
        self.assertEqual(len(seen), 3 + 4)

    def test_outcome_cls_is_honored(self):
        class Custom(campaign.PointOutcome):
            pass

        outcome, _seen = self._run(outcome_cls=Custom)
        self.assertIsInstance(outcome, Custom)

    def test_parallel_draws_preserve_input_order(self):
        # ThreadPoolExecutor.map returns results in the order the iterable
        # was given, not completion order -- a Monte Carlo record's seed
        # table must stay deterministic regardless of jobs > 1 scheduling.
        outcome, _seen = self._run(index=1, n_samples=6, jobs=3)
        expected_seeds = [sample_seed(_BASE_SEED, 1, s) for s in range(1, 7)]
        self.assertEqual([mc.seed for mc, _r in outcome.samples], expected_seeds)
        self.assertEqual(
            [round(r.measurements["vout"], 6) for _mc, r in outcome.samples],
            [round(5.0 + seed * 1e-6, 6) for seed in expected_seeds],
        )


class PointOutcomeTests(unittest.TestCase):
    def test_non_converged_draws_are_excluded_from_ok(self):
        outcome = _outcome([5.1, 5.2, 5.3], statuses=["ok", "failed", "ok"])
        self.assertEqual(len(outcome.ok), 2)
        self.assertEqual(outcome.values("vout"), [5.1, 5.3])

    def test_worst_is_the_highest_converged_draw(self):
        outcome = _outcome([5.1, 5.9, 5.3])
        mc, result = outcome.worst("vout")
        self.assertEqual(result.measurements["vout"], 5.9)
        self.assertEqual(mc.sample, 2)

    def test_worst_is_none_when_nothing_converged(self):
        outcome = _outcome([5.1], statuses=["failed"])
        self.assertIsNone(outcome.worst("vout"))

    def test_controls_agree_and_match_baseline(self):
        outcome = _outcome([5.1], control=5.0, baseline=5.0)
        self.assertTrue(outcome.controls_agree)
        self.assertTrue(outcome.control_matches_baseline)

    def test_a_baseline_that_differs_from_the_control_is_reported(self):
        # The strong negative control: a mismatch-off deck that does not
        # reproduce the plain deck must not read as PASS.
        outcome = _outcome([5.1], control=5.0, baseline=5.000001)
        self.assertTrue(outcome.controls_agree)
        self.assertFalse(outcome.control_matches_baseline)

    def test_an_empty_measurement_set_never_counts_as_agreement(self):
        outcome = _outcome([5.1], statuses=["ok"])
        outcome.controls[0][1].measurements.clear()
        outcome.controls[1][1].measurements.clear()
        self.assertFalse(outcome.controls_agree)


class PointSigmaSummaryTests(unittest.TestCase):
    def test_reports_the_min_and_max_per_point_sigma_in_microvolts(self):
        tight = _outcome([5.000000, 5.000001, 5.000002])
        loose = _outcome([5.00000, 5.00001, 5.00002])
        summary = campaign.point_sigma_summary(
            [tight, loose], lambda o: o.values("vout")
        )
        self.assertEqual(summary, "1–10 µV")

    def test_a_single_draw_per_point_has_no_sigma(self):
        summary = campaign.point_sigma_summary(
            [_outcome([5.0])], lambda o: o.values("vout")
        )
        self.assertEqual(summary, "n/a")

    def test_values_extractor_is_honored(self):
        outcome = _outcome([5.0, 6.0])
        self.assertEqual(
            campaign.point_sigma_summary([outcome], lambda o: []), "n/a"
        )


class FormatterTests(unittest.TestCase):
    """`fmt`/`mv` set the literal text of every recorded record table."""

    def test_fmt_is_six_significant_figures_by_default(self):
        self.assertEqual(campaign.fmt(6.002661234), "6.00266")

    def test_fmt_honors_a_wider_digit_count(self):
        self.assertEqual(campaign.fmt(6.002661234, 10), "6.002661234")

    def test_fmt_switches_to_exponent_form_for_small_magnitudes(self):
        self.assertEqual(campaign.fmt(1.2345e-06), "1.234500e-06")

    def test_fmt_reports_a_missing_value_as_na(self):
        self.assertEqual(campaign.fmt(None), "n/a")

    def test_mv_is_a_signed_millivolt_string_to_three_decimals(self):
        self.assertEqual(campaign.mv(0.0355), "+35.500")
        self.assertEqual(campaign.mv(-0.00266), "-2.660")
        self.assertEqual(campaign.mv(None), "n/a")


class LogHeaderTests(unittest.TestCase):
    """The provenance banner prepended to every committed corner log."""

    def _baseline(self, **kwargs) -> str:
        return campaign.baseline_log_header(
            _PDK, _TB, _POINT, "20260102-030405-abcdef0", _STAMP, "ngspice-46",
            source_experiment="fake-experiment", **kwargs,
        )

    def test_baseline_header_is_exact(self):
        self.assertEqual(
            self._baseline(),
            "* ====================================================================\n"
            "* record-id : 20260102-030405-abcdef0\n"
            "* testbench : sim/fake-experiment/testbench/fake_tb.spice\n"
            f"* dut       : {_TB.dut_path} ({_TB.dut_provenance_class})\n"
            "* corner    : tt_27c_vdrv5p00v\n"
            "* mismatch  : none -- plain harness deck (runner.compose_deck(mc=None)),\n"
            "*             byte-identical to what sim/run_corners.py generates.\n"
            "* pdk       : gf180mcuD (/nonexistent/gf180mcuD)\n"
            "* ngspice   : ngspice-46\n"
            "* run (UTC) : 2026-01-02T03:04:05Z\n"
            "* ====================================================================\n",
        )

    def test_extra_note_lines_are_indented_into_the_mismatch_block(self):
        header = self._baseline(extra_note_lines=("first note", "second note"))
        lines = header.splitlines()
        start = lines.index(
            "*             byte-identical to what sim/run_corners.py generates."
        )
        self.assertEqual(
            lines[start + 1:start + 3],
            ["*             first note", "*             second note"],
        )
        # ... and land before the pdk line, not after it.
        self.assertTrue(lines[start + 3].startswith("* pdk"))

    def test_draw_header_records_the_switch_the_sample_and_the_seed(self):
        header = campaign.log_header(
            _PDK, _TB, MismatchSample(sample=7, seed=12345), _POINT,
            "20260102-030405-abcdef0", _STAMP, "ngspice-46",
            source_experiment="fake-experiment",
        )
        self.assertIn(
            "* mismatch  : sw_stat_mismatch=1 (sample 7), sw_stat_global=0\n", header
        )
        self.assertIn("* seed      : 12345\n", header)

    def test_a_control_draw_header_records_the_switch_as_off(self):
        header = campaign.log_header(
            _PDK, _TB, MismatchSample(sample=CONTROL_SAMPLE, seed=9), _POINT,
            "20260102-030405-abcdef0", _STAMP, "ngspice-46",
            source_experiment="fake-experiment",
        )
        self.assertIn(
            f"* mismatch  : sw_stat_mismatch=0 (sample {CONTROL_SAMPLE}), "
            "sw_stat_global=0\n",
            header,
        )


class EvidenceWriterTests(unittest.TestCase):
    def test_sample_csv_layout_is_exact(self):
        outcome = _outcome([5.1, 5.2], control=5.0, baseline=5.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = campaign.write_sample_csv(
                Path(tmp), "20260102-030405-abcdef0", outcome, ["vout"]
            )
            self.assertEqual(path.name, "samples-tt_27c_vdrv5p00v.csv")
            # Committed evidence: LF line endings, not csv's default CRLF.
            raw = path.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            self.assertEqual(
                raw.decode(),
                "sample,seed,sw_stat_mismatch,status,vout\n"
                "baseline,,unset (plain harness deck),ok,5.0\n"
                "0,1,0,ok,5.0\n"
                "0,2,0,ok,5.0\n"
                "1,100,1,ok,5.1\n"
                "2,101,1,ok,5.2\n",
            )

    def test_sample_csv_leaves_a_non_converged_draws_cells_empty(self):
        outcome = _outcome([5.1, 5.2], statuses=["ok", "failed"])
        with tempfile.TemporaryDirectory() as tmp:
            path = campaign.write_sample_csv(
                Path(tmp), "20260102-030405-abcdef0", outcome, ["vout"]
            )
            self.assertEqual(path.read_text().splitlines()[-1], "2,101,1,failed,")

    def test_write_log_prepends_the_header_to_the_raw_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = campaign.write_log(
                Path(tmp), "20260102-030405-abcdef0", "tt_27c_vdrv5p00v",
                "* header\n", "raw ngspice text\n",
            )
            self.assertEqual(path.name, "tt_27c_vdrv5p00v.log")
            self.assertEqual(path.parent.name, "20260102-030405-abcdef0")
            self.assertEqual(path.read_text(), "* header\nraw ngspice text\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
