#!/usr/bin/env python3
"""Regression tests for ``power_array_folded.py`` (issue #254).

    python3 layout/common/test_power_array_folded.py

Standard-library ``unittest`` only, and deliberately **PDK-free and
klt-free** -- same convention ``layout/test_gen_gate_driver_core.py``
documents for exactly the same reason: everything under test here is either
pure arithmetic (the fold split, the ``mirror_y`` point transform, the
cross-row tie geometry) or a pure verdict function over an already-captured
``klt extract``-shaped dict, so this suite runs on a bare runner (the `test`
job in ``.github/workflows/ci.yml``) with nothing but ``python3``.

Three things are pinned here:

* :func:`power_array_folded.fold_rows` -- the ``rows=1``/``rows=2``-only
  split, and every one of its refusal paths (``rows>2``, an uneven/odd
  ``fingers``) raises rather than silently drawing disjoint devices (AC2).
* :func:`power_array_folded.build_tie_shapes` -- the cross-row tie geometry,
  pinned against **hand-computed** rectangles derived from a real ``klt gen
  mos_array`` response (captured once, verified against a real ``klt``
  install + resolved gf180mcu PDK -- see the module docstring's "Verified
  against a real `klt` install" paragraph -- and transcribed here as a
  literal fixture, not re-derived by calling the function under test).
* :func:`power_array_folded.fold_connectivity_verdict` -- AC3's own
  connectivity check. Its failing directions (a broken/missing tie) cannot be
  produced from a correctly generated GDS, so they are exercised here against
  a synthetic extraction dict shaped exactly like the *real* untied fixture
  this module's own docstring describes reproducing against a real ``klt
  extract`` run: two disjoint ``(s, g, d)`` triples, honest per-row
  ``G<r>``/``S<r>``/``D<r>`` labels -- the exact shape issue #254 reports the
  pre-existing arrays shipped in, and exactly what F-018's own "no same-layer
  scheme works" conclusion let through because nothing checked it.
"""

from __future__ import annotations

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from power_array_folded import (  # noqa: E402  (path set above)
    FoldError,
    _mirror_y,
    build_tie_shapes,
    fold_connectivity_verdict,
    fold_rows,
    row_offset_y,
    row_pads,
)

#: A real ``klt gen mos_array`` response, captured against a real `klt`
#: install (0.5.0) + resolved gf180mcu PDK for
#: ``{"w_um": 2.0, "l_um": 0.6, "fingers": 4, "finger_topology": "parallel",
#: "rows": 1, "cols": 1, "dummy": 0, "topology": "array", "flavor": "nfet",
#: "gate_contact": true}`` -- transcribed verbatim (not re-derived by calling
#: any function under test) so :func:`build_tie_shapes`'s own arithmetic is
#: pinned against real generator output, the same way
#: ``test_gen_gate_driver_core.py`` pins its own expectations against
#: hand-computed values.
REAL_ROW_REPORT = {
    "cell_name": "row_unit",
    "bbox_um": {"x0": -0.25, "y0": 0.0, "x1": 5.39, "y1": 4.46},
    "ports": [
        {
            "name": "U0_S",
            "layer": {"layer": 34, "datatype": 0},
            "x_um": 0.21,
            "y_um": 0.21,
            "width_um": 0.42,
            "direction_deg": 180,
        },
        {
            "name": "U0_D",
            "layer": {"layer": 34, "datatype": 0},
            "x_um": 4.93,
            "y_um": 3.43,
            "width_um": 0.42,
            "direction_deg": 0,
        },
        {
            "name": "U0_G",
            "layer": {"layer": 34, "datatype": 0},
            "x_um": 2.57,
            "y_um": 4.25,
            "width_um": 0.42,
            "direction_deg": 90,
        },
    ],
}

#: Same shape, but the gate pad is on Poly2 (30/0) instead of Metal1 --
#: ``gate_contact: false``'s real reported layer (also captured against a
#: real `klt` run; see power_array_folded.py's docstring on why this
#: generator requires ``gate_contact=True``).
REAL_ROW_REPORT_BARE_POLY_GATE = copy.deepcopy(REAL_ROW_REPORT)
REAL_ROW_REPORT_BARE_POLY_GATE["ports"][2]["layer"] = {"layer": 30, "datatype": 0}


