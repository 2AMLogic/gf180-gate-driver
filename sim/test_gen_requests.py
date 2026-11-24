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
Issue #556 added a fourth, ``sim/uvlo-reference-study/klt/gen_startup_requests.py``
(the DR-0024 gate-3 startup grid), over the same shared scaffolding, so the same
pinning covers its twelve committed request files.

Issue #560 added the two post-layout drive generators (nominal and 6 V stretch
requests for the no-RC and RC extracted DUTs of both drive facets) and, with
them, a second check class: the requests' effective limits are compared
against each facet's ``testbench/tb.json`` ``checks`` -- every check carried
at its tier-appropriate bound, the 45 nominal and 15 stretch PVT points
covered exactly once -- so a bound that drifts from its manifest fails here
even when the generator still reproduces its own committed bytes.

This file lives at ``sim/`` rather than inside one testbench's ``klt/`` directory
because the generators it runs live under multiple testbenches.

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

# Scripts copied into every sandbox, relative to sim/. All are copied every
# time: pex/gen_pex_requests.py imports the core generator from its parent
# directory (``sys.path.insert(0, HERE.parent)``), and both top-level generators
# import ``harness.klt_request`` from sim/ (``sys.path.insert(0, HERE.parents[1])``).
SCRIPTS = (
    "gate-driver-core-drive-with-uvlo/klt/gen_requests.py",
    "gate-driver-core-drive-with-uvlo/klt/pex/gen_pex_requests.py",
    "uvlo-trip-verification/klt/gen_requests.py",
    "uvlo-reference-study/klt/gen_startup_requests.py",
    "gate-driver-core-drive-postlayout/klt/gen_requests.py",
    "gate-driver-core-drive-with-uvlo-postlayout/klt/gen_requests.py",
    "level-shifter-oxide-safety-postlayout/klt/gen_requests.py",
)

# Non-script generator inputs mirrored into every sandbox, relative to sim/.
# The oxide-safety generator reads its facet's tb.json at generate time (its
# bounds and column names come from the manifest, never re-typed), so the
# byte-pinning sandbox needs the manifest too -- a tb.json edit that moves a
# request must fail here, not only on the machine that happens to re-run the
# generator.
SCRIPT_INPUTS = (
    "level-shifter-oxide-safety-postlayout/testbench/tb.json",
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
    (
        "uvlo-reference-study/klt/gen_startup_requests.py",
        tuple(
            f"uvlo-reference-study/klt/request-startup-{stem}.json"
            for stem in (
                "ramp-slow",
                "ramp-harness",
                "ramp-fast",
                "ramp-vfast",
                "ramp-1ns",
                "hold-2v0",
                "hold-3v0",
                "hold-5v0",
                "brownout",
                "deadinit-2v0",
                "deadinit-5v0",
                "deadinit-2v0-nokick",
            )
        ),
    ),
    (
        "gate-driver-core-drive-postlayout/klt/gen_requests.py",
        (
            "gate-driver-core-drive-postlayout/klt/request-nominal.json",
            "gate-driver-core-drive-postlayout/klt/request-nominal-rc.json",
            "gate-driver-core-drive-postlayout/klt/request-stretch.json",
            "gate-driver-core-drive-postlayout/klt/request-stretch-rc.json",
        ),
    ),
    (
        "gate-driver-core-drive-with-uvlo-postlayout/klt/gen_requests.py",
        (
            "gate-driver-core-drive-with-uvlo-postlayout/klt/request-nominal.json",
            "gate-driver-core-drive-with-uvlo-postlayout/klt/request-nominal-rc.json",
            "gate-driver-core-drive-with-uvlo-postlayout/klt/request-stretch.json",
            "gate-driver-core-drive-with-uvlo-postlayout/klt/request-stretch-rc.json",
        ),
    ),
    (
        "level-shifter-oxide-safety-postlayout/klt/gen_requests.py",
        (
            "level-shifter-oxide-safety-postlayout/klt/request-norcx.json",
            "level-shifter-oxide-safety-postlayout/klt/request-rc.json",
        ),
    ),
)

# The two post-layout drive facets of issue #560: (slug, tb.json check count
# re-derived from the manifest at assert time).
POSTLAYOUT_DRIVE_FACETS = (
    ("gate-driver-core-drive-postlayout", 20),
    ("gate-driver-core-drive-with-uvlo-postlayout", 23),
)


