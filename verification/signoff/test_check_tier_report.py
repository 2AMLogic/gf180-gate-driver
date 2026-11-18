#!/usr/bin/env python3
"""Regression tests for check_tier_report.py's pin anchoring (issue #288).

Stdlib only; builds throwaway repos under a temp dir, no klt, no PDK. Covers
the artifact-bound generic bindings (envelope-relative string path,
repo-scoped object path, malformed/missing/stale/wrong-item cases,
``source`` unable to redirect an explicit binding), the legacy item-8
``source`` fallback, a compound item-11-style list, the inventory
listed-hash check, and a smoke check of the committed tree.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import check_tier_report as c


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class Repo:
    """A scratch repo root with helpers to lay down artifacts and envelopes."""

    def __init__(self, tmp: str):
        self.root = Path(tmp).resolve()

    def write(self, rel: str, data: bytes | str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return path

    def envelope(self, rel: str, item: int | None, input_path, artifact_rel: str | None, source: str | None = None,
                 hash_override: str | None = None) -> str:
        env: dict = {"schema_version": 1, "kind": "generic", "status": "pass"}
        if item is not None:
            env["t1_item"] = item
        if source is not None:
            env["source"] = source
        inp: dict = {}
        if artifact_rel is not None:
            inp["content_hash"] = hash_override or sha((self.root / artifact_rel).read_bytes())
        if input_path is not None:
            inp["path"] = input_path
        env["provenance"] = {"input": inp}
        self.write(rel, json.dumps(env))
        return rel

    def manifest(self, **items) -> dict:
        return {"evidence": items}

    def anchor(self, manifest: dict) -> list[str]:
        return c.anchor_citations(manifest, repo_root=self.root)


class ArtifactBoundGeneric(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.write("layout/a.gds", b"GDS-BYTES")
        self.pin = sha(b"GDS-BYTES")

    def cite(self, item: int, env_rel: str, pin: str | None = None) -> dict:
        entry = {"file": env_rel}
        if pin is not False:
            entry["content_hash"] = pin or self.pin
        return self.r.manifest(**{str(item): entry})

    def test_repo_scoped_object_path_passes(self):
        env = self.r.envelope("sig/e.json", 2, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds")
        self.assertEqual(self.r.anchor(self.cite(2, env)), [])

    def test_string_path_resolves_beside_envelope(self):
        self.r.write("sig/inv.md", "x")
        pin = sha(b"x")
        env = self.r.envelope("sig/e.json", 1, "inv.md", "sig/inv.md")
        self.assertEqual(self.r.anchor(self.cite(1, env, pin)), [])

    def test_string_path_is_not_repo_relative(self):
        # "layout/a.gds" beside sig/ does not exist -> missing, not silently repo-relative.
        env = self.r.envelope("sig/e.json", 2, "layout/a.gds", "layout/a.gds")
        failures = self.r.anchor(self.cite(2, env))
        self.assertTrue(any("does not exist" in f for f in failures), failures)

    def test_stale_artifact_fails(self):
        env = self.r.envelope("sig/e.json", 2, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds")
        manifest = self.cite(2, env)
        self.r.write("layout/a.gds", b"EDITED")
        failures = self.r.anchor(manifest)
        self.assertTrue(any("stale citation" in f for f in failures), failures)

    def test_restoring_artifact_passes_again(self):
        env = self.r.envelope("sig/e.json", 2, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds")
        manifest = self.cite(2, env)
        self.r.write("layout/a.gds", b"EDITED")
        self.assertTrue(self.r.anchor(manifest))
        self.r.write("layout/a.gds", b"GDS-BYTES")
        self.assertEqual(self.r.anchor(manifest), [])

    def test_missing_artifact_fails(self):
        env = self.r.envelope("sig/e.json", 2, {"path": "layout/gone.gds", "scope": "repo"}, None)
        failures = self.r.anchor(self.cite(2, env))
        self.assertTrue(any("does not exist" in f for f in failures), failures)

    def test_missing_manifest_pin_fails(self):
        env = self.r.envelope("sig/e.json", 2, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds")
        failures = self.r.anchor(self.cite(2, env, pin=False))
        self.assertTrue(any("pins no content_hash" in f for f in failures), failures)

    def test_wrong_t1_item_fails(self):
        env = self.r.envelope("sig/e.json", 10, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds")
        failures = self.r.anchor(self.cite(2, env))
        self.assertTrue(any("declares t1_item" in f for f in failures), failures)

    def test_missing_or_nonint_t1_item_fails(self):
        for item in (None, True):
            env = self.r.envelope("sig/e.json", None, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds")
            if item is True:
                data = json.loads((self.r.root / env).read_text())
                data["t1_item"] = True
                self.r.write(env, json.dumps(data))
            failures = self.r.anchor(self.cite(1, env))
            self.assertTrue(any("declares t1_item" in f for f in failures), (item, failures))

    def test_malformed_declared_paths_fail_without_source_fallback(self):
        bad = [
            7,
            "",
            {"path": "layout/a.gds"},  # no scope
            {"path": "layout/a.gds", "scope": "envelope"},
            {"path": "", "scope": "repo"},
            {"path": 3, "scope": "repo"},
            {"path": "/etc/passwd", "scope": "repo"},
            {"path": "../outside.bin", "scope": "repo"},
        ]
        for declared in bad:
            # `source` points at a perfectly valid, correctly pinned file: a
            # malformed declared binding must still fail rather than fall back.
            env = self.r.envelope("sig/e.json", 2, declared, "layout/a.gds", source="layout/a.gds")
            failures = self.r.anchor(self.cite(2, env))
            self.assertTrue(failures, f"declared path {declared!r} was accepted")

    def test_source_cannot_redirect_an_explicit_binding(self):
        self.r.write("layout/other.gds", b"OTHER")
        env = self.r.envelope("sig/e.json", 2, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds",
                              source="layout/other.gds")
        # pin matches the declared artifact; passes and is unaffected by `source`.
        self.assertEqual(self.r.anchor(self.cite(2, env)), [])
        # a pin of the `source` file must NOT be accepted for the declared artifact.
        failures = self.r.anchor(self.cite(2, env, pin=sha(b"OTHER")))
        self.assertTrue(any("stale citation" in f for f in failures), failures)


class LegacyAndCompound(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.write("design/report.md", "report")

    def test_item8_source_fallback_still_anchors(self):
        env = {"schema_version": 1, "kind": "generic", "status": "pass", "source": "design/report.md",
               "provenance": {"input": {"content_hash": sha(b"report")}}}
        self.r.write("sig/c.json", json.dumps(env))
        manifest = self.r.manifest(**{"8": {"file": "sig/c.json", "content_hash": sha(b"report")}})
        self.assertEqual(self.r.anchor(manifest), [])
        self.r.write("design/report.md", "edited")
        self.assertTrue(any("stale citation" in f for f in self.r.anchor(manifest)))

    def test_item8_without_source_fails(self):
        env = {"schema_version": 1, "kind": "generic", "status": "pass", "provenance": {"input": {}}}
        self.r.write("sig/c.json", json.dumps(env))
        manifest = self.r.manifest(**{"8": {"file": "sig/c.json", "content_hash": sha(b"report")}})
        self.assertTrue(any("names no input path" in f for f in self.r.anchor(manifest)))

    def test_compound_item_anchors_each_half(self):
        self.r.write("layout/a.gds", b"GDS")
        a = self.r.envelope("sig/a.json", 11, {"path": "layout/a.gds", "scope": "repo"}, "layout/a.gds")
        legacy = {"schema_version": 1, "kind": "generic", "status": "pass", "source": "design/report.md",
                  "provenance": {"input": {"content_hash": sha(b"report")}}}
        self.r.write("sig/b.json", json.dumps(legacy))
        manifest = self.r.manifest(**{"11": [
            {"file": a, "content_hash": sha(b"GDS")},
            {"file": "sig/b.json", "content_hash": sha(b"report")},
        ]})
        self.assertEqual(self.r.anchor(manifest), [])
        self.r.write("design/report.md", "edited")
        failures = self.r.anchor(manifest)
        self.assertEqual(len(failures), 1)
        self.assertIn("item 11[1]", failures[0])


class NativeEnvelopeRepoScopedInput(unittest.TestCase):
    """klt 0.7 drc/erc/lvs envelopes name their input as ``{path, scope: repo}``."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.write("layout/a.gds", b"GDS")
        self.pin = sha(b"GDS")

    def drc(self, file_field):
        self.r.write("layout/drc/r.json", json.dumps({"violations": [], "file": file_field}))
        return self.r.manifest(**{"3": {"file": "layout/drc/r.json", "content_hash": self.pin}})

    def test_repo_scoped_object_input_anchors(self):
        manifest = self.drc({"path": "layout/a.gds", "scope": "repo"})
        self.assertEqual(self.r.anchor(manifest), [])

    def test_repo_scoped_object_input_detects_a_stale_artifact(self):
        manifest = self.drc({"path": "layout/a.gds", "scope": "repo"})
        self.r.write("layout/a.gds", b"EDITED")
        failures = self.r.anchor(manifest)
        self.assertEqual(len(failures), 1)
        self.assertIn("stale citation", failures[0])

    def test_external_scope_object_names_no_usable_input(self):
        manifest = self.drc({"path": None, "scope": "external"})
        self.assertTrue(any("names no input path" in f for f in self.r.anchor(manifest)))


