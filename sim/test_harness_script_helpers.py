"""Pins the helpers shared by the standalone sim/*/run_*.py scripts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def test_fmt_four_digits_and_none():
    assert script_helpers.fmt(1.23456789) == "1.2346"
    assert script_helpers.fmt(1.23456789, 6) == "1.234568"
    assert script_helpers.fmt(None) == "n/a"


def test_parse_dc_tables_and_column():
    tables = script_helpers.parse_dc_tables(LOG)
    assert tables == [
        (["v(a)", "v(b)"], [[1.0, 2.0], [3.0, 4.0]]),
        (["i(x)"], [[5e-3]]),
    ]
    header, rows = tables[0]
    assert script_helpers.column(header, rows, "v(b)") == [2.0, 4.0]


class _Pdk:
    design_include = "/pdk/design.ngspice"
    model_lib = "/pdk/sm141064.ngspice"


def test_corner_shim_sections_temp_and_extra_lines():
    deck = script_helpers.corner_shim(
        _Pdk(),
        ["typical", "cap_typical"],
        27,
        script="run_x.py",
        extra_lines=[".options reltol=1e-4"],
    )
    assert deck.splitlines() == [
        "* Generated per corner point by run_x.py from",
        "* $PDK_ROOT/$PDK (via sim/harness/pdk.py) -- do not edit by hand, and do not commit.",
        '.include "/pdk/design.ngspice"',
        '.lib "/pdk/sm141064.ngspice" typical',
        '.lib "/pdk/sm141064.ngspice" cap_typical',
        ".temp 27",
        ".options reltol=1e-4",
    ]
    assert deck.endswith("\n")


def test_build_points_matches_inline_grid():
    from harness import corners

    names = list(corners.CORNERS)[:2]
    temps = (-40.0, 125.0)
    supplies = {"vdd": 5.0}
    expected = corners.build_grid(
        [corners.CORNERS[n] for n in names], list(temps), [dict(supplies)]
    )
    got = script_helpers.build_points(names, temps, supplies)
    assert got == expected
    assert len(got) == len(names) * len(temps)


def test_claim_sigma_summary_uses_named_measurement():
    class Outcome:
        def values(self, name):
            assert name == "m"
            return [1.0, 3.0]

    from harness import campaign

    expected = campaign.point_sigma_summary([Outcome()], lambda o: o.values("m"))
    assert script_helpers.claim_sigma_summary([Outcome()], "m") == expected