def _mirror_generators(tmp: pathlib.Path) -> None:
    """Mirror the parts of ``sim/`` the generators need into ``tmp``.

    The whole harness package, so a generator that starts importing another
    harness module fails on its own merits rather than on a short copy list;
    every generator script at its real relative path (pex/gen_pex_requests.py
    imports the core generator from its parent directory); and the non-script
    generator inputs (the oxide-safety facet's tb.json).
    """
    shutil.copytree(
        SIM / "harness",
        tmp / "harness",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for rel in SCRIPTS:
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SIM / rel, dest)
    for rel in SCRIPT_INPUTS:
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SIM / rel, dest)


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
        _mirror_generators(tmp)

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


class PostlayoutDriveRequestsMatchTheirManifests(unittest.TestCase):
    """The post-layout drive requests carry their tb.json checks (issue #560).

    Every applicable min and max of each facet's ``testbench/tb.json`` must
    appear as a request limit at the tier-appropriate bound, the 45 nominal
    and 15 stretch PVT points must be covered exactly once with the 6 V
    stretch rows in their own request, and each request must name the body of
    the DUT variant it grades. The bound policy is un-sharded on purpose: the
    post-layout manifests carry no DR-0016 / DR-0020 exception, so the
    stretch sink bound is 1 A even at ss/sf 125 C -- pinned here the same way
    the PEX test above pins the schematic policy.
    """

    def _request(self, facet, tier, suffix=""):
        return json.loads(
            (SIM / facet / "klt" / f"request-{tier}{suffix}.json").read_text()
        )

    def test_check_keys_and_effective_limits_match_tbjson(self) -> None:
        for facet, n_checks in POSTLAYOUT_DRIVE_FACETS:
            with self.subTest(facet=facet):
                tb = json.loads(
                    (SIM / facet / "testbench" / "tb.json").read_text()
                )
                self.assertEqual(
                    len(tb["checks"]),
                    n_checks,
                    f"{facet}: tb.json check count moved; re-derive the "
                    "request measurement set from the manifest",
                )
                for tier in ("nominal", "stretch"):
                    for suffix in ("", "-rc"):
                        req = self._request(facet, tier, suffix)
                        limits = {
                            m["name"]: m.get("limits")
                            for m in req["measurements"]
                        }
                        self.assertEqual(
                            set(limits),
                            set(tb["checks"]) | {"vin_max_v", "vin_min_v"},
                            f"{facet} request-{tier}{suffix}: measurement "
                            "set must be the manifest checks plus the two "
                            "ungraded vin columns",
                        )
                        for key, check in tb["checks"].items():
                            override = (
                                check.get("stretch", {})
                                if tier == "stretch"
                                else {}
                            )
                            expected = {
                                k: v
                                for k, v in {**check, **override}.items()
                                if k in ("min", "max")
                            }
                            self.assertEqual(
                                limits[key],
                                expected,
                                f"{facet} request-{tier}{suffix} {key}: "
                                "effective bound must equal the tb.json "
                                f"{tier} tier",
                            )

    def test_corner_axes_partition_the_60_point_grid_exactly_once(self) -> None:
        for facet, _ in POSTLAYOUT_DRIVE_FACETS:
            with self.subTest(facet=facet):
                for suffix in ("", "-rc"):
                    nominal = self._request(facet, "nominal", suffix)
                    stretch = self._request(facet, "stretch", suffix)
                    for req, vlogic, vdrv in (
                        (nominal, [2.97, 3.3, 3.63], [4.5, 5.0, 5.5]),
                        (stretch, [3.3], [6.0]),
                    ):
                        self.assertEqual(
                            [p["name"] for p in req["corners"]["process"]],
                            ["tt", "ff", "ss", "fs", "sf"],
                        )
                        self.assertEqual(
                            req["corners"]["temperature_c"],
                            [-40.0, 27.0, 125.0],
                        )
                        # the harness's tied two-rail grid: same index count
                        # on both rails (swept together, never cross-producted)
                        self.assertEqual(
                            req["corners"]["supply_v"],
                            {"vsup_logic": vlogic, "vsup_drv": vdrv},
                        )
                        self.assertEqual(len(vlogic), len(vdrv))
                    n_points = (
                        len(nominal["corners"]["process"])
                        * len(nominal["corners"]["temperature_c"])
                        * len(nominal["corners"]["supply_v"]["vsup_logic"])
                    )
                    s_points = (
                        len(stretch["corners"]["process"])
                        * len(stretch["corners"]["temperature_c"])
                        * len(stretch["corners"]["supply_v"]["vsup_logic"])
                    )
                    self.assertEqual(n_points, 45)
                    self.assertEqual(s_points, 15)
                    # un-sharded policy: no DR-0016 exception -- 1 A sink
                    # minimum at every stretch corner, ss/sf 125 C included.
                    sink = {
                        m["name"]: m.get("limits")
                        for m in stretch["measurements"]
                    }["ipeak_sink_a"]
                    self.assertEqual(sink, {"min": 1.0})
                    source = {
                        m["name"]: m.get("limits")
                        for m in nominal["measurements"]
                    }["ipeak_source_a"]
                    self.assertEqual(source, {"min": 0.5})

    def test_each_request_names_its_duts_body(self) -> None:
        for facet, _ in POSTLAYOUT_DRIVE_FACETS:
            for tier in ("nominal", "stretch"):
                self.assertEqual(
                    self._request(facet, tier)["netlist"], "body.spice"
                )
                self.assertEqual(
                    self._request(facet, tier, "-rc")["netlist"],
                    "body-rc.spice",
                )

    def test_uvlo_facet_keeps_the_three_200ns_probes_flat_named(self) -> None:
        facet = "gate-driver-core-drive-with-uvlo-postlayout"
        for tier in ("nominal", "stretch"):
            for suffix in ("", "-rc"):
                req = self._request(facet, tier, suffix)
                forms = {
                    m["name"]: m.get("spice", "") + m.get("expr", "")
                    for m in req["measurements"]
                }
                for name, node in (
                    ("uvlo_lockout_at_in_high", "x3_lockout"),
                    ("uvlo_vout_at_in_high_v", "OUT"),
                    ("uvlo_vdrv_at_in_high_v", "VDD_DRV"),
                ):
                    self.assertIn(
                        f"FIND v({node}) AT=200n",
                        forms[name],
                        f"{facet} request-{tier}{suffix}: {name} must stay "
                        "a 200 ns FIND probe (crossing-free, so it returns "
                        "a value at a UVLO-locked corner)",
                    )
                # the flat extracted taper-node names, not the schematic's
                # dotted hierarchy
                self.assertIn("v(x2_n1)", forms["n1_max_v"])
        drive = self._request("gate-driver-core-drive-postlayout", "nominal")
        self.assertFalse(
            [m["name"] for m in drive["measurements"] if m["name"].startswith("uvlo_")],
            "the drive facet's manifest carries no uvlo probes",
        )


