#!/usr/bin/env python3
"""Unit tests for ``klt_env.require_klt`` and the runners' ``--klt`` plumbing.

Stdlib-only, no ``klt``, no PDK: pins the two resolver contracts every
report runner depends on (an explicit override wins even when nothing named
``klt`` is on ``PATH``; a missing ``klt`` prints the install hint and exits
1 -- the prerequisite-failure exit code the runners document), and the
argparse plumbing that feeds it in ``run_lvs.py``, ``run_pex_extract.py``
and ``run_drc.py`` (issue #486). ``run_erc.py`` carried the flag before any
of them was covered -- these tests pin the shared resolver entry point
rather than extending that gap.

The runner tests use ``build_parser()`` directly (the seam the flag is
threaded through), so they prove the flag *reaches the resolver argument*
without running ``klt``: omitting ``--klt`` parses to ``None`` (today's
PATH-resolved behavior, unchanged), passing it lands in ``args.klt``
verbatim.
"""

from __future__ import annotations

import contextlib
import io
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import klt_env  # noqa: E402  (path set above)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The runners are plain scripts, not a package: put each of their
# directories on sys.path (as the scripts themselves do for layout/common)
# and import the modules under their file names.
for _sub in ("lvs", "drc"):
    sys.path.insert(0, str(_REPO_ROOT / "layout" / _sub))

import run_drc  # noqa: E402  (paths set above)
import run_lvs  # noqa: E402
import run_pex_extract  # noqa: E402


def _klt_help(parser) -> str:
    """The help string of a parser's ``--klt`` argument (fails if absent)."""
    for action in parser._actions:
        if action.dest == "klt":
            return action.help
    raise AssertionError("parser has no --klt argument")


class RequireKltTest(unittest.TestCase):
    """The resolver contract in klt_env.require_klt()."""

    def setUp(self) -> None:
        self._old_path = os.environ.get("PATH")
        self._empty = tempfile.mkdtemp(prefix="klt-env-test-empty-")
        # A PATH with nothing named `klt` on it, so which() returns None
        # deterministically regardless of the host's real install.
        os.environ["PATH"] = self._empty
        self.addCleanup(self._restore_path)

    def _restore_path(self) -> None:
        if self._old_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = self._old_path

    def test_override_wins_without_path(self):
        # The contract --klt depends on: an explicit override is returned
        # as-is (not existence-checked), even with no klt on PATH at all.
        self.assertEqual(klt_env.require_klt("/x/klt"), "/x/klt")

    def test_missing_klt_prints_hint_and_exits_1(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                klt_env.require_klt()
        self.assertEqual(cm.exception.code, 1)
        message = stderr.getvalue()
        self.assertIn("'klt' not found on PATH", message)
        # The hint must keep pointing at the pinned-install guidance --
        # an unpinned install can silently change the deck (layout/README.md).
        self.assertIn("Reproducibility: pin the klt install", message)

    def test_klt_on_path_is_returned(self):
        bindir = tempfile.mkdtemp(prefix="klt-env-test-bin-")
        stub = Path(bindir, "klt")
        stub.write_text("#!/bin/sh\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.environ["PATH"] = bindir
        self.assertEqual(klt_env.require_klt(), str(stub))


class RunnerKltPlumbingTest(unittest.TestCase):
    """--klt reaches require_klt's override argument in all three runners."""

    def test_run_lvs_flag_reaches_parser(self):
        args = run_lvs.build_parser().parse_args(["x.gds", "--klt", "/x/klt"])
        self.assertEqual(args.klt, "/x/klt")

    def test_run_lvs_flag_optional(self):
        self.assertIsNone(run_lvs.build_parser().parse_args(["x.gds"]).klt)

    def test_run_pex_extract_flag_reaches_parser(self):
        args = run_pex_extract.build_parser().parse_args(["x.gds", "--klt", "/x/klt"])
        self.assertEqual(args.klt, "/x/klt")

    def test_run_pex_extract_flag_optional(self):
        self.assertIsNone(run_pex_extract.build_parser().parse_args(["x.gds"]).klt)

    def test_run_drc_flag_reaches_parser(self):
        args = run_drc.build_parser().parse_args(["x.gds", "--klt", "/x/klt"])
        self.assertEqual(args.klt, "/x/klt")

    def test_run_drc_flag_optional(self):
        self.assertIsNone(run_drc.build_parser().parse_args(["x.gds"]).klt)

    def test_help_text_matches_run_erc(self):
        # AC: same help text as run_erc.py:71-74, the pre-existing holder.
        # run_erc builds its parser inline in main(), so the expected string
        # is pinned as the literal copied from it -- a change there should
        # move this constant with it.
        reference = "path to the klt binary (default: 'klt' on PATH)"
        for parser, name in (
            (run_lvs.build_parser(), "run_lvs"),
            (run_pex_extract.build_parser(), "run_pex_extract"),
            (run_drc.build_parser(), "run_drc"),
        ):
            self.assertEqual(_klt_help(parser), reference, f"{name}'s --klt help drifted")


if __name__ == "__main__":
    unittest.main()