class FoldRowsTest(unittest.TestCase):
    def test_rows_one_passthrough(self):
        self.assertEqual(fold_rows(5, 1), [5])
        self.assertEqual(fold_rows(1, 1), [1])

    def test_rows_two_equal_split(self):
        self.assertEqual(fold_rows(8, 2), [4, 4])
        self.assertEqual(fold_rows(1300, 2), [650, 650])
        self.assertEqual(fold_rows(450, 2), [225, 225])

    def test_rows_two_odd_fingers_raises(self):
        with self.assertRaises(FoldError):
            fold_rows(7, 2)

    def test_rows_two_below_minimum_raises(self):
        with self.assertRaises(FoldError):
            fold_rows(0, 2)

    def test_rows_greater_than_two_always_raises(self):
        # AC2: rows > 2 is refused with a clear error, never silently drawn
        # as disjoint devices -- regardless of whether `fingers` would
        # otherwise divide evenly.
        for fingers in (6, 9, 100):
            with self.assertRaises(FoldError):
                fold_rows(fingers, 3)

    def test_rows_zero_raises(self):
        with self.assertRaises(FoldError):
            fold_rows(4, 0)


class MirrorYTest(unittest.TestCase):
    """Pins ``klt gen-compose``'s own ``orientation: "mirror_y"`` transform.

    ``(x, y) -> (x, -y)``, direction ``90 <-> 270``, ``0``/``180`` unchanged
    -- klayout-tools docs/cli/gen-compose.md's "Transform semantics" table.
    """

    def test_horizontal_directions_unchanged(self):
        self.assertEqual(_mirror_y(1.0, 2.0, 180), (1.0, -2.0, 180))
        self.assertEqual(_mirror_y(1.0, 2.0, 0), (1.0, -2.0, 0))

    def test_vertical_directions_swap(self):
        self.assertEqual(_mirror_y(1.0, 2.0, 90), (1.0, -2.0, 270))
        self.assertEqual(_mirror_y(1.0, 2.0, 270), (1.0, -2.0, 90))

    def test_applying_twice_returns_to_start(self):
        for direction in (0, 90, 180, 270):
            x, y, d = _mirror_y(3.0, -5.0, direction)
            self.assertEqual(_mirror_y(x, y, d), (3.0, -5.0, direction))


class RowOffsetYTest(unittest.TestCase):
    def test_offset_matches_hand_computation(self):
        # row0 occupies [0, 4.46]; row1 (mirrored) needs gap_um clear space
        # above row0's own top, then its own (mirrored) 4.46um height.
        self.assertAlmostEqual(row_offset_y(REAL_ROW_REPORT, 4.0), 4.46 + 4.0 + 4.46)
        self.assertAlmostEqual(row_offset_y(REAL_ROW_REPORT, 0.0), 4.46 + 4.46)


class RowPadsTest(unittest.TestCase):
    def test_row0_unchanged(self):
        pads = row_pads(REAL_ROW_REPORT, "none", 0.0)
        self.assertEqual(pads["s"][:3], (0.21, 0.21, 180))
        self.assertEqual(pads["d"][:3], (4.93, 3.43, 0))
        self.assertEqual(pads["g"][:3], (2.57, 4.25, 90))

    def test_row1_mirrored_and_offset(self):
        offset_y = row_offset_y(REAL_ROW_REPORT, 4.0)
        pads = row_pads(REAL_ROW_REPORT, "mirror_y", offset_y)
        # x unchanged by a Y-mirror; y negated then shifted by offset_y;
        # 90 <-> 270, 0/180 unchanged. Compared with assertAlmostEqual on the
        # y term since offset_y itself carries float rounding noise.
        for role, (x, y, d) in (("s", (0.21, 12.71, 180)), ("d", (4.93, 9.49, 0)), ("g", (2.57, 8.67, 270))):
            got_x, got_y, got_d = pads[role][:3]
            self.assertAlmostEqual(got_x, x)
            self.assertAlmostEqual(got_y, y)
            self.assertEqual(got_d, d)

    def test_rejects_unknown_orientation(self):
        with self.assertRaises(FoldError):
            row_pads(REAL_ROW_REPORT, "mirror_x", 0.0)


