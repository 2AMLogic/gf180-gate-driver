#!/usr/bin/env python3
"""Every `klt sim` request generator still reproduces its committed bytes.

Stdlib-only, no ``klt``, no PDK, no ngspice -- runs on the PDK-free CI runner
alongside the other generator self-tests (``.github/workflows/ci.yml``).

Why this exists (issue #424): ``gen_requests.request()`` gained three parameters
when the item-5 requests were sharded to carry the ratified DR-0016 / DR-0020
corner bounds (``9721e39``), and ``pex/gen_pex_requests.py`` -- which imports and
calls it -- kept the old 4-argument call for two weeks. Nothing noticed: no test
imported either generator, and the ``verification/signoff/README.md`` item-7
reproduction command whose *first line* is that script was never executed in CI.
The committed requests are the inputs of cited, append-only sign-off evidence, so
the failure mode is not a crash in production -- it is that the documented way to
regenerate graded evidence silently stops working.

The check is deliberately byte-level rather than structural. Every generator
writes ``json.dumps(..., indent=2) + "\\n"`` straight into the committed tree, so
a reformat is indistinguishable from a content change once it lands; pinning the
bytes means a regenerated request that differs from the one the evidence was
measured against fails here instead of being committed as if nothing moved.

Issue #441 widened this in two directions. It covers **all three** generators now
-- ``sim/uvlo-trip-verification/klt/gen_requests.py`` owns the four requests
behind the graded item-5 UVLO and drive-rail rows and had the identical exposure
with nothing guarding it -- and all three now take their process axis and request
envelope from ``sim/harness/klt_request.py`` instead of each carrying a hand-typed
copy, so this byte comparison is also what pins the shared module (and, through
it, ``harness/corners.py``'s five MOS bundles) against the committed requests.

This file lives at ``sim/`` rather than inside one testbench's ``klt/`` directory
because the generators it runs live under two different testbenches.

Each generator writes into ``Path(__file__).resolve().parent``, so the test
mirrors the parts of ``sim/`` they need into a temp tree -- the ``harness``
package plus the generator scripts at their real relative paths -- and runs them
there as subprocesses. Nothing under ``sim/`` is written by this test.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SIM = pathlib.Path(__file__).resolve().parent
CORE_KLT = SIM / "gate-driver-core-drive-with-uvlo" / "klt"
UVLO_KLT = SIM / "uvlo-trip-verification" / "klt"
UVLO_RECORDS = SIM / "uvlo-trip-verification" / "records"

# Scripts copied into every sandbox, relative to sim/. All three are copied every
# time: pex/gen_pex_requests.py imports the core generator from its parent
# directory (``sys.path.insert(0, HERE.parent)``), and both top-level generators
# import ``harness.klt_request`` from sim/ (``sys.path.insert(0, HERE.parents[1])``).
SCRIPTS = (
    "gate-driver-core-drive-with-uvlo/klt/gen_requests.py",
    "gate-driver-core-drive-with-uvlo/klt/pex/gen_pex_requests.py",
    "uvlo-trip-verification/klt/gen_requests.py",
)

# (generator relative to sim/, committed outputs it owns, also relative to sim/)
GENERATORS = (
    (
        "gate-driver-core-drive-with-uvlo/klt/gen_requests.py",
        (
            "gate-driver-core-drive-with-uvlo/klt/request-nominal-main.json",
            "gate-driver-core-drive-with-uvlo/klt/request-nominal-ss-warm-hot.json",
            "gate-driver-core-drive-with-uvlo/klt/request-nominal-ss-cold-mid-high.json",
            "gate-driver-core-drive-with-uvlo/klt/request-nominal-ss-cold-low.json",
            "gate-driver-core-drive-with-uvlo/klt/request-stretch-main.json",
            "gate-driver-core-drive-with-uvlo/klt/request-stretch-slow-cold-mid.json",
            "gate-driver-core-drive-with-uvlo/klt/request-stretch-hot-slow.json",
        ),
    ),
    (
        "gate-driver-core-drive-with-uvlo/klt/pex/gen_pex_requests.py",
        (
            "gate-driver-core-drive-with-uvlo/klt/pex/request-nominal.json",
            "gate-driver-core-drive-with-uvlo/klt/pex/request-stretch.json",
        ),
    ),
    (
        "uvlo-trip-verification/klt/gen_requests.py",
        (
            "uvlo-trip-verification/klt/request-trip.json",
            "uvlo-trip-verification/klt/request-response.json",
            "uvlo-trip-verification/klt/request-rail-nominal.json",
            "uvlo-trip-verification/klt/request-rail-stretch.json",
        ),
    ),
)


def _load_run_uvlo_trip():
    """Import ``sim/uvlo-trip-verification/run_uvlo_trip.py`` by path.

    Its directory is not a package and its basename is not importable from
    ``sim/``, so a file-location loader is the way in. It is stdlib-only at
    import time (it locates the PDK lazily, inside ``main()``), so this stays a
    PDK-free test.
    """
    path = SIM / "uvlo-trip-verification" / "run_uvlo_trip.py"
    spec = importlib.util.spec_from_file_location("run_uvlo_trip_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GeneratorsReproduceCommittedRequests(unittest.TestCase):
    def _run_in_sandbox(self, script_rel: str) -> pathlib.Path:
        """Run one generator in a temp mirror of sim/; return that tree."""
        # (not TestCase.enterContext -- that is 3.11+, and the harness targets
        # python3 >= 3.9, sim/harness/README.md)
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        tmp = pathlib.Path(tmpdir.name)
        # The whole harness package, so a generator that starts importing another
        # harness module fails on its own merits rather than on a short copy list.
        shutil.copytree(
            SIM / "harness",
            tmp / "harness",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        for rel in SCRIPTS:
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SIM / rel, dest)

        proc = subprocess.run(
            [sys.executable, str(tmp / script_rel)],
            capture_output=True,
            text=True,
            # -I would also drop the script's own directory from sys.path, which
            # the PEX generator's `import gen_requests` relies on. An empty cwd
            # that is not the sandbox is enough isolation here.
            cwd=tmp,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"{script_rel} failed to run:\n{proc.stdout}\n{proc.stderr}",
        )
        return tmp

    def test_each_generator_reproduces_its_committed_files_byte_for_byte(self) -> None:
        for script_rel, outputs in GENERATORS:
            with self.subTest(generator=script_rel):
                tmp = self._run_in_sandbox(script_rel)
                for rel in outputs:
                    produced = tmp / rel
                    committed = SIM / rel
                    self.assertTrue(
                        produced.is_file(),
                        f"{script_rel} did not write {rel}",
                    )
                    self.assertEqual(
                        produced.read_bytes(),
                        committed.read_bytes(),
                        f"{script_rel} no longer reproduces {rel} byte-for-byte. "
                        "The committed requests are inputs of cited, append-only "
                        "sign-off evidence: either the generator (or the shared "
                        "harness/klt_request.py scaffolding it builds on) regressed, "
                        "or the change is deliberate and the evidence measured "
                        "against the old request must be re-run and re-cited.",
                    )

    def test_pex_requests_carry_the_unsharded_matrix_at_spec_sec3_bounds(self) -> None:
        """The PEX requests deliberately do NOT use the DR-0016/DR-0020 shards.

        ``verification/signoff/README.md`` item 7 grades 60 corners against the
        plain spec Sec.3 bounds -- the stricter of the two. Pinning that here keeps
        a future "reuse the shards" edit from silently relaxing graded post-layout
        evidence (explicitly out of scope for #424; it is a spec decision).
        """
        pex = CORE_KLT / "pex"
        nominal = json.loads((pex / "request-nominal.json").read_text())
        stretch = json.loads((pex / "request-stretch.json").read_text())

        self.assertEqual(
            [p["name"] for p in nominal["corners"]["process"]],
            ["tt", "ff", "ss", "fs", "sf"],
        )
        self.assertEqual(nominal["corners"]["temperature_c"], [-40.0, 27.0, 125.0])
        self.assertEqual([p["name"] for p in stretch["corners"]["process"]],
                         ["tt", "ff", "ss", "fs", "sf"])
        self.assertEqual(stretch["corners"]["temperature_c"], [-40.0, 27.0, 125.0])

        def limits(req):
            return {m["name"]: m.get("limits") for m in req["measurements"]}

        # Sec.3 target bounds, not DR-0020's 0.45 A source minimum.
        self.assertEqual(limits(nominal)["ipeak_source_a"], {"min": 0.5})
        self.assertEqual(limits(nominal)["ipeak_sink_a"], {"min": 0.5})
        # Sec.3 stretch bounds, not DR-0016's 0.85 A sink minimum.
        self.assertEqual(limits(stretch)["ipeak_source_a"], {"min": 1.0})
        self.assertEqual(limits(stretch)["ipeak_sink_a"], {"min": 1.0})

        # The hierarchical diagnostic probe has no equivalent in the flat
        # extracted netlist and must stay dropped from the PEX requests.
        for req in (nominal, stretch):
            names = [m["name"] for m in req["measurements"]]
            self.assertNotIn("uvlo_lockout_at_in_high", names)
            for row in ("trise_s", "tfall_s", "tpdlh_s", "tpdhl_s",
                        "ipeak_source_a", "ipeak_sink_a"):
                self.assertIn(row, names)


class UvloRequestsRestateTheHarnessScript(unittest.TestCase):
    """The UVLO requests still score what ``run_uvlo_trip.py`` scores.

    ``uvlo-trip-verification/klt/gen_requests.py``'s docstring says its bounds are
    the ones ``../run_uvlo_trip.py`` grades against, but they are re-typed
    literals: ``klt`` wants plain numbers in ``limits`` and in the ``.meas``
    strings, and importing the harness script into a PDK-free generator would be a
    far bigger dependency than the four numbers are worth (issue #441 step 2).
    This is the equality check that stands in for that import -- read off the
    committed requests, which are what the sign-off grader actually sees.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = _load_run_uvlo_trip()
        cls.trip = json.loads((UVLO_KLT / "request-trip.json").read_text())
        cls.response = json.loads((UVLO_KLT / "request-response.json").read_text())

    @staticmethod
    def _measurement(request, name):
        for meas in request["measurements"]:
            if meas["name"] == name:
                return meas
        raise AssertionError(f"no measurement named {name!r}")

    def test_trip_limits_match_run_uvlo_trip_ranges(self) -> None:
        falling_lo, falling_hi = self.script.FALLING_RANGE
        rising_lo, rising_hi = self.script.RISING_RANGE
        self.assertEqual(
            self._measurement(self.trip, "falling_trip_v")["limits"],
            {"min": falling_lo, "max": falling_hi},
        )
        self.assertEqual(
            self._measurement(self.trip, "rising_trip_v")["limits"],
            {"min": rising_lo, "max": rising_hi},
        )
        # Decision record 0001 Decision 4 gives hysteresis a typical value only,
        # so the request must keep reporting it ungraded.
        self.assertNotIn("limits", self._measurement(self.trip, "hysteresis_v"))

    def test_response_limit_matches_run_uvlo_trip_max(self) -> None:
        self.assertEqual(
            self._measurement(self.response, "response_s")["limits"],
            {"max": self.script.RESPONSE_MAX_S},
        )

    def test_measurement_thresholds_match_run_uvlo_trip(self) -> None:
        """The levels baked into the ``.meas`` strings, not just the bounds."""
        lockout = f"v(lockout)={self.script.LOCKOUT_ABS_THRESHOLD_V:g}"
        for name in ("falling_trip_v", "rising_trip_v"):
            self.assertIn(lockout, self._measurement(self.trip, name)["spice"])

        response = self._measurement(self.response, "response_s")["spice"]
        # Timed from the ratified typical falling trip to the harness's OUT-low
        # proxy -- see the generator's module docstring for the ~1 ns difference
        # from the harness, which times from each corner's own measured trip.
        self.assertIn(f"VAL={self.script.FALLING_TYP:g} FALL=1", response)
        self.assertIn(f"VAL={self.script.OUT_LOW_PROXY_V:g} FALL=1", response)

    def test_temperature_axis_matches_run_uvlo_trip(self) -> None:
        for request in (self.trip, self.response):
            self.assertEqual(request["corners"]["temperature_c"], self.script.TEMPS)


class UvloRecordProseRendersTheRatifiedTargets(unittest.TestCase):
    """The DR-0001 figures in a UVLO record come from the script's own block.

    Issue #454: ``run_uvlo_trip.py``'s ``# decision record 0001 Decision 4/5
    targets.`` block is the named home for DR-0001's ratified numbers, but the
    paragraph that opens each record's results section carried its own
    hand-typed copy of ``3.6V`` / ``3.9V`` / ``300mV`` / ``500ns``. The verdict
    logic reads the constants and the evidence record quoted the literals, so an
    amendment to DR-0001 could move the grading without moving the prose that
    *states* what was graded -- and the prose is the copy that becomes
    append-only evidence.

    The paragraph is now rendered from those constants
    (``DR0001_TARGETS_PROSE``), and this is the check that the rendering equals,
    byte for byte, what the committed record already says. That equality is the
    whole test the issue asks for: wiring the constants up must not reword cited
    evidence by so much as a character.

    Pinned against the **newest** committed record rather than all of them: if
    DR-0001 is ever amended, the constants change, a fresh run supersedes, and
    the newest record is again what the script renders -- while the superseded
    records correctly keep stating the figures they were measured against.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = _load_run_uvlo_trip()

    @staticmethod
    def _newest_record() -> pathlib.Path:
        # Record filenames are `<UTC stamp>-<sha>.md`, so lexicographic order is
        # chronological order (sim/README.md's record-ID convention).
        records = sorted(UVLO_RECORDS.glob("*.md"))
        if not records:
            raise AssertionError(f"no committed record under {UVLO_RECORDS}")
        return records[-1]

    def test_prose_matches_the_newest_committed_record_byte_for_byte(self) -> None:
        record = self._newest_record()
        prefix = "Decision record 0001 Decision 4:"
        committed = [
            line for line in record.read_text().splitlines() if line.startswith(prefix)
        ]
        self.assertEqual(
            len(committed),
            1,
            f"{record.name} should state the DR-0001 Decision 4/5 targets exactly "
            f"once (found {len(committed)} lines starting {prefix!r})",
        )
        self.assertEqual(
            self.script.DR0001_TARGETS_PROSE,
            committed[0],
            "run_uvlo_trip.py no longer renders the DR-0001 Decision 4/5 paragraph "
            f"as {record.name} states it. Either the rendering regressed (fix the "
            "f-string -- the committed record is cited, append-only evidence and "
            "does not move), or DR-0001 itself was amended, in which case the new "
            "figures belong in the constants, the claim must be re-run, and the "
            "superseding record is what this pins against.",
        )

    def test_prose_source_re_types_none_of_the_ratified_figures(self) -> None:
        """No ratified figure is written as a literal inside the paragraph.

        Guards the direction the byte comparison cannot: an edit that re-typed
        ``3.6V`` back into the f-string would still equal the committed record
        today, and would still be the second source of truth this issue exists
        to remove. So this asserts over the *source* of the assignment, where a
        re-typed figure is visible and an interpolated one is not.
        """
        source = (SIM / "uvlo-trip-verification" / "run_uvlo_trip.py").read_text()
        _, _, after = source.partition("DR0001_TARGETS_PROSE = (")
        block, closed, _ = after.partition("\n)\n")
        self.assertTrue(closed, "could not locate the DR0001_TARGETS_PROSE assignment")

        s = self.script
        falling_lo, falling_hi = s.FALLING_RANGE
        rising_lo, rising_hi = s.RISING_RANGE
        for figure in (
            f"{s.FALLING_TYP:g}V",
            f"{s.RISING_TYP:g}V",
            f"{s.HYST_TYP * 1e3:g}mV",
            f"{s.RESPONSE_MAX_S * 1e9:g}ns",
            f"{falling_lo:g}-{falling_hi:g}",
            f"{rising_lo:g}-{rising_hi:g}",
        ):
            self.assertNotIn(
                figure,
                block,
                f"{figure!r} is hard-coded in the DR0001_TARGETS_PROSE f-string; "
                "interpolate the constant from the DR-0001 block instead so the "
                "record prose cannot drift from what the verdict logic grades.",
            )


if __name__ == "__main__":
    unittest.main()
