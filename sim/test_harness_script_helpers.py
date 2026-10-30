"""Pins the helpers shared by the standalone sim/*/run_*.py scripts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def _stub_ngspice(tmp_path, monkeypatch, body: str) -> Path:
    stub = tmp_path / "bin" / "ngspice"
    stub.parent.mkdir()
    stub.write_text("#!/bin/sh\n" + body)
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub.parent}:/usr/bin:/bin")
    return tmp_path


def test_run_ngspice_returns_combined_log(tmp_path, monkeypatch):
    work = _stub_ngspice(tmp_path, monkeypatch, "echo out; echo err >&2\n")
    assert script_helpers.run_ngspice(work, "d.spice", "typical @ 27 C") == "out\nerr\n"


def test_run_ngspice_raises_on_nonzero_exit(tmp_path, monkeypatch):
    import pytest

    work = _stub_ngspice(tmp_path, monkeypatch, "echo boom; exit 3\n")
    with pytest.raises(RuntimeError, match=r"exited 3 for d.spice \[ss @ 125 C\]"):
        script_helpers.run_ngspice(work, "d.spice", "ss @ 125 C")


def test_run_ngspice_raises_on_error_line(tmp_path, monkeypatch):
    import pytest

    work = _stub_ngspice(tmp_path, monkeypatch, "echo 'Error: no such model'\n")
    with pytest.raises(RuntimeError, match=r"reported an error for d.spice \[tt\]"):
        script_helpers.run_ngspice(work, "d.spice", "tt")


def test_run_corner_deck_stages_wrapper_and_included_files(tmp_path, monkeypatch):
    seen = {}

    def fake_run(work, deck_name, label):
        seen["deck_name"] = deck_name
        seen["label"] = label
        seen["files"] = {p.name: p.read_text() for p in work.iterdir()}
        return "log"

    monkeypatch.setattr(script_helpers, "run_ngspice", fake_run)
    deck = tmp_path / "dut.spice"
    deck.write_text("* dut\nR1 a b 1k")

    class _Pdk:
        design_include = "design.ngspice"
        model_lib = "sm141064.ngspice"

    log = script_helpers.run_corner_deck(
        deck, _Pdk(), ["typical"], 27.0,
        script="run_x.py", control=".control\nrun\n.endc", label="tt @ 27 C",
        prefix="x-", extra_lines=[".options abstol=1e-12"],
    )
    assert log == "log"
    assert seen["deck_name"] == "dut.spice" and seen["label"] == "tt @ 27 C"
    files = seen["files"]
    assert set(files) == {"corner.spice", "control.spice", "dut.spice"}
    assert ".temp 27" in files["corner.spice"]
    assert ".options abstol=1e-12" in files["corner.spice"]
    assert files["control.spice"] == ".control\nrun\n.endc"
    assert files["dut.spice"] == (
        '.include "corner.spice"\n* dut\nR1 a b 1k\n.include "control.spice"\n.end\n'
    )


def test_first_crossing_rising_interpolates():
    assert script_helpers.first_crossing([0, 1, 2], [0.0, 1.0, 3.0], 2.0) == 1.5


def test_first_crossing_falling_interpolates():
    assert script_helpers.first_crossing([0, 1, 2], [3.0, 1.0, 0.0], 2.0, rising=False) == 0.5


def test_first_crossing_direction_must_match():
    assert script_helpers.first_crossing([0, 1, 2], [3.0, 1.0, 0.0], 2.0) is None
    assert script_helpers.first_crossing([0, 1, 2], [0.0, 1.0, 3.0], 2.0, rising=False) is None


def test_first_crossing_skips_flat_segment_and_takes_first_crossing():
    xs, ys = [0, 1, 2, 3, 4], [1.0, 1.0, 1.0, 5.0, 0.0]
    assert script_helpers.first_crossing(xs, ys, 3.0) == 2.5


def test_first_crossing_threshold_on_sample_and_none_when_absent():
    assert script_helpers.first_crossing([0, 1], [0.0, 2.0], 2.0) == 1.0
    assert script_helpers.first_crossing([0, 1], [0.0, 2.0], 5.0) is None
    assert script_helpers.first_crossing([], [], 1.0) is None


def test_first_crossing_log_interpolates_in_log_y():
    # Geometric midpoint of 1e-6..1e-4 is 1e-5, halfway in x.
    got = script_helpers.first_crossing([0.0, 1.0], [1e-6, 1e-4], 1e-5, log=True)
    assert abs(got - 0.5) < 1e-12
    assert script_helpers.first_crossing([0.0, 1.0], [1e-6, 1e-4], 1e-5) != got


def test_first_crossing_log_nonpositive_bracket_returns_left_x():
    assert script_helpers.first_crossing([2.0, 3.0], [0.0, 1.0], 0.5, log=True) == 2.0


def test_range_verdict():
    rv = script_helpers.range_verdict
    assert rv(None, 0, 1) == "ERROR (no crossing found)"
    assert rv(0.5, 0, 1) == "PASS"
    assert rv(0, 0, 1) == "PASS" and rv(1, 0, 1) == "PASS"
    assert rv(-0.1, 0, 1) == "FAIL" and rv(1.1, 0, 1) == "FAIL"
    assert rv(5, None, 5) == "PASS" and rv(6, None, 5) == "FAIL"
    assert rv(-1, 0, None) == "FAIL"


def test_ronw_mismatch_run_sample_discloses_ngspice_error(tmp_path, monkeypatch):
    """A non-converged Monte Carlo draw is reported as ``"error"`` (with the
    shared runner's message), not raised -- the campaign must not abort."""
    import importlib.util

    _stub_ngspice(tmp_path, monkeypatch, "echo 'Error: timestep too small'\n")

    sim_dir = Path(__file__).resolve().parent
    monkeypatch.syspath_prepend(str(sim_dir / "low-side-power-switch"))
    spec = importlib.util.spec_from_file_location(
        "run_ronw_mismatch",
        sim_dir / "low-side-power-switch-ronw-mismatch" / "run_ronw_mismatch.py",
    )
    ronw = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, ronw)
    spec.loader.exec_module(ronw)

    class _Pdk:
        design_include = "design.ngspice"
        model_lib = "sm141064.ngspice"

    corner = harness_corners.CORNERS["tt"]
    status, log, flat = ronw._run_sample(_Pdk(), corner, 27.0, None)
    assert status == "error"
    assert "reported an error for" in log and "tt @ 27.0 C" in log
    assert flat == {}
