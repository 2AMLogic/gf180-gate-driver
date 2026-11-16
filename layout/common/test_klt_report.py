"""Issue #472: both report legs go through one checked failure block.

``klt_report`` is the single ``klt`` invocation every ``layout/`` signoff runner
shares. Two facts are pinned here:

1. **Both** legs of :func:`klt_report.run_klt_report` are checked against the
   caller's ``ok_codes``. The ``--format text`` leg's exit code used to be
   discarded while its stdout was written straight into append-only signoff
   evidence, so a failing text render could land bytes in a record that
   ``signoff_store``'s fail-closed contract exists to prevent.
2. There is exactly **one** copy of the failure block. ``run_klt`` and both
   report legs route through :func:`klt_report._raise_if_bad`, so the two entry
   points cannot drift apart again (they already had: ``str(argv[1])`` vs. a
   raw ``argv[1]``, a defaulted vs. a required ``ok_codes``).

Stdlib only, and no ``klt``: a two-case ``/bin/sh`` stub on disk plays the
binary, so the real ``subprocess.run`` path is exercised with no PDK and no
klayout. Nothing is written outside a temp dir.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import klt_report  # noqa: E402

OK_JSON = '{"violations": 0}'


def _klt_stub(
    directory: Path,
    *,
    json_rc: int = 0,
    text_rc: int = 0,
    json_out: str = OK_JSON,
    text_out: str = "DRC clean\n",
    json_err: str = "",
    text_err: str = "",
) -> str:
    """Write an executable ``klt`` stub that answers each ``--format`` leg.

    ``run_klt_report`` appends ``--format json`` / ``--format text`` last, so
    the stub dispatches on the tail of its own argv.
    """
    path = directory / "klt"
    path.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f"*'--format json') printf %s {shlex.quote(json_out)};"
        f" printf %s {shlex.quote(json_err)} >&2; exit {json_rc} ;;\n"
        f"*'--format text') printf %s {shlex.quote(text_out)};"
        f" printf %s {shlex.quote(text_err)} >&2; exit {text_rc} ;;\n"
        "*) echo 'stub: unexpected argv' >&2; exit 97 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return str(path)


class KltReportBothLegsChecked(unittest.TestCase):
    """json ok + text bad must raise; json ok + text ok must not change."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name).resolve()
        # Stands in for the caller's signoff stage dir: the module writes
        # nothing itself, so this must still be empty after a failed run.
        self.stage = self.tmp / "stage"
        self.stage.mkdir()

    def run_report(self, *, ok_codes=(0, 3), **stub):
        klt = _klt_stub(self.tmp, **stub)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                report = klt_report.run_klt_report(
                    self.tmp, [klt, "drc", "blk.gds"], ok_codes=ok_codes
                )
            except klt_report.KltRunError as exc:
                return None, exc, out.getvalue(), err.getvalue()
        return report, None, out.getvalue(), err.getvalue()

    def test_both_legs_ok_returns_json_text_and_payload(self):
        report, exc, _, err = self.run_report()
        self.assertIsNone(exc)
        self.assertEqual(report.json, OK_JSON)
        self.assertEqual(report.text, "DRC clean\n")
        self.assertEqual(report.payload, {"violations": 0})
        self.assertEqual(err, "")

    def test_tolerated_nonzero_exit_on_both_legs_still_returns(self):
        # The real DRC/LVS path: exit 3 is "violations found", not a failure.
        report, exc, _, _ = self.run_report(json_rc=3, text_rc=3)
        self.assertIsNone(exc)
        self.assertEqual(report.payload, {"violations": 0})

    def test_text_leg_outside_ok_codes_raises(self):
        report, exc, out, err = self.run_report(
            text_rc=2, text_out="half a table", text_err="klt: no text formatter\n"
        )
        self.assertIsNone(report)
        self.assertIsNotNone(exc)
        self.assertEqual(str(exc), "drc")
        # The failure block is the *text* leg's output, and names that leg.
        self.assertIn("klt: no text formatter", err)
        self.assertIn("error: klt drc --format text failed (exit 2)", err)
        self.assertIn("half a table", out)

    def test_text_leg_failure_writes_no_bytes(self):
        # The raise reaches the caller before it can stage report.text, so the
        # append-only record gets nothing from a failed render.
        report, exc, _, _ = self.run_report(text_rc=2)
        self.assertIsNone(report)
        self.assertIsNotNone(exc)
        self.assertEqual(list(self.stage.iterdir()), [])

    def test_json_leg_outside_ok_codes_raises_and_names_its_leg(self):
        report, exc, _, err = self.run_report(
            json_rc=2, json_err="klt: bad deck\n", text_rc=0
        )
        self.assertIsNone(report)
        self.assertEqual(str(exc), "drc")
        self.assertIn("klt: bad deck", err)
        self.assertIn("error: klt drc --format json failed (exit 2)", err)

    def test_json_leg_is_checked_before_the_text_leg(self):
        # Both legs bad: the json failure is the one reported, as before.
        _, exc, _, err = self.run_report(json_rc=2, text_rc=4)
        self.assertIsNotNone(exc)
        self.assertIn("--format json failed (exit 2)", err)
        self.assertNotIn("--format text", err)

    def test_both_formats_run_before_either_is_checked(self):
        # The module's documented ordering: a json failure must not skip the
        # text render (the two runs are what a caller's record is made of).
        klt = _klt_stub(self.tmp, json_rc=2)
        calls = []
        real = subprocess.run

        def spy(argv, **kwargs):
            calls.append(list(argv)[-2:])
            return real(argv, **kwargs)

        patcher = mock.patch.object(subprocess, "run", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(klt_report.KltRunError):
                    klt_report.run_klt_report(
                        self.tmp, [klt, "drc", "blk.gds"], ok_codes=(0, 3)
                    )
        self.assertEqual(calls, [["--format", "json"], ["--format", "text"]])


class RunKltUnchanged(unittest.TestCase):
    """``run_klt``'s own behaviour is what the report legs standardise on."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name).resolve()

    def single_format_stub(self, rc: int) -> str:
        path = self.tmp / "klt"
        path.write_text(
            f"#!/bin/sh\nprintf 'out\\n'; printf 'err\\n' >&2; exit {rc}\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return str(path)

    def test_returns_completed_process_on_a_tolerated_exit(self):
        proc = klt_report.run_klt(
            self.tmp, [self.single_format_stub(3), "lvs"], ok_codes=(0, 3)
        )
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(proc.stdout, "out\n")

    def test_bad_exit_keeps_the_single_format_message_shape(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with self.assertRaises(klt_report.KltRunError) as cm:
                klt_report.run_klt(self.tmp, [self.single_format_stub(1), "lvs"])
        self.assertEqual(str(cm.exception), "lvs")
        # No `--format` suffix: a single-format run has only one leg to name.
        self.assertIn("error: klt lvs failed (exit 1)\n", err.getvalue())
        self.assertIn("err", err.getvalue())
        self.assertIn("out", out.getvalue())

    def test_default_ok_codes_rejects_a_nonzero_exit(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(klt_report.KltRunError):
                    klt_report.run_klt(self.tmp, [self.single_format_stub(3), "lvs"])


class OneFailureBlock(unittest.TestCase):
    """The structural facts: one shared check, one ``ok_codes`` shape."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name).resolve()

    def checked_legs(self, call) -> list[int]:
        """Return the exit codes handed to ``_raise_if_bad`` by ``call``."""
        seen: list[int] = []
        real = klt_report._raise_if_bad

        def spy(argv, proc, ok_codes, **kwargs):
            seen.append(proc.returncode)
            return real(argv, proc, ok_codes, **kwargs)

        patcher = mock.patch.object(klt_report, "_raise_if_bad", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        call()
        return seen

    def test_run_klt_routes_through_the_shared_check(self):
        klt = _klt_stub(self.tmp)
        seen = self.checked_legs(
            lambda: klt_report.run_klt(self.tmp, [klt, "drc", "--format", "json"])
        )
        self.assertEqual(seen, [0])

    def test_both_report_legs_route_through_the_shared_check(self):
        # The regression this issue closes: two legs run, two legs checked.
        klt = _klt_stub(self.tmp, json_rc=3, text_rc=3)
        seen = self.checked_legs(
            lambda: klt_report.run_klt_report(
                self.tmp, [klt, "drc", "blk.gds"], ok_codes=(0, 3)
            )
        )
        self.assertEqual(seen, [3, 3])

    def test_ok_codes_has_the_same_shape_in_both_entry_points(self):
        for name in ("run_klt", "run_klt_report"):
            with self.subTest(entry_point=name):
                param = inspect.signature(getattr(klt_report, name)).parameters[
                    "ok_codes"
                ]
                self.assertEqual(param.kind, inspect.Parameter.KEYWORD_ONLY)
                self.assertEqual(param.default, (0,))

    def test_module_has_exactly_one_failure_block(self):
        source = (HERE / "klt_report.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("raise KltRunError("), 1)
        self.assertEqual(source.count("failed (exit "), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
