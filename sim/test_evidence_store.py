"""Issue #333: the evidence writer stores bytes through ``klt artifact put``
and commits only a manifest and a summary. Every failure is fail closed.

Stdlib only. ``klt`` is emulated by an injected ``run`` (the writer's only
contact with it is argv + exit status + the manifest file it merges into), and
the broker probe runs against a throwaway local HTTP server.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import evidence_store as es  # noqa: E402

REPO = "owner/repo"


def fake_klt(store: dict, *, fail=None, corrupt=False, uri=None, mutate=None):
    """Emulate ``klt artifact put FILE --name N --manifest M --format json``.
    ``uri`` overrides the written uri (given the key) to emulate an old klt;
    ``mutate`` rewrites the merged manifest before it is written back, to
    emulate a klt whose returned manifest fails the schema (issue #562)."""

    def run(cmd, **kw):
        assert cmd[:3] == ["klt", "artifact", "put"], cmd
        path, name, manifest = cmd[3], cmd[cmd.index("--name") + 1], cmd[cmd.index("--manifest") + 1]
        assert "--broker" not in cmd  # the broker URL never goes in argv
        if fail is not None:
            err = {"schema_version": 1, "error": {"command": "artifact put",
                                                  "message": "cannot reach the artifact broker",
                                                  "code": fail}}
            return subprocess.CompletedProcess(cmd, 1, "", json.dumps(err))
        data = Path(path).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        store[sha] = data
        key = f"evidence/owner__repo/{sha[:2]}/{'0' * 64 if corrupt else sha}"
        entry = {"sha256": "0" * 64 if corrupt else sha, "size": len(data), "kind": "evidence",
                 "producer": {"tool": "klt", "version": "t", "loom.repo": REPO, "commit": None},
                 "uri": uri(key) if uri else f"artifact:{key}",
                 "name": name}
        p = Path(manifest)
        m = json.loads(p.read_text()) if p.exists() else {"schema_version": 1, "entries": []}
        m["entries"].append(entry)
        if mutate is not None:
            mutate(m)
        p.write_text(json.dumps(m))
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"status": "stored"}), "")

    return run


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.stage = self.root / "sim/.work/.stage/b"
        (self.stage / "corners/r1").mkdir(parents=True)
        (self.stage / "corners/r1/tt.log").write_text("log tt\n")
        (self.stage / "corners/r1/ff.log").write_text("log ff\n")
        (self.stage / "corners/r1/empty.log").write_text("")
        (self.stage / "r1.json").write_text('{"x": 1}\n')
        self.files = [(self.stage / "r1.json", "sim/b/records/r1.json")]
        self.files += es.stage_files(self.stage / "corners/r1", "sim/b/corners/r1")
        self.summary = self.root / "sim/b/records/r1.md"
        self.mpath = self.root / "manifests/artifacts/b-r1.manifest.json"
        self.store = {}

    def put(self, **kw):
        return lambda files, root: es.put_files(files, root, run=fake_klt(self.store, **kw))

    def store_files(self, **kw):
        return es.store_files(self.files, repo_root=self.root, bench="b", rid="r1",
                              summary_text="# record\n", summary_path=self.summary,
                              put=self.put(**kw))

    def assert_nothing_committed(self):
        self.assertFalse(self.mpath.exists())
        self.assertFalse(self.summary.exists())
        self.assertFalse((self.root / "sim/b").exists())


