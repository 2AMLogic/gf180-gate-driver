"""Pins sim/mc_to_yield.py: which CSV rows become `klt yield` samples (issue #368).

Also pins that `verification/signoff/derive_ronw_bound.py` -- the fourth
campaign's emitter, whose bound is per-PVT control-relative -- selects its rows
through the same converter rather than a second copy of the rule (issue #427).
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import mc_to_yield as m


def _load_derive():
    """Import the Ron*W emitter by path; it is not on `sys.path`."""
    path = Path(__file__).resolve().parent.parent / "verification/signoff/derive_ronw_bound.py"
    spec = importlib.util.spec_from_file_location("derive_ronw_bound", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


derive = _load_derive()

HEADER = "sample,seed,sw_stat_mismatch,status,n1_max_v,n2_max_v,indrv_max_v\n"
ROWS = [
    "baseline,,unset (plain harness deck),ok,6.1,6.2,6.0\n",
    "0,1,0,ok,6.1,6.2,6.0\n",
    "0,2,0,ok,6.1,6.2,6.0\n",
    "0,10,1,ok,6.10,6.20,6.001\n",
    "1,11,1,failed,,,\n",
    "2,12,1,ok,6.30,6.20,6.002\n",
]


class ConvertTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, name: str, rows: list[str] = ROWS) -> Path:
        path = self.dir / name
        path.write_text(HEADER + "".join(rows))
        return path

    def test_baseline_and_control_rows_are_excluded(self):
        samples, seeds = m.read_draws(self.write("samples-p.csv"), ["indrv_max_v"])
        self.assertEqual(seeds, [10, 11, 12])
        self.assertEqual(len(samples), 3)

    def test_non_converged_draw_is_a_null_sample_not_a_drop(self):
        samples, _ = m.read_draws(self.write("samples-p.csv"), ["indrv_max_v"])
        self.assertEqual(samples, [6.001, None, 6.002])

    def test_multi_column_measurement_takes_the_worst_node(self):
        samples, _ = m.read_draws(self.write("samples-p.csv"), ["n1_max_v", "n2_max_v"])
        self.assertEqual(samples, [6.20, None, 6.30])

    def test_each_pvt_point_is_its_own_measurement_with_seed_and_n(self):
        self.write("samples-ss_27c.csv")
        self.write("samples-ff_27c.csv")
        doc = m.build_sample_set("gate-driver-indrv-mismatch", self.dir)
        names = [x["name"] for x in doc["measurements"]]
        self.assertEqual(names, ["indrv_max_v@ff_27c", "indrv_max_v@ss_27c"])
        first = doc["measurements"][0]
        self.assertEqual(first["limits"], {"max": 6.01})
        self.assertEqual(first["seeds"], {"first": 10, "last": 12, "n": 3})

    def test_missing_column_and_unknown_campaign_are_errors(self):
        path = self.dir / "samples-p.csv"
        path.write_text("sample,seed,sw_stat_mismatch,status\n0,1,1,ok\n")
        with self.assertRaises(m.ConversionError):
            m.read_draws(path, ["indrv_max_v"])
        with self.assertRaises(m.ConversionError):
            m.build_sample_set("nope", self.dir)

    def test_file_with_no_mismatch_draws_is_an_error(self):
        path = self.write("samples-p.csv", ROWS[:3])
        with self.assertRaises(m.ConversionError):
            m.read_draws(path, ["indrv_max_v"])

    def test_control_is_the_baseline_row_and_is_never_a_sample(self):
        path = self.write("samples-p.csv")
        self.assertEqual(m.read_control(path, ["indrv_max_v"]), 6.0)
        self.assertEqual(m.read_control(path, ["n1_max_v", "n2_max_v"]), 6.2)
        samples, _ = m.read_draws(path, ["indrv_max_v"])
        self.assertNotIn(6.0, samples)

    def test_missing_baseline_row_is_an_error(self):
        path = self.write("samples-p.csv", ROWS[1:])
        with self.assertRaises(m.ConversionError):
            m.read_control(path, ["indrv_max_v"])


RONW_HEADER = "sample,seed,sw_stat_mismatch,status,ronw_n06_3.6\n"
#: Ron*W-shaped: a `baseline` control whose sw_stat_mismatch cell is prose, two
#: zero-sigma control rows, then three draws -- one of them non-converged.
RONW_ROWS = [
    "baseline,,unset (plain deck),ok,4.0000\n",
    "0,20340821,0,ok,4.0000\n",
    "0,25340821,0,ok,4.0000\n",
    "1,20340822,1,ok,4.0100\n",
    "2,20340823,1,failed,\n",
    "3,20340824,1,ok,4.0300\n",
]


class RonwEmitterTest(unittest.TestCase):
    """Issue #427: the Ron*W path must share mc_to_yield's row selection."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        (self.dir / "samples-ss_125c.csv").write_text(RONW_HEADER + "".join(RONW_ROWS))

    def rows(self):
        return derive.build_rows(self.dir)

    def test_non_converged_draw_is_a_null_sample_not_a_shrunken_population(self):
        (row,) = self.rows()
        self.assertEqual(row["samples"], [4.01, None, 4.03])
        self.assertEqual(row["n"], 3)  # the population keeps all three draws
        self.assertEqual(row["n_converged"], 2)

    def test_null_sample_survives_into_the_emitted_document(self):
        doc = derive.sample_set(self.rows())
        self.assertEqual(doc["schema"], m.SCHEMA)
        self.assertEqual(doc["campaign"], derive.CAMPAIGN)
        (meas,) = doc["measurements"]
        self.assertEqual(meas["name"], "ronw_n06_3.6@ss_125c")
        self.assertIn("null", json.dumps(meas["samples"]))

    def test_control_and_limit_come_from_the_baseline_row(self):
        (row,) = self.rows()
        self.assertEqual(row["control"], 4.0)
        self.assertAlmostEqual(row["limit"], 4.0 + derive.allowed_excursion())
        self.assertAlmostEqual(row["limit"], 4.13432)

    def test_table_statistics_skip_the_null_without_counting_it_a_failure(self):
        (row,) = self.rows()
        self.assertAlmostEqual(row["excursion"], 0.03)  # max converged - control
        self.assertEqual(row["fails"], 0)  # a non-converged draw is errored, not a fail
        self.assertAlmostEqual(row["sigma"], 0.014142135623730935, places=12)

    def test_a_draw_over_the_limit_is_a_failure(self):
        over = RONW_ROWS[:-1] + ["3,20340824,1,ok,4.2000\n"]
        (self.dir / "samples-ss_125c.csv").write_text(RONW_HEADER + "".join(over))
        (row,) = self.rows()
        self.assertEqual(row["fails"], 1)

    def test_all_draws_non_converged_is_an_error_not_an_empty_population(self):
        dead = RONW_ROWS[:3] + ["1,20340822,1,failed,\n", "2,20340823,1,failed,\n"]
        (self.dir / "samples-ss_125c.csv").write_text(RONW_HEADER + "".join(dead))
        with self.assertRaises(m.ConversionError):
            self.rows()

    def test_emitter_reuses_the_converter_module_rather_than_a_second_copy(self):
        self.assertIs(derive.mc, m)


if __name__ == "__main__":
    unittest.main()