class SimEnvelopeNetlistClosure(unittest.TestCase):
    """``klt sim`` envelopes anchor on the body netlist and on every repo file it simulated (issue #367)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.write("sim/k/body.spice", b"BODY")
        self.r.write("design/dut.spice", b"DUT")
        self.pin = sha(b"BODY")
        closure = [
            {"path": "sim/k/body.spice", "scope": "repo", "sha256": hashlib.sha256(b"BODY").hexdigest()},
            {"path": "design/dut.spice", "scope": "repo", "sha256": hashlib.sha256(b"DUT").hexdigest()},
        ]
        env = {
            "schema_version": 3,
            "netlist": {"path": "sim/k/body.spice", "scope": "repo"},
            "corner_count": 1,
            "measurements": [],
            "environment": {"netlist_closure": closure},
        }
        self.r.write("sim/k/env.json", json.dumps(env))
        self.manifest = self.r.manifest(**{"5": [{"file": "sim/k/env.json", "content_hash": self.pin}]})

    def test_fresh_envelope_anchors(self):
        self.assertEqual(self.r.anchor(self.manifest), [])

    def test_editing_the_body_netlist_is_stale(self):
        self.r.write("sim/k/body.spice", b"EDITED")
        self.assertTrue(any("stale citation" in f for f in self.r.anchor(self.manifest)))

    def test_editing_the_included_dut_is_stale(self):
        self.r.write("design/dut.spice", b"EDITED")
        failures = self.r.anchor(self.manifest)
        self.assertEqual(len(failures), 1)
        self.assertIn("stale simulation input design/dut.spice", failures[0])

    def test_missing_closure_fails(self):
        env = json.loads((self.r.root / "sim/k/env.json").read_text())
        del env["environment"]["netlist_closure"]
        self.r.write("sim/k/env.json", json.dumps(env))
        self.assertTrue(any("netlist_closure" in f for f in self.r.anchor(self.manifest)))


class YieldReportSamplesInput(unittest.TestCase):
    """A ``klt yield`` report names its sample set beside itself (issue #368)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.write("verification/signoff/yield/s.samples.json", b"SAMPLES")
        self.r.write("verification/signoff/yield/s.yield.json",
                     json.dumps({"samples": "s.samples.json", "measurement_count": 1, "measurements": []}))
        self.manifest = self.r.manifest(**{"6": [{"file": "verification/signoff/yield/s.yield.json",
                                                  "content_hash": sha(b"SAMPLES"), "rows": ["a"]}]})

    def test_samples_beside_report_anchor(self):
        self.assertEqual(self.r.anchor(self.manifest), [])

    def test_edited_samples_fail(self):
        self.r.write("verification/signoff/yield/s.samples.json", b"EDITED")
        failures = self.r.anchor(self.manifest)
        self.assertEqual(len(failures), 1)
        self.assertIn("stale citation", failures[0])

    def test_missing_samples_fail(self):
        (self.r.root / "verification/signoff/yield/s.samples.json").unlink()
        self.assertTrue(any("does not exist" in f for f in self.r.anchor(self.manifest)))


class InventoryListedHashes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = Repo(self._tmp.name)
        self.r.write("design/x.sch", "sch")
        self.r.write("sim/pdk.json", "pdk")
        inv = (
            "| `design/x.sch` | `%s` |\n"
            "PDK: `sim/pdk.json` (sha256\n  `%s`)\n" % (sha(b"sch"), sha(b"pdk"))
        )
        self.r.write("sig/d.inventory.md", inv)
        self.pin = sha(inv.encode())
        env = self.r.envelope("sig/d.generic.json", 1,
                              {"path": "sig/d.inventory.md", "scope": "repo"}, "sig/d.inventory.md")
        self.manifest = self.r.manifest(**{"1": {"file": env, "content_hash": self.pin}})

    def refresh_pin(self):
        self.manifest["evidence"]["1"]["content_hash"] = sha((self.r.root / "sig/d.inventory.md").read_bytes())
        self.r.envelope("sig/d.generic.json", 1, {"path": "sig/d.inventory.md", "scope": "repo"}, "sig/d.inventory.md")

    def test_clean_inventory_passes(self):
        self.assertEqual(self.r.anchor(self.manifest), [])

    def test_editing_a_listed_source_fails(self):
        self.r.write("design/x.sch", "edited")
        failures = self.r.anchor(self.manifest)
        self.assertTrue(any("stale listing for design/x.sch" in f for f in failures), failures)

    def test_listed_file_missing_fails(self):
        (self.r.root / "sim/pdk.json").unlink()
        failures = self.r.anchor(self.manifest)
        self.assertTrue(any("listed file does not exist" in f for f in failures), failures)

    def test_inventory_with_no_listed_hashes_fails(self):
        self.r.write("sig/d.inventory.md", "nothing hashed here")
        self.refresh_pin()
        failures = self.r.anchor(self.manifest)
        self.assertTrue(any("lists no" in f for f in failures), failures)

    def test_editing_the_inventory_without_refresh_fails(self):
        text = (self.r.root / "sig/d.inventory.md").read_text()
        self.r.write("sig/d.inventory.md", text + "\nextra\n")
        failures = self.r.anchor(self.manifest)
        self.assertTrue(any("stale citation" in f for f in failures), failures)


class CommittedTree(unittest.TestCase):
    def test_committed_manifest_is_anchored(self):
        manifest = json.loads(c.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(c.anchor_citations(manifest), [])

    def test_inventory_paths_exist(self):
        for name in ("design-sources.inventory.md", "testbenches.inventory.md"):
            text = (c.SIGNOFF_DIR / name).read_text(encoding="utf-8")
            for path in set(__import__("re").findall(r"`((?:design|sim|layout|spec|verification)/[\w./-]+\.\w+)`", text)):
                self.assertTrue((c.REPO_ROOT / path).is_file(), f"{name} names a missing file: {path}")


class KltAttestItem10Inventory(unittest.TestCase):
    """End-to-end item-10 cases against the real grader (issue #511).

    The comment-neutrality of the ``ci.yml`` pin lives in klt's
    ``sha256-canonical-yaml-v1`` digest, not in this repo's checker -- the
    grader owns the algorithm and the repo duplicates none of it. So these
    tests drive ``klt signoff --attest`` and ``klt signoff --manifest`` in a
    throwaway git repo and grade the fresh render's item-10 row: a
    comment-only edit and a step added to an unrelated job stay ``met`` with
    no chain edit, while a gate change inside ``jobs.signoff`` and an
    un-refreshed raw-byte entry go ``unmet``/``stale_evidence``. Skipped
    when ``klt`` is not on PATH (CI's signoff job installs the pinned
    build, so this runs there); the checker's own pass-1 anchoring of the
    producer's envelope shape is asserted without klt below.
    """

    SCRATCH_CI = """\
name: scratch-ci
on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Unit tests
        run: echo unit-tests
  signoff:
    runs-on: ubuntu-latest
    steps:
      - name: Install klt
        run: pip install klt
      - name: Grade
        run: python3 verification/signoff/check_tier_report.py
"""

    SCRATCH_README = b"scratch readme\n"

    SCRATCH_INVENTORY = {
        "schema_version": 1,
        "kind": "t1-attestation-inventory",
        "t1_item": 10,
        "hygiene": [
            "README.md",
            {
                "path": ".github/workflows/ci.yml",
                "attest": "yaml",
                "select": "jobs.signoff",
            },
        ],
        "checks": [{"name": "ok", "argv": ["python3", "-c", "pass"]}],
    }

    @classmethod
    def setUpClass(cls):
        cls.klt = shutil.which("klt")
        if cls.klt is None:
            raise unittest.SkipTest(
                "klt not on PATH (CI's signoff job installs the pinned grader)"
            )
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.root = Path(cls._tmp.name).resolve()
        (cls.root / ".github/workflows").mkdir(parents=True)
        (cls.root / "attest").mkdir()
        (cls.root / ".github/workflows/ci.yml").write_bytes(cls.SCRATCH_CI.encode())
        (cls.root / "README.md").write_bytes(cls.SCRATCH_README)
        inventory = cls.root / "attest/item10.json"
        inventory.write_text(json.dumps(cls.SCRATCH_INVENTORY, indent=2) + "\n")
        # The grader's grading basis is the git index (klayout-tools #5857):
        # an untracked candidate is dropped, so stage everything first.
        subprocess.run(["git", "init", "-q"], cwd=cls.root, check=True)
        cls._git("add", "-A")
        proc = cls.klt_run(
            "signoff", "--attest", "10",
            "--inventory", "attest/item10.json",
            "-o", "attest/item10-envelope.json",
        )
        if proc.returncode != 0:
            if "unrecognized arguments" in (proc.stderr or ""):
                raise unittest.SkipTest(
                    "installed klt predates --attest (issue #511 needs the pinned build)"
                )
            raise AssertionError(f"attest failed in the scratch repo: {proc.stderr}")
        manifest = {
            "block": "scratch",
            "kind": "analog",
            "evidence": {
                "10": {
                    "file": "attest/item10-envelope.json",
                    "content_hash": sha(inventory.read_bytes()),
                }
            },
        }
        (cls.root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        cls.manifest = manifest
        cls._git("add", "-A")

    @classmethod
    def _git(cls, *args):
        subprocess.run(["git", *args], cwd=cls.root, check=True, capture_output=True)

    @classmethod
    def klt_run(cls, *argv):
        return subprocess.run(
            [cls.klt, *argv], cwd=cls.root, capture_output=True, text=True, check=False
        )

    @classmethod
    def item10(cls):
        proc = cls.klt_run("signoff", "--manifest", "manifest.json", "--format", "json")
        if proc.returncode not in (0, 3):
            raise AssertionError(f"render failed: {proc.stderr}")
        report = json.loads(proc.stdout)
        row = next(item for item in report["items"] if item.get("id") == 10)
        return row.get("status"), row.get("reason")

    def setUp(self):
        (self.root / ".github/workflows/ci.yml").write_bytes(self.SCRATCH_CI.encode())
        (self.root / "README.md").write_bytes(self.SCRATCH_README)

    def test_baseline_envelope_is_met(self):
        self.assertEqual(self.item10(), ("met", None))

    def test_comment_only_ci_edit_stays_met_with_no_chain_edit(self):
        path = self.root / ".github/workflows/ci.yml"
        path.write_bytes(self.SCRATCH_CI.encode() + b"\n# a pure comment\n")
        self.assertEqual(self.item10(), ("met", None))

    def test_key_reorder_stays_met(self):
        text = self.SCRATCH_CI.replace(
            "  push:\n  pull_request:\n", "  pull_request:\n  push:\n"
        )
        self.assertNotEqual(text, self.SCRATCH_CI)
        (self.root / ".github/workflows/ci.yml").write_text(text)
        self.assertEqual(self.item10(), ("met", None))

    def test_step_added_to_an_unrelated_job_stays_met(self):
        text = self.SCRATCH_CI.replace(
            "      - name: Unit tests\n        run: echo unit-tests",
            "      - name: Unit tests\n        run: echo unit-tests\n"
            "      - name: One more suite\n        run: echo more",
        )
        self.assertNotEqual(text, self.SCRATCH_CI)
        (self.root / ".github/workflows/ci.yml").write_text(text)
        self.assertEqual(self.item10(), ("met", None))

    def test_gate_change_inside_signoff_job_is_stale_evidence(self):
        text = self.SCRATCH_CI.replace(
            "      - name: Grade\n",
            "      - name: Grade\n        continue-on-error: true\n",
        )
        self.assertNotEqual(text, self.SCRATCH_CI)
        (self.root / ".github/workflows/ci.yml").write_text(text)
        self.assertEqual(self.item10(), ("unmet", "stale_evidence"))

    def test_raw_byte_entry_edit_without_refresh_is_stale_evidence(self):
        (self.root / "README.md").write_bytes(self.SCRATCH_README + b"edited\n")
        self.assertEqual(self.item10(), ("unmet", "stale_evidence"))

    def test_checker_pass1_anchors_the_producer_envelope(self):
        # The producer's generic envelope shape (attestation block, repo-scoped
        # provenance.input.path naming the attest inventory) anchors through the
        # checker's existing declared-input rule; the JSON inventory is not a
        # `.inventory.md`, so no markdown pair re-hash runs against it -- the
        # grader's live re-hash in the render above is the freshness gate.
        self.assertEqual(c.anchor_citations(self.manifest, repo_root=self.root), [])


if __name__ == "__main__":
    unittest.main()