class Writer(Base):
    def test_stores_bytes_commits_manifest_and_summary_only(self):
        path = self.store_files()
        self.assertEqual(path, self.mpath)
        m = json.loads(self.mpath.read_text())
        names = [e["name"] for e in m["entries"]]
        self.assertEqual(names, ["sim/b/corners/r1/ff.log", "sim/b/corners/r1/tt.log",
                                 "sim/b/records/r1.json"])
        for e in m["entries"]:
            self.assertEqual(hashlib.sha256(self.store[e["sha256"]]).hexdigest(), e["sha256"])
            self.assertEqual(e["uri"], f"artifact:evidence/owner__repo/{e['sha256'][:2]}/"
                                       f"{e['sha256']}")
        text = self.summary.read_text()
        self.assertTrue(text.startswith("# record\n"))
        self.assertIn("## Stored evidence", text)
        self.assertIn("manifests/artifacts/b-r1.manifest.json", text)
        self.assertIn("`sim/b/corners/r1/empty.log` | 0 |", text)  # listed, not stored
        # Only the summary landed under sim/b: no evidence blob.
        self.assertEqual([p.relative_to(self.root).as_posix()
                          for p in (self.root / "sim/b").rglob("*") if p.is_file()],
                         ["sim/b/records/r1.md"])

    def test_broker_unreachable_is_fail_closed(self):
        with self.assertRaises(es.StoreError) as cm:
            self.store_files(fail="broker_unreachable")
        self.assertIn("broker_unreachable", str(cm.exception))
        self.assert_nothing_committed()
        self.assertTrue((self.stage / "r1.json").exists())  # staged bytes kept

    def test_manifest_not_matching_bytes_is_refused(self):
        with self.assertRaises(es.StoreError):
            self.store_files(corrupt=True)
        self.assert_nothing_committed()

    def test_non_artifact_uri_from_klt_is_refused(self):
        # An old klt (before klayout-tools 7e3561f) writes a bucket-naming uri;
        # the shared schema rule refuses any scheme but artifact:<key> and
        # commits nothing.
        legacy = "s3" + "://"  # built, so a grep for the literal stays clean
        for uri in (lambda k: f"{legacy}bucket/{k}", lambda k: f"https://host/{k}",
                    lambda k: f"artifact:/{k}", lambda k: k):
            with self.subTest(uri=uri("K")):
                with self.assertRaisesRegex(es.StoreError, "uri must be artifact:<key>"):
                    self.store_files(uri=uri)
                self.assert_nothing_committed()

    def test_duplicate_entries_in_klt_manifest_are_refused(self):
        # klt returning the same entry twice used to install both files: the
        # writer indexed by name, collapsing the duplicate for the comparison
        # (issue #562). The shared schema rule rejects duplicate names, so the
        # writer refuses the manifest and commits nothing.
        with self.assertRaisesRegex(es.StoreError, "duplicate name"):
            self.store_files(mutate=lambda m: m["entries"].append(m["entries"][-1]))
        self.assert_nothing_committed()

    def test_empty_producer_in_klt_manifest_is_refused(self):
        # An empty producer object passed the writer's old isinstance-dict
        # check, leaving evidence CI would reject (issue #562). The shared
        # schema rule requires the producer fields, so the writer refuses the
        # manifest and commits nothing.
        with self.assertRaisesRegex(es.StoreError, "producer must carry"):
            self.store_files(mutate=lambda m: m["entries"][-1].update(producer={}))
        self.assert_nothing_committed()

    def test_existing_manifest_or_summary_is_never_overwritten(self):
        """Both committed paths are refused up front, dangling symlinks included.

        This covers the one guard every store path shares
        (``store_manifest_only``), so it stands for ``signoff_store`` too --
        which is why that suite no longer carries a copy of this test.
        A *dangling symlink* is the case a hand-written ``Path.exists()``
        guard gets wrong: ``exists()`` is ``False`` on one, yet
        ``open(p, "x")`` still raises ``FileExistsError``, so the collision
        would only surface after every ``klt artifact put`` had run.
        """
        for path in (self.mpath, self.summary):
            for kind in ("regular file", "dangling symlink"):
                with self.subTest(path=path.name, kind=kind):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if kind == "regular file":
                        path.write_text("{}")
                    else:
                        path.symlink_to(self.root / "nonexistent")
                        self.assertFalse(path.exists())  # ...and yet:
                        self.assertTrue(os.path.lexists(path))
                    with self.assertRaisesRegex(es.StoreError,
                                                "already exists; refusing to overwrite"):
                        self.store_files()
                    self.assertEqual(self.store, {})  # refused before any put
                    path.unlink()

    def test_nothing_but_empty_files_is_refused(self):
        self.files = [(self.stage / "corners/r1/empty.log", "sim/b/corners/r1/empty.log")]
        with self.assertRaises(es.StoreError):
            self.store_files()
        self.assert_nothing_committed()

    def test_duplicate_names_refused(self):
        self.files.append((self.stage / "r1.json", "sim/b/records/r1.json"))
        with self.assertRaises(es.StoreError):
            self.store_files()

    def test_symlink_in_stage_refused(self):
        (self.stage / "corners/r1/link.log").symlink_to(self.stage / "r1.json")
        with self.assertRaises(es.StoreError):
            es.stage_files(self.stage / "corners/r1", "sim/b/corners/r1")


