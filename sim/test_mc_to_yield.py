"""Pins sim/mc_to_yield.py: which CSV rows become `klt yield` samples (issue #368)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import mc_to_yield as m

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


if __name__ == "__main__":
    unittest.main()
