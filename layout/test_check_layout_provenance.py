#!/usr/bin/env python3
"""Regression tests for check_layout_provenance.py (issues #463, #528).

Stdlib only; builds throwaway repos under a temp dir, no klt, no PDK, no
KLayout. Covers each pinned hash (layout / source netlist / generator)
independently, the all-match pass, a missing artifact, missing and malformed
provenance, malformed provenance blocks, the klt-version arm's advisory
behaviour (drift, match, absent binary, failing ``--version``), the
``generator_deps`` arm pinning the generator's ``layout/common/`` import
closure (#528), and a smoke check of the committed tree.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import check_layout_provenance as c

PROVENANCE_REL = "layout/gate_driver_core.provenance.json"

# A minimal but *parseable* generator plus its layout/common/ dependencies:
# since #517 the real generator imports klt_env/klt_report from common/, and
# the #528 arm derives the pinned set by walking exactly these imports.
GEN_SRC = b"import argparse\nimport klt_env\nimport klt_report\n"
KLT_ENV_SRC = b"import shutil\n"
KLT_REPORT_SRC = b"import json\nimport klt_env\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Repo:
    """A scratch repo root with a provenance file and its pinned inputs."""

    def __init__(self, tmp: str):
        self.root = Path(tmp).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, rel: str, data: bytes | str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return path

    def artifacts(self) -> None:
        self.write("layout/gate_driver_core.gds", b"GDS-BYTES")
        self.write("design/netlist/gate_driver_core.spice", b"NETLIST-BYTES")
        self.write("layout/gen_gate_driver_core.py", GEN_SRC)
        self.write("layout/common/klt_env.py", KLT_ENV_SRC)
        self.write("layout/common/klt_report.py", KLT_REPORT_SRC)

    def provenance(self, *drops: str, **overrides) -> str:
        doc: dict = {
            "top_cell": "gate_driver_core",
            "layout": {
                "path": "layout/gate_driver_core.gds",
                "sha256": sha(b"GDS-BYTES"),
            },
            "source_netlist": {
                "path": "design/netlist/gate_driver_core.spice",
                "sha256": sha(b"NETLIST-BYTES"),
            },
            "generator": {
                "path": "layout/gen_gate_driver_core.py",
                "sha256": sha(GEN_SRC),
            },
            "generator_deps": [
                {
                    "module": "klt_env",
                    "path": "layout/common/klt_env.py",
                    "sha256": sha(KLT_ENV_SRC),
                },
                {
                    "module": "klt_report",
                    "path": "layout/common/klt_report.py",
                    "sha256": sha(KLT_REPORT_SRC),
                },
            ],
            "tools": {"klt_version": "klt 0.7.1.dev2599+geaf26f00df36"},
        }
        for key in drops:
            doc.pop(key, None)
        doc.update(overrides)
        self.write(PROVENANCE_REL, json.dumps(doc, indent=2))
        return PROVENANCE_REL

    def check(self, klt_runner=c.klt_version) -> tuple[int, str]:
        return c.run_check(
            self.root / PROVENANCE_REL,
            repo_root=self.root,
            klt_runner=klt_runner,
        )


NO_KLT = lambda binary: None  # noqa: E731 - klt absent from PATH


class HashFreshness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.artifacts()

    def test_all_match_passes(self):
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_layout_hash_mismatch_names_the_artifact(self):
        self.r.write("layout/gate_driver_core.gds", b"GDS-BYTES-CHANGED")
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("layout/gate_driver_core.gds", out)

    def test_source_netlist_hash_mismatch_names_the_artifact(self):
        self.r.write("design/netlist/gate_driver_core.spice", b"NETLIST-MOVED")
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("design/netlist/gate_driver_core.spice", out)

    def test_generator_hash_mismatch_names_the_artifact(self):
        # The #466 scenario: the generator is edited, provenance is not
        # refreshed, and before #463 nothing noticed.
        self.r.write("layout/gen_gate_driver_core.py", b"GENERATOR-EDITED")
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("layout/gen_gate_driver_core.py", out)
        self.assertIn("generator", out)

    def test_missing_artifact_is_a_named_failure(self):
        (self.r.root / "layout/gen_gate_driver_core.py").unlink()
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("layout/gen_gate_driver_core.py", out)

    def test_missing_provenance_fails_without_traceback(self):
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("cannot read", out)
        self.assertNotIn("Traceback", out)

    def test_malformed_provenance_fails_without_traceback(self):
        self.r.write(PROVENANCE_REL, "{not json")
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("cannot read", out)
        self.assertNotIn("Traceback", out)

    def test_block_without_hash_is_a_failure(self):
        self.r.provenance(generator={"path": "layout/gen_gate_driver_core.py"})
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("generator", out)

    def test_block_without_path_is_a_failure(self):
        self.r.provenance(source_netlist={"sha256": sha(b"NETLIST-BYTES")})
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("source_netlist", out)

    def test_absolute_pinned_path_is_rejected(self):
        self.r.provenance(
            generator={"path": "/etc/passwd", "sha256": sha(GEN_SRC)}
        )
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("generator", out)


class KltVersionArm(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.artifacts()
        self.r.provenance()  # records klt 0.7.1.dev2599+geaf26f00df36

    def test_drift_is_advisory_only(self):
        # The host condition on every sweep box: recorded 0.7.1, host 0.9.2.
        # Per #470 drift is the normal condition, not an error -- the arm
        # prints the drift and its consequence and stays exit zero.
        host = lambda binary: "klt 0.9.2.dev1029+g76f47afa48f1"  # noqa: E731
        code, out = self.r.check(klt_runner=host)
        self.assertEqual(code, 0, out)
        self.assertIn("0.7.1.dev2599", out)
        self.assertIn("0.9.2", out)
        self.assertIn("byte-equality", out.lower())

    def test_matching_version_prints_no_drift(self):
        same = lambda binary: "klt 0.7.1.dev2599+geaf26f00df36"  # noqa: E731
        code, out = self.r.check(klt_runner=same)
        self.assertEqual(code, 0, out)
        self.assertNotIn("drift", out.lower())

    def test_absent_klt_is_skipped_cleanly(self):
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertEqual(code, 0, out)
        self.assertIn("skip", out.lower())

    def test_failing_klt_version_is_skipped_cleanly(self):
        def failing(binary):
            raise c.KltVersionError("klt --version exited 1")

        code, out = self.r.check(klt_runner=failing)
        self.assertEqual(code, 0, out)
        self.assertIn("skip", out.lower())


class GeneratorDepsPin(unittest.TestCase):
    """The #528 arm: the generator's ``layout/common/`` import closure is pinned.

    After PR #517 the generator's klt argv assembly lives in
    ``common/klt_report.py`` and its binary resolution in ``common/klt_env.py``
    while only ``gen_gate_driver_core.py`` itself was pinned -- an edit to
    either helper changed what the generator runs without tripping any pin.
    The checker must derive the closure from the live generator (not trust a
    hand-listed record) and fail on every drift direction.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.artifacts()

    def test_fresh_deps_pass(self):
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertEqual(code, 0, out)

    def test_missing_generator_deps_block_fails_naming_the_modules(self):
        self.r.provenance("generator_deps")
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("generator_deps", out)
        self.assertIn("klt_env", out)
        self.assertIn("klt_report", out)

    def test_dep_hash_mismatch_names_the_file(self):
        # The pre-#528 gap: a klt_report edit changed what the generator runs
        # while every recorded hash still matched.
        self.r.write(
            "layout/common/klt_report.py",
            b"import json\nimport klt_env\n# argv edit\n",
        )
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("generator_deps", out)
        self.assertIn("layout/common/klt_report.py", out)

    def test_missing_dep_file_fails(self):
        (self.r.root / "layout/common/klt_env.py").unlink()
        self.r.provenance()
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("layout/common/klt_env.py", out)

    def test_generator_gaining_a_common_import_requires_a_new_pin(self):
        # The generator edit itself is attested (its own pin records the new
        # bytes); the import it gained is not -- the checker derives the
        # closure, so a hand-listed record cannot stay small.
        src = b"import klt_env\nimport klt_report\nimport power_array_folded\n"
        self.r.write("layout/gen_gate_driver_core.py", src)
        self.r.write("layout/common/power_array_folded.py", b"import math\n")
        self.r.provenance(
            generator={
                "path": "layout/gen_gate_driver_core.py",
                "sha256": sha(src),
            }
        )
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("power_array_folded", out)

    def test_transitive_common_import_is_pinned(self):
        # klt_report imports klt_env: a generator importing only klt_report
        # still depends on both files' bytes, so both must be pinned.
        src = b"import klt_report\n"
        self.r.write("layout/gen_gate_driver_core.py", src)
        self.r.provenance(
            generator={
                "path": "layout/gen_gate_driver_core.py",
                "sha256": sha(src),
            }
        )
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertEqual(code, 0, out)

    def test_stale_recorded_dep_fails(self):
        # The mirror direction: the generator dropped an import but the
        # record still pins it -- the provenance misdescribes the build.
        src = b"import klt_env\n"
        self.r.write("layout/gen_gate_driver_core.py", src)
        self.r.provenance(
            generator={
                "path": "layout/gen_gate_driver_core.py",
                "sha256": sha(src),
            }
        )
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("klt_report", out)

    def test_generator_without_common_imports_needs_no_deps(self):
        src = b"import argparse\n"
        self.r.write("layout/gen_gate_driver_core.py", src)
        self.r.provenance(
            "generator_deps",
            generator={
                "path": "layout/gen_gate_driver_core.py",
                "sha256": sha(src),
            },
        )
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertEqual(code, 0, out)

    def test_dep_path_escape_is_a_failure(self):
        self.r.provenance(
            generator_deps=[
                {
                    "module": "klt_env",
                    "path": "../outside.py",
                    "sha256": sha(KLT_ENV_SRC),
                },
                {
                    "module": "klt_report",
                    "path": "layout/common/klt_report.py",
                    "sha256": sha(KLT_REPORT_SRC),
                },
            ]
        )
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("generator_deps", out)

    def test_dep_recorded_under_the_wrong_path_fails(self):
        self.r.provenance(
            generator_deps=[
                {
                    "module": "klt_env",
                    "path": "layout/common/klt_report.py",
                    "sha256": sha(KLT_REPORT_SRC),
                },
                {
                    "module": "klt_report",
                    "path": "layout/common/klt_report.py",
                    "sha256": sha(KLT_REPORT_SRC),
                },
            ]
        )
        code, out = self.r.check(klt_runner=NO_KLT)
        self.assertNotEqual(code, 0)
        self.assertIn("klt_env", out)


class CommittedTree(unittest.TestCase):
    """Smoke check against the real repo: the recorded hashes match."""

    def test_committed_provenance_is_fresh(self):
        code, out = c.run_check(
            c.PROVENANCE, repo_root=c.REPO_ROOT, klt_runner=NO_KLT
        )
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