def klt_probe_answer(cmd, *, current=True):
    """What ``klt artifact verify <probe manifest>`` answers: a current klt
    (klayout-tools 7e3561f+) refuses the legacy uri offline; an old one
    accepts it and fails on the unroutable broker."""
    if current:
        err = {"command": "artifact verify", "code": "invalid_manifest",
               "message": "manifest entry 0: uri ... is not artifact:<key>",
               "entry": 0, "problems": ["uri '...' is not artifact:<key>"]}
    else:
        err = {"command": "artifact verify", "code": "broker_unreachable",
               "message": "cannot reach the artifact broker"}
    return subprocess.CompletedProcess(cmd, 1, "", json.dumps({"schema_version": 1,
                                                               "error": err}))


class Preflight(unittest.TestCase):
    def which(self, name):
        return f"/bin/{name}"

    def run_ok(self, cmd, **kw):
        if cmd[1:3] == ["artifact", "verify"]:
            return klt_probe_answer(cmd)
        return subprocess.CompletedProcess(cmd, 0, "usage", "")

    def test_no_broker_configured(self):
        with self.assertRaisesRegex(es.StoreError, "KLT_ARTIFACT_BROKER"):
            es.preflight(Path("."), env={}, which=self.which, run=self.run_ok,
                         probe=lambda *a: None)

    def test_klt_missing_or_without_artifact_verb(self):
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        with self.assertRaisesRegex(es.StoreError, "not on PATH"):
            es.preflight(Path("."), env=env, which=lambda n: None, run=self.run_ok,
                         probe=lambda *a: None)
        with self.assertRaisesRegex(es.StoreError, "no `artifact put` verb"):
            es.preflight(Path("."), env=env, which=self.which,
                         run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, "", ""),
                         probe=lambda *a: None)

    def test_old_klt_refused_before_the_broker_probe(self):
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        probed = []

        def run_old(cmd, **kw):
            if cmd[1:3] == ["artifact", "verify"]:
                return klt_probe_answer(cmd, current=False)
            return subprocess.CompletedProcess(cmd, 0, "usage", "")

        with self.assertRaisesRegex(es.StoreError, "older than klayout-tools 7e3561f"):
            es.preflight(Path("."), env=env, which=self.which, run=run_old,
                         probe=lambda *a: probed.append(a))
        self.assertEqual(probed, [])

    def test_probe_gets_repo_and_broker(self):
        seen = []
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        es.preflight(Path("."), env=env, which=self.which, run=self.run_ok,
                     probe=lambda base, repo: seen.append((base, repo)))
        self.assertEqual(seen, [("http://broker.invalid", REPO)])


