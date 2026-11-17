#!/usr/bin/env python3
"""Issue #468: the shared negative-control pass/fail epilogue.

Pins the one skeleton the four ``layout/`` negative controls now return
through (``layout/drc/deck_negative_control.py``,
``layout/lvs/lvs_negative_control.py``, ``layout/erc/erc_negative_control.py``,
``layout/ground_rail_negative_control.py``), so the verdict half of that
family cannot drift the way the ``klt``-invocation half did (#451).

What is pinned here is the part that is identical across all four and was
previously re-typed in each: every ``FAIL:`` line goes to stderr, the
caller's ``invalidates`` sentence goes to stderr and returns 1, the caller's
``confirms`` sentence goes to stdout and returns 0, and the two streams never
mix. Stdlib only.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import control_verdict as cv  # noqa: E402

INVALIDATES = "The deck did not flag a fixture it must flag -- not evidence until explained."
CONFIRMS = "ok: the deck flagged the known-bad fixture -- a real verdict"


def run(failures):
    """Call the helper, returning ``(exit_code, stdout, stderr)``."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cv.control_verdict(failures, invalidates=INVALIDATES, confirms=CONFIRMS)
    return code, out.getvalue(), err.getvalue()


class NoFailures(unittest.TestCase):
    """The pass arm: one ``confirms`` line on stdout, exit 0, stderr silent."""

    def test_returns_zero(self):
        code, _, _ = run([])
        self.assertEqual(code, 0)

    def test_prints_confirms_to_stdout(self):
        _, out, _ = run([])
        self.assertEqual(out, CONFIRMS + "\n")

    def test_stderr_stays_empty(self):
        # The whole point of a control's exit 0 is that it says nothing
        # alarming: an empty failures list must not print a FAIL: line.
        _, _, err = run([])
        self.assertEqual(err, "")

    def test_empty_tuple_is_also_a_pass(self):
        # Callers build `failures` as a list, but the no-op-on-empty case is
        # the one the four copies used to express incidentally (two looped
        # before the `if`, two inside it). Any empty sequence passes.
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cv.control_verdict((), invalidates=INVALIDATES, confirms=CONFIRMS)
        self.assertEqual((code, out.getvalue(), err.getvalue()), (0, CONFIRMS + "\n", ""))


class WithFailures(unittest.TestCase):
    """The fail arm: every FAIL: line then ``invalidates``, exit 1, stdout silent."""

    def test_returns_one(self):
        code, _, _ = run(["status was 'clean'"])
        self.assertEqual(code, 1)

    def test_prints_every_failure_then_invalidates_on_stderr(self):
        _, _, err = run(["first thing", "second thing"])
        self.assertEqual(
            err,
            "FAIL: first thing\nFAIL: second thing\n" + INVALIDATES + "\n",
        )

    def test_failure_order_is_the_callers_order(self):
        # The controls append assertions in the order a reader should take
        # them; the helper must not sort or dedupe them.
        _, _, err = run(["c", "a", "b", "a"])
        self.assertEqual(
            [line for line in err.splitlines() if line.startswith("FAIL: ")],
            ["FAIL: c", "FAIL: a", "FAIL: b", "FAIL: a"],
        )

    def test_confirms_is_never_printed(self):
        # A control that failed must not also emit its "real verdict" line --
        # that line is the claim the failure invalidates.
        _, out, err = run(["something broke"])
        self.assertEqual(out, "")
        self.assertNotIn(CONFIRMS, err)

    def test_invalidates_comes_after_all_failures(self):
        # "Report the failures, then explain what they invalidate" -- the
        # loop-placement question #468 settled.
        _, _, err = run(["one", "two"])
        lines = err.splitlines()
        self.assertEqual(lines[-1], INVALIDATES)
        self.assertTrue(all(line.startswith("FAIL: ") for line in lines[:-1]))


if __name__ == "__main__":
    unittest.main()