class BuildTieShapesTest(unittest.TestCase):
    """Pins the cross-row tie geometry against hand-computed rectangles.

    Every rectangle below is derived by hand from :data:`REAL_ROW_REPORT`'s
    own real, klt-reported pad positions -- not by calling
    :func:`build_tie_shapes` itself and trusting its own arithmetic, the same
    discipline ``test_gen_gate_driver_core.py`` documents for its own
    hand-computed expectations.
    """

    def test_shapes_match_hand_computation(self):
        shapes, row0, row1, offset_y = build_tie_shapes(
            REAL_ROW_REPORT, gap_um=4.0, trunk_margin_um=1.0
        )
        self.assertAlmostEqual(offset_y, 12.92)
        self.assertEqual(len(shapes), 7)
        for shape in shapes:
            self.assertEqual(shape["layer"], [34, 0])

        expected_rects = [
            [-1.25, 0.0, 0.21, 0.42],       # S0 stub -> left trunk
            [-1.46, 0.21, -1.04, 12.71],    # left (S) trunk column
            [-1.25, 12.5, 0.21, 12.92],     # left trunk -> S1 stub
            [4.93, 3.22, 6.39, 3.64],       # D0 stub -> right trunk
            [6.18, 3.43, 6.6, 9.49],        # right (D) trunk column
            [4.93, 9.28, 6.39, 9.7],        # right trunk -> D1 stub
            [2.36, 4.25, 2.78, 8.67],       # direct G0<->G1 tie box
        ]
        got_rects = [[round(v, 4) for v in shape["rect_um"]] for shape in shapes]
        self.assertEqual(got_rects, expected_rects)

        # row0/row1 pads returned alongside the shapes match row_pads()'s own
        # output for the same inputs (no silent second, divergent copy of the
        # placement math).
        self.assertEqual(row0["g"][:3], (2.57, 4.25, 90))
        got_x, got_y, got_d = row1["g"][:3]
        self.assertAlmostEqual(got_x, 2.57)
        self.assertAlmostEqual(got_y, 8.67)
        self.assertEqual(got_d, 270)

    def test_bare_poly_gate_raises(self):
        # gate_contact=False's real reported shape (gate on Poly2, source/
        # drain on Metal1) -- a plain metal box cannot tie a different layer,
        # so this must raise rather than silently draw a non-electrical box.
        with self.assertRaises(FoldError):
            build_tie_shapes(REAL_ROW_REPORT_BARE_POLY_GATE)


def _finger_device(s: str, g: str, d: str) -> dict:
    return {"class": "nfet", "nets": {"s": s, "g": g, "d": d, "b": "vsubs"}}


class FoldConnectivityVerdictTest(unittest.TestCase):
    """Pins AC3's own connectivity check against synthetic extraction facts.

    Same pattern as ``check_gate_driver_core.py``'s ``mim_stack_verdict`` /
    ``ground_rail_isolation_verdict`` tests: the function under test is pure,
    so its failing directions -- unreachable from a correctly generated GDS
    -- are exercised here instead of against a real broken fixture this repo
    would otherwise have to keep around on purpose.
    """

    NET_NAMES = {"s": "S", "d": "D", "g": "G"}

    def test_tied_fold_passes(self):
        # 8 fingers, alternating source/drain orientation -- exactly what a
        # real "parallel" folded device extracts as (confirmed against a
        # real klt extract run, see the module docstring).
        devices = [_finger_device("S", "G", "D") for _ in range(4)] + [
            _finger_device("D", "G", "S") for _ in range(4)
        ]
        verdict = fold_connectivity_verdict({"devices": devices}, self.NET_NAMES, 8)
        self.assertTrue(verdict["passed"], verdict["failures"])
        self.assertEqual(verdict["device_count"], 8)

    def test_untied_fold_fails_naming_both_rows(self):
        # The exact regression this check exists to catch (issue #254 /
        # F-018): each row kept its own honest, but disjoint, per-row
        # G<r>/S<r>/D<r> labels instead of sharing one net per bus -- passes
        # every geometric assertion (right finger count, right bbox) but is
        # electrically two m=4 devices, not one m=8 device.
        devices = [_finger_device("S0", "G0", "D0") for _ in range(4)] + [
            _finger_device("S1", "G1", "D1") for _ in range(4)
        ]
        verdict = fold_connectivity_verdict({"devices": devices}, self.NET_NAMES, 8)
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["device_count"], 8)
        joined = " ".join(verdict["failures"])
        for net in ("G0", "G1", "S0", "D0", "S1", "D1"):
            self.assertIn(net, joined)

    def test_partial_tie_fails_on_the_one_broken_finger(self):
        # 7 fingers tied correctly, 1 finger's gate landed on an anonymous
        # net -- a partially-broken tie must still fail, and must name only
        # the actual offender, not every finger.
        devices = [_finger_device("S", "G", "D") for _ in range(7)] + [
            _finger_device("S", "$7", "D")
        ]
        verdict = fold_connectivity_verdict({"devices": devices}, self.NET_NAMES, 8)
        self.assertFalse(verdict["passed"])
        self.assertIn("$7", " ".join(verdict["failures"]))

    def test_wrong_finger_count_fails(self):
        devices = [_finger_device("S", "G", "D") for _ in range(6)]
        verdict = fold_connectivity_verdict({"devices": devices}, self.NET_NAMES, 8)
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["device_count"], 6)
        self.assertEqual(verdict["expected_device_count"], 8)

    def test_extra_unrelated_net_on_one_finger_fails(self):
        devices = [_finger_device("S", "G", "D") for _ in range(4)] + [
            _finger_device("S", "G", "OTHER_NET")
        ]
        verdict = fold_connectivity_verdict({"devices": devices}, self.NET_NAMES, 5)
        self.assertFalse(verdict["passed"])
        self.assertIn("OTHER_NET", " ".join(verdict["failures"]))


if __name__ == "__main__":
    unittest.main()