class OxideSafetyRequestsMatchManifestAndGrid(unittest.TestCase):
    """The oxide-safety postlayout requests restate the harness bench (#559).

    Both requests must carry the harness grid's full 60 points (one request
    per DUT -- every tb.json check of this facet is tier-independent, so the
    #560 nominal/stretch split does not apply), the effective limits must
    equal the manifest's four ``checks`` exactly, the nine top-level columns
    must be the manifest's ``measure`` names, and the step/derived structure
    must preserve the harness's sampled-ratio and delay definitions (the
    19 ns / 59 ns instants, the 1.65 V / 2.5 V literal levels, the
    ``wave.hi / wave.drv`` ratio form).
    """

    SLUG = "level-shifter-oxide-safety-postlayout"
    COLUMNS = (
        "vgate_thinox_max", "vna_peak", "vnb_peak", "vccomp_dev_max",
        "vccomp_stack_max", "t_plh_ns", "t_phl_ns",
        "vout_hi_ratio", "vout_lo_ratio",
    )

    def setUp(self):
        self.tb = json.loads(
            (SIM / self.SLUG / "testbench" / "tb.json").read_text()
        )

    def _request(self, suffix):
        return json.loads(
            (SIM / self.SLUG / "klt" / f"request-{suffix}.json").read_text()
        )

    def test_limits_equal_the_tbjson_checks_and_columns_are_its_measure(self):
        for suffix in ("norcx", "rc"):
            with self.subTest(request=suffix):
                req = self._request(suffix)
                limits = {m["name"]: m.get("limits") for m in req["measurements"]}
                self.assertEqual(list(limits), list(self.COLUMNS))
                self.assertEqual(list(self.tb["measure"]), list(self.COLUMNS))
                for key, check in self.tb["checks"].items():
                    expected = {k: v for k, v in check.items()
                                if k in ("min", "max")}
                    self.assertEqual(limits[key], expected)
                # every other column is unbounded, exactly as in the records
                for name in limits:
                    if name not in self.tb["checks"]:
                        self.assertIsNone(
                            limits[name], f"{name} carries a limit the "
                            "manifest does not grade it against")

    def test_one_request_per_dut_covers_the_60_point_grid_exactly_once(self):
        for suffix, body in (("norcx", "body.spice"), ("rc", "body-rc.spice")):
            with self.subTest(request=suffix):
                req = self._request(suffix)
                self.assertEqual(req["netlist"], body)
                self.assertEqual(
                    [p["name"] for p in req["corners"]["process"]],
                    ["tt", "ff", "ss", "fs", "sf"],
                )
                self.assertEqual(
                    req["corners"]["temperature_c"], [-40.0, 27.0, 125.0]
                )
                # the harness grid tied by index: the three ±10 % pairs plus
                # the 3.3/6.0 vdrv stretch extra, never cross-producted
                self.assertEqual(
                    req["corners"]["supply_v"],
                    {
                        "vsup_logic": [2.97, 3.3, 3.63, 3.3],
                        "vsup_drv": [4.5, 5.0, 5.5, 6.0],
                    },
                )
                self.assertNotIn("analysis", req)
                steps = req["analysis_steps"]
                self.assertEqual(len(steps), 1)
                self.assertEqual(steps[0]["name"], "wave")
                self.assertEqual(
                    steps[0]["analysis"], {"kind": "tran", "args": "20p 200n"}
                )

    def test_step_preserves_the_harness_measurement_definitions(self):
        for suffix in ("norcx", "rc"):
            with self.subTest(request=suffix):
                req = self._request(suffix)
                step = req["analysis_steps"][0]
                spice = {
                    m["name"]: m["spice"]
                    for m in step["measurements"]
                    if "spice" in m
                }
                # the sampled ratios: IN_DRV at 59 ns (hi) and 19 ns (lo)
                # over the VDD_DRV denominator at 59 ns (drv) -- one solve,
                # the harness's own instants
                self.assertEqual(
                    spice["hi"], ".meas tran hi FIND v(IN_DRV) AT=59n"
                )
                self.assertEqual(
                    spice["lo"], ".meas tran lo FIND v(IN_DRV) AT=19n"
                )
                self.assertEqual(
                    spice["drv"], ".meas tran drv FIND v(VDD_DRV) AT=59n"
                )
                # the delays: the harness fragment's literal levels, verbatim
                self.assertEqual(
                    spice["t_plh"],
                    ".meas tran t_plh TRIG v(IN) VAL=1.65 RISE=1 "
                    "TARG v(IN_DRV) VAL=2.5 RISE=1",
                )
                self.assertEqual(
                    spice["t_phl"],
                    ".meas tran t_phl TRIG v(IN) VAL=1.65 FALL=1 "
                    "TARG v(IN_DRV) VAL=2.5 FALL=1",
                )
                derived = {m["name"]: m["expr"] for m in req["measurements"]}
                self.assertEqual(derived["vout_hi_ratio"], "wave.hi / wave.drv")
                self.assertEqual(derived["vout_lo_ratio"], "wave.lo / wave.drv")
                self.assertEqual(derived["t_plh_ns"], "wave.t_plh * 1e9")
                self.assertEqual(derived["t_phl_ns"], "wave.t_phl * 1e9")
                # the six thin-oxide differences and four MiM legs are the
                # manifest's own node pairs, as intermediate reductions
                exprs = {
                    m["name"]: m.get("expr")
                    for m in step["measurements"]
                    if "expr" in m
                }
                self.assertEqual(
                    exprs["dq1"], "vecmax(abs(v(IN)-v(x1_inb)))"
                )
                self.assertEqual(
                    exprs["dvc4"], "vecmax(abs(v(ANON295)-v(IN_DRV)))"
                )

    def test_generator_refuses_a_drifted_measure_expression(self):
        """A mutated tb.json ``measure`` expression must fail generation (#606).

        The committed requests restate the harness bench's nine ``measure``
        expressions, but ``manifest()`` used to compare only the column
        *names* (``list(tb["measure"])``), so mutating an expression (issue
        #606's ``t_plh*1e9`` -> ``t_plh*1e6`` scratch check) left the
        generator exiting 0 with byte-identical requests -- silent drift.
        ``manifest()`` now compares the full ``measure`` map, and this pins
        that the check actually fires.
        """
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        tmp = pathlib.Path(tmpdir.name)
        _mirror_generators(tmp)
        tb_path = tmp / self.SLUG / "testbench" / "tb.json"
        tb = json.loads(tb_path.read_text())
        tb["measure"]["t_plh_ns"] = "t_plh*1e6"
        tb_path.write_text(json.dumps(tb, indent=2) + "\n")
        proc = subprocess.run(
            [sys.executable, str(tmp / self.SLUG / "klt" / "gen_requests.py")],
            capture_output=True,
            text=True,
            # same isolation stance as _run_in_sandbox
            cwd=tmp,
        )
        self.assertNotEqual(
            proc.returncode,
            0,
            "a drifted tb.json `measure` expression must fail generation, "
            f"but gen_requests.py exited 0:\n{proc.stdout}\n{proc.stderr}",
        )


