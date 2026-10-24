"""Issue #348: signoff outputs go through the artifact store and fail closed.

Stdlib only. ``klt artifact put`` is emulated by the same fake the sim writer's
tests use (``sim/test_evidence_store.py``).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "sim"))

import signoff_store as ss  # noqa: E402
from test_evidence_store import fake_klt  # noqa: E402


class SignoffStore(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.bench, self.rid = "layout-lvs-blk", "20260101-000000-abc1234"
        self.stage = ss.stage_dir(self.root, self.bench, self.rid)
        (self.stage / f"{self.rid}.lvs.txt").write_text("text twin\n")
        (self.stage / f"{self.rid}.lvs-request.json").write_text("{}\n")
        self.store = {}
        self.mpath = self.root / f"manifests/artifacts/{self.bench}-{self.rid}.manifest.json"

    def put(self, **kw):
        return lambda files, root: ss.es.put_files(files, root, run=fake_klt(self.store, **kw))

    def store_run(self, **kw):
        return ss.store(self.stage, repo_root=self.root, bench=self.bench, rid=self.rid,
                        name_prefix="layout/lvs/reports/blk", put=self.put(**kw))

    def test_stores_bytes_and_commits_manifest_only(self):
        self.assertEqual(self.store_run(), self.mpath)
        names = [e["name"] for e in json.loads(self.mpath.read_text())["entries"]]
        self.assertEqual(names, [f"layout/lvs/reports/blk/{self.rid}.lvs-request.json",
                                 f"layout/lvs/reports/blk/{self.rid}.lvs.txt"])
        self.assertEqual(len(self.store), 2)
        self.assertFalse((self.root / "layout/lvs/reports").exists())  # no bytes in git

    def test_store_failure_is_fail_closed(self):
        with self.assertRaises(ss.StoreError):
            self.store_run(fail="broker_unreachable")
        self.assertFalse(self.mpath.exists())
        self.assertTrue((self.stage / f"{self.rid}.lvs.txt").exists())  # staged bytes kept

    def test_store_or_exit_exits_not_stored_and_commits_nothing(self):
        with self.assertRaises(SystemExit) as cm:
            ss.store_or_exit(self.stage, repo_root=self.root, bench=self.bench, rid=self.rid,
                             name_prefix="layout/lvs/reports/blk",
                             put=self.put(fail="broker_unreachable"))
        self.assertEqual(cm.exception.code, ss.EXIT_NOT_STORED)
        self.assertFalse(self.mpath.exists())

    def test_never_overwrites_a_manifest(self):
        self.mpath.parent.mkdir(parents=True)
        self.mpath.write_text("{}")
        with self.assertRaises(ss.StoreError):
            self.store_run()
        self.assertEqual(self.mpath.read_text(), "{}")
        self.assertEqual(self.store, {})

    def test_preflight_without_broker_exits(self):
        import os
        old = os.environ.pop(ss.es.ENV_BROKER, None)
        self.addCleanup(lambda: old is None or os.environ.__setitem__(ss.es.ENV_BROKER, old))
        with self.assertRaises(SystemExit) as cm:
            ss.preflight_or_exit(self.root)
        self.assertEqual(cm.exception.code, ss.EXIT_NOT_STORED)

    def test_new_record_id_skips_claimed_manifest_and_stage(self):
        import datetime as dt
        when = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        rid = ss.new_record_id(self.root, self.bench, self.root / "r", when, "abc1234")
        self.assertEqual(rid, "20260101-000001-abc1234")  # 000000 has a stage dir


if __name__ == "__main__":
    unittest.main()
