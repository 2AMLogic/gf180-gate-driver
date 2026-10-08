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


if __name__ == "__main__":
    unittest.main()
