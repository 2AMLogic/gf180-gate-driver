#!/usr/bin/env python3
"""Both request generators still reproduce their committed request-*.json bytes.

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

The check is deliberately byte-level rather than structural. Both generators write
``json.dumps(..., indent=2) + "\\n"`` straight into the committed tree, so a
reformat is indistinguishable from a content change once it lands; pinning the
bytes means a regenerated request that differs from the one the evidence was
measured against fails here instead of being committed as if nothing moved.

Each generator writes into ``Path(__file__).resolve().parent``, so the test copies
the two scripts into a temp tree of the same shape and runs them there as
subprocesses. Nothing under ``sim/`` is written by this test.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

KLT = pathlib.Path(__file__).resolve().parent
PEX = KLT / "pex"

# (generator relative to KLT, committed outputs it owns, relative to KLT)
GENERATORS = (
    (
        "gen_requests.py",
        (
            "request-nominal-main.json",
            "request-nominal-ss-warm-hot.json",
            "request-nominal-ss-cold-mid-high.json",
            "request-nominal-ss-cold-low.json",
            "request-stretch-main.json",
            "request-stretch-slow-cold-mid.json",
            "request-stretch-hot-slow.json",
        ),
    ),
    (
        "pex/gen_pex_requests.py",
        ("pex/request-nominal.json", "pex/request-stretch.json"),
    ),
)


class GeneratorsReproduceCommittedRequests(unittest.TestCase):
    def _run_in_sandbox(self, script_rel: str) -> pathlib.Path:
        """Run one generator in a temp copy of the klt/ tree; return that tree."""
        # (not TestCase.enterContext -- that is 3.11+, and the harness targets
        # python3 >= 3.9, sim/harness/README.md)
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        tmp = pathlib.Path(tmpdir.name)
        (tmp / "pex").mkdir()
        # Both generators are needed in every sandbox: the PEX one imports the
        # other from its parent directory (``sys.path.insert(0, HERE.parent)``).
        shutil.copy2(KLT / "gen_requests.py", tmp / "gen_requests.py")
        shutil.copy2(PEX / "gen_pex_requests.py", tmp / "pex" / "gen_pex_requests.py")

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
                    committed = KLT / rel
                    self.assertTrue(
                        produced.is_file(),
                        f"{script_rel} did not write {rel}",
                    )
                    self.assertEqual(
                        produced.read_bytes(),
                        committed.read_bytes(),
                        f"{script_rel} no longer reproduces {rel} byte-for-byte. "
                        "The committed requests are inputs of cited, append-only "
                        "sign-off evidence: either the generator regressed, or the "
                        "change is deliberate and the evidence measured against the "
                        "old request must be re-run and re-cited.",
                    )

    def test_pex_requests_carry_the_unsharded_matrix_at_spec_sec3_bounds(self) -> None:
        """The PEX requests deliberately do NOT use the DR-0016/DR-0020 shards.

        ``verification/signoff/README.md`` item 7 grades 60 corners against the
        plain spec Sec.3 bounds -- the stricter of the two. Pinning that here keeps
        a future "reuse the shards" edit from silently relaxing graded post-layout
        evidence (explicitly out of scope for #424; it is a spec decision).
        """
        import json

        nominal = json.loads((PEX / "request-nominal.json").read_text())
        stretch = json.loads((PEX / "request-stretch.json").read_text())

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


if __name__ == "__main__":
    unittest.main()