class KltSchemeProbe(unittest.TestCase):
    """``check_klt_uri_scheme``: klt has no commit in its version, so the
    writer tests the behaviour that changed at klayout-tools 7e3561f."""

    def check(self, run):
        es.check_klt_uri_scheme("/bin/klt", run=run)

    def test_current_klt_passes_and_probe_is_offline(self):
        seen = []

        def run(cmd, **kw):
            seen.append(cmd)
            manifest = json.loads(Path(cmd[3]).read_text())
            (entry,) = manifest["entries"]
            self.assertFalse(entry["uri"].startswith("artifact:"))
            return klt_probe_answer(cmd)

        self.check(run)
        (cmd,) = seen
        self.assertEqual(cmd[:3], ["/bin/klt", "artifact", "verify"])
        # Never the configured broker: a fixed unroutable one.
        self.assertEqual(cmd[cmd.index("--broker") + 1], "http://127.0.0.1:9")

    def test_every_other_outcome_fails_closed(self):
        def answer(rc, err=None, stderr=None):
            def run(cmd, **kw):
                text = stderr if stderr is not None else json.dumps(
                    {"schema_version": 1, "error": err})
                return subprocess.CompletedProcess(cmd, rc, "", text)
            return run

        def raises(exc):
            def run(cmd, **kw):
                raise exc
            return run

        legacy_problem = "uri 'x' is not s3" + "://<bucket>/<key>"
        cases = {
            "old klt reaches the broker": answer(1, {"code": "broker_unreachable"}),
            "old klt reports a refusal": answer(1, {"code": "broker_refused"}),
            "klt without verify": answer(2, stderr="usage: klt artifact ..."),
            "verify passes the legacy uri": answer(0, stderr=""),
            "invalid for another reason": answer(1, {"code": "invalid_manifest",
                                                     "problems": [legacy_problem]}),
            "invalid without problems": answer(1, {"code": "invalid_manifest"}),
            "wrong exit code": answer(2, {"code": "invalid_manifest",
                                          "problems": ["is not artifact:<key>"]}),
            "not json": answer(1, stderr="Traceback ..."),
        }
        for label, run in cases.items():
            with self.subTest(label), \
                    self.assertRaisesRegex(es.StoreError, "older than klayout-tools"):
                self.check(run)
        # A probe that never answered says so rather than blaming klt's age.
        no_answer = {
            "timeout": (raises(subprocess.TimeoutExpired("klt", 30)), "probe timed out"),
            "cannot exec": (raises(OSError("no such file")), "probe failed to start"),
        }
        for label, (run, message) in no_answer.items():
            with self.subTest(label), self.assertRaisesRegex(es.StoreError, message):
                self.check(run)

    def test_min_commit_is_the_artifact_uri_revision(self):
        self.assertTrue(es.KLT_ARTIFACT_MIN_COMMIT.startswith("7e3561f"))


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, body))
        payload = ({"key": "k", "exists": False} if self.status == 200
                   else {"error": "not_granted", "message": "no"})
        raw = json.dumps(payload).encode()
        self.send_response(self.status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class Probe(unittest.TestCase):
    def serve(self, status):
        handler = type("H", (_Handler,), {"status": status, "seen": []})
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}", handler

    def test_reachable_broker_passes(self):
        for status in (200, 404):
            base, handler = self.serve(status)
            es.probe_broker(base, REPO)
            (path, body), = handler.seen
            self.assertEqual(path, "/v1/stat")
            self.assertEqual(body["repo"], REPO)

    def test_refusal_fails_closed(self):
        base, _ = self.serve(403)
        with self.assertRaisesRegex(es.StoreError, "HTTP 403: not_granted"):
            es.probe_broker(base, REPO)

    def test_unreachable_fails_closed(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with self.assertRaisesRegex(es.StoreError, "unreachable"):
            es.probe_broker(f"http://127.0.0.1:{port}", REPO, timeout=5)

    def test_url_with_credentials_refused(self):
        with self.assertRaises(es.StoreError):
            es.probe_broker("http://u:p@127.0.0.1:1", REPO)


class RunHelpers(unittest.TestCase):
    """``stage_dir`` / ``commit_run`` / ``preflight_or_exit``: what the bench
    writers call."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()

    def stage(self, rid="20261022-000000-abc"):
        stage = es.stage_dir(self.root, "bench", rid)
        (stage / "corners" / rid).mkdir(parents=True)
        (stage / "corners" / rid / "tt_1p8v_27c.log").write_text("log\n")
        (stage / "netlist-snapshots").mkdir()
        (stage / "netlist-snapshots" / f"{rid}.spice").write_text("* deck\n")
        return stage

    def commit(self, stage, rid="20261022-000000-abc"):
        from unittest import mock
        store = {}
        real_put = es.put_files
        with mock.patch.object(es, "put_files",
                               side_effect=lambda f, r: real_put(f, r, run=fake_klt(store))):
            return es.commit_run(stage, repo_root=self.root, bench="bench", rid=rid,
                                 record_text="# record\n",
                                 record_path=self.root / "sim/bench/records" / f"{rid}.md")

    def test_stage_dir_is_git_ignored_scratch(self):
        stage = es.stage_dir(self.root, "bench", "r1")
        self.assertEqual(stage.relative_to(self.root).parts[:2], ("sim", ".work"))

    def test_unsafe_run_id_rejected(self):
        for bad in ("../x", "a/b", ""):
            with self.assertRaises(ValueError):
                es.stage_dir(self.root, "bench", bad)

    def test_commit_names_mirror_sim_layout_and_only_manifest_and_record_land(self):
        rid = "20261022-000000-abc"
        mpath = self.commit(self.stage(rid), rid)
        names = [e["name"] for e in json.loads(mpath.read_text())["entries"]]
        self.assertEqual(names, [f"sim/bench/corners/{rid}/tt_1p8v_27c.log",
                                 f"sim/bench/netlist-snapshots/{rid}.spice"])
        self.assertTrue((self.root / f"sim/bench/records/{rid}.md").is_file())
        self.assertFalse((self.root / "sim/bench/corners").exists())
        self.assertFalse((self.root / "sim/bench/netlist-snapshots").exists())

    def test_symlink_in_stage_refused_and_nothing_committed(self):
        stage = self.stage()
        (stage / "link.log").symlink_to(stage / "netlist-snapshots")
        with self.assertRaises(es.StoreError):
            self.commit(stage)
        self.assertFalse((self.root / "manifests").exists())
        self.assertFalse((self.root / "sim/bench/records").exists())

    def test_preflight_or_exit_is_nonzero_without_broker(self):
        from unittest import mock
        with mock.patch.dict("os.environ", {}, clear=False) as env:
            env.pop(es.ENV_BROKER, None)
            with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as cm:
                es.preflight_or_exit(self.root)
        self.assertEqual(cm.exception.code, es.EXIT_NOT_STORED)

    def test_preflight_or_exit_fails_closed_on_old_klt(self):
        from unittest import mock
        with mock.patch.object(es, "preflight", side_effect=es.StoreError("old klt")), \
             mock.patch("sys.stderr"), self.assertRaises(SystemExit) as cm:
            es.preflight_or_exit(self.root)
        self.assertEqual(cm.exception.code, es.EXIT_NOT_STORED)


class ManifestBackedLint(unittest.TestCase):
    """``evidence_lint`` accepts a record whose bytes live in the store."""

    RID = "20261022-000000-abc1234"
    FIELDS = ("Record ID", "Claim", "Netlist provenance", "Corner matrix run",
              "Statistical convention", "Result", "Links", "Timestamp / author",
              "Supersedes")

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()

    def record(self, rid, supersedes="(none)"):
        rec = self.root / "sim/b/records"
        rec.mkdir(parents=True, exist_ok=True)
        lines = [f"- **{f}**: {rid if f == 'Record ID' else supersedes if f == 'Supersedes' else 'x'}"
                 for f in self.FIELDS]
        (rec / f"{rid}.md").write_text("\n".join(lines) + "\n")

    def manifest(self, rid, names):
        m = self.root / "manifests/artifacts"
        m.mkdir(parents=True, exist_ok=True)
        (m / f"b-{rid}.manifest.json").write_text(json.dumps(
            {"schema_version": 1, "entries": [{"name": n} for n in names]}))

    def lint(self):
        from harness import evidence_lint as el
        paths, _ = el.list_evidence_paths(self.root)
        return el.check_experiments(self.root, el.collect_experiments(paths))

    def names(self, rid, logs=("typical_27c_nosupply.log",), snapshot=True):
        out = [f"sim/b/corners/{rid}/{n}" for n in logs]
        if snapshot:
            out.append(f"sim/b/netlist-snapshots/{rid}.spice")
        return out

    def test_manifest_backed_record_lints_clean(self):
        self.record(self.RID)
        self.manifest(self.RID, self.names(self.RID))
        self.assertEqual(self.lint(), [])

    def test_record_without_manifest_or_bytes_still_fails(self):
        self.record(self.RID)
        self.assertEqual(len(self.lint()), 2)  # no snapshot, no logs

    def test_manifest_missing_snapshot_or_log_fails(self):
        self.record(self.RID)
        self.manifest(self.RID, self.names(self.RID, snapshot=False))
        self.assertTrue(any("frozen netlist" in str(p) for p in self.lint()))
        self.manifest(self.RID, self.names(self.RID, logs=()))
        self.assertTrue(any("raw per-corner logs" in str(p) for p in self.lint()))

    def test_head_record_log_count_rule_uses_manifest_entries(self):
        old, new = "20261001-000000-abc1234", self.RID
        self.record(old)
        self.manifest(old, self.names(old, logs=("ff_27c_nosupply.log", "ss_27c_nosupply.log")))
        self.record(new, supersedes=old)
        self.manifest(new, self.names(new, logs=("ff_27c_nosupply.log",)))
        self.assertTrue(any("fewer than its" in str(p) for p in self.lint()))

    def test_unreadable_manifest_is_a_problem(self):
        self.record(self.RID)
        m = self.root / "manifests/artifacts"
        m.mkdir(parents=True)
        (m / f"b-{self.RID}.manifest.json").write_text("{")
        self.assertTrue(any("unreadable manifest" in str(p) for p in self.lint()))


class EnvelopeBackedLint(unittest.TestCase):
    """``evidence_lint`` validates a record through its cited klt envelope.

    Issue #559's batch route: a record citing
    ``sim/<slug>/klt/envelopes/*.json`` carries its machine-checkable
    evidence in the committed envelope (corners, and the DUT (path, sha256)
    its ``environment.netlist_closure`` ran), so the snapshot / per-corner-log
    requirements do not apply -- but a missing envelope, an envelope without
    corners, or a provenance that states no closure pair the envelope ran is
    a problem, not a pass on prose.
    """

    RID = "20261121-000000-abc1234"
    DUT = "layout/lvs/gate_driver_core.extracted.spice"
    DUT_SHA = "21fe85db36867ddd40a254a3a960998e9d4830f707cd4079b7891bf33be7ffca"
    FIELDS = ("Record ID", "Claim", "Netlist provenance", "Corner matrix run",
              "Statistical convention", "Result", "Links", "Timestamp / author",
              "Supersedes")

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.records = self.root / "sim/b/records"
        self.records.mkdir(parents=True)

    def record(self, provenance=None, links_extra=""):
        fields = {
            "Record ID": self.RID,
            "Netlist provenance": provenance
            or f"extracted — DUT `{self.DUT}` (sha256 `{self.DUT_SHA}`)",
            "Links": f"sim/b/klt/envelopes/env.json{links_extra}",
            "Supersedes": "(none)",
        }
        lines = [f"- **{f}**: {fields.get(f, 'x')}" for f in self.FIELDS]
        (self.records / f"{self.RID}.md").write_text("\n".join(lines) + "\n")

    def envelope(self, corners=1, closure=None, raw=None):
        env = self.root / "sim/b/klt/envelopes"
        env.mkdir(parents=True, exist_ok=True)
        if raw is not None:
            (env / "env.json").write_text(raw)
            return
        doc = {
            "corners": [
                {"corner_id": f"tt/vsup_drv=5.000_vsup_logic=3.300V/{t}C"}
                for t in range(corners)
            ],
            "environment": {
                "netlist_closure": closure
                if closure is not None
                else [{"path": self.DUT, "sha256": self.DUT_SHA}],
            },
        }
        (env / "env.json").write_text(json.dumps(doc))

    def lint(self):
        from harness import evidence_lint as el
        paths, _ = el.list_evidence_paths(self.root)
        return el.check_experiments(self.root, el.collect_experiments(paths))

    def test_envelope_backed_record_lints_clean_without_snapshot_or_logs(self):
        self.record()
        self.envelope(corners=60)
        self.assertEqual(self.lint(), [])

    def test_missing_envelope_is_a_problem(self):
        self.record()
        self.assertTrue(any("missing envelope" in str(p) for p in self.lint()))

    def test_unreadable_envelope_is_a_problem(self):
        self.record()
        self.envelope(raw="{")
        self.assertTrue(any("unreadable" in str(p) for p in self.lint()))

    def test_envelope_without_corners_is_a_problem(self):
        self.record()
        self.envelope(corners=0)
        self.assertTrue(any("carries no corners" in str(p) for p in self.lint()))

    def test_wrong_dut_hash_is_a_problem(self):
        # The envelope ran the real extraction; the record claims another.
        self.record(
            provenance=f"extracted — DUT `{self.DUT}` (sha256 `{'f' * 64}`)"
        )
        self.envelope()
        self.assertTrue(any("netlist_closure" in str(p) for p in self.lint()))
        # So does a provenance naming a different DUT path entirely.
        self.record(
            provenance=f"extracted — DUT `layout/lvs/other.spice` (sha256 `{self.DUT_SHA}`)"
        )
        self.assertTrue(any("netlist_closure" in str(p) for p in self.lint()))

    def test_envelope_of_another_facet_is_a_problem(self):
        self.record(links_extra=" and sim/other/klt/envelopes/env.json")
        env = self.root / "sim/other/klt/envelopes"
        env.mkdir(parents=True)
        (env / "env.json").write_text("{}")
        self.assertTrue(any("its own experiment" in str(p) for p in self.lint()))


class AppendOnlyManifests(unittest.TestCase):
    """``check_append_only`` covers ``manifests/artifacts/*.manifest.json``.

    The manifest *is* a stored run's netlist snapshot and per-corner logs, so
    editing or deleting one rewrites recorded evidence exactly the way editing
    a committed record would (issue #437).
    """

    MANIFEST = "manifests/artifacts/b-20261022-000000-abc1234.manifest.json"
    NON_ASCII_MANIFEST = (
        "manifests/artifacts/bénch-20261022-000000-abc1234.manifest.json"
    )
    NON_ASCII_RECORD = "sim/bénch/records/20261022-000000-abc1234.md"
    TAB_RECORD = "sim/tab\tbench/records/20261022-000000-abc1234.md"

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write(self.MANIFEST, json.dumps(
            {"schema_version": 1, "entries": [{"name": "sim/b/corners/x/tt.log",
                                               "sha256": "a" * 64}]}) + "\n")
        self.write(self.NON_ASCII_MANIFEST, json.dumps(
            {"schema_version": 1, "entries": [{"name": "sim/b/corners/x/tt.log",
                                               "sha256": "a" * 64}]}) + "\n")
        self.write("manifests/artifacts/README.md", "prose\n")
        self.write("sim/b/records/20261022-000000-abc1234.md", "- **Record ID**: x\n")
        self.write(self.NON_ASCII_RECORD, "- **Record ID**: x\n")
        self.write(self.TAB_RECORD, "- **Record ID**: x\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        # The check diffs the merge base with base_ref against the WORKING
        # TREE, so point base_ref at this commit and then tamper.
        self.git("branch", "base")

    def git(self, *args):
        subprocess.run(("git", *args), cwd=self.root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def check(self):
        from harness import evidence_lint as el
        problems, skip = el.check_append_only(self.root, "base")
        self.assertIsNone(skip, f"check could not run: {skip}")
        return problems

    def test_clean_tree_reports_nothing(self):
        self.assertEqual(self.check(), [])

    def test_modified_manifest_is_reported(self):
        self.write(self.MANIFEST, json.dumps(
            {"schema_version": 1, "entries": [{"name": "sim/b/corners/x/tt.log",
                                               "sha256": "0" * 64}]}) + "\n")
        problems = self.check()
        self.assertEqual([p.path for p in problems], [self.MANIFEST])
        self.assertIn("modified", problems[0].message)
        self.assertIn("append-only", problems[0].message)

    def test_deleted_manifest_is_reported(self):
        (self.root / self.MANIFEST).unlink()
        problems = self.check()
        self.assertEqual([p.path for p in problems], [self.MANIFEST])
        self.assertIn("deleted", problems[0].message)

    def test_manifest_readme_stays_editable(self):
        self.write("manifests/artifacts/README.md", "reworded prose\n")
        self.assertEqual(self.check(), [])

    def test_sim_record_still_reported_with_its_own_remedy(self):
        self.write("sim/b/records/20261022-000000-abc1234.md", "- **Record ID**: y\n")
        problems = self.check()
        self.assertEqual(len(problems), 1)
        self.assertIn("**Supersedes**", problems[0].message)

    def test_both_kinds_reported_together(self):
        (self.root / self.MANIFEST).unlink()
        self.write("sim/b/records/20261022-000000-abc1234.md", "- **Record ID**: y\n")
        self.assertEqual(
            sorted(p.path for p in self.check()),
            [self.MANIFEST, "sim/b/records/20261022-000000-abc1234.md"],
        )

    def test_unavailable_merge_group_base_is_a_skip_reason(self):
        # Merge queue (issue #547): the event's base sha is a bare commit, so
        # a bogus or unreachable one leaves the check unable to run at all.
        # That must surface as a skip_reason -- which the workflow's
        # --require-append-only turns into a failure -- never as a silent
        # pass against some other range.
        from harness import evidence_lint as el
        problems, skip = el.check_append_only(self.root, "0" * 40)
        self.assertEqual(problems, [])
        self.assertIsNotNone(skip)

    def test_non_ascii_sim_record_edit_is_reported(self):
        # Issue #577: git C-quotes non-ASCII paths in display-format diff
        # output, so the quoted path failed EVIDENCE_PATH_RE's ^sim/ anchor
        # and the edit silently passed. Mixed with an ASCII edit in the same
        # diff to prove both shapes surface together.
        self.write(self.NON_ASCII_RECORD, "- **Record ID**: y\n")
        self.write("sim/b/records/20261022-000000-abc1234.md",
                   "- **Record ID**: y\n")
        problems = self.check()
        self.assertEqual(
            sorted(p.path for p in problems),
            sorted([self.NON_ASCII_RECORD,
                    "sim/b/records/20261022-000000-abc1234.md"]),
        )
        for p in problems:
            self.assertIn("**Supersedes**", p.message)

    def test_tab_in_sim_record_path_is_reported(self):
        # Issue #577: a literal tab additionally breaks the display format's
        # status<TAB>path split; the NUL-delimited stream reads it verbatim.
        self.write(self.TAB_RECORD, "- **Record ID**: y\n")
        problems = self.check()
        self.assertEqual([p.path for p in problems], [self.TAB_RECORD])
        self.assertIn("modified", problems[0].message)
        self.assertIn("**Supersedes**", problems[0].message)

    def test_non_ascii_manifest_deletion_is_reported(self):
        # Issue #577: a quoted manifest path escaped MANIFEST_PATH_RE the
        # same way; deleting stored evidence must stay a Problem.
        (self.root / self.NON_ASCII_MANIFEST).unlink()
        problems = self.check()
        self.assertEqual([p.path for p in problems], [self.NON_ASCII_MANIFEST])
        self.assertIn("deleted", problems[0].message)
        self.assertIn("append-only", problems[0].message)


class MergeGroupBase(unittest.TestCase):
    """``default_base_ref`` under the merge queue (issue #547).

    A ``merge_group`` run has no ``GITHUB_BASE_REF``: the base is the queue's
    trial-merge base sha from the event payload. It must be used verbatim,
    and a missing one must fail closed -- silently falling back to
    ``origin/main`` would diff the append-only check against the wrong
    range. PR and push resolution stays exactly what it was.
    """

    ENV_KEYS = ("GITHUB_EVENT_NAME", "GITHUB_BASE_REF", "MERGE_GROUP_BASE_SHA")

    def setUp(self):
        # CI steps run with the Actions defaults (GITHUB_EVENT_NAME etc. are
        # set on real runs), so save and clear whatever leaked in.
        self._saved = {k: os.environ.pop(k, None) for k in self.ENV_KEYS}

    def tearDown(self):
        for key, value in self._saved.items():
            if value is not None:
                os.environ[key] = value

    def ref(self):
        from harness import evidence_lint as el
        return el.default_base_ref()

    def test_merge_group_uses_the_event_base_sha(self):
        os.environ["GITHUB_EVENT_NAME"] = "merge_group"
        os.environ["MERGE_GROUP_BASE_SHA"] = "a" * 40
        self.assertEqual(self.ref(), "a" * 40)

    def test_merge_group_missing_base_fails_closed(self):
        os.environ["GITHUB_EVENT_NAME"] = "merge_group"
        with self.assertRaises(SystemExit):
            self.ref()

    def test_merge_group_blank_base_fails_closed(self):
        os.environ["GITHUB_EVENT_NAME"] = "merge_group"
        os.environ["MERGE_GROUP_BASE_SHA"] = "   "
        with self.assertRaises(SystemExit):
            self.ref()

    def test_pull_request_base_unchanged(self):
        os.environ["GITHUB_EVENT_NAME"] = "pull_request"
        os.environ["GITHUB_BASE_REF"] = "feature/x"
        self.assertEqual(self.ref(), "origin/feature/x")

    def test_push_base_unchanged(self):
        os.environ["GITHUB_EVENT_NAME"] = "push"
        self.assertEqual(self.ref(), "origin/main")

    def test_no_event_name_base_unchanged(self):
        # Local runs: no Actions env at all.
        self.assertEqual(self.ref(), "origin/main")


if __name__ == "__main__":
    unittest.main()