class OxideBatchEnvelopesCoverTheGrid(unittest.TestCase):
    """Every committed oxide-safety envelope covers each DUT's grid exactly once.

    Each committed fleet report must hold the 60 unique corners of the
    harness grid (process x temperature x the four tied rail pairs), report
    all nine record columns at every corner, and pin the DUT it ran in
    ``environment.netlist_closure``. The sha256-vs-live-file match is the
    citing record's to state (bytes drift on a re-extraction; the envelope
    keeps the hash it ran) -- this pins only what cannot drift. More than
    one envelope per stem accumulates by design: #559 qualified the batch
    route on the pre-#510 DUTs, #510 re-ran it over the header-fixed DUTs,
    and every append-only envelope keeps pinning the bytes it ran.
    """

    SLUG = "level-shifter-oxide-safety-postlayout"
    ENVELOPES = {
        "norcx": ("oxide-norcx", "layout/lvs/gate_driver_core.extracted.spice"),
        "rc": ("oxide-rc", "layout/lvs/gate_driver_core.extracted-rc.spice"),
    }
    # The same nine record columns OxideSafetyRequestsMatchManifestAndGrid
    # pins the requests against -- one shared tuple, not a second copy (#606).
    COLUMNS = OxideSafetyRequestsMatchManifestAndGrid.COLUMNS
    GRID = {
        (p, t, vl, vd)
        for p in ("tt", "ff", "ss", "fs", "sf")
        for t in (-40.0, 27.0, 125.0)
        for vl, vd in ((2.97, 4.5), (3.3, 5.0), (3.63, 5.5), (3.3, 6.0))
    }

    def _envelopes(self, stem):
        matches = sorted((SIM / self.SLUG / "klt" / "envelopes").glob(
            f"*-{stem}.json"))
        self.assertGreaterEqual(
            len(matches), 1,
            f"expected at least one committed envelope for {stem}, found "
            f"{[m.name for m in matches]}",
        )
        return [(m.name, json.loads(m.read_text())) for m in matches]

    def test_each_envelope_covers_the_grid_exactly_once(self):
        for suffix, (stem, dut) in self.ENVELOPES.items():
            for name, env in self._envelopes(stem):
                with self.subTest(envelope=name):
                    seen = {
                        (
                            c["process"],
                            float(c["temperature_c"]),
                            float(c["supply_v"]["vsup_logic"]),
                            float(c["supply_v"]["vsup_drv"]),
                        )
                        for c in env["corners"]
                    }
                    self.assertEqual(len(env["corners"]), 60)
                    self.assertEqual(seen, self.GRID)
                    for c in env["corners"]:
                        # per corner, not accumulated: a union/overwrite across
                        # corners would examine only the last one
                        # the top-level record columns only -- the step-scoped
                        # `wave.*` results ride along in each corner entry
                        vals = {
                            m["name"]: m.get("value")
                            for m in c["measurements"]
                            if not m["name"].startswith("wave.")
                        }
                        self.assertEqual(set(vals), set(self.COLUMNS), c["corner_id"])
                        for name, value in vals.items():
                            self.assertIsNotNone(
                                value, f"{name} has no value at {c['corner_id']}"
                            )
                    closure = {
                        e["path"]: e["sha256"]
                        for e in env["environment"]["netlist_closure"]
                    }
                    self.assertIn(dut, closure)




if __name__ == "__main__":
    unittest.main()
